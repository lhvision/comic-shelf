from __future__ import annotations

import hashlib
import json
import logging
import re
import secrets
import sqlite3
import threading
import time
from contextlib import contextmanager
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

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = DATA_DIR / "comic_shelf.db"
_DB_PATH: Path = DEFAULT_DB_PATH


def set_db_path(path: Path) -> None:
    global _DB_PATH
    _DB_PATH = path


def get_db_path() -> Path:
    return _DB_PATH


@contextmanager
def get_db() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(_DB_PATH, timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
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
                PRIMARY KEY (source, source_id)
            );
            CREATE INDEX IF NOT EXISTS idx_comics_index_imported ON comics_index(imported_at DESC);
            CREATE INDEX IF NOT EXISTS idx_comics_index_source ON comics_index(source);
            CREATE INDEX IF NOT EXISTS idx_comics_index_title ON comics_index(title);

            CREATE VIRTUAL TABLE IF NOT EXISTS comic_dialogues_fts USING fts5(
                source UNINDEXED,
                source_id UNINDEXED,
                page_index UNINDEXED,
                bubble_id UNINDEXED,
                text,
                lang UNINDEXED,
                box_json UNINDEXED,
                tokenize='trigram'
            );

            CREATE TABLE IF NOT EXISTS comic_ocr_sync_meta (
                source TEXT NOT NULL,
                source_id TEXT NOT NULL,
                last_synced_mtime REAL NOT NULL DEFAULT 0.0,
                dialogue_count INTEGER NOT NULL DEFAULT 0,
                updated_at INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (source, source_id)
            );
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
        conn.commit()


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


