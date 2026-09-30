"""Shared display formatting helpers used by providers and storage."""
from __future__ import annotations

import re
from .zh_conv import to_simplified


def format_count(val: object) -> str:
    """Format numeric counts into human-readable metric strings like '3.4M' or '78k'."""
    if val is None or val == "":
        return ""
    try:
        n = int(str(val).replace(",", "").strip())
    except (ValueError, TypeError):
        return str(val).strip()

    if n < 0:
        return str(n)
    if n >= 1_000_000:
        val_m = n / 1_000_000
        formatted = f"{val_m:.1f}M"
        return formatted.replace(".0M", "M")
    if n >= 10_000:
        val_k = round(n / 1_000)
        return f"{val_k}k"
    if n >= 1_000:
        val_k = n / 1_000
        formatted = f"{val_k:.1f}k"
        return formatted.replace(".0k", "k")
    return str(n)


BRACKET_PATTERN = re.compile(
    r"\[([^\]]*)\]|［([^］]*)］|【([^】]*)】|〔([^〕]*)〕|〖([^〗]*)〗|〘([^〙]*)〙|\(([^\)]*)\)|（([^）]*)）|\{([^\}]*)\}|｛([^｝]*)｝"
)
VOL_MARKER = re.compile(
    r"(?:第?\s*\d+\s*[话話卷冊册期部篇]|vol\.?\s*\d+|\b\d{1,4}\b|[上下中]|前篇|后篇|後篇|中篇|番外|特别篇|特別篇|part\.?\s*\d+|ep\.?\s*\d+|ch\.?\s*\d+)",
    re.IGNORECASE,
)
METADATA_HINT = re.compile(
    r"(?:汉化|漢化|翻译|翻訳|扫图|掃圖|个人|個人|自翻|制作|製作|无修|無修|修正|dl版|digital|c\d{2,3}|comic1|例大祭|红楼梦|紅樓夢|\b\d{3,4}p\b|\b4k\b)",
    re.IGNORECASE,
)
WHITESPACE_PUNCT_PATTERN = re.compile(r"[\s\-_:：·・,.，。！？!?~～/／\\、|｜#＃]+")


def _replace_bracket(m: re.Match) -> str:
    inner = next((g for g in m.groups() if g is not None), "").strip()
    if not inner:
        return " "
    if not METADATA_HINT.search(inner) and VOL_MARKER.search(inner):
        return f" {inner} "
    return " "


def normalize_title(title: str) -> str:
    """Normalize a comic title for cross-provider deduplication (ADR 0031).

    1. Recursively strip bracketed metadata ([...], (...), 【...】, etc.) while preserving volume/part markers.
    2. Convert Traditional Chinese to Simplified Chinese.
    3. Collapse whitespace and separator punctuation while strictly preserving volume/part markers.
    4. Fallback to simplified stripped original title if stripping brackets leaves an empty string.
    """
    if not title:
        return ""
    cleaned = title
    for _ in range(3):
        next_cleaned = BRACKET_PATTERN.sub(_replace_bracket, cleaned)
        if next_cleaned == cleaned:
            break
        cleaned = next_cleaned
    simplified = to_simplified(cleaned)
    normalized = WHITESPACE_PUNCT_PATTERN.sub(" ", simplified).strip().lower()
    if not normalized:
        fallback = to_simplified(title)
        fb_norm = WHITESPACE_PUNCT_PATTERN.sub(" ", fallback).strip().lower()
        return fb_norm or title.strip().lower()
    return normalized
