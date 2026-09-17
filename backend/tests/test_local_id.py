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

    def tearDown(self) -> None:
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


if __name__ == "__main__":
    unittest.main()
