from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .config import DATA_DIR, LIBRARY_DIR
from .jobs import get_job, list_running, start_job
from .gate import _env_explicit, get_download_concurrency, set_download_concurrency
from .models import (
    CacheProgress,
    ComicDetail,
    ConcurrencyInfo,
    ConcurrencyRequest,
    DeleteResponse,
    FavoriteRequest,
    FavoriteResponse,
    ImportRequest,
    ImportResult,
    JobInfo,
    LibrarySummary,
    PageResponse,
    ProviderInfo,
)
from .providers import get_provider, provider_list
from .storage import ComicStore

app = FastAPI(
    title="Paper Room API",
    description="Local-first comic archive API (纸间). Provider: JMComic, extensible to other sites.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

store = ComicStore()


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "data_dir": str(DATA_DIR),
        "library": str(LIBRARY_DIR),
        "providers": [p["key"] for p in provider_list()],
    }


@app.get("/api/providers", response_model=list[ProviderInfo])
def providers() -> list[ProviderInfo]:
    return [ProviderInfo(**p) for p in provider_list()]


@app.get("/api/cache/jobs", response_model=list[JobInfo])
def running_cache_jobs() -> list[JobInfo]:
    """Running background prefetch jobs, for live shelf-card progress."""
    return [JobInfo(**job) for job in list_running()]


@app.get("/api/settings/download-concurrency", response_model=ConcurrencyInfo)
def download_concurrency_get() -> ConcurrencyInfo:
    return ConcurrencyInfo(
        limit=get_download_concurrency(),
        min=1,
        max=16,
        env_controlled=_env_explicit(),
    )


@app.put("/api/settings/download-concurrency", response_model=ConcurrencyInfo)
def download_concurrency_put(req: ConcurrencyRequest) -> ConcurrencyInfo:
    limit = set_download_concurrency(req.limit)
    return ConcurrencyInfo(
        limit=limit,
        min=1,
        max=16,
        env_controlled=_env_explicit(),
    )


@app.get("/api/library", response_model=list[LibrarySummary])
def library(
    q: str | None = Query(default=None, description="标题/作者/标签过滤"),
) -> list[LibrarySummary]:
    items = store.list_library()
    if q is None or not q.strip():
        return items

    needle = q.strip().casefold()
    return [
        item
        for item in items
        if needle in item.title.casefold()
        or needle in item.display_id.casefold()
        or any(needle in value.casefold() for value in [*item.authors, *item.works, *item.actors, *item.tags])
        # T11：让「第 5 话」等章节标题也能命中书架搜索
        or any(needle in title.casefold() for title in item.chapter_titles)
    ]


@app.post("/api/library/import", response_model=ImportResult)
def import_comic(req: ImportRequest) -> ImportResult:
    provider = get_provider(req.source)
    source_id = provider.normalize_id(req.id)

    if not req.refresh:
        fetched = store.load_fetched(req.source, source_id)
        if fetched is not None:
            return ImportResult(meta=fetched.meta, from_cache=True, prefetched=0, warnings=[])

    # Metadata + URL discovery happen on the request thread: fast and necessary
    # for a useful response. Page/cover downloads are the slow part, so they're
    # pushed to a background daemon thread and the UI polls cache_progress.
    # T12：refresh 时把旧 bundle 传给 provider，章节没变就不重复拉每一话的 photo HTML。
    existing = store.load_fetched(req.source, source_id) if req.refresh else None
    fetched = provider.fetch(source_id, existing=existing)
    fetched.meta.cover_count = max(1, min(req.prefetch_covers or fetched.meta.cover_count, fetched.meta.page_count))
    meta = store.save_fetched(fetched, refresh=req.refresh)
    fetched.meta = meta

    cover_count = (
        fetched.meta.cover_count
        if req.prefetch_all
        else (req.prefetch_covers or fetched.meta.cover_count)
    )
    start_job(req.source, source_id, lambda job: _prefetch_worker(job, fetched, cover_count, req.prefetch_all))

    return ImportResult(
        meta=fetched.meta,
        from_cache=False,
        prefetched=0,
        warnings=[],
        background=True,
    )


