from __future__ import annotations

import json
import logging
import sqlite3
import sys
import threading
import time
from datetime import datetime
from typing import Any

from ..formatting import normalize_title
from ..zh_conv import to_simplified
from .connection import _escape_like, get_db
from .dialogues import delete_comic_dialogues

logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# 书架全貌聚合统计（Facets）进程级内存缓存
# ----------------------------------------------------------------------
_facets_cache: dict[tuple[bool, str | None], tuple[float, dict[str, Any]]] = {}
_facets_cache_lock = threading.Lock()
_facets_compute_lock = threading.Lock()
_last_facets_invalidated_at: float = 0.0


def invalidate_facets_cache(force: bool = False) -> None:
    """使书架全貌聚合统计（Facets）缓存失效。

    Args:
        force: 若为 True，立即清空字典（用于单测隔离或显式重置）。
    """
    global _last_facets_invalidated_at
    with _facets_cache_lock:
        _last_facets_invalidated_at = time.monotonic()
        if force:
            _facets_cache.clear()



def rebuild_facets_snapshot(conn: sqlite3.Connection) -> None:
    """全量基于 comics_index 重建增量分面快照表 (library_stats_snapshot 与 library_tag_counts)。"""
    now_ts = time.time()
    conn.execute("DELETE FROM library_stats_snapshot")
    conn.execute("DELETE FROM library_tag_counts")

    # 1. 馆长全库与分源统计
    conn.execute(
        """
        INSERT INTO library_stats_snapshot (scope, total_books, total_pages, cached_pages, updated_at)
        SELECT 'admin:all', COUNT(*), COALESCE(SUM(page_count), 0), COALESCE(SUM(cached_pages), 0), ?
        FROM comics_index
        """,
        (now_ts,),
    )
    conn.execute(
        """
        INSERT INTO library_stats_snapshot (scope, total_books, total_pages, cached_pages, updated_at)
        SELECT 'admin:' || source, COUNT(*), COALESCE(SUM(page_count), 0), COALESCE(SUM(cached_pages), 0), ?
        FROM comics_index
        GROUP BY source
        """,
        (now_ts,),
    )

    # 2. 访客全库与分源统计 (hidden_from_guest = 0)
    conn.execute(
        """
        INSERT INTO library_stats_snapshot (scope, total_books, total_pages, cached_pages, updated_at)
        SELECT 'guest:all', COUNT(*), COALESCE(SUM(page_count), 0), COALESCE(SUM(cached_pages), 0), ?
        FROM comics_index
        WHERE hidden_from_guest = 0
        """,
        (now_ts,),
    )
    conn.execute(
        """
        INSERT INTO library_stats_snapshot (scope, total_books, total_pages, cached_pages, updated_at)
        SELECT 'guest:' || source, COUNT(*), COALESCE(SUM(page_count), 0), COALESCE(SUM(cached_pages), 0), ?
        FROM comics_index
        WHERE hidden_from_guest = 0
        GROUP BY source
        """,
        (now_ts,),
    )

    # 确保兜底基础行存在
    conn.execute(
        """
        INSERT OR IGNORE INTO library_stats_snapshot (scope, total_books, total_pages, cached_pages, updated_at)
        VALUES ('admin:all', 0, 0, 0, ?), ('guest:all', 0, 0, 0, ?)
        """,
        (now_ts, now_ts),
    )

    # 3. 标签统计：馆长全库与分源
    conn.execute(
        """
        INSERT INTO library_tag_counts (scope, tag, cnt)
        SELECT 'admin:all', value, COUNT(*)
        FROM comics_index ci, json_each(ci.tags_json)
        WHERE value IS NOT NULL AND value != ''
        GROUP BY value
        """
    )
    conn.execute(
        """
        INSERT INTO library_tag_counts (scope, tag, cnt)
        SELECT 'admin:' || source, value, COUNT(*)
        FROM comics_index ci, json_each(ci.tags_json)
        WHERE value IS NOT NULL AND value != ''
        GROUP BY source, value
        """
    )

    # 4. 标签统计：访客全库与分源
    conn.execute(
        """
        INSERT INTO library_tag_counts (scope, tag, cnt)
        SELECT 'guest:all', value, COUNT(*)
        FROM comics_index ci, json_each(ci.tags_json)
        WHERE hidden_from_guest = 0 AND value IS NOT NULL AND value != ''
        GROUP BY value
        """
    )
    conn.execute(
        """
        INSERT INTO library_tag_counts (scope, tag, cnt)
        SELECT 'guest:' || source, value, COUNT(*)
        FROM comics_index ci, json_each(ci.tags_json)
        WHERE hidden_from_guest = 0 AND value IS NOT NULL AND value != ''
        GROUP BY source, value
        """
    )


