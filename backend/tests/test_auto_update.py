"""Unit tests for multi-chapter auto-update engine and curator metadata protection (ADR 0029)."""
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.auto_update import run_auto_update_cycle
from app.db import (
    get_comics_due_for_auto_update,
    init_db,
    record_comic_auto_checked,
    upsert_comic_index,
)
from app.models import Chapter, ComicMeta, FetchedComic, PageRecord, RemotePage
from app.storage import ComicStore


def make_comic_index_item(source: str, source_id: str, title: str = "Test Comic", **kwargs) -> dict:
    item = {
        "source": source,
        "source_id": source_id,
        "display_id": f"{source.upper()}_{source_id}",
        "title": title,
        "authors_json": "[]",
        "works_json": "[]",
        "actors_json": "[]",
        "tags_json": "[]",
        "chapter_titles_json": '["话1", "话2"]',
        "page_count": 10,
        "cached_pages": 0,
        "cover_count": 4,
        "cover_indices_json": "[]",
        "views": "",
        "likes": "",
        "uploaded_at": "",
        "published_at": "",
        "updated_at": "",
        "imported_at": datetime.now(timezone.utc).isoformat(),
        "hidden_from_guest": 0,
        "mtime": 100.0,
        "auto_update_interval_days": 15,
        "last_auto_checked_at": "",
    }
    item.update(kwargs)
    return item


