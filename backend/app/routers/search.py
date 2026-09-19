"""Visual image similarity search, FTS5 dialogue full-text search, and OCR sync router."""
from __future__ import annotations

import asyncio
import secrets
from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile

from ..auth import can_read, is_curator, is_machine, require_curator
from ..db import search_dialogues, sync_comic_dialogues
from ..imsearch import check_imsearch_status, search_imsearch
from ..models import (
    DialogueSearchResponse,
    ImageSearchItem,
    ImageSearchStatusResponse,
    OcrSyncResponse,
)
from .common import _require_known_source, store

router = APIRouter(tags=["search"])


@router.get("/api/search/image/status", response_model=ImageSearchStatusResponse)
def image_search_status() -> ImageSearchStatusResponse:
    """Check availability of the imsearch sidecar container."""
    status = check_imsearch_status()
    return ImageSearchStatusResponse(**status)


@router.post("/api/search/image", response_model=list[ImageSearchItem])
async def image_search(request: Request, file: UploadFile = File(...)) -> list[ImageSearchItem]:
    """Perform visual search by uploading a screenshot or cropped image."""
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="上传图片不能为空")
    results = await asyncio.to_thread(search_imsearch, content, filename=file.filename or "query.jpg")
    filtered: list[ImageSearchItem] = []
    is_cur = is_curator(request)
    for r in results:
        m = store.load_meta(r.source, r.source_id)
        if m is not None:
            if is_cur or not getattr(m, "hidden_from_guest", False):
                filtered.append(r)
    return filtered


@router.get("/api/search/dialogue", response_model=DialogueSearchResponse)
def search_dialogue_endpoint(
    request: Request,
    q: str = Query(default="", max_length=200, description="搜索对白台词关键词"),
    source: str | None = Query(default=None, description="来源过滤 (jm, picacg, local)"),
    limit: int = Query(default=20, ge=1, le=100, description="返回结果上限"),
) -> DialogueSearchResponse:
    """基于 SQLite FTS5 对白全文检索漫画，支持简繁双向互通归一化与气泡坐标投影。"""
    if not can_read(request):
        raise HTTPException(status_code=401, detail="未授权访问，需要提供有效的通行口令")
    is_guest_user = not is_curator(request)
    limit_val = limit if isinstance(limit, int) else 20
    source_val = source.strip() if isinstance(source, str) and source.strip() else None
    q_val = q if isinstance(q, str) else ""
    results = search_dialogues(query=q_val, source=source_val, limit=limit_val, is_guest=is_guest_user)
    return DialogueSearchResponse(results=results, total=len(results))


@router.post("/api/library/{source}/{source_id}/ocr/sync", response_model=OcrSyncResponse)
def sync_ocr_endpoint(
    source: str,
    source_id: str,
    request: Request,
) -> OcrSyncResponse:
    """增量同步漫画伴生 OCR 识别台词至 SQLite FTS5 全文索引。支持馆长口令或外部流水线专用 Machine Token。"""
    _require_known_source(source)
    if not (is_curator(request) or is_machine(request)):
        require_curator(request)

    count = sync_comic_dialogues(source, source_id)
    return OcrSyncResponse(ok=True, count=count)
