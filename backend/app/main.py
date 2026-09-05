import asyncio
import secrets
import time
from datetime import datetime

from fastapi import FastAPI, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse

from pathlib import Path
from typing import Any, Callable

from .auth import (
    can_read,
    check_hotlink_protection,
    clear_auth_cookie,
    clear_device_cookie,
    extract_device_token,
    extract_token,
    get_client_ip,
    get_current_user_id,
    get_user_context,
    is_auth_required,
    is_authenticated,
    is_curator,
    is_guest,
    is_request_secure,
    require_curator,
    set_auth_cookie,
    set_device_cookie,
)
from .config import AUTH_SECRET, COVER_THUMB_WIDTH, DATA_DIR, ENABLE_DOCS, LIBRARY_DIR
from .db import (
    claim_guest_pass,
    create_guest_pass,
    delete_guest_device,
    delete_guest_pass,
    get_device_by_token,
    get_guest_pass_by_token,
    get_user_favorites,
    get_user_progress,
    get_user_all_progress,
    init_db,
    is_user_favorite,
    list_guest_passes,
    migrate_legacy_favorites,
    register_guest_device,
    set_user_favorite,
    set_user_progress,
    touch_device_active,
    update_guest_pass,
    verify_guest_pass_pin,
)
from .abuse import (
    clear_cooling_lock,
    clear_ip_login_failures,
    clear_pin_failures,
    clear_rate_limit,
    is_eviction_cooling_locked,
    is_ip_login_locked,
    is_pass_rate_limited,
    is_pin_locked,
    record_ip_login_failure_and_check_lock,
    record_pin_failure_and_check_lock,
)
from .jobs import get_job, list_running, start_job
from .gate import _env_explicit, get_download_concurrency, set_download_concurrency
from .imsearch import check_imsearch_status, search_imsearch
from .storage import ComicStore, _write_json_atomic
from .models import (
    AuthStatusResponse,
    CacheProgress,
    ChapterUpdateRequest,
    ClaimGuestPassRequest,
    ComicDetail,
    ComicMeta,
    ConcurrencyInfo,
    ConcurrencyRequest,
    CreateGuestPassRequest,
    DeleteResponse,
    DiscoveryFeed,
    DiscoveryItem,
    FavoriteRequest,
    FavoriteResponse,
    FetchedComic,
    GuestPassItem,
    GuestPrivacySettings,
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
    ReadingProgressRequest,
    ReadingProgressResponse,
    ReplacePathRequest,
    UpdateGuestPassRequest,
)
from contextlib import asynccontextmanager

from .abuse import check_guest_rate_limit
from .events import broadcast_event, shutdown_events, router as events_router
from .gate import get_guest_hide_new_comics, set_guest_hide_new_comics
from .providers import get_provider, provider_list


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Broadcast version event on service start so connected clients check for updates
    broadcast_event("system_version", {"version": "latest", "timestamp": time.time()})
    yield
    shutdown_events()


app = FastAPI(
    title="Paper Room API",
    description="Local-first comic archive API (纸间). Provider: JMComic, extensible to other sites.",
    version="0.1.0",
    docs_url="/docs" if ENABLE_DOCS else None,
    redoc_url="/redoc" if ENABLE_DOCS else None,
    openapi_url="/openapi.json" if ENABLE_DOCS else None,
    lifespan=lifespan,
)

app.include_router(events_router)

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


PUBLIC_AUTH_PATHS = frozenset({
    "/api/health",
    "/api/auth/status",
    "/api/auth/login",
    "/api/auth/claim",
    "/api/auth/logout",
})


