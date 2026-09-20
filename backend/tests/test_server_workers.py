"""The supported server entry point must not launch independent storage writers."""
from __future__ import annotations

import contextlib
import io
import os
from pathlib import Path
import runpy
import sys
import unittest
from unittest.mock import patch

SERVER = Path(__file__).resolve().parent.parent / "server.py"


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


if __name__ == "__main__":
    unittest.main()
