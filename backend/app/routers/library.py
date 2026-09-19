"""Library browsing, indexing, faceted search, discovery ranking, comic imports, and metadata management router."""
from __future__ import annotations

import hashlib
import json
import threading
import time
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, Response

from ..auth import get_current_user_id, is_curator, require_curator
from ..db import (
    get_library_facets,
    get_user_progress,
    is_user_favorite,
    purge_comic_db_records,
    query_library_index,
    set_user_favorite,
    set_user_progress,
)
from ..events import broadcast_event
from ..gate import get_guest_hide_new_comics
from ..jobs import cancel_job, start_job
from ..models import (
    ComicDetail,
    DeleteResponse,
    DiscoveryFeed,
    FavoriteRequest,
    FavoriteResponse,
    FetchedComic,
    ImportRequest,
    ImportResult,
    LibraryFacetsResponse,
    LibraryPageResponse,
    LibraryStats,
    LibrarySummary,
    MetadataUpdateRequest,
    ReadingProgressRequest,
    ReadingProgressResponse,
)
from ..providers import get_provider
from .common import _prefetch_worker, _require_known_source, _require_meta, store

router = APIRouter(tags=["library"])

SUPPORTED_DISCOVERY_SOURCES = ("jm", "picacg")
DISCOVERY_SOURCE_PATTERN = f"^({'|'.join(SUPPORTED_DISCOVERY_SOURCES)})$"


def _row_to_library_summary(row: dict[str, Any]) -> LibrarySummary:
    """Transforms an indexed SQLite row into a strongly typed LibrarySummary schema."""
    source = row["source"]
    source_id = row["source_id"]
    page_count = int(row["page_count"])
    cover_count = int(row["cover_count"])
    try:
        cover_indices = json.loads(row.get("cover_indices_json") or "[]")
    except Exception:
        cover_indices = []
    updated_at = row.get("updated_at") or ""

    count = len(cover_indices) if cover_indices else min(cover_count, page_count)
    v_tag = ""
    if updated_at:
        v_tag = f"?v={hashlib.md5(updated_at.encode()).hexdigest()[:8]}"
    cover_paths = [
        f"/api/library/{source}/{source_id}/covers/{index}/file.webp{v_tag}"
        for index in range(1, max(1, count) + 1)
    ] if page_count > 0 else []

    try:
        authors = json.loads(row["authors_json"])
    except Exception:
        authors = []
    try:
        works = json.loads(row["works_json"])
    except Exception:
        works = []
    try:
        actors = json.loads(row["actors_json"])
    except Exception:
        actors = []
    try:
        tags = json.loads(row["tags_json"])
    except Exception:
        tags = []
    try:
        chapter_titles = json.loads(row["chapter_titles_json"])
    except Exception:
        chapter_titles = []

    return LibrarySummary(
        source=source,
        source_id=source_id,
        display_id=row["display_id"],
        title=row["title"],
        authors=authors,
        works=works,
        actors=actors,
        tags=tags,
        chapter_titles=chapter_titles,
        page_count=page_count,
        cached_pages=int(row["cached_pages"]),
        cover_count=cover_count,
        views=str(row["views"]),
        likes=str(row["likes"]),
        uploaded_at=str(row.get("uploaded_at") or ""),
        published_at=str(row.get("published_at") or ""),
        updated_at=updated_at,
        imported_at=str(row.get("imported_at") or ""),
        hidden_from_guest=bool(row["hidden_from_guest"]),
        favorite=bool(row["is_favorite"]),
        last_page=int(row["last_page"]),
        cover_paths=cover_paths,
    )


@router.get("/api/library", response_model=LibraryPageResponse)
def library(
    request: Request,
    page: int = Query(default=1, ge=1, description="当前页码"),
    page_size: int = Query(default=24, ge=1, le=120, description="每页条数"),
    status: str = Query(default="all", pattern="^(all|reading|completed|unread)$", description="阅读状态"),
    favorite: bool = Query(default=False, description="只看喜欢"),
    source: str | None = Query(default=None, description="来源过滤 (jm, picacg, local)"),
    q: str | None = Query(default=None, description="标题/作者/标签过滤"),
    tag: str | None = Query(default=None, description="单标签过滤"),
    tags: str | None = Query(default=None, description="逗号分隔的多标签交集过滤（最多支持 5 个）"),
    sort: str = Query(default="recent", pattern="^(recent|title|pages|cached)$", description="排序方式"),
    ids: str | None = Query(default=None, description="指定逗号分隔的 source:source_id 列表，精准获取目标漫画"),
    offset: int | None = Query(default=None, ge=0, description="显式偏移量（支持平滑流式追加）"),
) -> LibraryPageResponse:
    """Queries indexed library items with multi-dimensional filtering, pagination, and sorting."""
    user_id = get_current_user_id(request)
    is_cur = is_curator(request)
    rows, total = query_library_index(
        user_id=user_id,
        is_curator=is_cur,
        page=page,
        page_size=page_size,
        status=status,
        favorite=favorite,
        source=source,
        q=q,
        tag=tag,
        tags=tags,
        sort=sort,
        ids=ids,
        offset=offset,
    )
    items = [_row_to_library_summary(r) for r in rows]
    actual_offset = offset if offset is not None else (page - 1) * page_size
    has_more = (actual_offset + len(items)) < total
    return LibraryPageResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_more=has_more,
    )