@app.middleware("http")
async def auth_and_security_middleware(request: Request, call_next):
    path = request.url.path

    # Allow public endpoints and non-API static files
    if (
        not path.startswith("/api/")
        or path in PUBLIC_AUTH_PATHS
        or path.startswith("/api/events")
        or path.startswith("/docs")
        or path.startswith("/redoc")
        or path == "/openapi.json"
    ):
        return await call_next(request)

    # Check hotlink protection for image binary endpoints (including static extension aliases)
    clean_stem = path
    if "." in path:
        stem, ext = path.rsplit(".", 1)
        if ext.lower() in {"webp", "jpg", "jpeg", "png"}:
            clean_stem = stem
    if clean_stem.endswith(("/file", "/thumbnail", "/cover")):
        try:
            check_hotlink_protection(request)
        except HTTPException as exc:
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

        # Rate limiting for guest readers on reading page binary endpoints (120 P/min + 45 P burst)
        # Note: /cover is excluded to prevent bookshelf grid loading from false-positive rate limiting
        if clean_stem.endswith(("/file", "/thumbnail")):
            _uid, _name, role = get_user_context(request)
            if role == "guest" and _uid.startswith("guest:"):
                try:
                    pass_id_val = int(_uid.split(":", 1)[1])
                    if not check_guest_rate_limit(pass_id_val):
                        return JSONResponse(
                            status_code=429,
                            content={"detail": "阅读翻页速率异常（超过 120 页/分钟），请稍憩数秒"},
                            headers={"Retry-After": "5"},
                        )
                except (ValueError, IndexError):
                    pass

    # Allow guest-permitted mutating operations (search, isolated favorite & reading progress)
    is_user_mutation = (
        (request.method == "POST" and path == "/api/search/image")
        or (request.method == "PATCH" and path.endswith("/favorite"))
        or (request.method == "PUT" and path.endswith("/progress"))
    )

    is_write = request.method in ("POST", "PUT", "PATCH", "DELETE") and not is_user_mutation
    if is_write:
        if not is_curator(request):
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
        # Read or guest-allowed mutation: require valid curator or guest token
        if not can_read(request):
            _uid, _name, role = get_user_context(request)
            detail = "通行证已过期，请联系馆长续期" if role == "expired" else "未授权访问，需要提供有效的通行口令"
            return JSONResponse(
                status_code=401,
                content={"detail": detail},
                headers={"WWW-Authenticate": "Bearer"},
            )

    return await call_next(request)


init_db()
store = ComicStore()


def _migrate_existing_favorites_to_db() -> None:
    try:
        curator_favs = get_user_favorites("curator")
        if curator_favs:
            return
        legacy_favs = []
        if LIBRARY_DIR.exists():
            for s_dir in LIBRARY_DIR.iterdir():
                if not s_dir.is_dir():
                    continue
                for c_dir in s_dir.iterdir():
                    if not c_dir.is_dir():
                        continue
                    meta = store.load_meta(s_dir.name, c_dir.name)
                    if meta and getattr(meta, "favorite", False):
                        legacy_favs.append((s_dir.name, c_dir.name))
        if legacy_favs:
            migrate_legacy_favorites(legacy_favs, "curator")
    except Exception:
        pass


_migrate_existing_favorites_to_db()


@app.get("/api/auth/status", response_model=AuthStatusResponse)
def auth_status(request: Request, response: Response) -> AuthStatusResponse:
    auth_req = is_auth_required()
    user_id, username, role = get_user_context(request)
    curator = role == "admin"
    guest = role == "guest"
    authed = curator or guest
    if authed and hasattr(request.state, "new_device_token"):
        is_sec = is_request_secure(request)
        set_device_cookie(response, request.state.new_device_token, secure=is_sec)

    requires_claim = False
    requires_pin = False
    token = extract_token(request)
    p_item = None
    if not authed and token:
        p_item = get_guest_pass_by_token(token)
        if p_item and p_item["is_active"] and not p_item["is_expired"]:
            if not p_item["is_claimed"]:
                requires_claim = True
            else:
                requires_pin = True

    return AuthStatusResponse(
        auth_required=auth_req,
        authenticated=authed,
        can_write=curator,
        role=role if authed else "unauthorized",
        username=username if authed else (p_item["username"] if p_item and (requires_claim or requires_pin) else ""),
        user_id=user_id if authed else (f"guest:{p_item['id']}" if p_item and (requires_claim or requires_pin) else ""),
        is_claimed=not requires_claim,
        requires_pin=requires_pin,
        requires_claim=requires_claim,
    )


