"""Chapter mixin managing multi-chapter directory migrations, title editing, and deletion."""
from __future__ import annotations

import datetime
import logging
import shutil
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from ..models import Chapter, ComicMeta, PageRecord, RemotePage
from .utils import CURRENT_DECODE_VERSION, _write_json_atomic

logger = logging.getLogger(__name__)


class ComicStoreChapterMixin:
    """Provides chapter organization, directory migration, and title editing operations."""

    def _migrate_flat_to_chapter(self: Any, meta: ComicMeta, first_chapter_id: str) -> list[tuple[Path, Path]]:
        """Move legacy flat pages and thumbnails into a chapter directory.

        Returns (original, destination) pairs so the caller can undo the moves
        if metadata persistence fails. A failed move rolls back this migration.
        """
        safe_chap = self._safe(first_chapter_id)
        moved: list[tuple[Path, Path]] = []
        try:
            for directory in (
                self.pages_dir(meta.source, meta.source_id),
                self.thumbs_dir(meta.source, meta.source_id),
            ):
                if not directory.exists():
                    continue
                target_dir = directory / safe_chap
                target_dir.mkdir(parents=True, exist_ok=True)
                for item in list(directory.iterdir()):
                    if item.is_file():
                        destination = target_dir / item.name
                        if not destination.exists():
                            item.rename(destination)
                            moved.append((item, destination))
        except OSError:
            for original, destination in reversed(moved):
                destination.replace(original)
            raise
        return moved

    def update_chapter_title(self: Any, source: str, source_id: str, chapter_id: str, new_title: str) -> ComicMeta:
        with self._lock_for(source, source_id):
            meta = self.load_meta(source, source_id)
            if meta is None:
                raise HTTPException(status_code=404, detail="本子还没有导入本地书库")

            chapter = next((c for c in meta.chapters if c.id == chapter_id), None)
            if chapter is None:
                raise HTTPException(status_code=404, detail=f"未找到章节：{chapter_id}")

            chapter.title = new_title.strip() or f"第 {chapter.index} 话"
            if source != "local":
                meta.custom_pages = True
            meta.updated_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            _write_json_atomic(self.album_path(source, source_id), meta.model_dump())
            self._invalidate_cache(source, source_id)
            return meta

    def delete_chapter(self: Any, source: str, source_id: str, chapter_id: str) -> ComicMeta:
        with self._lock_for(source, source_id):
            fetched = self.load_fetched(source, source_id)
            if fetched is None:
                raise HTTPException(status_code=404, detail="本子还没有导入本地书库")

            meta = fetched.meta
            chapter = next((c for c in meta.chapters if c.id == chapter_id), None)
            if chapter is None:
                raise HTTPException(status_code=404, detail=f"未找到章节：{chapter_id}")

            safe_cid = self._safe(chapter_id)
            chap_dir = self.pages_dir(source, source_id) / safe_cid
            if chap_dir.exists():
                shutil.rmtree(chap_dir, ignore_errors=True)

            thumb_dir = self.thumbs_dir(source, source_id) / safe_cid
            if thumb_dir.exists():
                shutil.rmtree(thumb_dir, ignore_errors=True)

            chap_cover = self.chapter_cover_path(meta, chapter)
            chap_cover.unlink(missing_ok=True)

            meta.pages = [p for p in meta.pages if p.chapter != chapter_id]
            fetched.remote_pages = [rp for rp in fetched.remote_pages if rp.chapter != chapter_id]
            meta.chapters = [c for c in meta.chapters if c.id != chapter_id]

            reindexed_pages: list[PageRecord] = []
            reindexed_remote: list[RemotePage] = []
            global_idx = 1

            for c_idx, ch in enumerate(meta.chapters, start=1):
                ch.index = c_idx
                ch.start = global_idx
                ch_pages = [p for p in meta.pages if p.chapter == ch.id]
                ch.page_count = len(ch_pages)
                for p in ch_pages:
                    p.index = global_idx
                    reindexed_pages.append(p)
                    global_idx += 1

            if not meta.chapters:
                for p in meta.pages:
                    p.index = global_idx
                    p.chapter = ""
                    reindexed_pages.append(p)
                    global_idx += 1

            for rp in fetched.remote_pages:
                matching_p = next((p for p in reindexed_pages if p.chapter == rp.chapter and p.file == rp.file), None)
                if matching_p is not None:
                    rp.index = matching_p.index
                    reindexed_remote.append(rp)

            meta.pages = reindexed_pages
            meta.page_count = len(reindexed_pages)
            fetched.remote_pages = reindexed_remote
            if source != "local":
                meta.custom_pages = True
            meta.updated_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            _write_json_atomic(self.album_path(source, source_id), meta.model_dump())
            remote_data = {
                "decode_version": CURRENT_DECODE_VERSION,
                "remote_pages": [rp.model_dump() for rp in fetched.remote_pages],
            }
            _write_json_atomic(self.remote_path(source, source_id), remote_data)
            self._invalidate_cache(source, source_id)
            return meta
