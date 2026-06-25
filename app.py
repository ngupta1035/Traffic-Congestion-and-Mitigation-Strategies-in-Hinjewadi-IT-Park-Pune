"""
TrafficIQ — Production-ready Traffic Congestion Analysis Application
Supports: Auth, MySQL/SQLite, Multi-video upload, Mitigation comparison, Themes
"""

import os, json, time, warnings, threading, uuid
from datetime import datetime
from functools import wraps
from collections import defaultdict

import cv2, numpy as np, pandas as pd
from flask import (Flask, request, jsonify, render_template,
                   send_from_directory, redirect, url_for,
                   session, flash, g)
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from ultralytics import YOLO

warnings.filterwarnings("ignore")

# ── App & Config ──────────────────────────────────────────────────────────
app = Flask(__name__)
app.config.from_pyfile("config.py", silent=True)

# Defaults (override in config.py or environment)
app.config.setdefault("SECRET_KEY", os.environ.get("SECRET_KEY", "dev-secret-change-in-prod-!@#"))
app.config.setdefault("SQLALCHEMY_DATABASE_URI",
    os.environ.get("DATABASE_URL", "sqlite:///trafficiq.db"))
app.config.setdefault("SQLALCHEMY_TRACK_MODIFICATIONS", False)
app.config.setdefault("UPLOAD_FOLDER", os.path.join("static", "uploads"))
app.config.setdefault("OUTPUT_FOLDER", os.path.join("static", "outputs"))
app.config.setdefault("MAX_CONTENT_LENGTH", 500 * 1024 * 1024)   # 500 MB
app.config.setdefault("ALLOWED_EXTENSIONS", {"mp4", "avi", "mov", "mkv", "webm"})

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

# ── YOLO Model (lazy singleton) ────────────────────────────────────────────
_model = None
_model_lock = threading.Lock()

def get_model():
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                model_path = os.path.join(os.path.dirname(__file__), "yolov8n.pt")
                _model = YOLO(model_path)
    return _model

# ── Domain Constants ──────────────────────────────────────────────────────
VEHICLE_CLASSES = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck", 1: "bicycle"}
VEHICLE_WEIGHTS = {"car": 1.0, "motorcycle": 0.5, "bus": 2.5, "truck": 2.5, "bicycle": 0.3}

STRATEGIES = {
    "FREE FLOW": ["Maintain current signal timings",
                  "Monitor for upstream build-up",
                  "Schedule maintenance in off-peak windows"],
    "LIGHT":     ["Minor signal optimisation recommended",
                  "Deploy variable message signs",
                  "Promote carpooling incentives"],
    "MODERATE":  ["Extend green phases by 15–20 s",
                  "Activate alternate route guidance",
                  "Evaluate additional turning lanes"],
    "HEAVY":     ["Activate adaptive signal control (SCOOT/SCATS)",
                  "Deploy traffic wardens; consider contraflow lanes",
                  "Introduce congestion pricing"],
    "SEVERE":    ["Emergency signal override — maximise throughput",
                  "Alert police; activate incident-management protocols",
                  "Urgent capacity expansion needed"],
}

SCORE_COLORS = {
    "FREE FLOW": "#00e676", "LIGHT": "#76ff03",
    "MODERATE": "#ffea00", "HEAVY": "#ff6d00", "SEVERE": "#d50000",
}
LEVEL_ORDER = ["FREE FLOW", "LIGHT", "MODERATE", "HEAVY", "SEVERE"]

# ── Database Models ───────────────────────────────────────────────────────
class User(db.Model):
    __tablename__ = "users"
    id         = db.Column(db.Integer, primary_key=True)
    username   = db.Column(db.String(64), unique=True, nullable=False)
    email      = db.Column(db.String(120), unique=True, nullable=False)
    password   = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    analyses   = db.relationship("VideoAnalysis", backref="owner", lazy=True)

    def set_password(self, plain):
        self.password = bcrypt.generate_password_hash(plain).decode("utf-8")

    def check_password(self, plain):
        return bcrypt.check_password_hash(self.password, plain)


