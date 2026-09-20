"""The supported server entry point must not launch independent storage writers."""
from __future__ import annotations

import contextlib
import io
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

BACKEND_DIR = Path(__file__).resolve().parent.parent
SERVER = BACKEND_DIR / "server.py"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


class TestServerWorkers(unittest.TestCase):
    def test_environment_cannot_override_single_worker_even_with_reload(self) -> None:
        for reload in ("0", "1"):
            with self.subTest(reload=reload), patch.dict(os.environ, {
                "COMIC_SHELF_WORKERS": "4", "WEB_CONCURRENCY": "4", "COMIC_SHELF_RELOAD": reload,
            }), patch.object(sys, "argv", [str(SERVER)]), patch("uvicorn.run") as run:
                runpy.run_path(str(SERVER), run_name="__main__")
                self.assertEqual(run.call_args.kwargs["workers"], 1)
                self.assertEqual(run.call_args.kwargs["reload"], reload == "1")

    def test_worker_cli_option_is_not_available(self) -> None:
        output = io.StringIO()
        with patch.object(sys, "argv", [str(SERVER), "--workers", "2"]), patch(
            "uvicorn.run"
        ) as run, contextlib.redirect_stderr(output):
            with self.assertRaises(SystemExit) as error:
                runpy.run_path(str(SERVER), run_name="__main__")
        self.assertEqual(error.exception.code, 2)
        self.assertIn("unrecognized arguments: --workers 2", output.getvalue())
        run.assert_not_called()

    def test_library_lock_rejects_a_second_process(self) -> None:
        from app.storage.utils import acquire_library_writer_lock

        with tempfile.TemporaryDirectory() as tmp:
            library = Path(tmp) / "library"
            fd = acquire_library_writer_lock(library)
            try:
                script = (
                    "import sys\n"
                    f"sys.path.insert(0, {str(BACKEND_DIR)!r})\n"
                    "from pathlib import Path\n"
                    "from app.storage.utils import acquire_library_writer_lock\n"
                    "try:\n"
                    f"    acquire_library_writer_lock(Path({str(library)!r}))\n"
                    "except RuntimeError:\n"
                    "    raise SystemExit(2)\n"
                    "raise SystemExit(0)\n"
                )
                result = subprocess.run(
                    [sys.executable, "-c", script],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 2, result.stderr)
            finally:
                os.close(fd)


if __name__ == "__main__":
    unittest.main()
