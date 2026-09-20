"""Regression tests for formatting legacy metadata without read-time writes."""
from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.models import Chapter, ComicMeta, FetchedComic, PageRecord, RemotePage
from app.storage import ComicStore
from app.storage.utils import _write_json_atomic
from tests.helpers import create_sample_image


class TestStorageMetadata(unittest.TestCase):
    def setUp(self) -> None:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.store = ComicStore(root=Path(temp_dir.name))
        self.addCleanup(self.store._cover_executor.shutdown)
        self.path = self.store.album_path("jm", "12345")
        self.path.parent.mkdir(parents=True)
        meta = ComicMeta(
            source="jm", source_id="12345", display_id="JM12345",
            title="Original", views="12,222", likes="1200",
        )
        self.path.write_text(meta.model_dump_json(), encoding="utf-8")

    def test_legacy_counts_remain_readable_when_storage_is_unwritable(self) -> None:
        original = self.path.read_bytes()
        with patch(
            "app.storage.base._write_json_atomic", side_effect=PermissionError("read-only library")
        ) as write:
            meta = self.store.load_meta("jm", "12345")
            self.assertIsNotNone(meta)
            self.assertEqual(meta.views, "12k")
            self.assertEqual(meta.likes, "1.2k")
            self.assertIs(self.store.load_meta("jm", "12345"), meta)
            write.assert_not_called()
        self.assertEqual(self.path.read_bytes(), original)

    def test_legacy_count_read_does_not_overwrite_a_concurrent_metadata_update(self) -> None:
        read_text = Path.read_text
        update_pending = True

        def read_then_update(path: Path, *args, **kwargs) -> str:
            nonlocal update_pending
            snapshot = read_text(path, *args, **kwargs)
            if path == self.path and update_pending:
                update_pending = False
                # Deterministically interleave a writer after the reader took its snapshot.
                self.store.update_metadata(
                    "jm", "12345", {"title": "Edited", "hidden_from_guest": True}
                )
            return snapshot

        # Isolate the metadata write from the unrelated SQLite index refresh.
        with patch.object(self.store, "_invalidate_cache"), patch.object(
            Path, "read_text", read_then_update
        ):
            self.assertIsNotNone(self.store.load_meta("jm", "12345"))

        saved = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(saved["title"], "Edited")
        self.assertTrue(saved["hidden_from_guest"])

    def _write_pages(self, orphaned: bool = False) -> ComicMeta:
        meta = ComicMeta.model_validate_json(self.path.read_text())
        meta.page_count = 2
        meta.pages = [
            PageRecord(index=1, file="00001.webp", ext=".webp", chapter="" if orphaned else "c1"),
            PageRecord(index=2, file="00002.webp", ext=".webp", chapter="c2"),
        ]
        meta.chapters = [Chapter(id="c2", index=1, start=2, page_count=1)] if orphaned else []
        if not orphaned:
            meta.raw = {"chapters": [
                {"id": "c1", "index": 1, "start": 1, "page_count": 1},
                {"id": "c2", "index": 2, "start": 2, "page_count": 1},
            ]}
        for page in meta.pages:
            target = self.store.page_path(meta, page.index)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"cached-page")
        self.path.write_text(meta.model_dump_json())
        return meta

    def test_read_only_cache_and_chapter_repair_does_not_write(self) -> None:
        self._write_pages()
        original = self.path.read_bytes()
        with patch("app.storage.base._write_json_atomic", side_effect=PermissionError) as write:
            meta = self.store.load_meta("jm", "12345", verify_cache=True)
            self.assertEqual([chapter.id for chapter in meta.chapters], ["c1", "c2"])
            self.assertTrue(all(page.cached for page in meta.pages))
            write.assert_not_called()
        self.assertEqual(self.path.read_bytes(), original)

    def test_detail_cache_reconciliation_does_not_write_a_stale_album(self) -> None:
        stale = self._write_pages()
        edited = stale.model_copy(update={"title": "Edited", "hidden_from_guest": True})
        self.path.write_text(edited.model_dump_json())
        with patch("app.storage.media._write_json_atomic", side_effect=PermissionError) as write:
            self.assertEqual(self.store.detail(stale).cached_pages, 2)
            write.assert_not_called()
        saved = ComicMeta.model_validate_json(self.path.read_text())
        self.assertEqual(saved.title, "Edited")
        self.assertTrue(saved.hidden_from_guest)

    def test_orphan_migration_rolls_back_when_album_write_fails(self) -> None:
        original = self._write_pages(orphaned=True)
        with patch("app.storage.base._write_json_atomic", side_effect=PermissionError):
            meta = self.store.load_meta("jm", "12345")
        self.assertEqual(meta.pages[0].chapter, "")
        self.assertEqual(self.store.page_path(meta, 1).read_bytes(), b"cached-page")
        self.assertEqual(ComicMeta.model_validate_json(self.path.read_text()), original)

    def test_partial_file_migration_rolls_back(self) -> None:
        self._write_pages(orphaned=True)
        thumbs = self.store.thumbs_dir("jm", "12345")
        thumbs.mkdir()
        (thumbs / "00001.webp").write_bytes(b"thumbnail")
        rename = Path.rename

        def deny_thumbnail_move(path: Path, destination: Path) -> Path:
            if path.parent == thumbs:
                raise PermissionError("read-only thumbnails")
            return rename(path, destination)

        with patch.object(Path, "rename", deny_thumbnail_move):
            meta = self.store.load_meta("jm", "12345")
        self.assertEqual(meta.pages[0].chapter, "")
        self.assertEqual(self.store.page_path(meta, 1).read_bytes(), b"cached-page")
        self.assertEqual((thumbs / "00001.webp").read_bytes(), b"thumbnail")

    def test_orphan_repair_and_metadata_edit_are_serialized(self) -> None:
        self._write_pages(orphaned=True)
        repair_writing = threading.Event()
        resume_repair = threading.Event()
        edit_started = threading.Event()
        edit_done = threading.Event()

        def paused_write(path: Path, data: dict) -> None:
            if data["title"] == "Original":
                repair_writing.set()
                if not resume_repair.wait(5):
                    raise TimeoutError("repair was not resumed")
            _write_json_atomic(path, data)

        def edit() -> None:
            edit_started.set()
            self.store.update_metadata("jm", "12345", {"title": "Edited", "hidden_from_guest": True})
            edit_done.set()

        with patch("app.storage.base._write_json_atomic", side_effect=paused_write), patch(
            "app.db.upsert_comic_index"
        ), ThreadPoolExecutor(max_workers=2) as pool:
            repair = pool.submit(self.store.load_meta, "jm", "12345")
            try:
                self.assertTrue(repair_writing.wait(5))
                editing = pool.submit(edit)
                self.assertTrue(edit_started.wait(5))
                self.assertFalse(edit_done.wait(0.05))
            finally:
                resume_repair.set()
            repair.result(timeout=5)
            editing.result(timeout=5)
        meta = self.store.load_meta("jm", "12345")
        self.assertEqual(meta.title, "Edited")
        self.assertTrue(meta.hidden_from_guest)
        self.assertEqual(meta.pages[0].chapter, "c1")
        self.assertEqual(self.store.page_path(meta, 1).read_bytes(), b"cached-page")

    def test_background_cache_update_preserves_newer_metadata(self) -> None:
        stale = self._write_pages()
        edited = stale.model_copy(update={"title": "Edited", "hidden_from_guest": True})
        self.path.write_text(edited.model_dump_json())
        with patch("app.db.update_comic_cached_pages"):
            self.store.update_page_cached(stale, 1, True)
        saved = ComicMeta.model_validate_json(self.path.read_text())
        self.assertEqual(saved.title, "Edited")
        self.assertTrue(saved.hidden_from_guest)
        self.assertTrue(saved.pages[0].cached)

    def test_background_cache_update_does_not_recreate_deleted_album(self) -> None:
        stale = self._write_pages()
        self.path.unlink()
        self.store.update_page_cached(stale, 1, True)
        self.assertFalse(self.path.exists())

    def test_cached_page_remains_readable_if_cache_flag_cannot_be_saved(self) -> None:
        meta = self._write_pages()
        fetched = FetchedComic(meta=meta, remote_pages=[])
        with patch("app.storage.media._write_json_atomic", side_effect=PermissionError):
            self.assertEqual(self.store.ensure_page(fetched, 1).read_bytes(), b"cached-page")

    def test_legacy_scramble_id_is_recovered_without_writing(self) -> None:
        meta = self._write_pages()
        meta.raw["album"] = {"scramble_id": "220980"}
        self.path.write_text(meta.model_dump_json())
        remote = self.store.remote_path("jm", "12345")
        page = RemotePage(index=1, url="https://example.com/1.webp", file="00001.webp", ext=".webp", chapter="c1")
        remote.write_text(json.dumps({"decode_version": 2, "remote_pages": [page.model_dump()]}))
        original = remote.read_bytes()
        with patch("app.storage.base._write_json_atomic", side_effect=PermissionError) as write:
            fetched = self.store.load_fetched("jm", "12345")
            self.assertEqual(fetched.remote_pages[0].scramble_id, "220980")
            write.assert_not_called()
        self.assertEqual(remote.read_bytes(), original)

    def test_orphan_repair_avoids_existing_chapter_ids(self) -> None:
        meta = self._write_pages(orphaned=True)
        meta.chapters[0].id = "c1"
        meta.pages[1].chapter = "c1"
        self.store.pages_dir("jm", "12345").joinpath("c2").rename(
            self.store.pages_dir("jm", "12345") / "c1"
        )
        self.path.write_text(meta.model_dump_json())
        healed = self.store.load_meta("jm", "12345")
        self.assertEqual([chapter.id for chapter in healed.chapters], ["c2", "c1"])
        for index in (1, 2):
            self.assertEqual(self.store.page_path(healed, index).read_bytes(), b"cached-page")

    def test_cover_download_allows_metadata_edit_and_preserves_it(self) -> None:
        meta = self._write_pages()
        self.store.page_path(meta, 1).unlink()
        fetched = FetchedComic(meta=meta, remote_pages=[
            RemotePage(index=1, url="https://example.com/1.webp", file="00001.webp", ext=".webp", chapter="c1"),
        ])
        downloading = threading.Event()
        resume_download = threading.Event()
        image = create_sample_image()

        def download(*_args) -> bytes:
            downloading.set()
            if not resume_download.wait(5):
                raise TimeoutError("download was not resumed")
            return image

        with patch("app.providers.registry.get_provider") as provider, patch("app.db.upsert_comic_index"), patch(
            "app.db.update_comic_cached_pages"
        ), ThreadPoolExecutor(max_workers=2) as pool:
            provider.return_value.download_page.side_effect = download
            cover = pool.submit(self.store.ensure_webp_cover, meta, fetched)
            try:
                self.assertTrue(downloading.wait(5))
                editing = pool.submit(
                    self.store.update_metadata, "jm", "12345",
                    {"title": "Edited during download", "hidden_from_guest": True},
                )
                editing.result(timeout=2)
            finally:
                resume_download.set()
            self.assertTrue(cover.result(timeout=5).is_file())
        saved = ComicMeta.model_validate_json(self.path.read_text())
        self.assertEqual(saved.title, "Edited during download")
        self.assertTrue(saved.hidden_from_guest)
        self.assertTrue(saved.pages[0].cached)

    def _write_remote_comic(self) -> FetchedComic:
        """Create a flat archive with one uncached remote page."""
        meta = ComicMeta.model_validate_json(self.path.read_text())
        meta.custom_pages = False
        meta.chapters = []
        meta.raw = {}
        meta.page_count = 1
        meta.pages = [PageRecord(index=1, file="00001.webp", ext=".webp")]
        remote = RemotePage(index=1, url="https://example.com/1.webp", file="00001.webp", ext=".webp")
        self.path.write_text(meta.model_dump_json())
        self.store.remote_path("jm", "12345").write_text(json.dumps({
            "decode_version": 2, "remote_pages": [remote.model_dump()],
        }))
        self.store._meta_cache.clear()
        self.store._fetched_cache.clear()
        return FetchedComic(meta=meta, remote_pages=[remote])

    def test_refresh_preserves_hidden_setting_changed_during_fetch(self) -> None:
        fetched = self._write_remote_comic()
        with patch("app.db.upsert_comic_index"):
            self.store.update_metadata("jm", "12345", {"hidden_from_guest": True})
            self.store.save_fetched(fetched, refresh=True)
        self.assertTrue(ComicMeta.model_validate_json(self.path.read_text()).hidden_from_guest)

    def test_download_uses_migrated_metadata_path_with_legacy_remote_descriptor(self) -> None:
        fetched = self._write_remote_comic()
        fetched.meta.chapters = [Chapter(id="c1", index=1, start=1, page_count=1)]
        fetched.meta.pages[0].chapter = "c1"
        self.path.write_text(fetched.meta.model_dump_json())
        image = create_sample_image()
        with patch("app.providers.registry.get_provider") as provider, patch("app.db.update_comic_cached_pages"):
            provider.return_value.download_page.return_value = image
            target = self.store.ensure_page(fetched, 1)
        self.assertEqual(target.parent.name, "c1")
        self.assertEqual(target.read_bytes(), image)

    def test_refresh_write_failure_restores_both_json_files_and_moved_pages(self) -> None:
        for failed_name in ("remote.json", "album.json"):
            with self.subTest(failed_name=failed_name):
                fetched = self._write_remote_comic()
                page_path = self.store.page_path(fetched.meta, 1)
                page_path.parent.mkdir(parents=True, exist_ok=True)
                page_path.write_bytes(b"original-page")
                remote_path = self.store.remote_path("jm", "12345")
                original_album = self.path.read_bytes()
                original_remote = remote_path.read_bytes()
                fetched.meta.chapters = [Chapter(id="new", index=1, start=1, page_count=1)]
                fetched.meta.pages[0].chapter = "new"
                fetched.remote_pages[0].chapter = "new"

                def fail_write(path: Path, data: dict) -> None:
                    if path.name == failed_name:
                        raise OSError("disk full")
                    _write_json_atomic(path, data)

                with patch("app.storage.base._write_json_atomic", side_effect=fail_write):
                    with self.assertRaises(OSError):
                        self.store.save_fetched(fetched, refresh=True)
                self.assertEqual(self.path.read_bytes(), original_album)
                self.assertEqual(remote_path.read_bytes(), original_remote)
                self.assertEqual(page_path.read_bytes(), b"original-page")
                self.assertFalse((page_path.parent / "new" / page_path.name).exists())
                self.assertEqual(list(self.path.parent.glob(".save-*")), [])

    def test_failed_initial_save_does_not_leave_half_an_archive(self) -> None:
        fetched = self._write_remote_comic()
        self.path.unlink()
        self.store.remote_path("jm", "12345").unlink()

        def fail_album(path: Path, data: dict) -> None:
            if path.name == "album.json":
                raise OSError("disk full")
            _write_json_atomic(path, data)

        with patch("app.storage.base._write_json_atomic", side_effect=fail_album):
            with self.assertRaises(OSError):
                self.store.save_fetched(fetched)
        self.assertFalse(self.path.exists())
        self.assertFalse(self.store.remote_path("jm", "12345").exists())

    def test_rollback_failure_keeps_original_metadata_backup(self) -> None:
        fetched = self._write_remote_comic()
        original = self.path.read_bytes()
        replace = Path.replace

        def fail_restore(path: Path, target: Path) -> Path:
            if path.parent.name.startswith(".save-"):
                raise PermissionError("restore denied")
            return replace(path, target)

        with patch("app.storage.base._write_json_atomic", side_effect=OSError("disk full")), patch.object(
            Path, "replace", fail_restore
        ):
            with self.assertRaises(PermissionError):
                self.store.save_fetched(fetched, refresh=True)
        backups = list(self.path.parent.glob(".save-*/album.json"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), original)

    def test_old_download_cannot_overwrite_replacement_or_recreate_deleted_comic(self) -> None:
        for action in ("replace", "delete", "delete_and_reimport", "refresh"):
            with self.subTest(action=action):
                self.path.parent.mkdir(parents=True, exist_ok=True)
                if not self.path.exists():
                    self.path.write_text(ComicMeta(source="jm", source_id="12345", display_id="JM12345", title="Original").model_dump_json())
                fetched = self._write_remote_comic()
                target = self.store.page_path(fetched.meta, 1)
                target.unlink(missing_ok=True)
                started, resume = threading.Event(), threading.Event()
                replacement = create_sample_image(color="green")

                def download(*_args) -> bytes:
                    started.set()
                    if not resume.wait(5):
                        raise TimeoutError("download was not resumed")
                    return create_sample_image(color="red")

                with patch("app.providers.registry.get_provider") as provider, patch(
                    "app.db.upsert_comic_index"
                ), patch("app.db.purge_comic_db_records"), patch.object(
                    self.store, "ensure_webp_cover"
                ), ThreadPoolExecutor(max_workers=1) as pool:
                    provider.return_value.download_page.side_effect = download
                    downloading = pool.submit(self.store.ensure_page, fetched, 1)
                    try:
                        self.assertTrue(started.wait(5))
                        if action == "replace":
                            self.store.replace_pages("jm", "12345", files=[("new.webp", replacement)])
                        elif action == "refresh":
                            updated = fetched.model_copy(deep=True)
                            updated.remote_pages[0].url = "https://example.com/updated.webp"
                            self.store.save_fetched(updated, refresh=True)
                        else:
                            self.store.delete("jm", "12345")
                            if action == "delete_and_reimport":
                                self.store.save_fetched(fetched.model_copy(deep=True))
                        remote_path = self.store.remote_path("jm", "12345")
                        remote_before = remote_path.read_bytes() if remote_path.exists() else None
                    finally:
                        resume.set()
                    with self.assertRaises(FileNotFoundError):
                        downloading.result(timeout=5)
                if action == "replace":
                    self.assertEqual(target.read_bytes(), replacement)
                else:
                    self.assertFalse(target.exists())
                if action == "delete":
                    self.assertFalse(self.path.parent.exists())
                else:
                    self.assertEqual(remote_path.read_bytes(), remote_before)


if __name__ == "__main__":
    unittest.main()