class VideoAnalysis(db.Model):
    __tablename__ = "video_analyses"
    id              = db.Column(db.Integer, primary_key=True)
    user_id         = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    job_id          = db.Column(db.String(36), unique=True, nullable=False)   # UUID
    filename        = db.Column(db.String(255), nullable=False)
    label           = db.Column(db.String(120), default="")                   # user-friendly name
    status          = db.Column(db.String(20), default="pending")             # pending|running|done|error
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at    = db.Column(db.DateTime)
    # Video metadata
    width           = db.Column(db.Integer)
    height          = db.Column(db.Integer)
    fps             = db.Column(db.Float)
    total_frames    = db.Column(db.Integer)
    duration_sec    = db.Column(db.Float)
    # Summary stats
    avg_score       = db.Column(db.Float)
    avg_vehicles    = db.Column(db.Float)
    dominant_level  = db.Column(db.String(20))
    peak_vehicles   = db.Column(db.Integer)
    peak_time_sec   = db.Column(db.Float)
    # JSON blobs
    vehicle_totals  = db.Column(db.Text)    # {"Cars":N, ...}
    level_pcts      = db.Column(db.Text)    # {"FREE FLOW":%, ...}
    timeseries      = db.Column(db.Text)    # {"labels":[], "scores":[], "vehicles":[]}
    distribution    = db.Column(db.Text)    # {"labels":[], "values":[], "colors":[]}
    composition     = db.Column(db.Text)    # {"labels":[], "values":[], "colors":[]}
    periods         = db.Column(db.Text)    # [{...}, ...]
    strategies      = db.Column(db.Text)    # ["...", ...]
    mitigation_tag  = db.Column(db.String(20), default="before")  # before | after
    # CSV path
    csv_path        = db.Column(db.String(255))
    error_msg       = db.Column(db.Text)


# ── Auth Helpers ──────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

def get_current_user():
    if "user_id" in session:
        return db.session.get(User, session["user_id"])
    return None

# ── Utility ───────────────────────────────────────────────────────────────
def allowed_file(filename):
    return ("." in filename and
            filename.rsplit(".", 1)[1].lower() in app.config["ALLOWED_EXTENSIONS"])

def safe_filename(filename):
    """Simple sanitiser — keep original extension."""
    base = os.path.basename(filename)
    name, ext = os.path.splitext(base)
    clean = "".join(c for c in name if c.isalnum() or c in "-_")[:60] or "video"
    return f"{clean}{ext.lower()}"

def congestion_level(vehicle_count, density_score, frame_area):
    density_ratio = density_score / max(frame_area, 1)
    score = vehicle_count * 3.5 + density_ratio * 180
    score = max(0, min(score, 100))
    if score < 20:   return "FREE FLOW", score, "#00e676"
    elif score < 40: return "LIGHT",     score, "#76ff03"
    elif score < 60: return "MODERATE",  score, "#ffea00"
    elif score < 80: return "HEAVY",     score, "#ff6d00"
    else:            return "SEVERE",    score, "#d50000"

def time_period(frame_idx, total_frames):
    p = frame_idx / max(total_frames, 1)
    if p < 0.15:   return "Early Morning"
    elif p < 0.35: return "Morning Peak"
    elif p < 0.55: return "Midday"
    elif p < 0.75: return "Evening Peak"
    elif p < 0.90: return "Night"
    else:          return "Late Night"

