"""Runtime-adjustable download concurrency gate.

``COMIC_SHELF_MAX_CONCURRENT_DOWNLOADS`` provides the default / hard ceiling.
The in-app setting (persisted to DATA_DIR/settings.json, backed by localStorage)
adjusts the live limit at runtime without needing a restart. When the env var is
explicitly set it wins and the UI reports ``env_controlled``.
"""
from __future__ import annotations

import json
import os
import threading

from .config import DATA_DIR, MAX_CONCURRENT_DOWNLOADS

_SETTINGS_FILE = DATA_DIR / "settings.json"
_SETTINGS_KEY = "download_concurrency"
_ENV = "COMIC_SHELF_MAX_CONCURRENT_DOWNLOADS"
_MIN = 1
_MAX = 16


class ConcurrencyGate:
    """A semaphore whose limit can change while threads are waiting."""

    def __init__(self, limit: int) -> None:
        self._limit = max(_MIN, int(limit))
        self._active = 0
        self._cond = threading.Condition()

    def set_limit(self, limit: int) -> int:
        with self._cond:
            self._limit = max(_MIN, int(limit))
            self._cond.notify_all()
            return self._limit

    def limit(self) -> int:
        with self._cond:
            return self._limit

    def _acquire(self) -> None:
        with self._cond:
            while self._active >= self._limit:
                self._cond.wait()
            self._active += 1

    def _release(self) -> None:
        with self._cond:
            self._active -= 1
            self._cond.notify()

    def __enter__(self) -> "ConcurrencyGate":
        self._acquire()
        return self

    def __exit__(self, *exc: object) -> None:
        self._release()


def _env_explicit() -> bool:
    return _ENV in os.environ


def _load_persisted() -> int | None:
    try:
        data = json.loads(_SETTINGS_FILE.read_text(encoding="utf-8"))
        value = int(data.get(_SETTINGS_KEY) or 0)
        return max(_MIN, value) if value > 0 else None
    except Exception:
        return None


def _save_persisted(limit: int) -> None:
    try:
        _SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        data: dict = {}
        if _SETTINGS_FILE.exists():
            try:
                data = json.loads(_SETTINGS_FILE.read_text(encoding="utf-8"))
            except Exception:
                data = {}
        data[_SETTINGS_KEY] = limit
        _SETTINGS_FILE.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


# Startup priority: explicit env var > persisted in-app choice > default.
if _env_explicit():
    _initial = MAX_CONCURRENT_DOWNLOADS
else:
    _initial = _load_persisted() or MAX_CONCURRENT_DOWNLOADS

download_gate = ConcurrencyGate(_initial)


def get_download_concurrency() -> int:
    return download_gate.limit()


def set_download_concurrency(limit: int) -> int:
    value = max(_MIN, min(int(limit), _MAX))
    # An explicitly set env var is the hard ceiling; never go above it.
    if _env_explicit():
        value = min(value, MAX_CONCURRENT_DOWNLOADS)
    _save_persisted(value)
    return download_gate.set_limit(value)