@app.get("/api/library/{source}/{source_id}", response_model=ComicDetail)
def comic_detail(source: str, source_id: str) -> ComicDetail:
    _require_known_source(source)
    fetched = store.load_fetched(source, source_id)
    if fetched is None:
        raise HTTPException(status_code=404, detail="本子还没有导入本地书库")
    return store.detail(fetched.meta)


@app.delete("/api/library/{source}/{source_id}", response_model=DeleteResponse)
def delete_comic(source: str, source_id: str) -> DeleteResponse:
    _require_known_source(source)
    return DeleteResponse(ok=store.delete(source, source_id), source=source, source_id=source_id)


@app.patch("/api/library/{source}/{source_id}/favorite", response_model=FavoriteResponse)
def set_favorite(source: str, source_id: str, req: FavoriteRequest) -> FavoriteResponse:
    _require_known_source(source)
    meta = store.load_meta(source, source_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="本子还没有导入本地书库")
    meta.favorite = req.favorite
    from .storage import _write_json_atomic

    _write_json_atomic(store.album_path(source, source_id), meta.model_dump())
    return FavoriteResponse(ok=True, favorite=meta.favorite)


@app.get("/api/library/{source}/{source_id}/cache", response_model=CacheProgress)
def cache_progress(source: str, source_id: str) -> CacheProgress:
    _require_known_source(source)
    fetched = store.load_fetched(source, source_id)
    if fetched is None:
        raise HTTPException(status_code=404, detail="本子还没有导入本地书库")
    cached = store.cached_page_count(fetched.meta)
    return CacheProgress(
        cached=cached,
        total=fetched.meta.page_count,
        complete=cached >= fetched.meta.page_count,
    )


@app.post("/api/library/{source}/{source_id}/cache", response_model=CacheProgress)
def cache_all(source: str, source_id: str) -> CacheProgress:
    _require_known_source(source)
    fetched = store.load_fetched(source, source_id)
    if fetched is None:
        raise HTTPException(status_code=404, detail="本子还没有导入本地书库")

    start_job(source, source_id, lambda job: _prefetch_worker(job, fetched, fetched.meta.cover_count, True))

    cached = store.cached_page_count(fetched.meta)
    return CacheProgress(cached=cached, total=fetched.meta.page_count, complete=cached >= fetched.meta.page_count)


@app.get("/api/library/{source}/{source_id}/cache/job", response_model=JobInfo)
def cache_job(source: str, source_id: str) -> JobInfo:
    """Poll an in-flight prefetch job (the UI already polls cache_progress)."""
    _require_known_source(source)
    job = get_job(source, source_id)
    if job is None:
        return JobInfo(source=source, source_id=source_id, running=False, done=True, total=0, prefetched=0)
    return JobInfo(**job)


@app.get("/api/library/{source}/{source_id}/pages/{index}", response_model=PageResponse)
def page_info(source: str, source_id: str, index: int) -> PageResponse:
    _require_known_source(source)
    fetched = store.load_fetched(source, source_id)
    if fetched is None:
        raise HTTPException(status_code=404, detail="本子还没有导入本地书库")
    meta = fetched.meta
    if index < 1 or index > meta.page_count:
        raise HTTPException(status_code=404, detail=f"页 {index} 不存在")
    return PageResponse(
        index=index,
        url=f"/api/library/{source}/{source_id}/pages/{index}/file",
        cached=_page_exists(store, meta, index),
    )


@app.get("/api/library/{source}/{source_id}/pages/{index}/file")
def page_file(source: str, source_id: str, index: int) -> FileResponse:
    meta = _require_meta(source, source_id)
    if index < 1 or index > meta.page_count:
        raise HTTPException(status_code=404, detail=f"页 {index} 不存在")

    fetched = store.load_fetched(source, source_id)
    if fetched is None:
        raise HTTPException(status_code=404, detail="本子缓存不完整，请先刷新导入")

    try:
        path = store.ensure_page(fetched, index)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"页面下载失败：{exc}") from exc
    return FileResponse(
        path,
        media_type=_guess_media_type(path.suffix),
        headers={"Cache-Control": "no-cache"},
    )


