"""
TrafficIQ Configuration
-----------------------
Copy this file as-is or override values with environment variables.
For MySQL: set DATABASE_URL and install PyMySQL + cryptography.
"""

import os

# ── Security ──────────────────────────────────────────────────────────────
# Change this to a long random string in production!
SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-to-a-long-random-secret")

# ── Database ──────────────────────────────────────────────────────────────
# Option A (default): SQLite — no setup needed, good for a laptop
SQLALCHEMY_DATABASE_URI = os.environ.get(
    "DATABASE_URL",
    "sqlite:///trafficiq.db"    # file will be created inside the instance/ folder
)

# Option B: MySQL — uncomment and fill in your credentials
# pip install PyMySQL cryptography
# SQLALCHEMY_DATABASE_URI = (
#     "mysql+pymysql://root:YOUR_PASSWORD@localhost:3306/trafficiq"
# )

SQLALCHEMY_TRACK_MODIFICATIONS = False

# ── Upload & Output folders (relative to app root) ────────────────────────
UPLOAD_FOLDER = "static/uploads"
OUTPUT_FOLDER = "static/outputs"

# ── Max file size (bytes) ─────────────────────────────────────────────────
MAX_CONTENT_LENGTH = 500 * 1024 * 1024   # 500 MB

# ── Allowed video extensions ──────────────────────────────────────────────
ALLOWED_EXTENSIONS = {"mp4", "avi", "mov", "mkv", "webm"}