@app.post("/api/auth/login", response_model=LoginResponse)
def auth_login(req: LoginRequest, request: Request, response: Response) -> LoginResponse:
    if not is_auth_required():
        return LoginResponse(ok=True, token="", role="admin", username="馆长", user_id="curator")

    ip = get_client_ip(request)
    if is_ip_login_locked(ip):
        raise HTTPException(status_code=429, detail="口令尝试过于频繁，该网络地址已临时锁定 5 分钟，请稍后再试")

    is_sec = is_request_secure(request)
    secret = req.secret.strip()
    if AUTH_SECRET and secrets.compare_digest(secret, AUTH_SECRET):
        clear_ip_login_failures(ip)
        set_auth_cookie(response, AUTH_SECRET, secure=is_sec)
        clear_device_cookie(response)  # Clean up any lingering guest device session
        return LoginResponse(ok=True, token=AUTH_SECRET, role="admin", username="馆长", user_id="curator")

    pass_item = get_guest_pass_by_token(secret)
    if pass_item is not None:
        if not pass_item["is_active"]:
            record_ip_login_failure_and_check_lock(ip)
            raise HTTPException(status_code=401, detail="该访客通行证已被停用")
        if pass_item["is_expired"]:
            record_ip_login_failure_and_check_lock(ip)
            raise HTTPException(status_code=401, detail="通行证已过期，请联系馆长续期")

        ua = request.headers.get("user-agent", "")

        # Case A: Unclaimed pass -> requires setting PIN
        if not pass_item["is_claimed"]:
            if not req.pin or not req.pin.strip():
                return LoginResponse(
                    ok=False,
                    token=pass_item["token"],
                    role="guest",
                    username=pass_item["username"],
                    user_id=f"guest:{pass_item['id']}",
                    is_claimed=False,
                    requires_claim=True,
                )
            try:
                claimed = claim_guest_pass(pass_item["id"], req.pin, req.username)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc))

            try:
                dev = register_guest_device(claimed["id"], user_agent=ua, ip=ip)
            except ValueError as exc:
                msg = str(exc)
                if "频繁" in msg or "安全保护锁定" in msg:
                    raise HTTPException(status_code=429, detail=msg)
                raise HTTPException(status_code=400, detail=msg)

            clear_ip_login_failures(ip)
            set_auth_cookie(response, claimed["token"], secure=is_sec)
            set_device_cookie(response, dev["device_token"], secure=is_sec)
            return LoginResponse(
                ok=True,
                token=claimed["token"],
                role="guest",
                username=claimed["username"],
                user_id=f"guest:{claimed['id']}",
                device_token=dev["device_token"],
                is_claimed=True,
            )

        # Case B: Claimed pass -> check device token or require PIN
        dev = None
        existing_dev_token = extract_device_token(request)
        if existing_dev_token:
            existing_dev = get_device_by_token(existing_dev_token)
            if existing_dev and existing_dev.get("pass_id") == pass_item["id"]:
                dev = existing_dev
                touch_device_active(dev["id"], ip)

        if dev is not None:
            clear_ip_login_failures(ip)
            set_auth_cookie(response, pass_item["token"], secure=is_sec)
            set_device_cookie(response, dev["device_token"], secure=is_sec)
            return LoginResponse(
                ok=True,
                token=pass_item["token"],
                role="guest",
                username=pass_item["username"],
                user_id=f"guest:{pass_item['id']}",
                device_token=dev["device_token"],
                is_claimed=True,
            )

        if not req.pin or not req.pin.strip():
            return LoginResponse(
                ok=False,
                token=pass_item["token"],
                role="guest",
                username=pass_item["username"],
                user_id=f"guest:{pass_item['id']}",
                is_claimed=True,
                requires_pin=True,
            )

        locked, lock_reason = is_pin_locked(pass_item["id"], ip)
        if locked:
            raise HTTPException(status_code=429, detail=lock_reason)

        if not verify_guest_pass_pin(pass_item["id"], req.pin.strip()):
            is_now_locked, failure_reason = record_pin_failure_and_check_lock(pass_item["id"], ip)
            if is_now_locked:
                raise HTTPException(status_code=429, detail=failure_reason)
            raise HTTPException(status_code=401, detail="PIN 码错误，请重新输入")

        clear_pin_failures(pass_item["id"], ip)
        clear_ip_login_failures(ip)

        try:
            dev = register_guest_device(pass_item["id"], user_agent=ua, ip=ip)
        except ValueError as exc:
            msg = str(exc)
            if "频繁" in msg or "安全保护锁定" in msg:
                raise HTTPException(status_code=429, detail=msg)
            raise HTTPException(status_code=400, detail=msg)

        set_auth_cookie(response, pass_item["token"], secure=is_sec)
        set_device_cookie(response, dev["device_token"], secure=is_sec)
        return LoginResponse(
            ok=True,
            token=pass_item["token"],
            role="guest",
            username=pass_item["username"],
            user_id=f"guest:{pass_item['id']}",
            device_token=dev["device_token"],
            is_claimed=True,
        )

    if record_ip_login_failure_and_check_lock(ip):
        raise HTTPException(status_code=429, detail="口令尝试过于频繁，该网络地址已临时锁定 5 分钟，请稍后再试")
    raise HTTPException(status_code=401, detail="通行口令错误，请重试")


