"""Multi-chapter comic auto-update engine and background scheduler.

Implements ADR 0029:
- Periodic auto-update inspection for non-local multi-chapter comics.
- Merges remote chapter additions while strictly preserving curator-edited metadata.
- Re-bound protection (ADR 0020): skips comics with custom_pages and records check timestamp.
- Preserves reading status and self-heals from completed to reading.
- Auto-triggers background prefetch if the comic was previously fully cached.
- Throttles requests with 3s delays between inspections to avoid upstream rate limiting.
- Graceful shutdown integration via threading.Event.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any

from .db import get_comics_due_for_auto_update
from .events import broadcast_event
from .jobs import start_job
from .providers import get_provider
from .routers.common import _prefetch_worker
from .storage import ComicStore

logger = logging.getLogger("paper_room.auto_update")


def run_auto_update_cycle(
    store: ComicStore,
    max_check: int = 10,
    sleep_seconds: float = 3.0,
    stop_event: threading.Event | None = None,
) -> dict[str, Any]:
    """Executes a single pass of auto-update inspections across eligible multi-chapter comics.

    Runs synchronously (intended to be executed in a background worker thread).
    """
    candidates = get_comics_due_for_auto_update(max_count=max_check)
    if not candidates:
        return {"total_due": 0, "checked": 0, "updated": 0, "errors": []}

    logger.info("Starting auto-update cycle for %d candidate comics", len(candidates))
    checked_count = 0
    updated_count = 0
    errors: list[dict[str, str]] = []

    for idx, cand in enumerate(candidates):
        if stop_event is not None and stop_event.is_set():
            logger.info("Auto-update cycle stopped by stop event")
            break

        if idx > 0 and sleep_seconds > 0:
            if stop_event is not None:
                if stop_event.wait(sleep_seconds):
                    break
            else:
                time.sleep(sleep_seconds)

        source = cand["source"]
        source_id = cand["source_id"]
        checked_at = datetime.now(timezone.utc).isoformat()

        try:
            meta = store.load_meta(source, source_id)
            if meta is None or meta.source == "local" or len(meta.chapters) <= 1:
                store.record_auto_checked(source, source_id, checked_at)
                continue

            # Respect re-bound protection (ADR 0020) and record check to prevent starvation
            if meta.custom_pages:
                logger.info("Skipping auto-update for %s/%s: re-bound protection active", source, source_id)
                store.record_auto_checked(source, source_id, checked_at)
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

            new_chapters_count = len(fetched.meta.chapters) - prev_chaps
            has_new_content = new_chapters_count > 0 or fetched.meta.page_count > prev_pages

            if has_new_content:
                # 馆长编辑过的资料不动，只并入章节与画页；抓取期间被删的作品不写回
                saved_meta = store.save_auto_update(fetched, checked_at)
                if saved_meta is None:
                    continue
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
                        lambda job, f=fetched: _prefetch_worker(job, f, f.meta.cover_count, True),
                    )
            else:
                # No new chapters/pages: do not overwrite curator metadata, only record checked timestamp
                store.record_auto_checked(source, source_id, checked_at)

        except Exception as exc:
            logger.warning("Auto-update failed for %s/%s: %s", source, source_id, exc)
            errors.append({"source": source, "source_id": source_id, "error": str(exc)})
            try:
                store.record_auto_checked(source, source_id, checked_at)
            except Exception:
                pass

    return {
        "total_due": len(candidates),
        "checked": checked_count,
        "updated": updated_count,
        "errors": errors,
    }


def auto_update_worker(
    store: ComicStore,
    stop_event: threading.Event,
    interval_seconds: int = 3600,
) -> None:
    """后台巡检线程：开机宽限 30 秒后，每 ``interval_seconds`` 秒跑一轮。

    ``stop_event`` 置位后把手上这本处理完就返回；lifespan 要 join 本线程之后才释放书库写锁。
    """
    logger.info("Auto-update background worker started (check interval: %ds)", interval_seconds)
    if stop_event.wait(30):
        return
    while True:
        try:
            run_auto_update_cycle(store, stop_event=stop_event)
        except Exception:
            logger.exception("Unexpected error in auto-update worker")
        if stop_event.wait(interval_seconds):
            return
