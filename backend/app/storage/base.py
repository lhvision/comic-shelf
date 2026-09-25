"""Base storage provider, filesystem directory mapping, thread synchronization, and metadata persistence."""
from __future__ import annotations

import datetime
import json
import logging
import os
import shutil
import threading
import uuid
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
from ..formatting import format_count
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
        self._download_waiters: dict[tuple[str, str, int], threading.Event] = {}

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

    def _migrate_flat_to_chapter(self, meta: ComicMeta, first_chapter_id: str) -> list[tuple[Path, Path]]:
        return []

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

    def _claim_page_download(self, source: str, source_id: str, index: int) -> tuple[threading.Event, bool]:
        key = (source, source_id, index)
        with self._locks_guard:
            existing = self._download_waiters.get(key)
            if existing is not None:
                return existing, False
            event = threading.Event()
            self._download_waiters[key] = event
            return event, True

    def _release_page_download(
        self, source: str, source_id: str, index: int, event: threading.Event
    ) -> None:
        with self._locks_guard:
            if self._download_waiters.get((source, source_id, index)) is event:
                self._download_waiters.pop((source, source_id, index), None)
        event.set()

    _SAVE_MARKER = ".in-progress"
    _REPLACED_DIR = "replaced"
    _REPLACED_REL = "replaced.rel"
    _WORK_DIR_NAME = ".work"
    _COMIC_REL = "comic.rel"

    def _work_dir(self) -> Path:
        return self.root / self._WORK_DIR_NAME

    def _ensure_work_dir(self) -> Path:
        path = self._work_dir()
        path.mkdir(exist_ok=True)
        return path

    def _new_work_path(self, prefix: str) -> Path:
        return self._ensure_work_dir() / f"{prefix}-{uuid.uuid4().hex}"

    def _new_work_item(self, prefix: str) -> Path:
        path = self._new_work_path(prefix)
        path.mkdir()
        return path

    def _write_work_comic_rel(self, work_item: Path, source: str, source_id: str) -> None:
        (work_item / self._COMIC_REL).write_text(f"{source}\n{source_id}\n", encoding="utf-8")

    def _comic_dir_from_work_item(self, work_item: Path) -> Path | None:
        rel_file = work_item / self._COMIC_REL
        if not rel_file.exists():
            return None
        lines = [line.strip() for line in rel_file.read_text(encoding="utf-8").splitlines() if line.strip()]
        if len(lines) < 2:
            return None
        source, source_id = lines[0], lines[1]
        if (
            not source
            or not source_id
            or source.startswith(".")
            or source_id.startswith(".")
            or "/" in source
            or "/" in source_id
            or ".." in source
            or ".." in source_id
        ):
            return None
        return self.comic_dir(source, source_id)

    def _begin_metadata_backup(self, album_path: Path, remote_path: Path) -> Path:
        album_path.parent.mkdir(parents=True, exist_ok=True)
        source_id = album_path.parent.name
        source = album_path.parent.parent.name
        backup_dir = self._new_work_item(".save")
        try:
            self._write_work_comic_rel(backup_dir, source, source_id)
            for path in (remote_path, album_path):
                if path.exists():
                    shutil.copy2(path, backup_dir / path.name)
            (backup_dir / self._SAVE_MARKER).write_bytes(b"")
        except OSError:
            shutil.rmtree(backup_dir, ignore_errors=True)
            raise
        return backup_dir

    def _rollback_metadata_backup(
        self,
        backup_dir: Path,
        paths: tuple[Path, Path],
        source: str,
        source_id: str,
        moved: list[tuple[Path, Path]] | None = None,
    ) -> None:
        with self._cache_guard:
            self._meta_cache.pop((source, source_id), None)
            self._fetched_cache.pop((source, source_id), None)
        for original, destination in reversed(moved or []):
            destination.replace(original)
        for path in paths:
            backup = backup_dir / path.name
            if backup.exists():
                shutil.copy2(backup, path)
            else:
                path.unlink(missing_ok=True)
        self._restore_replaced_dir(backup_dir)
        (backup_dir / self._SAVE_MARKER).unlink(missing_ok=True)
        shutil.rmtree(backup_dir, ignore_errors=True)

    def _finish_metadata_backup(self, backup_dir: Path) -> None:
        (backup_dir / self._SAVE_MARKER).unlink(missing_ok=True)
        shutil.rmtree(backup_dir, ignore_errors=True)

    def _stash_replaced_dir(self, backup_dir: Path, live: Path) -> None:
        comic_dir = self._comic_dir_from_work_item(backup_dir)
        if comic_dir is None:
            raise RuntimeError(f"save backup missing comic pointer: {backup_dir}")
        rel = live.resolve().relative_to(comic_dir.resolve()).as_posix()
        existed = live.exists()
        (backup_dir / self._REPLACED_REL).write_text(f"{rel}\n{int(existed)}\n", encoding="utf-8")
        if existed:
            live.rename(backup_dir / self._REPLACED_DIR)

    def _restore_replaced_dir(self, backup_dir: Path) -> None:
        rel_file = backup_dir / self._REPLACED_REL
        if not rel_file.exists():
            return
        lines = [line.strip() for line in rel_file.read_text(encoding="utf-8").splitlines() if line.strip()]
        if not lines:
            return
        rel = lines[0]
        existed = True if len(lines) < 2 else lines[1] == "1"
        if not rel or rel.startswith("/") or ".." in Path(rel).parts:
            return
        comic_dir = self._comic_dir_from_work_item(backup_dir)
        if comic_dir is None:
            return
        live = comic_dir / rel
        stash = backup_dir / self._REPLACED_DIR
        if stash.exists():
            if live.exists():
                shutil.rmtree(live)
            live.parent.mkdir(parents=True, exist_ok=True)
            stash.rename(live)
        elif not existed and live.exists():
            shutil.rmtree(live)

    def _replace_live_with_staging(self, backup_dir: Path, staging: Path, live: Path) -> None:
        self._stash_replaced_dir(backup_dir, live)
        staging.rename(live)

    def _restore_flat_layout_files(self, meta: ComicMeta) -> None:
        if meta.chapters:
            return
        for directory in (
            self.pages_dir(meta.source, meta.source_id),
            self.thumbs_dir(meta.source, meta.source_id),
        ):
            if not directory.is_dir():
                continue
            for child in list(directory.iterdir()):
                if not child.is_dir() or child.name.startswith("."):
                    continue
                for item in list(child.iterdir()):
                    if item.is_file():
                        destination = directory / item.name
                        if not destination.exists():
                            item.replace(destination)
                try:
                    child.rmdir()
                except OSError:
                    pass

    def recover_interrupted_saves(self) -> None:
        """Restore interrupted saves from library/.work; do not walk comic trees."""
        work = self._work_dir()
        if not work.is_dir():
            return
        failures: list[str] = []
        for backup_dir in sorted(path for path in work.iterdir() if path.is_dir() and not path.is_symlink()):
            name = backup_dir.name
            if name.startswith(".deleted-") or name.startswith(".tmp_"):
                shutil.rmtree(backup_dir, ignore_errors=True)
                continue
            if not name.startswith(".save-"):
                continue
            comic_dir = self._comic_dir_from_work_item(backup_dir)
            if comic_dir is None:
                logger.warning("Removing leftover save backup with no comic pointer: %s", backup_dir)
                shutil.rmtree(backup_dir, ignore_errors=True)
                continue
            source = comic_dir.parent.name
            source_id = comic_dir.name
            marker = backup_dir / self._SAVE_MARKER
            with self._lock_for(source, source_id):
                if not marker.exists():
                    logger.warning("Removing leftover backup after a finished save: %s", backup_dir)
                    shutil.rmtree(backup_dir, ignore_errors=True)
                    continue
                logger.warning("Restoring interrupted save for %s/%s from %s", source, source_id, backup_dir)
                try:
                    had_album = (backup_dir / "album.json").exists()
                    for name in ("remote.json", "album.json"):
                        src = backup_dir / name
                        dest = comic_dir / name
                        if src.exists():
                            shutil.copy2(src, dest)
                        else:
                            dest.unlink(missing_ok=True)
                    if (backup_dir / self._REPLACED_REL).exists():
                        self._restore_replaced_dir(backup_dir)
                    album_path = comic_dir / "album.json"
                    if album_path.exists() and not (backup_dir / self._REPLACED_REL).exists():
                        meta = ComicMeta.model_validate(json.loads(album_path.read_text(encoding="utf-8")))
                        self._restore_flat_layout_files(meta)
                    shutil.rmtree(backup_dir, ignore_errors=True)
                    if not had_album and not album_path.exists():
                        shutil.rmtree(comic_dir, ignore_errors=True)
                        continue
                except Exception:
                    logger.exception("Could not restore %s; leaving it for the next startup", backup_dir)
                    failures.append(str(backup_dir))
                    continue
                self._invalidate_cache(source, source_id)
        if failures:
            raise RuntimeError(
                "Could not restore interrupted saves: " + ", ".join(failures)
            )

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
                        "auto_update_interval_days": getattr(meta, "auto_update_interval_days", 15),
                        "last_auto_checked_at": getattr(meta, "last_auto_checked_at", ""),
                    })
            else:
                from ..db import purge_comic_db_records
                purge_comic_db_records(source, source_id)
        except Exception:
            logger.exception("Failed to refresh comic index for %s/%s", source, source_id)

    # ------------------------------------------------------------------
    # persistence
    # ------------------------------------------------------------------
    def save_fetched(
        self,
        fetched: FetchedComic,
        refresh: bool = False,
        *,
        backup_dir: Path | None = None,
    ) -> ComicMeta:
        """Save metadata and page descriptors under the comic lock.

        Preserve local visibility on refresh. A failed write rolls back JSON and
        this run's file moves. A crash leaves `.save-*/.in-progress` so startup
        can restore the previous JSON and any stashed page directory.
        """
        with self._lock_for(fetched.meta.source, fetched.meta.source_id):
            meta = fetched.meta

            existing_bundle = self.load_fetched(meta.source, meta.source_id)
            existing = existing_bundle.meta if existing_bundle is not None else None

            if refresh and existing is not None:
                if existing.custom_pages:
                    meta.custom_pages = True
                    meta.pages = existing.pages
                    meta.chapters = existing.chapters
                    meta.page_count = existing.page_count
                    fetched.remote_pages = existing_bundle.remote_pages

                meta.imported_at = existing.imported_at or meta.imported_at
                meta.favorite = existing.favorite
                meta.hidden_from_guest = existing.hidden_from_guest
                meta.auto_update_interval_days = getattr(existing, "auto_update_interval_days", 15)
                meta.last_auto_checked_at = getattr(meta, "last_auto_checked_at", "") or getattr(existing, "last_auto_checked_at", "")

            album_path = self.album_path(meta.source, meta.source_id)
            remote_path = self.remote_path(meta.source, meta.source_id)
            paths = (remote_path, album_path)
            if backup_dir is None:
                backup_dir = self._begin_metadata_backup(album_path, remote_path)
            moved: list[tuple[Path, Path]] = []
            try:
                if refresh and existing is not None:
                    if not existing.chapters and meta.chapters:
                        moved = self._migrate_flat_to_chapter(meta, meta.chapters[0].id)
                    for page in meta.pages:
                        target = self._chapter_page_path(meta, page)
                        page.cached = target.exists() and target.stat().st_size > 0

                _write_json_atomic(remote_path, {
                    "decode_version": CURRENT_DECODE_VERSION,
                    "remote_pages": [p.model_dump() for p in fetched.remote_pages],
                })
                _write_json_atomic(album_path, meta.model_dump())
                self._finish_metadata_backup(backup_dir)
            except Exception:
                self._rollback_metadata_backup(
                    backup_dir, paths, meta.source, meta.source_id, moved
                )
                raise
            self._invalidate_cache(meta.source, meta.source_id)
            return meta

    def record_auto_checked(self, source: str, source_id: str, checked_at: str) -> None:
        """Atomically updates last_auto_checked_at in album.json, cache, and DB index under lock."""
        with self._lock_for(source, source_id):
            meta = self.load_meta(source, source_id)
            if meta is not None:
                meta_copy = meta.model_copy(deep=True)
                meta_copy.last_auto_checked_at = checked_at
                p = self.album_path(source, source_id)
                _write_json_atomic(p, meta_copy.model_dump())
                try:
                    mtime = p.stat().st_mtime
                except Exception:
                    mtime = 0.0
                with self._cache_guard:
                    self._meta_cache[(source, source_id)] = (mtime, meta_copy)
        from ..db import record_comic_auto_checked
        record_comic_auto_checked(source, source_id, checked_at)

    def save_auto_update(self, fetched: FetchedComic, checked_at: str) -> ComicMeta | None:
        """巡检发现新章节时写盘：只换章节与画页，其余资料以锁内重读的最新版为准。

        抓取要花几秒，期间馆长可能改了资料或删了这本；删了就返回 None，不再写回来。
        """
        source, source_id = fetched.meta.source, fetched.meta.source_id
        with self._lock_for(source, source_id):
            latest = self.load_meta(source, source_id)
            if latest is None:
                return None
            merged = latest.model_copy(deep=True)
            merged.chapters = fetched.meta.chapters
            merged.pages = fetched.meta.pages
            merged.page_count = fetched.meta.page_count
            if fetched.meta.updated_at:
                merged.updated_at = fetched.meta.updated_at
            merged.last_auto_checked_at = checked_at
            fetched.meta = merged
            return self.save_fetched(fetched, refresh=True)

    def load_meta(self, source: str, source_id: str, verify_cache: bool = False) -> ComicMeta | None:
        """Loads comic metadata from memory cache or album.json with self-healing support."""
        with self._lock_for(source, source_id):
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
                for page in meta.pages:
                    page.cached = self._chapter_page_path(meta, page).exists()

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

            # Auto-heal: If PicAcg comic lacks cover_indices, backfill dual-source cover mapping
            if meta.source == "picacg" and not meta.cover_indices and meta.page_count:
                meta.cover_indices = ([1] + list(range(1, meta.cover_count)))[: meta.cover_count]

            # Auto-heal: If comic has chapters but first chapter start > 1 (orphaned flat pages 1..start-1 exist)
            if meta.chapters and meta.pages and meta.chapters[0].start > 1:
                healed = meta.model_copy(deep=True)
                orphaned_count = healed.chapters[0].start - 1
                existing_ids = {chapter.id for chapter in healed.chapters}
                ordinal = 1
                while f"c{ordinal}" in existing_ids:
                    ordinal += 1
                first_id = f"c{ordinal}"
                first = Chapter(id=first_id, index=1, title="第 1 话", page_count=orphaned_count, start=1)
                for page in healed.pages:
                    if page.index <= orphaned_count:
                        page.chapter = first_id
                healed.chapters.insert(0, first)
                for index, chapter in enumerate(healed.chapters, start=1):
                    chapter.index = index
                moved: list[tuple[Path, Path]] = []
                backup_dir: Path | None = None
                try:
                    backup_dir = self._begin_metadata_backup(path, self.remote_path(source, source_id))
                    moved = self._migrate_flat_to_chapter(healed, first_id)
                    _write_json_atomic(path, healed.model_dump())
                    self._finish_metadata_backup(backup_dir)
                    backup_dir = None
                except OSError as exc:
                    if backup_dir is not None:
                        self._rollback_metadata_backup(
                            backup_dir,
                            (self.remote_path(source, source_id), path),
                            source,
                            source_id,
                            moved,
                        )
                    logger.warning("Deferred chapter repair for %s/%s: %s", source, source_id, exc)
                else:
                    meta = healed
                    mtime = path.stat().st_mtime

            # Display-only normalization must not rewrite a stale snapshot or require write access.
            meta.views = format_count(meta.views)
            meta.likes = format_count(meta.likes)

            with self._cache_guard:
                self._meta_cache[(source, source_id)] = (mtime, meta)
            return meta

    def load_fetched(self, source: str, source_id: str, verify_cache: bool = False) -> FetchedComic | None:
        """Loads both metadata and remote page descriptors, executing self-healing decode migrations if needed."""
        with self._lock_for(source, source_id):
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

            version = int(data.get("decode_version", 1) or 1)
            if version < CURRENT_DECODE_VERSION:
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
        try:
            from ..jobs import cancel_job
            cancel_job(source, source_id)
        except Exception:
            pass
        with self._lock_for(source, source_id):
            target = self.comic_dir(source, source_id)
            existed = target.exists()
            if existed:
                trash = self._new_work_path(".deleted")
                target.rename(trash)
                shutil.rmtree(trash, ignore_errors=True)
            self._invalidate_cache(source, source_id)
            db_purged = False
            try:
                from ..db import purge_comic_db_records
                db_purged = bool(purge_comic_db_records(source, source_id))
            except Exception as e:
                logger.exception("Failed to purge comic db records for %s/%s: %s", source, source_id, e)
            return existed or db_purged

    def update_metadata(self, source: str, source_id: str, updates: dict[str, Any]) -> ComicMeta:
        with self._lock_for(source, source_id):
            meta = self.load_meta(source, source_id)
            if meta is None:
                raise HTTPException(status_code=404, detail="漫画不存在")
            meta = meta.model_copy(deep=True)

            for field in ("title", "authors", "works", "actors", "tags", "description", "uploader", "hidden_from_guest", "custom_pages", "auto_update_interval_days"):
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
            _write_json_atomic(self.album_path(source, source_id), meta.model_dump())
            self._invalidate_cache(source, source_id)
        if "cover_indices" in updates and updates["cover_indices"] is not None:
            # Regenerate covers with active pre-warming (both 720px & 360px WEBP + JPEG)
            fetched = self.load_fetched(source, source_id)
            if fetched is not None:
                for idx in range(1, len(meta.cover_paths()) + 1):
                    try:
                        self.ensure_webp_cover(meta, fetched, idx)
                        self.ensure_webp_cover(meta, fetched, idx, COVER_THUMB_WIDTH)
                    except Exception:
                        pass

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
        legacy_migrated = False
        legacy_path = None
        if not path.exists() and source == "jm":
            candidate = self.discovery_dir() / f"{self._safe(timeframe)}.json"
            if candidate.exists():
                path = candidate
                legacy_path = candidate
                legacy_migrated = True
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            feed = DiscoveryFeed.model_validate(data)
            if legacy_migrated and legacy_path:
                self.save_discovery_feed(feed)
                try:
                    legacy_path.unlink(missing_ok=True)
                except Exception:
                    pass
            # Auto-heal legacy picacomic.com domain to canonical picawang.com
            if feed.source == "picacg":
                pica_healed = False
                for it in feed.items:
                    if it.url and ("picacomic.com/comic/" in it.url):
                        it.url = f"https://picawang.com/comic/{it.source_id}"
                        pica_healed = True
                if pica_healed:
                    self.save_discovery_feed(feed)
            return feed
        except Exception:
            return None

    def save_discovery_feed(self, feed: DiscoveryFeed) -> None:
        src = getattr(feed, "source", "jm") or "jm"
        path = self.discovery_path(feed.timeframe, src)
        _write_json_atomic(path, feed.model_dump())
