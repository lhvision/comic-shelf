from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from app.models import Chapter, FetchedComic, RemotePage
from app.providers.picacg import PicacgProvider, calc_signature
from app.providers.registry import get_provider


class TestPicacgProvider(unittest.TestCase):
    def setUp(self) -> None:
        self.provider = PicacgProvider()

    def test_normalize_id(self) -> None:
        valid_id = "5ebe89bf63918511c2c362a7"

        # 1. Pure hex id
        self.assertEqual(self.provider.normalize_id("5ebe89bf63918511c2c362a7"), valid_id)
        self.assertEqual(self.provider.normalize_id("  5EBE89BF63918511C2C362A7  "), valid_id)

        # 2. Pica prefixes
        self.assertEqual(self.provider.normalize_id("pica:5ebe89bf63918511c2c362a7"), valid_id)
        self.assertEqual(self.provider.normalize_id("PICA5ebe89bf63918511c2c362a7"), valid_id)

        # 3. User web mirror URLs
        self.assertEqual(
            self.provider.normalize_id("https://picawang.com/comic/5ebe89bf63918511c2c362a7"),
            valid_id,
        )
        self.assertEqual(
            self.provider.normalize_id("https://manhuabika.com/comic/5ebe89bf63918511c2c362a7/"),
            valid_id,
        )
        self.assertEqual(
            self.provider.normalize_id("https://www.picacomic.com/comic/5ebe89bf63918511c2c362a7?page=2"),
            valid_id,
        )
        self.assertEqual(
            self.provider.normalize_id("https://i.bikaios.xyz/comic/5ebe89bf63918511c2c362a7"),
            valid_id,
        )

        # 4. Invalid input rejection
        with self.assertRaises(ValueError):
            self.provider.normalize_id("invalid-id-123")
        with self.assertRaises(ValueError):
            self.provider.normalize_id("https://example.com/not-a-comic")
        with self.assertRaises(ValueError):
            self.provider.normalize_id("5ebe89bf63918511c2c362a")  # 23 chars only

    def test_calc_signature(self) -> None:
        path = "comics/5ebe89bf63918511c2c362a7"
        nonce = "d41d8cd98f00b204e9800998ecf8427e"
        time_str = "1700000000"
        method = "GET"

        sig = calc_signature(path, nonce, time_str, method)
        self.assertTrue(isinstance(sig, str))
        self.assertEqual(len(sig), 64)  # SHA-256 hex digest length

        # Path with query params should be stripped
        sig_query = calc_signature(f"{path}?page=1&limit=20", nonce, time_str, method)
        self.assertEqual(sig, sig_query)

    def test_registry_integration(self) -> None:
        provider = get_provider("picacg")
        self.assertIsInstance(provider, PicacgProvider)
        self.assertEqual(provider.key, "picacg")
        self.assertEqual(provider.short_label, "哔咔")

        desc = provider.describe()
        self.assertEqual(desc["key"], "picacg")
        self.assertIn("5ebe89bf63918511c2c362a7", desc["example"])

    @patch.object(PicacgProvider, "ensure_token", return_value="mock_jwt_token")
    @patch.object(PicacgProvider, "_request")
    def test_fetch_comic_multi_chapter(self, mock_request: MagicMock, mock_token: MagicMock) -> None:
        # Mock responses for:
        # 1. GET comics/5ebe... -> comic detail
        # 2. GET comics/5ebe.../eps?page=1 -> 2 episodes
        # 3. GET comics/5ebe.../order/1/pages?page=1 -> 2 pages
        # 4. GET comics/5ebe.../order/2/pages?page=1 -> 1 page
        def mock_side_effect(method: str, endpoint: str, params: dict | None = None, **kwargs: object) -> dict:
            if endpoint == "comics/5ebe89bf63918511c2c362a7":
                return {
                    "code": 200,
                    "data": {
                        "comic": {
                            "_id": "5ebe89bf63918511c2c362a7",
                            "title": "测试哔咔本子",
                            "author": "测试作者",
                            "chineseTeam": "测试汉化组",
                            "categories": ["同人志"],
                            "tags": ["纯爱", "学妹"],
                            "description": "这是描述",
                            "pagesCount": 3,
                            "epsCount": 2,
                            "updated_at": "2026-09-01T00:00:00.000Z",
                            "likesCount": 999,
                            "viewsCount": 8888,
                        }
                    },
                }
            elif endpoint == "comics/5ebe89bf63918511c2c362a7/eps":
                return {
                    "code": 200,
                    "data": {
                        "eps": {
                            "docs": [
                                {"_id": "ep1", "order": 1, "title": "第 1 話"},
                                {"_id": "ep2", "order": 2, "title": "第 2 話"},
                            ],
                            "total": 2,
                            "pages": 1,
                        }
                    },
                }
            elif endpoint == "comics/5ebe89bf63918511c2c362a7/order/1/pages":
                return {
                    "code": 200,
                    "data": {
                        "pages": {
                            "docs": [
                                {
                                    "_id": "p1",
                                    "media": {"fileServer": "https://storage1.bwaa.co", "path": "comics/001.webp"},
                                },
                                {
                                    "_id": "p2",
                                    "media": {"fileServer": "https://storage1.bwaa.co", "path": "comics/002.webp"},
                                },
                            ],
                            "total": 2,
                            "pages": 1,
                        }
                    },
                }
            elif endpoint == "comics/5ebe89bf63918511c2c362a7/order/2/pages":
                return {
                    "code": 200,
                    "data": {
                        "pages": {
                            "docs": [
                                {
                                    "_id": "p3",
                                    "media": {"fileServer": "https://storage1.bwaa.co", "path": "comics/003.webp"},
                                },
                            ],
                            "total": 1,
                            "pages": 1,
                        }
                    },
                }
            raise ValueError(f"Unhandled endpoint {endpoint}")

        mock_request.side_effect = mock_side_effect

        fetched = self.provider.fetch("https://picawang.com/comic/5ebe89bf63918511c2c362a7")

        self.assertIsInstance(fetched, FetchedComic)
        meta = fetched.meta
        self.assertEqual(meta.source, "picacg")
        self.assertEqual(meta.source_id, "5ebe89bf63918511c2c362a7")
        self.assertEqual(meta.title, "测试哔咔本子")
        self.assertEqual(meta.authors, ["测试作者"])
        self.assertEqual(meta.uploader, "测试汉化组")
        self.assertIn("同人志", meta.tags)
        self.assertIn("纯爱", meta.tags)
        self.assertEqual(meta.page_count, 3)

        # Verify multi-chapter structure
        self.assertTrue(meta.is_multi_chapter)
        self.assertEqual(len(meta.chapters), 2)
        self.assertEqual(meta.chapters[0].title, "第 1 話")
        self.assertEqual(meta.chapters[0].start, 1)
        self.assertEqual(meta.chapters[0].page_count, 2)
        self.assertEqual(meta.chapters[1].title, "第 2 話")
        self.assertEqual(meta.chapters[1].start, 3)
        self.assertEqual(meta.chapters[1].page_count, 1)

        # Verify remote pages
        self.assertEqual(len(fetched.remote_pages), 3)
        self.assertEqual(fetched.remote_pages[0].url, "https://storage1.bwaa.co/static/comics/001.webp")
        self.assertEqual(fetched.remote_pages[0].index, 1)
        self.assertEqual(fetched.remote_pages[0].chapter, "1")
        self.assertEqual(fetched.remote_pages[2].index, 3)
        self.assertEqual(fetched.remote_pages[2].chapter, "2")

    @patch("app.providers.picacg.curl_requests.Session")
    def test_download_page_cdn_failover(self, mock_session_cls: MagicMock) -> None:
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        # 1st request (storage1.bwaa.co) fails with 502 Bad Gateway
        resp_fail = MagicMock()
        resp_fail.status_code = 502
        resp_fail.content = b""

        # 2nd request (fallback CDN e.g. storage.wikawika.xyz) succeeds with 200
        resp_success = MagicMock()
        resp_success.status_code = 200
        resp_success.content = b"FAKEMOCKWEBPIMAGEBYTES"

        mock_session.get.side_effect = [resp_fail, resp_success]

        page = RemotePage(
            index=1,
            url="https://storage1.bwaa.co/static/comics/001.webp",
            file="00001.webp",
            ext="webp",
            chapter="1",
        )
        fake_comic = MagicMock()

        content = self.provider.download_page(fake_comic, page)
        self.assertEqual(content, b"FAKEMOCKWEBPIMAGEBYTES")
        self.assertGreaterEqual(mock_session.get.call_count, 2)


if __name__ == "__main__":
    unittest.main()
