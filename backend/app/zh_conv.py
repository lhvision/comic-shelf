"""Simplified and Traditional Chinese bidirectional conversion utilities for dialogue FTS.

This module provides zero-external-dependency, high-performance bidirectional Chinese
conversion for Dialogue Full-Text Search (SQLite FTS5 Trigram).

Mapping data is decoupled into a compressed binary asset (`app/assets/zh_tables.dat`),
loaded lazily into memory upon first call, ensuring instant module import (<1ms) and
preventing IDE syntax highlighting/LSP lag from giant raw string literals.
"""
from __future__ import annotations

import threading
import zlib
from pathlib import Path

_ASSET_PATH = Path(__file__).resolve().parent / "assets" / "zh_tables.dat"

_INIT_LOCK = threading.Lock()
_S2T_TABLE: dict[int, int] | None = None
_T2S_TABLE: dict[int, int] | None = None


def _load_tables() -> tuple[dict[int, int], dict[int, int]]:
    """Lazily load and parse compressed Simplified <-> Traditional translation tables."""
    global _S2T_TABLE, _T2S_TABLE
    if _S2T_TABLE is not None and _T2S_TABLE is not None:
        return _S2T_TABLE, _T2S_TABLE

    with _INIT_LOCK:
        if _S2T_TABLE is not None and _T2S_TABLE is not None:
            return _S2T_TABLE, _T2S_TABLE

        if not _ASSET_PATH.exists():
            raise FileNotFoundError(
                f"Chinese conversion tables asset not found at {_ASSET_PATH}."
            )

        raw_data = _ASSET_PATH.read_bytes()
        decompressed = zlib.decompress(raw_data).decode("utf-8")
        st_blob, ts_blob = decompressed.split("\n", 1)

        st_map = {st_blob[i]: st_blob[i + 1] for i in range(0, len(st_blob), 2)}
        ts_map = {ts_blob[i]: ts_blob[i + 1] for i in range(0, len(ts_blob), 2)}

        _S2T_TABLE = str.maketrans(st_map)
        _T2S_TABLE = str.maketrans(ts_map)
        return _S2T_TABLE, _T2S_TABLE


def to_traditional(text: str) -> str:
    """Convert simplified Chinese characters to traditional."""
    if not text:
        return ""
    s2t, _ = _load_tables()
    return text.translate(s2t)


def to_simplified(text: str) -> str:
    """Convert traditional Chinese characters to simplified."""
    if not text:
        return ""
    _, t2s = _load_tables()
    return text.translate(t2s)


def expand_search_variants(query: str) -> list[str]:
    """Expand query into simplified and traditional variants for 100% recall."""
    clean_q = query.strip()
    if not clean_q:
        return []
    variants: list[str] = [clean_q]
    s_ver = to_simplified(clean_q)
    t_ver = to_traditional(clean_q)
    if s_ver and s_ver not in variants:
        variants.append(s_ver)
    if t_ver and t_ver not in variants:
        variants.append(t_ver)
    return variants
