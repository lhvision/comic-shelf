"""Regression tests for formatting legacy metadata without read-time writes."""
from __future__ import annotations

import json
import os
import sys
import time
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

    def _work_save(self, name: str = ".save-crash") -> Path:
        work = self.store.root / ".work"
        work.mkdir(exist_ok=True)
        backup = work / name
        backup.mkdir()
        (backup / "comic.rel").write_text("jm\n12345\n", encoding="utf-8")
        return backup

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
        original_read = Path.read_text
        reading = threading.Event()
        resume_read = threading.Event()
        edit_done = threading.Event()

        def blocked_read(path: Path, *args, **kwargs) -> str:
            snapshot = original_read(path, *args, **kwargs)
            if path == self.path:
                reading.set()
                if not resume_read.wait(5):
                    raise TimeoutError("metadata read was not resumed")
            return snapshot

        def edit() -> None:
            self.store.update_metadata(
                "jm", "12345", {"title": "Edited", "hidden_from_guest": True}
            )
            edit_done.set()

        with patch.object(self.store, "_invalidate_cache"), patch.object(
            Path, "read_text", blocked_read
        ), ThreadPoolExecutor(max_workers=2) as pool:
            reader = pool.submit(self.store.load_meta, "jm", "12345")
            try:
                self.assertTrue(reading.wait(5))
                editing = pool.submit(edit)
                self.assertFalse(edit_done.wait(0.05))
            finally:
                resume_read.set()
            self.assertIsNotNone(reader.result(timeout=5))
            editing.result(timeout=5)

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
        self.assertFalse((self.store.pages_dir("jm", "12345") / "c1").exists())
        self.assertFalse((thumbs / "c1").exists())

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
                self.assertEqual(list((self.store.root / ".work").glob(".save-*")), [])

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
        real_copy2 = __import__("shutil").copy2

        def fail_copy(src, dst, *args, **kwargs):
            if Path(src).parent.name.startswith(".save-"):
                raise PermissionError("restore denied")
            return real_copy2(src, dst, *args, **kwargs)

        with patch("app.storage.base._write_json_atomic", side_effect=OSError("disk full")), patch(
            "app.storage.base.shutil.copy2", fail_copy
        ):
            with self.assertRaises(PermissionError):
                self.store.save_fetched(fetched, refresh=True)
        backups = list((self.store.root / ".work").glob(".save-*/album.json"))
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

    def _persist_rebuilt_chapters(self) -> ComicMeta:
        self._write_pages()
        loaded = self.store.load_meta("jm", "12345")
        assert loaded is not None
        self.path.write_text(loaded.model_dump_json(), encoding="utf-8")
        self.store._meta_cache.clear()
        self.store._fetched_cache.clear()
        return loaded

    def test_failed_chapter_rename_is_not_persisted_by_cache_flag_write(self) -> None:
        original = self._persist_rebuilt_chapters()
        with patch("app.storage.chapters._write_json_atomic", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.store.update_chapter_title("jm", "12345", "c1", "Hijacked")
        self.assertEqual(self.store.load_meta("jm", "12345").chapters[0].title, original.chapters[0].title)
        with patch("app.db.update_comic_cached_pages"):
            self.store.update_page_cached(self.store.load_meta("jm", "12345"), 1, True)
        saved = ComicMeta.model_validate_json(self.path.read_text())
        self.assertEqual(saved.chapters[0].title, original.chapters[0].title)
        self.assertTrue(saved.pages[0].cached)

    def test_failed_chapter_delete_keeps_files_and_metadata(self) -> None:
        self._persist_rebuilt_chapters()
        target = self.store.page_path(self.store.load_meta("jm", "12345"), 2)
        with patch("app.storage.chapters._write_json_atomic", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.store.delete_chapter("jm", "12345", "c2")
        self.assertTrue(target.exists())
        saved = self.store.load_meta("jm", "12345")
        self.assertEqual([chapter.id for chapter in saved.chapters], ["c1", "c2"])
        self.assertEqual(self.store.page_path(saved, 2).read_bytes(), b"cached-page")

    def test_atomic_json_write_creates_temp_exclusively(self) -> None:
        path = self.path.parent / "exclusive.json"
        flags_seen: list[int] = []
        real_open = os.open

        def spy(name: str | bytes | os.PathLike[str], flags: int, *args, **kwargs) -> int:
            flags_seen.append(flags)
            return real_open(name, flags, *args, **kwargs)

        with patch("app.storage.utils.os.open", spy):
            _write_json_atomic(path, {"ok": True})
        self.assertTrue(flags_seen)
        self.assertTrue(flags_seen[0] & os.O_EXCL)
        self.assertTrue(flags_seen[0] & os.O_CREAT)
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"ok": True})

    def test_delete_renames_then_forgets_leftovers(self) -> None:
        target = self.path.parent
        work = self.store.root / ".work"
        work.mkdir(exist_ok=True)
        trash = work / ".deleted-dead"
        with patch("app.db.upsert_comic_index"), patch("app.db.purge_comic_db_records"):
            target.rename(trash)
            self.store.recover_interrupted_saves()
        self.assertFalse(trash.exists())
        self.assertFalse(target.exists())

    def test_recover_removes_unfinished_first_save(self) -> None:
        self.path.unlink()
        remote = self.store.remote_path("jm", "12345")
        remote.unlink(missing_ok=True)
        backup = self._work_save()
        (backup / ".in-progress").write_bytes(b"")
        pages = self.store.pages_dir("jm", "12345")
        pages.mkdir(parents=True, exist_ok=True)
        (pages / "00001.webp").write_bytes(b"new")
        (backup / "replaced.rel").write_text("pages\n0\n")
        with patch("app.db.upsert_comic_index"), patch("app.db.purge_comic_db_records"):
            self.store.recover_interrupted_saves()
        self.assertFalse(self.path.parent.exists())

    def test_recover_deletes_backup_from_a_finished_save(self) -> None:
        leftover = self._work_save(".save-deadbeef")
        (leftover / "album.json").write_text("{}", encoding="utf-8")
        with patch("app.db.upsert_comic_index"), patch("app.db.purge_comic_db_records"):
            self.store.recover_interrupted_saves()
        self.assertFalse(leftover.exists())

    def test_recover_restores_interrupted_save_and_flattens_pages(self) -> None:
        fetched = self._write_remote_comic()
        original_album = self.path.read_bytes()
        original_remote = self.store.remote_path("jm", "12345").read_bytes()
        page = self.store.pages_dir("jm", "12345") / "00001.webp"
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_bytes(b"original-page")
        chapter_dir = page.parent / "new"
        chapter_dir.mkdir()
        page.replace(chapter_dir / page.name)
        backup = self._work_save()
        (backup / "album.json").write_bytes(original_album)
        (backup / "remote.json").write_bytes(original_remote)
        (backup / ".in-progress").write_bytes(b"")
        self.path.write_text(
            ComicMeta(
                source="jm", source_id="12345", display_id="JM12345", title="New",
                chapters=[Chapter(id="new", index=1, start=1, page_count=1)],
            ).model_dump_json(),
            encoding="utf-8",
        )
        with patch("app.db.upsert_comic_index"):
            self.store.recover_interrupted_saves()
        self.assertEqual(self.path.read_bytes(), original_album)
        self.assertEqual(self.store.remote_path("jm", "12345").read_bytes(), original_remote)
        self.assertEqual(page.read_bytes(), b"original-page")
        self.assertFalse(chapter_dir.exists())
        self.assertFalse(backup.exists())

    def test_recover_restores_interrupted_chapter_delete(self) -> None:
        original = self._persist_rebuilt_chapters()
        target = self.store.page_path(original, 2)
        backup = self._work_save()
        (backup / "album.json").write_bytes(self.path.read_bytes())
        (backup / ".in-progress").write_bytes(b"")
        deleted = original.model_copy(deep=True)
        deleted.pages = [page for page in deleted.pages if page.chapter != "c2"]
        deleted.chapters = [chapter for chapter in deleted.chapters if chapter.id != "c2"]
        self.path.write_text(deleted.model_dump_json(), encoding="utf-8")
        self.store._meta_cache.clear()
        with patch("app.db.upsert_comic_index"):
            self.store.recover_interrupted_saves()
        saved = self.store.load_meta("jm", "12345")
        self.assertEqual([chapter.id for chapter in saved.chapters], ["c1", "c2"])
        self.assertTrue(target.exists())
        self.assertFalse(backup.exists())

    def test_recover_retries_after_partial_restore(self) -> None:
        self._write_remote_comic()
        original_album = self.path.read_bytes()
        original_remote = self.store.remote_path("jm", "12345").read_bytes()
        backup = self._work_save()
        (backup / "album.json").write_bytes(original_album)
        (backup / "remote.json").write_bytes(original_remote)
        (backup / ".in-progress").write_bytes(b"")
        self.path.write_text(
            ComicMeta(source="jm", source_id="12345", display_id="JM12345", title="New").model_dump_json(),
            encoding="utf-8",
        )
        self.store.remote_path("jm", "12345").write_text(
            '{"decode_version": 2, "remote_pages": []}', encoding="utf-8"
        )
        self.path.write_bytes(original_album)
        with patch("app.db.upsert_comic_index"):
            self.store.recover_interrupted_saves()
        self.assertEqual(self.path.read_bytes(), original_album)
        self.assertEqual(self.store.remote_path("jm", "12345").read_bytes(), original_remote)
        self.assertFalse(backup.exists())

    def test_recover_removes_tmp_work_without_scanning_pages(self) -> None:
        self._write_remote_comic()
        pages = self.store.pages_dir("jm", "12345")
        pages.mkdir(parents=True, exist_ok=True)
        kept = pages / "00001.webp"
        kept.write_bytes(b"keep")
        extra = pages / "00002.webp"
        extra.write_bytes(b"orphan")
        work = self.store.root / ".work"
        work.mkdir(exist_ok=True)
        staging = work / ".tmp_create_pages_1"
        staging.mkdir()
        (staging / "x.webp").write_bytes(b"staged")
        json_tmp = self.path.parent / ".album.json.tmp.1_1"
        json_tmp.write_bytes(b"{")
        with patch("app.db.upsert_comic_index"):
            self.store.recover_interrupted_saves()
        self.assertEqual(kept.read_bytes(), b"keep")
        self.assertTrue(extra.exists())
        self.assertFalse(staging.exists())
        self.assertTrue(json_tmp.exists())

    def test_recover_failure_keeps_backup_and_raises(self) -> None:
        leftover = self._work_save()
        (leftover / "album.json").write_bytes(self.path.read_bytes())
        (leftover / ".in-progress").write_bytes(b"")
        original = self.path.read_bytes()
        with patch("app.storage.base.shutil.copy2", side_effect=OSError("disk full")):
            with self.assertRaises(RuntimeError):
                self.store.recover_interrupted_saves()
        self.assertTrue((leftover / ".in-progress").exists())
        self.assertEqual(self.path.read_bytes(), original)

    def test_scramble_id_heal_does_not_cancel_download(self) -> None:
        fetched = self._write_remote_comic()
        fetched.meta.raw = {"album": {"scramble_id": "220980"}}
        self.path.write_text(fetched.meta.model_dump_json(), encoding="utf-8")
        target = self.store.page_path(fetched.meta, 1)
        target.unlink(missing_ok=True)
        image = create_sample_image()
        with patch("app.providers.registry.get_provider") as provider, patch(
            "app.db.update_comic_cached_pages"
        ), patch("app.db.upsert_comic_index"):
            provider.return_value.download_page.return_value = image
            self.assertEqual(self.store.ensure_page(fetched, 1).read_bytes(), image)

    def test_concurrent_ensure_page_downloads_once(self) -> None:
        fetched = self._write_remote_comic()
        target = self.store.page_path(fetched.meta, 1)
        target.unlink(missing_ok=True)
        started, resume = threading.Event(), threading.Event()
        calls: list[int] = []

        def download(*_args) -> bytes:
            calls.append(1)
            started.set()
            if not resume.wait(5):
                raise TimeoutError("download was not resumed")
            return create_sample_image()

        with patch("app.providers.registry.get_provider") as provider, patch(
            "app.db.update_comic_cached_pages"
        ), patch("app.db.upsert_comic_index"), ThreadPoolExecutor(max_workers=2) as pool:
            provider.return_value.download_page.side_effect = download
            first = pool.submit(self.store.ensure_page, fetched, 1)
            self.assertTrue(started.wait(5))
            second = pool.submit(self.store.ensure_page, fetched, 1)
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline and not second.running():
                time.sleep(0.01)
            resume.set()
            first.result(timeout=5)
            second.result(timeout=5)
        self.assertEqual(sum(calls), 1)
        self.assertTrue(target.exists())


if __name__ == "__main__":
    unittest.main()
