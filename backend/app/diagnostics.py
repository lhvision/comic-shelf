from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import DATA_DIR

import os
import re

logger = logging.getLogger(__name__)

_DIAG_LOG_PATH = DATA_DIR / "import_diagnostic.log"
_DIAG_LOCK = threading.Lock()
_MAX_LOG_BYTES = 5 * 1024 * 1024  # 5MB rotation threshold
_PROXY_CRED_RE = re.compile(r"://([^:@\s]*):([^@\s]+)@")


def _mask_diag_text(text: str) -> str:
    """脱敏日志中的密码与凭据，防止敏感信息落盘。"""
    if not text:
        return ""
    masked = _PROXY_CRED_RE.sub(r"://\1:***@", text)
    jm_pwd = os.getenv("JM_PASSWORD", "").strip()
    if jm_pwd and len(jm_pwd) >= 4 and jm_pwd in masked:
        masked = masked.replace(jm_pwd, "******")
    auth_secret = os.getenv("COMIC_SHELF_SECRET", "").strip()
    if auth_secret and len(auth_secret) >= 4 and auth_secret in masked:
        masked = masked.replace(auth_secret, "******")
    return masked


def get_diag_log_path() -> Path:
    """获取入库诊断日志文件的绝对路径。"""
    return _DIAG_LOG_PATH


def log_import_diag(category: str, message: str, **kwargs: Any) -> None:
    """写入脱敏后的结构化入库排查日志到 backend/data/import_diagnostic.log。

    格式: [2026-09-27T03:30:15.123Z] [CATEGORY] message key=val ...
    """
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    clean_msg = _mask_diag_text(message)
    extra = ""
    if kwargs:
        extra = " " + " ".join(f"{k}={_mask_diag_text(str(v))}" for k, v in kwargs.items())
    line = f"[{now_str}] [{category}] {clean_msg}{extra}\n"

    # 同步输出至标准日志，便于容器与终端观察
    logger.info("[IMPORT-DIAG] [%s] %s%s", category, clean_msg, extra)

    try:
        with _DIAG_LOCK:
            _DIAG_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            if _DIAG_LOG_PATH.exists() and _DIAG_LOG_PATH.stat().st_size > _MAX_LOG_BYTES:
                backup = _DIAG_LOG_PATH.with_suffix(".log.1")
                try:
                    if backup.exists():
                        backup.unlink()
                    _DIAG_LOG_PATH.rename(backup)
                except Exception:
                    pass
            with open(_DIAG_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(line)
                f.flush()
    except Exception as exc:
        logger.debug("Failed to write to import diagnostic log: %s", exc)
