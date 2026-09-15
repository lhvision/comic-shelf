"""Storage package for Paper Room comic archives."""
from __future__ import annotations

from .base import ComicStoreBase
from .chapters import ComicStoreChapterMixin
from .local import ComicStoreLocalMixin
from .media import ComicStoreMediaMixin
from .prefetch import ComicStorePrefetchMixin
from .utils import (
    CURRENT_DECODE_VERSION,
    IMAGE_EXTS,
    _NATURAL_SPLIT,
    _SAFE,
    _is_path_allowed,
    _write_json_atomic,
)
from ..config import MAX_PREFETCH


class ComicStore(
    ComicStoreBase,
    ComicStoreMediaMixin,
    ComicStoreChapterMixin,
    ComicStoreLocalMixin,
    ComicStorePrefetchMixin,
):
    """Local-first cache.

    Once ``album.json`` exists we never hit the network again for metadata
    unless the client explicitly asks for ``refresh=true``. Missing pages are
    lazy-downloaded only when they are actually viewed (or during an explicit
    "cache all" action).
    """

    pass


__all__ = [
    "ComicStore",
    "ComicStoreBase",
    "ComicStoreMediaMixin",
    "ComicStoreChapterMixin",
    "ComicStoreLocalMixin",
    "ComicStorePrefetchMixin",
    "CURRENT_DECODE_VERSION",
    "IMAGE_EXTS",
    "MAX_PREFETCH",
    "_SAFE",
    "_NATURAL_SPLIT",
    "_is_path_allowed",
    "_write_json_atomic",
]
