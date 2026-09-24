"""Visual image similarity search, FTS5 dialogue full-text search, and OCR sync router."""
from __future__ import annotations

import asyncio
import secrets
from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile

from ..auth import can_read, get_current_user_id, is_curator, is_machine, require_curator
from ..db import (
    STORY_CONTEXT_MAX_LINES,
    get_story_context,
    rebuild_dialogue_vectors,
    search_dialogues,
    search_dialogues_semantic,
    sync_comic_dialogues,
)
from ..imsearch import check_imsearch_status, search_imsearch
from ..models import (
    DialogueSearchResponse,
    DialogueVectorsResponse,
    ImageSearchItem,
    ImageSearchStatusResponse,
    OcrSyncResponse,
    SemanticDialogueResponse,
    StoryContextResponse,
)
from .common import _require_known_source, _require_meta, store

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
    """基于 SQLite FTS5 对白全文检索漫画，支持简繁双向互通归一化与气泡坐标投影。

    排序带本人视角（收藏/读过的排前面），所以这里必须把 user_id 传下去；访客与馆长的差别只影响
    顺序，命中页集合与 `bubble_count` 不受身份影响（`hidden_from_guest` 的可见性过滤除外）。
    正因为这份响应等于一次阅读偏好投影，它不可被共享缓存复用——缓存头由
    `auth_and_security_middleware` 统一给所有已过鉴权的 `/api` 响应补 `no-store`。
    """
    if not can_read(request):
        raise HTTPException(status_code=401, detail="未授权访问，需要提供有效的通行口令")
    is_guest_user = not is_curator(request)
    limit_val = limit if isinstance(limit, int) else 20
    source_val = source.strip() if isinstance(source, str) and source.strip() else None
    q_val = q if isinstance(q, str) else ""
    results = search_dialogues(
        query=q_val,
        source=source_val,
        limit=limit_val,
        is_guest=is_guest_user,
        user_id=get_current_user_id(request),
    )
    return DialogueSearchResponse(results=results, total=len(results))


@router.get("/api/search/dialogue-semantic", response_model=SemanticDialogueResponse)
def search_dialogue_semantic_endpoint(
    request: Request,
    q: str = Query(default="", max_length=200, description="想要的那句「意思」，不必与原文同字面"),
    source: str | None = Query(default=None, description="来源过滤 (jm, picacg, local)"),
    limit: int = Query(default=20, ge=1, le=100, description="返回结果上限"),
) -> SemanticDialogueResponse:
    """按意思找台词：字面完全不通（「告白」↔「我喜欢你」）时的第二条腿。

    这是**独立出口**，不并进 `/api/search/dialogue`：那条的排序里掺了本人视角（收藏、读过），
    且 `rank_score` 是池内归一，两者混进一次返回会让前端与 agent 分不清"这句像"还是"这本你熟"。
    需要字面命中就用那个，需要换句话也说得出就用这个。

    空结果必须能分辨原因，所以响应带 `available`/`reason`：
    `encoder_unavailable` = 这台机器没放语义模型（关键词检索不受影响）、
    `vectors_missing` / `dim_mismatch` = 向量库落后或换过模型，需要调一次重建接口、
    `query_too_short` = 问题不足 2 个字（语义腿是好的）。
    """
    if not can_read(request):
        raise HTTPException(status_code=401, detail="未授权访问，需要提供有效的通行口令")
    out = search_dialogues_semantic(
        query=q if isinstance(q, str) else "",
        source=source.strip() if isinstance(source, str) and source.strip() else None,
        limit=limit if isinstance(limit, int) else 20,
        is_guest=not is_curator(request),
        user_id=get_current_user_id(request),
    )
    return SemanticDialogueResponse(total=len(out["results"]), **out)


@router.post("/api/search/dialogue-vectors/rebuild", response_model=DialogueVectorsResponse)
def rebuild_dialogue_vectors_endpoint(request: Request) -> DialogueVectorsResponse:
    """全库重编台词向量（整库在 CPU 上要跑几十秒）。只对馆长开放：机器密钥的这个 POST 在全站中间件就被 403 挡下。

    日常不需要手动调：`*/ocr/sync` 每同步一本就顺手重编那一本。要跑它的只有两种情况——
    第一次装模型，以及换了模型（维度对不上，`reason` 会报 `dim_mismatch`）。
    """
    require_curator(request)
    status = rebuild_dialogue_vectors()
    return DialogueVectorsResponse(**status)


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


@router.get("/api/search/dialogue-context", response_model=StoryContextResponse)
def dialogue_context_endpoint(
    request: Request,
    source: str = Query(..., max_length=40, description="来源 (jm, picacg, local)"),
    source_id: str = Query(..., max_length=80, description="本子在本机的稳定 ID"),
    page_start: int = Query(1, ge=1, description="起始页（全书拍平后的全局页号，1 起）"),
    page_end: int = Query(..., ge=1, description="结束页（含）。跨度由 db 层夹到 200 页"),
    budget_lines: int = Query(
        120, ge=1, le=STORY_CONTEXT_MAX_LINES, description="台词行预算，撞顶回报 truncated"
    ),
) -> StoryContextResponse:
    """按页码区间导出原始台词流：不做关键词过滤、不带高亮态，按 (页号, 阅读顺序) 剧情原序返回。

    与 `/api/search/dialogue` 是同一份索引的两个出口，那个给人看（要 bm25 排序、要 `<mark>`、
    要压成 20 页），这个给取料用（要连续切片与原始 text）。因此只对馆长和 Machine Token 开放：
    一次能批量拉走整本对白，不该出现在访客态。机器密钥与访客一样看不到隐藏本（与它在其他接口上的
    口径一致）；只有馆长能取隐藏本。书不存在或对调用者不可见一律 404。
    """
    if not (is_curator(request) or is_machine(request)):
        require_curator(request)
    meta = _require_meta(source, source_id, request)

    ctx = get_story_context(source, source_id, page_start, page_end, budget_lines=budget_lines)
    return StoryContextResponse(source=source, source_id=source_id, title=meta.title, **ctx)
