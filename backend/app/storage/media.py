"""Media mixin handling image downloading, decoding migration, Pillow WebP/JPEG scaling, covers, and thumbnails."""
from __future__ import annotations

import io
import json
import logging
import os
import shutil
import tempfile
import threading
from pathlib import Path
from typing import Any, BinaryIO, Callable

from fastapi import HTTPException
from PIL import Image, ImageOps

from ..config import (
    COVER_QUALITY,
    COVER_THUMB_WIDTH,
    COVER_WEBP_QUALITY,
    COVER_WIDTH,
    PAGE_THUMB_QUALITY,
    PAGE_THUMB_WIDTH,
    TMP_DIR,
)
from ..models import Chapter, ComicMeta, FetchedComic, RemotePage
from .utils import CURRENT_DECODE_VERSION, _write_json_atomic

logger = logging.getLogger(__name__)


class ComicStoreMediaMixin:
    """Provides Pillow image processing, WebP transcoding, and on-demand page/cover fetching."""

    def _migrate_decode_v2(
        self: Any,
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

        covers_dir = self.covers_dir(meta.source, meta.source_id)
        if covers_dir.exists():
            shutil.rmtree(covers_dir)

        data["decode_version"] = CURRENT_DECODE_VERSION
        data.pop("decode_state", None)
        _write_json_atomic(remote_path, data)
        self._invalidate_cache(meta.source, meta.source_id)

    def update_page_cached(self: Any, meta: ComicMeta, index: int, cached: bool) -> None:
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
        try:
            from ..db import update_comic_cached_pages
            update_comic_cached_pages(meta.source, meta.source_id, self.cached_page_count(meta))
        except Exception:
            pass

    def ensure_page(self: Any, fetched: FetchedComic, index: int) -> Path:
        """Guarantees that a page exists on disk, downloading and decoding it on-demand if missing."""
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

            if not page.url:
                raise FileNotFoundError(f"本地页面文件不存在：{target}")

            from ..providers.registry import get_provider

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

    def cached_page_count(self: Any, meta: ComicMeta) -> int:
        return sum(1 for page in meta.pages if page.cached)

    def reconcile_cached_pages(self: Any, meta: ComicMeta) -> int:
        """Self-heal page.cached against disk files for any un-marked pages via batch directory scanning."""
        if not meta.pages or self.cached_page_count(meta) >= meta.page_count:
            return self.cached_page_count(meta)

        pages_base = self.pages_dir(meta.source, meta.source_id)
        if not pages_base.exists():
            return self.cached_page_count(meta)

        existing_by_dir: dict[Path, set[str]] = {}
        changed = False

        for page in meta.pages:
            if page.cached:
                continue
            parent_dir = pages_base / self._safe(page.chapter) if page.chapter else pages_base
            if parent_dir not in existing_by_dir:
                try:
                    if parent_dir.is_dir():
                        existing_by_dir[parent_dir] = {
                            entry.name
                            for entry in os.scandir(parent_dir)
                            if entry.is_file() and entry.stat().st_size > 0
                        }
                    else:
                        existing_by_dir[parent_dir] = set()
                except OSError:
                    existing_by_dir[parent_dir] = set()

            if page.file in existing_by_dir[parent_dir]:
                page.cached = True
                changed = True

        if changed:
            album_path = self.album_path(meta.source, meta.source_id)
            with self._cache_guard:
                _write_json_atomic(album_path, meta.model_dump())
                try:
                    mtime = album_path.stat().st_mtime
                except Exception:
                    mtime = 0.0
                self._meta_cache[(meta.source, meta.source_id)] = (mtime, meta)
                self._fetched_cache.pop((meta.source, meta.source_id), None)
            try:
                from ..db import update_comic_cached_pages
                update_comic_cached_pages(meta.source, meta.source_id, self.cached_page_count(meta))
            except Exception:
                pass
        return self.cached_page_count(meta)

    @staticmethod
    def _save_cover(
        source: Path | bytes | BinaryIO,
        target: Path,
        target_width: int | None = COVER_WIDTH,
        fmt: str = "JPEG",
        quality: int | None = None,
    ) -> None:
        """Resize one finished page or raw image bytes into a JPEG or WEBP cover/thumbnail file."""
        fmt_upper = fmt.upper()
        if fmt_upper in ("WEBP", "IMAGE/WEBP") or target.suffix.lower() == ".webp":
            save_quality = quality or COVER_WEBP_QUALITY
            save_kwargs = {"format": "WEBP", "quality": save_quality, "method": 4}
            tmp_suffix = f".tmp.{os.getpid()}.{threading.get_ident()}.webp"
        else:
            save_quality = quality or COVER_QUALITY
            save_kwargs = {"format": "JPEG", "quality": save_quality, "optimize": True, "progressive": True}
            tmp_suffix = f".tmp.{os.getpid()}.{threading.get_ident()}.jpg"

        fp = io.BytesIO(source) if isinstance(source, bytes) else source
        with Image.open(fp) as img:
            img = ImageOps.exif_transpose(img)
            if getattr(img, "is_animated", False):
                img.seek(0)
            if img.mode not in {"RGB", "L"}:
                img = img.convert("RGB")
            if target_width is not None:
                ratio = target_width / max(img.width, 1)
                if ratio < 1:
                    size = (target_width, max(1, round(img.height * ratio)))
                    resample_filter = (
                        Image.Resampling.BILINEAR
                        if target_width <= COVER_THUMB_WIDTH
                        else Image.Resampling.LANCZOS
                    )
                    img = img.resize(size, resample_filter)
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_suffix(tmp_suffix)
            try:
                img.save(tmp, **save_kwargs)
                tmp.replace(target)
            except Exception:
                try:
                    if tmp.exists():
                        tmp.unlink()
                except OSError:
                    pass
                raise

    @staticmethod
    def _resolve_cover_page_index(meta: ComicMeta, index: int) -> int:
        """Map a 1-based cover ordinal to the corresponding 1-based page index using meta.cover_indices."""
        if meta.cover_indices and 1 <= index <= len(meta.cover_indices):
            page_index = meta.cover_indices[index - 1]
        else:
            page_index = index
        return max(1, min(page_index, meta.page_count or 1))

    @classmethod
    def _convert_image_to_webp(cls, source_path: Path, target_webp: Path, quality: int | None = None) -> Path:
        """Fast-path: directly transcode an existing JPEG thumbnail to WEBP without resizing (2~5ms)."""
        if target_webp.exists() and target_webp.stat().st_size > 0:
            return target_webp
        cls._save_cover(source_path, target_webp, target_width=None, fmt="WEBP", quality=quality)
        return target_webp

    def scale_cover(
        self: Any, source_cover: Path, target: Path, target_width: int = COVER_THUMB_WIDTH, fmt: str = "JPEG"
    ) -> Path:
        """Downscale an existing high-res cover to target_width (e.g. 360px)."""
        if target.exists() and target.stat().st_size > 0:
            return target
        self._save_cover(source_cover, target, target_width=target_width, fmt=fmt)
        return target

    def _ensure_cover_variant(
        self: Any,
        meta: ComicMeta,
        fetched: FetchedComic | None,
        page_index: int,
        width: int | None,
        wants_webp: bool,
        get_path: Callable[[str, int | None], Path],
        error_msg: str,
    ) -> Path:
        """Unified 4-tier cover and thumbnail caching pipeline."""
        ext = "webp" if wants_webp else "jpg"
        target = get_path(ext, width)
        if target.exists() and target.stat().st_size > 0:
            return target

        with self._lock_for_page(meta.source, meta.source_id, page_index):
            if target.exists() and target.stat().st_size > 0:
                return target

            if wants_webp:
                target_jpg = get_path("jpg", width)
                if target_jpg.exists() and target_jpg.stat().st_size > 0:
                    res = self._convert_image_to_webp(target_jpg, target)
                    try:
                        target_jpg.unlink(missing_ok=True)
                    except OSError:
                        pass
                    return res

                if width and 0 < width <= COVER_THUMB_WIDTH:
                    base_webp = get_path("webp", None)
                    if base_webp.exists() and base_webp.stat().st_size > 0:
                        return self.scale_cover(base_webp, target, target_width=width, fmt="WEBP")
                    base_jpg = get_path("jpg", None)
                    if base_jpg.exists() and base_jpg.stat().st_size > 0:
                        return self.scale_cover(base_jpg, target, target_width=width, fmt="WEBP")
            else:
                if width and 0 < width <= COVER_THUMB_WIDTH:
                    base_cover = get_path("jpg", None)
                    if not (base_cover.exists() and base_cover.stat().st_size > 0):
                        if fetched is None:
                            raise FileNotFoundError(error_msg)
                        page_path = self.ensure_page(fetched, page_index)
                        self._save_cover(page_path, base_cover)
                    return self.scale_cover(base_cover, target, target_width=width)

            if fetched is None:
                raise FileNotFoundError(error_msg)
            page_path = self.ensure_page(fetched, page_index)
            fmt = "WEBP" if wants_webp else "JPEG"
            target_width = width or COVER_WIDTH
            self._save_cover(page_path, target, target_width=target_width, fmt=fmt)
            return target

    def ensure_cover(
        self: Any, meta: ComicMeta, fetched: FetchedComic | None = None, index: int = 1, width: int | None = None
    ) -> Path:
        """Ensure a JPEG cover exists at either 720px or 360px."""
        page_index = self._resolve_cover_page_index(meta, index)
        return self._ensure_cover_variant(
            meta=meta,
            fetched=fetched,
            page_index=page_index,
            width=width,
            wants_webp=False,
            get_path=lambda ext, w: self.cover_path(meta, index, w, ext=ext),
            error_msg="无法生成封面：本子缓存不完整",
        )

    def ensure_webp_cover(
        self: Any, meta: ComicMeta, fetched: FetchedComic | None = None, index: int = 1, width: int | None = None
    ) -> Path:
        """Ensure a WebP cover/thumbnail exists with fast-path downscaling and caching."""
        page_index = self._resolve_cover_page_index(meta, index)
        return self._ensure_cover_variant(
            meta=meta,
            fetched=fetched,
            page_index=page_index,
            width=width,
            wants_webp=True,
            get_path=lambda ext, w: self.cover_path(meta, index, w, ext=ext),
            error_msg="无法生成封面：本子缓存不完整，且未找到已有封面或缩略图",
        )

    def ensure_chapter_cover(
        self: Any, meta: ComicMeta, fetched: FetchedComic | None = None, chapter: Chapter | None = None, width: int | None = None
    ) -> Path:
        """JPEG cover for a chapter = its first page, pooled under covers/chapters/."""
        if chapter is None:
            raise ValueError("chapter 不能为空")
        return self._ensure_cover_variant(
            meta=meta,
            fetched=fetched,
            page_index=chapter.start,
            width=width,
            wants_webp=False,
            get_path=lambda ext, w: self.chapter_cover_path(meta, chapter, w, ext=ext),
            error_msg="无法生成章节封面：本子缓存不完整",
        )

    def ensure_webp_chapter_cover(
        self: Any, meta: ComicMeta, fetched: FetchedComic | None = None, chapter: Chapter | None = None, width: int | None = None
    ) -> Path:
        """Ensure a WebP chapter cover/thumbnail exists with fast-path downscaling and caching."""
        if chapter is None:
            raise ValueError("chapter 不能为空")
        return self._ensure_cover_variant(
            meta=meta,
            fetched=fetched,
            page_index=chapter.start,
            width=width,
            wants_webp=True,
            get_path=lambda ext, w: self.chapter_cover_path(meta, chapter, w, ext=ext),
            error_msg="无法生成章节封面：本子缓存不完整，且未找到已有封面或缩略图",
        )

    def ensure_page_thumb(
        self: Any,
        meta: ComicMeta,
        fetched: FetchedComic,
        index: int,
        ext: str = "webp",
    ) -> Path:
        """WebP/JPEG thumbnail used by the detail-page index grid with fast-path migration."""
        clean_ext = "webp" if ext.lower().lstrip(".") == "webp" else "jpg"
        target = self.page_thumb_path(meta, index, ext=clean_ext)
        if target.exists() and target.stat().st_size > 0:
            return target

        with self._lock_for_page(meta.source, meta.source_id, index):
            if target.exists() and target.stat().st_size > 0:
                return target

            with self._thumb_semaphore:
                if target.exists() and target.stat().st_size > 0:
                    return target

                if clean_ext == "webp":
                    legacy_jpg = self.page_thumb_path(meta, index, ext="jpg")
                    if legacy_jpg.exists() and legacy_jpg.stat().st_size > 0:
                        try:
                            res = self._convert_image_to_webp(legacy_jpg, target)
                            try:
                                legacy_jpg.unlink(missing_ok=True)
                            except OSError:
                                pass
                            return res
                        except Exception:
                            pass

                page_path = self.ensure_page(fetched, index)
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
                    if clean_ext == "webp":
                        tmp_target = target.with_name(f"{target.name}.tmp.{os.getpid()}.{threading.get_ident()}.webp")
                        try:
                            img.save(
                                tmp_target,
                                format="WEBP",
                                quality=COVER_WEBP_QUALITY,
                                method=4,
                            )
                            os.replace(tmp_target, target)
                            try:
                                legacy_jpg = self.page_thumb_path(meta, index, ext="jpg")
                                legacy_jpg.unlink(missing_ok=True)
                            except OSError:
                                pass
                        finally:
                            tmp_target.unlink(missing_ok=True)
                    else:
                        img.save(
                            target,
                            format="JPEG",
                            quality=PAGE_THUMB_QUALITY,
                            optimize=True,
                            progressive=True,
                        )

                return target
