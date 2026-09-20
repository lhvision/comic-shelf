from __future__ import annotations

import json
import logging
import os
import time
from abc import ABC, abstractmethod
from pathlib import Path

from ..models import DiscoveryItem, FetchedComic, RemotePage

logger = logging.getLogger("paper_room.provider.base")


class ComicProvider(ABC):
    """The extension point for other comic sites.

    To add a site (e.g. nhentai, e-hentai, hitomi), subclass this and register
    the instance in ``registry.py``. The HTTP API and the local cache are
    completely provider-neutral.
    """

    key: str = ""
    label: str = ""
    short_label: str = ""
    id_pattern: str = ""
    example: str = ""

    # ------------------------------------------------------------------
    # Secure Session / Credential Persistence (0o600 POSIX File Permissions)
    # ------------------------------------------------------------------
    @staticmethod
    def save_secure_session(path: Path, data: dict) -> None:
        """Atomically persist sensitive session/credentials with private POSIX permissions (0o600).

        Ensures zero-TOCTOU permission window (0o600 at creation), atomic replacement,
        and safe cleanup on failure.
        """
        temp_file: Path | None = None
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
            temp_file = path.parent / f".{path.name}.tmp.{os.getpid()}_{time.time_ns()}"
            fd = os.open(temp_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            try:
                with open(fd, "wb") as f:
                    f.write(payload)
                os.replace(temp_file, path)
                temp_file = None
            except Exception:
                if temp_file is not None and temp_file.exists():
                    temp_file.unlink(missing_ok=True)
                raise
        except Exception as exc:
            logger.warning("Failed to save secure session file %s: %s", path.name, exc)
        finally:
            if temp_file is not None and temp_file.exists():
                try:
                    temp_file.unlink(missing_ok=True)
                except OSError:
                    pass

    @staticmethod
    def load_secure_session(path: Path) -> dict | None:
        """Safely load a session json file."""
        try:
            if not path.is_file():
                return None
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else None
        except Exception as exc:
            logger.warning("Failed to load secure session file %s: %s", path.name, exc)
            return None

    @staticmethod
    def clear_secure_session(path: Path) -> None:
        """Safely remove a session file."""
        try:
            if path.is_file():
                path.unlink(missing_ok=True)
        except Exception as exc:
            logger.warning("Failed to clear secure session file %s: %s", path.name, exc)

    @abstractmethod
    def normalize_id(self, raw: str) -> str:
        """Turn user input into the canonical provider id."""

    @abstractmethod
    def fetch(
        self,
        raw_id: str,
        *,
        existing: "FetchedComic | None" = None,
    ) -> FetchedComic:
        """Fetch metadata + page URLs. Must not download page bytes here.

        ``existing`` is the local bundle on a ``refresh=true``; providers may use
        it to skip re-fetching unchanged chapters (T12 incremental refresh).
        """

    @abstractmethod
    def download_page(self, comic: FetchedComic, page: RemotePage) -> bytes:
        """Download one page. The storage layer decides when this is called."""

    def fetch_ranking(self, timeframe: str = "week", page: int = 1, limit: int = 20) -> list[DiscoveryItem]:
        """Optional hook for discovery feeds / rankings."""
        return []

    def describe(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "short_label": self.short_label or self.label,
            "id_pattern": self.id_pattern,
            "example": self.example,
        }
