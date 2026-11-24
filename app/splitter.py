"""Automatic splitting of a video into clips."""

from __future__ import annotations

import math
from pathlib import Path

from .config import AUTO_SPLIT_THRESHOLD, MAX_AUTO_CLIP_SEC, MIN_AUTO_CLIP_SEC


def detect_scenes(path: Path, duration: float) -> list[tuple[float, float]]:
    """Find shot changes with PySceneDetect. Returns (start, end) seconds per scene."""
    from scenedetect import ContentDetector, SceneManager, open_video

    video = open_video(str(path))
    manager = SceneManager()
    manager.add_detector(ContentDetector(threshold=AUTO_SPLIT_THRESHOLD))
    manager.detect_scenes(video=video, show_progress=False)
    scenes = [(start.seconds, end.seconds) for start, end in manager.get_scene_list()]
    return scenes or [(0.0, duration)]


def build_clips(
    scenes: list[tuple[float, float]],
    duration: float,
    min_len: float = MIN_AUTO_CLIP_SEC,
    max_len: float = MAX_AUTO_CLIP_SEC,
) -> list[dict[str, float]]:
    """Turn detected scenes into clips.

    - Scenes shorter than min_len are merged into their neighbour.
    - Scenes longer than max_len are split into equal parts no longer than max_len.
    - A video with no detected cuts is split the same way, so the fallback is automatic.
    """
    merged: list[list[float]] = []
    for start, end in scenes:
        if end - start <= 0:
            continue
        if merged and (merged[-1][1] - merged[-1][0]) < min_len:
            merged[-1][1] = end
        else:
            merged.append([start, end])

    # A short final scene is folded into the previous clip.
    if len(merged) > 1 and (merged[-1][1] - merged[-1][0]) < min_len:
        tail = merged.pop()
        merged[-1][1] = tail[1]

    clips: list[dict[str, float]] = []
    for start, end in merged:
        length = end - start
        parts = max(1, math.ceil(length / max_len))
        step = length / parts
        for i in range(parts):
            clips.append({"start": start + i * step, "end": start + (i + 1) * step})

    if not clips:
        clips = [{"start": 0.0, "end": duration}]

    # Fix rounding so the clips cover the whole video exactly.
    clips[0]["start"] = 0.0
    clips[-1]["end"] = duration
    return [{"start": round(c["start"], 3), "end": round(c["end"], 3)} for c in clips]
