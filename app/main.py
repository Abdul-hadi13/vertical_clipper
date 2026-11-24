"""HTTP API and web page for Vertical Clipper."""

from __future__ import annotations

import math
import re
import zipfile
from pathlib import Path
from typing import Callable
from uuid import uuid4

import cv2
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import (
    ALLOWED_EXTENSIONS,
    MAX_CLIP_SEC,
    MAX_SOURCE_MINUTES,
    MAX_UPLOAD_BYTES,
    MAX_UPLOAD_MB,
    MIN_CLIP_SEC,
    STATIC_DIR,
    WORK_DIR,
    ffmpeg_path,
)
from .exporter import export_clip
from .ingest import download_youtube, validate_youtube_url
from .jobs import Jobs, public_error
from .media import VideoInfo, probe, validate_landscape
from .schemas import ClipUpdate, UrlRequest
from .splitter import build_clips, detect_scenes
from .store import Store

app = FastAPI(title="Vertical Clipper", version="1.0.0")
store = Store(WORK_DIR)
jobs = Jobs()
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
Report = Callable[[float, str | None], None]


# ---------- helpers ----------

def _check_id(value: str) -> None:
    if not ID_PATTERN.match(value):
        raise HTTPException(404, "Not found")


def _get_video(video_id: str) -> dict:
    _check_id(video_id)
    video = store.get(video_id)
    if video is None:
        raise HTTPException(404, "Video not found")
    return video


def _find_clip(video: dict, clip_id: str) -> dict:
    _check_id(clip_id)
    for clip in video["clips"]:
        if clip["id"] == clip_id:
            return clip
    raise HTTPException(404, "Clip not found")


def _info(video: dict) -> VideoInfo:
    return VideoInfo(width=video["width"], height=video["height"], fps=video["fps"], duration=video["duration"])


def _clean_title(filename: str | None) -> str:
    stem = Path(filename or "video").stem
    return re.sub(r"[^\w .()\-]", "", stem)[:120].strip() or "Untitled video"


def _mark_error(video_id: str, exc: BaseException) -> None:
    message = public_error(exc)
    store.update(video_id, lambda v: v.update(status="error", error=message))


def _progress_slice(report: Report, base: float, span: float, label: str) -> Report:
    """Map a 0..1 progress from one step onto part of the overall job."""
    def inner(fraction: float, message: str | None = None) -> None:
        report(base + span * fraction, message or label)
    return inner


# ---------- background jobs ----------

def _analyze_source(report: Report, video_id: str, source: Path) -> dict:
    try:
        report(0.05, "Reading video details")
        info = probe(source)
        validate_landscape(info)
        if info.duration > MAX_SOURCE_MINUTES * 60:
            raise ValueError(f"This video is longer than the {MAX_SOURCE_MINUTES:.0f}-minute limit.")

        report(0.2, "Detecting scene changes (this can take a while)")
        scenes = detect_scenes(source, info.duration)

        report(0.8, "Creating clips")
        clips = [
            {"id": uuid4().hex, "number": n, "start": c["start"], "end": c["end"], "output": None}
            for n, c in enumerate(build_clips(scenes, info.duration), start=1)
        ]

        def apply(record: dict) -> None:
            record.update(
                status="ready",
                error=None,
                source=source.name,
                duration=round(info.duration, 3),
                width=info.width,
                height=info.height,
                fps=info.fps,
                clips=clips,
            )

        store.update(video_id, apply)
    except Exception as exc:
        _mark_error(video_id, exc)
        raise
    return {"video_id": video_id}


def _download_and_analyze(report: Report, video_id: str, url: str) -> dict:
    try:
        report(0.02, "Downloading from YouTube")
        source, title = download_youtube(url, store.video_dir(video_id), _progress_slice(report, 0.02, 0.6, "Downloading from YouTube"))
        store.update(video_id, lambda v: v.update(title=title[:120]))
    except Exception as exc:
        _mark_error(video_id, exc)
        raise
    return _analyze_source(_progress_slice(report, 0.65, 0.35, "Preparing"), video_id, source)


