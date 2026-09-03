"""Tiny in-process background task manager.

Heavy work (page/cover prefetch) used to run synchronously inside a FastAPI
request, which could keep the HTTP request open for minutes and made the whole
server feel "frozen". These tasks now run on a daemon thread and expose
progress through ``cache_progress`` / ``get_job``, which the UI already polls.
"""
from __future__ import annotations

import threading
import time
from typing import Any, Callable

_locker = threading.Lock()
_jobs: dict[str, dict[str, Any]] = {}
_MAX_JOBS = 100
_JOB_TTL_SECONDS = 1800  # 30 minutes


def _key(source: str, source_id: str) -> str:
    return f"{source}/{source_id}"


def _cleanup_unlocked() -> None:
    now = time.time()
    # Remove finished jobs older than TTL
    expired = [
        k
        for k, v in _jobs.items()
        if v.get("done") and v.get("finished_at") and (now - float(v["finished_at"])) > _JOB_TTL_SECONDS
    ]
    for k in expired:
        _jobs.pop(k, None)

    # If still above limit, remove oldest finished jobs
    if len(_jobs) > _MAX_JOBS:
        finished = [
            (k, v.get("finished_at") or 0)
            for k, v in _jobs.items()
            if v.get("done")
        ]
        finished.sort(key=lambda item: item[1])
        to_remove = len(_jobs) - _MAX_JOBS
        for k, _ in finished[:to_remove]:
            _jobs.pop(k, None)


def start_job(
    source: str,
    source_id: str,
    runner: Callable[[dict[str, Any]], None],
    *,
    chapter_id: str | None = None,
) -> dict[str, Any]:
    """Start ``runner(job)`` on a daemon thread. Re-uses a running job if present."""
    key = _key(source, source_id)
    with _locker:
        _cleanup_unlocked()
        existing = _jobs.get(key)
        if existing is not None and existing.get("running"):
            return dict(existing)

        job: dict[str, Any] = {
            "source": source,
            "source_id": source_id,
            "chapter_id": chapter_id,
            "running": True,
            "done": False,
            "total": 0,
            "prefetched": 0,
            "warnings": [],
            "error": "",
            "started_at": time.time(),
            "finished_at": None,
        }
        _jobs[key] = job

    def _run() -> None:
        try:
            runner(job)
        except Exception as exc:  # pragma: no cover - defensive
            with _locker:
                job["error"] = str(exc)
        finally:
            with _locker:
                job["running"] = False
                job["done"] = True
                job["finished_at"] = time.time()

    threading.Thread(
        target=_run,
        name=f"prefetch-{key}",
        daemon=True,
    ).start()
    return job


def get_job(source: str, source_id: str) -> dict[str, Any] | None:
    with _locker:
        job = _jobs.get(_key(source, source_id))
        return dict(job) if job is not None else None


def list_running() -> list[dict[str, Any]]:
    """Snapshot of all currently running jobs (for the shelf's live progress)."""
    with _locker:
        return [dict(job) for job in _jobs.values() if job.get("running")]