def _apply_facets_delta(
    conn: sqlite3.Connection,
    source: str,
    old_item: dict[str, Any] | None,
    new_item: dict[str, Any] | None,
) -> None:
    """增量应用单本漫画的变更到 library_stats_snapshot 与 library_tag_counts 快照表，达成 O(1) 增量维护。"""
    if old_item is None and new_item is None:
        return

    admin_scopes = ["admin:all"]
    guest_scopes = ["guest:all"]
    if source:
        admin_scopes.append(f"admin:{source}")
        guest_scopes.append(f"guest:{source}")
    now_ts = time.time()

    def _update_stats(scopes: list[str], d_books: int, d_pages: int, d_cached: int):
        if d_books == 0 and d_pages == 0 and d_cached == 0:
            return
        for sc in scopes:
            row = conn.execute(
                "SELECT total_books, total_pages, cached_pages FROM library_stats_snapshot WHERE scope = ?",
                (sc,),
            ).fetchone()
            if row:
                tb = max(0, int(row["total_books"] or 0) + d_books)
                tp = max(0, int(row["total_pages"] or 0) + d_pages)
                cp = max(0, int(row["cached_pages"] or 0) + d_cached)
                conn.execute(
                    "UPDATE library_stats_snapshot SET total_books = ?, total_pages = ?, cached_pages = ?, updated_at = ? WHERE scope = ?",
                    (tb, tp, cp, now_ts, sc),
                )
            else:
                tb = max(0, d_books)
                tp = max(0, d_pages)
                cp = max(0, d_cached)
                conn.execute(
                    "INSERT INTO library_stats_snapshot (scope, total_books, total_pages, cached_pages, updated_at) VALUES (?, ?, ?, ?, ?)",
                    (sc, tb, tp, cp, now_ts),
                )

    def _update_tags(scopes: list[str], tag_deltas: dict[str, int]):
        if not tag_deltas or not any(tag_deltas.values()):
            return
        for sc in scopes:
            for tag, delta in tag_deltas.items():
                if not tag or delta == 0:
                    continue
                if delta > 0:
                    conn.execute(
                        """
                        INSERT INTO library_tag_counts (scope, tag, cnt)
                        VALUES (?, ?, ?)
                        ON CONFLICT(scope, tag) DO UPDATE SET
                            cnt = cnt + excluded.cnt
                        """,
                        (sc, tag, delta),
                    )
                else:
                    conn.execute(
                        "UPDATE library_tag_counts SET cnt = cnt + ? WHERE scope = ? AND tag = ?",
                        (delta, sc, tag),
                    )
                    conn.execute(
                        "DELETE FROM library_tag_counts WHERE scope = ? AND tag = ? AND cnt <= 0",
                        (sc, tag),
                    )

    # 1. 新增入库（做加法）
    if old_item is None and new_item is not None:
        pages = int(new_item.get("page_count") or 0)
        cached = int(new_item.get("cached_pages") or 0)
        hidden = int(new_item.get("hidden_from_guest") or 0)
        try:
            tags = set(json.loads(new_item.get("tags_json") or "[]"))
        except Exception:
            tags = set()
        tag_deltas = {t: 1 for t in tags if t}

        _update_stats(admin_scopes, 1, pages, cached)
        _update_tags(admin_scopes, tag_deltas)

        if hidden == 0:
            _update_stats(guest_scopes, 1, pages, cached)
            _update_tags(guest_scopes, tag_deltas)
        return

    # 2. 移除藏书（做减法）
    if old_item is not None and new_item is None:
        pages = int(old_item.get("page_count") or 0)
        cached = int(old_item.get("cached_pages") or 0)
        hidden = int(old_item.get("hidden_from_guest") or 0)
        try:
            tags = set(json.loads(old_item.get("tags_json") or "[]"))
        except Exception:
            tags = set()
        tag_deltas = {t: -1 for t in tags if t}

        _update_stats(admin_scopes, -1, -pages, -cached)
        _update_tags(admin_scopes, tag_deltas)

        if hidden == 0:
            _update_stats(guest_scopes, -1, -pages, -cached)
            _update_tags(guest_scopes, tag_deltas)
        return

    # 3. 编辑或重新装订（差量计算）
    if old_item is not None and new_item is not None:
        old_pages = int(old_item.get("page_count") or 0)
        new_pages = int(new_item.get("page_count") or 0)
        old_cached = int(old_item.get("cached_pages") or 0)
        new_cached = int(new_item.get("cached_pages") or 0)
        old_hidden = int(old_item.get("hidden_from_guest") or 0)
        new_hidden = int(new_item.get("hidden_from_guest") or 0)

        try:
            old_tags = set(json.loads(old_item.get("tags_json") or "[]"))
        except Exception:
            old_tags = set()
        try:
            new_tags = set(json.loads(new_item.get("tags_json") or "[]"))
        except Exception:
            new_tags = set()

        d_pages = new_pages - old_pages
        d_cached = new_cached - old_cached
        admin_tag_deltas: dict[str, int] = {}
        for t in (new_tags - old_tags):
            if t:
                admin_tag_deltas[t] = 1
        for t in (old_tags - new_tags):
            if t:
                admin_tag_deltas[t] = -1

        _update_stats(admin_scopes, 0, d_pages, d_cached)
        _update_tags(admin_scopes, admin_tag_deltas)

        if old_hidden == 0 and new_hidden == 0:
            _update_stats(guest_scopes, 0, d_pages, d_cached)
            _update_tags(guest_scopes, admin_tag_deltas)
        elif old_hidden == 0 and new_hidden == 1:
            _update_stats(guest_scopes, -1, -old_pages, -old_cached)
            _update_tags(guest_scopes, {t: -1 for t in old_tags if t})
        elif old_hidden == 1 and new_hidden == 0:
            _update_stats(guest_scopes, 1, new_pages, new_cached)
            _update_tags(guest_scopes, {t: 1 for t in new_tags if t})




