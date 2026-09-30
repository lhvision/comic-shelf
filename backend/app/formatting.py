"""Shared display formatting helpers used by providers and storage."""
from __future__ import annotations


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


import re
from .zh_conv import to_simplified

BRACKET_PATTERN = re.compile(
    r"\[[^\]]*\]|［[^］]*］|【[^】]*】|〔[^〕]*〕|〖[^〗]*〗|〘[^〙]*〙|\([^\)]*\)|（[^）]*）|\{[^\}]*\}|｛[^｝]*｝"
)
WHITESPACE_PUNCT_PATTERN = re.compile(r"[\s\-_:：·・,.，。！？!?~～/／\\、|｜#＃]+")


def normalize_title(title: str) -> str:
    """Normalize a comic title for cross-provider deduplication (ADR 0031).

    1. Recursively strip bracketed metadata ([...], (...), 【...】, etc.).
    2. Convert Traditional Chinese to Simplified Chinese.
    3. Collapse whitespace and separator punctuation while strictly preserving volume/part markers.
    4. Fallback to simplified stripped original title if stripping brackets leaves an empty string.
    """
    if not title:
        return ""
    cleaned = title
    for _ in range(3):
        next_cleaned = BRACKET_PATTERN.sub(" ", cleaned)
        if next_cleaned == cleaned:
            break
        cleaned = next_cleaned
    simplified = to_simplified(cleaned)
    normalized = WHITESPACE_PUNCT_PATTERN.sub(" ", simplified).strip().lower()
    if not normalized:
        fallback = to_simplified(title)
        return WHITESPACE_PUNCT_PATTERN.sub(" ", fallback).strip().lower()
    return normalized
