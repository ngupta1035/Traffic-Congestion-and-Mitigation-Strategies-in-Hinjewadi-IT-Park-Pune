# TrafficIQ — Traffic Congestion Analysis Platform

A production-ready, laptop-friendly web application for analysing traffic
congestion in videos using YOLOv8. Features authentication, database storage,
multi-video processing, before/after mitigation comparison, and a responsive
Light / Dark / System-themed dashboard.

---

## Table of Contents

1. [Features](#features)
2. [Requirements](#requirements)
3. [Installation](#installation)
4. [Database Setup](#database-setup)
5. [Running the App](#running-the-app)
6. [Usage Guide](#usage-guide)
7. [Project Structure](#project-structure)
8. [Configuration Reference](#configuration-reference)
9. [Troubleshooting](#troubleshooting)

---

## Features

| Feature | Details |
|---|---|
| 🔐 Authentication | Signup / Login with bcrypt-hashed passwords |
| 🗄 Database | SQLite (zero setup) or MySQL |
| 🎬 Multi-video upload | Queue & process multiple videos simultaneously |
| 📊 Rich analytics | Timeseries, distribution, composition charts |
| 🔄 Before/After comparison | Side-by-side charts for mitigation impact |
| 🌙 Themes | Dark, Light, System (follows OS preference) |
| 📁 History | All past analyses stored & re-viewable |
| ⬇ CSV Export | Download raw frame-level data per analysis |
| 🛡 Secure | Per-user isolation, input validation, safe filenames |

---

## Requirements

- **Python 3.9+**
- **pip** (comes with Python)
- A modern web browser (Chrome, Firefox, Edge, Safari)
- *(Optional)* MySQL 8+ if you prefer MySQL over SQLite

> **Laptop note:** YOLOv8 nano (`yolov8n.pt`) is used intentionally — it is the
> lightest model and runs in real time on CPU. Videos are sampled at 1 frame/second
> to keep memory usage low.

---

## Installation

### 1. Clone / extract the project

```
cd trafficiq
```

### 2. Create a virtual environment (recommended)

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

The first run will also download `yolov8n.pt` automatically if it is missing
(~6 MB). It is already bundled in this project.

### 4. (MySQL only) Install the MySQL driver

```bash
pip install PyMySQL cryptography
```

---

## Database Setup

### Option A — SQLite (recommended for laptops, zero setup)

Nothing to do. The database file `instance/trafficiq.db` is created
automatically when you first run the app.

### Option B — MySQL

1. Create a database:

```sql
CREATE DATABASE trafficiq CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

2. Edit `config.py` — uncomment and fill in the MySQL line:

```python
SQLALCHEMY_DATABASE_URI = "mysql+pymysql://root:YOUR_PASSWORD@localhost:3306/trafficiq"
```

All tables are created automatically on first run.

---

## Running the App

```bash
# Make sure your virtual environment is active first!
python app.py
```

Then open **http://localhost:5000** in your browser.

### First-time setup

1. Click **Sign Up** and create an account.
2. You are redirected to the dashboard automatically.

---

## Usage Guide

### Uploading a Video

1. Go to the **Upload** tab.
2. Drag & drop one or more video files, or click to browse.
3. (Optional) Enter a descriptive **Label** (e.g. "Main St — Monday 8am").
4. Choose a **Mitigation tag**: *Before* or *After*.
5. Click **Analyse Videos**.

Videos are processed in background threads — you can upload more while the first
batch is running. A live status queue shows progress.

### Viewing Results

When a job shows **Done**, click **View →** in the queue, or go to the
**Results** tab. You will see:

- Key Performance Indicators (congestion score, vehicle counts, peak)
- Congestion score timeseries and vehicle count overlay
- Level distribution doughnut chart
- Vehicle composition bar chart
- Time-period breakdown table
- Recommended mitigation strategies

### History

The **History** tab lists all your past analyses. Click **View** to reload any
result, or **Del** to delete it permanently.

### Before / After Comparison

1. Go to the **Compare** tab.
2. Select a *Before* analysis and an *After* analysis.
3. Click **Compare Results**.

You will see:
- Score delta cards (improved / worsened indicator)
- Side-by-side congestion timeseries
- Level distribution grouped bar chart
- Vehicle count and vehicle mix comparisons

---

## Project Structure

```
trafficiq/
├── app.py                  # Main Flask application
├── config.py               # Configuration (DB, secret key, folders)
├── requirements.txt        # Python dependencies
├── yolov8n.pt              # YOLOv8 nano model weights
├── README.md               # This file
│
├── templates/
│   ├── auth.html           # Login / Signup page
│   └── dashboard.html      # Main dashboard (all tabs)
│
├── static/
│   ├── uploads/            # Uploaded video files (auto-created)
│   └── outputs/            # CSV exports (auto-created)
│
└── instance/
    └── trafficiq.db        # SQLite database (auto-created)
```

---

## Configuration Reference

All settings live in `config.py` and can be overridden with environment variables.

| Setting | Default | Description |
|---|---|---|
| `SECRET_KEY` | `"change-me-…"` | Flask session secret — **change in production** |
| `SQLALCHEMY_DATABASE_URI` | `sqlite:///trafficiq.db` | Database connection string |
| `UPLOAD_FOLDER` | `static/uploads` | Where uploaded videos are saved |
| `OUTPUT_FOLDER` | `static/outputs` | Where CSV exports are saved |
| `MAX_CONTENT_LENGTH` | 500 MB | Maximum upload size |

### Environment variable override example

```bash
SECRET_KEY="my-very-secret-key" DATABASE_URL="mysql+pymysql://root:pw@localhost/trafficiq" python app.py
```

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `ModuleNotFoundError: flask_sqlalchemy` | Run `pip install -r requirements.txt` with the venv active |
| `ModuleNotFoundError: ultralytics` | Same as above |
| App hangs on large video | Normal — YOLOv8 is running on CPU. Use shorter clips (<2 min) for faster results on a laptop |
| `sqlite3.OperationalError` | Delete `instance/trafficiq.db` and restart to recreate |
| Port 5000 already in use | Change the port in `app.py`: `app.run(port=5001)` |
| MySQL connection refused | Check MySQL is running: `mysql -u root -p` |
| Charts not rendering | Ensure internet access for Chart.js CDN, or download it locally |

---

## Performance Tips for Laptops

- **Use short clips** (30 s – 2 min) for quick feedback.
- **Lower resolution** videos process significantly faster (720p recommended).
- **Queue multiple videos** — they process concurrently in background threads,
  so you can submit several and come back later.
- The app samples **1 frame per second** by default, keeping memory usage low.

---

## Security Notes

- Passwords are hashed with bcrypt (cost factor 12).
- Each user can only see and access their own analyses.
- Uploaded filenames are sanitised before saving to disk.
- Use a strong `SECRET_KEY` in any shared or production environment.

---

*Built with Flask · SQLAlchemy · YOLOv8 · Chart.js*
