"""Prefetch mixin managing batch background page preheating and chapter prefetching."""
from __future__ import annotations

import logging
import time
from typing import Any, Callable

from ..config import COVER_THUMB_WIDTH, COVER_WIDTH, MAX_PREFETCH
from ..models import Chapter, FetchedComic

logger = logging.getLogger(__name__)


class ComicStorePrefetchMixin:
    """Provides concurrent batch prefetching for entire comics or isolated chapters."""

    def prefetch(
        self: Any,
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

        indexes: list[int]
        if prefetch_all:
            self.reconcile_cached_pages(meta)
            if meta.pages:
                uncached = [p.index for p in meta.pages if not p.cached]
            else:
                uncached = list(range(1, (meta.page_count or 0) + 1))
            limit = MAX_PREFETCH
            indexes = uncached[:limit]
            remaining = len(uncached) - len(indexes)
            if remaining > 0:
                warnings.append(
                    f"已达单批次预缓存上限（{limit} 页），全书尚余 {remaining} 页待缓存，可再次点击“缓存全部”继续顺延"
                )
        else:
            indexes = list(range(1, cover_count + 1))

        total = len(indexes)

        # Pre-warm official cover if provider supports it (e.g. PicAcg thumb)
        try:
            from ..providers.registry import get_provider
            prov = get_provider(meta.source)
            if hasattr(prov, "download_cover"):
                official_cover_bytes = prov.download_cover(fetched)
                if official_cover_bytes:
                    base_cover = self.cover_path(meta, 1, ext="webp")
                    thumb_cover = self.cover_path(meta, 1, COVER_THUMB_WIDTH, ext="webp")
                    self._save_cover(official_cover_bytes, base_cover, target_width=COVER_WIDTH, fmt="WEBP")
                    self._save_cover(official_cover_bytes, thumb_cover, target_width=COVER_THUMB_WIDTH, fmt="WEBP")
        except Exception as exc:
            logger.warning("预热官方封面异常，降级使用画页第一页: %s", exc)

        for index in indexes:
            success = False
            last_exc = None
            for attempt in range(2):
                try:
                    self.ensure_page(fetched, index)
                    if index <= min(meta.cover_count, meta.page_count):
                        self.ensure_webp_cover(fetched.meta, fetched, index)
                        self.ensure_webp_cover(fetched.meta, fetched, index, COVER_THUMB_WIDTH)
                    self.ensure_page_thumb(fetched.meta, fetched, index)
                    done += 1
                    success = True
                    break
                except Exception as exc:
                    last_exc = exc
                    if attempt == 0:
                        time.sleep(0.3)
            if not success:
                warnings.append(f"第 {index} 页缓存失败：{last_exc}")
                if index == 1 and last_exc is not None:
                    raise last_exc
            if on_progress is not None:
                on_progress(done, total)

        return done, warnings

    def prefetch_chapter(
        self: Any,
        fetched: FetchedComic,
        chapter: Chapter,
        *,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> tuple[int, list[str]]:
        """Download all pages of a specific chapter eagerly."""
        meta = fetched.meta
        warnings: list[str] = []
        done = 0
        indexes = list(range(chapter.start, chapter.start + chapter.page_count))
        total = len(indexes)

        for index in indexes:
            success = False
            last_exc = None
            for attempt in range(2):
                try:
                    self.ensure_page(fetched, index)
                    self.ensure_page_thumb(fetched.meta, fetched, index)
                    done += 1
                    success = True
                    break
                except Exception as exc:
                    last_exc = exc
                    if attempt == 0:
                        time.sleep(0.3)
            if not success:
                warnings.append(f"第 {index} 页缓存失败：{last_exc}")
            if on_progress is not None:
                on_progress(done, total)

        try:
            self.ensure_webp_chapter_cover(meta, fetched, chapter)
            self.ensure_webp_chapter_cover(meta, fetched, chapter, COVER_THUMB_WIDTH)
        except Exception:
            pass

        return done, warnings