# ── Background Analysis Worker ────────────────────────────────────────────
def run_analysis(job_id, video_path, filename):
    """Runs in a background thread; writes result to DB when done."""
    with app.app_context():
        job = VideoAnalysis.query.filter_by(job_id=job_id).first()
        if not job:
            return
        try:
            job.status = "running"
            db.session.commit()

            mdl = get_model()
            cap = cv2.VideoCapture(video_path)
            fps          = cap.get(cv2.CAP_PROP_FPS) or 25
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            width        = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height       = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            frame_area   = width * height
            duration_sec = total_frames / fps
            SAMPLE_EVERY = max(1, int(fps))   # 1 frame per second

            records, frame_idx = [], 0
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break
                if frame_idx % SAMPLE_EVERY == 0:
                    res = mdl(frame, verbose=False, classes=list(VEHICLE_CLASSES.keys()))[0]
                    counts, density = defaultdict(int), 0.0
                    for box in res.boxes:
                        cls_id = int(box.cls[0])
                        if cls_id in VEHICLE_CLASSES:
                            vtype = VEHICLE_CLASSES[cls_id]
                            counts[vtype] += 1
                            x1, y1, x2, y2 = box.xyxy[0].tolist()
                            density += (x2 - x1) * (y2 - y1) * VEHICLE_WEIGHTS.get(vtype, 1.0)
                    total_v = sum(counts.values())
                    lvl, score, color = congestion_level(total_v, density, frame_area)
                    records.append({
                        "frame": frame_idx, "time_sec": round(frame_idx / fps, 2),
                        "total_vehicles": total_v, "cars": counts["car"],
                        "buses": counts["bus"], "trucks": counts["truck"],
                        "motorcycles": counts["motorcycle"], "bicycles": counts["bicycle"],
                        "congestion_score": round(score, 2), "congestion_level": lvl,
                        "time_period": time_period(frame_idx, total_frames),
                    })
                frame_idx += 1
            cap.release()

            if not records:
                raise ValueError("No frames could be processed")

            df = pd.DataFrame(records)
            peak_row      = df.loc[df["congestion_score"].idxmax()]
            avg_score_val = round(df["congestion_score"].mean(), 1)
            avg_vehicles_val = round(df["total_vehicles"].mean(), 1)
            dominant      = df["congestion_level"].mode()[0]
            level_counts  = df["congestion_level"].value_counts().to_dict()
            level_pcts    = {l: round(100 * level_counts.get(l, 0) / len(df), 1) for l in LEVEL_ORDER}
            vehicle_totals = {
                "Cars": int(df["cars"].sum()), "Buses": int(df["buses"].sum()),
                "Trucks": int(df["trucks"].sum()), "Motorcycles": int(df["motorcycles"].sum()),
                "Bicycles": int(df["bicycles"].sum()),
            }
            period_df = (
                df.groupby("time_period")
                  .agg(avg_score=("congestion_score", "mean"),
                       avg_v=("total_vehicles", "mean"),
                       peak=("congestion_level", lambda x: x.mode()[0]))
                  .reset_index()
                  .sort_values("avg_score", ascending=False)
            )

            # Save CSV
            os.makedirs(app.config["OUTPUT_FOLDER"], exist_ok=True)
            csv_name = f"{job_id}.csv"
            csv_path = os.path.join(app.config["OUTPUT_FOLDER"], csv_name)
            df.to_csv(csv_path, index=False)

            # Persist to DB
            job.status         = "done"
            job.completed_at   = datetime.utcnow()
            job.width          = width
            job.height         = height
            job.fps            = round(fps, 1)
            job.total_frames   = total_frames
            job.duration_sec   = round(duration_sec, 1)
            job.avg_score      = avg_score_val
            job.avg_vehicles   = avg_vehicles_val
            job.dominant_level = dominant
            job.peak_vehicles  = int(peak_row["total_vehicles"])
            job.peak_time_sec  = round(float(peak_row["time_sec"]), 1)
            job.vehicle_totals = json.dumps(vehicle_totals)
            job.level_pcts     = json.dumps(level_pcts)
            job.timeseries     = json.dumps({
                "labels": df["time_sec"].tolist(),
                "scores": df["congestion_score"].tolist(),
                "vehicles": df["total_vehicles"].tolist(),
            })
            job.distribution   = json.dumps({
                "labels": LEVEL_ORDER,
                "values": [level_pcts[l] for l in LEVEL_ORDER],
                "colors": ["#00c853", "#76ff03", "#ffea00", "#ff6d00", "#d50000"],
            })
            job.composition    = json.dumps({
                "labels": list(vehicle_totals.keys()),
                "values": list(vehicle_totals.values()),
                "colors": ["#2196F3", "#FF5722", "#9C27B0", "#FF9800", "#00BCD4"],
            })
            job.periods        = json.dumps(period_df.to_dict(orient="records"))
            job.strategies     = json.dumps(STRATEGIES[dominant])
            job.csv_path       = csv_path
            db.session.commit()

        except Exception as e:
            job = VideoAnalysis.query.filter_by(job_id=job_id).first()
            if job:
                job.status    = "error"
                job.error_msg = str(e)
                db.session.commit()

