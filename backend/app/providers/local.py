from __future__ import annotations

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
        if clean.upper().startswith("LOC_") or clean.upper().startswith("LOC-"):
            clean = clean[4:]
        clean = _SAFE_ID.sub("_", clean).strip("._")
        return clean.lower() if clean else "collection"

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
