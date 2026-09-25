"""Unit tests for multi-chapter auto-update engine and hiatus detection (ADR 0029)."""
import os
import shutil
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.auto_update import is_comic_in_hiatus, parse_comic_date, run_auto_update_cycle
from app.db import (
    get_comics_due_for_auto_update,
    init_db,
    record_comic_auto_checked,
    upsert_comic_index,
)
from app.models import Chapter, ComicMeta, FetchedComic, PageRecord, RemotePage
from app.storage import ComicStore


class TestAutoUpdateEngine(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "comic_shelf.db"
        init_db(self.db_path)
        self.store = ComicStore(Path(self.temp_dir) / "library")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_parse_comic_date(self):
        self.assertIsNone(parse_comic_date(""))
        self.assertIsNone(parse_comic_date("invalid-date-string"))

        dt1 = parse_comic_date("2026-09-25T18:00:00Z")
        self.assertIsNotNone(dt1)
        self.assertEqual(dt1.year, 2026)

        dt2 = parse_comic_date("2026-09-25 18:00:00")
        self.assertIsNotNone(dt2)
        self.assertEqual(dt2.month, 9)

        dt3 = parse_comic_date("2026-09-25")
        self.assertIsNotNone(dt3)
        self.assertEqual(dt3.day, 25)

    def test_is_comic_in_hiatus(self):
        now = datetime.now()
        recent_date = (now - timedelta(days=10)).strftime("%Y-%m-%d")
        old_date = (now - timedelta(days=35)).strftime("%Y-%m-%d")

        meta_active = ComicMeta(
            source="jm",
            source_id="1001",
            display_id="JM1001",
            title="连载中漫画",
            updated_at=recent_date,
        )
        self.assertFalse(is_comic_in_hiatus(meta_active, max_inactive_days=30))

        meta_hiatus = ComicMeta(
            source="jm",
            source_id="1002",
            display_id="JM1002",
            title="断更漫画",
            updated_at=old_date,
        )
        self.assertTrue(is_comic_in_hiatus(meta_hiatus, max_inactive_days=30))

        # Comic with no update date should not be falsely judged as hiatus
        meta_no_date = ComicMeta(
            source="jm",
            source_id="1003",
            display_id="JM1003",
            title="无日期漫画",
            updated_at="",
            published_at="",
        )
        self.assertFalse(is_comic_in_hiatus(meta_no_date, max_inactive_days=30))

    def test_get_comics_due_for_auto_update_filtering(self):
        # 1. Local comic -> should be excluded
        upsert_comic_index({
            "source": "local",
            "source_id": "loc1",
            "display_id": "LOC1",
            "title": "Local Multi",
            "chapter_titles_json": '["话1", "话2"]',
            "auto_update_interval_days": 15,
            "last_auto_checked_at": "",
        })

        # 2. Single chapter remote -> should be excluded
        upsert_comic_index({
            "source": "jm",
            "source_id": "single1",
            "display_id": "JM_single",
            "title": "Single Chapter",
            "chapter_titles_json": '["单话"]',
            "auto_update_interval_days": 15,
            "last_auto_checked_at": "",
        })

        # 3. Multi-chapter remote with auto update disabled (0) -> excluded
        upsert_comic_index({
            "source": "jm",
            "source_id": "disabled1",
            "display_id": "JM_disabled",
            "title": "Disabled Auto Update",
            "chapter_titles_json": '["话1", "话2"]',
            "auto_update_interval_days": 0,
            "last_auto_checked_at": "",
        })

        # 4. Multi-chapter remote with auto update enabled (15 days), never checked -> INCLUDED
        upsert_comic_index({
            "source": "jm",
            "source_id": "due1",
            "display_id": "JM_due1",
            "title": "Due Comic",
            "chapter_titles_json": '["话1", "话2"]',
            "auto_update_interval_days": 15,
            "last_auto_checked_at": "",
        })

        candidates = get_comics_due_for_auto_update(max_count=10)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["source_id"], "due1")

        # Mark as checked now -> should no longer be due
        checked_now = datetime.now(timezone.utc).isoformat()
        record_comic_auto_checked("jm", "due1", checked_now)
        candidates_after = get_comics_due_for_auto_update(max_count=10)
        self.assertEqual(len(candidates_after), 0)

    def test_run_auto_update_cycle_hiatus(self):
        # Set up a multi-chapter comic in storage with updated_at > 30 days ago
        now = datetime.now()
        old_date = (now - timedelta(days=40)).strftime("%Y-%m-%d")

        chapters = [
            Chapter(id="c1", index=1, title="第 1 话", page_count=2, start=1),
            Chapter(id="c2", index=2, title="第 2 话", page_count=2, start=3),
        ]
        pages = [
            PageRecord(index=1, file="00001.webp", ext=".webp", cached=False, chapter="c1"),
            PageRecord(index=2, file="00002.webp", ext=".webp", cached=False, chapter="c1"),
            PageRecord(index=3, file="00001.webp", ext=".webp", cached=False, chapter="c2"),
            PageRecord(index=4, file="00002.webp", ext=".webp", cached=False, chapter="c2"),
        ]
        meta = ComicMeta(
            source="jm",
            source_id="hiatus_comic",
            display_id="JM_hiatus",
            title="断更漫画",
            page_count=4,
            chapters=chapters,
            pages=pages,
            updated_at=old_date,
            auto_update_interval_days=15,
            last_auto_checked_at="",
        )
        fetched = FetchedComic(
            meta=meta,
            remote_pages=[
                RemotePage(index=1, url="http://1", file="00001.webp", ext=".webp", chapter="c1"),
                RemotePage(index=2, url="http://2", file="00002.webp", ext=".webp", chapter="c1"),
                RemotePage(index=3, url="http://3", file="00001.webp", ext=".webp", chapter="c2"),
                RemotePage(index=4, url="http://4", file="00002.webp", ext=".webp", chapter="c2"),
            ],
        )
        self.store.save_fetched(fetched)

        # Run cycle with mock provider
        with patch("app.auto_update.get_provider") as mock_get_provider:
            res = run_auto_update_cycle(self.store, max_check=10, sleep_seconds=0)
            self.assertEqual(res["total_due"], 1)
            self.assertEqual(res["hiatus"], 1)
            self.assertEqual(res["checked"], 0)
            # Provider should not have been called because hiatus short-circuited!
            mock_get_provider.assert_not_called()

            # Verify last_auto_checked_at was updated to avoid tight-loop probing
            updated_meta = self.store.load_meta("jm", "hiatus_comic")
            self.assertTrue(bool(updated_meta.last_auto_checked_at))

    def test_run_auto_update_cycle_new_chapter(self):
        # Set up active comic (updated 5 days ago)
        now = datetime.now()
        recent_date = (now - timedelta(days=5)).strftime("%Y-%m-%d")

        chapters = [
            Chapter(id="c1", index=1, title="第 1 话", page_count=2, start=1),
            Chapter(id="c2", index=2, title="第 2 话", page_count=2, start=3),
        ]
        pages = [
            PageRecord(index=1, file="00001.webp", ext=".webp", cached=False, chapter="c1"),
            PageRecord(index=2, file="00002.webp", ext=".webp", cached=False, chapter="c1"),
            PageRecord(index=3, file="00001.webp", ext=".webp", cached=False, chapter="c2"),
            PageRecord(index=4, file="00002.webp", ext=".webp", cached=False, chapter="c2"),
        ]
        meta = ComicMeta(
            source="jm",
            source_id="active_comic",
            display_id="JM_active",
            title="连载漫画",
            page_count=4,
            chapters=chapters,
            pages=pages,
            updated_at=recent_date,
            auto_update_interval_days=15,
            last_auto_checked_at="",
        )
        fetched = FetchedComic(
            meta=meta,
            remote_pages=[
                RemotePage(index=1, url="http://1", file="00001.webp", ext=".webp", chapter="c1"),
                RemotePage(index=2, url="http://2", file="00002.webp", ext=".webp", chapter="c1"),
                RemotePage(index=3, url="http://3", file="00001.webp", ext=".webp", chapter="c2"),
                RemotePage(index=4, url="http://4", file="00002.webp", ext=".webp", chapter="c2"),
            ],
        )
        self.store.save_fetched(fetched)

        # Mock remote provider returning a new chapter c3 (2 more pages)
        new_chapters = list(chapters) + [
            Chapter(id="c3", index=3, title="第 3 话", page_count=2, start=5)
        ]
        new_pages = list(pages) + [
            PageRecord(index=5, file="00001.webp", ext=".webp", cached=False, chapter="c3"),
            PageRecord(index=6, file="00002.webp", ext=".webp", cached=False, chapter="c3"),
        ]
        new_meta = meta.model_copy(deep=True)
        new_meta.chapters = new_chapters
        new_meta.pages = new_pages
        new_meta.page_count = 6
        new_fetched = FetchedComic(
            meta=new_meta,
            remote_pages=fetched.remote_pages + [
                RemotePage(index=5, url="http://5", file="00001.webp", ext=".webp", chapter="c3"),
                RemotePage(index=6, url="http://6", file="00002.webp", ext=".webp", chapter="c3"),
            ],
        )

        mock_provider = MagicMock()
        mock_provider.fetch.return_value = new_fetched

        with patch("app.auto_update.get_provider", return_value=mock_provider), \
             patch("app.auto_update.broadcast_event") as mock_broadcast:
            res = run_auto_update_cycle(self.store, max_check=10, sleep_seconds=0)
            self.assertEqual(res["total_due"], 1)
            self.assertEqual(res["checked"], 1)
            self.assertEqual(res["updated"], 1)
            self.assertEqual(res["hiatus"], 0)

            # Check that SSE was broadcasted with action=auto_update_append
            mock_broadcast.assert_called_once()
            args = mock_broadcast.call_args[0]
            self.assertEqual(args[0], "library_changed")
            self.assertEqual(args[1]["action"], "auto_update_append")
            self.assertEqual(args[1]["new_chapters"], 1)

            # Check that storage now reflects 3 chapters and 6 pages
            reloaded = self.store.load_meta("jm", "active_comic")
            self.assertEqual(len(reloaded.chapters), 3)
            self.assertEqual(reloaded.page_count, 6)


if __name__ == "__main__":
    unittest.main()
