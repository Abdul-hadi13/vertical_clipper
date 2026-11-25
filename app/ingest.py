"""Getting a source video from a YouTube link (uploads are handled in main.py)."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlparse

import yt_dlp

from .config import ALLOWED_EXTENSIONS, ALLOWED_YOUTUBE_HOSTS, MAX_SOURCE_HEIGHT, MAX_SOURCE_MINUTES, ffmpeg_path


def validate_youtube_url(url: str) -> str:
    """Accept only https links to YouTube hosts. Raises ValueError otherwise."""
    cleaned = url.strip()
    parsed = urlparse(cleaned)
    if parsed.scheme not in ("http", "https") or parsed.hostname not in ALLOWED_YOUTUBE_HOSTS:
        raise ValueError("Please paste a YouTube link, for example https://www.youtube.com/watch?v=...")
    return cleaned


BOT_CHECK_MARKERS = ("not a bot", "sign in to confirm", "http error 429")


def _youtube_error_message(exc: Exception) -> str:
    """Turn yt-dlp's technical errors into a message a visitor can act on."""
    text = str(exc)
    if any(marker in text.lower() for marker in BOT_CHECK_MARKERS):
        # Hosting providers often share IP addresses that YouTube challenges. Uploading avoids this.
        return ("YouTube blocked the download from this server. "
                "Please download the video yourself and use 'Upload video' instead.")
    return ("The YouTube download was interrupted, usually by a slow or unstable connection. "
            f"Please try again. ({text.replace('ERROR: ', '')[:200]})")


def download_youtube(
    url: str,
    folder: Path,
    report: Optional[Callable[[float], None]] = None,
) -> tuple[Path, str]:
    """Download the video into `folder`. Returns (file path, video title)."""

    def on_progress(data: dict) -> None:
        if report and data.get("status") == "downloading":
            total = data.get("total_bytes") or data.get("total_bytes_estimate")
            if total:
                report(data.get("downloaded_bytes", 0) / total)

    options = {
        "format": (
            f"bv*[height<={MAX_SOURCE_HEIGHT}][ext=mp4]+ba[ext=m4a]"
            f"/b[height<={MAX_SOURCE_HEIGHT}][ext=mp4]/b[height<={MAX_SOURCE_HEIGHT}]"
        ),
        "outtmpl": str(folder / "source.%(ext)s"),
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "ffmpeg_location": ffmpeg_path(),
        "progress_hooks": [on_progress],
        # Slow or flaky connections often drop mid-download; allow longer waits and more retries.
        "socket_timeout": 60,
        "retries": 10,
        "fragment_retries": 10,
    }

    with yt_dlp.YoutubeDL(options) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
        except yt_dlp.utils.DownloadError as exc:
            raise ValueError(_youtube_error_message(exc)) from exc
        if info.get("is_live") or info.get("was_live"):
            raise ValueError("Live streams cannot be used. Please choose a regular video.")
        if (info.get("duration") or 0) > MAX_SOURCE_MINUTES * 60:
            raise ValueError(f"This video is longer than the {MAX_SOURCE_MINUTES:.0f}-minute limit.")
        try:
            ydl.download([url])
        except yt_dlp.utils.DownloadError as exc:
            raise ValueError(_youtube_error_message(exc)) from exc
        title = str(info.get("title") or "YouTube video")

    files = [p for p in folder.glob("source.*") if p.suffix.lower() in ALLOWED_EXTENSIONS]
    if not files:
        raise ValueError("The download finished but no video file was found.")
    return max(files, key=lambda p: p.stat().st_size), title
