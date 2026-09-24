"""Model Context Protocol (MCP) Server Router for Paper Room (纸间).

Implements the Model Context Protocol over Server-Sent Events (SSE) and direct JSON-RPC 2.0,
exposing atomic data tools, searchable resources, and prompt templates to AI Agents
(Claude Desktop, Antigravity, Cursor, Feishu Bot, etc.).
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import secrets
from typing import Any, AsyncGenerator, Callable
from urllib.parse import quote, urlencode

from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse

from ..abuse import (
    is_ip_login_locked,
    record_ip_login_failure_and_check_lock,
)
from ..auth import extract_token, get_client_ip, is_curator
from ..config import MCP_TOKEN
from ..db import (
    MAX_PAGE_BOXES,
    create_direct_pass,
    get_library_facets,
    get_story_context,
    query_library_index,
    search_dialogues,
    search_dialogues_semantic,
)
from ..imsearch import check_imsearch_status, search_imsearch
from ..providers import provider_list
from .common import store

logger = logging.getLogger("paper_room.mcp")

router = APIRouter(tags=["mcp"])

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "paper-room-mcp"
SERVER_VERSION = "0.1.0"
_MAX_MCP_SESSIONS = 50
# 台词两条腿的查询长度上限，与 REST 出口的 `q` 一致
_MAX_QUERY_CHARS = 200

# ----------------------------------------------------------------------
# In-memory SSE session queues for bidirectional MCP over SSE
# ----------------------------------------------------------------------
_mcp_sessions: dict[str, asyncio.Queue[str | None]] = {}
_sessions_lock = asyncio.Lock()


# ----------------------------------------------------------------------
# MCP Tools Catalog Definition
# ----------------------------------------------------------------------
MCP_TOOLS: list[dict[str, Any]] = [
    {
        "name": "search_by_image",
        "description": "使用图片的 Base64 编码在纸间漫画全库中进行视觉特征比对与局部搜图（ORB 特征匹配），精准召回所属漫画、页码与相似度分数。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "image_base64": {
                    "type": "string",
                    "description": "待搜索图片的 Base64 编码字符串（支持 data:image/... 前缀或纯 base64 数据）",
                },
                "limit": {
                    "type": "integer",
                    "description": "返回的最大候选匹配数量（1~20，默认 5）",
                    "default": 5,
                },
            },
            "required": ["image_base64"],
        },
    },
    {
        "name": "search_by_dialogue",
        "description": (
            "基于 SQLite FTS5 (Trigram 倒排索引) 在全库漫画分镜中全文检索台词对白与名场面，返回命中漫画、"
            "画页页码、对白气泡归一化坐标与高亮上下文。排序是相关度（`rank_score`，本次候选池内 0..1 归一）"
            "叠加馆长本人的收藏/完读率/最近阅读/站内热度后的结果——**顺序带个人视角，命中数不带**；"
            "要按纯文本相关度取料，请按 `rank_score` 自行重排。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "检索的台词或对白关键词（支持中日双语及简繁自动归一化）",
                },
                "source": {
                    "type": "string",
                    "description": "可选限定特定图源平台（如 'jm' | 'picacg' | 'local'）",
                },
                "limit": {
                    "type": "integer",
                    "description": "返回的最大匹配条数（1~50，默认 5）",
                    "default": 5,
                },
            },
            "required": ["text"],
        },
    },
    {
        "name": "search_by_meaning",
        "description": (
            "按「意思」找台词：字面完全不通时的第二条腿（搜「告白」能拿到「我喜欢你」、搜「脸红」能拿到"
            "「满脸通红」）。一页一条，取该页意思最近的那个气泡，带页码与归一化坐标，可直接拿去阅读器描边。"
            "分数是 `similarity`（余弦相似度，-1..1），**只在同一次查询的结果之间比高低**：真命中与噪声的"
            "分数区间重叠，没有可用的绝对阈值，能检索时总会返回最近的若干条，相关与否要读台词自己判断。"
            "它与 search_by_dialogue 的 `rank_score` 不是一个口径，不要混排、不要互相当阈值用。"
            "字面命中优先用 search_by_dialogue（更快更准），本工具用于换种说法也说得出、或需要近似表达素材的场景。"
            "`reason` 非空表示这次没有真正检索：`query_too_short` 换个完整点的说法再查；"
            "`encoder_unavailable` / `vectors_missing` / `dim_mismatch`（此时 `available=false`）是环境状态，重试无用。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "meaning": {
                    "type": "string",
                    "description": "想要表达的意思或场景，例如「告白」「被打败后认输」「久别重逢」",
                },
                "source": {
                    "type": "string",
                    "description": "可选限定特定图源平台（如 'jm' | 'picacg' | 'local'）",
                },
                "limit": {
                    "type": "integer",
                    "description": "返回的最大条数（1~50，默认 5）",
                    "default": 5,
                },
            },
            "required": ["meaning"],
        },
    },
    {
        "name": "query_shelf",
        "description": "多维度检索与筛选纸间书架藏书，支持标题/作者关键词、题材标签、图源平台、阅读进度与排序规则。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": "标题、作者、作品或角色检索词",
                },
                "tag": {
                    "type": "string",
                    "description": "题材或分类标签（如 '纯爱', '全彩', '同人'）",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "多标签交集筛选列表（如 ['纯爱', '全彩']）",
                },
                "source": {
                    "type": "string",
                    "description": "图源平台过滤（如 'jm' | 'picacg' | 'local'）",
                },
                "status": {
                    "type": "string",
                    "enum": ["all", "reading", "completed", "unread"],
                    "description": "阅读进度筛选",
                    "default": "all",
                },
                "favorite": {
                    "type": "boolean",
                    "description": "是否仅查询已加红心收藏的作品",
                },
                "sort": {
                    "type": "string",
                    "enum": ["recent", "pages", "views", "likes", "alpha"],
                    "description": "排序方式（默认 recent 最新导入）",
                    "default": "recent",
                },
                "limit": {
                    "type": "integer",
                    "description": "每页返回藏书数量（1~50，默认 20）",
                    "default": 20,
                },
                "offset": {
                    "type": "integer",
                    "description": "分页偏移量（默认 0）",
                    "default": 0,
                },
            },
        },
    },
    {
        "name": "get_comic_detail",
        "description": "获取指定漫画作品的完整结构化数据，包含元数据、作者、标签、章节目录列表与全局画页总量。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "图源平台标识（如 'jm' | 'picacg' | 'local'）",
                },
                "source_id": {
                    "type": "string",
                    "description": "图源作品唯一 ID（如禁漫车号 '523607'）",
                },
            },
            "required": ["source", "source_id"],
        },
    },
    {
        "name": "recommend_unread",
        "description": "根据书架藏书与阅读状态，智能推荐读者尚未阅读的高分或热门漫画作品。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "推荐作品数量（1~20，默认 5）",
                    "default": 5,
                },
                "tag": {
                    "type": "string",
                    "description": "可选指定期望的题材标签",
                },
                "source": {
                    "type": "string",
                    "description": "可选限定图源平台",
                },
            },
        },
    },
    {
        "name": "create_direct_pass",
        "description": "为指定漫画签发单本沙箱临时直达阅读 Token 与链接（默认 2 小时有效），读者无需全站登录即可安全阅读该作品并精准直达指定页码。已标记「对访客隐藏」的作品会被拒绝签发，请勿重试。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "图源平台标识（如 'jm' | 'picacg' | 'local'）",
                },
                "source_id": {
                    "type": "string",
                    "description": "作品 ID",
                },
                "page_index": {
                    "type": "integer",
                    "description": "期望直达的画页页码（1-indexed，默认 1）",
                    "default": 1,
                },
                "ttl_seconds": {
                    "type": "integer",
                    "description": "有效秒数（默认 7200 即 2 小时，最长 7 天）",
                    "default": 7200,
                },
            },
            "required": ["source", "source_id"],
        },
    },
    {
        "name": "get_shelf_stats",
        "description": "获取纸间全站藏书的聚合统计信息（藏书总数、在读数、完读数、收藏数、总画页数、台词索引数及高频标签分布）。",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "get_story_context",
        "description": (
            "取料出口：按「作品 + 页码区间」拉取原始台词流，供漫画分镜、动漫脚本、游戏对话等下游"
            "生成管线使用。顺序严格按剧情推进（页码 + 页内阅读顺序），不做相关度排序，不带 <mark> "
            "展示态标签；行数由 budget_lines 预算决定，撞预算回报 truncated=true 供下游决定是否续取。"
            "入参不接受关键词（要按台词找本子请用 search_by_dialogue）。返回分两份：lines 交给模型、"
            "boxes 交给渲染层，靠 line_id 关联——气泡坐标是画上去用的，塞进 prompt 只会成为噪声。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "图源平台标识（如 'jm' | 'picacg' | 'local'）",
                },
                "source_id": {
                    "type": "string",
                    "description": "作品 ID（与 source 组成复合键，单独不唯一定位一本书）",
                },
                "page_start": {
                    "type": "integer",
                    "description": "起始全局页号（1-indexed，含）",
                },
                "page_end": {
                    "type": "integer",
                    "description": "结束全局页号（含）；单次最多跨 200 页",
                },
                "budget_lines": {
                    "type": "integer",
                    "description": "预算行数，本次最多返回多少条台词（默认 120，上限 400）",
                    "default": 120,
                },
            },
            "required": ["source", "source_id", "page_start", "page_end"],
        },
    },
]

# ----------------------------------------------------------------------
# MCP Resources Catalog Definition
# ----------------------------------------------------------------------
MCP_RESOURCES: list[dict[str, Any]] = [
    {
        "uri": "shelf://stats",
        "name": "书架藏书聚合统计概览",
        "description": "纸间藏书总量、画页总量、离线缓存进度及高频标签分布",
        "mimeType": "application/json",
    },
    {
        "uri": "shelf://providers",
        "name": "支持的漫画图源清单",
        "description": "支持的图源列表（禁漫天堂、哔咔漫画、本地自建等）",
        "mimeType": "application/json",
    },
    {
        "uri": "shelf://recent",
        "name": "最新入库漫画列表",
        "description": "最近收录入馆的前 20 部漫画藏书元数据",
        "mimeType": "application/json",
    },
]

# ----------------------------------------------------------------------
# MCP Prompts Catalog Definition
# ----------------------------------------------------------------------
MCP_PROMPTS: list[dict[str, Any]] = [
    {
        "name": "find_comic_by_scene",
        "description": "根据用户描述的名场景或名台词线索，联合搜图与台词检索定位漫画出处",
        "arguments": [
            {
                "name": "clue",
                "description": "场景描述或记忆中的台词片段",
                "required": True,
            }
        ],
    },
    {
        "name": "recommend_comic",
        "description": "根据用户的阅读口味与题材偏好淘选合胃口的藏书",
        "arguments": [
            {
                "name": "preference",
                "description": "用户的偏好描述（如 '纯爱 全彩' 或 '剧情反转'）",
                "required": False,
            }
        ],
    },
]


# ----------------------------------------------------------------------
# Tool Execution Registry & Modular Handlers
# ----------------------------------------------------------------------
def _tool_search_by_image(arguments: dict[str, Any]) -> dict[str, Any]:
    raw_b64 = str(arguments.get("image_base64", ""))
    if not raw_b64:
        raise ValueError("image_base64 不能为空")
    if "," in raw_b64:
        raw_b64 = raw_b64.split(",", 1)[1]
    try:
        img_bytes = base64.b64decode(raw_b64)
    except Exception as e:
        raise ValueError(f"Base64 解码失败: {e}")

    limit = int(arguments.get("limit", 5))
    raw_results = search_imsearch(img_bytes)

    hits = []
    for item in raw_results[:limit]:
        meta = store.load_meta(item.source, item.source_id)
        title = meta.title if meta else item.source_id
        authors = meta.authors if meta else []
        hits.append({
            "source": item.source,
            "source_id": item.source_id,
            "title": title,
            "authors": authors,
            "page_index": item.page_index,
            "is_cover": item.is_cover,
            "similarity_score": round(item.score, 4),
            "confidence_percent": f"{round(item.score * 100, 1)}%",
            "reader_url": f"/comic/{item.source}/{item.source_id}/read/{item.page_index}",
        })

    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps({
                    "total_matched": len(hits),
                    "hits": hits,
                }, ensure_ascii=False, indent=2),
            }
        ],
        "isError": False,
    }


def _bubble_query(d: dict[str, Any]) -> dict[str, str]:
    """把一页命中拼成阅读器认得的高亮参数。

    阅读器只解析 `bubble_box` / `bubble_boxes` / `bubble_text` / `highlight_bubble=1|true`；
    历史版本在这里拼的是 `?bubble=<气泡 id>`，数字 id 不被解析，等于签发了一个
    永远不高亮的直达链接。坐标必须与前端 useDialogueSearch 的编码逐字对齐。
    """
    def encode(box: list[float]) -> str:
        return ",".join(f"{float(v):.4f}" for v in box)

    query: dict[str, str] = {}
    box = d.get("box") or []
    if len(box) == 4:
        query["bubble_box"] = encode(box)
    others = [b for b in (d.get("other_boxes") or []) if isinstance(b, list) and len(b) == 4]
    if others:
        query["bubble_boxes"] = ";".join(encode(b) for b in others[: MAX_PAGE_BOXES - 1])
    if d.get("text"):
        query["bubble_text"] = str(d["text"])
    if query:
        query["highlight_bubble"] = "1"
    return query


def _tool_search_by_dialogue(arguments: dict[str, Any]) -> dict[str, Any]:
    text = str(arguments.get("text", "")).strip()
    if not text:
        raise ValueError("text 台词关键词不能为空")
    if len(text) > _MAX_QUERY_CHARS:
        raise ValueError(f"text 不能超过 {_MAX_QUERY_CHARS} 字")
    source = arguments.get("source")
    limit = max(1, min(int(arguments.get("limit", 5)), 50))

    diag_results = search_dialogues(query=text, source=source, limit=limit, is_guest=False, user_id="curator")
    hits = []
    for d in diag_results:
        query = _bubble_query(d)
        url = f"/comic/{d['source']}/{d['source_id']}/read/{d['page_index']}"
        if query:
            url = f"{url}?{urlencode(query)}"
        hits.append({
            "source": d["source"],
            "source_id": d["source_id"],
            "title": d.get("title", d["source_id"]),
            "authors": d.get("authors", []),
            "page_index": d["page_index"],
            "bubble_id": d.get("bubble_id"),
            # 检索单元是气泡、展示单元是页：一行代表一整页，同页命中数与同页其余命中气泡一并给出
            "bubble_count": d.get("bubble_count"),
            "text": d["text"],
            "snippet": d.get("snippet", d["text"]),
            "box": d.get("box", []),
            "other_boxes": d.get("other_boxes", []),
            "rank_score": d.get("rank_score", 0.0),
            "reader_url": url,
        })

    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps({
                    "query": text,
                    "total_matched": len(hits),
                    "hits": hits,
                }, ensure_ascii=False, indent=2),
            }
        ],
        "isError": False,
    }


def _tool_search_by_meaning(arguments: dict[str, Any]) -> dict[str, Any]:
    meaning = str(arguments.get("meaning", "")).strip()
    if not meaning:
        raise ValueError("meaning 语义描述不能为空")
    if len(meaning) > _MAX_QUERY_CHARS:
        raise ValueError(f"meaning 不能超过 {_MAX_QUERY_CHARS} 字")
    out = search_dialogues_semantic(
        query=meaning,
        source=arguments.get("source"),
        limit=max(1, min(int(arguments.get("limit", 5)), 50)),
        is_guest=False,
        user_id="curator",
    )
    payload = []
    for h in out["results"]:
        url = f"/comic/{h['source']}/{h['source_id']}/read/{h['page_index']}"
        query = _bubble_query(h)
        if query:
            url = f"{url}?{urlencode(query)}"
        payload.append({**h, "reader_url": url})
    body: dict[str, Any] = {
        "query": meaning,
        "available": out["available"],
        "reason": out["reason"],
        "total_matched": len(payload),
        "scoring": "similarity 为余弦相似度，-1..1，只在同一次查询内比高低，没有可用的绝对阈值；"
        "与 search_by_dialogue 的 rank_score 不同口径，禁止混排",
        "hits": payload,
    }
    if out["reason"]:
        # 没走检索时把原因讲成人话交回去：环境状态重试无用，该改走 search_by_dialogue；
        # 问题太短则是换个说法就能查，两种都不能让调用方误读成"库里没有"
        body["hint"] = {
            "encoder_unavailable": "本机未放置语义编码器模型，只有关键词检索可用",
            "vectors_missing": "模型已就绪但台词向量还没建，需要馆长调用 POST /api/search/dialogue-vectors/rebuild",
            "dim_mismatch": "台词向量是别的模型编的（维度不一致），需要馆长重建向量库",
            "query_too_short": "问题不足 2 个字，换一个完整点的说法再查",
        }.get(out["reason"], out["reason"])
    return {
        "content": [{"type": "text", "text": json.dumps(body, ensure_ascii=False, indent=2)}],
        "isError": False,
    }


def _tool_query_shelf(arguments: dict[str, Any]) -> dict[str, Any]:
    keyword = arguments.get("keyword")
    tag = arguments.get("tag")
    tags = arguments.get("tags")
    source = arguments.get("source")
    status = arguments.get("status", "all")
    favorite = bool(arguments.get("favorite", False))
    sort = arguments.get("sort", "recent")
    limit = max(1, min(int(arguments.get("limit", 20)), 50))
    offset = max(0, int(arguments.get("offset", 0)))

    items, total = query_library_index(
        user_id="curator",
        is_curator=True,
        page=1,
        page_size=limit,
        status=status,
        favorite=favorite,
        source=source,
        q=keyword,
        tag=tag,
        tags=tags,
        sort=sort,
        offset=offset,
    )

    summaries = []
    for item in items:
        authors = json.loads(item["authors_json"]) if item.get("authors_json") else []
        tags_list = json.loads(item["tags_json"]) if item.get("tags_json") else []
        summaries.append({
            "source": item["source"],
            "source_id": item["source_id"],
            "display_id": item.get("display_id", item["source_id"]),
            "title": item["title"],
            "authors": authors,
            "tags": tags_list,
            "page_count": item["page_count"],
            "cached_pages": item.get("cached_pages", 0),
            "likes": item.get("likes", ""),
            "views": item.get("views", ""),
            "imported_at": item.get("imported_at", ""),
            "detail_url": f"/comic/{item['source']}/{item['source_id']}",
        })

    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps({
                    "total": total,
                    "returned": len(summaries),
                    "offset": offset,
                    "limit": limit,
                    "items": summaries,
                }, ensure_ascii=False, indent=2),
            }
        ],
        "isError": False,
    }


def _tool_get_comic_detail(arguments: dict[str, Any]) -> dict[str, Any]:
    source = str(arguments.get("source", "")).strip()
    source_id = str(arguments.get("source_id", "")).strip()
    if not source or not source_id:
        raise ValueError("source 与 source_id 不能为空")

    meta = store.load_meta(source, source_id)
    if not meta:
        return {
            "content": [{"type": "text", "text": f"作品不存在或尚未收录: {source}/{source_id}"}],
            "isError": True,
        }

    cached_count = store.cached_page_count(meta)
    chapters_data = [
        {
            "id": c.id,
            "index": c.index,
            "title": c.title,
            "page_count": c.page_count,
            "start_page": c.start,
        }
        for c in meta.chapters
    ]

    detail_payload = {
        "source": meta.source,
        "source_id": meta.source_id,
        "display_id": meta.display_id,
        "title": meta.title,
        "authors": meta.authors,
        "tags": meta.tags,
        "works": meta.works,
        "actors": meta.actors,
        "description": meta.description,
        "page_count": meta.page_count,
        "cached_pages": cached_count,
        "is_cached": cached_count >= meta.page_count if meta.page_count > 0 else False,
        "chapter_count": len(chapters_data),
        "chapters": chapters_data,
        "views": meta.views,
        "likes": meta.likes,
        "published_at": meta.published_at,
        "imported_at": meta.imported_at,
    }

    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(detail_payload, ensure_ascii=False, indent=2),
            }
        ],
        "isError": False,
    }


def _tool_recommend_unread(arguments: dict[str, Any]) -> dict[str, Any]:
    limit = max(1, min(int(arguments.get("limit", 5)), 20))
    tag = arguments.get("tag")
    source = arguments.get("source")

    items, total = query_library_index(
        user_id="curator",
        is_curator=True,
        page=1,
        page_size=limit,
        status="unread",
        source=source,
        tag=tag,
        sort="recent",
    )

    results = []
    for item in items:
        authors = json.loads(item["authors_json"]) if item.get("authors_json") else []
        tags_list = json.loads(item["tags_json"]) if item.get("tags_json") else []
        results.append({
            "source": item["source"],
            "source_id": item["source_id"],
            "title": item["title"],
            "authors": authors,
            "tags": tags_list,
            "page_count": item["page_count"],
            "detail_url": f"/comic/{item['source']}/{item['source_id']}",
        })

    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps({
                    "total_unread": total,
                    "recommendations": results,
                }, ensure_ascii=False, indent=2),
            }
        ],
        "isError": False,
    }


def _tool_create_direct_pass(arguments: dict[str, Any]) -> dict[str, Any]:
    source = str(arguments.get("source", "")).strip()
    source_id = str(arguments.get("source_id", "")).strip()
    page_index = max(1, int(arguments.get("page_index", 1)))
    ttl_seconds = max(60, min(int(arguments.get("ttl_seconds", 7200)), 86400 * 7))

    if not source or not source_id:
        raise ValueError("source 与 source_id 不能为空")

    meta = store.load_meta(source, source_id)
    if not meta:
        return {
            "content": [{"type": "text", "text": f"作品不存在: {source}/{source_id}"}],
            "isError": True,
        }

    # 直达链接是给访客看的，隐藏本就别从智能体这条路上漏出去；要真分享，由人在 Web 端点一下
    if meta.hidden_from_guest:
        raise ValueError(f"作品 {source}/{source_id} 已标记为对访客隐藏，MCP 通道拒绝为其签发直达阅读链接")

    safe_page = min(page_index, max(1, meta.page_count))
    res = create_direct_pass(
        source=source,
        source_id=source_id,
        page_index=safe_page,
        ttl_seconds=ttl_seconds,
    )
    safe_src = quote(source, safe="")
    safe_sid = quote(source_id, safe="")
    direct_url = f"/comic/{safe_src}/{safe_sid}/read/{safe_page}?temp_token={res['token']}"

    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps({
                    "token": res["token"],
                    "source": source,
                    "source_id": source_id,
                    "title": meta.title,
                    "page_index": page_index,
                    "direct_url": direct_url,
                    "expires_at": res["expires_at"],
                    "expires_in_seconds": res["expires_in"],
                    "expires_in_hours": round(res["expires_in"] / 3600, 1),
                }, ensure_ascii=False, indent=2),
            }
        ],
        "isError": False,
    }


def _tool_get_shelf_stats(arguments: dict[str, Any]) -> dict[str, Any]:
    facets = get_library_facets(is_curator=True)
    stats = facets.get("stats", {})
    im_status = check_imsearch_status()

    payload = {
        "total_books": stats.get("total_books", 0),
        "total_pages": stats.get("total_pages", 0),
        "cached_pages": stats.get("cached_pages", 0),
        "visual_search_available": im_status.get("available", False),
        "top_tags": facets.get("top_tags", []),
    }

    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(payload, ensure_ascii=False, indent=2),
            }
        ],
        "isError": False,
    }


def _tool_get_story_context(arguments: dict[str, Any]) -> dict[str, Any]:
    source = str(arguments.get("source", "")).strip()
    source_id = str(arguments.get("source_id", "")).strip()
    if not source or not source_id:
        raise ValueError("source 与 source_id 不能为空")
    try:
        page_start = int(arguments["page_start"])
        page_end = int(arguments["page_end"])
    except (KeyError, TypeError, ValueError):
        raise ValueError("page_start 与 page_end 必须是整数页号")
    budget = int(arguments.get("budget_lines", 120))

    # 与 REST 出口一样先确认书在库里：否则 agent 分不清"没这本书"和"这本没台词"
    meta = store.load_meta(source, source_id)
    if not meta:
        return {
            "content": [{"type": "text", "text": f"作品不存在或尚未收录: {source}/{source_id}"}],
            "isError": True,
        }

    ctx = get_story_context(source, source_id, page_start, page_end, budget_lines=budget)
    payload = {"source": source, "source_id": source_id, "title": meta.title, **ctx}
    return {
        "content": [
            {"type": "text", "text": json.dumps(payload, ensure_ascii=False, indent=2)}
        ],
        "isError": False,
    }


TOOL_HANDLERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "search_by_image": _tool_search_by_image,
    "search_by_dialogue": _tool_search_by_dialogue,
    "search_by_meaning": _tool_search_by_meaning,
    "query_shelf": _tool_query_shelf,
    "get_comic_detail": _tool_get_comic_detail,
    "recommend_unread": _tool_recommend_unread,
    "create_direct_pass": _tool_create_direct_pass,
    "get_shelf_stats": _tool_get_shelf_stats,
    "get_story_context": _tool_get_story_context,
}


async def execute_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Executes an MCP tool via registry dispatch and returns a standard JSON-RPC Tool Result."""
    handler = TOOL_HANDLERS.get(name)
    if not handler:
        return {
            "content": [{"type": "text", "text": f"未知的 MCP 工具: {name}"}],
            "isError": True,
        }
    try:
        # 工具里全是同步阻塞调用（识图 urllib 超时 10 秒、SQLite、numpy），服务又只有一个 worker：
        # 留在事件循环上跑，一次慢调用就卡住全站请求与所有 SSE。与 REST 识图端点一样丢进线程池
        return await asyncio.to_thread(handler, arguments)
    except Exception as exc:
        logger.warning("MCP tool execution error for '%s': %s", name, exc)
        return {
            "content": [{"type": "text", "text": f"工具执行异常: {exc}"}],
            "isError": True,
        }


