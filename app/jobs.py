"""Runs slow work (downloads, scene detection, exports) in the background and tracks progress."""

from __future__ import annotations

import threading
import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable
from uuid import uuid4

# Errors raised with these types are written for the user. Anything else gets a generic message.
USER_FACING_ERRORS = (ValueError, RuntimeError)


def public_error(exc: BaseException) -> str:
    if isinstance(exc, USER_FACING_ERRORS):
        return str(exc) or exc.__class__.__name__
    return "Unexpected error while processing. Check the server log for details."


class Jobs:
    def __init__(self, workers: int = 2):
        self._pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="clipper")
        self._jobs: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def submit(self, kind: str, fn: Callable[..., Any], *args: Any) -> str:
        job_id = uuid4().hex
        with self._lock:
            self._jobs[job_id] = {
                "id": job_id,
                "kind": kind,
                "status": "queued",
                "progress": 0.0,
                "message": "Waiting to start",
                "detail": None,  # {"total": n, "done": k, "current": i} when the job works on clips
                "result": None,
                "error": None,
            }
        self._pool.submit(self._run, job_id, fn, args)
        return job_id

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return dict(job) if job else None

    def _update(self, job_id: str, **fields: Any) -> None:
        with self._lock:
            self._jobs[job_id].update(fields)

    def _run(self, job_id: str, fn: Callable[..., Any], args: tuple) -> None:
        self._update(job_id, status="running", message="Starting")

        def report(progress: float, message: str | None = None, detail: dict | None = None) -> None:
            fields: dict[str, Any] = {"progress": max(0.0, min(1.0, progress))}
            if message is not None:
                fields["message"] = message
            if detail is not None:
                fields["detail"] = detail
            self._update(job_id, **fields)

        try:
            result = fn(report, *args)
            self._update(job_id, status="done", progress=1.0, message="Done", result=result)
        except Exception as exc:  # noqa: BLE001 - we report every failure to the UI
            traceback.print_exc()
            self._update(job_id, status="error", message="Failed", error=public_error(exc))
