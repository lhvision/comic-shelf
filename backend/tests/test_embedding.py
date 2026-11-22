"""模型文件缺失、指纹读取失败与恢复的回归测试；推理依赖使用假会话。"""

from __future__ import annotations

import json
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np

from app import embedding
from app.db import connection, dialogues, schema


class TestEmbeddingAvailability(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.data = Path(directory.name)
        self.model = self.data / "model.onnx"
        self.tokenizer = self.data / "tokenizer.json"
        self.model.write_bytes(b"model")
        self.tokenizer.write_bytes(b"tokenizer")
        self.addCleanup(connection.set_data_dir, connection.get_data_dir())
        self.addCleanup(connection.set_dialogue_db_path, connection.get_dialogue_db_path())
        connection.set_data_dir(self.data)
        schema.init_dialogue_db(self.data / "dialogues.db")
        state = mock.patch.multiple(
            embedding,
            _MODEL_PATH=self.model,
            _TOKENIZER_PATH=self.tokenizer,
            _STATE=None,
            _FAILED_SIGNATURE="",
            _SIGNATURE_CACHE=None,
        )
        state.start()
        self.addCleanup(state.stop)

    def loaded_model(self, session=None, tokenizer=None):
        state = embedding._EncoderState(
            session if session is not None else object(),
            tokenizer if tokenizer is not None else object(),
            2,
            embedding.model_signature(),
        )
        embedding._STATE = state
        return state

    def test_removed_model_clears_loaded_state_and_reports_unavailable(self):
        self.loaded_model()
        self.model.unlink()
        self.assertIsNone(embedding.dim())
        self.assertIsNone(embedding.encode_query("再次见面"))
        self.assertIsNone(embedding._STATE)
        self.assertEqual("encoder_unavailable", dialogues.dialogue_vector_status()["reason"])

    def test_removed_tokenizer_disables_loaded_model(self):
        self.loaded_model()
        self.tokenizer.unlink()
        self.assertIsNone(embedding.dim())
        self.assertIsNone(embedding.encode_documents(["再次见面"]))

    def test_fingerprint_stat_race_degrades_to_unavailable(self):
        self.loaded_model()
        with (
            mock.patch.object(embedding, "model_present", return_value=True),
            mock.patch.object(Path, "stat", side_effect=FileNotFoundError("模型刚被移走")),
            self.assertLogs(embedding.logger, level="WARNING"),
        ):
            self.assertEqual("", embedding.model_signature())
            self.assertIsNone(embedding.dim())

    def test_unreadable_model_keeps_non_strict_keyword_sync_available(self):
        self.loaded_model()
        self.model.write_bytes(b"changed-model")
        page = self.data / "library/local/book/pages/00001.ocr.json"
        page.parent.mkdir(parents=True)
        page.write_text(json.dumps({"bubbles": [{"id": 1, "text": "我们明天再见面"}]}))
        original_open = Path.open

        def denied_model_open(path, *args, **kwargs):
            if path == self.model:
                raise PermissionError("模型不可读")
            return original_open(path, *args, **kwargs)

        with (
            mock.patch.object(Path, "open", denied_model_open),
            self.assertLogs(embedding.logger, level="WARNING"),
        ):
            self.assertEqual("", embedding.model_signature())
            for strict in (False, True):
                self.assertEqual(1, dialogues.sync_comic_dialogues("local", "book", strict_vectors=strict))
            self.assertEqual("encoder_unavailable", dialogues.dialogue_vector_status()["reason"])
        self.assertTrue(dialogues.search_dialogues("见面"))
        with connection.get_dialogue_db() as conn:
            self.assertEqual(0, conn.execute("SELECT count(*) FROM comic_dialogue_vectors").fetchone()[0])

    def test_restored_model_can_initialize_after_disappearing(self):
        self.loaded_model()
        self.model.unlink()
        self.assertIsNone(embedding.dim())
        self.model.write_bytes(b"restored-model")
        session = mock.Mock()
        session.run.return_value = [np.zeros((1, 1, 3), dtype=np.float32)]
        tokenizer = mock.Mock()
        tokenizer_type = mock.Mock()
        tokenizer_type.from_file.return_value = tokenizer
        with (
            mock.patch.dict(
                "sys.modules",
                {
                    "onnxruntime": SimpleNamespace(InferenceSession=mock.Mock(return_value=session)),
                    "tokenizers": SimpleNamespace(Tokenizer=tokenizer_type),
                },
            ),
            mock.patch.object(embedding, "_feed", return_value={}),
        ):
            self.assertEqual(3, embedding.dim())
        self.assertIs(session, embedding._STATE.session)
        self.assertIs(tokenizer, embedding._STATE.tokenizer)

    def test_inflight_documents_keep_original_model_dimension(self):
        session = mock.Mock()
        session.run.return_value = [np.array([[[1.0, 0.0]]], dtype=np.float32)]
        state = self.loaded_model(session, mock.Mock())
        original_load = embedding._load
        captured = threading.Event()
        resume = threading.Event()

        def pause_after_load():
            snapshot = original_load()
            captured.set()
            if not resume.wait(2):
                raise TimeoutError("编码任务未恢复")
            return snapshot

        replacement_session = mock.Mock()
        replacement_session.run.return_value = [np.zeros((1, 1, 3), dtype=np.float32)]
        with (
            mock.patch.object(embedding, "_load", side_effect=pause_after_load),
            mock.patch.object(embedding, "_feed", return_value={}),
            mock.patch.dict(
                "sys.modules",
                {
                    "onnxruntime": SimpleNamespace(InferenceSession=lambda *args, **kwargs: replacement_session),
                    "tokenizers": SimpleNamespace(Tokenizer=SimpleNamespace(from_file=lambda path: mock.Mock())),
                },
            ),
            ThreadPoolExecutor(max_workers=1) as pool,
        ):
            task = pool.submit(embedding.encode_documents, ["再次见面"], expected_signature=state.signature)
            try:
                self.assertTrue(captured.wait(2))
                self.model.write_bytes(b"replacement-model")
                self.assertEqual(3, original_load().dim)
            finally:
                resume.set()
            result = task.result(timeout=2)
        self.assertEqual((1, 2), result.shape)
        np.testing.assert_array_equal(result, [[1, 0]])

    def test_encoding_rejects_different_expected_model_before_inference(self):
        session = mock.Mock()
        self.loaded_model(session, mock.Mock())
        self.assertIsNone(embedding.encode_documents(["再次见面"], expected_signature="another-model"))
        self.assertIsNone(embedding.encode_query("再次见面", expected_signature="another-model"))
        session.run.assert_not_called()

    def test_model_change_during_initialization_is_not_published(self):
        session = mock.Mock()

        def replace_during_probe(*args):
            self.model.write_bytes(b"replacement-model")
            return [np.zeros((1, 1, 3), dtype=np.float32)]

        session.run.side_effect = replace_during_probe
        with (
            mock.patch.dict(
                "sys.modules",
                {
                    "onnxruntime": SimpleNamespace(InferenceSession=lambda *args, **kwargs: session),
                    "tokenizers": SimpleNamespace(Tokenizer=SimpleNamespace(from_file=lambda path: mock.Mock())),
                },
            ),
            mock.patch.object(embedding, "_feed", return_value={}),
        ):
            with self.assertLogs(embedding.logger, level="WARNING"):
                self.assertIsNone(embedding.dim())
            self.assertIsNone(embedding._STATE)
            session.run.side_effect = None
            session.run.return_value = [np.zeros((1, 1, 3), dtype=np.float32)]
            self.assertEqual(3, embedding.dim())


if __name__ == "__main__":
    unittest.main()
