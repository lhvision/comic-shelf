"""广告实样、正文保留、坏资产回退、向量重试和同步预算；全部使用一次性书库。"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from app import embedding
from app.db import connection, dialogues, schema
from app.ocr import assets
from app.ocr import sync as sync_ocr
from app.ocr.classification import advertisement_page_reason


class TestOCRReliability(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.data = Path(self.temp.name)
        self.old_data = connection.get_data_dir()
        self.old_db = connection.get_dialogue_db_path()
        connection.set_data_dir(self.data)
        schema.init_dialogue_db(self.data / "dialogues.db")
        self.encoder = mock.patch.object(embedding, "dim", return_value=2)
        self.signature = mock.patch.object(embedding, "model_signature", return_value="test-model")
        self.documents = mock.patch.object(embedding, "encode_documents", side_effect=self.encode)
        for patch in (self.encoder, self.signature, self.documents):
            patch.start()

    def tearDown(self):
        for patch in (self.encoder, self.signature, self.documents):
            patch.stop()
        connection.set_data_dir(self.old_data)
        connection.set_dialogue_db_path(self.old_db)
        self.temp.cleanup()

    @staticmethod
    def encode(texts, batch=64, *, expected_signature=None):
        return np.tile(np.array([1.0, 0.0], dtype=np.float32), (len(texts), 1))

    def sidecar(self, sid, page, texts):
        path = self.data / "library/local" / sid / "pages" / f"{page:05d}.ocr.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "engine": "rapidocr",
                    "bubbles": [
                        {"id": index, "order": index, "box": [0.1, 0.1, 0.4, 0.4], "text": text}
                        for index, text in enumerate(texts, start=1)
                    ],
                }
            ),
            encoding="utf-8",
        )
        return path

    def records(self):
        with connection.get_dialogue_db() as conn:
            return [
                tuple(row)
                for row in conn.execute("SELECT page_index, text, kind FROM comic_dialogues_fts ORDER BY rowid")
            ]

    def test_jm_page_32_is_preserved_but_not_searchable(self):
        fixture = Path(__file__).parent / "fixtures/ocr/jm-advertisement.ocr.json"
        payload = json.loads(fixture.read_text())
        page = self.sidecar("advertisement", 32, [])
        page.write_bytes(fixture.read_bytes())
        before = page.read_bytes()
        self.sidecar("advertisement", 1, ["第一页开始了我们的故事", "I love you", "把你的邮箱给我"])
        self.assertEqual(
            "platform_download_poster",
            advertisement_page_reason([bubble["text"] for bubble in payload["bubbles"]], payload["bubbles"]),
        )
        dialogues.sync_comic_dialogues("local", "advertisement", strict_vectors=True)
        self.assertEqual(before, page.read_bytes())
        ad = [row for row in self.records() if row[0] == 32]
        self.assertEqual(8, len(ad))
        self.assertTrue(all(row[2] == "paratext" for row in ad))
        self.assertTrue(all(row[2] == "dialogue" for row in self.records() if row[0] == 1))
        for text in ("沉醉", "根本就活不下去", "社群系统"):
            self.assertEqual([], dialogues.search_dialogues(text))
        with mock.patch.object(embedding, "encode_query", return_value=np.array([1, 0], dtype=np.float32)):
            result = dialogues.search_dialogues_semantic("社群系统")
            self.assertTrue(result["results"])
            self.assertTrue(all(item["page_index"] == 1 for item in result["results"]))
        with connection.get_dialogue_db() as conn:
            self.assertEqual(
                0, conn.execute("SELECT count(*) FROM comic_dialogue_vectors WHERE page_index = 32").fetchone()[0]
            )

    def test_small_corner_promotion_does_not_exclude_story(self):
        texts = ["我们明天还在这里见面吗？", "JM官方唯一号扫码下载", "https://jm365.work/demo"]
        bubbles = [{"text": text, "box": [0.9, 0.9, 0.92, 0.98]} for text in texts]
        bubbles[0]["box"] = [0.1, 0.1, 0.5, 0.8]
        self.assertEqual("", advertisement_page_reason(texts, bubbles))

    def test_corrupt_asset_preserves_previous_index_and_sync_signature(self):
        page = self.sidecar("broken", 1, ["原本的剧情对白"])
        dialogues.sync_comic_dialogues("local", "broken", strict_vectors=True)
        before = self.records()
        with connection.get_dialogue_db() as conn:
            signature = conn.execute("SELECT source_signature FROM comic_ocr_sync_meta").fetchone()[0]
        page.write_text("{broken", encoding="utf-8")
        with self.assertRaises(json.JSONDecodeError):
            dialogues.sync_comic_dialogues("local", "broken", strict_vectors=True)
        self.assertEqual(before, self.records())
        with connection.get_dialogue_db() as conn:
            self.assertEqual(signature, conn.execute("SELECT source_signature FROM comic_ocr_sync_meta").fetchone()[0])
        self.assertTrue(dialogues.comic_dialogues_need_sync("local", "broken"))

    def test_failed_second_vector_batch_retries_without_reparsing_keywords(self):
        self.sidecar("retry", 1, [f"这是第{index}条完整对白" for index in range(130)])
        calls = []

        def fail_second(texts, batch=64, *, expected_signature=None):
            calls.append(len(texts))
            if len(calls) == 2:
                raise RuntimeError("模拟第二批失败")
            return self.encode(texts)

        with mock.patch.object(embedding, "encode_documents", side_effect=fail_second), self.assertRaises(RuntimeError):
            dialogues.sync_comic_dialogues("local", "retry", strict_vectors=True)
        self.assertEqual([64, 64], calls)
        self.assertEqual(130, len(self.records()))
        with connection.get_dialogue_db() as conn:
            self.assertEqual(0, conn.execute("SELECT count(*) FROM comic_dialogue_vectors").fetchone()[0])
            self.assertEqual("", conn.execute("SELECT vector_source_signature FROM comic_ocr_sync_meta").fetchone()[0])
        with mock.patch.object(dialogues, "read_json", side_effect=AssertionError("只补向量不应解析原文")):
            self.assertEqual(130, dialogues.sync_comic_dialogues("local", "retry", strict_vectors=True))
        with connection.get_dialogue_db() as conn:
            self.assertEqual(130, conn.execute("SELECT count(*) FROM comic_dialogue_vectors").fetchone()[0])
        self.assertFalse(dialogues.comic_dialogues_need_sync("local", "retry"))

    def test_model_change_same_dimension_reencodes(self):
        self.sidecar("model", 1, ["我们明天再见面"])
        dialogues.sync_comic_dialogues("local", "model", strict_vectors=True)
        with mock.patch.object(embedding, "model_signature", return_value="changed-model"):
            self.assertTrue(dialogues.comic_dialogues_need_sync("local", "model"))
            self.assertEqual("model_mismatch", dialogues.dialogue_vector_status()["reason"])
            with mock.patch.object(dialogues, "read_json", side_effect=AssertionError("模型变化不应重读原文")):
                dialogues.sync_comic_dialogues("local", "model", strict_vectors=True)
            self.assertTrue(dialogues.dialogue_vector_status()["available"])

    def test_model_only_reencoding_failure_is_counted_and_retries(self):
        self.sidecar("model-retry", 1, ["我们明天再见面"])
        dialogues.sync_comic_dialogues("local", "model-retry", strict_vectors=True)
        with mock.patch.object(embedding, "model_signature", return_value="changed-model"):
            with (
                mock.patch.object(embedding, "encode_documents", side_effect=RuntimeError("模拟模型重编码失败")),
                self.assertRaisesRegex(RuntimeError, "模拟模型重编码失败"),
            ):
                dialogues.sync_comic_dialogues("local", "model-retry", strict_vectors=True)
            status = dialogues.dialogue_vector_status()
            self.assertEqual((1, 1), (status["pending_comics"], status["failed_comics"]))
            with connection.get_dialogue_db() as conn:
                self.assertEqual(1, conn.execute("SELECT count(*) FROM comic_dialogue_vectors").fetchone()[0])
            with mock.patch.object(dialogues, "read_sidecar", side_effect=AssertionError("重试不能重读关键词")):
                dialogues.sync_comic_dialogues("local", "model-retry", strict_vectors=True)
            status = dialogues.dialogue_vector_status()
            self.assertTrue(status["complete"])
            self.assertEqual(0, status["failed_comics"])

    def test_old_model_failure_does_not_mark_successful_reencoding_failed(self):
        self.sidecar("model-concurrent", 1, ["我们明天再见面"])
        dialogues.sync_comic_dialogues("local", "model-concurrent", strict_vectors=True)

        def newer_commit(texts, batch=64, *, expected_signature=None):
            with (
                mock.patch.object(embedding, "model_signature", return_value="newest-model"),
                mock.patch.object(embedding, "encode_documents", side_effect=self.encode),
            ):
                dialogues.sync_comic_dialogues("local", "model-concurrent", strict_vectors=True)
            raise RuntimeError("旧编码任务失败")

        with mock.patch.object(embedding, "model_signature", return_value="changed-model"):
            with (
                mock.patch.object(embedding, "encode_documents", side_effect=newer_commit),
                self.assertRaisesRegex(RuntimeError, "旧编码任务失败"),
            ):
                dialogues.sync_comic_dialogues("local", "model-concurrent", strict_vectors=True)
            with mock.patch.object(embedding, "model_signature", return_value="newest-model"):
                status = dialogues.dialogue_vector_status()
                self.assertTrue(status["complete"])
                self.assertEqual(0, status["failed_comics"])

    def test_sync_budget_and_skip_vectors_resume(self):
        for sid in ("a", "b", "c"):
            self.sidecar(sid, 1, ["我们明天再见面"])
        for expected in (1, 2, 3, 3):
            with (
                mock.patch.object(
                    sys, "argv", ["sync", "--data-dir", str(self.data), "--limit", "1", "--skip-vectors"]
                ),
                mock.patch.dict(os.environ),
            ):
                self.assertEqual(0, sync_ocr.main())
            self.assertEqual(expected, len(self.records()))
        with connection.get_dialogue_db() as conn:
            self.assertEqual(0, conn.execute("SELECT count(*) FROM comic_dialogue_vectors").fetchone()[0])
        with (
            mock.patch.object(sys, "argv", ["sync", "--data-dir", str(self.data), "--limit", "1"]),
            mock.patch.dict(os.environ),
        ):
            self.assertEqual(0, sync_ocr.main())
        with connection.get_dialogue_db() as conn:
            self.assertEqual(1, conn.execute("SELECT count(*) FROM comic_dialogue_vectors").fetchone()[0])

    def test_legacy_vectors_require_reencoding_after_schema_upgrade(self):
        self.sidecar("legacy-vectors", 1, ["我们明天再见面"])
        dialogues.sync_comic_dialogues("local", "legacy-vectors", strict_vectors=True)
        with connection.get_dialogue_db() as conn:
            conn.execute("ALTER TABLE comic_ocr_sync_meta DROP COLUMN vector_source_signature")
            conn.execute("ALTER TABLE comic_ocr_sync_meta DROP COLUMN vector_model_signature")
        schema.init_dialogue_db()
        status = dialogues.dialogue_vector_status()
        self.assertFalse(status["available"])
        self.assertEqual("model_mismatch", status["reason"])
        self.assertEqual(1, status["pending_comics"])
        with mock.patch.object(embedding, "encode_query") as query:
            self.assertEqual(
                {"results": [], "available": False, "reason": "model_mismatch"},
                dialogues.search_dialogues_semantic("见面"),
            )
            query.assert_not_called()
        self.assertTrue(dialogues.search_dialogues("见面"))
        with mock.patch.object(dialogues, "read_sidecar", side_effect=AssertionError("补向量不应重读关键词")):
            dialogues.sync_comic_dialogues("local", "legacy-vectors", strict_vectors=True)
        status = dialogues.dialogue_vector_status()
        self.assertTrue(status["available"])
        self.assertTrue(status["complete"])

    def test_vectors_without_sync_metadata_are_not_searchable(self):
        self.sidecar("orphan-vectors", 1, ["我们明天再见面"])
        dialogues.sync_comic_dialogues("local", "orphan-vectors", strict_vectors=True)
        with connection.get_dialogue_db() as conn:
            conn.execute("DELETE FROM comic_ocr_sync_meta")
        status = dialogues.dialogue_vector_status()
        self.assertFalse(status["available"])
        self.assertEqual("model_mismatch", status["reason"])

    def test_unsigned_metadata_without_vectors_does_not_disable_search(self):
        self.sidecar("ready", 1, ["我们明天再见面"])
        self.sidecar("short", 1, ["你好"])
        dialogues.sync_comic_dialogues("local", "ready", strict_vectors=True)
        dialogues.sync_comic_dialogues("local", "short", sync_vectors=False)
        self.assertTrue(dialogues.dialogue_vector_status()["available"])

    def test_query_model_change_rejects_search_before_vector_scan(self):
        self.sidecar("query-model", 1, ["我们明天再见面"])
        dialogues.sync_comic_dialogues("local", "query-model", strict_vectors=True)
        with (
            mock.patch.object(embedding, "encode_query", return_value=None) as query,
            mock.patch.object(dialogues, "_vector_chunks") as chunks,
        ):
            result = dialogues.search_dialogues_semantic("见面")
            self.assertEqual({"results": [], "available": False, "reason": "model_mismatch"}, result)
            query.assert_called_once_with("见面", expected_signature="test-model")
            chunks.assert_not_called()

    def test_chunked_recall_matches_cache_across_repeated_pages_and_ties(self):
        self.sidecar("chunks", 1, [f"同页的第{index}条完整台词" for index in range(90)])
        for page in range(2, 80):
            self.sidecar("chunks", page, ["我们明天再见面"])
        dialogues.sync_comic_dialogues("local", "chunks", strict_vectors=True)
        with (
            mock.patch.object(embedding, "encode_query", return_value=np.array([1, 0], dtype=np.float32)),
            mock.patch.object(dialogues, "_VECTOR_SCAN_BATCH", 7),
        ):
            with mock.patch.object(dialogues, "_VECTOR_CACHE_MAX_BYTES", 32 * 1024 * 1024):
                cached = dialogues.search_dialogues_semantic("见面", limit=20)
            with mock.patch.object(dialogues, "_VECTOR_CACHE_MAX_BYTES", 0):
                streamed = dialogues.search_dialogues_semantic("见面", limit=20)
                self.assertIsNone(dialogues._VECTOR_CACHE)
        self.assertEqual(cached, streamed)
        self.assertEqual(list(range(1, 21)), [item["page_index"] for item in streamed["results"]])
        self.assertEqual(1, streamed["results"][0]["bubble_id"])

    def test_query_read_snapshot_does_not_mix_old_vectors_and_new_text(self):
        self.sidecar("snapshot", 1, ["原本的剧情对白"])
        dialogues.sync_comic_dialogues("local", "snapshot", strict_vectors=True)
        original_chunks = dialogues._vector_chunks

        def concurrent_update(*args):
            for chunk in original_chunks(*args):
                with connection.get_dialogue_db() as writer:
                    writer.execute(
                        "UPDATE comic_dialogues_fts SET text = '新版本的剧情对白', text_norm = '新版本的剧情对白'"
                    )
                    dialogues._bump_vector_version(writer)
                yield chunk

        with (
            mock.patch.object(embedding, "encode_query", return_value=np.array([1, 0], dtype=np.float32)),
            mock.patch.object(dialogues, "_vector_chunks", side_effect=concurrent_update),
        ):
            result = dialogues.search_dialogues_semantic("剧情")
        self.assertEqual("原本的剧情对白", result["results"][0]["text"])

    def test_old_encoder_cannot_overwrite_new_vector_commit(self):
        self.sidecar("concurrent", 1, ["我们明天再见面"])
        dialogues.sync_comic_dialogues("local", "concurrent", strict_vectors=True)

        def new_commit(texts, batch=64, *, expected_signature=None):
            with connection.get_dialogue_db() as writer:
                writer.execute(
                    "UPDATE comic_dialogue_vectors SET vec = ?", (np.array([0, 1], dtype=np.float32).tobytes(),)
                )
                dialogues._bump_vector_version(writer)
            return self.encode(texts)

        with (
            mock.patch.object(embedding, "encode_documents", side_effect=new_commit),
            self.assertRaisesRegex(RuntimeError, "向量索引发生变化"),
        ):
            dialogues.embed_comic_dialogues("local", "concurrent")
        with connection.get_dialogue_db() as conn:
            vector = conn.execute("SELECT vec FROM comic_dialogue_vectors").fetchone()[0]
        np.testing.assert_array_equal(np.frombuffer(vector, dtype=np.float32), [0, 1])

    def test_changed_original_rejects_old_ocr_even_on_incremental_sync(self):
        from PIL import Image

        page = self.sidecar("original", 1, ["最初的完整对白"])
        image = page.with_name("00001.png")
        Image.new("RGB", (40, 60), "white").save(image)
        payload = json.loads(page.read_text())
        payload["source_image"] = {"size": image.stat().st_size, "mtime_ns": image.stat().st_mtime_ns}
        page.write_text(json.dumps(payload))
        dialogues.sync_comic_dialogues("local", "original", strict_vectors=True)
        before = self.records()
        self.assertEqual(0, dialogues.dialogue_vector_status()["unverified_pages"])
        Image.new("RGB", (80, 120), "black").save(image)
        self.assertTrue(dialogues.comic_dialogues_need_sync("local", "original"))
        with self.assertRaisesRegex(ValueError, "OCR 已过期"):
            dialogues.sync_comic_dialogues("local", "original", strict_vectors=True)
        self.assertEqual(before, self.records())
        image.unlink()
        with self.assertRaisesRegex(ValueError, "原图缺失"):
            dialogues.sync_comic_dialogues("local", "original", strict_vectors=True)
        self.assertEqual(before, self.records())

    def test_legacy_assets_are_counted_as_unverified_not_rejected(self):
        self.sidecar("legacy", 1, ["历史版本的完整对白"])
        dialogues.sync_comic_dialogues("local", "legacy", strict_vectors=True)
        self.assertEqual(1, dialogues.dialogue_vector_status()["unverified_pages"])
        self.assertEqual(1, len(self.records()))

    def test_input_budgets_leave_previous_index_untouched(self):
        page = self.sidecar("budget", 1, ["原有完整对白"])
        dialogues.sync_comic_dialogues("local", "budget", strict_vectors=True)
        before = self.records()
        for patch, texts in (
            (mock.patch.object(assets, "MAX_SIDECAR_BYTES", 16), ["原有完整对白"]),
            (mock.patch.object(assets, "MAX_PAGE_BUBBLES", 1), ["一句完整对白", "第二句完整对白"]),
            (mock.patch.object(assets, "MAX_TEXT_CHARS", 4), ["这是一句超过预算的对白"]),
        ):
            self.sidecar("budget", 1, texts)
            with patch, self.assertRaisesRegex(ValueError, "预算"):
                dialogues.sync_comic_dialogues("local", "budget", strict_vectors=True)
            self.assertEqual(before, self.records())
        self.assertTrue(page.exists())

    def test_keyword_publish_rejects_new_index_commit(self):
        page = self.sidecar("conflict", 1, ["最初的完整对白"])
        dialogues.sync_comic_dialogues("local", "conflict", strict_vectors=True)
        self.sidecar("conflict", 1, ["旧任务即将发布的对白"])
        original_read = dialogues.read_sidecar

        def new_commit(file, **kwargs):
            payload = original_read(file, **kwargs)
            if file == page:
                with connection.get_dialogue_db() as writer:
                    writer.execute("UPDATE comic_dialogues_fts SET text = '另一个任务的新提交'")
                    dialogues._bump_vector_version(writer)
            return payload

        with (
            mock.patch.object(dialogues, "read_sidecar", side_effect=new_commit),
            self.assertRaisesRegex(RuntimeError, "已有新提交"),
        ):
            dialogues.sync_comic_dialogues("local", "conflict", strict_vectors=True)
        self.assertEqual("另一个任务的新提交", self.records()[0][1])

    def test_vector_progress_reports_pending_failed_and_completed(self):
        self.sidecar("complete", 1, ["已经编码的完整对白"])
        self.sidecar("pending", 1, ["等待编码的完整对白"])
        self.sidecar("failed", 1, ["编码失败的完整对白"])
        dialogues.sync_comic_dialogues("local", "complete", strict_vectors=True)
        dialogues.sync_comic_dialogues("local", "pending", sync_vectors=False)
        with (
            mock.patch.object(embedding, "encode_documents", side_effect=RuntimeError("模拟编码失败")),
            self.assertRaises(RuntimeError),
        ):
            dialogues.sync_comic_dialogues("local", "failed", strict_vectors=True)
        status = dialogues.dialogue_vector_status()
        self.assertTrue(status["available"])
        self.assertFalse(status["complete"])
        self.assertEqual((3, 2, 1), (status["eligible_comics"], status["pending_comics"], status["failed_comics"]))
        dialogues.sync_comic_dialogues("local", "failed", strict_vectors=True)
        dialogues.sync_comic_dialogues("local", "pending", strict_vectors=True)
        status = dialogues.dialogue_vector_status()
        self.assertTrue(status["complete"])
        self.assertEqual((0, 0), (status["pending_comics"], status["failed_comics"]))

    def test_failure_status_write_error_does_not_break_keyword_fallback(self):
        import sqlite3

        self.sidecar("fallback", 1, ["已提交关键词的完整对白"])
        dialogues.sync_comic_dialogues("local", "fallback", sync_vectors=False)
        original_connection = dialogues.get_dialogue_db
        calls = 0

        def fail_status_write():
            nonlocal calls
            calls += 1
            if calls > 1:
                raise sqlite3.OperationalError("模拟状态写锁繁忙")
            return original_connection()

        with (
            mock.patch.object(dialogues, "get_dialogue_db", side_effect=fail_status_write),
            mock.patch.object(dialogues, "embed_comic_dialogues", side_effect=RuntimeError("模拟编码失败")),
        ):
            dialogues._sync_dialogue_vectors("local", "fallback", "source", strict=False)
        self.assertEqual("已提交关键词的完整对白", self.records()[0][1])

    def test_page_mutations_and_sync_commit_share_a_reentrant_lock(self):
        import threading
        from concurrent.futures import ThreadPoolExecutor

        from app.storage import ComicStore

        store = ComicStore(self.data / "library")
        entered = threading.Event()

        def index_commit():
            with assets.comic_asset_lock(self.data / "library", "local", "locked"):
                entered.set()

        with ThreadPoolExecutor(max_workers=1) as pool:
            with store._lock_for("local", "locked"), store._lock_for("local", "locked"):
                task = pool.submit(index_commit)
                self.assertFalse(entered.wait(0.1))
            task.result(timeout=2)
        self.assertTrue(entered.is_set())


if __name__ == "__main__":
    unittest.main()