def upsert_comic_index(item: dict[str, Any]) -> None:
    """插入或更新漫画影子索引记录，并增量同步分面快照。"""
    defaults = {
        "source": "",
        "source_id": "",
        "display_id": "",
        "title": "",
        "authors_json": "[]",
        "works_json": "[]",
        "actors_json": "[]",
        "tags_json": "[]",
        "chapter_titles_json": "[]",
        "page_count": 0,
        "cached_pages": 0,
        "cover_count": 4,
        "cover_indices_json": "[]",
        "views": "",
        "likes": "",
        "uploaded_at": "",
        "published_at": "",
        "updated_at": "",
        "imported_at": "",
        "hidden_from_guest": 0,
        "mtime": 0.0,
        "auto_update_interval_days": 15,
        "last_auto_checked_at": "",
        "normalized_title": "",
    }
    merged_item = {**defaults, **item}
    source = str(merged_item.get("source") or "")
    source_id = str(merged_item.get("source_id") or "")
    if not merged_item.get("normalized_title"):
        merged_item["normalized_title"] = normalize_title(str(merged_item.get("title") or ""))

    with get_db() as conn:
        old_row = conn.execute(
            "SELECT page_count, cached_pages, hidden_from_guest, tags_json FROM comics_index WHERE source = ? AND source_id = ?",
            (source, source_id),
        ).fetchone()
        old_item = dict(old_row) if old_row else None

        conn.execute(
            """
            INSERT INTO comics_index (
                source, source_id, display_id, title,
                authors_json, works_json, actors_json, tags_json, chapter_titles_json,
                page_count, cached_pages, cover_count, cover_indices_json,
                views, likes, uploaded_at, published_at, updated_at, imported_at,
                hidden_from_guest, mtime, auto_update_interval_days, last_auto_checked_at,
                normalized_title
            ) VALUES (
                :source, :source_id, :display_id, :title,
                :authors_json, :works_json, :actors_json, :tags_json, :chapter_titles_json,
                :page_count, :cached_pages, :cover_count, :cover_indices_json,
                :views, :likes, :uploaded_at, :published_at, :updated_at, :imported_at,
                :hidden_from_guest, :mtime, :auto_update_interval_days, :last_auto_checked_at,
                :normalized_title
            ) ON CONFLICT(source, source_id) DO UPDATE SET
                display_id = excluded.display_id,
                title = excluded.title,
                authors_json = excluded.authors_json,
                works_json = excluded.works_json,
                actors_json = excluded.actors_json,
                tags_json = excluded.tags_json,
                chapter_titles_json = excluded.chapter_titles_json,
                page_count = excluded.page_count,
                cached_pages = excluded.cached_pages,
                cover_count = excluded.cover_count,
                cover_indices_json = excluded.cover_indices_json,
                views = excluded.views,
                likes = excluded.likes,
                uploaded_at = excluded.uploaded_at,
                published_at = excluded.published_at,
                updated_at = excluded.updated_at,
                imported_at = excluded.imported_at,
                hidden_from_guest = excluded.hidden_from_guest,
                mtime = excluded.mtime,
                auto_update_interval_days = excluded.auto_update_interval_days,
                last_auto_checked_at = excluded.last_auto_checked_at,
                normalized_title = excluded.normalized_title
            """,
            merged_item,
        )
        _apply_facets_delta(conn, source, old_item, merged_item)
        conn.commit()
    invalidate_facets_cache()


