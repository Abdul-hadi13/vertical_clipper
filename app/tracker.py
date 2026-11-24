"""Subject tracking: follow the largest face so the 9:16 crop stays on the speaker."""

from __future__ import annotations

from typing import Callable, Optional

import cv2
import numpy as np

from .config import DEADZONE_FRACTION, SMOOTHING_ALPHA, TRACK_SAMPLES_PER_SEC
from .media import VideoInfo

ANALYSIS_WIDTH = 640
_FACE_MODEL = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"


def smooth_centers(
    samples: list[tuple[float, float]],
    alpha: float = SMOOTHING_ALPHA,
    deadzone: float = 0.0,
) -> list[tuple[float, float]]:
    """Exponential smoothing with a dead zone.

    The crop only moves when the target drifts more than `deadzone` pixels, which stops
    the frame from jittering on small head movements. Each step moves `alpha` of the way.
    """
    if not samples:
        return []
    smoothed: list[tuple[float, float]] = []
    current = samples[0][1]
    for t, target in samples:
        if abs(target - current) > deadzone:
            current += alpha * (target - current)
        smoothed.append((t, current))
    return smoothed


def track_centers(
    source: str,
    info: VideoInfo,
    start: float,
    end: float,
    report: Optional[Callable[[float], None]] = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Return (times, centers) for [start, end].

    times are seconds from the clip start. centers are the smoothed horizontal
    subject positions in source pixels. When no face is seen the last known
    position is kept, starting from the frame centre.
    """
    cascade = cv2.CascadeClassifier(_FACE_MODEL)
    cap = cv2.VideoCapture(source)
    first = round(start * info.fps)
    last = round(end * info.fps)
    step = max(1, round(info.fps / TRACK_SAMPLES_PER_SEC))
    scale = ANALYSIS_WIDTH / info.width
    small_size = (ANALYSIS_WIDTH, max(1, round(info.height * scale)))

    samples: list[tuple[float, float]] = []
    last_center = info.width / 2
    try:
        cap.set(cv2.CAP_PROP_POS_FRAMES, first)
        total = max(1, last - first)
        for index in range(first, last):
            ok, frame = cap.read()
            if not ok:
                break
            offset = index - first
            if offset % step == 0:
                small = cv2.resize(frame, small_size, interpolation=cv2.INTER_AREA)
                gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
                faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(40, 40))
                if len(faces):
                    x, _, w, _ = max(faces, key=lambda f: f[2] * f[3])
                    last_center = (x + w / 2) / scale
                samples.append((offset / info.fps, last_center))
            if report and offset % 30 == 0:
                report(0.5 * offset / total)
    finally:
        cap.release()

    if not samples:
        samples = [(0.0, info.width / 2)]
    smoothed = smooth_centers(samples, deadzone=DEADZONE_FRACTION * info.width)
    times = np.array([t for t, _ in smoothed])
    centers = np.array([c for _, c in smoothed])
    return times, centers