# ----------------------------------------------------------------------
# Resource Content Provider Registry
# ----------------------------------------------------------------------
def _read_shelf_stats() -> dict[str, Any]:
    facets = get_library_facets(is_curator=True)
    return {
        "contents": [
            {
                "uri": "shelf://stats",
                "mimeType": "application/json",
                "text": json.dumps(facets, ensure_ascii=False, indent=2),
            }
        ]
    }


def _read_shelf_providers() -> dict[str, Any]:
    return {
        "contents": [
            {
                "uri": "shelf://providers",
                "mimeType": "application/json",
                "text": json.dumps(provider_list(), ensure_ascii=False, indent=2),
            }
        ]
    }


def _read_shelf_recent() -> dict[str, Any]:
    items, _ = query_library_index(
        user_id="curator",
        is_curator=True,
        page=1,
        page_size=20,
        sort="recent",
    )
    recent_list = [
        {
            "source": item["source"],
            "source_id": item["source_id"],
            "title": item["title"],
            "authors": json.loads(item["authors_json"]) if item.get("authors_json") else [],
            "tags": json.loads(item["tags_json"]) if item.get("tags_json") else [],
            "page_count": item["page_count"],
        }
        for item in items
    ]
    return {
        "contents": [
            {
                "uri": "shelf://recent",
                "mimeType": "application/json",
                "text": json.dumps(recent_list, ensure_ascii=False, indent=2),
            }
        ]
    }


