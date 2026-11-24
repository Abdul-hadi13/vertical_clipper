import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.media import VideoInfo, crop_left_edge, crop_width_for, validate_landscape  # noqa: E402
from app.tracker import smooth_centers  # noqa: E402

LANDSCAPE = VideoInfo(width=1920, height=1080, fps=30.0, duration=60.0)


def test_crop_window_is_9_by_16_and_even():
    assert crop_width_for(1080) == 608  # 1080 * 9 / 16 = 607.5, rounded to an even width
    assert crop_width_for(720) % 2 == 0


def test_crop_follows_subject_and_stays_inside_frame():
    assert crop_left_edge(0, LANDSCAPE) == 0
    assert crop_left_edge(1920, LANDSCAPE) == 1920 - crop_width_for(1080)
    centered = crop_left_edge(960, LANDSCAPE)
    assert abs((centered + crop_width_for(1080) / 2) - 960) <= 1


def test_video_narrower_than_9_by_16_is_rejected():
    narrow = VideoInfo(width=500, height=1000, fps=30.0, duration=10.0)
    with pytest.raises(ValueError):
        validate_landscape(narrow)


def test_9_by_16_video_is_accepted():
    validate_landscape(VideoInfo(width=720, height=1280, fps=30.0, duration=10.0))


def test_smoothing_ignores_small_jitter_inside_deadzone():
    samples = [(i * 0.2, 500.0 + (3 if i % 2 else -3)) for i in range(20)]
    smoothed = smooth_centers(samples, alpha=0.2, deadzone=10.0)
    # Jitter of +/-3 px is inside the 10 px dead zone, so the crop never moves from its start.
    assert np.allclose([c for _, c in smoothed], samples[0][1])


def test_smoothing_moves_gradually_towards_a_large_change():
    samples = [(i * 0.2, 100.0) for i in range(5)] + [(1.0 + i * 0.2, 900.0) for i in range(30)]
    smoothed = [c for _, c in smooth_centers(samples, alpha=0.2, deadzone=10.0)]
    assert smoothed[5] < smoothed[-1]            # still moving
    assert 100.0 < smoothed[5] < 900.0           # not a jump
    assert smoothed[-1] > 850.0                  # eventually arrives
