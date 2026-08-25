import secrets
import time
from datetime import datetime

from fastapi import FastAPI, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from .auth import (
    can_read,
    check_hotlink_protection,
    clear_auth_cookie,
    is_admin,
    is_auth_required,
    is_authenticated,
    is_curator,
    is_guest,
    require_admin,
    set_auth_cookie,
)
from .config import AUTH_SECRET, DATA_DIR, ENABLE_DOCS, GUEST_SECRET, LIBRARY_DIR
from .jobs import get_job, list_running, start_job
from .gate import _env_explicit, get_download_concurrency, set_download_concurrency
from .imsearch import check_imsearch_status, search_imsearch
from .models import (
    AuthStatusResponse,
    CacheProgress,
    ComicDetail,
    ConcurrencyInfo,
    ConcurrencyRequest,
    DeleteResponse,
    DiscoveryFeed,
    DiscoveryItem,
    FavoriteRequest,
    FavoriteResponse,
    ImageSearchItem,
    ImageSearchResponse,
    ImageSearchStatusResponse,
    ImportRequest,
    ImportResult,
    JobInfo,
    LibrarySummary,
    LocalAppendRequest,
    LocalComicCreateRequest,
    LocalPathImportRequest,
    LoginRequest,
    LoginResponse,
    MetadataUpdateRequest,
    PageResponse,
    ProviderInfo,
)
from .providers import get_provider, provider_list
from .storage import ComicStore

app = FastAPI(
    title="Paper Room API",
    description="Local-first comic archive API (纸间). Provider: JMComic, extensible to other sites.",
    version="0.1.0",
    docs_url="/docs" if ENABLE_DOCS else None,
    redoc_url="/redoc" if ENABLE_DOCS else None,
    openapi_url="/openapi.json" if ENABLE_DOCS else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def auth_and_security_middleware(request: Request, call_next):
    path = request.url.path

    # Allow public endpoints and non-API static files
    if (
        not path.startswith("/api/")
        or path in {"/api/health", "/api/auth/status", "/api/auth/login", "/api/auth/logout"}
        or path.startswith("/docs")
        or path.startswith("/redoc")
        or path.startswith("/openapi.json")
    ):
        return await call_next(request)

    # Check hotlink protection for image endpoints
    if "/pages/" in path or "/covers/" in path or "/chapters/" in path:
        try:
            check_hotlink_protection(request)
        except HTTPException as exc:
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    # Write / Mutating operations require curator privileges
    is_write = request.method in ("POST", "PUT", "PATCH", "DELETE") and path != "/api/search/image"
    if is_write:
        if not is_admin(request):
            if is_guest(request):
                return JSONResponse(
                    status_code=403,
                    content={"detail": "访客模式下禁止执行修改操作，请先解锁馆长权限"},
                )
            return JSONResponse(
                status_code=401,
                content={"detail": "未授权访问，需要提供有效的通行口令"},
                headers={"WWW-Authenticate": "Bearer"},
            )
    else:
        # Read operations: require valid curator or guest token
        if not can_read(request):
            return JSONResponse(
                status_code=401,
                content={"detail": "未授权访问，需要提供有效的通行口令"},
                headers={"WWW-Authenticate": "Bearer"},
            )

    return await call_next(request)


store = ComicStore()


@app.get("/api/auth/status", response_model=AuthStatusResponse)
def auth_status(request: Request) -> AuthStatusResponse:
    auth_req = is_auth_required()
    curator = is_curator(request)
    guest = is_guest(request)
    authed = curator or guest
    role = "admin" if curator else ("guest" if guest else "unauthorized")
    return AuthStatusResponse(
        auth_required=auth_req,
        authenticated=authed,
        can_write=curator,
        role=role,
        has_guest_secret=bool(GUEST_SECRET),
    )


@app.post("/api/auth/login", response_model=LoginResponse)
def auth_login(req: LoginRequest, response: Response) -> LoginResponse:
    if not is_auth_required():
        return LoginResponse(ok=True, token="", role="admin")

    secret = req.secret.strip()
    if AUTH_SECRET and secrets.compare_digest(secret, AUTH_SECRET):
        set_auth_cookie(response, AUTH_SECRET)
        return LoginResponse(ok=True, token=AUTH_SECRET, role="admin")

    if GUEST_SECRET and secrets.compare_digest(secret, GUEST_SECRET):
        set_auth_cookie(response, GUEST_SECRET)
        return LoginResponse(ok=True, token=GUEST_SECRET, role="guest")

    raise HTTPException(status_code=401, detail="通行口令错误，请重试")



@app.post("/api/auth/logout")
def auth_logout(response: Response) -> dict[str, bool]:
    clear_auth_cookie(response)
    return {"ok": True}


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "data_dir": str(DATA_DIR),
        "library": str(LIBRARY_DIR),
        "providers": [p["key"] for p in provider_list()],
        "auth_required": is_auth_required(),
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
    request: Request,
    q: str | None = Query(default=None, description="标题/作者/标签过滤"),
) -> list[LibrarySummary]:
    items = store.list_library()
    if not is_curator(request):
        items = [item for item in items if not item.hidden_from_guest]

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


