import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.splitter import build_clips  # noqa: E402


def test_clips_cover_whole_video_without_gaps():
    scenes = [(0.0, 30.0), (30.0, 95.0), (95.0, 100.0)]
    clips = build_clips(scenes, duration=100.0)
    assert clips[0]["start"] == 0.0
    assert clips[-1]["end"] == 100.0
    for previous, current in zip(clips, clips[1:]):
        assert previous["end"] == current["start"]


def test_long_scene_is_split_into_parts_no_longer_than_max():
    clips = build_clips([(0.0, 150.0)], duration=150.0, max_len=60.0)
    assert len(clips) == 3
    assert all(c["end"] - c["start"] <= 60.0 + 1e-6 for c in clips)


def test_short_scenes_are_merged_into_a_neighbour():
    scenes = [(0.0, 2.0), (2.0, 3.0), (3.0, 30.0)]
    clips = build_clips(scenes, duration=30.0, min_len=5.0)
    assert len(clips) == 1
    assert clips[0] == {"start": 0.0, "end": 30.0}


def test_no_cuts_falls_back_to_fixed_length_parts():
    clips = build_clips([(0.0, 200.0)], duration=200.0, max_len=60.0)
    assert len(clips) == 4
    assert clips[-1]["end"] == 200.0


def test_empty_scene_list_still_gives_one_clip():
    assert build_clips([], duration=12.0) == [{"start": 0.0, "end": 12.0}]
