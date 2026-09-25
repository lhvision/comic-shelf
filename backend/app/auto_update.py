"""Multi-chapter comic auto-update engine and background scheduler.

Implements ADR 0029:
- Periodic auto-update inspection for non-local multi-chapter comics.
- 30-day hiatus detection and throttling: skips remote inspection if updated_at > 30 days ago.
- Preserves reading status and self-heals from completed to reading.
- Auto-triggers background prefetch if the comic was previously fully cached.
- Throttles requests with 3s delays between inspections to avoid upstream rate limiting.
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any

from .db import get_comics_due_for_auto_update, record_comic_auto_checked
from .events import broadcast_event
from .jobs import start_job
from .models import ComicMeta
from .providers import get_provider
from .routers.common import _prefetch_worker
from .storage import ComicStore
from .storage.utils import _write_json_atomic

logger = logging.getLogger("paper_room.auto_update")


def parse_comic_date(date_str: str) -> datetime | None:
    """Parses various date and timestamp formats from remote providers or local records."""
    if not date_str or not str(date_str).strip():
        return None
    s = str(date_str).strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(s)
    except Exception:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            pass
    return None


def is_comic_in_hiatus(meta_or_date: str | ComicMeta, max_inactive_days: int = 30) -> bool:
    """Checks whether the comic has had no remote updates in over 30 days (1 month).

    Comics judged as in hiatus are paused from automatic background inspection to save
    network bandwidth and prevent upstream anti-bot triggers.
    """
    if isinstance(meta_or_date, ComicMeta):
        date_str = meta_or_date.updated_at or meta_or_date.published_at or meta_or_date.imported_at
    else:
        date_str = str(meta_or_date)

    dt = parse_comic_date(date_str)
    if dt is None:
        return False

    now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
    diff_seconds = (now - dt).total_seconds()
    return diff_seconds > (max_inactive_days * 86400)


def run_auto_update_cycle(
    store: ComicStore,
    max_check: int = 10,
    sleep_seconds: float = 3.0,
) -> dict[str, Any]:
    """Executes a single pass of auto-update inspections across eligible multi-chapter comics.

    Runs synchronously (intended to be executed in a background worker thread).
    """
    candidates = get_comics_due_for_auto_update(max_count=max_check)
    if not candidates:
        return {"total_due": 0, "checked": 0, "updated": 0, "hiatus": 0, "errors": []}

    logger.info("Starting auto-update cycle for %d candidate comics", len(candidates))
    checked_count = 0
    updated_count = 0
    hiatus_count = 0
    errors: list[dict[str, str]] = []

    for idx, cand in enumerate(candidates):
        source = cand["source"]
        source_id = cand["source_id"]

        try:
            meta = store.load_meta(source, source_id)
            if meta is None:
                continue

            # Must be non-local multi-chapter
            if meta.source == "local" or len(meta.chapters) <= 1:
                continue

            # Respect re-bound protection (ADR 0020)
            if meta.custom_pages:
                logger.info("Skipping auto-update for %s/%s: re-bound protection active", source, source_id)
                continue

            checked_at = datetime.now(timezone.utc).isoformat()

            # Hiatus detection: skip if remote hasn't updated in > 30 days
            if is_comic_in_hiatus(meta, max_inactive_days=30):
                hiatus_count += 1
                logger.info(
                    "Comic %s/%s is in hiatus (> 30 days without update, last: %s); skipping auto-check",
                    source,
                    source_id,
                    meta.updated_at or meta.published_at,
                )
                meta.last_auto_checked_at = checked_at
                _write_json_atomic(store.album_path(source, source_id), meta.model_dump())
                record_comic_auto_checked(source, source_id, checked_at)
                continue

            # Remote incremental fetch
            checked_count += 1
            cached_bundle = store.load_fetched(source, source_id)
            prev_chaps = len(cached_bundle.meta.chapters) if cached_bundle else 0
            prev_pages = cached_bundle.meta.page_count if cached_bundle else 0
            was_fully_cached = (
                prev_pages > 0 and store.cached_page_count(cached_bundle.meta) >= prev_pages
            ) if cached_bundle else False

            provider = get_provider(source)
            fetched = provider.fetch(source_id, existing=cached_bundle)
            fetched.meta.last_auto_checked_at = checked_at

            new_chapters_count = len(fetched.meta.chapters) - prev_chaps
            has_new_content = new_chapters_count > 0 or fetched.meta.page_count > prev_pages

            saved_meta = store.save_fetched(fetched, refresh=True)
            record_comic_auto_checked(source, source_id, checked_at)

            if has_new_content:
                updated_count += 1
                logger.info(
                    "Auto-update detected %d new chapters (%d -> %d pages) for %s/%s",
                    new_chapters_count,
                    prev_pages,
                    saved_meta.page_count,
                    source,
                    source_id,
                )
                broadcast_event(
                    "library_changed",
                    {
                        "action": "auto_update_append",
                        "source": source,
                        "source_id": source_id,
                        "new_chapters": max(0, new_chapters_count),
                        "timestamp": time.time(),
                    },
                )

                # Auto-prefetch new pages if previously fully cached
                if was_fully_cached:
                    start_job(
                        source,
                        source_id,
                        lambda job: _prefetch_worker(job, fetched, fetched.meta.cover_count, True),
                    )

            if idx < len(candidates) - 1 and sleep_seconds > 0:
                time.sleep(sleep_seconds)

        except Exception as exc:
            logger.warning("Auto-update failed for %s/%s: %s", source, source_id, exc)
            errors.append({"source": source, "source_id": source_id, "error": str(exc)})
            # Record checked timestamp so a broken/failing comic doesn't loop infinitely
            try:
                checked_at = datetime.now(timezone.utc).isoformat()
                record_comic_auto_checked(source, source_id, checked_at)
            except Exception:
                pass

    return {
        "total_due": len(candidates),
        "checked": checked_count,
        "updated": updated_count,
        "hiatus": hiatus_count,
        "errors": errors,
    }


async def auto_update_loop(store: ComicStore, interval_seconds: int = 3600) -> None:
    """Asyncio background daemon loop running periodic auto-update cycles.

    Wakes up every ``interval_seconds`` (default 1 hour) to inspect due comics.
    """
    logger.info("Auto-update background daemon started (check interval: %ds)", interval_seconds)
    # Grace period after server boot before starting first auto-update pass
    try:
        await asyncio.sleep(30)
    except asyncio.CancelledError:
        return

    while True:
        try:
            await asyncio.to_thread(run_auto_update_cycle, store)
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.exception("Unexpected error in auto_update_loop: %s", exc)

        try:
            await asyncio.sleep(interval_seconds)
        except asyncio.CancelledError:
            break