def get_user_all_progress(user_id: str) -> dict[tuple[str, str], int]:
    """批量获取用户的所有漫画阅读进度映射: (source, source_id) -> last_page"""
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT source, source_id, last_page
            FROM user_reading_progress
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchall()
        return {(row["source"], row["source_id"]): int(row["last_page"]) for row in rows}


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
                hidden_from_guest, mtime
            ) VALUES (
                :source, :source_id, :display_id, :title,
                :authors_json, :works_json, :actors_json, :tags_json, :chapter_titles_json,
                :page_count, :cached_pages, :cover_count, :cover_indices_json,
                :views, :likes, :uploaded_at, :published_at, :updated_at, :imported_at,
                :hidden_from_guest, :mtime
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
                mtime = excluded.mtime
            """,
            item,
        )
        conn.commit()


def delete_comic_index(source: str, source_id: str) -> None:
    """删除指定漫画的影子索引。"""
    with get_db() as conn:
        conn.execute(
            "DELETE FROM comics_index WHERE source = ? AND source_id = ?",
            (source, source_id),
        )
        conn.commit()


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
    sort: str = "recent",
    ids: str | None = None,
    offset: int | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """支持万级藏书的毫秒级 SQL 分页、模糊过滤、状态关联与多模式排序。"""
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

    if tag and tag.strip():
        conditions.append("EXISTS (SELECT 1 FROM json_each(ci.tags_json) WHERE value = :tag)")
        params["tag"] = tag.strip()

    if q and q.strip():
        raw_q = q.strip()
        escaped_q = raw_q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        needle = f"%{escaped_q}%"
        params["needle"] = needle
        conditions.append(
            """(
                ci.title LIKE :needle ESCAPE '\\'
                OR ci.display_id LIKE :needle ESCAPE '\\'
                OR ci.authors_json LIKE :needle ESCAPE '\\'
                OR ci.works_json LIKE :needle ESCAPE '\\'
                OR ci.actors_json LIKE :needle ESCAPE '\\'
                OR ci.tags_json LIKE :needle ESCAPE '\\'
                OR ci.chapter_titles_json LIKE :needle ESCAPE '\\'
            )"""
        )

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


def get_library_facets(is_curator: bool, source: str | None = None) -> dict[str, Any]:
    """聚合全站藏书本数、总页数、缓存页数与高频前 30 个标签。"""
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


# ----------------------------------------------------------------------
# 台词全文索引（comic_dialogues_fts）同步与检索
# ----------------------------------------------------------------------

def _make_snippet(text: str, terms: list[str], max_chars: int = 60) -> str:
    """为检索命中文本生成呼吸高亮标记与摘要片段，严格进行 HTML 转义以彻底免疫 XSS。"""
    if not text:
        return ""
    import html
    escaped_text = html.escape(text)
    if not terms:
        return escaped_text[:max_chars] + ("..." if len(escaped_text) > max_chars else "")
    valid_terms = [re.escape(html.escape(t.strip())) for t in terms if t.strip()]
    if not valid_terms:
        return escaped_text[:max_chars] + ("..." if len(escaped_text) > max_chars else "")
    pattern = "(" + "|".join(valid_terms) + ")"
    m = re.search(pattern, escaped_text, re.IGNORECASE)
    if not m:
        return escaped_text[:max_chars] + ("..." if len(escaped_text) > max_chars else "")
    start = max(0, m.start() - 15)
    end = min(len(escaped_text), m.end() + 35)
    sub = escaped_text[start:end]
    highlighted = re.sub(pattern, r"<mark>\1</mark>", sub, flags=re.IGNORECASE)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(escaped_text) else ""
    return f"{prefix}{highlighted}{suffix}"


def sync_comic_dialogues(source: str, source_id: str, force: bool = False) -> int:
    """从画页伴生 OCR 数据（*.ocr.json）同步台词至 comic_dialogues_fts。

    安全沙箱与原子性保证：
    1. 严格过滤路径穿越符号并校验 DATA_DIR 边界，禁止任意目录探测；
    2. 先清空当前 (source, source_id) 的旧索引，再全量写入新气泡记录，杜绝幽灵索引。
    """
    safe_source = re.sub(r"[^a-zA-Z0-9_\-\.]+", "_", source).strip("._") or "_"
    safe_id = re.sub(r"[^a-zA-Z0-9_\-\.]+", "_", source_id).strip("._") or "_"
    while ".." in safe_id:
        safe_id = safe_id.replace("..", "_")
    while ".." in safe_source:
        safe_source = safe_source.replace("..", "_")

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

    # 读取 album.json 以便建立多章节全局页号映射
    page_map: dict[str, int] = {}
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
                for p in meta_dict.get("pages", []):
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

    records: list[tuple[str, str, int, int | str, str, str, str]] = []
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
            except (ValueError, TypeError):
                pass
        elif payload.get("page") is not None:
            try:
                page_idx = int(payload["page"])
            except (ValueError, TypeError):
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

        for b_idx, b in enumerate(bubbles, start=1):
            if not isinstance(b, dict):
                continue
            text = str(b.get("text", "")).strip()
            if not text:
                continue
            bubble_id = b.get("id", b_idx)
            lang = b.get("lang") or top_lang
            box = b.get("box", [])
            box_json = json.dumps(box, ensure_ascii=False)
            records.append((source, source_id, page_idx, bubble_id, text, str(lang), box_json))

    latest_mtime: float = 0.0
    for f in ocr_files:
        try:
            mt = f.stat().st_mtime
            if mt > latest_mtime:
                latest_mtime = mt
        except OSError:
            pass

    # 增量检查：若非 force 模式，比对元数据表；若 OCR 文件自上次入库以来未发生任何变动，直接返回已有计数（0 毫秒跳过）
    if not force:
        with get_db() as conn:
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

    with get_db() as conn:
        with conn:
            conn.execute(
                "DELETE FROM comic_dialogues_fts WHERE source = ? AND source_id = ?",
                (source, source_id),
            )
            if records:
                conn.executemany(
                    """
                    INSERT INTO comic_dialogues_fts (
                        source, source_id, page_index, bubble_id, text, lang, box_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
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
        return len(records)


def delete_comic_dialogues(source: str, source_id: str) -> None:
    """删除指定漫画的所有台词全文索引与增量元数据。"""
    with get_db() as conn:
        with conn:
            conn.execute(
                "DELETE FROM comic_dialogues_fts WHERE source = ? AND source_id = ?",
                (source, source_id),
            )
            conn.execute(
                "DELETE FROM comic_ocr_sync_meta WHERE source = ? AND source_id = ?",
                (source, source_id),
            )


def cleanup_orphan_comic_dialogues(data_dir: Path | None = None) -> int:
    """清理已从磁盘物理删除但仍残留在 FTS5 与元数据中的孤儿对白索引。"""
    if data_dir is None:
        data_dir = DATA_DIR
    data_resolved = data_dir.resolve()
    cleaned = 0
    with get_db() as conn:
        rows = conn.execute("SELECT DISTINCT source, source_id FROM comic_dialogues_fts").fetchall()
        for r in rows:
            src, sid = r["source"], r["source_id"]
            comic_dir = data_resolved / "library" / src / sid
            if not comic_dir.is_dir():
                with conn:
                    conn.execute("DELETE FROM comic_dialogues_fts WHERE source = ? AND source_id = ?", (src, sid))
                    conn.execute("DELETE FROM comic_ocr_sync_meta WHERE source = ? AND source_id = ?", (src, sid))
                cleaned += 1
                logger.info(f"Cleaned orphan dialogue index for deleted comic {src}/{sid}")
    return cleaned


def search_dialogues(
    query: str,
    source: str | None = None,
    limit: int = 20,
    is_guest: bool = False,
) -> list[dict[str, Any]]:
    """检索台词全文索引，支持简繁双向展开、模糊分词与访客权限过滤。"""
    clean_query = query.strip()
    if not clean_query:
        return []

    from .zh_conv import expand_search_variants

    variants = expand_search_variants(clean_query)
    is_not_guest = 0 if is_guest else 1
    if not isinstance(limit, int):
        try:
            limit = int(limit)
        except Exception:
            limit = 20
    limit = max(1, min(limit, 100))

    match_variants = [v for v in variants if len(v) >= 3]
    rows: list[sqlite3.Row] = []

    with get_db() as conn:
        if match_variants:
            match_terms = ['"' + v.replace('"', '""') + '"' for v in match_variants]
            match_expr = " OR ".join(match_terms)
            sql_match = """
                SELECT
                    f.source,
                    f.source_id,
                    f.page_index,
                    f.bubble_id,
                    f.text,
                    f.lang,
                    f.box_json,
                    snippet(comic_dialogues_fts, 4, '<mark>', '</mark>', '...', 20) as snippet_text,
                    ci.display_id,
                    ci.title,
                    ci.cover_indices_json,
                    ci.authors_json,
                    ci.hidden_from_guest
                FROM comic_dialogues_fts f
                LEFT JOIN comics_index ci
                    ON ci.source = f.source AND ci.source_id = f.source_id
                WHERE comic_dialogues_fts MATCH :match_expr
                  AND (:source IS NULL OR f.source = :source)
                  AND (:is_not_guest OR (ci.source IS NOT NULL AND COALESCE(ci.hidden_from_guest, 0) = 0))
                LIMIT :limit
            """
            try:
                rows = conn.execute(
                    sql_match,
                    {
                        "match_expr": match_expr,
                        "source": source,
                        "is_not_guest": is_not_guest,
                        "limit": limit,
                    },
                ).fetchall()
            except sqlite3.OperationalError:
                rows = []

        if not rows:
            like_clauses = []
            params: dict[str, Any] = {
                "source": source,
                "is_not_guest": is_not_guest,
                "limit": limit,
            }
            for i, v in enumerate(variants):
                param_name = f"like_{i}"
                like_clauses.append(f"f.text LIKE :{param_name}")
                params[param_name] = f"%{v}%"

            where_text = " OR ".join(like_clauses)
            sql_like = f"""
                SELECT
                    f.source,
                    f.source_id,
                    f.page_index,
                    f.bubble_id,
                    f.text,
                    f.lang,
                    f.box_json,
                    '' as snippet_text,
                    ci.display_id,
                    ci.title,
                    ci.cover_indices_json,
                    ci.authors_json,
                    ci.hidden_from_guest
                FROM comic_dialogues_fts f
                LEFT JOIN comics_index ci
                    ON ci.source = f.source AND ci.source_id = f.source_id
                WHERE ({where_text})
                  AND (:source IS NULL OR f.source = :source)
                  AND (:is_not_guest OR (ci.source IS NOT NULL AND COALESCE(ci.hidden_from_guest, 0) = 0))
                LIMIT :limit
            """
            rows = conn.execute(sql_like, params).fetchall()

        results: list[dict[str, Any]] = []
        for r in rows:
            box = []
            if r["box_json"]:
                try:
                    box = json.loads(r["box_json"])
                except Exception:
                    box = []

            cover_indices = []
            if r["cover_indices_json"]:
                try:
                    cover_indices = json.loads(r["cover_indices_json"])
                except Exception:
                    cover_indices = []
            first_idx = cover_indices[0] if cover_indices else 0
            cover = f"/api/library/{r['source']}/{r['source_id']}/covers/{first_idx}/file"

            authors = []
            if r["authors_json"]:
                try:
                    authors = json.loads(r["authors_json"])
                except Exception:
                    authors = []

            raw_text = r["text"] or ""
            snip = r["snippet_text"] if "snippet_text" in r.keys() and r["snippet_text"] else ""
            if not snip or "<mark>" not in snip:
                snip = _make_snippet(raw_text, variants)

            results.append({
                "source": r["source"],
                "source_id": r["source_id"],
                "display_id": r["display_id"] or r["source_id"],
                "title": r["title"] or r["source_id"],
                "page_index": int(r["page_index"]),
                "bubble_id": r["bubble_id"],
                "text": raw_text,
                "snippet": snip,
                "box": box,
                "lang": r["lang"] or "zh",
                "cover": cover,
                "authors": authors,
            })
        return results