@router.get("/api/library/facets", response_model=LibraryFacetsResponse)
def library_facets(
    request: Request,
    source: str | None = Query(default=None, description="来源过滤"),
) -> LibraryFacetsResponse:
    """Aggregates bookshelf facets, reading status statistics, and top tags."""
    is_cur = is_curator(request)
    data = get_library_facets(is_curator=is_cur, source=source)
    return LibraryFacetsResponse(
        stats=LibraryStats(**data["stats"]),
        top_tags=data["top_tags"],
    )


@router.get("/api/discovery/ranking", response_model=DiscoveryFeed)
def discovery_ranking(
    request: Request,
    source: str = Query(default="jm", pattern=DISCOVERY_SOURCE_PATTERN),
    timeframe: str = Query(default="week", pattern="^(week|month|day)$"),
    refresh: bool = False,
) -> DiscoveryFeed:
    """Fetches trending or popular comic rankings from upstream providers (curator only)."""
    require_curator(request)

    now_ts = time.time()
    cached_feed = store.load_discovery_feed(timeframe, source=source)
    feed: DiscoveryFeed | None = None

    if not refresh and cached_feed is not None:
        try:
            feed_dt = datetime.strptime(cached_feed.updated_at, "%Y-%m-%d %H:%M:%S")
            if now_ts - feed_dt.timestamp() < 12 * 3600:
                feed = cached_feed
        except Exception:
            feed = cached_feed

    if feed is None:
        provider = get_provider(source)
        try:
            items = provider.fetch_ranking(timeframe=timeframe)
            feed = DiscoveryFeed(
                source=source,
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


# In-memory LRU cache for discovery covers (zero disk write under Scheme A)
# Key: f"{source}:{source_id}" -> (timestamp: float, content: bytes, media_type: str)
_discovery_cover_cache: dict[str, tuple[float, bytes, str]] = {}
_discovery_cover_lock = threading.Lock()
_DISCOVERY_COVER_CACHE_MAX = 100
_DISCOVERY_COVER_TTL = 3600.0  # 1 hour


def _sniff_image_media_type(data: bytes) -> str:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
        return "image/gif"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


@router.get("/api/discovery/cover")
def discovery_cover(
    request: Request,
    source: str = Query(default="jm", pattern=DISCOVERY_SOURCE_PATTERN),
    source_id: str = Query(...),
    cover_url: str | None = None,
) -> Response:
    """Proxies and caches remote discovery cover images in memory only (curator only).
    Zero disk writes under Scheme A (on-demand viewing).
    """
    require_curator(request)

    cache_key = f"{source}:{source_id}"
    now = time.time()

    with _discovery_cover_lock:
        if cache_key in _discovery_cover_cache:
            cached_ts, cached_data, cached_type = _discovery_cover_cache[cache_key]
            if now - cached_ts < _DISCOVERY_COVER_TTL:
                return Response(
                    content=cached_data,
                    media_type=cached_type,
                    headers={
                        "Cache-Control": "private, max-age=3600",
                        "X-Discovery-Cover-Cache": "HIT",
                    },
                )
            else:
                _discovery_cover_cache.pop(cache_key, None)

    # Resolve target cover_url if not explicitly provided
    resolved_cover_url = cover_url.strip() if isinstance(cover_url, str) else ""
    if not resolved_cover_url:
        for tf in ("week", "month", "day"):
            cached_feed = store.load_discovery_feed(tf, source=source)
            if cached_feed:
                for item in cached_feed.items:
                    if item.source_id == source_id and item.cover_url:
                        resolved_cover_url = item.cover_url
                        break
            if resolved_cover_url:
                break

    if not resolved_cover_url:
        raise HTTPException(status_code=404, detail="未找到该条目的封面图片地址")

    provider = get_provider(source)
    if not hasattr(provider, "download_cover_by_url"):
        raise HTTPException(status_code=400, detail=f"图源 {source} 不支持直接封面代理")

    try:
        data = provider.download_cover_by_url(resolved_cover_url)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"拉取封面失败: {exc}") from exc

    if not data:
        raise HTTPException(status_code=404, detail="无法下载该漫画封面或封面已失效")

    media_type = _sniff_image_media_type(data)

    with _discovery_cover_lock:
        if len(_discovery_cover_cache) >= _DISCOVERY_COVER_CACHE_MAX:
            oldest_key = next(iter(_discovery_cover_cache))
            _discovery_cover_cache.pop(oldest_key, None)
        _discovery_cover_cache[cache_key] = (now, data, media_type)

    return Response(
        content=data,
        media_type=media_type,
        headers={
            "Cache-Control": "private, max-age=3600",
            "X-Discovery-Cover-Cache": "MISS",
        },
    )