def purge_comic_db_records(source: str, source_id: str) -> bool:
    """彻底级联清理指定漫画在 SQLite 数据库中的所有关联记录并增量维护快照：
    1. 影子索引 (comics_index) 及增量分面快照 (library_stats_snapshot, library_tag_counts)
    2. 用户喜欢标记 (user_favorites)
    3. 用户阅读进度 (user_reading_progress)
    4. 单本沙箱专属通行证 (direct_passes)
    5. 台词全文检索与 OCR 同步元数据 (comic_dialogues_fts, comic_ocr_sync_meta)
    """
    purged = False
    with get_db() as conn:
        old_row = conn.execute(
            "SELECT page_count, cached_pages, hidden_from_guest, tags_json FROM comics_index WHERE source = ? AND source_id = ?",
            (source, source_id),
        ).fetchone()
        old_item = dict(old_row) if old_row else None

        c1 = conn.execute(
            "DELETE FROM comics_index WHERE source = ? AND source_id = ?",
            (source, source_id),
        ).rowcount
        c2 = conn.execute(
            "DELETE FROM user_favorites WHERE source = ? AND source_id = ?",
            (source, source_id),
        ).rowcount
        c3 = conn.execute(
            "DELETE FROM user_reading_progress WHERE source = ? AND source_id = ?",
            (source, source_id),
        ).rowcount
        c4 = conn.execute(
            "DELETE FROM direct_passes WHERE source = ? AND source_id = ?",
            (source, source_id),
        ).rowcount

        if old_item is not None:
            _apply_facets_delta(conn, source, old_item, None)

        conn.commit()
        if (c1 + c2 + c3 + c4) > 0:
            purged = True

    try:
        delete_comic_dialogues(source, source_id)
    except Exception as exc:
        # 语料删不掉不该让删书失败，但必须留警告：孤儿台词行仍会被检索命中，却拼不出书名
        logger.warning("清理台词索引失败 %s/%s: %s", source, source_id, exc)

    if purged:
        invalidate_facets_cache()

    return purged


def delete_comic_index(source: str, source_id: str) -> None:
    """删除指定漫画的影子索引及级联元数据。"""
    purge_comic_db_records(source, source_id)


def get_all_indexed_mtimes() -> dict[tuple[str, str], float]:
    """获取索引库中所有已记录条目的 (source, source_id) -> mtime 映射。
    若条目缺少 imported_at 或为非标准格式（含空格），则视为脏数据（返回 -1.0），促使 sync_library_index 触发自愈归一化。
    """
    with get_db() as conn:
        rows = conn.execute("SELECT source, source_id, mtime, imported_at FROM comics_index").fetchall()
        return {
            (r["source"], r["source_id"]): float(r["mtime"]) if (r["imported_at"] and " " not in r["imported_at"]) else -1.0
            for r in rows
        }


def get_comic_index_count() -> int:
    """获取当前已建立影子索引的漫画总数。"""
    with get_db() as conn:
        row = conn.execute("SELECT COUNT(*) as cnt FROM comics_index").fetchone()
        return int(row["cnt"]) if row else 0


