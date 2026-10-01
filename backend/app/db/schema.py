from __future__ import annotations

import json
import logging
import sqlite3
import time
from pathlib import Path

from ..formatting import normalize_title
from .connection import (
    get_data_dir,
    get_db,
    get_db_path,
    get_dialogue_db,
    get_dialogue_db_path,
    set_db_path,
    set_dialogue_db_path,
)
from .index import rebuild_facets_snapshot
from .dialogues import sync_comic_dialogues

logger = logging.getLogger(__name__)

def init_db(db_path: Path | None = None) -> None:
    if db_path is not None:
        set_db_path(db_path)

    get_db_path().parent.mkdir(parents=True, exist_ok=True)
    with get_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS guest_passes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                token TEXT UNIQUE NOT NULL,
                pin_hash TEXT NOT NULL DEFAULT '',
                pin_salt TEXT NOT NULL DEFAULT '',
                expires_at INTEGER,
                is_active INTEGER NOT NULL DEFAULT 1,
                max_devices INTEGER NOT NULL DEFAULT 2,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_guest_passes_token ON guest_passes(token);

            CREATE TABLE IF NOT EXISTS guest_devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pass_id INTEGER NOT NULL,
                device_token TEXT UNIQUE NOT NULL,
                device_name TEXT NOT NULL,
                user_agent TEXT NOT NULL DEFAULT '',
                last_ip TEXT NOT NULL DEFAULT '',
                created_at INTEGER NOT NULL,
                last_active_at INTEGER NOT NULL,
                FOREIGN KEY (pass_id) REFERENCES guest_passes(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_guest_devices_token ON guest_devices(device_token);
            CREATE INDEX IF NOT EXISTS idx_guest_devices_pass ON guest_devices(pass_id);

            CREATE TABLE IF NOT EXISTS user_favorites (
                user_id TEXT NOT NULL,
                source TEXT NOT NULL,
                source_id TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                PRIMARY KEY (user_id, source, source_id)
            );
            CREATE INDEX IF NOT EXISTS idx_user_favorites_user ON user_favorites(user_id);

            CREATE TABLE IF NOT EXISTS user_reading_progress (
                user_id TEXT NOT NULL,
                source TEXT NOT NULL,
                source_id TEXT NOT NULL,
                last_page INTEGER NOT NULL,
                total_pages INTEGER NOT NULL DEFAULT 0,
                updated_at INTEGER NOT NULL,
                PRIMARY KEY (user_id, source, source_id)
            );
            CREATE INDEX IF NOT EXISTS idx_user_progress_user ON user_reading_progress(user_id);

            CREATE TABLE IF NOT EXISTS comics_index (
                source TEXT NOT NULL,
                source_id TEXT NOT NULL,
                display_id TEXT NOT NULL,
                title TEXT NOT NULL,
                authors_json TEXT NOT NULL DEFAULT '[]',
                works_json TEXT NOT NULL DEFAULT '[]',
                actors_json TEXT NOT NULL DEFAULT '[]',
                tags_json TEXT NOT NULL DEFAULT '[]',
                chapter_titles_json TEXT NOT NULL DEFAULT '[]',
                page_count INTEGER NOT NULL DEFAULT 0,
                cached_pages INTEGER NOT NULL DEFAULT 0,
                cover_count INTEGER NOT NULL DEFAULT 4,
                cover_indices_json TEXT NOT NULL DEFAULT '[]',
                views TEXT NOT NULL DEFAULT '',
                likes TEXT NOT NULL DEFAULT '',
                uploaded_at TEXT NOT NULL DEFAULT '',
                published_at TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL DEFAULT '',
                imported_at TEXT NOT NULL DEFAULT '',
                hidden_from_guest INTEGER NOT NULL DEFAULT 0,
                mtime REAL NOT NULL DEFAULT 0.0,
                auto_update_interval_days INTEGER NOT NULL DEFAULT 15,
                last_auto_checked_at TEXT NOT NULL DEFAULT '',
                normalized_title TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (source, source_id)
            );
            CREATE INDEX IF NOT EXISTS idx_comics_index_imported ON comics_index(imported_at DESC);
            CREATE INDEX IF NOT EXISTS idx_comics_index_source ON comics_index(source);
            CREATE INDEX IF NOT EXISTS idx_comics_index_title ON comics_index(title);
            CREATE INDEX IF NOT EXISTS idx_comics_index_pages ON comics_index(page_count DESC);
            CREATE INDEX IF NOT EXISTS idx_comics_index_cached ON comics_index(cached_pages DESC);

            CREATE TABLE IF NOT EXISTS direct_passes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token TEXT UNIQUE NOT NULL,
                source TEXT NOT NULL,
                source_id TEXT NOT NULL,
                page_index INTEGER NOT NULL DEFAULT 1,
                created_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_direct_passes_token ON direct_passes(token);
            CREATE INDEX IF NOT EXISTS idx_direct_passes_expires ON direct_passes(expires_at);

            CREATE TABLE IF NOT EXISTS library_stats_snapshot (
                scope TEXT PRIMARY KEY,
                total_books INTEGER NOT NULL DEFAULT 0,
                total_pages INTEGER NOT NULL DEFAULT 0,
                cached_pages INTEGER NOT NULL DEFAULT 0,
                updated_at REAL NOT NULL DEFAULT 0.0
            );

            CREATE TABLE IF NOT EXISTS library_tag_counts (
                scope TEXT NOT NULL,
                tag TEXT NOT NULL,
                cnt INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (scope, tag)
            );
            CREATE INDEX IF NOT EXISTS idx_tag_counts_rank ON library_tag_counts(scope, cnt DESC, tag ASC);
            """
        )
        # Migrations: ensure max_devices, pin_hash, pin_salt columns exist for existing DB
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(guest_passes)").fetchall()]
        if "max_devices" not in cols:
            conn.execute("ALTER TABLE guest_passes ADD COLUMN max_devices INTEGER NOT NULL DEFAULT 2")
        if "pin_hash" not in cols:
            conn.execute("ALTER TABLE guest_passes ADD COLUMN pin_hash TEXT NOT NULL DEFAULT ''")
        if "pin_salt" not in cols:
            conn.execute("ALTER TABLE guest_passes ADD COLUMN pin_salt TEXT NOT NULL DEFAULT ''")

        # Migrations for comics_index: auto_update_interval_days, last_auto_checked_at, normalized_title
        c_cols = [r["name"] for r in conn.execute("PRAGMA table_info(comics_index)").fetchall()]
        if "auto_update_interval_days" not in c_cols:
            conn.execute("ALTER TABLE comics_index ADD COLUMN auto_update_interval_days INTEGER NOT NULL DEFAULT 15")
        if "last_auto_checked_at" not in c_cols:
            conn.execute("ALTER TABLE comics_index ADD COLUMN last_auto_checked_at TEXT NOT NULL DEFAULT ''")
        if "normalized_title" not in c_cols:
            conn.execute("ALTER TABLE comics_index ADD COLUMN normalized_title TEXT NOT NULL DEFAULT ''")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_comics_index_norm_title ON comics_index(normalized_title)")

        # Ensure normalized_title is backfilled for any existing entries
        empty_norm_rows = conn.execute("SELECT source, source_id, title FROM comics_index WHERE normalized_title = '' AND title != ''").fetchall()
        if empty_norm_rows:
            updates = [(normalize_title(r["title"]), r["source"], r["source_id"]) for r in empty_norm_rows]
            conn.executemany("UPDATE comics_index SET normalized_title = ? WHERE source = ? AND source_id = ?", updates)

        # Ensure facets snapshot is populated on cold start / first migration
        snap_count = conn.execute("SELECT COUNT(*) as cnt FROM library_stats_snapshot").fetchone()
        if not snap_count or int(snap_count["cnt"]) == 0:
            rebuild_facets_snapshot(conn)

        conn.commit()

    # 初始化并确保独立的台词专库 (comic_dialogues.db) 就绪
    init_dialogue_db(get_dialogue_db_path())


_CREATE_DIALOGUES_FTS = """
    CREATE VIRTUAL TABLE IF NOT EXISTS comic_dialogues_fts USING fts5(
        source UNINDEXED,
        source_id UNINDEXED,
        page_index UNINDEXED,
        bubble_id UNINDEXED,
        text UNINDEXED,
        lang UNINDEXED,
        box_json UNINDEXED,
        reading_order UNINDEXED,
        kind UNINDEXED,
        text_norm,
        tokenize='trigram'
    );
"""

# 倒排只建在 text_norm（写入侧折成简体字形）上，text 退为 UNINDEXED 的原文副本：
# 查繁查简都命中，返回的仍是页面上那套字形（zh_conv 逐字符 1:1，偏移不变）。
# 新增列只能追加在末尾：FTS5 不支持 ALTER ADD COLUMN，缺列即整表重建（见 _migrate_dialogue_schema）。
_DIALOGUE_COLUMNS = {
    "source",
    "source_id",
    "page_index",
    "bubble_id",
    "text",
    "lang",
    "box_json",
    "reading_order",
    "kind",
    "text_norm",
}


def _migrate_dialogue_schema(conn: sqlite3.Connection) -> bool:
    """FTS5 虚拟表不支持 ALTER TABLE ADD COLUMN，缺任何一列都只能整表重建。

    comic_dialogues_fts 是 pages/*.ocr.json 的派生索引，删表不丢原始数据。但必须
    在同一事务里清空 comic_ocr_sync_meta：sync_comic_dialogues 靠 mtime 比对做增量，
    元数据若留着，重灌会被静默跳过，台词检索从此永远返回空。

    Returns:
        True 表示确实重建了表，调用方必须回填，否则台词检索静默返 0、与「无匹配」不可区分。
    """
    columns = {row[1] for row in conn.execute("PRAGMA table_info(comic_dialogues_fts)")}
    if not columns or _DIALOGUE_COLUMNS <= columns:
        return False

    missing = sorted(_DIALOGUE_COLUMNS - columns)
    # get_dialogue_db 是默认事务模式，DDL 不会隐式开事务，DROP 与 CREATE 会各自自动提交。
    # 不显式 BEGIN 的话，中途崩掉会留下"新表已建、元数据仍说已同步"，下次启动列齐了不再重建
    conn.execute("BEGIN")
    conn.execute("DROP TABLE comic_dialogues_fts")
    conn.execute(_CREATE_DIALOGUES_FTS)
    conn.execute("DELETE FROM comic_ocr_sync_meta")
    conn.commit()
    logger.warning(
        "Rebuilt comic_dialogues_fts to add %s and reset OCR sync metadata; dialogue index is empty until backfill",
        missing,
    )
    return True


def backfill_dialogue_index() -> int:
    """整表重建后遍历书库，把所有带伴生 OCR 文件的漫画重灌回索引。

    空索引与「这本书没有这句台词」在接口上无法区分，所以回填必须紧跟重建（错题本 #136）。
    """
    library_dir = get_data_dir() / "library"
    if not library_dir.is_dir():
        return 0

    total = 0
    for source_dir in sorted(p for p in library_dir.iterdir() if p.is_dir()):
        for comic_dir in sorted(p for p in source_dir.iterdir() if p.is_dir()):
            pages_dir = comic_dir / "pages"
            if not pages_dir.is_dir() or not any(pages_dir.glob("**/*.ocr.json")):
                continue
            try:
                total += sync_comic_dialogues(source_dir.name, comic_dir.name, force=True)
            except Exception as exc:
                logger.warning("台词索引回填失败 %s/%s: %s", source_dir.name, comic_dir.name, exc)
    return total


def init_dialogue_db(dialogue_db_path: Path | None = None) -> None:
    """初始化独立的台词全文检索专库 (comic_dialogues.db)，整表重建后就地回填，新列为 NULL 的书按书重灌。"""
    if dialogue_db_path is not None:
        set_dialogue_db_path(dialogue_db_path)

    get_dialogue_db_path().parent.mkdir(parents=True, exist_ok=True)
    rebuilt = False
    with get_dialogue_db() as conn:
        conn.executescript(
            f"""
            {_CREATE_DIALOGUES_FTS}

            CREATE TABLE IF NOT EXISTS comic_ocr_sync_meta (
                source TEXT NOT NULL,
                source_id TEXT NOT NULL,
                last_synced_mtime REAL NOT NULL DEFAULT 0.0,
                dialogue_count INTEGER NOT NULL DEFAULT 0,
                updated_at INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (source, source_id)
            );

            CREATE TABLE IF NOT EXISTS comic_dialogue_vectors (
                source TEXT NOT NULL,
                source_id TEXT NOT NULL,
                page_index INTEGER NOT NULL,
                bubble_id TEXT NOT NULL,
                dim INTEGER NOT NULL,
                vec BLOB NOT NULL,
                updated_at INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (source, source_id, page_index, bubble_id)
            );

            CREATE TABLE IF NOT EXISTS comic_dialogue_vectors_version (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                version INTEGER NOT NULL
            );
            INSERT OR IGNORE INTO comic_dialogue_vectors_version (id, version) VALUES (1, 0);
            """
        )
        rebuilt = _migrate_dialogue_schema(conn)
        # 列齐了不会触发重建，只能按行认出热重载用旧 INSERT 回填的半成品（错题本 #145）：清掉它们的元数据，下面逐本重灌
        half_synced = conn.execute(
            "SELECT DISTINCT source, source_id FROM comic_dialogues_fts WHERE kind IS NULL OR text_norm IS NULL"
        ).fetchall()
        conn.executemany(
            "DELETE FROM comic_ocr_sync_meta WHERE source = ? AND source_id = ?",
            [(r["source"], r["source_id"]) for r in half_synced],
        )
        conn.commit()

    if rebuilt:
        restored = backfill_dialogue_index()
        logger.warning("comic_dialogues_fts 重建完毕，已回填 %d 条台词", restored)
    for r in half_synced:
        try:
            sync_comic_dialogues(r["source"], r["source_id"], force=True)
        except Exception as exc:
            logger.warning("台词索引半截迁移重灌失败 %s/%s: %s", r["source"], r["source_id"], exc)
    if half_synced:
        logger.warning("发现 %d 本台词索引新列为 NULL（错题本 #145），已按书重灌", len(half_synced))

