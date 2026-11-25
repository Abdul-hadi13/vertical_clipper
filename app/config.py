"""Central settings. Most values can be overridden with environment variables."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import imageio_ffmpeg

PROJECT_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = PROJECT_DIR / "static"
WORK_DIR = Path(os.environ.get("CLIPPER_WORK_DIR", PROJECT_DIR / "workdir")).resolve()

# Upload and source limits
MAX_UPLOAD_MB = float(os.environ.get("CLIPPER_MAX_UPLOAD_MB", "2048"))
MAX_UPLOAD_BYTES = int(MAX_UPLOAD_MB * 1024 * 1024)
MAX_SOURCE_MINUTES = float(os.environ.get("CLIPPER_MAX_SOURCE_MINUTES", "240"))
MAX_SOURCE_HEIGHT = 1080
ALLOWED_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm"}
ALLOWED_YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}

# Public-demo safeguards: old files are deleted, and the queue is capped
RETENTION_HOURS = float(os.environ.get("CLIPPER_RETENTION_HOURS", "12"))
MAX_ACTIVE_JOBS = int(os.environ.get("CLIPPER_MAX_ACTIVE_JOBS", "4"))

# Automatic splitting
AUTO_SPLIT_THRESHOLD = 27.0  # PySceneDetect content-change threshold
MIN_AUTO_CLIP_SEC = 5.0
MAX_AUTO_CLIP_SEC = 60.0

# Manual trimming limits
MIN_CLIP_SEC = 1.0
MAX_CLIP_SEC = 180.0

# Output and subject tracking
OUTPUT_WIDTH = 1080
OUTPUT_HEIGHT = 1920
TRACK_SAMPLES_PER_SEC = 5.0
SMOOTHING_ALPHA = 0.2  # 0..1, lower = smoother but slower to follow
DEADZONE_FRACTION = 0.01  # ignore subject movements smaller than 1% of frame width


def ffmpeg_path() -> str:
    """Use FFMPEG_PATH if set, then ffmpeg on PATH, then the FFmpeg bundled with imageio-ffmpeg."""
    configured = os.environ.get("FFMPEG_PATH")
    if configured:
        return configured
    on_path = shutil.which("ffmpeg")
    if on_path:
        return on_path
    return imageio_ffmpeg.get_ffmpeg_exe()
