from __future__ import annotations

import time
from typing import Any

from .connection import get_db

def get_user_favorites(user_id: str) -> set[tuple[str, str]]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT source, source_id FROM user_favorites WHERE user_id = ?",
            (user_id,),
        ).fetchall()
        return {(r["source"], r["source_id"]) for r in rows}


def is_user_favorite(user_id: str, source: str, source_id: str) -> bool:
    with get_db() as conn:
        row = conn.execute(
            "SELECT 1 FROM user_favorites WHERE user_id = ? AND source = ? AND source_id = ?",
            (user_id, source, source_id),
        ).fetchone()
        return row is not None


def set_user_favorite(user_id: str, source: str, source_id: str, favorite: bool) -> bool:
    now = int(time.time())
    with get_db() as conn:
        if favorite:
            conn.execute(
                """
                INSERT OR IGNORE INTO user_favorites (user_id, source, source_id, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, source, source_id, now),
            )
        else:
            conn.execute(
                "DELETE FROM user_favorites WHERE user_id = ? AND source = ? AND source_id = ?",
                (user_id, source, source_id),
            )
        conn.commit()
    return favorite


def migrate_legacy_favorites(album_favorites: list[tuple[str, str]], curator_id: str = "curator") -> int:
    """首次初始化时，将 album.json 中历史标记的 favorite: true 迁移到馆长的独立喜欢库中"""
    now = int(time.time())
    count = 0
    with get_db() as conn:
        for source, source_id in album_favorites:
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO user_favorites (user_id, source, source_id, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (curator_id, source, source_id, now),
            )
            if cur.rowcount > 0:
                count += 1
        conn.commit()
    return count


# ----------------------------------------------------------------------
# 用户专属阅读进度（User Reading Progress）
# ----------------------------------------------------------------------

def get_user_progress(user_id: str, source: str, source_id: str) -> dict[str, Any] | None:
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT last_page, total_pages, updated_at
            FROM user_reading_progress
            WHERE user_id = ? AND source = ? AND source_id = ?
            """,
            (user_id, source, source_id),
        ).fetchone()
        if row:
            return {
                "last_page": row["last_page"],
                "total_pages": row["total_pages"],
                "updated_at": row["updated_at"],
            }
        return None



def set_user_progress(
    user_id: str,
    source: str,
    source_id: str,
    last_page: int,
    total_pages: int = 0,
) -> dict[str, Any]:
    now = int(time.time())
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO user_reading_progress (user_id, source, source_id, last_page, total_pages, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, source, source_id) DO UPDATE SET
                last_page = excluded.last_page,
                total_pages = CASE WHEN excluded.total_pages > 0 THEN excluded.total_pages ELSE user_reading_progress.total_pages END,
                updated_at = excluded.updated_at
            """,
            (user_id, source, source_id, last_page, total_pages, now),
        )
        conn.commit()
    return {
        "last_page": last_page,
        "total_pages": total_pages,
        "updated_at": now,
    }

