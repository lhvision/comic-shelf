from __future__ import annotations

import datetime
import re
from typing import TYPE_CHECKING

from .base import ComicProvider

if TYPE_CHECKING:
    from ..models import FetchedComic, RemotePage

_SAFE_ID = re.compile(r"[^a-zA-Z0-9_-]+")


class LocalProvider(ComicProvider):
    """Local-first custom comic / image collection provider (本地自建 / 拆帧图集)."""

    key = "local"
    label = "本地自建"
    short_label = "本地"
    id_pattern = r"^[a-zA-Z0-9_-]+$"
    example = "tiya-frames"

    def normalize_id(self, raw: str) -> str:
        clean = raw.strip()
        if clean.upper().startswith(("LOC_", "LOC-")):
            clean = clean[4:]
        clean = _SAFE_ID.sub("_", clean).strip("._")
        return clean.lower() if clean else "collection"

    def generate_id(self) -> str:
        """Generates a clean, time-ordered identifier for local comics, e.g. '20260918_010452'."""
        return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    def display_id(self, source_id: str) -> str:
        """Constructs human-facing display_id / book plate stamp (e.g. 'LOC_20260918_010452').

        If source_id has a historical or redundant 'loc_' prefix (e.g. 'loc_20260917_194250'),
        it strips it to avoid ugly stuttering like 'LOC_loc_20260917_194250'.
        """
        clean = source_id.strip()
        if clean.lower().startswith("loc_") or clean.lower().startswith("loc-"):
            clean = clean[4:]
        clean = clean.strip("._")
        return f"LOC_{clean}" if clean else "LOC_collection"

    def fetch(
        self,
        raw_id: str,
        *,
        existing: FetchedComic | None = None,
    ) -> FetchedComic:
        if existing is not None:
            return existing
        from fastapi import HTTPException

        raise HTTPException(
            status_code=400,
            detail=f"本地漫画 '{raw_id}' 尚未创建，请通过自建工坊或目录导入创建",
        )

    def download_page(self, comic: FetchedComic, page: RemotePage) -> bytes:
        from ..config import LIBRARY_DIR

        # For local provider, files are located on disk inside library/local/<source_id>/pages/
        source_id = comic.meta.source_id
        if page.chapter:
            path = LIBRARY_DIR / "local" / source_id / "pages" / page.chapter / page.file
        else:
            path = LIBRARY_DIR / "local" / source_id / "pages" / page.file

        if path.exists():
            return path.read_bytes()
        raise FileNotFoundError(f"本地页面文件不存在：{path}")
