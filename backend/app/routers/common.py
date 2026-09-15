"""Common dependencies, helpers, and shared store instance for Paper Room routers."""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Callable

from fastapi import HTTPException, Request
from fastapi.responses import FileResponse

from ..auth import is_curator
from ..config import COVER_THUMB_WIDTH
from ..events import broadcast_event
from ..models import ComicMeta, FetchedComic
from ..providers import provider_list
from ..storage import ComicStore

logger = logging.getLogger(__name__)

# Immutable cache control with Vary: Accept for WebP/JPEG content-negotiated responses
CACHE_CONTROL_IMMUTABLE_VARY = {
    "Cache-Control": "public, max-age=31536000, immutable",
    "Vary": "Accept",
}

# Global singleton storage instance
store = ComicStore()


def _require_known_source(source: str) -> None:
    """Validates source provider key against registered provider list."""
    if source not in {p["key"] for p in provider_list()}:
        raise HTTPException(status_code=404, detail=f"未知来源：{source}")


def _require_meta(source: str, source_id: str, request: Request | None = None) -> ComicMeta:
    """Loads comic metadata from disk, enforcing guest privacy boundaries."""
    _require_known_source(source)
    meta = store.load_meta(source, source_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="本子还没有导入本地书库")
    if request is not None and not is_curator(request) and getattr(meta, "hidden_from_guest", False):
        raise HTTPException(status_code=404, detail="本子还没有导入本地书库")
    return meta


def _guess_media_type(suffix: str) -> str:
    """Resolves standard MIME media type from image file suffix."""
    return {
        ".webp": "image/webp",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".avif": "image/avif",
    }.get(suffix.lower(), "application/octet-stream")


def _client_accepts_webp(request: Request, ext: str | None = None) -> bool:
    """Detects whether client prefers or explicitly requests WebP image format."""
    if ext:
        return ext.lower() == "webp"
    accept = request.headers.get("accept", "")
    return "image/webp" in accept


def _serve_negotiated_image(
    *,
    source: str,
    source_id: str,
    wants_webp: bool,
    get_path: Callable[[str], Path],
    generate_image: Callable[[FetchedComic | None, str], Path],
    error_subject: str = "封面",
) -> FileResponse:
    """Serves a content-negotiated image (WebP or JPEG), generating it on-demand if missing."""
    ext = "webp" if wants_webp else "jpg"
    media_type = "image/webp" if wants_webp else "image/jpeg"

    existing = get_path(ext)
    if existing.exists() and existing.stat().st_size > 0:
        return FileResponse(
            existing,
            media_type=media_type,
            headers=CACHE_CONTROL_IMMUTABLE_VARY,
        )

    fetched = store.load_fetched(source, source_id)
    try:
        path = generate_image(fetched, ext)
    except (FileNotFoundError, KeyError) as exc:
        raise HTTPException(status_code=404, detail=f"{error_subject}不存在或缓存不完整：{exc}") from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"{error_subject}生成失败：{exc}") from exc

    return FileResponse(
        path,
        media_type=media_type,
        headers=CACHE_CONTROL_IMMUTABLE_VARY,
    )


def _prefetch_worker(
    job: dict[str, Any],
    fetched: FetchedComic,
    cover_count: int,
    prefetch_all: bool,
) -> None:
    """Run inside a background thread; keeps job progress fresh for polling."""
    meta = fetched.meta
    if meta.custom_pages:
        job["status"] = "done"
        job["prefetched"] = meta.page_count
        job["total"] = meta.page_count
        return

    store.reconcile_cached_pages(meta)
    initial_cached = store.cached_page_count(meta)
    job["total"] = meta.page_count
    job["prefetched"] = initial_cached

    def _on_progress(batch_done: int, batch_total: int) -> None:
        job["prefetched"] = min(initial_cached + batch_done, meta.page_count)
        job["total"] = meta.page_count

    warnings: list[str] = []
    try:
        done, warnings = store.prefetch(
            fetched,
            cover_count=cover_count,
            prefetch_all=prefetch_all,
            on_progress=_on_progress,
        )
    finally:
        store.reconcile_cached_pages(meta)
        final_cached = store.cached_page_count(meta)
        job["prefetched"] = final_cached
        job["total"] = meta.page_count
        job["warnings"] = warnings
        is_complete = final_cached >= meta.page_count
        import sys
        app_main = sys.modules.get("app.main")
        emit_fn = getattr(app_main, "broadcast_event", broadcast_event) if app_main else broadcast_event
        emit_fn(
            "library_changed",
            {
                "action": "cache_complete" if is_complete else "cache_partial",
                "source": fetched.meta.source,
                "source_id": fetched.meta.source_id,
                "timestamp": time.time(),
            },
        )