@router.post("/api/library/import", response_model=ImportResult)
def import_comic(req: ImportRequest) -> ImportResult:
    """Imports remote comic metadata into local library and initiates background page caching."""
    provider = get_provider(req.source)
    try:
        source_id = provider.normalize_id(req.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not req.refresh:
        cached = store.load_fetched(req.source, source_id)
        # Self-healing: if cached comic has 0 pages (broken historical record), bypass cache and re-fetch
        if cached is not None and cached.meta.page_count > 0:
            return ImportResult(meta=cached.meta, from_cache=True, prefetched=0, warnings=[])

    # Metadata + URL discovery happen on the request thread: fast and necessary
    # for a useful response. Page/cover downloads are the slow part, so they're
    # pushed to a background daemon thread and the UI polls cache_progress.
    existing: FetchedComic | None = None
    if req.refresh:
        cached_bundle = store.load_fetched(req.source, source_id)
        if cached_bundle is not None and cached_bundle.meta.page_count > 0:
            if cached_bundle.meta.custom_pages:
                raise HTTPException(
                    status_code=400,
                    detail="该漫画画页已由馆长重新装订保护，禁止远端重刷覆盖。如需更新元数据，请在详情页直接编辑资料。",
                )
            existing = cached_bundle
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


@router.get("/api/library/{source}/{source_id}", response_model=ComicDetail)
def comic_detail(source: str, source_id: str, request: Request) -> ComicDetail:
    """Returns comprehensive comic details, chapter index, page list, and user favorite status."""
    meta = _require_meta(source, source_id, request)
    detail = store.detail(meta)
    user_id = get_current_user_id(request)
    detail.meta.favorite = is_user_favorite(user_id, source, source_id)
    return detail


@router.delete("/api/library/{source}/{source_id}", response_model=DeleteResponse)
def delete_comic(source: str, source_id: str) -> DeleteResponse:
    """Permanently deletes a comic from the local library, purging FTS dialogues, index, and cached images."""
    _require_known_source(source)
    cancel_job(source, source_id)
    purge_comic_db_records(source, source_id)
    ok = store.delete(source, source_id)
    if ok:
        broadcast_event(
            "library_changed",
            {"action": "delete", "source": source, "source_id": source_id, "timestamp": time.time()},
        )
    return DeleteResponse(ok=ok, source=source, source_id=source_id)


@router.patch("/api/library/{source}/{source_id}/metadata", response_model=ComicDetail)
def update_comic_metadata(source: str, source_id: str, req: MetadataUpdateRequest) -> ComicDetail:
    """Updates editable metadata fields (title, authors, tags, works, actors) of a comic."""
    _require_known_source(source)
    updates = req.model_dump(exclude_unset=True)
    meta = store.update_metadata(source, source_id, updates)
    broadcast_event(
        "library_changed",
        {"action": "update_metadata", "source": source, "source_id": source_id, "timestamp": time.time()},
    )
    return store.detail(meta)


@router.patch("/api/library/{source}/{source_id}/favorite", response_model=FavoriteResponse)
def set_favorite(source: str, source_id: str, req: FavoriteRequest, request: Request) -> FavoriteResponse:
    """Toggles or updates the favorite status of a comic for the authenticated user."""
    _require_meta(source, source_id, request)
    user_id = get_current_user_id(request)
    new_fav = set_user_favorite(user_id, source, source_id, req.favorite)
    return FavoriteResponse(ok=True, favorite=new_fav)


@router.get("/api/library/{source}/{source_id}/progress", response_model=ReadingProgressResponse)
def get_reading_progress_api(source: str, source_id: str, request: Request) -> ReadingProgressResponse:
    """Fetches current user's reading progress for a given comic."""
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


@router.put("/api/library/{source}/{source_id}/progress", response_model=ReadingProgressResponse)
def save_reading_progress_api(
    source: str,
    source_id: str,
    req: ReadingProgressRequest,
    request: Request,
) -> ReadingProgressResponse:
    """Records updated reading progress for the authenticated user."""
    meta = _require_meta(source, source_id, request)
    user_id = get_current_user_id(request)
    prog = set_user_progress(user_id, source, source_id, req.page, req.total_pages or meta.page_count)
    return ReadingProgressResponse(ok=True, **prog)