# ── Auth Routes ───────────────────────────────────────────────────────────
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm  = request.form.get("confirm", "")

        errors = []
        if len(username) < 3:
            errors.append("Username must be at least 3 characters.")
        if len(password) < 8:
            errors.append("Password must be at least 8 characters.")
        if password != confirm:
            errors.append("Passwords do not match.")
        if User.query.filter_by(username=username).first():
            errors.append("Username already taken.")
        if User.query.filter_by(email=email).first():
            errors.append("Email already registered.")

        if errors:
            return jsonify({"ok": False, "errors": errors}), 400

        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        session["user_id"]  = user.id
        session["username"] = user.username
        return jsonify({"ok": True, "redirect": url_for("dashboard")})

    return render_template("auth.html", mode="signup")


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        password   = request.form.get("password", "")

        user = (User.query.filter_by(username=identifier).first() or
                User.query.filter_by(email=identifier).first())

        if not user or not user.check_password(password):
            return jsonify({"ok": False, "errors": ["Invalid username or password."]}), 401

        session["user_id"]  = user.id
        session["username"] = user.username
        return jsonify({"ok": True, "redirect": url_for("dashboard")})

    return render_template("auth.html", mode="login")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ── Dashboard ─────────────────────────────────────────────────────────────
@app.route("/")
@login_required
def dashboard():
    user = get_current_user()
    analyses = (VideoAnalysis.query
                .filter_by(user_id=user.id)
                .order_by(VideoAnalysis.created_at.desc())
                .all())
    return render_template("dashboard.html", user=user, analyses=analyses)

# ── Upload & Queue ────────────────────────────────────────────────────────
@app.route("/upload", methods=["POST"])
@login_required
def upload():
    user = get_current_user()
    files = request.files.getlist("videos")
    label = request.form.get("label", "").strip()
    mitigation_tag = request.form.get("mitigation_tag", "before")

    if not files or all(f.filename == "" for f in files):
        return jsonify({"error": "No files selected"}), 400

    jobs = []
    for f in files:
        if not allowed_file(f.filename):
            continue
        job_id   = str(uuid.uuid4())
        filename = safe_filename(f.filename)
        # Unique path per job
        upload_dir = app.config["UPLOAD_FOLDER"]
        os.makedirs(upload_dir, exist_ok=True)
        video_path = os.path.join(upload_dir, f"{job_id}_{filename}")
        f.save(video_path)

        job = VideoAnalysis(
            user_id        = user.id,
            job_id         = job_id,
            filename       = filename,
            label          = label or filename,
            mitigation_tag = mitigation_tag,
            status         = "pending",
        )
        db.session.add(job)
        db.session.commit()

        # Fire analysis in background thread
        t = threading.Thread(target=run_analysis,
                             args=(job_id, video_path, filename),
                             daemon=True)
        t.start()
        jobs.append({"job_id": job_id, "filename": filename})

    if not jobs:
        return jsonify({"error": "No valid video files found"}), 400

    return jsonify({"ok": True, "jobs": jobs})

# ── Job Status Polling ─────────────────────────────────────────────────────
@app.route("/status/<job_id>")
@login_required
def job_status(job_id):
    user = get_current_user()
    job = VideoAnalysis.query.filter_by(job_id=job_id, user_id=user.id).first()
    if not job:
        return jsonify({"error": "Not found"}), 404
    return jsonify({
        "job_id":   job.job_id,
        "status":   job.status,
        "filename": job.filename,
        "label":    job.label,
        "error":    job.error_msg,
    })

# ── Full Analysis Result ───────────────────────────────────────────────────
@app.route("/result/<job_id>")
@login_required
def get_result(job_id):
    user = get_current_user()
    job = VideoAnalysis.query.filter_by(job_id=job_id, user_id=user.id).first()
    if not job:
        return jsonify({"error": "Not found"}), 404
    if job.status != "done":
        return jsonify({"status": job.status, "error": job.error_msg}), 200

    return jsonify({
        "job_id":   job.job_id,
        "status":   "done",
        "label":    job.label,
        "filename": job.filename,
        "mitigation_tag": job.mitigation_tag,
        "created_at": job.created_at.isoformat(),
        "meta": {
            "width": job.width, "height": job.height,
            "fps": job.fps, "total_frames": job.total_frames,
            "duration_sec": job.duration_sec,
            "filename": job.filename,
        },
        "summary": {
            "avg_score":      job.avg_score,
            "avg_vehicles":   job.avg_vehicles,
            "dominant":       job.dominant_level,
            "level_pcts":     json.loads(job.level_pcts or "{}"),
            "peak_vehicles":  job.peak_vehicles,
            "peak_time_sec":  job.peak_time_sec,
            "vehicle_totals": json.loads(job.vehicle_totals or "{}"),
            "strategies":     json.loads(job.strategies or "[]"),
            "score_color":    SCORE_COLORS.get(job.dominant_level, "#888"),
        },
        "timeseries":  json.loads(job.timeseries  or "{}"),
        "distribution":json.loads(job.distribution or "{}"),
        "composition": json.loads(job.composition  or "{}"),
        "periods":     json.loads(job.periods      or "[]"),
        "score_colors": SCORE_COLORS,
    })

