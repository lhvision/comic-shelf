"""Base storage provider, filesystem directory mapping, thread synchronization, and metadata persistence."""
from __future__ import annotations

import datetime
import json
import logging
import os
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from ..config import (
    COVER_THUMB_WIDTH,
    DATA_DIR,
    LIBRARY_DIR,
)
from ..models import (
    Chapter,
    ComicDetail,
    ComicMeta,
    DiscoveryFeed,
    FetchedComic,
    LibrarySummary,
    PageRecord,
    RemotePage,
)
from .utils import (
    CURRENT_DECODE_VERSION,
    _SAFE,
    _write_json_atomic,
)

logger = logging.getLogger(__name__)


class ComicStoreBase:
    """Base repository managing filesystem directory structures, thread locks, and album metadata."""

    def __init__(self, root: Path = LIBRARY_DIR) -> None:
        self.root = root
        self._page_locks: dict[tuple[str, str, int] | tuple[str, str], threading.RLock] = {}
        self._locks_guard = threading.Lock()
        self._thumb_semaphore = threading.BoundedSemaphore(
            int(os.getenv("COMIC_SHELF_THUMB_CONCURRENCY", "4"))
        )
        self._meta_cache: dict[tuple[str, str], tuple[float, ComicMeta]] = {}
        self._fetched_cache: dict[tuple[str, str], tuple[float, float, FetchedComic]] = {}
        self._cache_guard = threading.Lock()
        self._cover_executor = ThreadPoolExecutor(
            max_workers=int(os.getenv("COMIC_SHELF_COVER_CONCURRENCY", "2")),
            thread_name_prefix="cover-worker",
        )

    # ------------------------------------------------------------------
    # paths
    # ------------------------------------------------------------------
    @staticmethod
    def _safe(value: str) -> str:
        return _SAFE.sub("_", value).strip("._") or "_"

    def comic_dir(self, source: str, source_id: str) -> Path:
        return self.root / self._safe(source) / self._safe(source_id)

    def album_path(self, source: str, source_id: str) -> Path:
        return self.comic_dir(source, source_id) / "album.json"

    def remote_path(self, source: str, source_id: str) -> Path:
        return self.comic_dir(source, source_id) / "remote.json"

    def pages_dir(self, source: str, source_id: str) -> Path:
        return self.comic_dir(source, source_id) / "pages"

    def covers_dir(self, source: str, source_id: str) -> Path:
        return self.comic_dir(source, source_id) / "covers"

    def page_path(self, meta: ComicMeta, index: int) -> Path:
        page = next((p for p in meta.pages if p.index == index), None)
        if page is not None:
            return self._chapter_page_path(meta, page)
        return self.pages_dir(meta.source, meta.source_id) / f"{index:05d}.webp"

    def _chapter_page_path(self, meta: ComicMeta, page: PageRecord) -> Path:
        """Route a page to ``pages/<chapter>/<file>`` for multi-chapter albums,
        or the legacy flat ``pages/<file>`` layout for single-chapter albums."""
        base = self.pages_dir(meta.source, meta.source_id)
        filename = Path(page.file).name or f"{page.index:05d}.webp"
        if page.chapter:
            return base / self._safe(page.chapter) / filename
        return base / filename

    def cover_path(self, meta: ComicMeta, index: int, width: int | None = None, ext: str = "jpg") -> Path:
        clean_ext = "webp" if ext.lower().lstrip(".") == "webp" else "jpg"
        suffix = f".{clean_ext}"
        if width and 0 < width <= COVER_THUMB_WIDTH:
            return self.covers_dir(meta.source, meta.source_id) / f"{index:03d}_{width}{suffix}"
        return self.covers_dir(meta.source, meta.source_id) / f"{index:03d}{suffix}"

    def thumbs_dir(self, source: str, source_id: str) -> Path:
        return self.comic_dir(source, source_id) / "thumbs"

    def page_thumb_path(self, meta: ComicMeta, index: int, ext: str = "webp") -> Path:
        page = next((p for p in meta.pages if p.index == index), None)
        if page is not None:
            return self._chapter_thumb_path(meta, page, ext=ext)
        clean_ext = "webp" if ext.lower().lstrip(".") == "webp" else "jpg"
        return self.thumbs_dir(meta.source, meta.source_id) / f"{index:05d}.{clean_ext}"

    def _chapter_thumb_path(self, meta: ComicMeta, page: PageRecord, ext: str = "webp") -> Path:
        clean_ext = "webp" if ext.lower().lstrip(".") == "webp" else "jpg"
        filename = f"{page.index:05d}.{clean_ext}"
        if page.chapter:
            return self.thumbs_dir(meta.source, meta.source_id) / self._safe(page.chapter) / filename
        return self.thumbs_dir(meta.source, meta.source_id) / filename

    def chapter_covers_dir(self, source: str, source_id: str) -> Path:
        return self.covers_dir(source, source_id) / "chapters"

    def chapter_cover_path(
        self, meta: ComicMeta, chapter: Chapter, width: int | None = None, ext: str = "jpg"
    ) -> Path:
        clean_ext = "webp" if ext.lower().lstrip(".") == "webp" else "jpg"
        suffix = f".{clean_ext}"
        if width and 0 < width <= COVER_THUMB_WIDTH:
            return self.chapter_covers_dir(meta.source, meta.source_id) / f"{self._safe(chapter.id)}_{width}{suffix}"
        return self.chapter_covers_dir(meta.source, meta.source_id) / f"{self._safe(chapter.id)}{suffix}"

    # ------------------------------------------------------------------
    # polymorphic mixin hooks & defaults
    # ------------------------------------------------------------------
    def cached_page_count(self, meta: ComicMeta) -> int:
        return sum(1 for page in meta.pages if page.cached)

    def reconcile_cached_pages(self, meta: ComicMeta) -> int:
        return self.cached_page_count(meta)

    def _migrate_flat_to_chapter(self, meta: ComicMeta, first_chapter_id: str) -> None:
        pass

    def _migrate_decode_v2(
        self,
        meta: ComicMeta,
        pages: list[RemotePage],
        remote_path: Path,
        data: dict,
    ) -> None:
        pass

    def ensure_webp_cover(
        self,
        meta: ComicMeta,
        fetched: FetchedComic | None = None,
        index: int = 1,
        width: int | None = None,
    ) -> Path:
        return self.cover_path(meta, index, width, ext="webp")

    # ------------------------------------------------------------------
    # locks & cache
    # ------------------------------------------------------------------
    def _lock_for(self, source: str, source_id: str) -> threading.RLock:
        with self._locks_guard:
            return self._page_locks.setdefault((source, source_id), threading.RLock())

    def _lock_for_page(self, source: str, source_id: str, index: int) -> threading.RLock:
        with self._locks_guard:
            return self._page_locks.setdefault((source, source_id, index), threading.RLock())

    def _invalidate_cache(self, source: str, source_id: str) -> None:
        with self._cache_guard:
            self._meta_cache.pop((source, source_id), None)
            self._fetched_cache.pop((source, source_id), None)
        try:
            album_path = self.album_path(source, source_id)
            if album_path.exists():
                meta = self.load_meta(source, source_id)
                if meta:
                    from ..db import upsert_comic_index
                    try:
                        mtime = album_path.stat().st_mtime
                    except Exception:
                        mtime = 0.0
                    cached_pages = self.cached_page_count(meta)
                    upsert_comic_index({
                        "source": meta.source,
                        "source_id": meta.source_id,
                        "display_id": meta.display_id,
                        "title": meta.title,
                        "authors_json": json.dumps(meta.authors, ensure_ascii=False),
                        "works_json": json.dumps(meta.works, ensure_ascii=False),
                        "actors_json": json.dumps(meta.actors, ensure_ascii=False),
                        "tags_json": json.dumps(meta.tags, ensure_ascii=False),
                        "chapter_titles_json": json.dumps([c.title for c in meta.chapters], ensure_ascii=False),
                        "page_count": meta.page_count,
                        "cached_pages": cached_pages,
                        "cover_count": meta.cover_count,
                        "cover_indices_json": json.dumps(meta.cover_indices, ensure_ascii=False),
                        "views": str(meta.views),
                        "likes": str(meta.likes),
                        "uploaded_at": meta.published_at,
                        "published_at": meta.published_at,
                        "updated_at": meta.updated_at,
                        "imported_at": meta.imported_at,
                        "hidden_from_guest": 1 if getattr(meta, "hidden_from_guest", False) else 0,
                        "mtime": mtime,
                    })
            else:
                from ..db import delete_comic_dialogues, delete_comic_index
                delete_comic_index(source, source_id)
                delete_comic_dialogues(source, source_id)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # persistence
    # ------------------------------------------------------------------
    def save_fetched(self, fetched: FetchedComic, refresh: bool = False) -> ComicMeta:
        """Atomically persists comic metadata and remote page descriptors to disk."""
        meta = fetched.meta

        existing_bundle = self.load_fetched(meta.source, meta.source_id)
        existing = existing_bundle.meta if existing_bundle is not None else None

        if refresh and existing is not None:
            if existing.custom_pages:
                meta.custom_pages = True
                meta.pages = existing.pages
                meta.chapters = existing.chapters
                meta.page_count = existing.page_count

            meta.imported_at = existing.imported_at or meta.imported_at
            meta.favorite = existing.favorite

            # 单章节升级多章节时，自动将平铺旧文件迁移至首话子目录
            if not existing.chapters and meta.chapters:
                self._migrate_flat_to_chapter(meta, meta.chapters[0].id)

            for page in meta.pages:
                target = self._chapter_page_path(meta, page)
                try:
                    page.cached = target.exists() and target.stat().st_size > 0
                except Exception:
                    page.cached = False

        _write_json_atomic(self.album_path(meta.source, meta.source_id), meta.model_dump())
        _write_json_atomic(
            self.remote_path(meta.source, meta.source_id),
            {
                "decode_version": CURRENT_DECODE_VERSION,
                "remote_pages": [p.model_dump() for p in fetched.remote_pages],
            },
        )
        self._invalidate_cache(meta.source, meta.source_id)
        return meta

    def load_meta(self, source: str, source_id: str, verify_cache: bool = False) -> ComicMeta | None:
        """Loads comic metadata from memory cache or album.json with self-healing support."""
        path = self.album_path(source, source_id)
        if not path.exists():
            return None

        try:
            mtime = path.stat().st_mtime
        except Exception:
            return None

        if not verify_cache:
            with self._cache_guard:
                cached = self._meta_cache.get((source, source_id))
                if cached is not None and cached[0] == mtime:
                    return cached[1]

        try:
            meta = ComicMeta.model_validate(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            return None

        if verify_cache:
            changed = False
            for page in meta.pages:
                actual = self._chapter_page_path(meta, page).exists()
                if page.cached != actual:
                    page.cached = actual
                    changed = True
            if changed:
                _write_json_atomic(path, meta.model_dump())
                try:
                    mtime = path.stat().st_mtime
                except Exception:
                    pass

        if (
            not meta.chapters
            and meta.pages
            and any(page.chapter for page in meta.pages)
        ):
            raw_chapters = (meta.raw or {}).get("chapters") or []
            if raw_chapters:
                rebuilt: list[Chapter] = []
                for ordinal, item in enumerate(raw_chapters, start=1):
                    try:
                        chapter = Chapter.model_validate(item)
                    except Exception:
                        continue
                    chapter.title = " ".join(str(chapter.title).split())
                    chapter.index = ordinal
                    rebuilt.append(chapter)
                if rebuilt:
                    meta.chapters = rebuilt
                    _write_json_atomic(path, meta.model_dump())
                    try:
                        mtime = path.stat().st_mtime
                    except Exception:
                        pass

        # Auto-heal: If PicAcg comic lacks cover_indices, backfill dual-source cover mapping
        if meta.source == "picacg" and not meta.cover_indices and meta.page_count:
            meta.cover_indices = ([1] + list(range(1, meta.cover_count)))[: meta.cover_count]

        # Auto-heal: If comic has chapters but first chapter start > 1 (orphaned flat pages 1..start-1 exist)
        if meta.chapters and meta.pages and meta.chapters[0].start > 1:
            orphaned_count = meta.chapters[0].start - 1
            first_id = "c1"
            c1 = Chapter(id=first_id, index=1, title="第 1 话", page_count=orphaned_count, start=1)
            self._migrate_flat_to_chapter(meta, first_id)
            for p in meta.pages:
                if p.index < meta.chapters[0].start:
                    p.chapter = first_id
            new_chapters = [c1]
            for idx, ch in enumerate(meta.chapters, start=2):
                ch.index = idx
                new_chapters.append(ch)
            meta.chapters = new_chapters
            _write_json_atomic(path, meta.model_dump())
            try:
                mtime = path.stat().st_mtime
            except Exception:
                pass

        with self._cache_guard:
            self._meta_cache[(source, source_id)] = (mtime, meta)
        return meta

    def load_fetched(self, source: str, source_id: str, verify_cache: bool = False) -> FetchedComic | None:
        """Loads both metadata and remote page descriptors, executing self-healing decode migrations if needed."""
        meta = self.load_meta(source, source_id, verify_cache=verify_cache)
        if meta is None:
            return None

        remote_path = self.remote_path(source, source_id)
        album_path = self.album_path(source, source_id)
        try:
            album_mtime = album_path.stat().st_mtime
            remote_mtime = remote_path.stat().st_mtime if remote_path.exists() else 0.0
        except Exception:
            album_mtime, remote_mtime = 0.0, 0.0

        if not verify_cache:
            with self._cache_guard:
                cached = self._fetched_cache.get((source, source_id))
                if cached is not None and cached[0] == album_mtime and cached[1] == remote_mtime:
                    return cached[2]

        pages: list[RemotePage] = []
        data: dict = {}
        if remote_path.exists():
            try:
                data = json.loads(remote_path.read_text(encoding="utf-8"))
                pages = [RemotePage.model_validate(p) for p in data.get("remote_pages", [])]
            except Exception:
                data = {}
                pages = []

        if pages and any(not page.scramble_id for page in pages):
            scramble_id = str(
                (meta.raw or {}).get("album", {}).get("scramble_id") or ""
            )
            for page in pages:
                if not page.scramble_id:
                    page.scramble_id = scramble_id
            data["remote_pages"] = [page.model_dump() for page in pages]
            if remote_path.exists():
                _write_json_atomic(remote_path, data)
                try:
                    remote_mtime = remote_path.stat().st_mtime
                except Exception:
                    pass

        version = int(data.get("decode_version", 1) or 1)
        if version < CURRENT_DECODE_VERSION:
            with self._lock_for(source, source_id):
                self._migrate_decode_v2(meta, pages, remote_path, data)
                try:
                    remote_mtime = remote_path.stat().st_mtime
                except Exception:
                    pass

        fetched = FetchedComic(meta=meta, remote_pages=pages)
        with self._cache_guard:
            self._fetched_cache[(source, source_id)] = (album_mtime, remote_mtime, fetched)
        return fetched

    # ------------------------------------------------------------------
    # library queries & summary helpers
    # ------------------------------------------------------------------
    def summary(self, meta: ComicMeta) -> LibrarySummary:
        cached_count = self.cached_page_count(meta)
        return LibrarySummary(
            source=meta.source,
            source_id=meta.source_id,
            display_id=meta.display_id,
            title=meta.title,
            authors=meta.authors,
            works=meta.works,
            actors=meta.actors,
            tags=meta.tags,
            favorite=meta.favorite,
            hidden_from_guest=getattr(meta, "hidden_from_guest", False),
            page_count=meta.page_count,
            views=meta.views,
            likes=meta.likes,
            uploaded_at=meta.published_at,
            published_at=meta.published_at,
            updated_at=meta.updated_at,
            imported_at=meta.imported_at,
            cover_paths=meta.cover_paths(),
            cached_pages=cached_count,
            cover_count=meta.cover_count,
            chapter_titles=[c.title for c in meta.chapters],
        )

    def detail(self, meta: ComicMeta) -> ComicDetail:
        cached = self.reconcile_cached_pages(meta)
        return ComicDetail(
            meta=meta,
            cached_pages=cached,
            cache_complete=cached >= meta.page_count,
            cover_paths=meta.cover_paths(),
        )

    def delete(self, source: str, source_id: str) -> bool:
        target = self.comic_dir(source, source_id)
        self._invalidate_cache(source, source_id)
        if target.exists():
            shutil.rmtree(target)
            return True
        return False

    def update_metadata(self, source: str, source_id: str, updates: dict[str, Any]) -> ComicMeta:
        meta = self.load_meta(source, source_id)
        if meta is None:
            raise HTTPException(status_code=404, detail="漫画不存在")

        for field in ("title", "authors", "works", "actors", "tags", "description", "uploader", "hidden_from_guest", "custom_pages"):
            if field in updates and updates[field] is not None:
                setattr(meta, field, updates[field])

        meta.updated_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if "cover_indices" in updates and updates["cover_indices"] is not None:
            raw_indices = updates["cover_indices"]
            max_p = max(1, meta.page_count)
            valid_indices: list[int] = []
            for slot_i, item in enumerate(raw_indices, start=1):
                default_slot = min(slot_i, max_p)
                try:
                    val = int(item)
                    if val < 1:
                        val = 1
                    elif val > max_p:
                        val = default_slot
                    valid_indices.append(val)
                except (ValueError, TypeError):
                    valid_indices.append(default_slot)
            meta.cover_indices = valid_indices[:4]
            # Clean old covers so they get regenerated from the new indices
            covers_dir = self.covers_dir(source, source_id)
            if covers_dir.exists():
                for f in list(covers_dir.iterdir()):
                    if f.is_file() and f.suffix.lower() in {".jpg", ".jpeg", ".webp"}:
                        f.unlink(missing_ok=True)
            # Regenerate covers with active pre-warming (both 720px & 360px WEBP + JPEG)
            fetched = self.load_fetched(source, source_id)
            if fetched is not None:
                for idx in range(1, len(meta.cover_paths()) + 1):
                    try:
                        self.ensure_webp_cover(meta, fetched, idx)
                        self.ensure_webp_cover(meta, fetched, idx, COVER_THUMB_WIDTH)
                    except Exception:
                        pass

        _write_json_atomic(self.album_path(source, source_id), meta.model_dump())
        self._invalidate_cache(source, source_id)
        return meta

    # ------------------------------------------------------------------
    # discovery feeds & rankings cache
    # ------------------------------------------------------------------
    def discovery_dir(self) -> Path:
        p = DATA_DIR / "discovery"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def discovery_path(self, timeframe: str, source: str = "jm") -> Path:
        return self.discovery_dir() / f"{self._safe(source)}_{self._safe(timeframe)}.json"

    def load_discovery_feed(self, timeframe: str, source: str = "jm") -> DiscoveryFeed | None:
        path = self.discovery_path(timeframe, source)
        if not path.exists() and source == "jm":
            legacy_path = self.discovery_dir() / f"{self._safe(timeframe)}.json"
            if legacy_path.exists():
                path = legacy_path
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return DiscoveryFeed.model_validate(data)
        except Exception:
            return None

    def save_discovery_feed(self, feed: DiscoveryFeed) -> None:
        src = getattr(feed, "source", "jm") or "jm"
        path = self.discovery_path(feed.timeframe, src)
        _write_json_atomic(path, feed.model_dump())