def update_comic_cached_pages(source: str, source_id: str, cached_pages: int) -> None:
    """当后台单页缓存推进时，快速更新影子索引与分面快照中的 cached_pages 计数值。"""
    with get_db() as conn:
        row = conn.execute(
            "SELECT cached_pages, hidden_from_guest FROM comics_index WHERE source = ? AND source_id = ?",
            (source, source_id),
        ).fetchone()
        if not row:
            return
        old_cached = int(row["cached_pages"] or 0)
        hidden = int(row["hidden_from_guest"] or 0)
        d_cached = cached_pages - old_cached
        if d_cached == 0:
            return

        conn.execute(
            "UPDATE comics_index SET cached_pages = ? WHERE source = ? AND source_id = ?",
            (cached_pages, source, source_id),
        )
        admin_scopes = ["admin:all"]
        guest_scopes = ["guest:all"]
        if source:
            admin_scopes.append(f"admin:{source}")
            guest_scopes.append(f"guest:{source}")
        now_ts = time.time()
        for sc in admin_scopes:
            conn.execute(
                "UPDATE library_stats_snapshot SET cached_pages = MAX(0, cached_pages + ?), updated_at = ? WHERE scope = ?",
                (d_cached, now_ts, sc),
            )
        if hidden == 0:
            for sc in guest_scopes:
                conn.execute(
                    "UPDATE library_stats_snapshot SET cached_pages = MAX(0, cached_pages + ?), updated_at = ? WHERE scope = ?",
                    (d_cached, now_ts, sc),
                )
        conn.commit()
    invalidate_facets_cache()