# ── History List ──────────────────────────────────────────────────────────
@app.route("/history")
@login_required
def history():
    user = get_current_user()
    jobs = (VideoAnalysis.query
            .filter_by(user_id=user.id)
            .order_by(VideoAnalysis.created_at.desc())
            .all())
    result = []
    for j in jobs:
        result.append({
            "job_id":         j.job_id,
            "label":          j.label,
            "filename":       j.filename,
            "status":         j.status,
            "created_at":     j.created_at.isoformat(),
            "dominant_level": j.dominant_level,
            "avg_score":      j.avg_score,
            "mitigation_tag": j.mitigation_tag,
        })
    return jsonify(result)

# ── Comparison Endpoint ────────────────────────────────────────────────────
@app.route("/compare", methods=["POST"])
@login_required
def compare():
    user = get_current_user()
    data = request.get_json()
    before_id = data.get("before_id")
    after_id  = data.get("after_id")

    def fetch(jid):
        return VideoAnalysis.query.filter_by(job_id=jid, user_id=user.id, status="done").first()

    before = fetch(before_id)
    after  = fetch(after_id)

    if not before or not after:
        return jsonify({"error": "One or both analyses not found or not complete"}), 404

    def to_dict(j):
        return {
            "label":          j.label,
            "filename":       j.filename,
            "mitigation_tag": j.mitigation_tag,
            "avg_score":      j.avg_score,
            "avg_vehicles":   j.avg_vehicles,
            "dominant_level": j.dominant_level,
            "level_pcts":     json.loads(j.level_pcts or "{}"),
            "vehicle_totals": json.loads(j.vehicle_totals or "{}"),
            "timeseries":     json.loads(j.timeseries  or "{}"),
            "score_color":    SCORE_COLORS.get(j.dominant_level, "#888"),
        }

    b = to_dict(before)
    a = to_dict(after)

    # Improvement deltas
    score_delta   = round(a["avg_score"]    - b["avg_score"], 1)
    vehicle_delta = round(a["avg_vehicles"] - b["avg_vehicles"], 1)

    return jsonify({
        "before": b,
        "after":  a,
        "delta": {
            "score":    score_delta,
            "vehicles": vehicle_delta,
            "improved": score_delta < 0,
        },
        "score_colors": SCORE_COLORS,
        "level_order":  LEVEL_ORDER,
    })

# ── Delete Analysis ───────────────────────────────────────────────────────
@app.route("/delete/<job_id>", methods=["DELETE"])
@login_required
def delete_analysis(job_id):
    user = get_current_user()
    job = VideoAnalysis.query.filter_by(job_id=job_id, user_id=user.id).first()
    if not job:
        return jsonify({"error": "Not found"}), 404
    db.session.delete(job)
    db.session.commit()
    return jsonify({"ok": True})

# ── CSV Download ───────────────────────────────────────────────────────────
@app.route("/download/<job_id>")
@login_required
def download_csv(job_id):
    user = get_current_user()
    job = VideoAnalysis.query.filter_by(job_id=job_id, user_id=user.id, status="done").first()
    if not job or not job.csv_path:
        return jsonify({"error": "Not available"}), 404
    directory = os.path.abspath(app.config["OUTPUT_FOLDER"])
    filename  = os.path.basename(job.csv_path)
    return send_from_directory(directory, filename, as_attachment=True,
                               download_name=f"trafficiq_{job.label}.csv")

# ── Init DB ───────────────────────────────────────────────────────────────
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=False, port=5000, threaded=True)
