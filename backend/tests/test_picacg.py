from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.models import Chapter, FetchedComic, RemotePage
from app.providers.picacg import (
    PicacgProvider,
    _apply_pacing,
    _validate_download_host,
    calc_signature,
    is_valid_image,
    sanitize_proxy_url,
)
from app.providers.registry import get_provider


class TestPicacgProvider(unittest.TestCase):
    def setUp(self) -> None:
        self.provider = PicacgProvider()
        if hasattr(self.provider._tls, "session"):
            delattr(self.provider._tls, "session")
        self.patch_down_pacing = patch("app.providers.picacg.PICA_DOWNLOAD_PACING_MS", 0)
        self.patch_api_pacing = patch("app.providers.picacg.PICA_API_PACING_MS", 0)
        self.patch_down_pacing.start()
        self.patch_api_pacing.start()
        self.addCleanup(self.patch_down_pacing.stop)
        self.addCleanup(self.patch_api_pacing.stop)

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
        with self.assertRaises(ValueError):
            self.provider.normalize_id("5ebe89bf63918511c2c362a78")  # 25 chars (must reject, not truncate)
        with self.assertRaises(ValueError):
            self.provider.normalize_id("5ebe89bf63918511c2c362a75ebe89bf")  # 32 chars MD5 (must reject)

    def test_calc_signature(self) -> None:
        path = "comics/5ebe89bf63918511c2c362a7"
        nonce = "d41d8cd98f00b204e9800998ecf8427e"
        time_str = "1700000000"
        method = "GET"

        sig = calc_signature(path, nonce, time_str, method)
        self.assertTrue(isinstance(sig, str))
        self.assertEqual(len(sig), 64)  # SHA-256 hex digest length

        # Path with query params should be preserved in HMAC hash (Ref: wgh136/PicaComic)
        sig_query = calc_signature(f"{path}?page=1&limit=20", nonce, time_str, method)
        self.assertNotEqual(sig, sig_query)

    def test_format_count_and_date(self) -> None:
        from app.providers.picacg import format_count, format_date

        self.assertEqual(format_count(3389119), "3.4M")
        self.assertEqual(format_count("77951"), "78k")
        self.assertEqual(format_count(1200), "1.2k")
        self.assertEqual(format_count(950), "950")
        self.assertEqual(format_count(0), "0")
        self.assertEqual(format_count(""), "")

        self.assertEqual(format_date("2020-05-14T17:41:13.983Z"), "2020-05-14")
        self.assertEqual(format_date("2024-05-18"), "2024-05-18")
        self.assertEqual(format_date(""), "")

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
                            "created_at": "2026-08-15T00:00:00.000Z",
                            "updated_at": "2026-09-01T00:00:00.000Z",
                            "likesCount": 999,
                            "viewsCount": 8888,
                            "thumb": {
                                "fileServer": "https://storage1.bwaa.co",
                                "path": "comics/thumb.jpg",
                            },
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
        self.assertEqual(meta.cover_count, 3)
        self.assertEqual(meta.cover_indices, [1, 1, 2])
        self.assertEqual(meta.published_at, "2026-08-15")
        self.assertEqual(meta.updated_at, "2026-09-01")
        self.assertEqual(meta.views, "8.9k")
        self.assertEqual(meta.likes, "999")

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

        # 4. Incremental fetch test: pass existing=fetched
        # Should reuse chapters 1 and 2 without making any order/{order}/pages requests
        mock_request.reset_mock()
        fetched_incremental = self.provider.fetch(
            "https://picawang.com/comic/5ebe89bf63918511c2c362a7",
            existing=fetched,
        )
        self.assertEqual(len(fetched_incremental.remote_pages), 3)
        self.assertEqual(len(fetched_incremental.meta.chapters), 2)
        # Should only have called GET comics/id and GET comics/id/eps (total 2 requests)
        self.assertEqual(mock_request.call_count, 2)
        called_endpoints = [call[0][1] for call in mock_request.call_args_list]
        self.assertIn("comics/5ebe89bf63918511c2c362a7", called_endpoints)
        self.assertIn("comics/5ebe89bf63918511c2c362a7/eps", called_endpoints)
        for ep in called_endpoints:
            self.assertNotIn("pages", ep)

    @patch("app.providers.picacg.curl_requests.Session")
    def test_download_page_cdn_failover(self, mock_session_cls: MagicMock) -> None:
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        # 1st request (storage1.bwaa.co) fails with 502 Bad Gateway
        resp_fail = MagicMock()
        resp_fail.status_code = 502
        resp_fail.content = b""

        # 2nd request (fallback CDN e.g. storage.wikawika.xyz) succeeds with valid WebP
        valid_webp = b"RIFF\x00\x01\x00\x00WEBPVP8 " + (b"\x00" * 200)
        resp_success = MagicMock()
        resp_success.status_code = 200
        resp_success.content = valid_webp

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
        self.assertEqual(content, valid_webp)
        self.assertGreaterEqual(mock_session.get.call_count, 2)

    @patch("app.providers.picacg.curl_requests.Session")
    def test_download_cover(self, mock_session_cls: MagicMock) -> None:
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        valid_jpeg = b"\xff\xd8\xff\xe0" + (b"\x00" * 200)
        resp_success = MagicMock()
        resp_success.status_code = 200
        resp_success.content = valid_jpeg
        mock_session.get.return_value = resp_success

        fake_comic = MagicMock()
        fake_comic.meta.raw = {
            "thumb": {
                "fileServer": "https://storage1.bwaa.co",
                "path": "comics/thumb.jpg",
            }
        }

        cover = self.provider.download_cover(fake_comic)
        self.assertEqual(cover, valid_jpeg)

        # Without thumb object in raw, should return None
        fake_empty_comic = MagicMock()
        fake_empty_comic.meta.raw = {}
        self.assertIsNone(self.provider.download_cover(fake_empty_comic))

    def test_download_page_ssrf_and_host_validation(self) -> None:
        # 1. Localhost and private IPs must be rejected
        with self.assertRaises(ValueError):
            _validate_download_host("localhost")
        with self.assertRaises(ValueError):
            _validate_download_host("127.0.0.1")
        with self.assertRaises(ValueError):
            _validate_download_host("0.0.0.0")
        with self.assertRaises(ValueError):
            _validate_download_host("192.168.1.1")
        with self.assertRaises(ValueError):
            _validate_download_host("10.0.0.1")
        with self.assertRaises(ValueError):
            _validate_download_host("169.254.169.254")

        # 2. Direct public IPs must also be rejected
        with self.assertRaises(ValueError):
            _validate_download_host("1.1.1.1")

        # 3. DNS rebinding domains and internal suffixes must be rejected
        with self.assertRaises(ValueError):
            _validate_download_host("127.0.0.1.nip.io")
        with self.assertRaises(ValueError):
            _validate_download_host("localtest.me")
        with self.assertRaises(ValueError):
            _validate_download_host("router.lan")
        with self.assertRaises(ValueError):
            _validate_download_host("server.local")
        with self.assertRaises(ValueError):
            _validate_download_host("service.internal")

        # 4. Unknown external domains must be rejected
        with self.assertRaises(ValueError):
            _validate_download_host("evil-attacker.com")

        # 5. Legitimate PicAcg CDNs must pass
        _validate_download_host("storage1.bwaa.co")
        _validate_download_host("storage.wikawika.xyz")
        _validate_download_host("s3.bwaa.co")
        _validate_download_host("img.picacomic.com")

        # 6. Custom extra CDN hosts via PICA_EXTRA_CDN_HOSTS must pass
        with patch("app.providers.picacg.PICA_EXTRA_CDN_HOSTS", ["custom-mirror.myhomelab.org"]):
            _validate_download_host("custom-mirror.myhomelab.org")

    def test_is_valid_image(self) -> None:
        # Valid magic headers
        self.assertTrue(is_valid_image(b"\xff\xd8\xff\xe0" + (b"\x00" * 30)))  # JPEG
        self.assertTrue(is_valid_image(b"\x89PNG\r\n\x1a\n" + (b"\x00" * 30)))  # PNG
        self.assertTrue(is_valid_image(b"RIFF\x20\x00\x00\x00WEBPVP8 " + (b"\x00" * 20)))  # WebP
        self.assertTrue(is_valid_image(b"GIF89a" + (b"\x00" * 20)))  # GIF
        self.assertTrue(is_valid_image(b"\x00\x00\x00\x1cftypavif" + (b"\x00" * 20)))  # AVIF

        # Invalid / non-image payloads
        self.assertFalse(is_valid_image(b"<!DOCTYPE html><html><body>Error</body></html>"))
        self.assertFalse(is_valid_image(b'{"code": 403, "message": "Cloudflare blocked"}'))
        self.assertFalse(is_valid_image(b"short"))
        self.assertFalse(is_valid_image(b""))

    def test_sanitize_proxy_url(self) -> None:
        # Proxy URLs with credentials must be masked
        msg = "Failed to connect to http://miku:secret123@192.168.1.1:7890/test"
        sanitized = sanitize_proxy_url(msg)
        self.assertNotIn("secret123", sanitized)
        self.assertIn("http://miku:***@192.168.1.1:7890/test", sanitized)

        socks_msg = "Error socks5://admin:p%40ssword@proxy.domain.com:1080"
        self.assertNotIn("p%40ssword", sanitize_proxy_url(socks_msg))

        # Messages without credentials should remain unchanged
        plain_msg = "Connection refused to http://127.0.0.1:7890"
        self.assertEqual(sanitize_proxy_url(plain_msg), plain_msg)

    @patch("app.providers.picacg.PICA_EMAIL", "new_user@example.com")
    def test_load_cached_token_email_mismatch(self) -> None:
        # If cache was saved for old_user@example.com, it should not be used
        mock_file = MagicMock()
        mock_file.exists.return_value = True
        mock_file.read_text.return_value = '{"token": "old_jwt", "email": "old_user@example.com", "time": 9999999999}'
        with patch.object(self.provider, "_session_file", mock_file):
            token = self.provider._load_cached_token()
            self.assertIsNone(token)

    @patch("app.providers.picacg.time.sleep")
    def test_apply_pacing(self, mock_sleep: MagicMock) -> None:
        # 0 ms must not trigger sleep
        _apply_pacing(0)
        mock_sleep.assert_not_called()

        # > 0 ms must trigger sleep within +/-20% jitter bounds
        _apply_pacing(250)
        mock_sleep.assert_called_once()
        slept = mock_sleep.call_args[0][0]
        self.assertGreaterEqual(slept, 0.20)
        self.assertLessEqual(slept, 0.30)

    @patch("app.routers.library.store.load_fetched")
    @patch("app.routers.library.get_provider")
    @patch("app.routers.library.store.save_fetched")
    @patch("app.routers.library.start_job")
    def test_import_self_healing_zero_pages(
        self,
        mock_job: MagicMock,
        mock_save: MagicMock,
        mock_get_prov: MagicMock,
        mock_load: MagicMock,
    ) -> None:
        from app.routers.library import import_comic
        from app.models import ComicMeta, FetchedComic, ImportRequest

        # 1. Simulate cached comic has page_count == 0 (historical broken record)
        broken_meta = ComicMeta(
            source="picacg",
            source_id="5ebe89bf63918511c2c362a7",
            display_id="PICA_5ebe89bf63918511c2c362a7",
            title="损坏记录",
            page_count=0,
        )
        broken_comic = FetchedComic(meta=broken_meta, remote_pages=[])
        mock_load.return_value = broken_comic

        # 2. Mock fresh fetch
        fresh_meta = ComicMeta(
            source="picacg",
            source_id="5ebe89bf63918511c2c362a7",
            display_id="PICA_5ebe89bf63918511c2c362a7",
            title="测试自愈",
            page_count=1260,
        )
        fresh_comic = FetchedComic(meta=fresh_meta, remote_pages=[])
        mock_prov = MagicMock()
        mock_prov.normalize_id.return_value = "5ebe89bf63918511c2c362a7"
        mock_prov.fetch.return_value = fresh_comic
        mock_get_prov.return_value = mock_prov
        mock_save.return_value = fresh_meta

        req = ImportRequest(source="picacg", id="5ebe89bf63918511c2c362a7", refresh=False)
        result = import_comic(req)

        # Must not return from cache; must call provider.fetch with existing=None
        self.assertFalse(result.from_cache)
        self.assertEqual(result.meta.page_count, 1260)
        mock_prov.fetch.assert_called_once_with("5ebe89bf63918511c2c362a7", existing=None)

    def test_resolve_cover_page_index(self) -> None:
        from app.models import ComicMeta
        from app.storage import ComicStore

        # With dual-source cover_indices (Cover 1 is thumb -> page 1 fallback, Cover 2..4 -> page 1..3)
        meta = ComicMeta(
            source="picacg",
            source_id="abc",
            display_id="PICA_abc",
            title="Test",
            page_count=10,
            cover_count=4,
            cover_indices=[1, 1, 2, 3],
        )
        self.assertEqual(ComicStore._resolve_cover_page_index(meta, 1), 1)
        self.assertEqual(ComicStore._resolve_cover_page_index(meta, 2), 1)
        self.assertEqual(ComicStore._resolve_cover_page_index(meta, 3), 2)
        self.assertEqual(ComicStore._resolve_cover_page_index(meta, 4), 3)
        # Out of bounds index falls back to index clamped to page_count
        self.assertEqual(ComicStore._resolve_cover_page_index(meta, 5), 5)
        self.assertEqual(ComicStore._resolve_cover_page_index(meta, 15), 10)

        # Standard generic comic without cover_indices
        meta_generic = ComicMeta(
            source="jm",
            source_id="123",
            display_id="JM123",
            title="Test",
            page_count=20,
        )
        self.assertEqual(ComicStore._resolve_cover_page_index(meta_generic, 1), 1)
        self.assertEqual(ComicStore._resolve_cover_page_index(meta_generic, 2), 2)
        self.assertEqual(ComicStore._resolve_cover_page_index(meta_generic, 3), 3)


if __name__ == "__main__":
    unittest.main()
