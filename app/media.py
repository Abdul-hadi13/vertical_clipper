"""Reading video files and working out crop geometry."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2


@dataclass(frozen=True)
class VideoInfo:
    width: int
    height: int
    fps: float
    duration: float


def probe(path: Path) -> VideoInfo:
    """Read basic video details with OpenCV. Raises ValueError if the file is not a readable video."""
    cap = cv2.VideoCapture(str(path))
    try:
        if not cap.isOpened():
            raise ValueError("This file could not be opened as a video.")
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        frames = float(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    finally:
        cap.release()

    if width <= 0 or height <= 0 or fps <= 0 or frames <= 0:
        raise ValueError("This file does not look like a video with a readable timeline.")
    return VideoInfo(width=width, height=height, fps=fps, duration=frames / fps)


def crop_width_for(source_height: int) -> int:
    """Width of a 9:16 window that spans the full source height (kept even for encoders)."""
    return (round(source_height * 9 / 16)) & ~1


MIN_ASPECT = 1.7   # 16:9 is about 1.78; 1.85 (cinema widescreen) is still accepted
MAX_ASPECT = 1.9


def validate_widescreen(info: VideoInfo) -> None:
    """The test asks for 16:9 input. Other shapes would need different crop rules, so they are refused."""
    aspect = info.width / info.height
    if not (MIN_ASPECT <= aspect <= MAX_ASPECT):
        raise ValueError(
            f"This video is {info.width}x{info.height}. Please use a 16:9 widescreen video "
            "(for example 1920x1080 or 1280x720)."
        )


def crop_left_edge(center_x: float, info: VideoInfo) -> int:
    """Left pixel of the 9:16 window centered on center_x, kept inside the frame."""
    cw = crop_width_for(info.height)
    left = int(round(center_x - cw / 2))
    return max(0, min(left, info.width - cw))

