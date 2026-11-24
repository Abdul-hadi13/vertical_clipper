"""Saves video and clip details to disk so they survive a server restart."""

from __future__ import annotations

import copy
import json
import os
import shutil
import threading
from pathlib import Path
from typing import Callable


class Store:
    def __init__(self, root: Path):
        self.root = root
        self._videos_dir = root / "videos"
        self._videos_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._videos: dict[str, dict] = {}
        for meta in self._videos_dir.glob("*/meta.json"):
            try:
                record = json.loads(meta.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if record.get("status") == "processing":
                record.update(status="error", error="The server restarted before this video finished processing.")
            self._videos[record["id"]] = record

    def video_dir(self, video_id: str) -> Path:
        return self._videos_dir / video_id

    def create(self, video_id: str, title: str) -> None:
        with self._lock:
            self.video_dir(video_id).mkdir(parents=True, exist_ok=True)
            record = {
                "id": video_id,
                "title": title,
                "status": "processing",
                "error": None,
                "source": None,
                "duration": 0.0,
                "width": 0,
                "height": 0,
                "fps": 0.0,
                "clips": [],
                "bundle": None,
            }
            self._videos[video_id] = record
            self._save(record)

    def get(self, video_id: str) -> dict | None:
        with self._lock:
            record = self._videos.get(video_id)
            return copy.deepcopy(record) if record else None

    def update(self, video_id: str, mutate: Callable[[dict], None]) -> None:
        with self._lock:
            record = self._videos[video_id]
            mutate(record)
            self._save(record)

    def discard(self, video_id: str) -> None:
        with self._lock:
            self._videos.pop(video_id, None)
            shutil.rmtree(self.video_dir(video_id), ignore_errors=True)

    def _save(self, record: dict) -> None:
        path = self.video_dir(record["id"]) / "meta.json"
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(record, indent=2), encoding="utf-8")
        os.replace(tmp, path)
