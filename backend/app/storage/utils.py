"""Low-level filesystem helpers, atomic JSON writing, and path traversal security checks."""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

from .. import file_io
from ..config import DATA_DIR, LIBRARY_DIR, TMP_DIR

_write_bytes_atomic = file_io.write_bytes_atomic
_write_json_atomic = file_io.write_json_atomic

logger = logging.getLogger(__name__)

_SAFE = re.compile(r"[^a-zA-Z0-9._-]+")
_NATURAL_SPLIT = re.compile(r"(\d+)")
IMAGE_EXTS = frozenset({".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif", ".bmp"})

# v1 stored raw JM images (scrambled). v2 stores de-scrambled images using
# jmcomic's official JmImageTool algorithm. Existing v1 caches are migrated
# locally, without re-downloading anything from the remote site.
CURRENT_DECODE_VERSION = 2


def acquire_library_writer_lock(library_dir: Path) -> int:
    """Take an exclusive file lock so only one API process can write a library.

    The returned descriptor must stay open until the process stops serving.
    """
    import fcntl

    library_dir.mkdir(parents=True, exist_ok=True)
    lock_path = library_dir / ".writer.lock"
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        os.close(fd)
        raise RuntimeError(
            "书库已有正在运行的 API 实例。同一书库只能由一个写入进程使用，"
            "请不要使用多个 Uvicorn worker 或多个容器挂载同一目录。"
        ) from exc
    os.ftruncate(fd, 0)
    os.write(fd, str(os.getpid()).encode("ascii"))
    os.fsync(fd)
    return fd


def _is_path_allowed(path: Path) -> bool:
    """Enforces strict path traversal security by checking against whitelisted root directories."""
    proj_root = Path(__file__).resolve().parents[3]
    allowed_bases = [
        DATA_DIR.resolve(),
        LIBRARY_DIR.resolve(),
        TMP_DIR.resolve(),
        proj_root.resolve(),
        Path.cwd().resolve(),
    ]
    extra = os.getenv("COMIC_SHELF_ALLOWED_DIRS", "").strip()
    if extra:
        for p in extra.split(os.pathsep):
            if p.strip():
                try:
                    allowed_bases.append(Path(p.strip()).expanduser().resolve())
                except Exception as e:
                    logger.warning("Failed to parse allowed import path '%s': %s", p, e)
    try:
        resolved = path.resolve()
        return any(resolved == base or resolved.is_relative_to(base) for base in allowed_bases)
    except Exception:
        return False
