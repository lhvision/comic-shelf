"""HTTP 搜索限频、忙碌快速拒绝、异常归还槽位及状态权限，使用假时间和请求。"""

from __future__ import annotations

import threading
import unittest
from collections import OrderedDict
from unittest import mock

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.ocr import search_limits
from app.routers import search
from tests.test_dialogue_fts import make_mock_request


class TestSearchLimits(unittest.TestCase):
    def setUp(self):
        self.patches = (
            mock.patch.object(search_limits, "_BUCKETS", OrderedDict()),
            mock.patch.object(search_limits, "_SEMANTIC_SLOTS", threading.BoundedSemaphore(1)),
            mock.patch.object(search_limits, "_KEYWORD_SLOTS", threading.BoundedSemaphore(4)),
            mock.patch.object(search_limits, "get_client_ip", return_value="fixture-ip"),
        )
        for patch in self.patches:
            patch.start()

    def tearDown(self):
        for patch in reversed(self.patches):
            patch.stop()

    def test_separate_rate_budgets_refill_with_monotonic_time(self):
        request = make_mock_request()
        with mock.patch("time.monotonic", return_value=10):
            for _ in range(3):
                with search_limits.dialogue_search_slot(request, semantic=True):
                    pass
            with self.assertRaises(HTTPException) as error:
                with search_limits.dialogue_search_slot(request, semantic=True):
                    self.fail("超预算不得进入搜索")
            self.assertEqual(429, error.exception.status_code)
            self.assertEqual("1", error.exception.headers["Retry-After"])
            with search_limits.dialogue_search_slot(request):
                pass
        with mock.patch("time.monotonic", return_value=11):
            with search_limits.dialogue_search_slot(request, semantic=True):
                pass

    def test_busy_search_rejects_without_waiting_and_releases_after_failure(self):
        request = make_mock_request()
        with search_limits.dialogue_search_slot(request, semantic=True):
            with self.assertRaises(HTTPException):
                with search_limits.dialogue_search_slot(request, semantic=True):
                    self.fail("并发满不得进入搜索")
        with self.assertRaisesRegex(RuntimeError, "模拟搜索失败"):
            with search_limits.dialogue_search_slot(request, semantic=True):
                raise RuntimeError("模拟搜索失败")
        with search_limits.dialogue_search_slot(request, semantic=True):
            pass

    def test_idle_records_expire_and_total_is_bounded(self):
        request = make_mock_request()
        with mock.patch.object(search_limits, "_MAX_BUCKETS", 2), mock.patch("time.monotonic", return_value=10):
            for ip in ("ip-a", "ip-b", "ip-c"):
                with (
                    mock.patch.object(search_limits, "get_client_ip", return_value=ip),
                    search_limits.dialogue_search_slot(request),
                ):
                    pass
            self.assertEqual(2, len(search_limits._BUCKETS))
        with mock.patch("time.monotonic", return_value=311), search_limits.dialogue_search_slot(request):
            pass
        self.assertEqual(1, len(search_limits._BUCKETS))

    def test_http_limit_is_enforced_before_query_and_retains_no_store(self):
        from app.main import app

        with (
            TestClient(app) as client,
            mock.patch.object(search, "can_read", return_value=True),
            mock.patch.object(
                search, "search_dialogues_semantic", return_value={"results": [], "available": True, "reason": ""}
            ) as query,
        ):
            with search_limits.dialogue_search_slot(make_mock_request(), semantic=True):
                result = client.get("/api/search/dialogue-semantic", params={"q": "测试"})
            self.assertEqual(429, result.status_code)
            self.assertEqual("1", result.headers["retry-after"])
            self.assertEqual("no-store", result.headers["cache-control"])
            query.assert_not_called()

    def test_status_requires_curator_and_does_not_leak_counts_in_guest_search(self):
        from app.main import app

        with (
            TestClient(app) as client,
            mock.patch.object(search, "require_curator", side_effect=HTTPException(403, "fixture denied")),
            mock.patch.object(search, "dialogue_vector_status") as status,
        ):
            result = client.get("/api/search/dialogue-vectors/status")
            self.assertEqual(403, result.status_code)
            status.assert_not_called()
        with (
            mock.patch.object(search, "can_read", return_value=True),
            mock.patch.object(
                search, "search_dialogues_semantic", return_value={"results": [], "available": True, "reason": ""}
            ),
        ):
            result = search.search_dialogue_semantic_endpoint(make_mock_request(), q="测试", source=None, limit=20)
            self.assertNotIn("pending_comics", result.model_dump())


if __name__ == "__main__":
    unittest.main()