RESOURCE_HANDLERS: dict[str, Callable[[], dict[str, Any]]] = {
    "shelf://stats": _read_shelf_stats,
    "shelf://providers": _read_shelf_providers,
    "shelf://recent": _read_shelf_recent,
}


async def read_resource(uri: str) -> dict[str, Any]:
    """Reads the contents of an MCP resource by URI."""
    handler = RESOURCE_HANDLERS.get(uri)
    if not handler:
        raise ValueError(f"Resource not found: {uri}")
    # 同 execute_tool：资源读取也是同步 SQLite 查询，不能占着事件循环
    return await asyncio.to_thread(handler)


# ----------------------------------------------------------------------
# JSON-RPC 2.0 Request Processor
# ----------------------------------------------------------------------
async def _process_single_jsonrpc_request(req_data: Any) -> dict[str, Any] | None:
    """Processes an individual JSON-RPC 2.0 request or notification and returns a response."""
    if not isinstance(req_data, dict):
        return {
            "jsonrpc": "2.0",
            "id": None,
            "error": {"code": -32600, "message": "Invalid Request: expected JSON object"},
        }

    msg_id = req_data.get("id")
    method = req_data.get("method")
    params = req_data.get("params", {}) or {}

    # Notification (no id)
    if msg_id is None:
        if method == "notifications/initialized":
            logger.info("MCP Client connected and initialized")
        return None

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {
                    "tools": {"listChanged": False},
                    "resources": {"subscribe": False, "listChanged": False},
                    "prompts": {"listChanged": False},
                },
                "serverInfo": {
                    "name": SERVER_NAME,
                    "version": SERVER_VERSION,
                },
                "instructions": (
                    "纸间 (Paper Room) 本地漫画收藏馆 MCP 服务端。提供以图搜图、台词全文检索、"
                    "书架藏书筛选、详情获取与单本临时直达阅读票据签发能力。"
                ),
            },
        }

    elif method == "ping":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {}}

    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {"tools": MCP_TOOLS},
        }

    elif method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments", {}) or {}
        tool_result = await execute_tool(tool_name, arguments)
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": tool_result,
        }

    elif method == "resources/list":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {"resources": MCP_RESOURCES},
        }

    elif method == "resources/read":
        uri = params.get("uri")
        try:
            res_content = await read_resource(uri)
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": res_content,
            }
        except Exception as err:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32602, "message": str(err)},
            }

    elif method == "prompts/list":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {"prompts": MCP_PROMPTS},
        }

    elif method == "prompts/get":
        prompt_name = params.get("name")
        if prompt_name == "find_comic_by_scene":
            clue = params.get("arguments", {}).get("clue", "")
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "description": "名场面与台词联合定位",
                    "messages": [
                        {
                            "role": "user",
                            "content": {
                                "type": "text",
                                "text": (
                                    "请在纸间漫画库中查找以下线索对应的漫画作品与具体页码：记得原话先用 search_by_dialogue，"
                                    "只记得大意或字面没命中时用 search_by_meaning，有截图用 search_by_image；"
                                    "定位到本子后要看前后剧情再用 get_story_context 取那几页的台词。\n\n"
                                    f"【线索】：{clue}"
                                ),
                            },
                        }
                    ],
                },
            }
        elif prompt_name == "recommend_comic":
            pref = params.get("arguments", {}).get("preference", "热门")
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "description": "漫画推荐提示",
                    "messages": [
                        {
                            "role": "user",
                            "content": {
                                "type": "text",
                                "text": f"请结合 query_shelf 与 recommend_unread 工具，为读者推荐符合偏好（{pref}）且尚未阅读的纸间藏书，并附上直达阅读链接。",
                            },
                        }
                    ],
                },
            }
        else:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32601, "message": f"Prompt not found: {prompt_name}"},
            }

    else:
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }


async def process_jsonrpc_request(req_data: Any) -> Any:
    """Processes an incoming JSON-RPC 2.0 request, batch array, or notification."""
    if isinstance(req_data, list):
        if not req_data:
            return {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32600, "message": "Invalid Request: empty batch"},
            }
        results = []
        for single_req in req_data:
            res = await _process_single_jsonrpc_request(single_req)
            if res is not None:
                results.append(res)
        return results if results else None

    return await _process_single_jsonrpc_request(req_data)


def _require_mcp_auth(request: Request) -> None:
    """MCP 面只认馆长口令，外加一把可单独撤销的子凭据 `COMIC_SHELF_MCP_TOKEN`。

    不认机器密钥：那把钥匙同时握在 OCR 流水线手里（入库与伴生同步都要用），外发到智能体配置里
    等于连"往库里写东西"一起交出去，换它得连流水线一起重启；而 MCP 工具按馆长视角取料，
    机器密钥进来就能读到隐藏本台词。

    失败尝试走与 `/api/auth/login` 同一套 IP 锁规则，但单独记在 `mcp:<ip>` 键下：全站中间件对
    `/api/mcp` 是提前放行的，这里不计数就没有任何东西挡得住对着密钥的反复猜测；而与网页登录共用
    一个计数的话，一个配错凭据、不停重连的智能体会把同 IP 的馆长网页登录一起锁死。
    """
    ip = get_client_ip(request)
    # 取不到 IP 时保持空键（abuse 对空键不计数），免得所有无 IP 请求挤进同一个 "mcp:" 桶互相锁死
    key = f"mcp:{ip}" if ip else ""
    if is_ip_login_locked(key):
        raise HTTPException(
            status_code=429,
            detail="MCP 凭据尝试过于频繁，该网络地址已临时锁定 5 分钟，请稍后再试",
            headers={"Retry-After": "300"},
        )

    granted = is_curator(request)
    token = extract_token(request)
    if not granted and MCP_TOKEN:
        granted = bool(token) and secrets.compare_digest(token, MCP_TOKEN)

    if granted:
        # 成功不清零计数（同 /api/auth/login）：否则手握 MCP 凭据的人每猜 9 次馆长口令
        # 就用自己的凭据成功一次把计数清掉，可以无限试下去
        return

    # 同一个错误凭据窗口内只计一次：配错凭据、不停重连的智能体不会把自己锁死
    record_ip_login_failure_and_check_lock(key, f"{token}\0{request.headers.get('x-machine-token', '').strip()}")
    raise HTTPException(
        status_code=401,
        # 文案固定：若随是否配置子凭据而变，匿名者凭一次 401 就能摸清这台服务配没配子凭据
        detail="未授权访问：MCP 接口需要馆长口令或 MCP 凭据 (Curator or MCP Credential Required)",
        headers={"WWW-Authenticate": "Bearer"},
    )