def _export_one(video_id: str, clip_id: str, start: float, end: float, info: VideoInfo, report: Report) -> str:
    folder = store.video_dir(video_id)
    source_name = store.get(video_id)["source"]
    output = folder / "exports" / f"{clip_id}.mp4"
    output.parent.mkdir(exist_ok=True)
    export_clip(folder / source_name, info, start, end, output, report)

    relative = f"exports/{clip_id}.mp4"

    def apply(record: dict) -> None:
        for clip in record["clips"]:
            # Only record the file if the clip was not edited while it was rendering.
            if clip["id"] == clip_id and clip["start"] == start and clip["end"] == end:
                clip["output"] = relative

    store.update(video_id, apply)
    return relative


def _export_clip_job(report: Report, video_id: str, clip_id: str, start: float, end: float) -> dict:
    # Export failures are reported through the job only; the video itself stays ready.
    _export_one(video_id, clip_id, start, end, _info(store.get(video_id)), report)
    return {"clip_id": clip_id}


def _export_all_job(report: Report, video_id: str) -> dict:
    video = store.get(video_id)
    info = _info(video)
    clips = [dict(c) for c in video["clips"]]
    if not clips:
        raise ValueError("There are no clips to export.")

    for index, clip in enumerate(clips):
        label = f"Exporting clip {index + 1} of {len(clips)}"
        step = 1 / len(clips)
        _export_one(video_id, clip["id"], clip["start"], clip["end"], info,
                    _progress_slice(report, index * step, step, label))

    bundle_relative = "exports/all-clips.zip"
    bundle = store.video_dir(video_id) / bundle_relative
    with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as archive:
        for clip in clips:
            archive.write(store.video_dir(video_id) / "exports" / f"{clip['id']}.mp4", arcname=f"clip-{clip['number']:02d}.mp4")
    store.update(video_id, lambda v: v.update(bundle=bundle_relative))
    return {"bundle": bundle_relative}


def _validate_range(start: float, end: float, duration: float) -> None:
    if not (math.isfinite(start) and math.isfinite(end)):
        raise HTTPException(400, "Start and end must be numbers.")
    if start < 0 or end > duration + 0.001 or end <= start:
        raise HTTPException(400, f"Start and end must be inside the video (0 to {duration:.1f} s) and the end must be after the start.")
    length = end - start
    if length < MIN_CLIP_SEC:
        raise HTTPException(400, f"A clip must be at least {MIN_CLIP_SEC:.0f} second long.")
    if length > MAX_CLIP_SEC:
        raise HTTPException(400, f"A clip can be at most {MAX_CLIP_SEC:.0f} seconds long.")


# ---------- routes: pages and health ----------

@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "ffmpeg": ffmpeg_path(), "opencv": cv2.__version__, "max_upload_mb": MAX_UPLOAD_MB}


# ---------- routes: add a video ----------

@app.post("/api/videos/upload", status_code=202)
async def upload_video(file: UploadFile = File(...)) -> dict:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type. Use one of: {', '.join(sorted(ALLOWED_EXTENSIONS))}")

    video_id = uuid4().hex
    store.create(video_id, title=_clean_title(file.filename))
    source = store.video_dir(video_id) / f"upload{suffix}"  # server-chosen name, never the user's filename
    written = 0
    try:
        with source.open("wb") as out:
            while chunk := await file.read(1024 * 1024):
                written += len(chunk)
                if written > MAX_UPLOAD_BYTES:
                    raise HTTPException(413, f"The file is larger than the {MAX_UPLOAD_MB:.0f} MB upload limit.")
                out.write(chunk)
    except HTTPException:
        store.discard(video_id)
        raise

    job_id = jobs.submit("analyze", _analyze_source, video_id, source)
    return {"video_id": video_id, "job_id": job_id}


