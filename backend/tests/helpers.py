"""Shared test helpers, fixtures, and mock builders for backend tests."""
from __future__ import annotations

import io
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock
from PIL import Image

# Ensure backend root is on sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def create_sample_image(
    color: str = "red",
    size: tuple[int, int] = (100, 100),
    fmt: str = "WEBP",
) -> bytes:
    """Generate in-memory image bytes for testing."""
    im = Image.new("RGB", size, color=color)
    buf = io.BytesIO()
    im.save(buf, format=fmt)
    return buf.getvalue()


def make_mock_request(
    path: str = "/api/library",
    headers: dict[str, str] | None = None,
    cookies: dict[str, str] | None = None,
    query_params: dict[str, str] | None = None,
    client_host: str = "127.0.0.1",
) -> MagicMock:
    """Construct a mock FastAPI/Starlette Request object."""
    req = MagicMock()
    req.state = type("State", (), {})()
    req.url.path = path
    headers_dict = {k.lower(): v for k, v in (headers or {}).items()}
    req.headers.get = lambda k, default="": headers_dict.get(k.lower(), default)
    req.cookies.get = lambda k, default="": (cookies or {}).get(k, default)
    req.query_params.get = lambda k, default="": (query_params or {}).get(k, default)
    client_mock = MagicMock()
    client_mock.host = client_host
    req.client = client_mock
    return req


def setup_temp_sqlite_db() -> tuple[tempfile.TemporaryDirectory, Path]:
    """Create a temporary directory and return an initialized test SQLite database path."""
    import app.db as db_mod

    tmp_dir = tempfile.TemporaryDirectory(prefix="test_comic_shelf_")
    db_path = Path(tmp_dir.name) / "test_shelf.db"
    db_mod.init_db(db_path)
    return tmp_dir, db_path
