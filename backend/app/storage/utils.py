"""Low-level filesystem helpers, atomic JSON writing, and path traversal security checks."""
from __future__ import annotations

import json
import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from ..config import DATA_DIR, LIBRARY_DIR, TMP_DIR

logger = logging.getLogger(__name__)

_SAFE = re.compile(r"[^a-zA-Z0-9._-]+")
_NATURAL_SPLIT = re.compile(r"(\d+)")
IMAGE_EXTS = frozenset({".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif", ".bmp"})

# v1 stored raw JM images (scrambled). v2 stores de-scrambled images using
# jmcomic's official JmImageTool algorithm. Existing v1 caches are migrated
# locally, without re-downloading anything from the remote site.
CURRENT_DECODE_VERSION = 2


def _write_json_atomic(path: Path, data: Any) -> None:
    """Writes a JSON document atomically using a temporary file and atomic swap."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = None, None
    try:
        fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
        tmp = Path(tmp_name)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if tmp is not None and tmp.exists():
            tmp.unlink(missing_ok=True)


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