@app.get("/api/search/image/status", response_model=ImageSearchStatusResponse)
def image_search_status() -> ImageSearchStatusResponse:
    """Check availability of the imsearch sidecar container."""
    status = check_imsearch_status()
    return ImageSearchStatusResponse(**status)


@app.post("/api/search/image", response_model=list[ImageSearchItem])
async def image_search(request: Request, file: UploadFile = File(...)) -> list[ImageSearchItem]:
    """Perform visual search by uploading a screenshot or cropped image."""
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="上传图片不能为空")
    results = search_imsearch(content, filename=file.filename or "query.jpg")
    if not is_curator(request):
        filtered = []
        for r in results:
            m = store.load_meta(r.source, r.source_id)
            if m and not getattr(m, "hidden_from_guest", False):
                filtered.append(r)
        return filtered
    return results


@app.get("/api/discovery/ranking", response_model=DiscoveryFeed)
def discovery_ranking(
    request: Request,
    timeframe: str = Query(default="week", pattern="^(week|month|day)$"),
    refresh: bool = False,
) -> DiscoveryFeed:
    require_admin(request)

    now_ts = time.time()
    cached_feed = store.load_discovery_feed(timeframe)
    feed: DiscoveryFeed | None = None

    if not refresh and cached_feed is not None:
        try:
            feed_dt = datetime.strptime(cached_feed.updated_at, "%Y-%m-%d %H:%M:%S")
            if now_ts - feed_dt.timestamp() < 12 * 3600:
                feed = cached_feed
        except Exception:
            feed = cached_feed

    if feed is None:
        provider = get_provider("jm")
        try:
            items = provider.fetch_ranking(timeframe=timeframe)
            feed = DiscoveryFeed(
                timeframe=timeframe,
                updated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                items=items,
            )
            store.save_discovery_feed(feed)
        except Exception as exc:
            if cached_feed is not None:
                feed = cached_feed
            else:
                raise HTTPException(status_code=502, detail=f"拉取排行榜失败：{exc}") from exc

    # Populate in_library status for current library
    for item in feed.items:
        meta = store.load_meta(item.source, item.source_id)
        item.in_library = meta is not None

    return feed


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
def comic_detail(source: str, source_id: str, request: Request) -> ComicDetail:
    meta = _require_meta(source, source_id, request)
    return store.detail(meta)


@app.delete("/api/library/{source}/{source_id}", response_model=DeleteResponse)
def delete_comic(source: str, source_id: str) -> DeleteResponse:
    _require_known_source(source)
    return DeleteResponse(ok=store.delete(source, source_id), source=source, source_id=source_id)


@app.patch("/api/library/{source}/{source_id}/metadata", response_model=ComicDetail)
def update_comic_metadata(source: str, source_id: str, req: MetadataUpdateRequest) -> ComicDetail:
    _require_known_source(source)
    updates = req.model_dump(exclude_unset=True)
    meta = store.update_metadata(source, source_id, updates)
    return store.detail(meta)


@app.post("/api/library/local/create", response_model=ComicDetail)
def create_local_comic(req: LocalComicCreateRequest) -> ComicDetail:
    meta = store.create_local_comic(req)
    return store.detail(meta)


@app.post("/api/library/local/import-path", response_model=ComicDetail)
def import_local_path(req: LocalPathImportRequest) -> ComicDetail:
    meta = store.import_local_path(req)
    return store.detail(meta)


@app.post("/api/library/local/{source_id}/upload-pages", response_model=ComicDetail)
async def upload_local_pages(
    source_id: str,
    chapter_id: str = Query(default="", description="目标章节 id"),
    new_chapter_title: str = Query(default="", description="若创建新章节，传入新章节标题"),
    files: list[UploadFile] = File(...),
) -> ComicDetail:
    file_tuples: list[tuple[str, bytes]] = []
    for f in files:
        content = await f.read()
        if content:
            file_tuples.append((f.filename or "page.webp", content))

    meta = store.append_pages(
        source_id=source_id,
        files=file_tuples,
        target_chapter=chapter_id,
        new_chapter_title=new_chapter_title,
    )
    return store.detail(meta)