class TestAutoUpdateEngine(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "comic_shelf.db"
        init_db(self.db_path)
        self.store = ComicStore(Path(self.temp_dir) / "library")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_get_comics_due_for_auto_update_filtering(self):
        # 1. Local comic -> should be excluded
        upsert_comic_index(make_comic_index_item(
            source="local",
            source_id="loc1",
            chapter_titles_json='["话1", "话2"]',
            auto_update_interval_days=15,
        ))

        # 2. Single chapter remote -> should be excluded
        upsert_comic_index(make_comic_index_item(
            source="jm",
            source_id="single1",
            chapter_titles_json='["单话"]',
            auto_update_interval_days=15,
        ))

        # 3. Multi-chapter remote with auto update disabled (0) -> excluded
        upsert_comic_index(make_comic_index_item(
            source="jm",
            source_id="disabled1",
            chapter_titles_json='["话1", "话2"]',
            auto_update_interval_days=0,
        ))

        # 4. Multi-chapter remote with auto update enabled (15 days), never checked -> INCLUDED
        upsert_comic_index(make_comic_index_item(
            source="jm",
            source_id="due1",
            chapter_titles_json='["话1", "话2"]',
            auto_update_interval_days=15,
            last_auto_checked_at="",
        ))

        candidates = get_comics_due_for_auto_update(max_count=10)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["source_id"], "due1")

        # Mark as checked now -> should no longer be due
        checked_now = datetime.now(timezone.utc).isoformat()
        record_comic_auto_checked("jm", "due1", checked_now)
        candidates_after = get_comics_due_for_auto_update(max_count=10)
        self.assertEqual(len(candidates_after), 0)

    def test_curator_metadata_preserved_when_no_new_content(self):
        """P0 regression test: When auto-update inspects a comic with no new chapters,

        the curator's edited title, tags, and description must remain strictly intact.
        """
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
            source_id="curator_comic",
            display_id="JM_curator",
            title="馆长自定义标题",
            authors=["馆长自定义作者"],
            tags=["馆长自定标签A", "馆长自定标签B"],
            description="馆长手写简介",
            page_count=4,
            chapters=chapters,
            pages=pages,
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

        # Provider returns same chapters but with upstream raw title/tags
        remote_raw_meta = meta.model_copy(deep=True)
        remote_raw_meta.title = "远端原始网站标题"
        remote_raw_meta.authors = ["远端原作者"]
        remote_raw_meta.tags = ["远端未清洗标签"]
        remote_raw_meta.description = "远端简介"

        mock_provider = MagicMock()
        mock_provider.fetch.return_value = FetchedComic(
            meta=remote_raw_meta,
            remote_pages=fetched.remote_pages,
        )

        with patch("app.auto_update.get_provider", return_value=mock_provider):
            res = run_auto_update_cycle(self.store, max_check=10, sleep_seconds=0)
            self.assertEqual(res["total_due"], 1)
            self.assertEqual(res["checked"], 1)
            self.assertEqual(res["updated"], 0)

        # Verify curator's metadata is 100% preserved
        reloaded = self.store.load_meta("jm", "curator_comic")
        self.assertEqual(reloaded.title, "馆长自定义标题")
        self.assertEqual(reloaded.authors, ["馆长自定义作者"])
        self.assertEqual(reloaded.tags, ["馆长自定标签A", "馆长自定标签B"])
        self.assertEqual(reloaded.description, "馆长手写简介")
        self.assertTrue(bool(reloaded.last_auto_checked_at))

    def test_curator_metadata_preserved_when_new_content_appended(self):
        """P0 regression test: When auto-update detects new chapters, it must append chapters

        while preserving curator-edited title, tags, and description.
        """
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
            source_id="curator_new_chap",
            display_id="JM_new_chap",
            title="馆长精心设定的标题",
            authors=["馆长设定的作者"],
            tags=["典藏", "同人"],
            description="馆长定制简介",
            page_count=4,
            chapters=chapters,
            pages=pages,
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

        # Provider returns 3 chapters, but with raw remote title/tags
        new_chapters = list(chapters) + [
            Chapter(id="c3", index=3, title="第 3 话", page_count=2, start=5)
        ]
        new_pages = list(pages) + [
            PageRecord(index=5, file="00001.webp", ext=".webp", cached=False, chapter="c3"),
            PageRecord(index=6, file="00002.webp", ext=".webp", cached=False, chapter="c3"),
        ]
        provider_meta = ComicMeta(
            source="jm",
            source_id="curator_new_chap",
            display_id="JM_new_chap",
            title="远端覆盖标题（应被丢弃）",
            authors=["远端原作者"],
            tags=["远端标签"],
            description="远端覆盖简介（应被丢弃）",
            page_count=6,
            chapters=new_chapters,
            pages=new_pages,
            auto_update_interval_days=15,
        )
        mock_provider = MagicMock()
        mock_provider.fetch.return_value = FetchedComic(
            meta=provider_meta,
            remote_pages=fetched.remote_pages + [
                RemotePage(index=5, url="http://5", file="00001.webp", ext=".webp", chapter="c3"),
                RemotePage(index=6, url="http://6", file="00002.webp", ext=".webp", chapter="c3"),
            ],
        )

        with patch("app.auto_update.get_provider", return_value=mock_provider), \
             patch("app.auto_update.broadcast_event"):
            res = run_auto_update_cycle(self.store, max_check=10, sleep_seconds=0)
            self.assertEqual(res["total_due"], 1)
            self.assertEqual(res["checked"], 1)
            self.assertEqual(res["updated"], 1)

        reloaded = self.store.load_meta("jm", "curator_new_chap")
        # Structural fields updated:
        self.assertEqual(len(reloaded.chapters), 3)
        self.assertEqual(reloaded.page_count, 6)
        # Curator metadata strictly preserved:
        self.assertEqual(reloaded.title, "馆长精心设定的标题")
        self.assertEqual(reloaded.authors, ["馆长设定的作者"])
        self.assertEqual(reloaded.tags, ["典藏", "同人"])
        self.assertEqual(reloaded.description, "馆长定制简介")

    def test_fetch_window_keeps_curator_edits_and_deletions(self):
        """抓取要花几秒：这期间馆长改的资料不能被抓取前的旧快照盖掉，删掉的作品也不能被写回来。"""
        for source_id in ("edited", "deleted"):
            self.store.save_fetched(FetchedComic(
                meta=ComicMeta(
                    source="jm",
                    source_id=source_id,
                    display_id=f"JM_{source_id}",
                    title="旧标题",
                    page_count=2,
                    chapters=[
                        Chapter(id="c1", index=1, title="第 1 话", page_count=1, start=1),
                        Chapter(id="c2", index=2, title="第 2 话", page_count=1, start=2),
                    ],
                    pages=[
                        PageRecord(index=1, file="00001.webp", ext=".webp", chapter="c1"),
                        PageRecord(index=2, file="00001.webp", ext=".webp", chapter="c2"),
                    ],
                ),
                remote_pages=[],
            ))

        def fetch_while_curator_acts(source_id, existing=None):
            if source_id == "edited":
                self.store.update_metadata("jm", source_id, {"title": "抓取期间改的标题"})
            else:
                self.store.delete("jm", source_id)
            remote = existing.meta.model_copy(deep=True)
            remote.chapters.append(Chapter(id="c3", index=3, title="第 3 话", page_count=1, start=3))
            remote.pages.append(PageRecord(index=3, file="00001.webp", ext=".webp", chapter="c3"))
            remote.page_count = 3
            return FetchedComic(meta=remote, remote_pages=[])

        mock_provider = MagicMock()
        mock_provider.fetch.side_effect = fetch_while_curator_acts
        with patch("app.auto_update.get_provider", return_value=mock_provider), \
                patch("app.auto_update.broadcast_event"):
            res = run_auto_update_cycle(self.store, max_check=10, sleep_seconds=0)

        self.assertEqual(res["updated"], 1)
        edited = self.store.load_meta("jm", "edited")
        self.assertEqual(edited.title, "抓取期间改的标题")
        self.assertEqual(edited.page_count, 3)
        self.assertIsNone(self.store.load_meta("jm", "deleted"))
        self.assertFalse(self.store.comic_dir("jm", "deleted").exists())

    def test_rebound_protection_and_starvation_prevention(self):
        """P1 #3 regression test: Comics with custom_pages=True must be skipped

        AND must record last_auto_checked_at so they do not starve the inspection queue.
        """
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
            source_id="rebound_comic",
            display_id="JM_rebound",
            title="重新装订漫画",
            page_count=4,
            chapters=chapters,
            pages=pages,
            custom_pages=True,
            auto_update_interval_days=15,
            last_auto_checked_at="",
        )
        fetched = FetchedComic(meta=meta, remote_pages=[])
        self.store.save_fetched(fetched)

        with patch("app.auto_update.get_provider") as mock_provider:
            res = run_auto_update_cycle(self.store, max_check=10, sleep_seconds=0)
            self.assertEqual(res["total_due"], 1)
            self.assertEqual(res["checked"], 0)
            mock_provider.assert_not_called()

            # Verify checked_at timestamp was recorded to prevent queue starvation
            reloaded = self.store.load_meta("jm", "rebound_comic")
            self.assertTrue(bool(reloaded.last_auto_checked_at))

            # Next query should return 0 candidates
            next_due = get_comics_due_for_auto_update(max_count=10)
            self.assertEqual(len(next_due), 0)

    def test_stop_event_interrupts_cycle(self):
        """P2 #5 regression test: stop_event signals worker to immediately abort cycle."""
        stop_event = threading.Event()
        stop_event.set()

        chapters = [
            Chapter(id="c1", index=1, title="第 1 话", page_count=2, start=1),
            Chapter(id="c2", index=2, title="第 2 话", page_count=2, start=3),
        ]
        meta = ComicMeta(
            source="jm",
            source_id="stop_comic",
            display_id="JM_stop",
            title="待停漫画",
            page_count=4,
            chapters=chapters,
            pages=[],
            auto_update_interval_days=15,
            last_auto_checked_at="",
        )
        self.store.save_fetched(FetchedComic(meta=meta, remote_pages=[]))

        with patch("app.auto_update.get_provider") as mock_provider:
            res = run_auto_update_cycle(self.store, max_check=10, sleep_seconds=1.0, stop_event=stop_event)
            self.assertEqual(res["checked"], 0)
            mock_provider.assert_not_called()

    def test_lifespan_keeps_writer_lock_until_worker_exits(self):
        """P2 #5 回归：关停时要等巡检线程写完手上这本，lifespan 才能释放书库写锁。"""
        import asyncio

        import app.main as main_mod
        from app.storage.utils import acquire_library_writer_lock

        library = Path(self.temp_dir) / "lifespan_library"
        lock_seen: list[str] = []

        def busy_worker(store, stop_event):
            stop_event.wait()
            time.sleep(0.2)  # 关停信号到达时，手上这本还在抓取、写盘
            try:
                probe = acquire_library_writer_lock(library)
            except RuntimeError:
                lock_seen.append("held")
            else:
                os.close(probe)
                lock_seen.append("released")

        async def serve_once():
            async with main_mod.lifespan(main_mod.app):
                pass

        old_root = main_mod.store.root
        main_mod.store.root = library
        try:
            # 暂存 PDF 清扫走的是真实 TMP_DIR，这里必须挡掉
            with patch.object(main_mod, "LIBRARY_DIR", library), \
                    patch.object(main_mod, "ENABLE_AUTO_UPDATE", True), \
                    patch.object(main_mod, "auto_update_worker", busy_worker), \
                    patch.object(main_mod.store, "_cleanup_staged_pdfs"):
                asyncio.run(serve_once())
        finally:
            main_mod.store.root = old_root

        self.assertEqual(lock_seen, ["held"])

    def test_import_and_refresh_sets_last_auto_checked_at(self):
        """收录与手动刷新都必须写入 last_auto_checked_at，防止新收录的作品立即到期。"""
        import app.routers.library as lib_router
        from app.models import ImportRequest

        chapters = [
            Chapter(id="c1", index=1, title="第 1 话", page_count=2, start=1),
            Chapter(id="c2", index=2, title="第 2 话", page_count=2, start=3),
        ]
        pages = [
            PageRecord(index=1, file="00001.webp", ext=".webp", chapter="c1"),
            PageRecord(index=2, file="00002.webp", ext=".webp", chapter="c1"),
            PageRecord(index=3, file="00001.webp", ext=".webp", chapter="c2"),
            PageRecord(index=4, file="00002.webp", ext=".webp", chapter="c2"),
        ]
        remote = ComicMeta(
            source="jm",
            source_id="new_import_comic",
            display_id="JM_new_import_comic",
            title="新收录漫画",
            page_count=4,
            chapters=chapters,
            pages=pages,
            auto_update_interval_days=15,
        )
        mock_provider = MagicMock()
        mock_provider.normalize_id.return_value = "new_import_comic"
        mock_provider.fetch.return_value = FetchedComic(meta=remote, remote_pages=[])

        with patch.object(lib_router, "store", self.store), \
                patch("app.routers.library.get_provider", return_value=mock_provider), \
                patch("app.routers.library.start_job"), \
                patch("app.routers.library.broadcast_event"):
            # 1. 首次收录 (refresh=False)
            res1 = lib_router.import_comic(ImportRequest(source="jm", id="new_import_comic", refresh=False))
            self.assertTrue(bool(res1.meta.last_auto_checked_at))
            reloaded1 = self.store.load_meta("jm", "new_import_comic")
            self.assertEqual(reloaded1.last_auto_checked_at, res1.meta.last_auto_checked_at)

            # 新收录作品由于刚写了巡检时间，绝不能立即进入待巡检队列
            due = get_comics_due_for_auto_update(max_count=10)
            self.assertEqual(len(due), 0)

            # 2. 手动刷新 (refresh=True)
            res2 = lib_router.import_comic(ImportRequest(source="jm", id="new_import_comic", refresh=True))
            self.assertTrue(bool(res2.meta.last_auto_checked_at))
            reloaded2 = self.store.load_meta("jm", "new_import_comic")
            self.assertEqual(reloaded2.last_auto_checked_at, res2.meta.last_auto_checked_at)

    def test_auto_update_heals_published_at_and_enforces_monotonicity(self):
        """P0 regression test: When auto-update discovers an earlier true published_at

        or later updated_at, it heals published_at and advances updated_at while preserving
        monotonicity (published_at never moves forward, updated_at never regresses).
        """
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
        # Existing comic has drifted published_at: 2025-10-05 and updated_at: 2025-10-05
        meta = ComicMeta(
            source="jm",
            source_id="drifted_dates_comic",
            display_id="JM_drifted",
            title="测试追更漫画",
            published_at="2025-10-05",
            updated_at="2025-10-05",
            page_count=4,
            chapters=chapters,
            pages=pages,
            auto_update_interval_days=7,
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

        # Provider returns 3 chapters with true earlier published_at: 2025-10-01 and new update: 2026-03-01
        new_chapters = list(chapters) + [
            Chapter(id="c3", index=3, title="第 3 话", page_count=2, start=5)
        ]
        new_pages = list(pages) + [
            PageRecord(index=5, file="00001.webp", ext=".webp", cached=False, chapter="c3"),
            PageRecord(index=6, file="00002.webp", ext=".webp", cached=False, chapter="c3"),
        ]
        provider_meta = ComicMeta(
            source="jm",
            source_id="drifted_dates_comic",
            display_id="JM_drifted",
            title="测试追更漫画",
            published_at="2025-10-01",  # Healed earlier date
            updated_at="2026-03-01",    # New chapter date
            page_count=6,
            chapters=new_chapters,
            pages=new_pages,
            auto_update_interval_days=7,
        )
        mock_provider = MagicMock()
        mock_provider.fetch.return_value = FetchedComic(
            meta=provider_meta,
            remote_pages=fetched.remote_pages + [
                RemotePage(index=5, url="http://5", file="00001.webp", ext=".webp", chapter="c3"),
                RemotePage(index=6, url="http://6", file="00002.webp", ext=".webp", chapter="c3"),
            ],
        )

        with patch("app.auto_update.get_provider", return_value=mock_provider), \
             patch("app.auto_update.broadcast_event"):
            res = run_auto_update_cycle(self.store, max_check=10, sleep_seconds=0)
            self.assertEqual(res["updated"], 1)

        reloaded = self.store.load_meta("jm", "drifted_dates_comic")
        # 1. published_at healed from 2025-10-05 to earlier 2025-10-01
        self.assertEqual(reloaded.published_at, "2025-10-01")
        # 2. updated_at advanced from 2025-10-05 to 2026-03-01
        self.assertEqual(reloaded.updated_at, "2026-03-01")
        # 3. Partial ordering holds
        self.assertLessEqual(reloaded.published_at, reloaded.updated_at)

    def test_auto_update_heals_legacy_zero_sentinel_dates(self):
        """P1 regression test: When auto-update encounters legacy '0' sentinel dates

        in existing record, it successfully heals published_at and updated_at
        without getting trapped by falsy/dictionary-order anomalies.
        """
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
            source_id="zero_sentinel_comic",
            display_id="JM_zero",
            title="测试零值漫画",
            published_at="0",
            updated_at="0",
            page_count=4,
            chapters=chapters,
            pages=pages,
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

        # Provider returns 3 chapters with healed dates
        new_chapters = list(chapters) + [
            Chapter(id="c3", index=3, title="第 3 话", page_count=2, start=5)
        ]
        new_pages = list(pages) + [
            PageRecord(index=5, file="00001.webp", ext=".webp", cached=False, chapter="c3"),
            PageRecord(index=6, file="00002.webp", ext=".webp", cached=False, chapter="c3"),
        ]
        provider_meta = ComicMeta(
            source="jm",
            source_id="zero_sentinel_comic",
            display_id="JM_zero",
            title="测试零值漫画",
            published_at="2025-10-01",
            updated_at="2025-10-03",
            page_count=6,
            chapters=new_chapters,
            pages=new_pages,
            auto_update_interval_days=15,
        )
        mock_provider = MagicMock()
        mock_provider.fetch.return_value = FetchedComic(
            meta=provider_meta,
            remote_pages=fetched.remote_pages + [
                RemotePage(index=5, url="http://5", file="00001.webp", ext=".webp", chapter="c3"),
                RemotePage(index=6, url="http://6", file="00002.webp", ext=".webp", chapter="c3"),
            ],
        )

        with patch("app.auto_update.get_provider", return_value=mock_provider), \
             patch("app.auto_update.broadcast_event"):
            res = run_auto_update_cycle(self.store, max_check=10, sleep_seconds=0)
            self.assertEqual(res["updated"], 1)

        reloaded = self.store.load_meta("jm", "zero_sentinel_comic")
        self.assertEqual(reloaded.published_at, "2025-10-01")
        self.assertEqual(reloaded.updated_at, "2025-10-03")

    def test_dormancy_backoff_and_curator_supremacy(self):
        """测试 60 天休眠退避机制与馆长自定义周期的协同（ADR 0029 修订）。"""
        now = datetime.now(timezone.utc)
        date_70_days_ago = (now - timedelta(days=70)).strftime("%Y-%m-%d")
        date_10_days_ago = (now - timedelta(days=10)).strftime("%Y-%m-%d")

        # 1. Comic A：默认 15 天，已停更 70 天，20 天前检查过 -> 自动退避至 60 天，此时未满 60 天不应到期
        upsert_comic_index(make_comic_index_item(
            source="jm",
            source_id="dormant_not_due",
            chapter_titles_json='["话1", "话2"]',
            updated_at=date_70_days_ago,
            auto_update_interval_days=15,
            last_auto_checked_at=(now - timedelta(days=20)).isoformat(),
        ))

        # 2. Comic B：默认 15 天，已停更 70 天，65 天前检查过 -> 退避至 60 天且已满 60 天 -> 应到期
        upsert_comic_index(make_comic_index_item(
            source="jm",
            source_id="dormant_due",
            chapter_titles_json='["话1", "话2"]',
            updated_at=date_70_days_ago,
            auto_update_interval_days=15,
            last_auto_checked_at=(now - timedelta(days=65)).isoformat(),
        ))

        # 3. Comic C：默认 15 天，10 天前活跃更新，16 天前检查过 -> 维持 15 天且已满 15 天 -> 应到期
        upsert_comic_index(make_comic_index_item(
            source="jm",
            source_id="active_due",
            chapter_titles_json='["话1", "话2"]',
            updated_at=date_10_days_ago,
            auto_update_interval_days=15,
            last_auto_checked_at=(now - timedelta(days=16)).isoformat(),
        ))

        # 4. Comic D：馆长自定 7 天，已停更 70 天，8 天前检查过 -> 馆长优先不退避且已满 7 天 -> 应到期
        upsert_comic_index(make_comic_index_item(
            source="jm",
            source_id="curator_7d_due",
            chapter_titles_json='["话1", "话2"]',
            updated_at=date_70_days_ago,
            auto_update_interval_days=7,
            last_auto_checked_at=(now - timedelta(days=8)).isoformat(),
        ))

        due_candidates = get_comics_due_for_auto_update(max_count=10)
        due_ids = {c["source_id"] for c in due_candidates}

        self.assertNotIn("dormant_not_due", due_ids, "停更 70 天的漫画应退避至 60 天，距上次检查仅 20 天不应到期")
        self.assertIn("dormant_due", due_ids, "停更 70 天且距上次检查 65 天应到期")
        self.assertIn("active_due", due_ids, "活跃漫画（10 天前更新）应保持 15 天周期到期")
        self.assertIn("curator_7d_due", due_ids, "馆长自定义 7 天的高频追更不受休眠退避影响，8 天已到期")

    def test_dormancy_backoff_self_heals_when_new_chapter_found(self):
        """测试休眠状态的漫画在探测到新章节后，自动自愈恢复 15 天基准周期。"""
        now = datetime.now(timezone.utc)
        date_70_days_ago = (now - timedelta(days=70)).strftime("%Y-%m-%d")
        today_str = now.strftime("%Y-%m-%d")

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
            source_id="dormant_heal",
            display_id="JM_dormant_heal",
            title="休眠自愈测试本",
            updated_at=date_70_days_ago,
            page_count=4,
            chapters=chapters,
            pages=pages,
            auto_update_interval_days=15,
            last_auto_checked_at=(now - timedelta(days=65)).isoformat(),
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

        # 此时应到期（满 60 天）
        due = get_comics_due_for_auto_update(max_count=10)
        self.assertIn("dormant_heal", {c["source_id"] for c in due})

        # Mock 远端返回新章节 c3，日期为今日
        new_chapters = list(chapters) + [
            Chapter(id="c3", index=3, title="第 3 话", page_count=2, start=5)
        ]
        new_pages = list(pages) + [
            PageRecord(index=5, file="00001.webp", ext=".webp", cached=False, chapter="c3"),
            PageRecord(index=6, file="00002.webp", ext=".webp", cached=False, chapter="c3"),
        ]
        provider_meta = ComicMeta(
            source="jm",
            source_id="dormant_heal",
            display_id="JM_dormant_heal",
            title="休眠自愈测试本",
            updated_at=today_str,
            page_count=6,
            chapters=new_chapters,
            pages=new_pages,
            auto_update_interval_days=15,
        )
        mock_provider = MagicMock()
        mock_provider.fetch.return_value = FetchedComic(
            meta=provider_meta,
            remote_pages=fetched.remote_pages + [
                RemotePage(index=5, url="http://5", file="00001.webp", ext=".webp", chapter="c3"),
                RemotePage(index=6, url="http://6", file="00002.webp", ext=".webp", chapter="c3"),
            ],
        )

        with patch("app.auto_update.get_provider", return_value=mock_provider), \
             patch("app.auto_update.broadcast_event"):
            res = run_auto_update_cycle(self.store, max_check=10, sleep_seconds=0)
            self.assertEqual(res["updated"], 1)

        reloaded = self.store.load_meta("jm", "dormant_heal")
        self.assertEqual(reloaded.page_count, 6)
        self.assertEqual(reloaded.updated_at, today_str)

        # 模拟经过 16 天（< 60 天，但 >= 15 天）
        simulated_now = time.time() + 16 * 86400
        with patch("time.time", return_value=simulated_now):
            due_next = get_comics_due_for_auto_update(max_count=10)
            self.assertIn(
                "dormant_heal",
                {c["source_id"] for c in due_next},
                "更新后 updated_at 为最新，周期应自愈恢复为 15 天并在 16 天后重新到期",
            )

    def test_completion_detection_retires_auto_update_on_import(self):
        """测试标题、标签或最终章节命中完结特征时，系统默认 15 天自动归档为 0，馆长自定义优先。"""
        # 1. 最后一话包含「下篇 (完结)」 -> 自动设为 0
        meta_completed_chap = ComicMeta(
            source="jm",
            source_id="comp_chap",
            display_id="JM_comp_chap",
            title="连载短篇",
            chapters=[
                Chapter(id="c1", index=1, title="第 1 话 上篇", page_count=2, start=1),
                Chapter(id="c2", index=2, title="第 2 话 下篇 (完结)", page_count=2, start=3),
            ],
            pages=[
                PageRecord(index=1, file="01.webp", ext=".webp", cached=False, chapter="c1"),
                PageRecord(index=2, file="02.webp", ext=".webp", cached=False, chapter="c1"),
                PageRecord(index=3, file="03.webp", ext=".webp", cached=False, chapter="c2"),
                PageRecord(index=4, file="04.webp", ext=".webp", cached=False, chapter="c2"),
            ],
            auto_update_interval_days=15,
        )
        saved = self.store.save_fetched(FetchedComic(
            meta=meta_completed_chap,
            remote_pages=[
                RemotePage(index=1, url="http://1", file="01.webp", ext=".webp", chapter="c1"),
                RemotePage(index=2, url="http://2", file="02.webp", ext=".webp", chapter="c1"),
                RemotePage(index=3, url="http://3", file="03.webp", ext=".webp", chapter="c2"),
                RemotePage(index=4, url="http://4", file="04.webp", ext=".webp", chapter="c2"),
            ],
        ))
        self.assertEqual(saved.auto_update_interval_days, 0, "末话标题为下篇(完结)应自动归档 auto_update_interval_days=0")

        # 2. 标签包含「完结」 -> 自动设为 0
        meta_completed_tag = ComicMeta(
            source="jm",
            source_id="comp_tag",
            display_id="JM_comp_tag",
            title="完结标签漫画",
            tags=["同人", "完结"],
            chapters=[
                Chapter(id="c1", index=1, title="第 1 话", page_count=2, start=1),
                Chapter(id="c2", index=2, title="第 2 话", page_count=2, start=3),
            ],
            pages=[
                PageRecord(index=1, file="01.webp", ext=".webp", cached=False, chapter="c1"),
                PageRecord(index=2, file="02.webp", ext=".webp", cached=False, chapter="c1"),
                PageRecord(index=3, file="03.webp", ext=".webp", cached=False, chapter="c2"),
                PageRecord(index=4, file="04.webp", ext=".webp", cached=False, chapter="c2"),
            ],
            auto_update_interval_days=15,
        )
        saved_tag = self.store.save_fetched(FetchedComic(
            meta=meta_completed_tag,
            remote_pages=[
                RemotePage(index=1, url="http://1", file="01.webp", ext=".webp", chapter="c1"),
                RemotePage(index=2, url="http://2", file="02.webp", ext=".webp", chapter="c1"),
                RemotePage(index=3, url="http://3", file="03.webp", ext=".webp", chapter="c2"),
                RemotePage(index=4, url="http://4", file="04.webp", ext=".webp", chapter="c2"),
            ],
        ))
        self.assertEqual(saved_tag.auto_update_interval_days, 0, "标签含完结应自动归档 auto_update_interval_days=0")

        # 3. 未完结（中篇） -> 保持 15 天
        meta_ongoing = ComicMeta(
            source="jm",
            source_id="ongoing_mid",
            display_id="JM_ongoing_mid",
            title="进行中作品",
            chapters=[
                Chapter(id="c1", index=1, title="第 1 话 前篇", page_count=2, start=1),
                Chapter(id="c2", index=2, title="第 2 话 中篇", page_count=2, start=3),
            ],
            pages=[
                PageRecord(index=1, file="01.webp", ext=".webp", cached=False, chapter="c1"),
                PageRecord(index=2, file="02.webp", ext=".webp", cached=False, chapter="c1"),
                PageRecord(index=3, file="03.webp", ext=".webp", cached=False, chapter="c2"),
                PageRecord(index=4, file="04.webp", ext=".webp", cached=False, chapter="c2"),
            ],
            auto_update_interval_days=15,
        )
        saved_ongoing = self.store.save_fetched(FetchedComic(
            meta=meta_ongoing,
            remote_pages=[
                RemotePage(index=1, url="http://1", file="01.webp", ext=".webp", chapter="c1"),
                RemotePage(index=2, url="http://2", file="02.webp", ext=".webp", chapter="c1"),
                RemotePage(index=3, url="http://3", file="03.webp", ext=".webp", chapter="c2"),
                RemotePage(index=4, url="http://4", file="04.webp", ext=".webp", chapter="c2"),
            ],
        ))
        self.assertEqual(saved_ongoing.auto_update_interval_days, 15, "末话为中篇不应误判完结，应保留 15 天")

        # 4. 馆长自定义意志绝对优先（自定义 7 天即便是完结本也不自动覆盖）
        meta_curator = ComicMeta(
            source="jm",
            source_id="curator_override",
            display_id="JM_curator",
            title="馆长特许关注 [完结]",
            chapters=[
                Chapter(id="c1", index=1, title="第 1 话", page_count=2, start=1),
                Chapter(id="c2", index=2, title="第 2 话 最终话", page_count=2, start=3),
            ],
            pages=[
                PageRecord(index=1, file="01.webp", ext=".webp", cached=False, chapter="c1"),
                PageRecord(index=2, file="02.webp", ext=".webp", cached=False, chapter="c1"),
                PageRecord(index=3, file="03.webp", ext=".webp", cached=False, chapter="c2"),
                PageRecord(index=4, file="04.webp", ext=".webp", cached=False, chapter="c2"),
            ],
            auto_update_interval_days=7,
        )
        saved_curator = self.store.save_fetched(FetchedComic(
            meta=meta_curator,
            remote_pages=[
                RemotePage(index=1, url="http://1", file="01.webp", ext=".webp", chapter="c1"),
                RemotePage(index=2, url="http://2", file="02.webp", ext=".webp", chapter="c1"),
                RemotePage(index=3, url="http://3", file="03.webp", ext=".webp", chapter="c2"),
                RemotePage(index=4, url="http://4", file="04.webp", ext=".webp", chapter="c2"),
            ],
        ))
        self.assertEqual(saved_curator.auto_update_interval_days, 7, "馆长显式自定义 7 天应受绝对尊重，不自动关停")

    def test_120_day_dormancy_cutoff_retires_comic(self):
        """测试停更满 120 天的作品自动永久关停归档（auto_update_interval_days = 0），且馆长自定义不受影响。"""
        now = datetime.now(timezone.utc)
        date_130_days_ago = (now - timedelta(days=130)).strftime("%Y-%m-%d")

        # 1. 默认 15 天，停更 130 天 -> 应触发 120 天硬关停，且不作为巡检候选
        upsert_comic_index(make_comic_index_item(
            source="jm",
            source_id="cutoff_130d",
            chapter_titles_json='["话1", "话2"]',
            updated_at=date_130_days_ago,
            auto_update_interval_days=15,
            last_auto_checked_at=(now - timedelta(days=70)).isoformat(),
        ))

        # 2. 馆长自定义 7 天，停更 130 天 -> 馆长优先不关停，且已超 7 天 -> 应到期
        upsert_comic_index(make_comic_index_item(
            source="jm",
            source_id="curator_130d",
            chapter_titles_json='["话1", "话2"]',
            updated_at=date_130_days_ago,
            auto_update_interval_days=7,
            last_auto_checked_at=(now - timedelta(days=8)).isoformat(),
        ))

        due_candidates = get_comics_due_for_auto_update(max_count=10)
        due_ids = {c["source_id"] for c in due_candidates}

        self.assertNotIn("cutoff_130d", due_ids, "停更 130 天的默认周期作品应被硬关停，不返回为到期候选")
        self.assertIn("curator_130d", due_ids, "馆长自定义 7 天的作品应绝对尊重，即便停更 130 天仍正常巡检")

        # 检验 cutoff_130d 在索引中已被写为 0
        from app.db import get_db
        with get_db() as conn:
            row = conn.execute(
                "SELECT auto_update_interval_days FROM comics_index WHERE source = 'jm' AND source_id = 'cutoff_130d'"
            ).fetchone()
            self.assertEqual(row["auto_update_interval_days"], 0, "120 天硬关停应持久化写回 auto_update_interval_days = 0")

    def test_auto_update_cycle_retires_when_new_chapter_is_final(self):
        """测试自动追更巡检拉取到「最终话」新章节时，合并后自动关停后续巡检。"""
        now = datetime.now(timezone.utc)
        chapters = [
            Chapter(id="c1", index=1, title="第 1 话", page_count=2, start=1),
            Chapter(id="c2", index=2, title="第 2 话", page_count=2, start=3),
        ]
        pages = [
            PageRecord(index=1, file="01.webp", ext=".webp", cached=False, chapter="c1"),
            PageRecord(index=2, file="02.webp", ext=".webp", cached=False, chapter="c1"),
            PageRecord(index=3, file="03.webp", ext=".webp", cached=False, chapter="c2"),
            PageRecord(index=4, file="04.webp", ext=".webp", cached=False, chapter="c2"),
        ]
        meta = ComicMeta(
            source="jm",
            source_id="final_chap_test",
            display_id="JM_final_chap",
            title="测试迎向结局漫画",
            updated_at=(now - timedelta(days=20)).strftime("%Y-%m-%d"),
            page_count=4,
            chapters=chapters,
            pages=pages,
            auto_update_interval_days=15,
            last_auto_checked_at=(now - timedelta(days=25)).isoformat(),
        )
        fetched = FetchedComic(
            meta=meta,
            remote_pages=[
                RemotePage(index=1, url="http://1", file="01.webp", ext=".webp", chapter="c1"),
                RemotePage(index=2, url="http://2", file="02.webp", ext=".webp", chapter="c1"),
                RemotePage(index=3, url="http://3", file="03.webp", ext=".webp", chapter="c2"),
                RemotePage(index=4, url="http://4", file="04.webp", ext=".webp", chapter="c2"),
            ],
        )
        self.store.save_fetched(fetched)

        # 远端新发布了第 3 话，标题为「第 3 话 最终话」
        new_chapters = list(chapters) + [
            Chapter(id="c3", index=3, title="第 3 话 最终话", page_count=2, start=5)
        ]
        new_pages = list(pages) + [
            PageRecord(index=5, file="05.webp", ext=".webp", cached=False, chapter="c3"),
            PageRecord(index=6, file="06.webp", ext=".webp", cached=False, chapter="c3"),
        ]
        provider_meta = ComicMeta(
            source="jm",
            source_id="final_chap_test",
            display_id="JM_final_chap",
            title="测试迎向结局漫画",
            updated_at=now.strftime("%Y-%m-%d"),
            page_count=6,
            chapters=new_chapters,
            pages=new_pages,
            auto_update_interval_days=15,
        )
        mock_provider = MagicMock()
        mock_provider.fetch.return_value = FetchedComic(
            meta=provider_meta,
            remote_pages=fetched.remote_pages + [
                RemotePage(index=5, url="http://5", file="05.webp", ext=".webp", chapter="c3"),
                RemotePage(index=6, url="http://6", file="06.webp", ext=".webp", chapter="c3"),
            ],
        )

        with patch("app.auto_update.get_provider", return_value=mock_provider), \
             patch("app.auto_update.broadcast_event"):
            res = run_auto_update_cycle(self.store, max_check=10, sleep_seconds=0)
            self.assertEqual(res["updated"], 1)

        reloaded = self.store.load_meta("jm", "final_chap_test")
        self.assertEqual(reloaded.page_count, 6)
        self.assertEqual(reloaded.auto_update_interval_days, 0, "更新最终话后应自动将 auto_update_interval_days 设为 0")


if __name__ == "__main__":
    unittest.main()
