"""Shared test setup: a temporary work folder and a small generated 16:9 test video."""

import os
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))


@pytest.fixture(scope="session")
def work_dir(tmp_path_factory) -> Path:
    # Must be set before the app is imported, because the app creates its store at import time.
    folder = tmp_path_factory.mktemp("workdir")
    os.environ["CLIPPER_WORK_DIR"] = str(folder)
    return folder


@pytest.fixture(scope="session")
def sample_video(tmp_path_factory) -> Path:
    """A 12-second 1280x720 video with a scene cut at 6 s and a bright square that moves."""
    path = tmp_path_factory.mktemp("media") / "sample.mp4"
    fps, width, height, seconds = 25, 1280, 720, 12
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    for i in range(fps * seconds):
        frame = np.full((height, width, 3), 40 if i < fps * 6 else 150, dtype=np.uint8)
        x = 100 + int((i / (fps * seconds)) * 900)
        cv2.rectangle(frame, (x, 250), (x + 200, 450), (255, 255, 255), -1)
        writer.write(frame)
    writer.release()
    return path