@app.post("/api/videos/from-url", status_code=202)
def video_from_url(body: UrlRequest) -> dict:
    try:
        url = validate_youtube_url(body.url)
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    video_id = uuid4().hex
    store.create(video_id, title="YouTube video (loading)")
    job_id = jobs.submit("download", _download_and_analyze, video_id, url)
    return {"video_id": video_id, "job_id": job_id}


# ---------- routes: read and edit ----------

@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    _check_id(job_id)
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    return job


@app.get("/api/videos/{video_id}")
def get_video(video_id: str) -> dict:
    return _get_video(video_id)


@app.get("/api/videos/{video_id}/source")
def get_source(video_id: str) -> FileResponse:
    video = _get_video(video_id)
    if not video["source"]:
        raise HTTPException(409, "The video is still being prepared")
    return FileResponse(store.video_dir(video_id) / video["source"])


@app.patch("/api/videos/{video_id}/clips/{clip_id}")
def update_clip(video_id: str, clip_id: str, body: ClipUpdate) -> dict:
    video = _get_video(video_id)
    if video["status"] != "ready":
        raise HTTPException(409, "The video is not ready yet")
    _find_clip(video, clip_id)
    _validate_range(body.start, body.end, video["duration"])

    def apply(record: dict) -> None:
        for clip in record["clips"]:
            if clip["id"] == clip_id:
                clip.update(start=round(body.start, 3), end=round(body.end, 3), output=None)
        record["bundle"] = None  # the zip of all clips is now out of date

    store.update(video_id, apply)
    return _get_video(video_id)


@app.post("/api/videos/{video_id}/clips", status_code=201)
def add_clip(video_id: str, body: ClipUpdate) -> dict:
    video = _get_video(video_id)
    if video["status"] != "ready":
        raise HTTPException(409, "The video is not ready yet")
    _validate_range(body.start, body.end, video["duration"])

    def apply(record: dict) -> None:
        number = max((c["number"] for c in record["clips"]), default=0) + 1
        record["clips"].append({
            "id": uuid4().hex,
            "number": number,
            "start": round(body.start, 3),
            "end": round(body.end, 3),
            "output": None,
        })
        record["bundle"] = None

    store.update(video_id, apply)
    return _get_video(video_id)


@app.post("/api/videos/{video_id}/clips/{clip_id}/export", status_code=202)
def export_one(video_id: str, clip_id: str) -> dict:
    video = _get_video(video_id)
    if video["status"] != "ready":
        raise HTTPException(409, "The video is not ready yet")
    clip = _find_clip(video, clip_id)
    job_id = jobs.submit("export", _export_clip_job, video_id, clip_id, clip["start"], clip["end"])
    return {"job_id": job_id}


@app.post("/api/videos/{video_id}/export-all", status_code=202)
def export_all(video_id: str) -> dict:
    video = _get_video(video_id)
    if video["status"] != "ready":
        raise HTTPException(409, "The video is not ready yet")
    if not video["clips"]:
        raise HTTPException(409, "There are no clips to export")
    job_id = jobs.submit("export-all", _export_all_job, video_id)
    return {"job_id": job_id}


@app.get("/api/videos/{video_id}/clips/{clip_id}/download")
def download_clip(video_id: str, clip_id: str) -> FileResponse:
    video = _get_video(video_id)
    clip = _find_clip(video, clip_id)
    if not clip["output"]:
        raise HTTPException(404, "This clip has not been exported yet")
    return FileResponse(store.video_dir(video_id) / clip["output"], filename=f"clip-{clip['number']:02d}.mp4")


@app.get("/api/videos/{video_id}/bundle")
def download_bundle(video_id: str) -> FileResponse:
    video = _get_video(video_id)
    if not video["bundle"]:
        raise HTTPException(404, "Export all clips first")
    return FileResponse(store.video_dir(video_id) / video["bundle"], filename="clips.zip")
