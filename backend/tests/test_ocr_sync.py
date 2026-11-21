"""真实 shell 编排及本机增量入库回归；仅用一次性书库和假的画页识别引擎。"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


class TestLocalSync(unittest.TestCase):
    def setUp(self):
        from PIL import Image

        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.data = self.root / "outer/library/data"
        self.library = self.data / "library"
        self.page = self.library / "jm/1/pages/page.png"
        self.page.parent.mkdir(parents=True)
        Image.new("RGB", (40, 60), "white").save(self.page)
        scripts = self.root / "scripts"
        scripts.mkdir()
        repo = Path(__file__).resolve().parents[2]
        shutil.copyfile(repo / "scripts/ocr.sh", scripts / "ocr.sh")
        (self.root / ".venv").symlink_to(sys.prefix, target_is_directory=True)
        (self.root / ".venv-ocr/bin").mkdir(parents=True)
        (self.root / ".venv-ocr/bin/python").symlink_to(sys.executable)
        shutil.copyfile(Path(sys.prefix) / "pyvenv.cfg", self.root / ".venv-ocr/pyvenv.cfg")
        (self.root / ".venv-ocr/lib").symlink_to(Path(sys.prefix) / "lib", target_is_directory=True)
        self.log = self.root / "calls.jsonl"
        self.env = {
            **os.environ,
            "OCR_TEST_DATA": str(self.data),
            "OCR_TEST_LOG": str(self.log),
            "COMIC_SHELF_DATA": str(self.root / "wrong-library"),
            "COMIC_SHELF_OCR_VENV": str(self.root / ".venv-ocr"),
        }
        # 真实 worker 的参数解析、增量与落盘；阻止它导入任何后端数据库模块。
        (scripts / "ocr_worker.py").write_text(
            textwrap.dedent("""
            import json, os, sys
            from pathlib import Path
            from unittest import mock
            from tests.test_ocr_worker import TestBatchRun
            from scripts import ocr_worker
            with open(os.environ["OCR_TEST_LOG"], "a") as log:
                log.write(json.dumps(["ocr", sys.executable, sys.argv[1:]]) + "\\n")
            case = TestBatchRun()
            case.data_dir = Path(os.environ["OCR_TEST_DATA"])
            case.library = case.data_dir / "library"
            fail_on = os.environ.get("OCR_TEST_FAIL_PAGE", "").split(",")
            with mock.patch.dict(sys.modules, {"app.db": None}), mock.patch.object(ocr_worker, "cuda_ready", return_value=(True, "")):
                code, _ = case._run(*sys.argv[1:], fail_on=fail_on)
            raise SystemExit(code)
        """)
        )
        # 成功路径直接调用后端入口；失败路径仅注入同步或建表故障。
        (scripts / "sync_ocr.py").write_text(
            textwrap.dedent("""
            import json, os, sys
            from unittest import mock
            from app.sync_ocr import main
            with open(os.environ["OCR_TEST_LOG"], "a") as log:
                log.write(json.dumps(["sync", sys.executable, sys.argv[1:]]) + "\\n")
            if os.environ.get("OCR_TEST_FAIL_INIT"):
                os.environ["COMIC_SHELF_DATA"] = os.environ["OCR_TEST_DATA"]
                with mock.patch("app.db.schema.init_dialogue_db", side_effect=OSError("模拟建表失败")):
                    raise SystemExit(main())
            if os.environ.get("OCR_TEST_FAIL_SYNC") and "--check" not in sys.argv:
                os.environ["COMIC_SHELF_DATA"] = os.environ["OCR_TEST_DATA"]
                with mock.patch("app.db.dialogues.sync_comic_dialogues", side_effect=OSError("模拟入库失败")):
                    raise SystemExit(main())
            raise SystemExit(main())
        """)
        )

    def tearDown(self):
        self.temp.cleanup()

    def run_ocr(self, *args, **env):
        result = subprocess.run(
            ["bash", "scripts/ocr.sh", "run", "--data-dir", str(self.data), "--sync-local", *args],
            cwd=self.root,
            env={**self.env, **env},
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        return result

    def test_gpu_extraction_and_local_sync_use_separate_environments(self):
        result = self.run_ocr("--source=jm", "--id=1")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        calls = [json.loads(line) for line in self.log.read_text().splitlines()]
        self.assertEqual(["ocr", "sync", "ocr", "sync"], [call[0] for call in calls])
        self.assertTrue(all(".venv-ocr" in call[1] and "--gpu" in call[2] for call in calls if call[0] == "ocr"))
        self.assertTrue(all("/.venv/" in call[1] for call in calls if call[0] == "sync"))
        with sqlite3.connect(self.data / "comic_dialogues.db") as conn:
            self.assertEqual(
                [("jm", "1", "台词")],
                conn.execute("SELECT source, source_id, text FROM comic_dialogues_fts").fetchall(),
            )
        self.assertFalse((self.data / "comic_shelf.db").exists(), "台词同步不能初始化主库")
        self.assertFalse((self.root / "wrong-library").exists())

    def test_failed_sync_retries_on_incremental_hit_including_single_image(self):
        for args in ((), ("--image", str(self.page))):
            with self.subTest(args=args):
                for fails in ("1", "1", ""):
                    result = self.run_ocr(*args, OCR_TEST_FAIL_SYNC=fails)
                    self.assertEqual(1 if fails else 0, result.returncode, result.stdout + result.stderr)
                    output = self.page.with_name("page.ocr.json")
                    if fails == "1" and not hasattr(self, "before"):
                        self.before = output.read_bytes(), output.stat().st_mtime_ns
                    self.assertEqual(self.before, (output.read_bytes(), output.stat().st_mtime_ns))
        with sqlite3.connect(self.data / "comic_dialogues.db") as conn:
            self.assertEqual(1, conn.execute("SELECT count(*) FROM comic_dialogues_fts").fetchone()[0])

    def test_partial_extraction_failure_still_syncs_good_results_and_returns_failure(self):
        from PIL import Image

        Image.new("RGB", (40, 60), "white").save(self.page.parent / "bad.png")
        for _ in range(2):
            result = self.run_ocr(OCR_TEST_FAIL_PAGE="bad.png")
            self.assertEqual(1, result.returncode, result.stdout + result.stderr)
            with sqlite3.connect(self.data / "comic_dialogues.db") as conn:
                self.assertEqual(1, conn.execute("SELECT count(*) FROM comic_dialogues_fts").fetchone()[0])
        self.assertFalse((self.page.parent / "bad.ocr.json").exists())

    def test_module_entry_works_with_only_the_container_app_directory(self):
        repo = Path(__file__).resolve().parents[2]
        isolated = self.root / "container"
        shutil.copytree(repo / "backend/app", isolated / "app", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        (isolated / "sitecustomize.py").write_text(
            'import sys\nfor name in ("rapidocr", "onnxruntime", "numpy", "cv2", "tokenizers"):\n    sys.modules[name] = None\n'
        )
        self.page.with_name("page.ocr.json").write_text(
            json.dumps(
                {
                    "engine": "rapidocr",
                    "bubbles": [{"id": 1, "order": 1, "box": [0.1, 0.1, 0.4, 0.4], "text": "台词"}],
                }
            )
        )
        result = subprocess.run(
            [sys.executable, "-m", "app.sync_ocr", "--source", "jm", "--id", "1"],
            cwd=isolated,
            env={**self.env, "PYTHONPATH": str(isolated), "COMIC_SHELF_DATA": str(self.data)},
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        with sqlite3.connect(self.data / "comic_dialogues.db") as conn:
            self.assertEqual("台词", conn.execute("SELECT text FROM comic_dialogues_fts").fetchone()[0])
        self.assertFalse((self.data / "comic_shelf.db").exists())

    def test_scoped_sync_preserves_other_comics_even_when_their_directory_is_missing(self):
        result = self.run_ocr()
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        with sqlite3.connect(self.data / "comic_dialogues.db") as conn:
            conn.execute(
                "INSERT INTO comic_dialogues_fts SELECT source, 'orphan', page_index, bubble_id, text, lang, "
                "box_json, reading_order, kind, text_norm FROM comic_dialogues_fts WHERE source_id = '1'"
            )
        result = subprocess.run(
            [sys.executable, "-m", "app.sync_ocr", "--data-dir", str(self.data), "--id", "1"],
            cwd=self.root,
            env=self.env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        with sqlite3.connect(self.data / "comic_dialogues.db") as conn:
            self.assertEqual(
                [("1",), ("orphan",)],
                conn.execute("SELECT source_id FROM comic_dialogues_fts ORDER BY source_id").fetchall(),
            )

    def test_bad_inputs_or_init_failure_stop_before_extraction(self):
        shutil.copyfile(self.page, self.root / "outside.png")
        for args, env in (
            (("--source", "missing"), {}),
            (("--page", "abc"), {}),
            (("--directory", str(self.page.parent)), {}),
            (("--image", str(self.root / "outside.png")), {}),
            ((), {"OCR_TEST_FAIL_INIT": "1"}),
        ):
            with self.subTest(args=args, env=env):
                result = self.run_ocr(*args, **env)
                self.assertNotEqual(0, result.returncode, result.stdout + result.stderr)
                self.assertEqual([], list(self.library.rglob("*.ocr.json")))


class TestIndexBoundaries(unittest.TestCase):
    def setUp(self):
        from unittest import mock

        from app.db import connection, dialogues, schema

        self.temp = tempfile.TemporaryDirectory()
        self.data = Path(self.temp.name)
        self.book = self.data / "library/local/book"
        self.book.mkdir(parents=True)
        self.connection = connection
        self.dialogues = dialogues
        self.schema = schema
        self.old_data = connection.get_data_dir()
        self.old_db = connection.get_dialogue_db_path()
        connection.set_data_dir(self.data)
        schema.init_dialogue_db(self.data / "dialogues.db")
        self.embedding = mock.patch.object(dialogues, "embed_comic_dialogues", return_value=0)
        self.embedding.start()

    def tearDown(self):
        self.embedding.stop()
        self.connection.set_data_dir(self.old_data)
        self.connection.set_dialogue_db_path(self.old_db)
        self.temp.cleanup()

    def sidecar(self, name, text):
        path = self.book / "pages" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {"engine": "rapidocr", "bubbles": [{"id": 1, "order": 1, "box": [0.1, 0.1, 0.4, 0.4], "text": text}]}
            )
        )
        return path

    def records(self):
        with self.connection.get_dialogue_db() as conn:
            return [
                tuple(row)
                for row in conn.execute("SELECT page_index, text FROM comic_dialogues_fts ORDER BY page_index")
            ]

    def test_deleted_sidecar_updates_index_without_force(self):
        old = self.sidecar("00001.ocr.json", "第一页台词")
        self.sidecar("00002.ocr.json", "第二页台词")
        self.assertEqual(2, self.dialogues.sync_comic_dialogues("local", "book"))
        old.unlink()
        self.assertEqual(1, self.dialogues.sync_comic_dialogues("local", "book"))
        self.assertEqual([(2, "第二页台词")], self.records())

    def test_album_only_change_updates_global_page_mapping(self):
        self.sidecar("c1/00001.ocr.json", "第一话台词")
        self.sidecar("c2/00001.ocr.json", "第二话台词")
        album = self.book / "album.json"
        for order in (("c1", "c2"), ("c2", "c1")):
            album.write_text(
                json.dumps(
                    {
                        "pages": [
                            {"index": index, "file": "00001.png", "chapter": chapter}
                            for index, chapter in enumerate(order, start=1)
                        ]
                    }
                )
            )
            self.assertEqual(2, self.dialogues.sync_comic_dialogues("local", "book"))
        self.assertEqual([(1, "第二话台词"), (2, "第一话台词")], self.records())

    def test_preserved_old_mtime_does_not_hide_added_or_rewritten_files(self):
        first = self.sidecar("00001.ocr.json", "最初的台词")
        old_time = first.stat().st_mtime_ns
        self.sidecar("00002.ocr.json", "第二页台词")
        self.assertEqual(2, self.dialogues.sync_comic_dialogues("local", "book"))
        added = self.sidecar("00003.ocr.json", "第三页台词")
        os.utime(added, ns=(old_time - 10_000, old_time - 10_000))
        self.sidecar("00001.ocr.json", "更新的台词")
        os.utime(first, ns=(old_time, old_time))
        self.assertEqual(3, self.dialogues.sync_comic_dialogues("local", "book"))
        self.assertEqual([(1, "更新的台词"), (2, "第二页台词"), (3, "第三页台词")], self.records())

    def test_unchanged_comic_skips_json_parsing_and_encoding(self):
        from unittest import mock

        self.sidecar("00001.ocr.json", "第一条台词")
        self.assertEqual(1, self.dialogues.sync_comic_dialogues("local", "book"))
        with (
            mock.patch.object(self.dialogues, "read_json", side_effect=AssertionError("缓存命中不应解析 JSON")),
            mock.patch.object(self.dialogues, "embed_comic_dialogues", side_effect=AssertionError("缓存命中不应编码")),
        ):
            self.assertEqual(1, self.dialogues.sync_comic_dialogues("local", "book"))

    def test_linked_assets_are_skipped_and_linked_page_directory_is_rejected(self):
        self.sidecar("00001.ocr.json", "自己的台词")
        foreign = self.data / "foreign"
        foreign.mkdir()
        (foreign / "00002.ocr.json").write_text(json.dumps({"bubbles": [{"text": "不属于这本的台词"}]}))
        pages = self.book / "pages"
        (pages / "00002.ocr.json").symlink_to(foreign / "00002.ocr.json")
        (pages / "linked-chapter").symlink_to(foreign, target_is_directory=True)
        self.assertEqual(1, self.dialogues.sync_comic_dialogues("local", "book"))
        self.assertEqual([(1, "自己的台词")], self.records())
        pages.rename(self.book / "saved-pages")
        pages.symlink_to(foreign, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "符号链接"):
            self.dialogues.sync_comic_dialogues("local", "book")
        self.assertEqual([(1, "自己的台词")], self.records())

    def test_link_swap_before_read_preserves_previous_index(self):
        from unittest import mock

        path = self.sidecar("00001.ocr.json", "原本的台词")
        self.assertEqual(1, self.dialogues.sync_comic_dialogues("local", "book"))
        foreign = self.data / "foreign.json"
        foreign.write_text(json.dumps({"bubbles": [{"text": "不能读入的台词"}]}))
        original_read = self.dialogues.read_json

        def swap_link(file, **kwargs):
            if file == path:
                path.unlink()
                path.symlink_to(foreign)
            return original_read(file, **kwargs)

        with mock.patch.object(self.dialogues, "read_json", side_effect=swap_link), self.assertRaises(OSError):
            self.dialogues.sync_comic_dialogues("local", "book", force=True)
        self.assertEqual([(1, "原本的台词")], self.records())

    def test_old_metadata_migrates_without_rebuilding_fts(self):
        self.sidecar("00001.ocr.json", "原本的台词")
        self.assertEqual(1, self.dialogues.sync_comic_dialogues("local", "book"))
        with self.connection.get_dialogue_db() as conn:
            conn.execute("ALTER TABLE comic_ocr_sync_meta DROP COLUMN source_signature")
            conn.execute("UPDATE comic_ocr_sync_meta SET last_synced_mtime = 9e12")
        self.sidecar("00001.ocr.json", "更新的台词")
        self.schema.init_dialogue_db()
        self.assertEqual([(1, "原本的台词")], self.records())
        self.assertEqual(1, self.dialogues.sync_comic_dialogues("local", "book"))
        self.assertEqual([(1, "更新的台词")], self.records())

    def test_source_change_during_sync_preserves_previous_index(self):
        from unittest import mock

        path = self.sidecar("00001.ocr.json", "原本的台词")
        self.assertEqual(1, self.dialogues.sync_comic_dialogues("local", "book"))
        original_read = self.dialogues.read_json

        def change_after_read(file, **kwargs):
            data = original_read(file, **kwargs)
            if file == path:
                self.sidecar("00001.ocr.json", "并发的新台词")
            return data

        with (
            mock.patch.object(self.dialogues, "read_json", side_effect=change_after_read),
            self.assertRaisesRegex(RuntimeError, "发生变化"),
        ):
            self.dialogues.sync_comic_dialogues("local", "book", force=True)
        self.assertEqual([(1, "原本的台词")], self.records())


if __name__ == "__main__":
    unittest.main()