@app.post("/api/auth/claim", response_model=LoginResponse)
def auth_claim(req: ClaimGuestPassRequest, request: Request, response: Response) -> LoginResponse:
    return auth_login(LoginRequest(secret=req.token, pin=req.pin, username=req.username), request, response)



@app.post("/api/auth/logout")
def auth_logout(request: Request, response: Response) -> dict[str, bool]:
    dev_token = extract_device_token(request)
    if dev_token:
        dev = get_device_by_token(dev_token)
        if dev:
            delete_guest_device(dev["id"])
    clear_auth_cookie(response)
    clear_device_cookie(response)
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


@app.get("/api/settings/guest-privacy", response_model=GuestPrivacySettings)
def guest_privacy_get() -> GuestPrivacySettings:
    return GuestPrivacySettings(guest_hide_new_comics=get_guest_hide_new_comics())


@app.put("/api/settings/guest-privacy", response_model=GuestPrivacySettings)
def guest_privacy_put(req: GuestPrivacySettings, request: Request) -> GuestPrivacySettings:
    require_curator(request)
    val = set_guest_hide_new_comics(req.guest_hide_new_comics)
    return GuestPrivacySettings(guest_hide_new_comics=val)



@app.get("/api/library", response_model=list[LibrarySummary])
def library(
    request: Request,
    q: str | None = Query(default=None, description="标题/作者/标签过滤"),
) -> list[LibrarySummary]:
    user_id = get_current_user_id(request)
    user_favs = get_user_favorites(user_id)
    user_prog = get_user_all_progress(user_id)
    items = store.list_library()
    for item in items:
        item.favorite = (item.source, item.source_id) in user_favs
        item.last_page = user_prog.get((item.source, item.source_id), 0)

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
    results = await asyncio.to_thread(search_imsearch, content, filename=file.filename or "query.jpg")
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
    require_curator(request)

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
    try:
        source_id = provider.normalize_id(req.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not req.refresh:
        fetched = store.load_fetched(req.source, source_id)
        if fetched is not None:
            return ImportResult(meta=fetched.meta, from_cache=True, prefetched=0, warnings=[])

    # Metadata + URL discovery happen on the request thread: fast and necessary
    # for a useful response. Page/cover downloads are the slow part, so they're
    # pushed to a background daemon thread and the UI polls cache_progress.
    # T12：refresh 时把旧 bundle 传给 provider，章节没变就不重复拉每一话的 photo HTML。
    existing = store.load_fetched(req.source, source_id) if req.refresh else None
    try:
        fetched = provider.fetch(source_id, existing=existing)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"从来源获取漫画失败：{exc}") from exc

    fetched.meta.cover_count = max(1, min(req.prefetch_covers or fetched.meta.cover_count, fetched.meta.page_count))
    if not req.refresh and existing is None and get_guest_hide_new_comics():
        fetched.meta.hidden_from_guest = True
    meta = store.save_fetched(fetched, refresh=req.refresh)
    fetched.meta = meta

    broadcast_event(
        "library_changed",
        {"action": "import", "source": req.source, "source_id": source_id, "timestamp": time.time()},
    )

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
    detail = store.detail(meta)
    user_id = get_current_user_id(request)
    detail.meta.favorite = is_user_favorite(user_id, source, source_id)
    return detail


@app.delete("/api/library/{source}/{source_id}", response_model=DeleteResponse)
def delete_comic(source: str, source_id: str) -> DeleteResponse:
    _require_known_source(source)
    ok = store.delete(source, source_id)
    if ok:
        broadcast_event(
            "library_changed",
            {"action": "delete", "source": source, "source_id": source_id, "timestamp": time.time()},
        )
    return DeleteResponse(ok=ok, source=source, source_id=source_id)