def get_comics_due_for_auto_update(max_count: int = 10) -> list[dict[str, Any]]:
    """获取所有已到期需要进行自动追更巡检的非本地多章节漫画。

    过滤条件：
    1. 来源非 local（仅限远端图源）；
    2. auto_update_interval_days > 0（未关闭自动追更）；
    3. chapter_titles_json 话数 > 1（必须为多章节作品）；
    4. 当前时间距离上次检查时间 >= auto_update_interval_days * 86400。
    """
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT source, source_id, display_id, title, updated_at, published_at,
                   auto_update_interval_days, last_auto_checked_at, chapter_titles_json
            FROM comics_index
            WHERE source != 'local'
              AND auto_update_interval_days > 0
            """
        ).fetchall()

        now_ts = time.time()
        candidates: list[dict[str, Any]] = []
        for r in rows:
            try:
                chaps = json.loads(r["chapter_titles_json"] or "[]")
                if len(chaps) <= 1:
                    continue
            except Exception:
                continue

            interval_days = int(r["auto_update_interval_days"])
            last_checked = str(r["last_auto_checked_at"] or "")
            last_ts = 0.0
            if last_checked:
                try:
                    s = last_checked.strip()
                    if s.endswith("Z"):
                        s = s[:-1] + "+00:00"
                    last_ts = datetime.fromisoformat(s).timestamp()
                except Exception:
                    try:
                        last_ts = float(last_checked)
                    except Exception:
                        last_ts = 0.0

            if (now_ts - last_ts) >= (interval_days * 86400):
                candidates.append(dict(r))
                if len(candidates) >= max_count:
                    break
        return candidates


def record_comic_auto_checked(source: str, source_id: str, checked_at: str) -> None:
    """更新指定漫画在影子索引中的上次自动巡检时间戳。"""
    with get_db() as conn:
        conn.execute(
            "UPDATE comics_index SET last_auto_checked_at = ? WHERE source = ? AND source_id = ?",
            (checked_at, source, source_id),
        )
        conn.commit()


def find_comic_mirrors(
    source: str,
    source_id: str,
    title: str | None = None,
    normalized_title: str | None = None,
    limit: int = 5,
    is_curator: bool = False,
) -> list[dict[str, Any]]:
    """基于规范化标题查找馆内的异源/多版本同名作品（ADR 0031）。"""
    if not normalized_title:
        if not title:
            return []
        normalized_title = normalize_title(title)
    if not normalized_title:
        return []

    with get_db() as conn:
        sql = """
            SELECT source, source_id, display_id, title, page_count
            FROM comics_index
            WHERE normalized_title = ? AND (source != ? OR source_id != ?)
        """
        params: list[Any] = [normalized_title, source, source_id]
        if not is_curator:
            sql += " AND hidden_from_guest = 0"
        sql += " LIMIT ?"
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def batch_find_comic_mirrors(
    items: list[tuple[str, str, str]],
    is_curator: bool = False,
) -> dict[tuple[str, str], dict[str, Any] | None]:
    """批量查找候选作品在馆内的镜像匹配（首个匹配项），单次数据库连接完成以消除 N+1 查询。"""
    if not items:
        return {}
    res: dict[tuple[str, str], dict[str, Any] | None] = {}
    norm_map: dict[tuple[str, str], str] = {}
    norm_to_keys: dict[str, list[tuple[str, str]]] = {}
    for s, sid, t in items:
        norm = normalize_title(t)
        if norm:
            norm_map[(s, sid)] = norm
            norm_to_keys.setdefault(norm, []).append((s, sid))
        res[(s, sid)] = None

    if not norm_to_keys:
        return res

    with get_db() as conn:
        placeholders = ",".join("?" for _ in norm_to_keys)
        sql = f"""
            SELECT source, source_id, display_id, title, page_count, normalized_title
            FROM comics_index
            WHERE normalized_title IN ({placeholders})
        """
        params: list[Any] = list(norm_to_keys.keys())
        if not is_curator:
            sql += " AND hidden_from_guest = 0"
        rows = conn.execute(sql, params).fetchall()

        matches_by_norm: dict[str, list[dict[str, Any]]] = {}
        for r in rows:
            matches_by_norm.setdefault(r["normalized_title"], []).append(dict(r))

        for (s, sid), norm in norm_map.items():
            candidates = matches_by_norm.get(norm, [])
            for c in candidates:
                if c["source"] != s or c["source_id"] != sid:
                    res[(s, sid)] = c
                    break
    return res


def query_library_index(
    user_id: str,
    is_curator: bool,
    page: int = 1,
    page_size: int = 24,
    status: str = "all",
    favorite: bool = False,
    source: str | None = None,
    q: str | None = None,
    scope: str = "all",
    tag: str | None = None,
    tags: list[str] | str | None = None,
    sort: str = "recent",
    ids: str | None = None,
    offset: int | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Queries comics_index with pagination, multi-criteria filtering, and user reading progress joins.

    Args:
        user_id: Authenticated user identifier (used to resolve favorites and progress).
        is_curator: When False, automatically hides comics flagged with hidden_from_guest.
        page: 1-indexed page number (used when offset is not provided).
        page_size: Number of items per page.
        status: Reading status filter ('all', 'reading', 'completed', 'unread').
        favorite: When True, filters strictly to comics favorited by user_id.
        source: Optional provider filter (e.g., 'jm', 'local', 'picacg').
        q: Optional search query matched against title, authors, works, actors, and tags.
        scope: Search scope ('all', 'title_id', 'id', 'author', 'tag').
        tag: Optional exact tag filter evaluated via json_each(tags_json).
        tags: Optional comma-separated or list of tags for multi-tag compound AND filtering.
        sort: Sort mode ('recent', 'uploaded', 'views', 'likes', 'pages', 'alpha').
        ids: Optional comma-separated list of "source/source_id" keys to filter to.
        offset: Explicit SQL offset override, bypassing page * page_size calculation.

    Returns:
        A tuple of (matching_comic_dictionaries, total_matched_count).
    """
    conditions: list[str] = []
    params: dict[str, Any] = {"user_id": user_id}

    if not is_curator:
        conditions.append("ci.hidden_from_guest = 0")

    if source:
        conditions.append("ci.source = :source")
        params["source"] = source

    if favorite:
        conditions.append("uf.user_id IS NOT NULL")

    if status == "reading":
        conditions.append("COALESCE(urp.last_page, 0) > 0 AND COALESCE(urp.last_page, 0) < ci.page_count AND ci.page_count > 0")
    elif status == "completed":
        conditions.append("COALESCE(urp.last_page, 0) >= ci.page_count AND ci.page_count > 0")
    elif status == "unread":
        conditions.append("COALESCE(urp.last_page, 0) = 0")

    # Multi-Tag Compound Filter: Collect all tags for AND-intersection filtering
    all_tags: list[str] = []
    if tag and tag.strip():
        all_tags.append(tag.strip())
    if tags:
        if isinstance(tags, str):
            for t in tags.split(","):
                t_clean = t.strip()
                if t_clean and t_clean not in all_tags:
                    all_tags.append(t_clean)
        elif isinstance(tags, (list, tuple)):
            for t in tags:
                if isinstance(t, str):
                    t_clean = t.strip()
                    if t_clean and t_clean not in all_tags:
                        all_tags.append(t_clean)

    # 限制多标签交集最大数量（最多 5 个），防范极端查询导致 SQLite 变量耗尽与 CPU 算力耗尽
    all_tags = all_tags[:5]

    for i, t in enumerate(all_tags):
        param_name = f"tag_{i}"
        conditions.append(f"EXISTS (SELECT 1 FROM json_each(ci.tags_json) WHERE value = :{param_name})")
        params[param_name] = t

    if q and q.strip():
        raw_q = q.strip()
        # 汉化组元数据简繁混用、无法规范，书架检索只能在查询侧展开简繁变体（ADR 0017 2026-09-23 修订）
        from ..zh_conv import expand_search_variants

        groups = []
        for i, v in enumerate([v for v in expand_search_variants(raw_q) if v]):
            p_key = f"needle_{i}"
            params[p_key] = f"%{_escape_like(v)}%"
            if scope == "id":
                groups.append(f"(ci.display_id LIKE :{p_key} ESCAPE '\\' OR ci.source_id LIKE :{p_key} ESCAPE '\\')")
            elif scope == "author":
                groups.append(f"(ci.authors_json LIKE :{p_key} ESCAPE '\\')")
            elif scope == "tag":
                groups.append(f"(ci.tags_json LIKE :{p_key} ESCAPE '\\')")
            elif scope == "title_id":
                groups.append(f"(ci.title LIKE :{p_key} ESCAPE '\\' OR ci.display_id LIKE :{p_key} ESCAPE '\\')")
            else:
                groups.append(
                    f"""(
                    ci.title LIKE :{p_key} ESCAPE '\\'
                    OR ci.display_id LIKE :{p_key} ESCAPE '\\'
                    OR ci.authors_json LIKE :{p_key} ESCAPE '\\'
                    OR ci.works_json LIKE :{p_key} ESCAPE '\\'
                    OR ci.actors_json LIKE :{p_key} ESCAPE '\\'
                    OR ci.tags_json LIKE :{p_key} ESCAPE '\\'
                    OR ci.chapter_titles_json LIKE :{p_key} ESCAPE '\\'
                )"""
                )
        if groups:
            conditions.append("(" + " OR ".join(groups) + ")")

    if ids and ids.strip():
        id_list = [item.strip() for item in ids.split(",") if item.strip()][:120]
        if id_list:
            placeholders = []
            for i, val in enumerate(id_list):
                p_key = f"target_id_{i}"
                placeholders.append(f":{p_key}")
                params[p_key] = val
            conditions.append(f"(ci.source || ':' || ci.source_id) IN ({', '.join(placeholders)})")

    where_sql = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    relevance_order = ""
    if q and q.strip() and scope == "all" and "needle_0" in params:
        params["exact_q"] = raw_q
        relevance_order = """CASE
            WHEN ci.title = :exact_q COLLATE NOCASE OR ci.display_id = :exact_q COLLATE NOCASE OR ci.source_id = :exact_q COLLATE NOCASE THEN 0
            WHEN ci.title LIKE :needle_0 ESCAPE '\\' THEN 1
            WHEN ci.authors_json LIKE :needle_0 ESCAPE '\\' THEN 2
            ELSE 3
        END ASC, """

    order_sql = f"ORDER BY {relevance_order}ci.imported_at DESC, ci.source ASC, ci.source_id ASC"
    if sort == "recent":
        order_sql = f"""ORDER BY {relevance_order}
            CASE
                WHEN COALESCE(urp.last_page, 0) >= ci.page_count AND ci.page_count > 0 THEN 1
                ELSE 0
            END ASC,
            ci.imported_at DESC,
            ci.source ASC,
            ci.source_id ASC"""
    elif sort == "title":
        order_sql = f"ORDER BY {relevance_order}ci.title COLLATE NOCASE ASC, ci.imported_at DESC, ci.source ASC, ci.source_id ASC"
    elif sort == "pages":
        order_sql = f"ORDER BY {relevance_order}ci.page_count DESC, ci.imported_at DESC, ci.source ASC, ci.source_id ASC"
    elif sort == "cached":
        order_sql = f"ORDER BY {relevance_order}(CAST(ci.cached_pages AS REAL) / MAX(ci.page_count, 1)) DESC, ci.imported_at DESC, ci.source ASC, ci.source_id ASC"

    count_sql = f"""
        SELECT COUNT(*) as cnt
        FROM comics_index ci
        LEFT JOIN user_favorites uf
            ON uf.source = ci.source AND uf.source_id = ci.source_id AND uf.user_id = :user_id
        LEFT JOIN user_reading_progress urp
            ON urp.source = ci.source AND urp.source_id = ci.source_id AND urp.user_id = :user_id
        {where_sql}
    """

    actual_offset = max(0, offset) if offset is not None else max(0, (page - 1) * page_size)
    params["limit"] = page_size
    params["offset"] = actual_offset

    data_sql = f"""
        SELECT
            ci.source,
            ci.source_id,
            ci.display_id,
            ci.title,
            ci.authors_json,
            ci.works_json,
            ci.actors_json,
            ci.tags_json,
            ci.chapter_titles_json,
            ci.page_count,
            ci.cached_pages,
            ci.cover_count,
            ci.cover_indices_json,
            ci.views,
            ci.likes,
            ci.uploaded_at,
            ci.published_at,
            ci.updated_at,
            ci.imported_at,
            ci.hidden_from_guest,
            COALESCE(uf.user_id IS NOT NULL, 0) as is_favorite,
            COALESCE(urp.last_page, 0) as last_page
        FROM comics_index ci
        LEFT JOIN user_favorites uf
            ON uf.source = ci.source AND uf.source_id = ci.source_id AND uf.user_id = :user_id
        LEFT JOIN user_reading_progress urp
            ON urp.source = ci.source AND urp.source_id = ci.source_id AND urp.user_id = :user_id
        {where_sql}
        {order_sql}
        LIMIT :limit OFFSET :offset
    """

    with get_db() as conn:
        total_row = conn.execute(count_sql, params).fetchone()
        total = int(total_row["cnt"]) if total_row else 0
        rows = conn.execute(data_sql, params).fetchall()
        return [dict(r) for r in rows], total


