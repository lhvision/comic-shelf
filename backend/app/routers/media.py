"""Media streaming, page binary delivery, thumbnails, covers, and cache progress router."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from ..config import COVER_THUMB_WIDTH
from ..jobs import get_job, start_job
from ..models import CacheProgress, JobInfo, PageResponse
from .common import (
    CACHE_CONTROL_IMMUTABLE_VARY,
    _client_accepts_webp,
    _guess_media_type,
    _prefetch_worker,
    _require_meta,
    _serve_negotiated_image,
    store,
)

router = APIRouter(tags=["media"])

CACHE_CONTROL_IMMUTABLE = {"Cache-Control": "public, max-age=2592000, immutable"}


@router.get("/api/library/{source}/{source_id}/cache", response_model=CacheProgress)
def cache_progress(source: str, source_id: str, request: Request) -> CacheProgress:
    """Returns the caching progress of the whole comic."""
    meta = _require_meta(source, source_id, request)
    cached = store.cached_page_count(meta)
    return CacheProgress(
        cached=cached,
        total=meta.page_count,
        complete=cached >= meta.page_count,
    )


@router.post("/api/library/{source}/{source_id}/cache", response_model=CacheProgress)
def cache_all(source: str, source_id: str, request: Request) -> CacheProgress:
    """Triggers background prefetching of all pages and covers in a comic."""
    _require_meta(source, source_id, request)
    fetched = store.load_fetched(source, source_id)
    if fetched is None:
        raise HTTPException(status_code=404, detail="本子还没有导入本地书库")

    if fetched.meta.custom_pages:
        raise HTTPException(status_code=400, detail="该漫画画页已由馆长重新装订保护，禁止远端自动覆盖。")

    store.reconcile_cached_pages(fetched.meta)
    cached = store.cached_page_count(fetched.meta)
    if cached >= fetched.meta.page_count:
        return CacheProgress(cached=cached, total=fetched.meta.page_count, complete=True)

    start_job(source, source_id, lambda job: _prefetch_worker(job, fetched, fetched.meta.cover_count, True))

    return CacheProgress(cached=cached, total=fetched.meta.page_count, complete=False)


@router.get("/api/library/{source}/{source_id}/cache/job", response_model=JobInfo)
def cache_job(source: str, source_id: str, request: Request) -> JobInfo:
    """Poll an in-flight prefetch job (the UI already polls cache_progress)."""
    _require_meta(source, source_id, request)
    job = get_job(source, source_id)
    if job is None:
        return JobInfo(source=source, source_id=source_id, running=False, done=True, total=0, prefetched=0)
    return JobInfo(**job)


@router.get("/api/library/{source}/{source_id}/pages/{index}", response_model=PageResponse)
def page_info(source: str, source_id: str, index: int, request: Request) -> PageResponse:
    """Returns page file link and local cache status for reader navigation."""
    meta = _require_meta(source, source_id, request)
    if index < 1 or index > meta.page_count:
        raise HTTPException(status_code=404, detail=f"页 {index} 不存在")
    page = next((p for p in meta.pages if p.index == index), None)
    return PageResponse(
        index=index,
        url=f"/api/library/{source}/{source_id}/pages/{index}/file",
        cached=page.cached if page is not None else False,
    )


@router.get("/api/library/{source}/{source_id}/pages/{index}/file")
@router.get("/api/library/{source}/{source_id}/pages/{index}/file.{ext}")
def page_file(source: str, source_id: str, index: int, request: Request, ext: str | None = None) -> FileResponse:
    """Streams original decoded page image with long-lived immutable caching."""
    meta = _require_meta(source, source_id, request)
    if index < 1 or index > meta.page_count:
        raise HTTPException(status_code=404, detail=f"页 {index} 不存在")

    page_path = store.page_path(meta, index)
    if page_path.exists() and page_path.stat().st_size > 0:
        return FileResponse(
            page_path,
            media_type=_guess_media_type(page_path.suffix),
            headers=CACHE_CONTROL_IMMUTABLE,
        )

    fetched = store.load_fetched(source, source_id)
    if fetched is None:
        raise HTTPException(status_code=404, detail="本子缓存不完整，请先刷新导入")

    try:
        path = store.ensure_page(fetched, index)
    except HTTPException:
        raise
    except (FileNotFoundError, KeyError) as exc:
        raise HTTPException(status_code=404, detail=f"页面文件不存在：{exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"页面下载失败：{exc}") from exc
    return FileResponse(
        path,
        media_type=_guess_media_type(path.suffix),
        headers=CACHE_CONTROL_IMMUTABLE,
    )


@router.get("/api/library/{source}/{source_id}/pages/{index}/thumbnail")
@router.get("/api/library/{source}/{source_id}/pages/{index}/thumbnail.{ext}")
def page_thumbnail(source: str, source_id: str, index: int, request: Request, ext: str | None = None) -> FileResponse:
    """Lightweight WebP/JPEG for the detail-page page-index grid (`ext` bound for CDN caching)."""
    meta = _require_meta(source, source_id, request)
    if index < 1 or index > meta.page_count:
        raise HTTPException(status_code=404, detail=f"页 {index} 不存在")

    wants_webp = _client_accepts_webp(request, ext)
    target_ext = "webp" if wants_webp else "jpg"
    media_type = "image/webp" if wants_webp else "image/jpeg"

    thumb_path = store.page_thumb_path(meta, index, ext=target_ext)
    if thumb_path.exists() and thumb_path.stat().st_size > 0:
        return FileResponse(
            thumb_path,
            media_type=media_type,
            headers=CACHE_CONTROL_IMMUTABLE_VARY,
        )

    fetched = store.load_fetched(source, source_id)
    if fetched is None:
        raise HTTPException(status_code=404, detail="本子还没有导入本地书库")

    try:
        path = store.ensure_page_thumb(meta, fetched, index, ext=target_ext)
    except HTTPException:
        raise
    except (FileNotFoundError, KeyError) as exc:
        raise HTTPException(status_code=404, detail=f"缩略图源文件不存在：{exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"页面缩略图生成失败：{exc}") from exc
    return FileResponse(
        path,
        media_type=media_type,
        headers=CACHE_CONTROL_IMMUTABLE_VARY,
    )


@router.get("/api/library/{source}/{source_id}/covers/{index}/file")
@router.get("/api/library/{source}/{source_id}/covers/{index}/file.{ext}")
def cover_file(
    source: str,
    source_id: str,
    index: int,
    request: Request,
    v: str | None = None,
    ext: str | None = None,
    w: int | None = None,
) -> FileResponse:
    """Streams comic cover thumbnail with WebP/JPEG negotiation and width adaptation."""
    meta = _require_meta(source, source_id, request)
    max_covers = len(meta.cover_indices) if meta.cover_indices else meta.cover_count
    if index < 1 or index > max_covers or index > meta.page_count:
        raise HTTPException(status_code=404, detail=f"封面 {index} 不存在")

    target_width = COVER_THUMB_WIDTH if (w is not None and w == COVER_THUMB_WIDTH) else None
    wants_webp = _client_accepts_webp(request, ext)

    return _serve_negotiated_image(
        source=source,
        source_id=source_id,
        wants_webp=wants_webp,
        get_path=lambda target_ext: store.cover_path(meta, index, target_width, ext=target_ext),
        generate_image=lambda fetched, target_ext: (
            store.ensure_webp_cover(meta, fetched, index, target_width)
            if target_ext == "webp"
            else store.ensure_cover(meta, fetched, index, target_width)
        ),
        error_subject=f"封面 {index}",
    )
