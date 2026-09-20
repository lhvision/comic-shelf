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
