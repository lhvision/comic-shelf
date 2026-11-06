import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Ensure backend package is importable
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import _load_dotenv


class TestConfigEnvCascade(unittest.TestCase):
    def setUp(self):
        self.orig_env = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.orig_env)

    def test_load_dotenv_from_data_dir(self):
        with tempfile.TemporaryDirectory() as tmp_data_dir:
            env_file = Path(tmp_data_dir) / ".env"
            env_file.write_text(
                "COMIC_SHELF_SECRET=secret_from_data_dir\n"
                "COMIC_SHELF_PORT=9090\n"
                "# Commented line\n"
                "EMPTY_VAL=\n"
                "QUOTED_VAL=\"hello_world\"\n",
                encoding="utf-8",
            )
            # Ensure keys not already present in environment
            os.environ.pop("COMIC_SHELF_SECRET", None)
            os.environ.pop("COMIC_SHELF_PORT", None)
            os.environ.pop("QUOTED_VAL", None)

            with patch.dict(os.environ, {"COMIC_SHELF_DATA": tmp_data_dir}):
                _load_dotenv()
                self.assertEqual(os.environ.get("COMIC_SHELF_SECRET"), "secret_from_data_dir")
                self.assertEqual(os.environ.get("COMIC_SHELF_PORT"), "9090")
                self.assertEqual(os.environ.get("QUOTED_VAL"), "hello_world")

    def test_system_env_takes_precedence_over_dotenv(self):
        with tempfile.TemporaryDirectory() as tmp_data_dir:
            env_file = Path(tmp_data_dir) / ".env"
            env_file.write_text("COMIC_SHELF_SECRET=from_file\n", encoding="utf-8")

            with patch.dict(
                os.environ,
                {
                    "COMIC_SHELF_DATA": tmp_data_dir,
                    "COMIC_SHELF_SECRET": "system_level_secret",
                },
            ):
                _load_dotenv()
                self.assertEqual(os.environ.get("COMIC_SHELF_SECRET"), "system_level_secret")

    def test_root_dotenv_takes_precedence_over_data_dir_dotenv(self):
        with tempfile.TemporaryDirectory() as tmp_root_dir, tempfile.TemporaryDirectory() as tmp_data_dir:
            root_env = Path(tmp_root_dir) / ".env"
            root_env.write_text(
                "COMIC_SHELF_SECRET=root_secret\n"
                "COMIC_SHELF_PORT=8888\n",
                encoding="utf-8",
            )
            data_env = Path(tmp_data_dir) / ".env"
            data_env.write_text(
                "COMIC_SHELF_SECRET=data_dir_secret\n"
                "COMIC_SHELF_HOST=0.0.0.0\n",
                encoding="utf-8",
            )
            os.environ.pop("COMIC_SHELF_SECRET", None)
            os.environ.pop("COMIC_SHELF_PORT", None)
            os.environ.pop("COMIC_SHELF_HOST", None)

            with patch("app.config.PROJECT_ROOT", Path(tmp_root_dir)):
                with patch.dict(os.environ, {"COMIC_SHELF_DATA": tmp_data_dir}):
                    _load_dotenv()
                    # Tier 2 (root .env) takes precedence over Tier 3 (data dir .env)
                    self.assertEqual(os.environ.get("COMIC_SHELF_SECRET"), "root_secret")
                    self.assertEqual(os.environ.get("COMIC_SHELF_PORT"), "8888")
                    # Tier 3 (data dir .env) provides missing keys as fallback
                    self.assertEqual(os.environ.get("COMIC_SHELF_HOST"), "0.0.0.0")


if __name__ == "__main__":
    unittest.main()
