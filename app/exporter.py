"""Cut a clip, follow the subject and write a 1080x1920 MP4 with FFmpeg."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Callable, Optional

import cv2
import numpy as np

from .config import OUTPUT_HEIGHT, OUTPUT_WIDTH, ffmpeg_path
from .media import VideoInfo, crop_left_edge, crop_width_for
from .tracker import track_centers


def build_ffmpeg_command(
    ffmpeg: str,
    source: Path,
    start: float,
    duration: float,
    fps: float,
    output: Path,
) -> list[str]:
    """FFmpeg reads raw cropped frames from stdin and audio from the source file."""
    return [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "bgr24",
        "-s", f"{OUTPUT_WIDTH}x{OUTPUT_HEIGHT}", "-r", f"{fps:.6f}", "-i", "pipe:0",
        "-ss", f"{start:.3f}", "-t", f"{duration:.3f}", "-i", str(source),
        "-map", "0:v:0", "-map", "1:a:0?",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k",
        "-shortest", "-movflags", "+faststart",
        str(output),
    ]


def export_clip(
    source: Path,
    info: VideoInfo,
    start: float,
    end: float,
    output: Path,
    report: Optional[Callable[[float, str], None]] = None,
) -> None:
    """Export [start, end] as a vertical clip. Progress goes from 0 to 1."""
    if end <= start:
        raise ValueError("The clip must end after it starts.")

    def track_progress(fraction: float) -> None:
        if report:
            report(fraction * 0.5, "Tracking the subject")

    times, centers = track_centers(str(source), info, start, end, track_progress)

    duration = end - start
    frame_count = max(1, round(duration * info.fps))
    command = build_ffmpeg_command(ffmpeg_path(), source, start, duration, info.fps, output)
    try:
        proc = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as exc:
        raise RuntimeError(f"FFmpeg could not be started: {exc}") from exc

    cap = cv2.VideoCapture(str(source))
    cap.set(cv2.CAP_PROP_POS_FRAMES, round(start * info.fps))
    crop_w = crop_width_for(info.height)
    try:
        for i in range(frame_count):
            ok, frame = cap.read()
            if not ok:
                break
            center = float(np.interp(i / info.fps, times, centers))
            left = crop_left_edge(center, info)
            window = frame[:, left:left + crop_w]
            vertical = cv2.resize(window, (OUTPUT_WIDTH, OUTPUT_HEIGHT), interpolation=cv2.INTER_AREA)
            proc.stdin.write(vertical.tobytes())
            if report and i % 30 == 0:
                report(0.5 + 0.5 * i / frame_count, "Rendering clip")
        proc.stdin.close()
        error_output = proc.stderr.read()
        code = proc.wait()
    except BrokenPipeError:
        code = proc.wait()
        error_output = proc.stderr.read()
    finally:
        cap.release()
        if proc.poll() is None:
            proc.kill()

    if code != 0:
        tail = error_output.decode(errors="replace").strip()[-400:]
        raise RuntimeError(f"FFmpeg failed to write the clip. {tail}")
    if report:
        report(1.0, "Clip ready")