@app.post("/api/library/local/{source_id}/append", response_model=ComicDetail)
def append_local_comic(source_id: str, req: LocalAppendRequest) -> ComicDetail:
    meta = store.append_pages(
        source_id=source_id,
        server_path=req.server_path,
        target_chapter=req.target_chapter,
        new_chapter_title=req.new_chapter_title,
    )
    return store.detail(meta)



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
    meta = store.load_meta(source, source_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="本子还没有导入本地书库")
    cached = store.cached_page_count(meta)
    return CacheProgress(
        cached=cached,
        total=meta.page_count,
        complete=cached >= meta.page_count,
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
def page_info(source: str, source_id: str, index: int, request: Request) -> PageResponse:
    meta = _require_meta(source, source_id, request)
    if index < 1 or index > meta.page_count:
        raise HTTPException(status_code=404, detail=f"页 {index} 不存在")
    page = next((p for p in meta.pages if p.index == index), None)
    return PageResponse(
        index=index,
        url=f"/api/library/{source}/{source_id}/pages/{index}/file",
        cached=page.cached if page is not None else False,
    )


CACHE_CONTROL_IMMUTABLE = {"Cache-Control": "public, max-age=2592000, immutable"}


@app.get("/api/library/{source}/{source_id}/pages/{index}/file")
def page_file(source: str, source_id: str, index: int, request: Request) -> FileResponse:
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
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"页面下载失败：{exc}") from exc
    return FileResponse(
        path,
        media_type=_guess_media_type(path.suffix),
        headers=CACHE_CONTROL_IMMUTABLE,
    )


@app.get("/api/library/{source}/{source_id}/pages/{index}/thumbnail")
def page_thumbnail(source: str, source_id: str, index: int, request: Request) -> FileResponse:
    """Lightweight JPEG for the detail-page page-index grid."""
    _require_known_source(source)
    meta = _require_meta(source, source_id, request)
    if index < 1 or index > meta.page_count:
        raise HTTPException(status_code=404, detail=f"页 {index} 不存在")

    thumb_path = store.page_thumb_path(meta, index)
    if thumb_path.exists() and thumb_path.stat().st_size > 0:
        return FileResponse(
            thumb_path,
            media_type="image/jpeg",
            headers=CACHE_CONTROL_IMMUTABLE,
        )

    fetched = store.load_fetched(source, source_id)
    if fetched is None:
        raise HTTPException(status_code=404, detail="本子还没有导入本地书库")

    try:
        path = store.ensure_page_thumb(meta, fetched, index)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"页面缩略图生成失败：{exc}") from exc
    return FileResponse(
        path,
        media_type="image/jpeg",
        headers=CACHE_CONTROL_IMMUTABLE,
    )


@app.get("/api/library/{source}/{source_id}/covers/{index}/file")
def cover_file(source: str, source_id: str, index: int, request: Request, v: str | None = None) -> FileResponse:
    meta = _require_meta(source, source_id, request)
    max_covers = len(meta.cover_indices) if meta.cover_indices else meta.cover_count
    if index < 1 or index > max_covers or index > meta.page_count:
        raise HTTPException(status_code=404, detail=f"封面 {index} 不存在")

    cover_path = store.cover_path(meta, index)
    if cover_path.exists() and cover_path.stat().st_size > 0:
        return FileResponse(
            cover_path,
            media_type="image/jpeg",
            headers=CACHE_CONTROL_IMMUTABLE,
        )

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
        headers=CACHE_CONTROL_IMMUTABLE,
    )


@app.get("/api/library/{source}/{source_id}/chapters/{chapter_id}/cover")
def chapter_cover(source: str, source_id: str, chapter_id: str, request: Request) -> FileResponse:
    """T17：章节目录封面（该话第一页），池化在 covers/chapters/ 下，失败前端回落占位。"""
    meta = _require_meta(source, source_id, request)
    chapter = next((c for c in meta.chapters if c.id == chapter_id), None)
    if chapter is None:
        raise HTTPException(status_code=404, detail="没有这个章节")

    chap_cover_path = store.chapter_cover_path(meta, chapter)
    if chap_cover_path.exists() and chap_cover_path.stat().st_size > 0:
        return FileResponse(
            chap_cover_path,
            media_type="image/jpeg",
            headers=CACHE_CONTROL_IMMUTABLE,
        )

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
        headers=CACHE_CONTROL_IMMUTABLE,
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


def _require_meta(source: str, source_id: str, request: Request | None = None) -> ComicMeta:
    _require_known_source(source)
    meta = store.load_meta(source, source_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="本子还没有导入本地书库")
    if request is not None and not is_curator(request) and getattr(meta, "hidden_from_guest", False):
        raise HTTPException(status_code=404, detail="本子还没有导入本地书库")
    return meta


def _guess_media_type(suffix: str) -> str:
    return {
        ".webp": "image/webp",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".avif": "image/avif",
    }.get(suffix.lower(), "application/octet-stream")


# ----------------------------------------------------------------------
# SPA Static file mounting (All-in-one / NAS single-container deployment)
# ----------------------------------------------------------------------
import os
from pathlib import Path

_DIST_DIR = Path(
    os.getenv(
        "COMIC_SHELF_STATIC_DIR",
        str(Path(__file__).resolve().parents[2] / "dist"),
    )
)

if _DIST_DIR.exists() and (_DIST_DIR / "index.html").exists():
    from fastapi.staticfiles import StaticFiles

    app.mount(
        "/",
        StaticFiles(directory=str(_DIST_DIR), html=True),
        name="spa",
    )

