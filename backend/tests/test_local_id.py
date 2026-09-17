"""Unit tests for local comic id generation, normalization, and display_id auto-healing."""
from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.models import LocalComicCreateRequest
from app.providers.local import LocalProvider
from app.storage import ComicStore


class TestLocalComicId(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="test_local_id_"))
        self.store = ComicStore(root=self.tmp_dir)
        import os
        os.environ["COMIC_SHELF_ALLOWED_DIRS"] = str(self.tmp_dir)

    def tearDown(self) -> None:
        import os
        os.environ.pop("COMIC_SHELF_ALLOWED_DIRS", None)
        try:
            self.store._cover_executor.shutdown(wait=True)
        except Exception:
            pass
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_provider_id_normalization_and_display(self) -> None:
        provider = LocalProvider()

        # 1. Normal custom ID
        self.assertEqual(provider.normalize_id("tiya-frames"), "tiya-frames")
        self.assertEqual(provider.display_id("tiya-frames"), "LOC_tiya-frames")

        # 2. Input with LOC_ / LOC- prefix
        self.assertEqual(provider.normalize_id("LOC_tiya-frames"), "tiya-frames")
        self.assertEqual(provider.normalize_id("LOC-tiya-frames"), "tiya-frames")

        # 3. Input with loc_ prefix
        self.assertEqual(provider.normalize_id("loc_20260917_194250"), "20260917_194250")
        self.assertEqual(provider.display_id("loc_20260917_194250"), "LOC_20260917_194250")

        # 4. Clean date-based id
        gen_id = provider.generate_id()
        self.assertTrue(re.match(r"^\d{8}_\d{6}$", gen_id), f"generate_id output {gen_id} did not match YYYYMMDD_HHMMSS")
        self.assertEqual(provider.display_id(gen_id), f"LOC_{gen_id}")

    def test_create_local_comic_auto_id(self) -> None:
        # Create without explicit id
        req = LocalComicCreateRequest(title="自制测试漫画")
        meta = self.store.create_local_comic(req)

        self.assertFalse(meta.source_id.startswith("loc_"), f"source_id should not start with loc_: {meta.source_id}")
        self.assertTrue(re.match(r"^\d{8}_\d{6}(_\d+)?$", meta.source_id), f"Unexpected source_id: {meta.source_id}")
        self.assertFalse(meta.display_id.startswith("LOC_loc_"), f"display_id should not start with LOC_loc_: {meta.display_id}")
        self.assertEqual(meta.display_id, f"LOC_{meta.source_id}")

    def test_create_local_comic_custom_id(self) -> None:
        # Create with explicit custom id
        req = LocalComicCreateRequest(id="my-custom-manga", title="自定义ID漫画")
        meta = self.store.create_local_comic(req)

        self.assertEqual(meta.source_id, "my-custom-manga")
        self.assertEqual(meta.display_id, "LOC_my-custom-manga")

    def test_create_local_comic_duplicate_custom_id_conflict(self) -> None:
        req = LocalComicCreateRequest(id="unique-manga", title="第一本")
        self.store.create_local_comic(req)

        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as ctx:
            self.store.create_local_comic(req)
        self.assertEqual(ctx.exception.status_code, 409)

    def test_fallback_name_collision_auto_increment(self) -> None:
        # First allocation with fallback name
        source_id1, display_id1 = self.store._allocate_local_id(fallback_name="my_series")
        self.assertEqual(source_id1, "my_series")
        self.assertEqual(display_id1, "LOC_my_series")

        # Fake existing album on disk
        album_file1 = self.store.album_path("local", source_id1)
        album_file1.parent.mkdir(parents=True, exist_ok=True)
        album_file1.write_text("{}", encoding="utf-8")

        # Second allocation with same fallback name should auto-increment to _1
        source_id2, display_id2 = self.store._allocate_local_id(fallback_name="my_series")
        self.assertEqual(source_id2, "my_series_1")
        self.assertEqual(display_id2, "LOC_my_series_1")

        # Fake existing album for _1
        album_file2 = self.store.album_path("local", source_id2)
        album_file2.parent.mkdir(parents=True, exist_ok=True)
        album_file2.write_text("{}", encoding="utf-8")

        # Third allocation should auto-increment to _2
        source_id3, display_id3 = self.store._allocate_local_id(fallback_name="my_series")
        self.assertEqual(source_id3, "my_series_2")
        self.assertEqual(display_id3, "LOC_my_series_2")

    def test_import_from_local_dir_duplicate_custom_id_conflict(self) -> None:
        from fastapi import HTTPException
        from app.models import LocalPathImportRequest

        # Prepare dummy folder with an image
        import_dir = self.tmp_dir / "import_source"
        import_dir.mkdir(parents=True, exist_ok=True)
        (import_dir / "00001.jpg").write_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9")

        req = LocalPathImportRequest(path=str(import_dir), id="dir-manga", title="第一本")
        self.store.import_local_path(req)

        # Re-importing with same explicit id should trigger 409
        with self.assertRaises(HTTPException) as ctx:
            self.store.import_local_path(req)
        self.assertEqual(ctx.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