def _compute_library_facets(is_curator: bool, source: str | None = None) -> dict[str, Any]:
    """从增量快照表 (library_stats_snapshot 与 library_tag_counts) 高性能读取分面统计，耗时稳定在 0.1ms。"""
    scope = f"{'admin' if is_curator else 'guest'}:{source if source else 'all'}"
    with get_db() as conn:
        has_snapshot = conn.execute("SELECT 1 FROM library_stats_snapshot LIMIT 1").fetchone()
        if not has_snapshot:
            rebuild_facets_snapshot(conn)
            conn.commit()

        stats_row = conn.execute(
            "SELECT total_books, total_pages, cached_pages FROM library_stats_snapshot WHERE scope = ?",
            (scope,),
        ).fetchone()

        tag_rows = conn.execute(
            "SELECT tag, cnt FROM library_tag_counts WHERE scope = ? ORDER BY cnt DESC, tag ASC LIMIT 30",
            (scope,),
        ).fetchall()

        return {
            "stats": {
                "total_books": int(stats_row["total_books"] or 0) if stats_row else 0,
                "total_pages": int(stats_row["total_pages"] or 0) if stats_row else 0,
                "cached_pages": int(stats_row["cached_pages"] or 0) if stats_row else 0,
            },
            "top_tags": [(str(r["tag"]), int(r["cnt"])) for r in tag_rows],
        }