@app.patch("/api/library/{source}/{source_id}/metadata", response_model=ComicDetail)
def update_comic_metadata(source: str, source_id: str, req: MetadataUpdateRequest) -> ComicDetail:
    _require_known_source(source)
    updates = req.model_dump(exclude_unset=True)
    meta = store.update_metadata(source, source_id, updates)
    broadcast_event(
        "library_changed",
        {"action": "update_metadata", "source": source, "source_id": source_id, "timestamp": time.time()},
    )
    return store.detail(meta)


@app.patch("/api/library/{source}/{source_id}/chapters/{chapter_id}", response_model=ComicDetail)
def update_chapter_title(
    source: str,
    source_id: str,
    chapter_id: str,
    req: ChapterUpdateRequest,
) -> ComicDetail:
    _require_known_source(source)
    meta = store.update_chapter_title(source, source_id, chapter_id, req.title)
    return store.detail(meta)


@app.delete("/api/library/{source}/{source_id}/chapters/{chapter_id}", response_model=ComicDetail)
def delete_chapter(source: str, source_id: str, chapter_id: str) -> ComicDetail:
    _require_known_source(source)
    meta = store.delete_chapter(source, source_id, chapter_id)
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

    meta = await asyncio.to_thread(
        store.append_pages,
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


@app.post("/api/library/{source}/{source_id}/replace-pages", response_model=ComicDetail)
async def replace_comic_pages(
    source: str,
    source_id: str,
    chapter_id: str = Query(default="", description="目标章节 id（多章节漫画可选）"),
    files: list[UploadFile] = File(...),
) -> ComicDetail:
    _require_known_source(source)
    file_tuples: list[tuple[str, bytes]] = []
    for f in files:
        content = await f.read()
        if content:
            file_tuples.append((f.filename or "page.webp", content))

    meta = await asyncio.to_thread(
        store.replace_pages,
        source=source,
        source_id=source_id,
        files=file_tuples,
        target_chapter=chapter_id,
    )
    return store.detail(meta)


@app.post("/api/library/{source}/{source_id}/replace-path", response_model=ComicDetail)
def replace_comic_pages_from_path(
    source: str,
    source_id: str,
    req: ReplacePathRequest,
) -> ComicDetail:
    _require_known_source(source)
    meta = store.replace_pages(
        source=source,
        source_id=source_id,
        server_path=req.server_path,
        target_chapter=req.target_chapter,
    )
    return store.detail(meta)


@app.patch("/api/library/{source}/{source_id}/favorite", response_model=FavoriteResponse)
def set_favorite(source: str, source_id: str, req: FavoriteRequest, request: Request) -> FavoriteResponse:
    _require_known_source(source)
    _require_meta(source, source_id, request)
    user_id = get_current_user_id(request)
    new_fav = set_user_favorite(user_id, source, source_id, req.favorite)
    return FavoriteResponse(ok=True, favorite=new_fav)


@app.get("/api/library/{source}/{source_id}/progress", response_model=ReadingProgressResponse)
def get_reading_progress_api(source: str, source_id: str, request: Request) -> ReadingProgressResponse:
    meta = _require_meta(source, source_id, request)
    user_id = get_current_user_id(request)
    prog = get_user_progress(user_id, source, source_id)
    if prog is None:
        return ReadingProgressResponse(ok=True, last_page=0, total_pages=meta.page_count, updated_at=0)
    return ReadingProgressResponse(
        ok=True,
        last_page=prog["last_page"],
        total_pages=prog["total_pages"],
        updated_at=prog["updated_at"],
    )


@app.put("/api/library/{source}/{source_id}/progress", response_model=ReadingProgressResponse)
def save_reading_progress_api(
    source: str,
    source_id: str,
    req: ReadingProgressRequest,
    request: Request,
) -> ReadingProgressResponse:
    meta = _require_meta(source, source_id, request)
    user_id = get_current_user_id(request)
    prog = set_user_progress(user_id, source, source_id, req.page, req.total_pages or meta.page_count)
    return ReadingProgressResponse(ok=True, **prog)


# ----------------------------------------------------------------------
# 馆长访客通行证管理（Curator Passes Management）
# ----------------------------------------------------------------------

@app.get("/api/curator/passes", response_model=list[GuestPassItem])
def curator_list_passes(request: Request) -> list[GuestPassItem]:
    require_curator(request)
    return [GuestPassItem(**p) for p in list_guest_passes()]


@app.post("/api/curator/passes", response_model=GuestPassItem)
def curator_create_pass(req: CreateGuestPassRequest, request: Request) -> GuestPassItem:
    require_curator(request)
    try:
        p = create_guest_pass(
            username=req.username,
            expires_days=req.expires_days,
            custom_token=req.custom_token,
            pin=req.pin,
            max_devices=req.max_devices,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return GuestPassItem(**p)


@app.patch("/api/curator/passes/{pass_id}", response_model=GuestPassItem)
def curator_update_pass(pass_id: int, req: UpdateGuestPassRequest, request: Request) -> GuestPassItem:
    require_curator(request)
    try:
        p = update_guest_pass(
            pass_id=pass_id,
            username=req.username,
            is_active=req.is_active,
            extend_days=req.extend_days,
            reset_token=req.reset_token,
            reset_pin=req.reset_pin,
            custom_pin=req.custom_pin,
            expires_days=req.expires_days,
            max_devices=req.max_devices,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if p is None:
        raise HTTPException(status_code=404, detail="未找到该访客通行证")
    if req.reset_pin or req.custom_pin:
        clear_pin_failures(pass_id)
    return GuestPassItem(**p)


@app.delete("/api/curator/passes/{pass_id}")
def curator_delete_pass(pass_id: int, request: Request) -> dict[str, bool]:
    require_curator(request)
    ok = delete_guest_pass(pass_id)
    if not ok:
        raise HTTPException(status_code=404, detail="未找到该访客通行证")
    return {"ok": True}


@app.delete("/api/curator/passes/{pass_id}/devices/{device_id}")
def curator_delete_pass_device(pass_id: int, device_id: int, request: Request) -> dict[str, bool]:
    require_curator(request)
    ok = delete_guest_device(device_id, pass_id=pass_id)
    if not ok:
        raise HTTPException(status_code=404, detail="未找到该设备或已被移除")
    return {"ok": True}


@app.get("/api/library/{source}/{source_id}/cache", response_model=CacheProgress)
def cache_progress(source: str, source_id: str, request: Request) -> CacheProgress:
    meta = _require_meta(source, source_id, request)
    cached = store.cached_page_count(meta)
    return CacheProgress(
        cached=cached,
        total=meta.page_count,
        complete=cached >= meta.page_count,
    )


@app.post("/api/library/{source}/{source_id}/cache", response_model=CacheProgress)
def cache_all(source: str, source_id: str, request: Request) -> CacheProgress:
    _require_meta(source, source_id, request)
    fetched = store.load_fetched(source, source_id)
    if fetched is None:
        raise HTTPException(status_code=404, detail="本子还没有导入本地书库")

    if fetched.meta.custom_pages:
        raise HTTPException(status_code=400, detail="该漫画画页已由馆长重新装订保护，禁止远端自动覆盖。")

    start_job(source, source_id, lambda job: _prefetch_worker(job, fetched, fetched.meta.cover_count, True))

    cached = store.cached_page_count(fetched.meta)
    return CacheProgress(cached=cached, total=fetched.meta.page_count, complete=cached >= fetched.meta.page_count)


@app.get("/api/library/{source}/{source_id}/cache/job", response_model=JobInfo)
def cache_job(source: str, source_id: str, request: Request) -> JobInfo:
    """Poll an in-flight prefetch job (the UI already polls cache_progress)."""
    _require_meta(source, source_id, request)
    job = get_job(source, source_id)
    if job is None:
        return JobInfo(source=source, source_id=source_id, running=False, done=True, total=0, prefetched=0)
    return JobInfo(**job)


@app.get("/api/library/{source}/{source_id}/chapters/{chapter_id}/cache", response_model=CacheProgress)
def chapter_cache_progress(source: str, source_id: str, chapter_id: str, request: Request) -> CacheProgress:
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


@app.post("/api/library/{source}/{source_id}/chapters/{chapter_id}/cache", response_model=CacheProgress)
def cache_chapter(source: str, source_id: str, chapter_id: str, request: Request) -> CacheProgress:
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
                "action": "chapter_cache_complete",
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


@app.get("/api/library/{source}/{source_id}/pages/{index}", response_model=PageResponse)
def page_info(source: str, source_id: str, index: int, request: Request) -> PageResponse:
    meta = _require_meta(source, source_id, request)
    if index < 1 or index > meta.page_count:
        raise HTTPException(status_code=404, detail=f"页 {index} 不存在")
    page = next((p for p in meta.pages if p.index == index), None)
    return PageResponse(
        index=index,
        url=f"/api/library/{source}/{source_id}/pages/{index}/file.webp",
        cached=page.cached if page is not None else False,
    )


CACHE_CONTROL_IMMUTABLE = {"Cache-Control": "public, max-age=2592000, immutable"}
CACHE_CONTROL_IMMUTABLE_VARY = {
    "Cache-Control": "public, max-age=2592000, immutable",
    "Vary": "Accept",
}


def _client_accepts_webp(request: Request, ext: str | None = None) -> bool:
    if ext and ext.lower() == "webp":
        return True
    accept = request.headers.get("accept", "")
    return "image/webp" in accept


@app.get("/api/library/{source}/{source_id}/pages/{index}/file")
@app.get("/api/library/{source}/{source_id}/pages/{index}/file.{ext}")
def page_file(source: str, source_id: str, index: int, request: Request, ext: str | None = None) -> FileResponse:
    # Note: `ext` is bound by route pattern for CDN cache recognition; media_type is inferred from on-disk file.
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
@app.get("/api/library/{source}/{source_id}/pages/{index}/thumbnail.{ext}")
def page_thumbnail(source: str, source_id: str, index: int, request: Request, ext: str | None = None) -> FileResponse:
    """Lightweight JPEG for the detail-page page-index grid (`ext` bound for CDN caching)."""
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


def _serve_negotiated_image(
    *,
    source: str,
    source_id: str,
    wants_webp: bool,
    get_path: Callable[[str], Path],
    generate_image: Callable[[FetchedComic | None, str], Path],
    error_subject: str = "封面",
) -> FileResponse:
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


@app.get("/api/library/{source}/{source_id}/covers/{index}/file")
@app.get("/api/library/{source}/{source_id}/covers/{index}/file.{ext}")
def cover_file(
    source: str,
    source_id: str,
    index: int,
    request: Request,
    v: str | None = None,
    ext: str | None = None,
    w: int | None = None,
) -> FileResponse:
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


@app.get("/api/library/{source}/{source_id}/chapters/{chapter_id}/cover")
@app.get("/api/library/{source}/{source_id}/chapters/{chapter_id}/cover.{ext}")
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
    if meta.custom_pages:
        job["status"] = "done"
        job["prefetched"] = meta.page_count
        job["total"] = meta.page_count
        return

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
    broadcast_event(
        "library_changed",
        {"action": "cache_complete", "source": fetched.meta.source, "source_id": fetched.meta.source_id, "timestamp": time.time()},
    )


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
    import mimetypes
    from fastapi.staticfiles import StaticFiles
    from starlette.exceptions import HTTPException

    mimetypes.add_type("application/manifest+json", ".webmanifest")

    class SPAStaticFiles(StaticFiles):
        """SPA-aware static file handler: falls back to index.html for client routes on 404."""

        async def get_response(self, path: str, scope):
            try:
                response = await super().get_response(path, scope)
            except HTTPException as ex:
                if ex.status_code == 404:
                    filename = Path(path).name
                    # If target has a file extension (e.g. .js, .png, .json), it is a missing static file -> keep 404
                    is_file_request = "." in filename and not filename.startswith(".")
                    if not is_file_request:
                        response = await super().get_response("index.html", scope)
                        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
                        return response
                raise

            clean_path = path.strip("/")
            if clean_path in ("", "index.html", "sw.js", "registerSW.js", "manifest.webmanifest"):
                response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            elif clean_path.startswith("assets/") or clean_path.startswith("workbox-"):
                response.headers["Cache-Control"] = "public, max-age=31536000, immutable"

            if clean_path == "sw.js":
                response.headers["Service-Worker-Allowed"] = "/"

            if clean_path == "manifest.webmanifest":
                response.headers["Access-Control-Allow-Origin"] = "*"
                response.headers["Content-Type"] = "application/manifest+json"

            return response

    app.mount(
        "/",
        SPAStaticFiles(directory=str(_DIST_DIR), html=True),
        name="spa",
    )

