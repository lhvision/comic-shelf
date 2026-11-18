from __future__ import annotations

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from ..config import DATA_DIR

DEFAULT_DB_PATH = DATA_DIR / "comic_shelf.db"
_DB_PATH: Path = DEFAULT_DB_PATH
_DATA_DIR: Path = DATA_DIR

DEFAULT_DIALOGUE_DB_PATH = DATA_DIR / "comic_dialogues.db"
_DIALOGUE_DB_PATH: Path = DEFAULT_DIALOGUE_DB_PATH


def get_data_dir() -> Path:
    """当前生效的数据目录（台词伴生文件从它下面的 library/ 读取）。"""
    return _DATA_DIR


def set_data_dir(path: Path) -> None:
    """重定向数据目录，供测试使用；与 set_db_path() 一样必须显式调用，不要给模块属性赋值。"""
    global _DATA_DIR
    _DATA_DIR = Path(path)


def set_db_path(path: Path) -> None:
    global _DB_PATH, _DIALOGUE_DB_PATH
    _DB_PATH = path
    if "comic_shelf" in path.name:
        _DIALOGUE_DB_PATH = path.parent / path.name.replace("comic_shelf", "comic_dialogues")
    else:
        _DIALOGUE_DB_PATH = path.parent / f"{path.stem}_dialogues.db"
    try:
        from .index import invalidate_facets_cache

        invalidate_facets_cache(force=True)
    except ImportError:
        pass


def get_db_path() -> Path:
    return _DB_PATH


def set_dialogue_db_path(path: Path) -> None:
    global _DIALOGUE_DB_PATH
    _DIALOGUE_DB_PATH = path


def get_dialogue_db_path() -> Path:
    return _DIALOGUE_DB_PATH


@contextmanager
def get_dialogue_db() -> Generator[sqlite3.Connection]:
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
def get_db() -> Generator[sqlite3.Connection]:
    conn = sqlite3.connect(_DB_PATH, timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def _escape_like(text: str) -> str:
    """转义 SQLite LIKE 查询中的特殊通配符 %、_ 与转义符自身。"""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