def _copy_facets(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "stats": dict(data["stats"]),
        "top_tags": list(data["top_tags"]),
    }


def get_library_facets(
    is_curator: bool,
    source: str | None = None,
    bypass_cache: bool = False,
) -> dict[str, Any]:
    """Aggregates library statistics (total books, pages, cached pages) and top 30 most frequent tags.

    具备增量持久化快照表与进程级内存双重加速：
    1. 读操作：未发生写变动时 0ms 纯内存命中；写变动后首次读直接点查增量快照表（0.1ms 级），彻底根除全量 json_each 扫库；
    2. 写操作：单本漫画增量加减差量维护快照，耗时 <1ms，即时一致性；
    3. 异常自愈：当 bypass_cache=True 时自动全量重算重建快照落表。

    Args:
        is_curator: When False, excludes comics marked as hidden_from_guest from counts.
        source: Optional source filter to scope facets to a single provider.
        bypass_cache: When True, bypasses in-memory cache and rebuilds facets snapshot directly.

    Returns:
        Dict containing total_books, total_pages, cached_pages, and tags list with counts.
    """
    key = (is_curator, source)

    if not bypass_cache:
        with _facets_cache_lock:
            if key in _facets_cache:
                cached_at, cached_data = _facets_cache[key]
                if cached_at >= _last_facets_invalidated_at:
                    return _copy_facets(cached_data)

    with _facets_compute_lock:
        if bypass_cache:
            with get_db() as conn:
                rebuild_facets_snapshot(conn)
                conn.commit()
        else:
            with _facets_cache_lock:
                if key in _facets_cache:
                    cached_at, cached_data = _facets_cache[key]
                    if cached_at >= _last_facets_invalidated_at:
                        return _copy_facets(cached_data)

        compute_started_at = time.monotonic()
        compute_fn = getattr(sys.modules.get("app.db"), "_compute_library_facets", _compute_library_facets)
        result = compute_fn(is_curator=is_curator, source=source)

        with _facets_cache_lock:
            if key not in _facets_cache and len(_facets_cache) >= 32:
                _facets_cache.pop(next(iter(_facets_cache)))
            _facets_cache[key] = (compute_started_at, result)

        return _copy_facets(result)


