from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import secrets
import sqlite3
import string
import threading
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from .abuse import (
    clear_cooling_lock,
    clear_pin_failures,
    clear_rate_limit,
    is_eviction_cooling_locked,
    is_pass_rate_limited,
    record_eviction_and_check_lock,
)
from .config import DATA_DIR
from .zh_conv import to_simplified

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = DATA_DIR / "comic_shelf.db"
_DB_PATH: Path = DEFAULT_DB_PATH

DEFAULT_DIALOGUE_DB_PATH = DATA_DIR / "comic_dialogues.db"
_DIALOGUE_DB_PATH: Path = DEFAULT_DIALOGUE_DB_PATH

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


def set_db_path(path: Path) -> None:
    global _DB_PATH, _DIALOGUE_DB_PATH
    _DB_PATH = path
    if "comic_shelf" in path.name:
        _DIALOGUE_DB_PATH = path.parent / path.name.replace("comic_shelf", "comic_dialogues")
    else:
        _DIALOGUE_DB_PATH = path.parent / f"{path.stem}_dialogues.db"
    invalidate_facets_cache(force=True)


def get_db_path() -> Path:
    return _DB_PATH


def set_dialogue_db_path(path: Path) -> None:
    global _DIALOGUE_DB_PATH
    _DIALOGUE_DB_PATH = path


def get_dialogue_db_path() -> Path:
    return _DIALOGUE_DB_PATH


@contextmanager
def get_dialogue_db() -> Iterator[sqlite3.Connection]:
    _DIALOGUE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DIALOGUE_DB_PATH, timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    try:
        with conn:
            yield conn
    finally:
        conn.close()


