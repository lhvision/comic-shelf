from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.providers.base import ComicProvider


class DummyProvider(ComicProvider):
    key = "dummy"

    def normalize_id(self, raw: str) -> str:
        return raw

    def fetch(self, raw_id: str, *, existing=None):
        raise NotImplementedError

    def download_page(self, comic, page) -> bytes:
        raise NotImplementedError


class TestProviderBaseSecureSession(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp_dir.name)
        self.session_file = self.tmp_path / "subdir" / "session.json"
        self.provider = DummyProvider()

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_save_load_clear_lifecycle_and_permissions(self) -> None:
        data = {"token": "secret_xyz", "uid": 12345, "roles": ["vip"]}

        # 1. Save session (auto creates parent directories and enforces 0o600)
        self.provider.save_secure_session(self.session_file, data)
        self.assertTrue(self.session_file.is_file())

        if hasattr(os, "stat"):
            mode = self.session_file.stat().st_mode & 0o777
            self.assertEqual(mode, 0o600)

        # 2. Load session
        loaded = self.provider.load_secure_session(self.session_file)
        self.assertEqual(loaded, data)

        # 3. Clear session
        self.provider.clear_secure_session(self.session_file)
        self.assertFalse(self.session_file.exists())
        self.assertIsNone(self.provider.load_secure_session(self.session_file))

    def test_load_non_existent_and_invalid_json(self) -> None:
        # Non-existent
        self.assertIsNone(self.provider.load_secure_session(self.tmp_path / "none.json"))

        # Broken / invalid JSON
        broken_file = self.tmp_path / "broken.json"
        broken_file.write_text("not a valid json {", encoding="utf-8")
        self.assertIsNone(self.provider.load_secure_session(broken_file))

        # Non-dict JSON (e.g. array or integer)
        array_file = self.tmp_path / "array.json"
        array_file.write_text("[1, 2, 3]", encoding="utf-8")
        self.assertIsNone(self.provider.load_secure_session(array_file))


if __name__ == "__main__":
    unittest.main()
