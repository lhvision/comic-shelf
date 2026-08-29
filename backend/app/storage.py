from __future__ import annotations

import datetime
import json
import logging
import os
import re
import shutil
import tempfile
import threading
from pathlib import Path
from typing import Any, Callable, Iterable

from fastapi import HTTPException

from .config import (
    COVER_QUALITY,
    COVER_WIDTH,
    DATA_DIR,
    LIBRARY_DIR,
    MAX_PREFETCH,
    PAGE_THUMB_QUALITY,
    PAGE_THUMB_WIDTH,
    TMP_DIR,
)
from .models import (
    Chapter,
    ComicDetail,
    ComicMeta,
    DiscoveryFeed,
    DiscoveryItem,
    FetchedComic,
    ImportResult,
    LibrarySummary,
    PageRecord,
    RemotePage,
)
from .providers.local import LocalProvider

logger = logging.getLogger(__name__)

_SAFE = re.compile(r"[^a-zA-Z0-9._-]+")

# v1 stored raw JM images (scrambled). v2 stores de-scrambled images using
# jmcomic's official JmImageTool algorithm. Existing v1 caches are migrated
# locally, without re-downloading anything from the remote site.
CURRENT_DECODE_VERSION = 2


def _write_json_atomic(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = None, None
    try:
        fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
        tmp = Path(tmp_name)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if tmp is not None and tmp.exists():
            tmp.unlink(missing_ok=True)


def _is_path_allowed(path: Path) -> bool:
    proj_root = Path(__file__).resolve().parents[2]
    allowed_bases = [
        DATA_DIR.resolve(),
        LIBRARY_DIR.resolve(),
        TMP_DIR.resolve(),
        proj_root.resolve(),
        Path.cwd().resolve(),
    ]
    extra = os.getenv("COMIC_SHELF_ALLOWED_DIRS", "").strip()
    if extra:
        for p in extra.split(os.pathsep):
            if p.strip():
                try:
                    allowed_bases.append(Path(p.strip()).expanduser().resolve())
                except Exception as e:
                    logger.warning("Failed to parse allowed import path '%s': %s", p, e)
    try:
        resolved = path.resolve()
        return any(resolved == base or resolved.is_relative_to(base) for base in allowed_bases)
    except Exception:
        return False


class ComicStore:
    """Local-first cache.

    Once ``album.json`` exists we never hit the network again for metadata
    unless the client explicitly asks for ``refresh=true``. Missing pages are
    lazy-downloaded only when they are actually viewed (or during an explicit
    "cache all" action).
    """

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
        if page is None:
            raise KeyError(f"页 {index} 不存在（共 {meta.page_count} 页）")
        return self._chapter_page_path(meta, page)

    def _chapter_page_path(self, meta: ComicMeta, page: PageRecord) -> Path:
        """Route a page to ``pages/<chapter>/<file>`` for multi-chapter albums,
        or the legacy flat ``pages/<file>`` layout for single-chapter albums."""
        base = self.pages_dir(meta.source, meta.source_id)
        if page.chapter:
            return base / self._safe(page.chapter) / page.file
        return base / page.file

    def _chapter_thumb_path(self, meta: ComicMeta, page: PageRecord) -> Path:
        base = self.thumbs_dir(meta.source, meta.source_id)
        if page.chapter:
            return base / self._safe(page.chapter) / f"{page.index:05d}.jpg"
        return base / f"{page.index:05d}.jpg"

    def cover_path(self, meta: ComicMeta, index: int) -> Path:
        return self.covers_dir(meta.source, meta.source_id) / f"{index:03d}.jpg"

    def thumbs_dir(self, source: str, source_id: str) -> Path:
        return self.comic_dir(source, source_id) / "thumbs"

    def page_thumb_path(self, meta: ComicMeta, index: int) -> Path:
        page = next((p for p in meta.pages if p.index == index), None)
        if page is None:
            raise KeyError(f"页 {index} 不存在（共 {meta.page_count} 页）")
        return self._chapter_thumb_path(meta, page)

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

    # ------------------------------------------------------------------
    # persistence
    # ------------------------------------------------------------------
    def _migrate_flat_to_chapter(self, meta: ComicMeta, first_chapter_id: str) -> None:
        """Migrate flat pages/ and thumbs/ files to pages/<first_chapter_id>/
        when a previously single-chapter comic is updated to multi-chapter."""
        safe_chap = self._safe(first_chapter_id)

        pages_dir = self.pages_dir(meta.source, meta.source_id)
        if pages_dir.exists():
            target_dir = pages_dir / safe_chap
            target_dir.mkdir(parents=True, exist_ok=True)
            for item in list(pages_dir.iterdir()):
                if item.is_file():
                    dest = target_dir / item.name
                    if not dest.exists():
                        item.rename(dest)

        thumbs_dir = self.thumbs_dir(meta.source, meta.source_id)
        if thumbs_dir.exists():
            target_thumb_dir = thumbs_dir / safe_chap
            target_thumb_dir.mkdir(parents=True, exist_ok=True)
            for item in list(thumbs_dir.iterdir()):
                if item.is_file():
                    dest = target_thumb_dir / item.name
                    if not dest.exists():
                        item.rename(dest)

    def save_fetched(self, fetched: FetchedComic, refresh: bool = False) -> ComicMeta:
        meta = fetched.meta

        existing_bundle = self.load_fetched(meta.source, meta.source_id)
        existing = existing_bundle.meta if existing_bundle is not None else None

        if refresh and existing is not None:
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
    # legacy cache migration: raw scrambled JM images -> decoded images
    # ------------------------------------------------------------------
    def _migrate_decode_v2(
        self,
        meta: ComicMeta,
        pages: list[RemotePage],
        remote_path: Path,
        data: dict,
    ) -> None:
        """Decode already-cached v1 page files without touching the network.

        The v1 provider saved raw images. ``JmImageTool.decode_and_save`` is the
        same routine ``JmDownloader`` uses, so we can recover correct pages from
        the existing local files instead of re-downloading them.
        """
        from jmcomic import JmImageTool

        # Another process/request may have finished this migration between our
        # version check and taking the lock.
        if remote_path.exists():
            try:
                latest = json.loads(remote_path.read_text(encoding="utf-8"))
                if int(latest.get("decode_version", 1) or 1) >= CURRENT_DECODE_VERSION:
                    return
                decode_state = latest.get("decode_state") or {}
                data = latest
            except Exception:
                decode_state = data.get("decode_state") or {}
        else:
            decode_state = data.get("decode_state") or {}

        decoded: set[int] = {
            int(index) for index in decode_state.get("decoded", [])
        }

        pages_dir = self.pages_dir(meta.source, meta.source_id)
        for page in pages:
            if page.chapter:
                target = pages_dir / self._safe(page.chapter) / page.file
            else:
                target = pages_dir / page.file
            if not target.exists() or page.index in decoded:
                continue
            if not page.scramble_id:
                continue

            url = page.url.split("?", 1)[0]
            num = JmImageTool.get_num_by_url(page.scramble_id, url)
            if num != 0:
                # Write the decoded image on the same filesystem as the
                # cache so the final os.replace() is atomic.
                target.parent.mkdir(parents=True, exist_ok=True)
                fd, tmp_name = tempfile.mkstemp(
                    prefix=f".{target.name}.decode.",
                    suffix=page.ext or ".webp",
                    dir=str(target.parent),
                )
                os.close(fd)
                tmp_path = Path(tmp_name)
                try:
                    source = JmImageTool.open_image(str(target))
                    try:
                        JmImageTool.decode_and_save(num, source, str(tmp_path))
                    finally:
                        source.close()
                    os.replace(tmp_path, target)
                finally:
                    tmp_path.unlink(missing_ok=True)

            decoded.add(page.index)
            data["decode_state"] = {"decoded": sorted(decoded)}
            _write_json_atomic(remote_path, data)

        # Old covers were generated from scrambled pages; rebuild them lazily.
        covers_dir = self.covers_dir(meta.source, meta.source_id)
        if covers_dir.exists():
            shutil.rmtree(covers_dir)

        data["decode_version"] = CURRENT_DECODE_VERSION
        data.pop("decode_state", None)
        _write_json_atomic(remote_path, data)
        self._invalidate_cache(meta.source, meta.source_id)

    def update_page_cached(self, meta: ComicMeta, index: int, cached: bool) -> None:
        for page in meta.pages:
            if page.index == index:
                page.cached = cached
                break
        album_path = self.album_path(meta.source, meta.source_id)
        _write_json_atomic(album_path, meta.model_dump())
        try:
            mtime = album_path.stat().st_mtime
        except Exception:
            mtime = 0.0
        with self._cache_guard:
            self._meta_cache[(meta.source, meta.source_id)] = (mtime, meta)
            self._fetched_cache.pop((meta.source, meta.source_id), None)

    # ------------------------------------------------------------------
    # pages and covers
    # ------------------------------------------------------------------
    def ensure_page(self, fetched: FetchedComic, index: int) -> Path:
        meta = fetched.meta
        target = self.page_path(meta, index)
        if target.exists():
            page = next((p for p in meta.pages if p.index == index), None)
            if page is not None and not page.cached:
                self.update_page_cached(meta, index, True)
            return target

        page = next((p for p in fetched.remote_pages if p.index == index), None)
        if page is None:
            raise KeyError(f"页 {index} 不存在（共 {meta.page_count} 页）")

        with self._lock_for_page(meta.source, meta.source_id, index):
            if target.exists():
                return target

            from .providers.registry import get_provider

            provider = get_provider(meta.source)
            data = provider.download_page(fetched, page)

            TMP_DIR.mkdir(parents=True, exist_ok=True)
            tmp_path = TMP_DIR / f"{meta.source}_{meta.source_id}_{index:05d}.part"
            try:
                tmp_path.write_bytes(data)
                target.parent.mkdir(parents=True, exist_ok=True)
                os.replace(tmp_path, target)
            finally:
                tmp_path.unlink(missing_ok=True)

            self.update_page_cached(meta, index, True)
            return target

    def cached_page_count(self, meta: ComicMeta) -> int:
        return sum(1 for page in meta.pages if page.cached)

    @staticmethod
    def _save_cover(page_path: Path, target: Path) -> None:
        """Resize one finished page into a JPEG cover/thumbnail file."""
        from PIL import Image, ImageOps

        with Image.open(page_path) as img:
            img = ImageOps.exif_transpose(img)
            if getattr(img, "is_animated", False):
                img.seek(0)
            if img.mode not in {"RGB", "L"}:
                img = img.convert("RGB")
            ratio = COVER_WIDTH / max(img.width, 1)
            if ratio < 1:
                size = (COVER_WIDTH, max(1, round(img.height * ratio)))
                img = img.resize(size, Image.Resampling.LANCZOS)
            target.parent.mkdir(parents=True, exist_ok=True)
            img.save(target, format="JPEG", quality=COVER_QUALITY, optimize=True, progressive=True)

    def ensure_cover(self, meta: ComicMeta, fetched: FetchedComic, index: int) -> Path:
        target = self.cover_path(meta, index)
        if target.exists() and target.stat().st_size > 0:
            return target

        with self._lock_for_page(meta.source, meta.source_id, index):
            if target.exists() and target.stat().st_size > 0:
                return target

            if meta.cover_indices and 1 <= index <= len(meta.cover_indices):
                page_index = meta.cover_indices[index - 1]
            else:
                page_index = index
            page_index = max(1, min(page_index, meta.page_count or 1))

            page_path = self.ensure_page(fetched, page_index)
            self._save_cover(page_path, target)
            return target

    def chapter_covers_dir(self, source: str, source_id: str) -> Path:
        return self.covers_dir(source, source_id) / "chapters"

    def chapter_cover_path(self, meta: ComicMeta, chapter: Chapter) -> Path:
        return self.chapter_covers_dir(meta.source, meta.source_id) / f"{self._safe(chapter.id)}.jpg"

    def ensure_chapter_cover(self, meta: ComicMeta, fetched: FetchedComic, chapter: Chapter) -> Path:
        """JPEG cover for a chapter = its first page, pooled under covers/chapters/.

        T17（章节目录封面池化）：目录不再走每话第一页的 thumbnail（那也要下载整页 +
        生成 360px 缩略图），改用章节封面端点一次生成并缓存，失败由前端回落书脊占位。
        """
        target = self.chapter_cover_path(meta, chapter)
        if target.exists() and target.stat().st_size > 0:
            return target

        with self._lock_for_page(meta.source, meta.source_id, chapter.start):
            if target.exists() and target.stat().st_size > 0:
                return target

            page_path = self.ensure_page(fetched, chapter.start)
            self._save_cover(page_path, target)
            return target

    def ensure_page_thumb(self, meta: ComicMeta, fetched: FetchedComic, index: int) -> Path:
        """Small JPEG thumbnail used by the detail-page index grid."""
        target = self.page_thumb_path(meta, index)
        if target.exists() and target.stat().st_size > 0:
            return target

        with self._lock_for_page(meta.source, meta.source_id, index):
            if target.exists() and target.stat().st_size > 0:
                return target

            with self._thumb_semaphore:
                if target.exists() and target.stat().st_size > 0:
                    return target

                page_path = self.ensure_page(fetched, index)
                from PIL import Image, ImageOps

                with Image.open(page_path) as img:
                    img = ImageOps.exif_transpose(img)
                    if getattr(img, "is_animated", False):
                        img.seek(0)
                    if img.mode not in {"RGB", "L"}:
                        img = img.convert("RGB")
                    ratio = PAGE_THUMB_WIDTH / max(img.width, 1)
                    if ratio < 1:
                        size = (PAGE_THUMB_WIDTH, max(1, round(img.height * ratio)))
                        img = img.resize(size, Image.Resampling.LANCZOS)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    img.save(
                        target,
                        format="JPEG",
                        quality=PAGE_THUMB_QUALITY,
                        optimize=True,
                        progressive=True,
                    )

                return target

    def prefetch(
        self,
        fetched: FetchedComic,
        *,
        cover_count: int,
        prefetch_all: bool,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> tuple[int, list[str]]:
        """Download cover pages eagerly; optionally cache the whole book."""
        meta = fetched.meta
        warnings: list[str] = []
        done = 0

        cover_count = max(0, min(cover_count, meta.page_count or 0))
        if cover_count == 0 and meta.page_count > 0:
            cover_count = min(4, meta.page_count)

        indexes: Iterable[int]
        if prefetch_all:
            indexes = list(range(1, min(meta.page_count, MAX_PREFETCH) + 1))
            if meta.page_count > MAX_PREFETCH:
                warnings.append(
                    f"单次预缓存上限为 {MAX_PREFETCH} 页，剩余页面将在阅读时自动缓存"
                )
        else:
            indexes = list(range(1, cover_count + 1))

        total = len(indexes)
        for index in indexes:
            try:
                self.ensure_page(fetched, index)
                if index <= min(meta.cover_count, meta.page_count):
                    self.ensure_cover(fetched.meta, fetched, index)
                # T-Optimize: Pre-generate thumbnail during prefetch for warm detail-page hits
                self.ensure_page_thumb(fetched.meta, fetched, index)
                done += 1
            except Exception as exc:  # keep import usable even if one page fails
                warnings.append(f"第 {index} 页缓存失败：{exc}")
                if index == 1:
                    raise
            finally:
                if on_progress is not None:
                    on_progress(done, total)

        return done, warnings

    # ------------------------------------------------------------------
    # library queries
    # ------------------------------------------------------------------
    def list_library(self) -> list[LibrarySummary]:
        items: list[LibrarySummary] = []
        if not self.root.exists():
            return items

        for source_dir in sorted(self.root.iterdir()):
            if not source_dir.is_dir():
                continue
            for comic_dir in sorted(source_dir.iterdir()):
                if not comic_dir.is_dir():
                    continue
                fetched = self.load_fetched(source_dir.name, comic_dir.name)
                if fetched is None:
                    continue
                items.append(self.summary(fetched.meta))
        return items

    def summary(self, meta: ComicMeta) -> LibrarySummary:
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
            cached_pages=self.cached_page_count(meta),
            cover_count=meta.cover_count,
            chapter_titles=[c.title for c in meta.chapters],
        )

    def detail(self, meta: ComicMeta) -> ComicDetail:
        cached = self.cached_page_count(meta)
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

    # ------------------------------------------------------------------
    # metadata & local comic operations
    # ------------------------------------------------------------------
    @staticmethod
    def _natural_key(s: str) -> list[int | str]:
        return [int(text) if text.isdigit() else text.lower() for text in re.split(r"(\d+)", s)]

    def update_metadata(self, source: str, source_id: str, updates: dict[str, Any]) -> ComicMeta:
        meta = self.load_meta(source, source_id)
        if meta is None:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="漫画不存在")

        import datetime

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
                    if f.is_file() and f.suffix.lower() in {".jpg", ".jpeg"}:
                        f.unlink(missing_ok=True)
            # Regenerate covers
            fetched = self.load_fetched(source, source_id)
            if fetched is not None:
                for idx in range(1, len(meta.cover_paths()) + 1):
                    try:
                        self.ensure_cover(meta, fetched, idx)
                    except Exception:
                        pass

        _write_json_atomic(self.album_path(source, source_id), meta.model_dump())
        self._invalidate_cache(source, source_id)
        return meta

    def create_local_comic(self, req: Any) -> ComicMeta:
        from .providers.local import LocalProvider
        import datetime

        provider = LocalProvider()
        source_id = provider.normalize_id(req.id) if req.id else f"loc_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"

        comic_dir = self.comic_dir("local", source_id)
        comic_dir.mkdir(parents=True, exist_ok=True)
        self.pages_dir("local", source_id).mkdir(parents=True, exist_ok=True)

        chapters: list[Chapter] = []
        if getattr(req, "chapters", None):
            for idx, c in enumerate(req.chapters, start=1):
                cid = provider.normalize_id(c.id) if getattr(c, "id", "") else f"c{idx}"
                title = getattr(c, "title", "") or f"第 {idx} 话"
                chapters.append(Chapter(id=cid, index=idx, title=title, page_count=0, start=1))

        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        meta = ComicMeta(
            source="local",
            source_id=source_id,
            display_id=f"LOC_{source_id}",
            title=req.title,
            authors=req.authors or ["自制"],
            works=req.works or [],
            actors=req.actors or [],
            tags=req.tags or [],
            description=req.description or "",
            uploader=req.uploader or "自制",
            page_count=0,
            cover_count=4,
            cover_indices=getattr(req, "cover_indices", []) or [],
            published_at=now_str,
            updated_at=now_str,
            imported_at=now_str,
            chapters=chapters,
            hidden_from_guest=getattr(req, "hidden_from_guest", False),
        )

        _write_json_atomic(self.album_path("local", source_id), meta.model_dump())
        _write_json_atomic(
            self.remote_path("local", source_id),
            {"decode_version": CURRENT_DECODE_VERSION, "remote_pages": []},
        )
        self._invalidate_cache("local", source_id)
        return meta

    def import_local_path(self, req: Any) -> ComicMeta:
        IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif", ".bmp"}
        raw_path = Path(req.path).expanduser()
        if not raw_path.is_absolute():
            # Check relative to project root or cwd
            proj_root = Path(__file__).resolve().parents[2]
            cand1 = proj_root / raw_path
            cand2 = Path.cwd() / raw_path
            raw_path = cand1 if cand1.exists() else cand2

        if not raw_path.exists() or not raw_path.is_dir():
            raise HTTPException(status_code=400, detail=f"指定目录不存在或不是文件夹：{req.path}")

        if not _is_path_allowed(raw_path):
            raise HTTPException(
                status_code=400,
                detail=f"出于安全考虑，禁止从指定目录导入（{raw_path}）。如需导入，请配置 COMIC_SHELF_ALLOWED_DIRS 环境变量。",
            )

        provider = LocalProvider()
        source_id = provider.normalize_id(req.id) if req.id else provider.normalize_id(raw_path.name)
        if not source_id:
            source_id = f"loc_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Detect subdirectories with images
        subdirs = [d for d in raw_path.iterdir() if d.is_dir() and not d.name.startswith(".")]
        subdirs.sort(key=lambda d: self._natural_key(d.name))

        multi_chap_dirs: list[tuple[str, str, list[Path]]] = []
        for d in subdirs:
            imgs = [f for f in d.iterdir() if f.is_file() and f.suffix.lower() in IMAGE_EXTS]
            if imgs:
                imgs.sort(key=lambda f: self._natural_key(f.name))
                multi_chap_dirs.append((provider.normalize_id(d.name), d.name, imgs))

        target_pages_dir = self.pages_dir("local", source_id)
        target_pages_dir.mkdir(parents=True, exist_ok=True)

        pages: list[PageRecord] = []
        remote_pages: list[RemotePage] = []
        chapters: list[Chapter] = []

        global_idx = 1
        if multi_chap_dirs:
            # Multi-chapter layout
            for chap_idx, (chap_id, chap_title, img_files) in enumerate(multi_chap_dirs, start=1):
                chap_pages_dir = target_pages_dir / self._safe(chap_id)
                chap_pages_dir.mkdir(parents=True, exist_ok=True)
                start_page = global_idx
                chap_page_count = len(img_files)

                for local_i, img_file in enumerate(img_files, start=1):
                    ext = img_file.suffix.lower()
                    dest_name = f"{local_i:05d}{ext}"
                    dest_path = chap_pages_dir / dest_name
                    shutil.copy2(img_file, dest_path)

                    pages.append(PageRecord(index=global_idx, file=dest_name, ext=ext, cached=True, chapter=chap_id))
                    remote_pages.append(RemotePage(index=global_idx, url="", file=dest_name, ext=ext, chapter=chap_id))
                    global_idx += 1

                chapters.append(
                    Chapter(
                        id=chap_id,
                        index=chap_idx,
                        title=chap_title,
                        page_count=chap_page_count,
                        start=start_page,
                    )
                )
        else:
            # Single-chapter flat layout
            img_files = [f for f in raw_path.iterdir() if f.is_file() and f.suffix.lower() in IMAGE_EXTS]
            img_files.sort(key=lambda f: self._natural_key(f.name))
            if not img_files:
                raise HTTPException(status_code=400, detail=f"目录中未找到支持的图片文件（支持 {', '.join(IMAGE_EXTS)}）")

            for local_i, img_file in enumerate(img_files, start=1):
                ext = img_file.suffix.lower()
                dest_name = f"{local_i:05d}{ext}"
                dest_path = target_pages_dir / dest_name
                shutil.copy2(img_file, dest_path)

                pages.append(PageRecord(index=global_idx, file=dest_name, ext=ext, cached=True, chapter=""))
                remote_pages.append(RemotePage(index=global_idx, url="", file=dest_name, ext=ext, chapter=""))
                global_idx += 1

        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        title = req.title.strip() if req.title and req.title.strip() else raw_path.name

        meta = ComicMeta(
            source="local",
            source_id=source_id,
            display_id=f"LOC_{source_id}",
            title=title,
            authors=req.authors or ["自制"],
            works=req.works or [],
            actors=req.actors or [],
            tags=req.tags or [],
            description=req.description or "",
            uploader=req.uploader or "本地导入",
            page_count=len(pages),
            cover_count=4,
            cover_indices=getattr(req, "cover_indices", []) or [],
            published_at=now_str,
            updated_at=now_str,
            imported_at=now_str,
            pages=pages,
            chapters=chapters,
            hidden_from_guest=getattr(req, "hidden_from_guest", False),
        )

        fetched = FetchedComic(meta=meta, remote_pages=remote_pages)
        self.save_fetched(fetched, refresh=False)

        # Generate covers and thumbs for initial pages
        for i in range(1, min(meta.cover_count, meta.page_count) + 1):
            try:
                self.ensure_cover(meta, fetched, i)
            except Exception as e:
                logger.warning("Failed to generate initial cover %d for %s: %s", i, source_id, e)

        if meta.chapters:
            for ch in meta.chapters:
                try:
                    self.ensure_chapter_cover(meta, fetched, ch)
                except Exception as e:
                    logger.warning("Failed to generate chapter cover for %s (%s): %s", source_id, ch.id, e)

        return meta

    def append_pages(
        self,
        source_id: str,
        files: list[tuple[str, bytes]] | None = None,
        server_path: str = "",
        target_chapter: str = "",
        new_chapter_title: str = "",
    ) -> ComicMeta:
        fetched = self.load_fetched("local", source_id)
        if fetched is None:
            raise HTTPException(status_code=404, detail="本地漫画不存在")

        meta = fetched.meta
        provider = LocalProvider()
        IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif", ".bmp"}

        # Collect source image items: list of (ext, bytes or Path)
        items: list[tuple[str, bytes | Path]] = []
        if files:
            sorted_files = sorted(files, key=lambda f: self._natural_key(f[0]))
            for filename, content in sorted_files:
                ext = Path(filename).suffix.lower() or ".webp"
                if ext in IMAGE_EXTS:
                    items.append((ext, content))
        elif server_path:
            raw_path = Path(server_path).expanduser()
            if not raw_path.is_absolute():
                proj_root = Path(__file__).resolve().parents[2]
                cand1 = proj_root / raw_path
                cand2 = Path.cwd() / raw_path
                raw_path = cand1 if cand1.exists() else cand2
            if not raw_path.exists() or not raw_path.is_dir():
                raise HTTPException(status_code=400, detail=f"指定目录不存在：{server_path}")
            if not _is_path_allowed(raw_path):
                raise HTTPException(
                    status_code=400,
                    detail=f"出于安全考虑，禁止从指定目录导入（{raw_path}）。如需导入，请配置 COMIC_SHELF_ALLOWED_DIRS 环境变量。",
                )
            img_files = [f for f in raw_path.iterdir() if f.is_file() and f.suffix.lower() in IMAGE_EXTS]
            img_files.sort(key=lambda f: self._natural_key(f.name))
            for f in img_files:
                items.append((f.suffix.lower(), f))

        if not items:
            raise HTTPException(status_code=400, detail="未提供有效的图片文件")

        target_pages_dir = self.pages_dir("local", source_id)
        target_pages_dir.mkdir(parents=True, exist_ok=True)

        is_new_chapter = bool(new_chapter_title)
        if is_new_chapter:
            # If the comic was previously a single-chapter flat comic, promote existing pages to Chapter 1
            if not meta.chapters and meta.pages:
                first_chap_id = "c1"
                self._migrate_flat_to_chapter(meta, first_chap_id)
                old_count = len(meta.pages)
                for p in meta.pages:
                    p.chapter = first_chap_id
                for rp in fetched.remote_pages:
                    rp.chapter = first_chap_id
                first_chap = Chapter(
                    id=first_chap_id,
                    index=1,
                    title="第 1 话",
                    page_count=old_count,
                    start=1,
                )
                meta.chapters = [first_chap]
                try:
                    self.ensure_chapter_cover(meta, fetched, first_chap)
                except Exception as e:
                    logger.warning("Failed to generate cover for synthesized Chapter 1 %s: %s", source_id, e)

            # Adding a new chapter to the comic
            new_chap_idx = len(meta.chapters) + 1
            new_chap_id = provider.normalize_id(f"c{new_chap_idx}_{datetime.datetime.now().strftime('%M%S')}")
            chap_dir = target_pages_dir / self._safe(new_chap_id)
            chap_dir.mkdir(parents=True, exist_ok=True)

            start_idx = meta.page_count + 1
            for local_i, (ext, data_or_path) in enumerate(items, start=1):
                dest_name = f"{local_i:05d}{ext}"
                dest_path = chap_dir / dest_name
                if isinstance(data_or_path, Path):
                    shutil.copy2(data_or_path, dest_path)
                else:
                    dest_path.write_bytes(data_or_path)

                cur_idx = meta.page_count + local_i
                meta.pages.append(PageRecord(index=cur_idx, file=dest_name, ext=ext, cached=True, chapter=new_chap_id))
                fetched.remote_pages.append(RemotePage(index=cur_idx, url="", file=dest_name, ext=ext, chapter=new_chap_id))

            meta.page_count += len(items)
            new_chap = Chapter(
                id=new_chap_id,
                index=new_chap_idx,
                title=new_chapter_title.strip() or f"第 {new_chap_idx} 话",
                page_count=len(items),
                start=start_idx,
            )
            meta.chapters.append(new_chap)
            try:
                self.ensure_chapter_cover(meta, fetched, new_chap)
            except Exception as e:
                logger.warning("Failed to generate cover for new chapter %s: %s", new_chap_id, e)
        else:
            # Appending to existing single chapter or target chapter
            chap_id = target_chapter or (meta.chapters[0].id if meta.chapters else "")
            chap_dir = (target_pages_dir / self._safe(chap_id)) if chap_id else target_pages_dir
            chap_dir.mkdir(parents=True, exist_ok=True)

            existing_in_chap = [p for p in meta.pages if p.chapter == chap_id]
            offset = len(existing_in_chap)

            new_chap_pages: list[tuple[str, str]] = []
            for local_i, (ext, data_or_path) in enumerate(items, start=1):
                dest_name = f"{offset + local_i:05d}{ext}"
                dest_path = chap_dir / dest_name
                if isinstance(data_or_path, Path):
                    shutil.copy2(data_or_path, dest_path)
                else:
                    dest_path.write_bytes(data_or_path)
                new_chap_pages.append((dest_name, ext))

            if not meta.chapters:
                # Single-chapter flat comic
                for local_i, (dest_name, ext) in enumerate(new_chap_pages, start=1):
                    cur_idx = offset + local_i
                    meta.pages.append(PageRecord(index=cur_idx, file=dest_name, ext=ext, cached=True, chapter=""))
                    fetched.remote_pages.append(RemotePage(index=cur_idx, url="", file=dest_name, ext=ext, chapter=""))
                meta.page_count = len(meta.pages)
            else:
                # Multi-chapter comic: Re-index all pages and chapters monotonically
                chap_page_map: dict[str, list[PageRecord]] = {}
                for ch in meta.chapters:
                    chap_page_map[ch.id] = [p for p in meta.pages if p.chapter == ch.id]

                if chap_id not in chap_page_map:
                    chap_page_map[chap_id] = []

                for dest_name, ext in new_chap_pages:
                    chap_page_map[chap_id].append(
                        PageRecord(index=0, file=dest_name, ext=ext, cached=True, chapter=chap_id)
                    )

                rebuilt_pages: list[PageRecord] = []
                rebuilt_remote: list[RemotePage] = []
                global_idx = 1
                for ch in meta.chapters:
                    ch.start = global_idx
                    ch_pages = chap_page_map.get(ch.id, [])
                    ch.page_count = len(ch_pages)
                    for p in ch_pages:
                        p.index = global_idx
                        rebuilt_pages.append(p)
                        rebuilt_remote.append(
                            RemotePage(index=global_idx, url="", file=p.file, ext=p.ext, chapter=ch.id)
                        )
                        global_idx += 1

                meta.pages = rebuilt_pages
                fetched.remote_pages = rebuilt_remote
                meta.page_count = len(meta.pages)

        meta.updated_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.save_fetched(fetched, refresh=True)
        return meta

    def replace_pages(
        self,
        source: str,
        source_id: str,
        files: list[tuple[str, bytes]] | None = None,
        server_path: str = "",
        target_chapter: str = "",
    ) -> ComicMeta:
        with self._lock_for(source, source_id):
            fetched = self.load_fetched(source, source_id)
            if fetched is None:
                raise HTTPException(status_code=404, detail="漫画不存在")

            meta = fetched.meta
            IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif", ".bmp"}

            valid_items: list[tuple[str, bytes]] = []
            if files:
                sorted_files = sorted(files, key=lambda f: self._natural_key(f[0]))
                for filename, content in sorted_files:
                    ext = Path(filename).suffix.lower()
                    if ext in IMAGE_EXTS and content:
                        valid_items.append((ext, content))
            elif server_path:
                raw_path = Path(server_path).expanduser()
                if not raw_path.is_absolute():
                    proj_root = Path(__file__).resolve().parents[2]
                    cand1 = proj_root / raw_path
                    cand2 = Path.cwd() / raw_path
                    raw_path = cand1 if cand1.exists() else cand2
                if not raw_path.exists():
                    raise HTTPException(status_code=400, detail=f"指定路径不存在：{server_path}")
                if not _is_path_allowed(raw_path):
                    raise HTTPException(
                        status_code=400,
                        detail=f"出于安全考虑，禁止从指定目录导入（{raw_path}）。如需导入，请配置 COMIC_SHELF_ALLOWED_DIRS 环境变量。",
                    )
                if raw_path.is_dir():
                    img_files = [
                        f
                        for f in raw_path.iterdir()
                        if f.is_file() and f.suffix.lower() in IMAGE_EXTS and _is_path_allowed(f.resolve())
                    ]
                elif raw_path.is_file() and raw_path.suffix.lower() in IMAGE_EXTS and _is_path_allowed(raw_path.resolve()):
                    img_files = [raw_path]
                else:
                    raise HTTPException(status_code=400, detail=f"指定路径不是有效的图片文件或目录：{server_path}")

                img_files.sort(key=lambda f: self._natural_key(f.name))
                for f in img_files:
                    valid_items.append((f.suffix.lower(), f.read_bytes()))

            if not valid_items:
                raise HTTPException(status_code=400, detail="未提供有效的图片文件")

            # 暂存与严格 PIL 合法性校验（原子性保证）
            comic_dir = self.pages_dir(source, source_id).parent
            staging_dir = comic_dir / ".tmp_replace"
            if staging_dir.exists():
                shutil.rmtree(staging_dir, ignore_errors=True)
            staging_dir.mkdir(parents=True, exist_ok=True)

            from PIL import Image
            import io

            staged_names: list[tuple[str, str]] = []
            try:
                for idx, (ext, content) in enumerate(valid_items, start=1):
                    try:
                        img = Image.open(io.BytesIO(content))
                        img.verify()
                    except Exception as exc:
                        raise HTTPException(
                            status_code=400,
                            detail=f"上传的文件损坏或不是有效图片 (第 {idx} 张): {exc}",
                        )
                    dest_name = f"{idx:05d}{ext}"
                    dest_path = staging_dir / dest_name
                    dest_path.write_bytes(content)
                    staged_names.append((dest_name, ext))
            except Exception:
                shutil.rmtree(staging_dir, ignore_errors=True)
                raise

            target_pages_dir = self.pages_dir(source, source_id)
            target_pages_dir.mkdir(parents=True, exist_ok=True)

            if target_chapter and meta.chapters:
                target_ch = next((c for c in meta.chapters if c.id == target_chapter), None)
                if not target_ch:
                    shutil.rmtree(staging_dir, ignore_errors=True)
                    raise HTTPException(status_code=404, detail=f"章节 {target_chapter} 不存在")

                chap_dir = target_pages_dir / self._safe(target_chapter)
                backup_chap_dir = target_pages_dir / f".tmp_chap_old_{self._safe(target_chapter)}"
                if backup_chap_dir.exists():
                    shutil.rmtree(backup_chap_dir, ignore_errors=True)

                if chap_dir.exists():
                    chap_dir.rename(backup_chap_dir)

                try:
                    staging_dir.rename(chap_dir)
                    shutil.rmtree(backup_chap_dir, ignore_errors=True)
                except Exception:
                    if backup_chap_dir.exists() and not chap_dir.exists():
                        backup_chap_dir.rename(chap_dir)
                    shutil.rmtree(staging_dir, ignore_errors=True)
                    raise

                chap_page_map: dict[str, list[PageRecord]] = {}
                for ch in meta.chapters:
                    if ch.id == target_chapter:
                        chap_page_map[ch.id] = [
                            PageRecord(index=0, file=dest_name, ext=ext, cached=True, chapter=ch.id)
                            for dest_name, ext in staged_names
                        ]
                    else:
                        chap_page_map[ch.id] = [p for p in meta.pages if p.chapter == ch.id]

                rebuilt_pages: list[PageRecord] = []
                rebuilt_remote: list[RemotePage] = []
                global_idx = 1
                for ch in meta.chapters:
                    ch.start = global_idx
                    ch_pages = chap_page_map.get(ch.id, [])
                    ch.page_count = len(ch_pages)
                    for p in ch_pages:
                        p.index = global_idx
                        rebuilt_pages.append(p)
                        rebuilt_remote.append(
                            RemotePage(index=global_idx, url="", file=p.file, ext=p.ext, chapter=ch.id)
                        )
                        global_idx += 1

                meta.pages = rebuilt_pages
                fetched.remote_pages = rebuilt_remote
                meta.page_count = len(meta.pages)
                try:
                    self.ensure_chapter_cover(meta, fetched, target_ch)
                except Exception as e:
                    logger.warning("Failed to regenerate cover for chapter %s: %s", target_chapter, e)
            else:
                backup_pages_dir = comic_dir / ".pages_old"
                if backup_pages_dir.exists():
                    shutil.rmtree(backup_pages_dir, ignore_errors=True)

                if target_pages_dir.exists():
                    target_pages_dir.rename(backup_pages_dir)

                try:
                    staging_dir.rename(target_pages_dir)
                    shutil.rmtree(backup_pages_dir, ignore_errors=True)
                except Exception:
                    if backup_pages_dir.exists() and not target_pages_dir.exists():
                        backup_pages_dir.rename(target_pages_dir)
                    shutil.rmtree(staging_dir, ignore_errors=True)
                    raise

                new_pages = [
                    PageRecord(index=i, file=dest_name, ext=ext, cached=True, chapter="")
                    for i, (dest_name, ext) in enumerate(staged_names, start=1)
                ]
                new_remote = [
                    RemotePage(index=i, url="", file=dest_name, ext=ext, chapter="")
                    for i, (dest_name, ext) in enumerate(staged_names, start=1)
                ]
                meta.pages = new_pages
                fetched.remote_pages = new_remote
                meta.page_count = len(new_pages)
                meta.chapters = []

            meta.custom_pages = True
            meta.cover_count = min(4, meta.page_count)
            meta.cover_indices = []

            thumbs_dir = self.thumbs_dir(source, source_id)
            covers_dir = self.covers_dir(source, source_id)
            shutil.rmtree(thumbs_dir, ignore_errors=True)
            shutil.rmtree(covers_dir, ignore_errors=True)
            thumbs_dir.mkdir(parents=True, exist_ok=True)
            covers_dir.mkdir(parents=True, exist_ok=True)

            for i in range(1, min(5, meta.page_count + 1)):
                try:
                    self.ensure_cover(meta, fetched, i)
                except Exception as e:
                    logger.warning("Failed to regenerate cover %d for %s/%s: %s", i, source, source_id, e)

            meta.updated_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.save_fetched(fetched, refresh=True)
            return meta

    def update_chapter_title(self, source: str, source_id: str, chapter_id: str, new_title: str) -> ComicMeta:
        meta = self.load_meta(source, source_id)
        if meta is None:
            raise HTTPException(status_code=404, detail="本子还没有导入本地书库")

        chapter = next((c for c in meta.chapters if c.id == chapter_id), None)
        if chapter is None:
            raise HTTPException(status_code=404, detail=f"未找到章节：{chapter_id}")

        chapter.title = new_title.strip() or f"第 {chapter.index} 话"
        meta.updated_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        _write_json_atomic(self.album_path(source, source_id), meta.model_dump())
        self._invalidate_cache(source, source_id)
        return meta

    def delete_chapter(self, source: str, source_id: str, chapter_id: str) -> ComicMeta:
        fetched = self.load_fetched(source, source_id)
        if fetched is None:
            raise HTTPException(status_code=404, detail="本子还没有导入本地书库")

        meta = fetched.meta
        chapter = next((c for c in meta.chapters if c.id == chapter_id), None)
        if chapter is None:
            raise HTTPException(status_code=404, detail=f"未找到章节：{chapter_id}")

        # Delete physical directory and covers for this chapter
        safe_cid = self._safe(chapter_id)
        chap_dir = self.pages_dir(source, source_id) / safe_cid
        if chap_dir.exists():
            shutil.rmtree(chap_dir, ignore_errors=True)

        thumb_dir = self.thumbs_dir(source, source_id) / safe_cid
        if thumb_dir.exists():
            shutil.rmtree(thumb_dir, ignore_errors=True)

        chap_cover = self.chapter_cover_path(meta, chapter)
        chap_cover.unlink(missing_ok=True)

        # Remove pages belonging to this chapter
        meta.pages = [p for p in meta.pages if p.chapter != chapter_id]
        fetched.remote_pages = [rp for rp in fetched.remote_pages if rp.chapter != chapter_id]
        meta.chapters = [c for c in meta.chapters if c.id != chapter_id]

        # Re-index all remaining pages and chapters monotonically
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

        # If no chapters left but pages exist
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
        meta.updated_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        _write_json_atomic(self.album_path(source, source_id), meta.model_dump())
        remote_data = {
            "decode_version": CURRENT_DECODE_VERSION,
            "remote_pages": [rp.model_dump() for rp in fetched.remote_pages],
        }
        _write_json_atomic(self.remote_path(source, source_id), remote_data)
        self._invalidate_cache(source, source_id)
        return meta

    # ------------------------------------------------------------------
    # discovery feeds & rankings cache
    # ------------------------------------------------------------------
    def discovery_dir(self) -> Path:
        p = DATA_DIR / "discovery"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def discovery_path(self, timeframe: str) -> Path:
        return self.discovery_dir() / f"{self._safe(timeframe)}.json"

    def load_discovery_feed(self, timeframe: str) -> DiscoveryFeed | None:
        path = self.discovery_path(timeframe)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return DiscoveryFeed.model_validate(data)
        except Exception:
            return None

    def save_discovery_feed(self, feed: DiscoveryFeed) -> None:
        path = self.discovery_path(feed.timeframe)
        _write_json_atomic(path, feed.model_dump())