@app.get("/api/library/{source}/{source_id}/pages/{index}/thumbnail")
def page_thumbnail(source: str, source_id: str, index: int) -> FileResponse:
    """Lightweight JPEG for the detail-page page-index grid."""
    _require_known_source(source)
    fetched = store.load_fetched(source, source_id)
    if fetched is None:
        raise HTTPException(status_code=404, detail="本子还没有导入本地书库")
    meta = fetched.meta
    if index < 1 or index > meta.page_count:
        raise HTTPException(status_code=404, detail=f"页 {index} 不存在")

    try:
        path = store.ensure_page_thumb(meta, fetched, index)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"页面缩略图生成失败：{exc}") from exc
    return FileResponse(
        path,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-cache"},
    )


@app.get("/api/library/{source}/{source_id}/covers/{index}/file")
def cover_file(source: str, source_id: str, index: int) -> FileResponse:
    meta = _require_meta(source, source_id)
    if index < 1 or index > meta.cover_count or index > meta.page_count:
        raise HTTPException(status_code=404, detail=f"封面 {index} 不存在")

    fetched = store.load_fetched(source, source_id)
    if fetched is None:
        raise HTTPException(status_code=404, detail="本子缓存不完整，请先刷新导入")

    try:
        path = store.ensure_cover(meta, fetched, index)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"封面生成失败：{exc}") from exc
    return FileResponse(
        path,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-cache"},
    )


@app.get("/api/library/{source}/{source_id}/chapters/{chapter_id}/cover")
def chapter_cover(source: str, source_id: str, chapter_id: str) -> FileResponse:
    """T17：章节目录封面（该话第一页），池化在 covers/chapters/ 下，失败前端回落占位。"""
    meta = _require_meta(source, source_id)
    chapter = next((c for c in meta.chapters if c.id == chapter_id), None)
    if chapter is None:
        raise HTTPException(status_code=404, detail="没有这个章节")

    fetched = store.load_fetched(source, source_id)
    if fetched is None:
        raise HTTPException(status_code=404, detail="本子缓存不完整，请先刷新导入")

    try:
        path = store.ensure_chapter_cover(meta, fetched, chapter)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"章节封面生成失败：{exc}") from exc
    return FileResponse(
        path,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-cache"},
    )


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------
def _prefetch_worker(
    job: dict,
    fetched,
    cover_count: int,
    prefetch_all: bool,
) -> None:
    """Run inside a background thread; keeps job progress fresh for polling."""
    meta = fetched.meta

    def _on_progress(done: int, total: int) -> None:
        job["prefetched"] = done
        job["total"] = total

    done, warnings = store.prefetch(
        fetched,
        cover_count=cover_count,
        prefetch_all=prefetch_all,
        on_progress=_on_progress,
    )
    job["prefetched"] = done
    job["total"] = meta.page_count
    job["warnings"] = warnings


def _require_known_source(source: str) -> None:
    if source not in {p["key"] for p in provider_list()}:
        raise HTTPException(status_code=404, detail=f"未知来源：{source}")


def _require_meta(source: str, source_id: str):
    _require_known_source(source)
    meta = store.load_meta(source, source_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="本子还没有导入本地书库")
    return meta


def _page_exists(store: ComicStore, meta, index: int) -> bool:
    page = next((p for p in meta.pages if p.index == index), None)
    return page is not None and (store.pages_dir(meta.source, meta.source_id) / page.file).exists()


def _guess_media_type(suffix: str) -> str:
    return {
        ".webp": "image/webp",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".avif": "image/avif",
    }.get(suffix.lower(), "application/octet-stream")
