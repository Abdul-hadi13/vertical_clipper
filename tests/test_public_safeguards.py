"""Safeguards for a public demo: cleanup, busy limit, and friendly YouTube errors."""

import os
import sys
import time
from pathlib import Path
from uuid import uuid4

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ingest import _youtube_error_message  # noqa: E402
from app.jobs import Jobs  # noqa: E402
from app.store import Store  # noqa: E402


def _make_video(store: Store, age_hours: float, status: str = "ready") -> str:
    video_id = uuid4().hex
    store.create(video_id, title="t")
    store.update(video_id, lambda v: v.update(status=status))
    old = time.time() - age_hours * 3600
    os.utime(store.video_dir(video_id) / "meta.json", (old, old))
    return video_id


def test_purge_removes_old_videos_and_keeps_recent_ones(tmp_path):
    store = Store(tmp_path)
    old_id = _make_video(store, age_hours=20)
    new_id = _make_video(store, age_hours=1)

    removed = store.purge_older_than(time.time() - 12 * 3600)

    assert removed == 1
    assert store.get(old_id) is None
    assert not store.video_dir(old_id).exists()
    assert store.get(new_id) is not None


def test_purge_never_deletes_a_video_still_processing(tmp_path):
    store = Store(tmp_path)
    busy_id = _make_video(store, age_hours=20, status="processing")

    assert store.purge_older_than(time.time() - 12 * 3600) == 0
    assert store.get(busy_id) is not None


def test_active_jobs_are_counted_until_they_finish():
    jobs = Jobs(workers=1)
    started = []

    def slow(report):
        started.append(True)
        time.sleep(0.3)

    jobs.submit("a", slow)
    jobs.submit("b", slow)
    assert jobs.active_count() >= 1
    deadline = time.time() + 5
    while jobs.active_count() and time.time() < deadline:
        time.sleep(0.05)
    assert jobs.active_count() == 0


@pytest.mark.parametrize("text", [
    "ERROR: [youtube] abc: Sign in to confirm you're not a bot.",
    "HTTP Error 429: Too Many Requests",
])
def test_bot_block_gets_a_friendly_upload_instead_message(text):
    message = _youtube_error_message(Exception(text))
    assert "blocked" in message.lower()
    assert "upload video" in message.lower()


def test_other_download_errors_keep_the_retry_message():
    message = _youtube_error_message(Exception("ERROR: The read operation timed out"))
    assert "try again" in message.lower()
