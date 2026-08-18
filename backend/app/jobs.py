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


def _key(source: str, source_id: str) -> str:
    return f"{source}/{source_id}"


def start_job(
    source: str,
    source_id: str,
    runner: Callable[[dict[str, Any]], None],
) -> dict[str, Any]:
    """Start ``runner(job)`` on a daemon thread. Re-uses a running job if present."""
    key = _key(source, source_id)
    with _locker:
        existing = _jobs.get(key)
        if existing is not None and existing.get("running"):
            return existing

        job: dict[str, Any] = {
            "source": source,
            "source_id": source_id,
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
            job["error"] = str(exc)
        finally:
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
