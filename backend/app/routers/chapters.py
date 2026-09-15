"""Chapter management, title updating, deletion, cover serving, and prefetch router."""
from __future__ import annotations

import time
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from ..config import COVER_THUMB_WIDTH
from ..db import sync_comic_dialogues
from ..events import broadcast_event
from ..jobs import start_job
from ..models import CacheProgress, ChapterUpdateRequest, ComicDetail
from .common import (
    _client_accepts_webp,
    _require_known_source,
    _require_meta,
    _serve_negotiated_image,
    store,
)

router = APIRouter(tags=["chapters"])


@router.patch("/api/library/{source}/{source_id}/chapters/{chapter_id}", response_model=ComicDetail)
def update_chapter_title(
    source: str,
    source_id: str,
    chapter_id: str,
    req: ChapterUpdateRequest,
) -> ComicDetail:
    """Updates the title of a specific chapter within a comic."""
    _require_known_source(source)
    meta = store.update_chapter_title(source, source_id, chapter_id, req.title)
    broadcast_event(
        "library_changed",
        {
            "action": "update_chapter",
            "source": source,
            "source_id": source_id,
            "chapter_id": chapter_id,
            "timestamp": time.time(),
        },
    )
    return store.detail(meta)


@router.delete("/api/library/{source}/{source_id}/chapters/{chapter_id}", response_model=ComicDetail)
def delete_chapter(source: str, source_id: str, chapter_id: str) -> ComicDetail:
    """Deletes a specific chapter from a comic, purging its page files and re-indexing remaining pages."""
    _require_known_source(source)
    meta = store.delete_chapter(source, source_id, chapter_id)
    sync_comic_dialogues(source, source_id)
    broadcast_event(
        "library_changed",
        {
            "action": "delete_chapter",
            "source": source,
            "source_id": source_id,
            "chapter_id": chapter_id,
            "timestamp": time.time(),
        },
    )
    return store.detail(meta)


@router.get("/api/library/{source}/{source_id}/chapters/{chapter_id}/cache", response_model=CacheProgress)
def chapter_cache_progress(source: str, source_id: str, chapter_id: str, request: Request) -> CacheProgress:
    """Returns the caching/prefetch progress of a specific chapter."""
    meta = _require_meta(source, source_id, request)
    chapter = next((c for c in (meta.chapters or []) if c.id == chapter_id), None)
    if chapter is None:
        raise HTTPException(status_code=404, detail=f"未找到章节 {chapter_id}")
    cached = sum(1 for p in meta.pages if p.chapter == chapter_id and p.cached)
    return CacheProgress(
        cached=cached,
        total=chapter.page_count,
        complete=cached >= chapter.page_count,
    )


@router.post("/api/library/{source}/{source_id}/chapters/{chapter_id}/cache", response_model=CacheProgress)
def cache_chapter(source: str, source_id: str, chapter_id: str, request: Request) -> CacheProgress:
    """Triggers background prefetch for a specific chapter."""
    _require_meta(source, source_id, request)
    fetched = store.load_fetched(source, source_id)
    if fetched is None:
        raise HTTPException(status_code=404, detail="本子还没有导入本地书库")
    if fetched.meta.custom_pages:
        raise HTTPException(status_code=400, detail="该漫画画页已由馆长重新装订保护，禁止远端自动覆盖。")

    chapter = next((c for c in (fetched.meta.chapters or []) if c.id == chapter_id), None)
    if chapter is None:
        raise HTTPException(status_code=404, detail=f"未找到章节 {chapter_id}")

    def _chapter_worker(job: dict) -> None:
        def _on_progress(done: int, total: int) -> None:
            job["prefetched"] = done
            job["total"] = total

        done, warnings = store.prefetch_chapter(fetched, chapter, on_progress=_on_progress)
        job["prefetched"] = done
        job["total"] = chapter.page_count
        job["warnings"] = warnings
        broadcast_event(
            "library_changed",
            {
                "action": "chapter_cache_complete" if done >= chapter.page_count else "chapter_cache_partial",
                "source": source,
                "source_id": source_id,
                "chapter_id": chapter_id,
                "timestamp": time.time(),
            },
        )

    start_job(source, source_id, _chapter_worker, chapter_id=chapter_id)
    cached = sum(1 for p in fetched.meta.pages if p.chapter == chapter_id and p.cached)
    return CacheProgress(
        cached=cached,
        total=chapter.page_count,
        complete=cached >= chapter.page_count,
    )


@router.get("/api/library/{source}/{source_id}/chapters/{chapter_id}/cover")
@router.get("/api/library/{source}/{source_id}/chapters/{chapter_id}/cover.{ext}")
def chapter_cover(
    source: str,
    source_id: str,
    chapter_id: str,
    request: Request,
    ext: str | None = None,
    w: int | None = None,
) -> FileResponse:
    """T17：章节目录封面（该话第一页），池化在 covers/chapters/ 下，失败前端回落占位。支持 WebP 内容协商。"""
    meta = _require_meta(source, source_id, request)
    chapter = next((c for c in meta.chapters if c.id == chapter_id), None)
    if chapter is None:
        raise HTTPException(status_code=404, detail="没有这个章节")

    target_width = COVER_THUMB_WIDTH if (w is not None and w == COVER_THUMB_WIDTH) else None
    wants_webp = _client_accepts_webp(request, ext)

    return _serve_negotiated_image(
        source=source,
        source_id=source_id,
        wants_webp=wants_webp,
        get_path=lambda target_ext: store.chapter_cover_path(meta, chapter, target_width, ext=target_ext),
        generate_image=lambda fetched, target_ext: (
            store.ensure_webp_chapter_cover(meta, fetched, chapter, target_width)
            if target_ext == "webp"
            else store.ensure_chapter_cover(meta, fetched, chapter, target_width)
        ),
        error_subject=f"章节封面 {chapter_id}",
    )
