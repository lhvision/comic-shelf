"""FastAPI application entry point for Paper Room (纸间).

Assembles modular routers, security middleware, and SPA static hosting.
"""
from __future__ import annotations

import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from .abuse import check_guest_rate_limit
from .auth import (
    can_read,
    check_hotlink_protection,
    get_user_context,
    is_curator,
    is_guest,
)
from .config import ENABLE_DOCS, LIBRARY_DIR
from .db import (
    delete_comic_index,
    get_all_indexed_mtimes,
    get_user_favorites,
    init_db,
    migrate_legacy_favorites,
    upsert_comic_index,
)
from .events import broadcast_event, router as events_router, shutdown_events
from .imsearch import check_imsearch_status, search_imsearch
from .jobs import start_job
from .providers import get_provider
from .routers import (
    auth_router,
    chapters_router,
    library_router,
    local_comic_router,
    media_router,
    search_router,
    system_router,
)
from .routers.auth import (
    auth_claim,
    auth_login,
    auth_logout,
    auth_status,
    curator_create_pass,
    curator_delete_pass,
    curator_delete_pass_device,
    curator_list_passes,
    curator_update_pass,
)
from .routers.chapters import (
    cache_chapter,
    chapter_cache_progress,
    chapter_cover,
    delete_chapter,
    update_chapter_title,
)
from .routers.common import (
    _client_accepts_webp,
    _guess_media_type,
    _prefetch_worker,
    _require_known_source,
    _require_meta,
    _serve_negotiated_image,
    store,
)
from .routers.library import (
    comic_detail,
    delete_comic,
    discovery_ranking,
    get_reading_progress_api,
    import_comic,
    library,
    library_facets,
    save_reading_progress_api,
    set_favorite,
    update_comic_metadata,
)
from .routers.local_comic import (
    append_comic,
    create_local_comic,
    import_local_path,
    replace_comic_pages,
    replace_comic_pages_from_path,
    upload_comic_pages,
)
from .routers.media import (
    cache_all,
    cache_job,
    cache_progress,
    cover_file,
    page_file,
    page_info,
    page_thumbnail,
)
from .routers.search import (
    image_search,
    image_search_status,
    search_dialogue_endpoint,
    sync_ocr_endpoint,
)
from .storage import ComicStore

logger = logging.getLogger(__name__)


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


