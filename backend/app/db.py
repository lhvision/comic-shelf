from __future__ import annotations

import hashlib
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