@contextmanager
def get_db() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(_DB_PATH, timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def hash_pin(pin: str, salt: str = "") -> tuple[str, str]:
    if not salt:
        salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", pin.strip().encode("utf-8"), salt.encode("utf-8"), 100_000).hex()
    return h, salt


def verify_pin(pin: str, pin_hash: str, salt: str) -> bool:
    if not pin_hash or not salt or not pin:
        return False
    # Standard PBKDF2 verification (100,000 rounds)
    h_pbkdf2, _ = hash_pin(pin.strip(), salt)
    if secrets.compare_digest(h_pbkdf2, pin_hash):
        return True
    # Legacy single-round SHA-256 fallback for migration compatibility
    h_legacy = hashlib.sha256(f"{salt}:{pin.strip()}".encode("utf-8")).hexdigest()
    return secrets.compare_digest(h_legacy, pin_hash)


_INVISIBLE_OR_OVERRIDE_CHARS = frozenset(
    "\u200B\u200C\u200D\uFEFF\u202A\u202B\u202C\u202D\u202E\u2066\u2067\u2068\u2069\u00A0"
)


def sanitize_username(name: str, max_length: int = 20) -> str:
    """Sanitizes visitor username against XSS tags, control characters, and formula injection:
    - Strips leading/trailing whitespace and normalizes consecutive spaces
    - Removes ASCII control characters (0x00-0x1F, 0x7F) and zero-width/bidi overrides
    - Strips HTML-sensitive brackets (<, >)
    - Strips spreadsheet formula trigger characters (=, +, -, @) if at the beginning
    - Truncates to max_length
    """
    if not name:
        return ""
    # Remove control characters, zero-width characters, and bidirectional override characters
    cleaned = "".join(
        ch for ch in name
        if ord(ch) >= 32 and ord(ch) != 127 and ch not in _INVISIBLE_OR_OVERRIDE_CHARS
    )
    # Normalize multiple whitespace into a single space
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    # Strip HTML brackets to prevent raw tag storage
    cleaned = cleaned.replace("<", "").replace(">", "")
    # Strip leading formula characters to prevent CSV injection
    cleaned = cleaned.lstrip("=+-@\t\r\n")
    return cleaned[:max_length].strip()


def init_db(db_path: Path | None = None) -> None:
    if db_path is not None:
        set_db_path(db_path)

    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
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

        # Migrations for comics_index: auto_update_interval_days, last_auto_checked_at
        c_cols = [r["name"] for r in conn.execute("PRAGMA table_info(comics_index)").fetchall()]
        if "auto_update_interval_days" not in c_cols:
            conn.execute("ALTER TABLE comics_index ADD COLUMN auto_update_interval_days INTEGER NOT NULL DEFAULT 15")
        if "last_auto_checked_at" not in c_cols:
            conn.execute("ALTER TABLE comics_index ADD COLUMN last_auto_checked_at TEXT NOT NULL DEFAULT ''")
        conn.commit()

    # 初始化并确保独立的台词专库 (comic_dialogues.db) 就绪
    init_dialogue_db(_DIALOGUE_DB_PATH)


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
    library_dir = DATA_DIR / "library"
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

    _DIALOGUE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
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


# ----------------------------------------------------------------------
# 访客通行证（Guest Pass）CRUD 与设备会话
# ----------------------------------------------------------------------

def parse_device_name(ua: str) -> str:
    if not ua:
        return "未知设备"
    ua_lower = ua.lower()

    # Platform
    platform = "未知系统"
    if "iphone" in ua_lower:
        platform = "iPhone"
    elif "ipad" in ua_lower:
        platform = "iPad"
    elif "android" in ua_lower:
        platform = "Android"
    elif "macintosh" in ua_lower or "mac os" in ua_lower:
        platform = "macOS"
    elif "windows" in ua_lower:
        platform = "Windows"
    elif "linux" in ua_lower:
        platform = "Linux"

    # Browser
    browser = "浏览器"
    if "micromessenger" in ua_lower:
        browser = "微信"
    elif "edg" in ua_lower:
        browser = "Edge"
    elif "chrome" in ua_lower or "crios" in ua_lower:
        browser = "Chrome"
    elif "safari" in ua_lower and "chrome" not in ua_lower and "crios" not in ua_lower:
        browser = "Safari"
    elif "firefox" in ua_lower or "fxios" in ua_lower:
        browser = "Firefox"

    return f"{platform} · {browser}"


def _row_to_pass(
    row: sqlite3.Row | dict[str, Any],
    devices: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    d = dict(row)
    now = int(time.time())
    expires_at = d.get("expires_at")
    is_expired = bool(expires_at is not None and now > expires_at)
    is_active = bool(d.get("is_active", 1))
    max_devices = int(d.get("max_devices", 2) or 2)
    dev_list = devices if devices is not None else []
    device_count = len(dev_list)
    is_claimed = bool(d.get("pin_hash"))

    if not is_active:
        activation_status = "disabled"
    elif is_expired:
        activation_status = "expired"
    elif device_count == 0:
        activation_status = "pending"
    elif device_count >= max_devices:
        activation_status = "full"
    else:
        activation_status = "active"

    return {
        "id": d["id"],
        "username": d["username"],
        "token": d["token"],
        "expires_at": expires_at,
        "is_active": is_active,
        "is_expired": is_expired,
        "is_claimed": is_claimed,
        "has_pin": is_claimed,
        "max_devices": max_devices,
        "device_count": device_count,
        "devices": dev_list,
        "activation_status": activation_status,
        "is_cooling_locked": is_eviction_cooling_locked(d["id"]),
        "is_rate_limited": is_pass_rate_limited(d["id"]),
        "created_at": d["created_at"],
        "updated_at": d["updated_at"],
    }


def create_guest_pass(
    username: str,
    expires_days: int | None = None,
    custom_token: str | None = None,
    expires_at: int | None = None,
    max_devices: int = 2,
    pin: str | None = None,
) -> dict[str, Any]:
    username = sanitize_username(username)
    if not username:
        raise ValueError("访客名称不能为空或包含非法字符")
    token = custom_token.strip() if custom_token and custom_token.strip() else secrets.token_hex(16)
    now = int(time.time())
    if expires_at is None and expires_days is not None:
        expires_at = now + expires_days * 86400
    safe_max_devices = max(1, min(5, max_devices))

    pin_h, pin_s = ("", "")
    if pin and pin.strip():
        p_str = pin.strip()
        if not (len(p_str) >= 4 and len(p_str) <= 6 and p_str.isdigit()):
            raise ValueError("PIN 码必须为 4~6 位纯数字")
        pin_h, pin_s = hash_pin(p_str)

    try:
        with get_db() as conn:
            cur = conn.execute(
                """
                INSERT INTO guest_passes (username, token, pin_hash, pin_salt, expires_at, is_active, max_devices, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?)
                """,
                (username, token, pin_h, pin_s, expires_at, safe_max_devices, now, now),
            )
            conn.commit()
            pass_id = cur.lastrowid
    except sqlite3.IntegrityError:
        raise ValueError("该通行口令已存在，请更换口令")

    return get_guest_pass_by_id(pass_id)  # type: ignore[return-value]


def claim_guest_pass(
    pass_id: int,
    pin: str,
    username: str | None = None,
) -> dict[str, Any]:
    pin_str = str(pin).strip()
    if not (len(pin_str) >= 4 and len(pin_str) <= 6 and pin_str.isdigit()):
        raise ValueError("PIN 码必须为 4~6 位纯数字")

    pass_item = get_guest_pass_by_id(pass_id)
    if pass_item is None:
        raise ValueError("通行证不存在")
    if not pass_item["is_active"]:
        raise ValueError("通行证已被停用")
    if pass_item["is_expired"]:
        raise ValueError("通行证已过期")
    if pass_item["is_claimed"]:
        raise ValueError("该通行证已被认领，请直接输入 PIN 码登入")

    h, salt = hash_pin(pin_str)
    now = int(time.time())
    if username and username.strip():
        sanitized = sanitize_username(username)
        new_username = sanitized or pass_item["username"]
    else:
        new_username = pass_item["username"]

    with get_db() as conn:
        cur = conn.execute(
            """
            UPDATE guest_passes
            SET pin_hash = ?, pin_salt = ?, username = ?, updated_at = ?
            WHERE id = ? AND (pin_hash = '' OR pin_hash IS NULL)
            """,
            (h, salt, new_username, now, pass_id),
        )
        conn.commit()
        if cur.rowcount == 0:
            raise ValueError("该通行证已被认领，请直接输入 PIN 码登入")

    return get_guest_pass_by_id(pass_id)  # type: ignore[return-value]


def verify_guest_pass_pin(pass_id: int, pin: str) -> bool:
    with get_db() as conn:
        row = conn.execute("SELECT pin_hash, pin_salt FROM guest_passes WHERE id = ?", (pass_id,)).fetchone()
        if not row or not row["pin_hash"]:
            return False
        return verify_pin(pin, row["pin_hash"], row["pin_salt"])


def list_guest_passes() -> list[dict[str, Any]]:
    with get_db() as conn:
        pass_rows = conn.execute("SELECT * FROM guest_passes ORDER BY created_at DESC").fetchall()
        device_rows = conn.execute("SELECT * FROM guest_devices ORDER BY last_active_at DESC").fetchall()

        dev_map: dict[int, list[dict[str, Any]]] = {}
        for dr in device_rows:
            d = dict(dr)
            dev_map.setdefault(d["pass_id"], []).append(d)

        return [_row_to_pass(r, dev_map.get(r["id"], [])) for r in pass_rows]


def get_guest_pass_by_id(pass_id: int) -> dict[str, Any] | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM guest_passes WHERE id = ?", (pass_id,)).fetchone()
        if not row:
            return None
        dev_rows = conn.execute(
            "SELECT * FROM guest_devices WHERE pass_id = ? ORDER BY last_active_at DESC",
            (pass_id,),
        ).fetchall()
        return _row_to_pass(row, [dict(r) for r in dev_rows])


def get_guest_pass_by_token(token: str) -> dict[str, Any] | None:
    if not token or not token.strip():
        return None
    with get_db() as conn:
        row = conn.execute("SELECT * FROM guest_passes WHERE token = ?", (token.strip(),)).fetchone()
        if not row:
            return None
        pass_id = row["id"]
        dev_rows = conn.execute(
            "SELECT * FROM guest_devices WHERE pass_id = ? ORDER BY last_active_at DESC",
            (pass_id,),
        ).fetchall()
        return _row_to_pass(row, [dict(r) for r in dev_rows])


def update_guest_pass(
    pass_id: int,
    username: str | None = None,
    is_active: bool | None = None,
    extend_days: int | None = None,
    reset_token: bool = False,
    expires_days: int | None = None,
    max_devices: int | None = None,
    reset_pin: bool = False,
    custom_pin: str | None = None,
) -> dict[str, Any] | None:
    existing = get_guest_pass_by_id(pass_id)
    if existing is None:
        return None

    now = int(time.time())
    new_username = existing["username"]
    if username is not None:
        cleaned = sanitize_username(username)
        if not cleaned:
            raise ValueError("访客名称不能为空或包含非法字符")
        new_username = cleaned
    new_is_active = int(is_active) if is_active is not None else (1 if existing["is_active"] else 0)
    new_token = secrets.token_hex(16) if reset_token else existing["token"]
    new_max_devices = max(1, min(5, max_devices)) if max_devices is not None else existing["max_devices"]

    with get_db() as conn:
        row = conn.execute("SELECT pin_hash, pin_salt FROM guest_passes WHERE id = ?", (pass_id,)).fetchone()
        current_pin_hash = row["pin_hash"] if row else ""
        current_pin_salt = row["pin_salt"] if row else ""

    if reset_pin:
        current_pin_hash = ""
        current_pin_salt = ""
    elif custom_pin is not None:
        p_str = custom_pin.strip()
        if p_str:
            if not (len(p_str) >= 4 and len(p_str) <= 6 and p_str.isdigit()):
                raise ValueError("PIN 码必须为 4~6 位纯数字")
            current_pin_hash, current_pin_salt = hash_pin(p_str)

    new_expires_at = existing["expires_at"]
    if expires_days is not None:
        new_expires_at = (now + expires_days * 86400) if expires_days > 0 else None
    elif extend_days is not None and extend_days > 0:
        base_time = now if (new_expires_at is None or new_expires_at < now) else new_expires_at
        new_expires_at = base_time + extend_days * 86400

    try:
        with get_db() as conn:
            conn.execute(
                """
                UPDATE guest_passes
                SET username = ?, token = ?, pin_hash = ?, pin_salt = ?, expires_at = ?, is_active = ?, max_devices = ?, updated_at = ?
                WHERE id = ?
                """,
                (new_username, new_token, current_pin_hash, current_pin_salt, new_expires_at, new_is_active, new_max_devices, now, pass_id),
            )
            if reset_token or reset_pin:
                # Token or PIN changed: invalidate all active devices for this pass and clear locks
                conn.execute("DELETE FROM guest_devices WHERE pass_id = ?", (pass_id,))
                clear_cooling_lock(pass_id)
                clear_rate_limit(pass_id)
                clear_pin_failures(pass_id)
            elif max_devices is not None:
                # If quota shrunk below current device count, evict oldest devices
                dev_rows = conn.execute(
                    "SELECT id FROM guest_devices WHERE pass_id = ? ORDER BY last_active_at ASC, id ASC",
                    (pass_id,),
                ).fetchall()
                while len(dev_rows) > new_max_devices:
                    oldest_id = dev_rows.pop(0)["id"]
                    conn.execute("DELETE FROM guest_devices WHERE id = ?", (oldest_id,))

            conn.commit()
    except sqlite3.IntegrityError:
        raise ValueError("该通行口令已存在，请更换口令")

    return get_guest_pass_by_id(pass_id)


def delete_guest_pass(pass_id: int) -> bool:
    clear_cooling_lock(pass_id)
    clear_rate_limit(pass_id)
    clear_pin_failures(pass_id)
    with get_db() as conn:
        conn.execute("DELETE FROM guest_devices WHERE pass_id = ?", (pass_id,))
        conn.execute("DELETE FROM user_favorites WHERE user_id = ?", (f"guest:{pass_id}",))
        conn.execute("DELETE FROM user_reading_progress WHERE user_id = ?", (f"guest:{pass_id}",))
        cur = conn.execute("DELETE FROM guest_passes WHERE id = ?", (pass_id,))
        conn.commit()
        return cur.rowcount > 0


# ----------------------------------------------------------------------
# 访客物理设备会话（Guest Devices & LRU Eviction）
# ----------------------------------------------------------------------

_device_register_lock = threading.Lock()


def register_guest_device(
    pass_id: int,
    user_agent: str = "",
    ip: str = "",
) -> dict[str, Any]:
    now = int(time.time())
    with _device_register_lock:
        with get_db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            pass_row = conn.execute("SELECT * FROM guest_passes WHERE id = ?", (pass_id,)).fetchone()
            if not pass_row:
                raise ValueError("通行证不存在")
            pass_dict = dict(pass_row)
            if not pass_dict["is_active"]:
                raise ValueError("通行证已被停用")
            if pass_dict["expires_at"] and now > pass_dict["expires_at"]:
                raise ValueError("通行证已过期")

            max_devices = int(pass_dict.get("max_devices", 2) or 2)

            # LRU eviction: if devices count >= max_devices, delete oldest
            dev_rows = conn.execute(
                "SELECT id FROM guest_devices WHERE pass_id = ? ORDER BY last_active_at ASC, id ASC",
                (pass_id,),
            ).fetchall()

            if len(dev_rows) >= max_devices and is_eviction_cooling_locked(pass_id):
                raise ValueError("该通行证近期设备置换过于频繁，已触发安全保护锁定 10 分钟，暂不允许新设备接入")

            while len(dev_rows) >= max_devices:
                oldest_id = dev_rows.pop(0)["id"]
                conn.execute("DELETE FROM guest_devices WHERE id = ?", (oldest_id,))
                record_eviction_and_check_lock(pass_id)

            token = secrets.token_hex(24)
            safe_ua = str(user_agent) if isinstance(user_agent, str) else ""
            safe_ip = str(ip) if isinstance(ip, str) else ""
            name = parse_device_name(safe_ua)
            cur = conn.execute(
                """
                INSERT INTO guest_devices (pass_id, device_token, device_name, user_agent, last_ip, created_at, last_active_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (pass_id, token, name, safe_ua, safe_ip, now, now),
            )
            conn.commit()
            dev_id = cur.lastrowid
            row = conn.execute("SELECT * FROM guest_devices WHERE id = ?", (dev_id,)).fetchone()
            return dict(row)


def get_device_by_token(device_token: str) -> dict[str, Any] | None:
    if not device_token or not device_token.strip():
        return None
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT d.*, p.username, p.token as pass_token, p.is_active as pass_is_active,
                   p.expires_at as pass_expires_at, p.max_devices
            FROM guest_devices d
            JOIN guest_passes p ON d.pass_id = p.id
            WHERE d.device_token = ?
            """,
            (device_token.strip(),),
        ).fetchone()
        return dict(row) if row else None


def touch_device_active(device_id: int, ip: str = "") -> None:
    now = int(time.time())
    with get_db() as conn:
        if ip:
            conn.execute(
                "UPDATE guest_devices SET last_active_at = ?, last_ip = ? WHERE id = ?",
                (now, ip, device_id),
            )
        else:
            conn.execute(
                "UPDATE guest_devices SET last_active_at = ? WHERE id = ?",
                (now, device_id),
            )
        conn.commit()


def delete_guest_device(device_id: int, pass_id: int | None = None) -> bool:
    with get_db() as conn:
        if pass_id is not None:
            cur = conn.execute("DELETE FROM guest_devices WHERE id = ? AND pass_id = ?", (device_id, pass_id))
        else:
            cur = conn.execute("DELETE FROM guest_devices WHERE id = ?", (device_id,))
        conn.commit()
        return cur.rowcount > 0


# ----------------------------------------------------------------------
# 用户专属喜欢（User Favorites）
# ----------------------------------------------------------------------

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


# ----------------------------------------------------------------------
# 藏书影子索引（comics_index）操作与查询
# ----------------------------------------------------------------------

def upsert_comic_index(item: dict[str, Any]) -> None:
    """插入或更新漫画影子索引记录。"""
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO comics_index (
                source, source_id, display_id, title,
                authors_json, works_json, actors_json, tags_json, chapter_titles_json,
                page_count, cached_pages, cover_count, cover_indices_json,
                views, likes, uploaded_at, published_at, updated_at, imported_at,
                hidden_from_guest, mtime, auto_update_interval_days, last_auto_checked_at
            ) VALUES (
                :source, :source_id, :display_id, :title,
                :authors_json, :works_json, :actors_json, :tags_json, :chapter_titles_json,
                :page_count, :cached_pages, :cover_count, :cover_indices_json,
                :views, :likes, :uploaded_at, :published_at, :updated_at, :imported_at,
                :hidden_from_guest, :mtime, :auto_update_interval_days, :last_auto_checked_at
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
                last_auto_checked_at = excluded.last_auto_checked_at
            """,
            item,
        )
        conn.commit()
    invalidate_facets_cache()


def purge_comic_db_records(source: str, source_id: str) -> bool:
    """彻底级联清理指定漫画在 SQLite 数据库中的所有关联记录：
    1. 影子索引 (comics_index)
    2. 用户喜欢标记 (user_favorites)
    3. 用户阅读进度 (user_reading_progress)
    4. 单本沙箱专属通行证 (direct_passes)
    5. 台词全文检索与 OCR 同步元数据 (comic_dialogues_fts, comic_ocr_sync_meta)
    """
    purged = False
    with get_db() as conn:
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
    """获取索引库中所有已记录条目的 (source, source_id) -> mtime 映射。"""
    with get_db() as conn:
        rows = conn.execute("SELECT source, source_id, mtime FROM comics_index").fetchall()
        return {(r["source"], r["source_id"]): float(r["mtime"]) for r in rows}


def get_comic_index_count() -> int:
    """获取当前已建立影子索引的漫画总数。"""
    with get_db() as conn:
        row = conn.execute("SELECT COUNT(*) as cnt FROM comics_index").fetchone()
        return int(row["cnt"]) if row else 0


def update_comic_cached_pages(source: str, source_id: str, cached_pages: int) -> None:
    """当后台单页缓存推进时，快速更新影子索引中的 cached_pages 计数值。"""
    with get_db() as conn:
        conn.execute(
            "UPDATE comics_index SET cached_pages = ? WHERE source = ? AND source_id = ?",
            (cached_pages, source, source_id),
        )
        conn.commit()


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


def query_library_index(
    user_id: str,
    is_curator: bool,
    page: int = 1,
    page_size: int = 24,
    status: str = "all",
    favorite: bool = False,
    source: str | None = None,
    q: str | None = None,
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
        from .zh_conv import expand_search_variants

        groups = []
        for i, v in enumerate([v for v in expand_search_variants(raw_q) if v]):
            p_key = f"needle_{i}"
            params[p_key] = f"%{_escape_like(v)}%"
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

    order_sql = "ORDER BY ci.imported_at DESC, ci.source ASC, ci.source_id ASC"
    if sort == "recent":
        order_sql = """ORDER BY
            CASE
                WHEN COALESCE(urp.last_page, 0) >= ci.page_count AND ci.page_count > 0 THEN 1
                ELSE 0
            END ASC,
            ci.imported_at DESC,
            ci.source ASC,
            ci.source_id ASC"""
    elif sort == "title":
        order_sql = "ORDER BY ci.title COLLATE NOCASE ASC, ci.imported_at DESC, ci.source ASC, ci.source_id ASC"
    elif sort == "pages":
        order_sql = "ORDER BY ci.page_count DESC, ci.imported_at DESC, ci.source ASC, ci.source_id ASC"
    elif sort == "cached":
        order_sql = "ORDER BY (CAST(ci.cached_pages AS REAL) / MAX(ci.page_count, 1)) DESC, ci.imported_at DESC, ci.source ASC, ci.source_id ASC"

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
    conditions: list[str] = []
    params: dict[str, Any] = {}
    if not is_curator:
        conditions.append("ci.hidden_from_guest = 0")
    if source:
        conditions.append("ci.source = :source")
        params["source"] = source

    where_sql = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    stats_sql = f"""
        SELECT
            COUNT(*) as total_books,
            COALESCE(SUM(page_count), 0) as total_pages,
            COALESCE(SUM(cached_pages), 0) as cached_pages
        FROM comics_index ci
        {where_sql}
    """

    tags_sql = f"""
        SELECT value as tag, COUNT(*) as cnt
        FROM comics_index ci, json_each(ci.tags_json)
        {where_sql}
        GROUP BY value
        ORDER BY cnt DESC
        LIMIT 30
    """

    with get_db() as conn:
        stats_row = conn.execute(stats_sql, params).fetchone()
        tag_rows = conn.execute(tags_sql, params).fetchall()
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

    具备进程级内存缓存与防击穿保护：
    1. 读操作：未发生写变动时 0ms 纯内存命中，彻底消除全表 json_each 扫库开销；
    2. 写操作：标记失效时间戳，写即失效，确保数据强一致性；
    3. 防击穿与防竞态：Double-checked locking 杜绝并发穿透，时间戳锚定计算前规避 TOCTOU 脏读。

    Args:
        is_curator: When False, excludes comics marked as hidden_from_guest from counts.
        source: Optional source filter to scope facets to a single provider.
        bypass_cache: When True, bypasses in-memory cache and recomputes directly.

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
        if not bypass_cache:
            with _facets_cache_lock:
                if key in _facets_cache:
                    cached_at, cached_data = _facets_cache[key]
                    if cached_at >= _last_facets_invalidated_at:
                        return _copy_facets(cached_data)

        compute_started_at = time.monotonic()
        result = _compute_library_facets(is_curator=is_curator, source=source)

        with _facets_cache_lock:
            if key not in _facets_cache and len(_facets_cache) >= 32:
                _facets_cache.pop(next(iter(_facets_cache)))
            _facets_cache[key] = (compute_started_at, result)

        return _copy_facets(result)


# ----------------------------------------------------------------------
# 台词全文索引（comic_dialogues_fts）同步与检索
# ----------------------------------------------------------------------

# 阅读器一次最多画几个气泡（代表气泡 + 同页其余命中气泡）；超出的只计入 bubble_count，免得撑长 URL、糊满画面
MAX_PAGE_BOXES = 6

# 只折 ASCII 大小写，与 LIKE 和 SQLite lower() 同一口径。不用 str.lower()：它会把个别字符
# 变长（'İ' → 'i̇'），折完的下标就对不回原文了
_ASCII_LOWER = str.maketrans(string.ascii_uppercase, string.ascii_lowercase)


def _normalize_box(raw: Any) -> list[float] | None:
    """把侧车里的 box 收敛成 4 个有限数值，形状不对就整条判废。

    只判长度拦不住 4 键 dict 与嵌套四点表，放过去会在响应模型校验时让检索端点 500。
    """
    if not isinstance(raw, list) or len(raw) != 4:
        return None
    out: list[float] = []
    for v in raw:
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            return None
        f = float(v)
        if not math.isfinite(f):
            return None
        out.append(f)
    return out


def _coerce_order_index(raw: Any, fallback: int) -> int:
    """把侧车里可能畸形（浮点、字符串、1e999、dict）的序号收敛成正整数。"""
    try:
        n = int(raw)
    except (TypeError, ValueError, OverflowError):
        return fallback
    return n if n >= 0 else fallback


def _make_snippet(raw: str, norm: str, needle: str, max_chars: int = 60) -> str:
    """摘要与高亮：在归一列里定位，按 1:1 偏移切回原文再加 `<mark>`。

    Args:
        raw: 入库时保留的**原文**（页面上那套字形），也是最终展示的内容。
        norm: 该行的归一文本（`to_simplified(raw)`），只用来定位。
        needle: 归一后的查询串，与 norm 同一套字形。
        max_chars: 定位失败时前缀摘要的长度。

    Returns:
        带 `<mark>` 的纯文本片段，前后按需补 `...`；由前台安全声明式解析，不拼 HTML。

    `to_simplified` 是逐字符 1:1 映射，norm 上的下标可原样切回 raw（ADR 0017 2026-09-23 修订）。
    定位不分 ASCII 大小写，与 trigram、LIKE 同一口径。
    """
    if not raw:
        return ""
    start = norm.translate(_ASCII_LOWER).find(needle.translate(_ASCII_LOWER)) if needle else -1
    if start < 0:
        return raw[:max_chars] + ("..." if len(raw) > max_chars else "")
    end = start + len(needle)
    head = max(0, start - 15)
    tail = min(len(raw), end + 35)
    marked = f"{raw[head:start]}<mark>{raw[start:end]}</mark>{raw[end:tail]}"
    prefix = "..." if head > 0 else ""
    suffix = "..." if tail < len(raw) else ""
    return f"{prefix}{marked}{suffix}"


DIALOGUE_KIND = "dialogue"
PARATEXT_KIND = "paratext"

# 书名页与版权页在书头，后记与通告在书尾：页位 + 特征词比几何轮廓判据可靠（ADR 0017 决策 7）
FRONT_MATTER_PAGES = 2
BACK_MATTER_PAGES = 4
# 短篇整本都是正文，位置规则对它没有意义；册页数不足此数时只认特征词。
MIN_PAGES_FOR_POSITION_RULE = 10
# 后记是成段的长文，正文页平均每句只有十来字，用它兜住没有特征词的后记页
BACK_MATTER_MEAN_LINE_CHARS = 25

# 水印与页码：真台词一定有中日文字形，纯拉丁/数字且极短的就是噪声（站点名的 OCR 变体列举不完）
_CJK_RE = re.compile(r"[぀-ヿ一-鿿＀-￯]")
NOISE_MAX_CHARS = 12
# 刻意不收「我是」「禁止」这类真台词里也常见的宽词
_PARATEXT_RE = re.compile(
    r"(图源|翻校|嵌字|扫图|校对|压制|汉化|翻译|仅供|转载|商业|邮箱|@[A-Za-z0-9]"
    r"|https?://|www\.|pixiv|fanbox|twitter|comiket|comic\s*market|qq群|群号|加群|微博"
    r"|后记|前言|附录|presented by|凳行|尧行|印刷)",
    re.IGNORECASE,
)


def _is_noise_line(text: str) -> bool:
    return not _CJK_RE.search(text) and len(text) <= NOISE_MAX_CHARS


def classify_dialogue_kind(
    page_index: int,
    page_count: int,
    page_texts: list[str],
    text: str,
) -> str | None:
    """判定一条 OCR 文本的语料类别。

    Args:
        page_index: 全书拍平后的全局页号（1 起）。
        page_count: 该漫画总页数；取不到时传 0，位置规则自动失效。
        page_texts: 同一页上的全部文本，用于判断整页是否像后记。
        text: 待判定的单条文本。

    Returns:
        'dialogue' 分镜台词、'paratext' 书名页/版权页/后记等副文本，
        None 表示纯噪声（水印、页码），不该进索引。
    """
    if _is_noise_line(text):
        return None
    if _PARATEXT_RE.search(text):
        return PARATEXT_KIND

    if page_count >= MIN_PAGES_FOR_POSITION_RULE:
        if page_index <= FRONT_MATTER_PAGES:
            return PARATEXT_KIND
        if page_index > page_count - BACK_MATTER_PAGES and page_texts:
            mean_line_chars = sum(len(t) for t in page_texts) / len(page_texts)
            long_form_page = mean_line_chars >= BACK_MATTER_MEAN_LINE_CHARS
            # 噪声行不能替整页定性：它本就不入库，正文页上同样满是水印（ADR 0017 决策 7 的 09-22 修正）
            credit_page = any(_PARATEXT_RE.search(t) for t in page_texts)
            if long_form_page or credit_page:
                return PARATEXT_KIND

    return DIALOGUE_KIND


def _dialogue_key(source: str, source_id: str) -> tuple[str, str]:
    """台词库的统一主键清洗：与存储层 `comic_dir()` 定位目录用的是同一套字符集。

    写行、增量元数据查表、删除三处必须走同一个函数，否则任一处用了未清洗的入参，
    同一本书就会在索引里挂到两个键上，删除时只清得掉一个。
    """

    def clean(v: object) -> str:
        s = re.sub(r"[^a-zA-Z0-9_\-\.]+", "_", str(v)).strip("._") or "_"
        while ".." in s:
            s = s.replace("..", "_")
        return s

    return clean(source), clean(source_id)


def sync_comic_dialogues(source: str, source_id: str, force: bool = False) -> int:
    """Syncs comic page OCR dialogues (*.ocr.json) into the comic_dialogues_fts table.

    Security sandbox and atomicity guarantees:
    1. Strictly sanitizes directory path symbols and bounds traversal within DATA_DIR.
    2. Atomically clears prior index rows for this comic before inserting new records.

    入库时按 classify_dialogue_kind 打上 kind：副文本只登记不检索，水印与页码直接丢弃。

    Args:
        source: Provider key (e.g., 'jm', 'picacg', 'local').
        source_id: Unique comic identifier.
        force: If True, bypasses mtime check and forces a full re-index.

    Returns:
        The total number of dialogue bubble records indexed.
    """
    safe_source, safe_id = _dialogue_key(source, source_id)
    # 找目录、写库、查元数据、删除统一用清洗后的键，否则会留下删不掉的孤儿语料（见 _dialogue_key）
    source, source_id = safe_source, safe_id

    data_resolved = DATA_DIR.resolve()
    candidates = [
        DATA_DIR / "library" / safe_source / safe_id / "pages",
        DATA_DIR / safe_source / safe_id / "pages",
        DATA_DIR / "library" / safe_source / safe_id,
    ]
    target_dir: Path | None = None
    for cand in candidates:
        try:
            cand_resolved = cand.resolve()
            if cand_resolved.is_relative_to(data_resolved) and cand_resolved.is_dir():
                target_dir = cand_resolved
                break
        except Exception:
            continue

    ocr_files: list[Path] = []
    if target_dir is not None:
        if target_dir.name == "pages":
            ocr_files = sorted(target_dir.glob("**/*.ocr.json"))
        else:
            pages_sub = target_dir / "pages"
            if pages_sub.is_dir():
                ocr_files = sorted(pages_sub.glob("**/*.ocr.json"))
            else:
                ocr_files = sorted(target_dir.glob("*.ocr.json"))

    latest_mtime: float = 0.0
    for f in ocr_files:
        try:
            mt = f.stat().st_mtime
            if mt > latest_mtime:
                latest_mtime = mt
        except OSError:
            pass

    # 增量检查放在解析之前：OCR 文件自上次入库以来没变就直接返回已有计数，不读不解析
    if not force:
        with get_dialogue_db() as conn:
            row = conn.execute(
                "SELECT last_synced_mtime, dialogue_count FROM comic_ocr_sync_meta WHERE source = ? AND source_id = ?",
                (source, source_id),
            ).fetchone()
            if row:
                stored_mtime = float(row["last_synced_mtime"])
                stored_count = int(row["dialogue_count"])
                # 当 OCR 文件未变动（或原本就无 OCR 文件且已同步记录为 0）时直接命中增量缓存
                if stored_mtime >= latest_mtime and (latest_mtime > 0 or stored_count == 0):
                    return stored_count

    # 读取 album.json 以便建立多章节全局页号映射
    page_map: dict[str, int] = {}
    page_count = 0
    album_candidates = []
    if target_dir is not None:
        if target_dir.name == "pages":
            album_candidates.append(target_dir.parent / "album.json")
        else:
            album_candidates.append(target_dir / "album.json")
    album_candidates.append(DATA_DIR / "library" / safe_source / safe_id / "album.json")
    for ac in album_candidates:
        try:
            ac_resolved = ac.resolve()
            if not ac_resolved.is_relative_to(data_resolved):
                continue
            if ac_resolved.is_file():
                meta_dict = json.loads(ac_resolved.read_text(encoding="utf-8"))
                pages = meta_dict.get("pages", [])
                try:
                    page_count = int(meta_dict.get("page_count") or len(pages))
                except (TypeError, ValueError, OverflowError):
                    page_count = len(pages)
                for p in pages:
                    idx_val = p.get("index")
                    f_val = p.get("file", "")
                    chap_val = p.get("chapter", "")
                    if idx_val is not None:
                        s = Path(f_val).stem
                        page_map[s] = int(idx_val)
                        if chap_val:
                            page_map[f"{chap_val}/{s}"] = int(idx_val)
                break
        except Exception:
            pass

    records: list[tuple[str, str, int, int | str, str, str, str, int, str, str]] = []
    for f in ocr_files:
        try:
            payload = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue

        page_idx: int | None = None
        if payload.get("page_index") is not None:
            try:
                page_idx = int(payload["page_index"])
            except (ValueError, TypeError, OverflowError):
                pass
        elif payload.get("page") is not None:
            try:
                page_idx = int(payload["page"])
            except (ValueError, TypeError, OverflowError):
                pass

        if page_idx is None:
            stem = f.name[:-9] if f.name.endswith(".ocr.json") else f.stem
            chap_stem = f"{f.parent.name}/{stem}"
            if chap_stem in page_map:
                page_idx = page_map[chap_stem]
            elif stem in page_map:
                page_idx = page_map[stem]
            elif stem.isdigit():
                page_idx = int(stem)
            else:
                m = re.search(r"\d+", stem)
                page_idx = int(m.group(0)) if m else 1

        top_lang = payload.get("lang") or "zh"
        bubbles = payload.get("bubbles", [])
        if not isinstance(bubbles, list):
            continue

        # 副文本判定要看整页：后记页上的单句可能很短，但它旁边的长句会暴露整页性质
        page_texts = [str(b.get("text", "")).strip() for b in bubbles if isinstance(b, dict)]
        page_texts = [t for t in page_texts if t]

        for b_idx, b in enumerate(bubbles, start=1):
            if not isinstance(b, dict):
                continue
            text = str(b.get("text", "")).strip()
            if not text:
                continue
            kind = classify_dialogue_kind(page_idx, page_count, page_texts, text)
            if kind is None:
                continue
            bubble_id = b.get("id", b_idx)
            if isinstance(bubble_id, bool) or not isinstance(bubble_id, (int, str)):
                bubble_id = b_idx
            lang = b.get("lang") or top_lang
            # 形状不合法的 box 存空数组：宁可丢坐标，不能让一行脏侧车毒化整条检索链路
            box = _normalize_box(b.get("box")) or []
            box_json = json.dumps(box, ensure_ascii=False)
            # 旧伴生文件没有 order，只能退回数组下标（其顺序为检测模型输出，并非阅读顺序）；
            # 这类文件需用 ocr_worker --force 重跑，才能拿到真正的 reading_order
            reading_order = _coerce_order_index(b.get("order"), b_idx)
            records.append(
                (
                    source,
                    source_id,
                    page_idx,
                    bubble_id,
                    text,
                    str(lang),
                    box_json,
                    reading_order,
                    kind,
                    to_simplified(text),
                )
            )

    with get_dialogue_db() as conn:
        conn.execute(
            "DELETE FROM comic_dialogues_fts WHERE source = ? AND source_id = ?",
            (source, source_id),
        )
        if records:
            conn.executemany(
                """
                INSERT INTO comic_dialogues_fts (
                    source, source_id, page_index, bubble_id, text, lang, box_json, reading_order, kind, text_norm
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                records,
            )
        conn.execute(
            """
            INSERT OR REPLACE INTO comic_ocr_sync_meta (
                source, source_id, last_synced_mtime, dialogue_count, updated_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (source, source_id, latest_mtime, len(records), int(time.time())),
        )

    # 向量重建放在 FTS 事务**外面**：模型冷启动可达秒级，扣着写锁会卡住关键词入库。
    # 失败只记日志：关键词已经提交，可选的语义腿出错不能把这次同步报成 500
    try:
        embed_comic_dialogues(source, source_id)
    except Exception as exc:
        logger.warning("台词向量重编失败 %s/%s: %s", source, source_id, exc)
    return len(records)


def delete_comic_dialogues(source: str, source_id: str) -> None:
    """删除指定漫画的所有台词全文索引与增量元数据。"""
    # 入参清洗与写入端对齐：调用方可能拿 URL 参数或 album.json 字段来删，不洗就删不掉
    source, source_id = _dialogue_key(source, source_id)
    with get_dialogue_db() as conn:
        conn.execute(
            "DELETE FROM comic_dialogues_fts WHERE source = ? AND source_id = ?",
            (source, source_id),
        )
        conn.execute(
            "DELETE FROM comic_ocr_sync_meta WHERE source = ? AND source_id = ?",
            (source, source_id),
        )
        conn.execute(
            "DELETE FROM comic_dialogue_vectors WHERE source = ? AND source_id = ?",
            (source, source_id),
        )
        _bump_vector_version(conn)


def _dialogue_comics_meta_map(keys: list[tuple[str, str]], user_id: str) -> dict[tuple[str, str], sqlite3.Row]:
    """跨库轻量关联：一次拿回这些书的元数据、访客隐藏标记与本人的收藏/阅读进度。

    关键词检索与语义检索共用同一份关联，两边返回的书名/封面/作者才不会长得不一样。
    收藏与进度走 LEFT JOIN 一次取全，与 `query_comics` 同一套写法。
    """
    comics_map: dict[tuple[str, str], sqlite3.Row] = {}
    if not keys:
        return comics_map
    where_or = " OR ".join(["(ci.source = ? AND ci.source_id = ?)"] * len(keys))
    flat_params: list[str] = [p for k in keys for p in k]
    sql_ci = f"""
        SELECT
            ci.source,
            ci.source_id,
            ci.display_id,
            ci.title,
            ci.cover_indices_json,
            ci.authors_json,
            ci.hidden_from_guest,
            ci.page_count,
            ci.views,
            ci.likes,
            (uf.user_id IS NOT NULL) AS is_favorite,
            COALESCE(urp.last_page, 0) AS last_page,
            urp.updated_at AS progress_at
        FROM comics_index ci
        LEFT JOIN user_favorites uf
            ON uf.source = ci.source AND uf.source_id = ci.source_id AND uf.user_id = ?
        LEFT JOIN user_reading_progress urp
            ON urp.source = ci.source AND urp.source_id = ci.source_id AND urp.user_id = ?
        WHERE {where_or}
    """
    with get_db() as shelf_conn:
        for row in shelf_conn.execute(sql_ci, [user_id, user_id, *flat_params]).fetchall():
            comics_map[(row["source"], row["source_id"])] = row
    return comics_map


def embed_comic_dialogues(source: str, source_id: str) -> int:
    """把一本书的对白行重编成语义向量写进 `comic_dialogue_vectors`。

    Returns:
        实际写入的向量条数。编码器不可用（没放模型、缺 numpy）时返回 0，不打断关键词链路——
        语义检索是增量能力。
    """
    from . import embedding

    dim = embedding.dim()
    source, source_id = _dialogue_key(source, source_id)
    rows: list[sqlite3.Row] = []
    if dim is not None:
        with get_dialogue_db() as conn:
            rows = conn.execute(
                "SELECT page_index, bubble_id, text FROM comic_dialogues_fts"
                " WHERE source = :source AND source_id = :source_id AND kind = :kind"
                "  AND length(text) >= :min_chars",
                {
                    "source": source,
                    "source_id": source_id,
                    "kind": DIALOGUE_KIND,
                    "min_chars": embedding.MIN_EMBED_CHARS,
                },
            ).fetchall()
    try:
        vectors = embedding.encode_documents([r["text"] for r in rows]) if rows else None
    except Exception as exc:
        # 编码中途出错按编码器不可用处理：旧向量同样对不上刚重写的 FTS 行，要一起删掉
        logger.warning("台词向量编码失败 %s/%s: %s", source, source_id, exc)
        vectors = None
    # 编不出新向量（编码器不可用、或这本书已没有可编的对白）就把旧的一并删掉：
    # FTS 行刚被重写，留着它们就是相似度按旧文本算、展示的却是新文本
    with get_dialogue_db() as conn:
        conn.execute(
            "DELETE FROM comic_dialogue_vectors WHERE source = ? AND source_id = ?",
            (source, source_id),
        )
        if vectors is not None:
            now = int(time.time())
            conn.executemany(
                "INSERT INTO comic_dialogue_vectors (source, source_id, page_index, bubble_id, dim, vec, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    (source, source_id, int(r["page_index"]), str(r["bubble_id"]), dim,
                     vectors[i].tobytes(), now)
                    for i, r in enumerate(rows)
                ],
            )
        _bump_vector_version(conn)
    return len(rows) if vectors is not None else 0


def rebuild_dialogue_vectors() -> dict[str, Any]:
    """全库重建台词向量：编码器就绪时把每条对白重新过一遍模型。"""
    from . import embedding

    dim = embedding.dim()
    if dim is None:
        return {"ok": False, "reason": "encoder_unavailable", "encoded": 0, "comics": 0}
    with get_dialogue_db() as conn:
        books = conn.execute(
            "SELECT DISTINCT source, source_id FROM comic_dialogues_fts WHERE kind = :kind",
            {"kind": DIALOGUE_KIND},
        ).fetchall()
    encoded = 0
    for b in books:
        try:
            encoded += embed_comic_dialogues(b["source"], b["source_id"])
        except Exception as exc:
            logger.warning("台词向量重建失败 %s/%s: %s", b["source"], b["source_id"], exc)
    logger.info("台词向量重建完成：%d 本 / %d 条", len(books), encoded)
    return {"ok": True, "reason": "", "encoded": encoded, "comics": len(books), "dim": dim}


def _vector_status() -> tuple[dict[str, Any], tuple[Any, ...]]:
    """语义腿的状态与向量矩阵的缓存戳子，一次查询同时给出。

    戳子是 (台词库路径, 写入版本号, 维度)：库路径让测试与"换库"读不到上一个库的矩阵；
    版本号记在库里，和向量写在同一个事务里推进，所以 `ocr.sh sync` 这类别的进程写完，
    服务不重启也能看到新矩阵，同一秒内重编、条数不变也不会读到旧矩阵。
    """
    from . import embedding

    dim = embedding.dim()
    with get_dialogue_db() as conn:
        row = conn.execute(
            "SELECT count(*) AS n, count(DISTINCT dim) AS dims, max(dim) AS dim,"
            " (SELECT version FROM comic_dialogue_vectors_version) AS version"
            " FROM comic_dialogue_vectors"
        ).fetchone()
    stored = int(row["n"] or 0)
    stored_dim = int(row["dim"] or 0) if stored else 0
    if dim is None:
        reason = "encoder_unavailable"
    elif stored == 0:
        reason = "vectors_missing"
    elif row["dims"] > 1 or stored_dim != dim:
        # 换过模型（维度不同）却没重建：新旧向量混在一堆里算余弦，分数会莫名其妙
        reason = "dim_mismatch"
    else:
        reason = ""
    status = {"available": reason == "", "reason": reason, "vectors": stored, "dim": stored_dim or (dim or 0)}
    return status, (str(_DIALOGUE_DB_PATH), row["version"], stored_dim)


def dialogue_vector_status() -> dict[str, Any]:
    """语义检索这条腿现在能不能走，以及为什么不能。"""
    return _vector_status()[0]


_VECTOR_CACHE: tuple[Any, ...] | None = None


def _bump_vector_version(conn: sqlite3.Connection) -> None:
    """写或删向量的事务里调用：版本号与向量一起提交，读者不会把旧矩阵记在新版本号下。"""
    conn.execute("UPDATE comic_dialogue_vectors_version SET version = version + 1")


def _vector_store(stamp: tuple[Any, ...], dim: int) -> tuple[list[tuple[str, str, int, str]], Any]:
    """取回 (键列表, 向量矩阵)，按 `_vector_status` 给的戳子做进程内缓存。

    不缓存的话每次检索都要重读全部 BLOB 再 np.stack，这是语义检索里最大的一笔开销。
    整体一次性赋值，不留"半个新矩阵被别的线程看见"的窗口。
    """
    global _VECTOR_CACHE
    if _VECTOR_CACHE is not None and _VECTOR_CACHE[0] == stamp:
        return _VECTOR_CACHE[1], _VECTOR_CACHE[2]
    with get_dialogue_db() as conn:
        rows = conn.execute(
            "SELECT source, source_id, page_index, bubble_id, vec FROM comic_dialogue_vectors WHERE dim = ?",
            (dim,),
        ).fetchall()

    import numpy as np

    keys = [(r["source"], r["source_id"], int(r["page_index"]), str(r["bubble_id"])) for r in rows]
    matrix = (
        np.stack([np.frombuffer(r["vec"], dtype=np.float32) for r in rows])
        if rows
        else np.zeros((0, dim), dtype=np.float32)
    )
    _VECTOR_CACHE = (stamp, keys, matrix)
    return keys, matrix


def search_dialogues_semantic(
    query: str,
    source: str | None = None,
    limit: int = 20,
    is_guest: bool = False,
    user_id: str = "",
) -> dict[str, Any]:
    """按意思找台词：把问题编码成向量，与语料向量取余弦近邻。

    与 `search_dialogues` 刻意分成两个出口（ADR 0028）：每页只留最相似的气泡、不吐 snippet；
    分数是 `similarity`（余弦，只在同一次查询内比高低），不复用 `rank_score`，也不掺业务信号。
    访客隐藏本与未收录本的过滤规则与关键词出口一致。

    Returns:
        `{"results": [...], "available": bool, "reason": str}`。没有分数下限，能检索时总会给出
        最近的若干页，所以"没走检索"只能靠 `reason` 说：`encoder_unavailable` /
        `vectors_missing` / `dim_mismatch` 时 `available` 为 False（这台机器走不了语义腿）；
        `query_too_short` 时 `available` 为 True（腿是好的，问题太短）；正常检索为空串。
    """
    from . import embedding

    status, stamp = _vector_status()
    if not status["available"]:
        return {"results": [], "available": False, "reason": status["reason"]}
    clean_query = (query or "").strip()
    if len(clean_query) < 2:
        return {"results": [], "available": True, "reason": "query_too_short"}
    qv = embedding.encode_query(clean_query)
    if qv is None:
        return {"results": [], "available": False, "reason": "encoder_unavailable"}

    limit = max(1, min(int(limit), 100))
    fetch_limit = min(max(limit * 5, 50), 200)

    keys_all, matrix = _vector_store(stamp, int(qv.shape[0]))
    import numpy as np

    # 书级过滤先于取前 K：访客隐藏本若等到取完才剔除，会白占名额让访客拿到的结果少于 limit
    book_keys = sorted({(k[0], k[1]) for k in keys_all if not source or k[0] == source})
    comics_map = _dialogue_comics_meta_map(book_keys, user_id)
    allowed = {
        b for b in book_keys
        if not is_guest or (comics_map.get(b) is not None and not comics_map[b]["hidden_from_guest"])
    }
    mask = np.fromiter(((k[0], k[1]) in allowed for k in keys_all), dtype=bool, count=len(keys_all))
    sims = np.where(mask, matrix @ qv, -np.inf)
    valid = int(mask.sum())

    # 同页只留相似度最高的气泡；按页去重后不够数就把 K 翻倍重取，直到够数或候选取尽
    hits: list[tuple[tuple[str, str, int, str], float]] = []
    pages: set[tuple[str, str, int]] = set()
    k = min(fetch_limit, valid)
    while k > 0:
        # 先按下标排再稳定排序：同分时保持入库顺序，与全量 argsort 的结果一致
        top = np.sort(np.argpartition(-sims, k - 1)[:k])
        hits, pages = [], set()
        for i in top[np.argsort(-sims[top], kind="stable")]:
            key = keys_all[int(i)]
            if key[:3] in pages:
                continue
            pages.add(key[:3])
            hits.append((key, float(sims[int(i)])))
            if len(hits) >= fetch_limit:
                break
        if len(hits) >= fetch_limit or k >= valid:
            break
        k = min(k * 2, valid)
    # 原文按气泡回表：向量表只存坐标外的最小信息，文本/框仍以 FTS 那行为准，
    # 避免两个表说同一句话的不同版本。
    texts: dict[tuple[str, str, int, str], sqlite3.Row] = {}
    if pages:
        clause = " OR ".join(["(f.source = ? AND f.source_id = ? AND f.page_index = ?)"] * len(pages))
        flat: list[Any] = [p for k in pages for p in k]
        with get_dialogue_db() as conn:
            for r in conn.execute(
                f"SELECT f.source, f.source_id, f.page_index, f.bubble_id, f.text, f.lang, f.box_json"
                f" FROM comic_dialogues_fts f WHERE ({clause}) AND f.kind = ?",
                [*flat, DIALOGUE_KIND],
            ).fetchall():
                texts[(r["source"], r["source_id"], int(r["page_index"]), str(r["bubble_id"]))] = r

    results: list[dict[str, Any]] = []
    for key, sim in hits:
        r = texts.get(key)
        if r is None:
            continue
        ci = comics_map.get((key[0], key[1]))
        results.append(
            {
                "source": key[0],
                "source_id": key[1],
                **_dialogue_book_fields(key[0], key[1], ci),
                "page_index": key[2],
                "bubble_id": r["bubble_id"],
                "text": r["text"] or "",
                # 与关键词出口同理：写入口已归一，读侧不再重复校验
                "box": json.loads(r["box_json"]),
                "lang": r["lang"] or "zh",
                "similarity": round(sim, 4),
            }
        )
        if len(results) >= limit:
            break
    return {"results": results, "available": True, "reason": ""}


def _safe_json_list(raw: Any) -> list[Any]:
    """元数据里的 JSON 数组字段：脏值一律退化成空表，不为了它把整次检索打断。"""
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except Exception:
        return []
    return value if isinstance(value, list) else []


def _dialogue_book_fields(src: str, sid: str, ci: sqlite3.Row | None) -> dict[str, Any]:
    """台词检索结果里按书派生的字段，关键词与语义两个出口共用；元数据缺失时退回书号本身。"""
    cover_indices = _safe_json_list(ci["cover_indices_json"]) if ci else []
    return {
        "display_id": ci["display_id"] if ci and ci["display_id"] else sid,
        "title": ci["title"] if ci and ci["title"] else sid,
        "cover": f"/api/library/{src}/{sid}/covers/{cover_indices[0] if cover_indices else 0}/file",
        "authors": _safe_json_list(ci["authors_json"]) if ci else [],
    }


def cleanup_orphan_comic_dialogues(data_dir: Path | None = None) -> int:
    """清理已从磁盘物理删除但仍残留在 FTS5、向量与元数据中的孤儿对白索引。"""
    if data_dir is None:
        data_dir = DATA_DIR
    data_resolved = data_dir.resolve()
    with get_dialogue_db() as conn:
        rows = conn.execute("SELECT DISTINCT source, source_id FROM comic_dialogues_fts").fetchall()

    to_delete: list[tuple[str, str]] = []
    for r in rows:
        src, sid = r["source"], r["source_id"]
        candidates = [
            data_resolved / "library" / src / sid,
            data_resolved / src / sid,
        ]
        if not any(c.is_dir() for c in candidates):
            to_delete.append((src, sid))

    if not to_delete:
        return 0

    with get_dialogue_db() as conn:
        for src, sid in to_delete:
            conn.execute("DELETE FROM comic_dialogues_fts WHERE source = ? AND source_id = ?", (src, sid))
            conn.execute("DELETE FROM comic_ocr_sync_meta WHERE source = ? AND source_id = ?", (src, sid))
            conn.execute(
                "DELETE FROM comic_dialogue_vectors WHERE source = ? AND source_id = ?", (src, sid)
            )
            logger.info("Cleaned orphan dialogue index for deleted comic %s/%s", src, sid)
        _bump_vector_version(conn)
    return len(to_delete)


def _escape_like(text: str) -> str:
    """转义 SQLite LIKE 查询中的特殊通配符 %、_ 与转义符自身。"""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _parse_metric_count(value: Any) -> int | None:
    """把 provider 侧的 "209K" / "9.9M" / "102" / "" 解析成整数；解析不出来回报 None。

    `comics_index.views` / `likes` 是上游站点的展示字符串，不是数字列。认不出就当"没有这个信号"，
    绝不当成 0：本地导入的本子没有站点热度，算成 0 阅读量等于替它们编一个。
    """
    text = str(value or "").strip().replace(",", "")
    if not text:
        return None
    m = re.fullmatch(r"(\d+(?:\.\d+)?)([km]?)", text, re.IGNORECASE)
    if not m:
        return None
    multiplier = {"": 1, "k": 1_000, "m": 1_000_000}[m.group(2).lower()]
    return int(float(m.group(1)) * multiplier)


def search_dialogues(
    query: str,
    source: str | None = None,
    limit: int = 20,
    is_guest: bool = False,
    user_id: str = "",
) -> list[dict[str, Any]]:
    """Search the dialogue FTS index, ordered by relevance fused with library signals and
    aggregated to page level.

    Short queries (< 2 chars) are blocked immediately to prevent unindexed table scans.
    Only `dialogue` rows surface here: 书名页/版权页/后记等副文本照样入库（kind='paratext'，
    供取料与语义召回使用），但它们不是台词，不该出现在台词检索结果里。

    Args:
        query: Full-text search string (folded once by `to_simplified`, matching the indexed `text_norm`).
        source: Optional source filter.
        limit: Maximum number of matched pages to return (1..100, default 20).
        is_guest: When True, filters out dialogue results from hidden_from_guest comics.
        user_id: Viewer identity used **for ordering only** — its favorites/reading progress
            feed the business signals below. Empty string or a user with no history simply
            yields zero lift, which is the "无信号退回纯相关度" case.

    Returns:
        One entry per matched page (at most `limit`), each carrying the page's best-scoring
        bubble as the representative snippet/box, `other_boxes` with up to `MAX_PAGE_BOXES - 1`
        further matched bubbles on that page for the reader to outline at once, plus
        `bubble_count` — how many bubbles on that page matched within the fetched candidate
        pool (not a corpus-wide total) — and `rank_score`, the representative bubble's relevance
        min-max normalized **within the caller-visible rows of this candidate pool** (0..1, higher
        is more relevant; only comparable inside one query, never across queries).
        3+ 字符的查询走 text_norm 上的 trigram 倒排并按 bm25 排序；2 字查询产不出任何
        trigram token，只能走 LIKE 扫描（按 词频 ÷ 文本长度 近似排序，即 bm25 中真正
        区分候选的那两项）。两条都在归一列上比，所以繁简输入命中同一批语料。

        截断留谁由 `rank_score` 加业务信号决定（推导见 `_rank_dialogue_pages` 与 ADR 0017 决策 9）。
        `bubble_count` 与身份无关；`rank_score` 的标尺只取调用者看得见的行，访客与馆长可能拿到
        不同的分数与顺序（错题本 #139 的保密例外）。
    """
    clean_query = query.strip()
    # 短词全表扫描防爆守卫：少于 2 个字符直接阻断，杜绝无索引全表扫描
    if len(clean_query) < 2:
        return []

    # 只认一个归一 needle：写入侧已折成简体，查询走同一张 1:1 表自然汇合（ADR 0017 2026-09-23 修订）
    needle = to_simplified(clean_query)
    limit = max(1, min(int(limit), 100))

    diag_rows: list[sqlite3.Row] = []
    # 候选池不按身份分档：bubble_count 是池内计数，池大小不同，同一页在两种身份下的命中数就不同
    fetch_limit = min(max(limit * 5, 50), 200)

    with get_dialogue_db() as conn:
        if len(needle) >= 3:
            # 只有走 MATCH 的这一支有 bm25 分数可用；trigram 索引键是三字窗口，
            # 故 2 字 needle 进不了倒排、只能走下面的 LIKE。3 字以上 MATCH 为空就是真没有：
            # trigram 覆盖全部三字子串，LIKE 再扫一遍全表也只会同样 0 行。
            # bm25 越相关越负，这里取负换成"越大越相关"，与 LIKE 那条同向，才能叠业务信号。
            # 命中的是归一列，摘要由 _make_snippet 在原文上定位，不用 SQL snippet()。
            sql_match = """
                SELECT
                    f.source,
                    f.source_id,
                    f.page_index,
                    f.bubble_id,
                    f.text,
                    f.text_norm,
                    f.lang,
                    f.box_json,
                    -bm25(comic_dialogues_fts) AS rank_score
                FROM comic_dialogues_fts f
                WHERE f.text_norm MATCH :needle
                  AND f.kind = :kind
                  AND (:source IS NULL OR f.source = :source)
                ORDER BY rank_score DESC, f.page_index, f.bubble_id
                LIMIT :fetch_limit
            """
            try:
                diag_rows = conn.execute(
                    sql_match,
                    {
                        "needle": '"' + needle.replace('"', '""') + '"',
                        "source": source,
                        "kind": DIALOGUE_KIND,
                        "fetch_limit": fetch_limit,
                    },
                ).fetchall()
            except sqlite3.OperationalError:
                # 含 NUL 这类 FTS5 解析不了的查询：当作无命中，不让检索端点 500
                diag_rows = []
        else:
            # :like 是带通配的匹配式，:term 是数出现次数的原串，不能共用一个绑定。
            # LIKE 不分 ASCII 大小写而 replace() 分，所以两边都折成小写再数（lower() 只折 ASCII，长度不变）。
            params: dict[str, Any] = {
                "like": f"%{_escape_like(needle)}%",
                "term": needle.translate(_ASCII_LOWER),
                "source": source,
                "kind": DIALOGUE_KIND,
                "fetch_limit": fetch_limit,
            }
            # 2 字查询没有 bm25 可用，手工补上其中真正区分候选的两项：词频 ÷ 文本长度
            # （IDF 对同一次查询是常数，省略）。词频按字符数计：length 差值 = 出现次数 × needle 长度。
            like_rank = (
                "(CAST(length(f.text_norm) - length(replace(lower(f.text_norm), :term, '')) AS REAL)"
                " / max(length(f.text_norm), 1))"
            )
            sql_like = f"""
                SELECT
                    f.source,
                    f.source_id,
                    f.page_index,
                    f.bubble_id,
                    f.text,
                    f.text_norm,
                    f.lang,
                    f.box_json,
                    {like_rank} AS rank_score
                FROM comic_dialogues_fts f
                WHERE (f.text_norm LIKE :like ESCAPE '\\')
                  AND f.kind = :kind
                  AND (:source IS NULL OR f.source = :source)
                ORDER BY {like_rank} DESC,
                         f.page_index, f.bubble_id
                LIMIT :fetch_limit
            """
            diag_rows = conn.execute(sql_like, params).fetchall()

    if not diag_rows:
        return []

    unique_keys = list({(r["source"], r["source_id"]) for r in diag_rows})
    comics_map = _dialogue_comics_meta_map(unique_keys, user_id)

    # 聚合到页：diag_rows 已按相关度降序，某页首次出现的那条即该页最高分代表句，
    # 之后再出现的同页气泡只累加命中数，不另起一行（检索单元是气泡，展示单元是页）。
    # bubble_count 因此是候选池（fetch_limit 行）内的计数，不是全库该页命中总数。
    # 这里不按 limit 收口：聚完的全部页才是排名的候选集，先截断再融合等于让 bm25 独裁。
    page_hits: dict[tuple[str, str, int], dict[str, Any]] = {}
    visible_scores: list[float] = []
    for r in diag_rows:
        src, sid = r["source"], r["source_id"]
        ci = comics_map.get((src, sid))
        if is_guest and ci and ci["hidden_from_guest"]:
            continue
        if is_guest and not ci:
            continue
        visible_scores.append(float(r["rank_score"]))

        page_idx = int(r["page_index"])
        # 唯一的写入口 sync_comic_dialogues 已把 box 归一成 4 个有限数值或空表，读侧不再重复校验
        box: list[float] = json.loads(r["box_json"])

        key = (src, sid, page_idx)
        hit = page_hits.get(key)
        if hit is not None:
            hit["bubble_count"] += 1
            # 同页其余命中气泡按相关度顺序补足，供阅读器一次画全；上限外的高频页只多算计数
            extra: list[list[float]] = hit["other_boxes"]
            if box and len(extra) < MAX_PAGE_BOXES - 1:
                extra.append(box)
            continue
        raw_text = r["text"] or ""
        page_hits[key] = {
            "source": src,
            "source_id": sid,
            **_dialogue_book_fields(src, sid, ci),
            "page_index": page_idx,
            "bubble_id": r["bubble_id"],
            "bubble_count": 1,
            "text": raw_text,
            "snippet": _make_snippet(raw_text, r["text_norm"] or "", needle),
            "box": box,
            "other_boxes": [],
            "lang": r["lang"] or "zh",
            "rank_score": float(r["rank_score"]),
        }

    pages = list(page_hits.values())
    if not pages:
        return []
    # 归一标尺只取调用者看得见的那些候选行的极值：若把隐藏本的行也算进去，访客看到的最高分
    # 一旦低于 1.0，就等于告诉他"某本对你隐藏的书里有更贴切的这句话"（错题本 #139 的保密例外）。
    # 代价是同一句查询，访客与馆长拿到的 rank_score 可能不同；它本就只在本次候选内部可比。
    pool_lo = min(visible_scores)
    pool_hi = max(visible_scores)
    return _rank_dialogue_pages(pages, comics_map, pool_lo, pool_hi)[:limit]


# 业务信号权重：四项合计封顶 0.5，也就是相关度差 0.5 以上翻不了盘（见 _rank_dialogue_pages）
DIALOGUE_SIGNAL_WEIGHTS = {"heat": 0.15, "favorite": 0.15, "finished": 0.10, "recent": 0.10}
# "最近阅读"的衰减窗口：30 天前读过的就不再算新
DIALOGUE_RECENT_WINDOW_DAYS = 30.0


def _comic_signals(ci: sqlite3.Row | None, now: float) -> tuple[float | None, float, float, float]:
    """从 comics_index 的一行读出四项业务信号的原始值：热度原始分、完读率、收藏、最近阅读衰减。

    返回的热度是 `log10(1+views) + log10(1+likes)` 的未归一原始值，`None` 表示这本没有热度可谈
    （本地导入的本子 views/likes 都是空串）；后三项天然是 0..1，不需要再归一。
    """
    if ci is None:
        return None, 0.0, 0.0, 0.0
    views = _parse_metric_count(ci["views"])
    likes = _parse_metric_count(ci["likes"])
    heat = None if (views is None and likes is None) else math.log10(1 + (views or 0)) + math.log10(1 + (likes or 0))
    page_count = int(ci["page_count"] or 0)
    last_page = int(ci["last_page"] or 0)
    finished = min(1.0, last_page / page_count) if page_count > 0 and last_page > 0 else 0.0
    favorite = 1.0 if ci["is_favorite"] else 0.0
    progress_at = ci["progress_at"]
    recent = 0.0
    if progress_at:
        days = max(0.0, (now - float(progress_at)) / 86400.0)
        recent = max(0.0, 1.0 - days / DIALOGUE_RECENT_WINDOW_DAYS)
    return heat, finished, favorite, recent


def _rank_dialogue_pages(
    pages: list[dict[str, Any]],
    comics_map: dict[tuple[str, str], sqlite3.Row],
    pool_lo: float,
    pool_hi: float,
    now: float | None = None,
) -> list[dict[str, Any]]:
    """先把相关度按候选池极值 min-max 归一，再叠业务信号，按最终分降序回报（同分保持原次序）。

    为什么必须叠：2 字查询的"词频 ÷ 文本长度"很粗，前几十名常整片打平，不叠信号的话截断留谁
    只由偶然次序决定（ADR 0017 决策 9）。

    `pool_lo` / `pool_hi` 是调用者**看得见的候选行**的极值（调用方已按身份过滤，理由见调用处），
    页级代表分恒落在该区间内，所以 `rank_score` 稳定在 0..1。

    四项信号（权重见 `DIALOGUE_SIGNAL_WEIGHTS`）：热度取 `views`/`likes` 对数后在**本次池内出现过的
    那些书**之间 min-max（跨池、跨查询的绝对值没有可比性）；完读率与收藏来自本人的阅读进度与收藏；
    最近阅读按 30 天线性衰减。全部是非负抬升且合计 ≤ 0.5，所以业务信号只在相关度接近时决定成败，
    不会把一本明显不相关的本子顶上来；没有任何信号时抬升恒为 0，顺序就退回纯相关度。
    """
    if not pages:
        return pages
    if now is None:
        now = time.time()

    span = pool_hi - pool_lo
    for p in pages:
        # 两条检索路径的原始分量纲完全不同（MATCH 支是取负后的 bm25，LIKE 支是词频÷文本长度），
        # 只有先在同一池内归一，才加得动后面那些 0..1 的信号
        p["rank_score"] = 1.0 if span <= 0 else (p["rank_score"] - pool_lo) / span

    weights = DIALOGUE_SIGNAL_WEIGHTS
    book_signals: dict[tuple[str, str], tuple[float | None, float, float, float]] = {}
    for p in pages:
        key = (p["source"], p["source_id"])
        book_signals.setdefault(key, _comic_signals(comics_map.get(key), now))
    heat_values = [s[0] for s in book_signals.values() if s[0] is not None]
    heat_lo = min(heat_values) if heat_values else 0.0
    heat_span = (max(heat_values) - heat_lo) if heat_values else 0.0

    ranked: list[tuple[float, int, dict[str, Any]]] = []
    for i, p in enumerate(pages):
        heat, finished, favorite, recent = book_signals[(p["source"], p["source_id"])]
        heat_norm = 0.0 if heat is None or heat_span <= 0 else (heat - heat_lo) / heat_span
        lift = (
            weights["heat"] * heat_norm
            + weights["favorite"] * favorite
            + weights["finished"] * finished
            + weights["recent"] * recent
        )
        ranked.append((p["rank_score"] + lift, i, p))
    # 显式带原次序做第二键：sort 稳定，但这里要的是"同分 = 归一前谁先到谁在前"
    ranked.sort(key=lambda t: (-t[0], t[1]))
    return [t[2] for t in ranked]


STORY_CONTEXT_MAX_LINES = 400
STORY_CONTEXT_MAX_PAGES = 200


def get_story_context(
    source: str,
    source_id: str,
    page_start: int,
    page_end: int,
    budget_lines: int = 120,
) -> dict[str, Any]:
    """按页码区间取原始台词物料，供下游生成管线使用（与台词检索同为一份索引的另一个出口）。

    按 `(page_index, reading_order)` 的剧情原序给连续切片：不收关键词、不吐展示态字段，撞预算必须回报
    `truncated`；`reading_order` 有空洞、不输出 `speaker`。边界纪律与已知限制见 ADR 0017 决策 8。

    Args:
        source: 图源平台标识（如 'jm' | 'local' | 'picacg'）。
        source_id: 作品唯一 ID；与 source 组成复合键，单靠它不唯一定位一本书。
        page_start: 起始全局页号（1 起，含）。
        page_end: 结束全局页号（含）。
        budget_lines: 预算行数，即本次最多返回多少条台词。

    Returns:
        {'lines': [{'line_id', 'page_index', 'reading_order', 'text'}],
         'boxes': [{'line_id', 'box'}],
         'truncated': bool, 'budget_lines': int, 'requested_pages': [p0, p1]}
        `truncated` 为真表示区间内还有没返回的内容：要么预算用尽，要么页跨度被夹到 200 页。
        `requested_pages` 是实际覆盖的页区间，跨度被夹时比请求的短，下游据它接着往后取。
    """
    source, source_id = _dialogue_key(source, source_id)
    p0 = max(1, int(page_start))
    p1 = max(p0, int(page_end))
    # 区间上限先夹页号，再夹预算：一次取料最多跨 200 页 / 400 行，杜绝"整本书一把梭"
    pages_clamped = p1 > p0 + STORY_CONTEXT_MAX_PAGES - 1
    p1 = min(p1, p0 + STORY_CONTEXT_MAX_PAGES - 1)
    budget = max(1, min(int(budget_lines), STORY_CONTEXT_MAX_LINES))

    with get_dialogue_db() as conn:
        rows = conn.execute(
            """
            SELECT page_index, bubble_id, reading_order, text, box_json
            FROM comic_dialogues_fts
            WHERE source = :source AND source_id = :source_id
              AND page_index BETWEEN :p0 AND :p1
              AND kind = :kind
            ORDER BY page_index, reading_order, bubble_id
            LIMIT :cap
            """,
            {
                "source": source,
                "source_id": source_id,
                "p0": p0,
                "p1": p1,
                "kind": DIALOGUE_KIND,
                "cap": budget + 1,
            },
        ).fetchall()

    truncated = len(rows) > budget or pages_clamped
    lines: list[dict[str, Any]] = []
    boxes: list[dict[str, Any]] = []
    for r in rows[:budget]:
        page_index = int(r["page_index"])
        line_id = f"{page_index}:{r['bubble_id']}"
        lines.append(
            {
                "line_id": line_id,
                "page_index": page_index,
                "reading_order": int(r["reading_order"]),
                "text": r["text"],
            }
        )
        box = json.loads(r["box_json"])
        if box:
            boxes.append({"line_id": line_id, "box": box})

    return {
        "lines": lines,
        "boxes": boxes,
        "truncated": truncated,
        "budget_lines": budget,
        "requested_pages": [p0, p1],
    }


def create_direct_pass(
    source: str,
    source_id: str,
    page_index: int = 1,
    ttl_seconds: int = 7200,
    custom_token: str | None = None,
) -> dict[str, Any]:
    """Issues a sandboxed temporary direct pass for a single comic."""
    token = custom_token.strip() if custom_token and custom_token.strip() else secrets.token_hex(16)
    now = int(time.time())
    expires_at = now + max(60, min(86400 * 7, ttl_seconds))
    safe_page = max(1, page_index)

    with get_db() as conn:
        conn.execute("DELETE FROM direct_passes WHERE expires_at <= ?", (now,))
        conn.execute(
            """
            INSERT INTO direct_passes (token, source, source_id, page_index, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (token, source, source_id, safe_page, now, expires_at),
        )
        conn.commit()

    return {
        "token": token,
        "source": source,
        "source_id": source_id,
        "page_index": safe_page,
        "created_at": now,
        "expires_at": expires_at,
        "expires_in": expires_at - now,
    }


def get_direct_pass(token: str) -> dict[str, Any] | None:
    """Retrieves a valid unexpired single-comic direct pass by token."""
    if not token or not token.strip():
        return None
    now = int(time.time())
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM direct_passes WHERE token = ? AND expires_at > ?",
            (token.strip(), now),
        ).fetchone()
        if not row:
            return None
        res = dict(row)
        res["expires_in"] = max(1, int(res["expires_at"] - now))
        return res


def clean_expired_direct_passes() -> int:
    """Purges expired direct passes from the database."""
    now = int(time.time())
    with get_db() as conn:
        cur = conn.execute("DELETE FROM direct_passes WHERE expires_at <= ?", (now,))
        conn.commit()
        return cur.rowcount