# ----------------------------------------------------------------------
# FastAPI Router Endpoints: SSE Transport & Direct HTTP JSON-RPC
# ----------------------------------------------------------------------
@router.get("/api/mcp/sse")
@router.get("/mcp/sse")
async def mcp_sse_endpoint(request: Request) -> StreamingResponse:
    """Server-Sent Events (SSE) stream endpoint for Model Context Protocol (MCP).

    Standard MCP over SSE lifecycle:
    1. Generates a unique session_id;
    2. Emits an initial 'endpoint' event with the message delivery URL;
    3. Streams JSON-RPC 2.0 messages from the session queue to the client.
    """
    _require_mcp_auth(request)
    async with _sessions_lock:
        if len(_mcp_sessions) >= _MAX_MCP_SESSIONS:
            raise HTTPException(
                status_code=429,
                detail=f"MCP 并发会话数超限（最大支持 {_MAX_MCP_SESSIONS} 个并发会话）",
            )
        session_id = secrets.token_hex(16)
        queue: asyncio.Queue[str | None] = asyncio.Queue(maxsize=100)
        _mcp_sessions[session_id] = queue

    # 刻意不把调用方自带的凭据拼进下面这个 URL：uvicorn 与反代访问日志默认记完整查询串，
    # 那样站长口令/机器密钥会在日志里长期留存。session_id 是服务端每次连接新发的 128bit
    # 随机值、断连即回收，它的保密等级就等于一次性会话票据，不需要再叠一层长效凭据。
    message_endpoint_url = f"/api/mcp/messages?session_id={session_id}"

    async def sse_stream() -> AsyncGenerator[str, None]:
        try:
            # Emit standard MCP 'endpoint' handshake event
            yield f"event: endpoint\ndata: {message_endpoint_url}\n\n"

            while True:
                if await request.is_disconnected():
                    break
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=25.0)
                    if msg is None:
                        break
                    yield f"event: message\ndata: {msg}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            async with _sessions_lock:
                _mcp_sessions.pop(session_id, None)

    return StreamingResponse(
        sse_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/api/mcp/messages")
@router.post("/mcp/messages")
async def mcp_messages_endpoint(
    request: Request,
    session_id: str = Query(..., description="Active MCP SSE session ID"),
) -> Response:
    """Receives JSON-RPC 2.0 requests for an established MCP SSE session.

    续话只需持有活会话的 `session_id`（服务端每连接新发、断连即回收），不再要求重出示长
    效凭据——这正是把凭据从 URL 里拿掉后，只按 URL 回话的客户端仍能工作的原因。
    """
    async with _sessions_lock:
        queue = _mcp_sessions.get(session_id)

    if queue is None:
        # 直接 404，不验凭据也不计失败：会话表只在内存里，服务一重启客户端手里的旧 session_id 全部作废，
        # 而续话本就不带凭据——在这里验凭据，断线后每条消息都会记成一次失败，几条就把该 IP 锁住。
        # session_id 是 128bit 随机值，拿 401/404 的差别去猜活会话并不现实
        raise HTTPException(status_code=404, detail="MCP session not found or expired")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON-RPC payload")

    resp_payload = await process_jsonrpc_request(payload)
    if resp_payload is not None:
        try:
            queue.put_nowait(json.dumps(resp_payload, ensure_ascii=False))
        except asyncio.QueueFull:
            raise HTTPException(status_code=429, detail="MCP session queue is full")

    return Response(status_code=202, media_type="text/plain", content="Accepted")


@router.post("/api/mcp/rpc")
@router.post("/mcp")
async def mcp_direct_rpc_endpoint(request: Request) -> JSONResponse:
    """Direct HTTP JSON-RPC 2.0 endpoint for stateless or simple MCP tool callers."""
    _require_mcp_auth(request)
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content={"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}},
        )

    resp = await process_jsonrpc_request(payload)
    if resp is None:
        return JSONResponse(status_code=204, content=None)
    return JSONResponse(content=resp)
