from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_ROOT / "backend"


def _load_dotenv() -> None:
    for env_file in (PROJECT_ROOT / ".env", BACKEND_DIR / ".env"):
        if env_file.is_file():
            try:
                for line in env_file.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k, v = k.strip(), v.strip().strip("'\"")
                    if k and k not in os.environ:
                        os.environ[k] = v
            except Exception:
                pass


_load_dotenv()

DATA_DIR = Path(os.getenv("COMIC_SHELF_DATA", BACKEND_DIR / "data")).resolve()

LIBRARY_DIR = DATA_DIR / "library"
TMP_DIR = DATA_DIR / "tmp"

LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
TMP_DIR.mkdir(parents=True, exist_ok=True)

COVER_WIDTH = int(os.getenv("COMIC_SHELF_COVER_WIDTH", "840"))
COVER_QUALITY = int(os.getenv("COMIC_SHELF_COVER_QUALITY", "82"))
COVER_COUNT = int(os.getenv("COMIC_SHELF_COVER_COUNT", "4"))

PAGE_THUMB_WIDTH = int(os.getenv("COMIC_SHELF_PAGE_THUMB_WIDTH", "360"))
PAGE_THUMB_QUALITY = int(os.getenv("COMIC_SHELF_PAGE_THUMB_QUALITY", "78"))

INDEX_FILE = DATA_DIR / "index.json"

# Be polite: cap eager prefetch when the user asks for "all" pages.
MAX_PREFETCH = int(os.getenv("COMIC_SHELF_MAX_PREFETCH", "600"))

# Keep page downloads to a small, steady concurrency. The JM CDN throttles or
# queues bursts of parallel image requests (the detail page wants thumbnails
# for many pages at once); firing them all simultaneously makes every request
# hit a timeout. 3 in-flight downloads is polite to the CDN and still fast.
MAX_CONCURRENT_DOWNLOADS = int(os.getenv("COMIC_SHELF_MAX_CONCURRENT_DOWNLOADS", "3"))

IMSEARCH_URL = os.getenv("COMIC_SHELF_IMSEARCH_URL", "http://localhost:8765").rstrip("/")

ENABLE_DOCS = os.getenv("COMIC_SHELF_ENABLE_DOCS", "false").lower() in ("1", "true", "yes")

# Curator key for full access (blank = open access, non-blank = protected)
AUTH_SECRET = os.getenv("COMIC_SHELF_SECRET", os.getenv("COMIC_SHELF_AUTH_TOKEN", "")).strip()

# Anti-hotlinking / storage bucket abuse protection
ENABLE_HOTLINK_PROTECTION = os.getenv("COMIC_SHELF_ENABLE_HOTLINK_PROTECTION", "true").lower() in ("1", "true", "yes")


