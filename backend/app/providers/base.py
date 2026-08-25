from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import DiscoveryItem, FetchedComic, RemotePage


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
