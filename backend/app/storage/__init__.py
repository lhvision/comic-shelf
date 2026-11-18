"""Storage package for Paper Room comic archives."""

from __future__ import annotations

from .base import ComicStoreBase
from .chapters import ComicStoreChapterMixin
from .local import ComicStoreLocalMixin
from .media import ComicStoreMediaMixin
from .prefetch import ComicStorePrefetchMixin


class ComicStore(
    ComicStoreMediaMixin,
    ComicStoreChapterMixin,
    ComicStoreLocalMixin,
    ComicStorePrefetchMixin,
    ComicStoreBase,
):
    """Local-first cache.

    Once ``album.json`` exists we never hit the network again for metadata
    unless the client explicitly asks for ``refresh=true``. Missing pages are
    lazy-downloaded only when they are actually viewed (or during an explicit
    "cache all" action).
    """


__all__ = ["ComicStore"]