def sync_library_index(store: ComicStore) -> None:
    """Syncs existing album.json files on disk into comics_index if missing or modified."""
    try:
        if not store.root.exists():
            return
        existing_mtimes = get_all_indexed_mtimes()
        disk_keys: set[tuple[str, str]] = set()

        for source_dir in store.root.iterdir():
            if not source_dir.is_dir():
                continue
            for comic_dir in source_dir.iterdir():
                if not comic_dir.is_dir():
                    continue
                source, source_id = source_dir.name, comic_dir.name
                disk_keys.add((source, source_id))
                album_path = store.album_path(source, source_id)
                if not album_path.exists():
                    continue
                try:
                    mtime = album_path.stat().st_mtime
                except Exception:
                    mtime = 0.0

                if (source, source_id) in existing_mtimes and existing_mtimes[(source, source_id)] == mtime:
                    continue

                meta = store.load_meta(source, source_id)
                if meta is None:
                    continue

                cached_pages = store.cached_page_count(meta)
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
                })

        for source, source_id in set(existing_mtimes.keys()) - disk_keys:
            delete_comic_index(source, source_id)
    except Exception as exc:
        logger.warning("sync_library_index error: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_db()
        _migrate_existing_favorites_to_db()
        sync_library_index(store)
        store._cleanup_staged_pdfs(max_age_seconds=0)
    except Exception as exc:
        logger.warning("Startup initialization error: %s", exc)
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

# ----------------------------------------------------------------------
# Register modular routers
# ----------------------------------------------------------------------
app.include_router(events_router)
app.include_router(auth_router)
app.include_router(system_router)
app.include_router(library_router)
app.include_router(chapters_router)
app.include_router(local_comic_router)
app.include_router(media_router)
app.include_router(search_router)

# ----------------------------------------------------------------------
# Middlewares
# ----------------------------------------------------------------------
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

        # Rate limiting for guest readers on reading page binary endpoints (180 P/min + 100 P burst)
        # Note: /cover is excluded to prevent bookshelf grid loading from false-positive rate limiting
        if clean_stem.endswith(("/file", "/thumbnail")):
            _uid, _name, role = get_user_context(request)
            if role == "guest" and _uid.startswith("guest:"):
                try:
                    pass_id_val = int(_uid.split(":", 1)[1])
                    if not check_guest_rate_limit(pass_id_val):
                        return JSONResponse(
                            status_code=429,
                            content={"detail": "阅读翻页速率异常（超过 180 页/分钟），请稍憩数秒"},
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


# ----------------------------------------------------------------------
# SPA Static file mounting (All-in-one / NAS single-container deployment)
# ----------------------------------------------------------------------
import mimetypes
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.staticfiles import StaticFiles

mimetypes.add_type("application/manifest+json", ".webmanifest")


class SPAStaticFiles(StaticFiles):
    """SPA-aware static file handler: falls back to index.html for client routes on 404."""

    async def get_response(self, path: str, scope):
        try:
            response = await super().get_response(path, scope)
        except (HTTPException, StarletteHTTPException) as ex:
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


def _resolve_dist_dir() -> Path:
    env_dir = os.getenv("COMIC_SHELF_STATIC_DIR")
    if env_dir:
        return Path(env_dir)
    # Check candidate directories in order:
    # 1. Monorepo root dist (local dev: backend/app/main.py -> ../../dist)
    # 2. Container app dist (Dockerfile: /app/app/main.py -> ../dist -> /app/dist)
    # 3. Current working directory ./dist
    candidates = [
        Path(__file__).resolve().parents[2] / "dist",
        Path(__file__).resolve().parents[1] / "dist",
        Path.cwd() / "dist",
    ]
    for cand in candidates:
        if cand.exists() and (cand / "index.html").exists():
            return cand
    return candidates[0]


_DIST_DIR = _resolve_dist_dir()

if _DIST_DIR.exists() and (_DIST_DIR / "index.html").exists():
    app.mount(
        "/",
        SPAStaticFiles(directory=str(_DIST_DIR), html=True),
        name="spa",
    )


# Re-export public symbols for backward-compatibility with tests and external consumers
__all__ = [
    "app",
    "auth_and_security_middleware",
    "auth_claim",
    "auth_login",
    "auth_logout",
    "auth_status",
    "broadcast_event",
    "cache_all",
    "cache_chapter",
    "cache_job",
    "cache_progress",
    "chapter_cache_progress",
    "chapter_cover",
    "check_imsearch_status",
    "comic_detail",
    "cover_file",
    "create_local_comic",
    "curator_create_pass",
    "curator_delete_pass",
    "curator_delete_pass_device",
    "curator_list_passes",
    "curator_update_pass",
    "delete_chapter",
    "delete_comic",
    "discovery_ranking",
    "get_provider",
    "get_reading_progress_api",
    "image_search",
    "image_search_status",
    "import_comic",
    "import_local_path",
    "library",
    "library_facets",
    "page_file",
    "page_info",
    "page_thumbnail",
    "replace_comic_pages",
    "replace_comic_pages_from_path",
    "save_reading_progress_api",
    "search_dialogue_endpoint",
    "search_imsearch",
    "set_favorite",
    "SPAStaticFiles",
    "start_job",
    "store",
    "sync_library_index",
    "sync_ocr_endpoint",
    "update_chapter_title",
    "update_comic_metadata",
    "upload_comic_pages",
    "_client_accepts_webp",
    "_guess_media_type",
    "_prefetch_worker",
    "_require_known_source",
    "_require_meta",
    "_resolve_dist_dir",
    "_serve_negotiated_image",
]
