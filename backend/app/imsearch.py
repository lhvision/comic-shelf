from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request
import uuid
from typing import Any

from .config import IMSEARCH_URL
from .models import ImageSearchItem

logger = logging.getLogger("paper_room.imsearch")

# Bypass local system/environment HTTP proxies (e.g. Clash, v2ray) for direct Sidecar communication
_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

# Match library/<source>/<source_id>/covers/<num>.<ext>
# or library/<source>/<source_id>/covers/chapters/<chapter_id>.<ext>
# or library/<source>/<source_id>/(pages|thumbs)/.../<num>.<ext>
_COVER_PATTERN = re.compile(
    r"library[/\\](?P<source>[^/\\]+)[/\\](?P<source_id>[^/\\]+)[/\\]covers[/\\](?:chapters[/\\])?(?P<num>\d+)\.[a-zA-Z0-9]+$"
)
_PAGE_PATTERN = re.compile(
    r"library[/\\](?P<source>[^/\\]+)[/\\](?P<source_id>[^/\\]+)[/\\](?:pages|thumbs)[/\\](?:[^/\\]+[/\\])*(?P<num>\d+)\.[a-zA-Z0-9]+$"
)


def parse_imsearch_path(raw_path: str) -> tuple[str, str, int, bool] | None:
    """Extract (source, source_id, page_index, is_cover) from an image file path."""
    match = _COVER_PATTERN.search(raw_path)
    if match:
        return match.group("source"), match.group("source_id"), 1, True
    match = _PAGE_PATTERN.search(raw_path)
    if match:
        return match.group("source"), match.group("source_id"), int(match.group("num")), False
    return None


def check_imsearch_status(base_url: str = IMSEARCH_URL) -> dict[str, Any]:
    """Check whether the external imsearch sidecar is reachable."""
    try:
        req = urllib.request.Request(f"{base_url}/metrics", method="GET")
        with _opener.open(req, timeout=1.5) as resp:
            return {"available": resp.status == 200, "url": base_url}
    except Exception as e:
        logger.debug("Imsearch sidecar not available: %s", e)
        return {"available": False, "url": base_url}


def search_imsearch(
    image_bytes: bytes, base_url: str = IMSEARCH_URL, filename: str = "query.jpg"
) -> list[ImageSearchItem]:
    """Send image query to imsearch server and parse results."""
    try:
        boundary = f"----PaperRoomBoundary{uuid.uuid4().hex}"
        header = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            f"Content-Type: image/jpeg\r\n\r\n"
        ).encode("utf-8")
        footer = f"\r\n--{boundary}--\r\n".encode("utf-8")
        body = header + image_bytes + footer

        req = urllib.request.Request(
            f"{base_url}/search",
            data=body,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Content-Length": str(len(body)),
            },
            method="POST",
        )

        with _opener.open(req, timeout=10.0) as resp:
            if resp.status != 200:
                logger.warning("imsearch returned status %s", resp.status)
                return []
            raw_text = resp.read().decode("utf-8")

        data = json.loads(raw_text)
        raw_results = data.get("result", [])

        # Deduplicate matches per (source, source_id, page_index), retaining the highest score
        seen: dict[tuple[str, str, int, bool], float] = {}
        for item in raw_results:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                raw_score, path_str = float(item[0]), str(item[1])
                # Normalize 0..100 percentage score to 0..1 range
                score = raw_score / 100.0 if raw_score > 1.0 else raw_score
                # Discard low-confidence noise (<35%)
                if score < 0.35:
                    continue
                parsed = parse_imsearch_path(path_str)
                if parsed:
                    key = parsed
                    if key not in seen or score > seen[key]:
                        seen[key] = score

        results: list[ImageSearchItem] = [
            ImageSearchItem(
                source=src,
                source_id=sid,
                page_index=p_idx,
                is_cover=is_cov,
                score=round(sc, 4),
            )
            for (src, sid, p_idx, is_cov), sc in seen.items()
        ]
        # Sort descending by match score
        results.sort(key=lambda r: r.score, reverse=True)

        # Lowe's ratio & margin filter: discard candidates far weaker than the best match
        if results:
            top_score = results[0].score
            min_threshold = max(0.40, top_score * 0.80)
            results = [r for r in results if r.score >= min_threshold]

        return results
    except Exception as e:
        logger.warning("Failed to search image with imsearch: %s", e)
        return []
