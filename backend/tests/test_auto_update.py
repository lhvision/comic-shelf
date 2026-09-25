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
        "imported_at": "2026-01-01T00:00:00Z",
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


if __name__ == "__main__":
    unittest.main()
