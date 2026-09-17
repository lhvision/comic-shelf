from __future__ import annotations

import json
import sys
import tempfile
import time
import unittest
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.models import ComicMeta, FetchedComic, RemotePage
from app.providers.jm import JMProvider, _is_safe_remote_domain, _mask_sensitive


class TestJMProvider(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp_dir.name)
        self.provider = JMProvider()
        self.provider._domain_cache_file = self.tmp_path / "jm_html_domain.json"
        self.provider._session_cache_file = self.tmp_path / "jm_session.json"
        if hasattr(self.provider._tls, "session"):
            delattr(self.provider._tls, "session")

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_normalize_id(self) -> None:
        self.assertEqual(self.provider.normalize_id("523607"), "523607")
        self.assertEqual(self.provider.normalize_id("JM523607"), "523607")
        self.assertEqual(self.provider.normalize_id("  jm523607  "), "523607")
        self.assertEqual(self.provider.normalize_id("JM12345678"), "12345678")

        with self.assertRaises(ValueError):
            self.provider.normalize_id("1234")  # too short
        with self.assertRaises(ValueError):
            self.provider.normalize_id("JM1234567890")  # too long
        with self.assertRaises(ValueError):
            self.provider.normalize_id("abc523607")  # invalid prefix

    def test_safe_remote_domain_ssrf_protection(self) -> None:
        # Legitimate public domains
        self.assertTrue(_is_safe_remote_domain("18comic.vip"))
        self.assertTrue(_is_safe_remote_domain("cdn-msp.jmapiproxy1.cc"))
        self.assertTrue(_is_safe_remote_domain("jmcomic.me"))
        self.assertTrue(_is_safe_remote_domain("img.example.com"))

        # SSRF: loopback, link-local, private LAN, cloud metadata
        self.assertFalse(_is_safe_remote_domain("127.0.0.1"))
        self.assertFalse(_is_safe_remote_domain("127.0.0.1:8080"))
        self.assertFalse(_is_safe_remote_domain("10.0.0.1"))
        self.assertFalse(_is_safe_remote_domain("172.16.0.1"))
        self.assertFalse(_is_safe_remote_domain("192.168.1.1:80"))
        self.assertFalse(_is_safe_remote_domain("169.254.169.254"))
        self.assertFalse(_is_safe_remote_domain("::1"))
        self.assertFalse(_is_safe_remote_domain("[::1]:8080"))
        self.assertFalse(_is_safe_remote_domain("fe80::1"))

        # SSRF: octal / hex / obfuscated IP representations
        self.assertFalse(_is_safe_remote_domain("0177.0.0.1"))

        # SSRF: URI components, userinfo credentials, path traversal tokens (including post-colon)
        self.assertFalse(_is_safe_remote_domain("attacker.com@127.0.0.1"))
        self.assertFalse(_is_safe_remote_domain("trusted.com:80@127.0.0.1"))
        self.assertFalse(_is_safe_remote_domain("trusted.com:80/evil"))
        self.assertFalse(_is_safe_remote_domain("trusted.com:80?query"))
        self.assertFalse(_is_safe_remote_domain("trusted.com:80#hash"))
        self.assertFalse(_is_safe_remote_domain("trusted.com:80%2f"))
        self.assertFalse(_is_safe_remote_domain("foo.com/bar"))
        self.assertFalse(_is_safe_remote_domain("foo.com?bar"))
        self.assertFalse(_is_safe_remote_domain("foo.com#bar"))

        # SSRF: internal / unresolvable top-level domains & blacklisted hostnames
        self.assertFalse(_is_safe_remote_domain("localhost"))
        self.assertFalse(_is_safe_remote_domain("broadcasthost"))
        self.assertFalse(_is_safe_remote_domain("jm-88.cc"))  # parked advertising domain
        self.assertFalse(_is_safe_remote_domain("gateway.lan"))
        self.assertFalse(_is_safe_remote_domain("printer.local"))
        self.assertFalse(_is_safe_remote_domain("service.internal"))
        self.assertFalse(_is_safe_remote_domain("test.invalid"))
        self.assertFalse(_is_safe_remote_domain("nas.home.arpa"))

        # Malformed / empty / single-token
        self.assertFalse(_is_safe_remote_domain(""))
        self.assertFalse(_is_safe_remote_domain("   "))
        self.assertFalse(_is_safe_remote_domain("internalhost"))
        self.assertFalse(_is_safe_remote_domain("a" * 255))

    def test_mask_sensitive(self) -> None:
        with patch("app.providers.jm.JM_PASSWORD", "SuperSecretPass!123"):
            msg = "Error connecting to http://alice:SuperSecretPass!123@127.0.0.1:7890"
            masked = _mask_sensitive(msg)
            self.assertNotIn("SuperSecretPass!123", masked)
            self.assertIn("***", masked)

            # Error without username
            msg2 = "Proxy failed: socks5://:MyProxyPass@1.2.3.4:1080"
            masked2 = _mask_sensitive(msg2)
            self.assertNotIn("MyProxyPass", masked2)

        # Short password (e.g. 2 characters): masks inside credentials, does not replace regular text
        with patch("app.providers.jm.JM_PASSWORD", "ab"):
            cred_msg = "Proxy auth failed: http://user:ab@127.0.0.1:8080"
            self.assertIn(":***@", _mask_sensitive(cred_msg))
            normal_msg = "about this abstract album"
            self.assertEqual(_mask_sensitive(normal_msg), "about this abstract album")

    def test_proxy_helpers(self) -> None:
        # 1. Sanitize proxy URLs
        self.assertEqual(self.provider._sanitize_proxy(""), "")
        self.assertEqual(self.provider._sanitize_proxy("  "), "")
        self.assertEqual(
            self.provider._sanitize_proxy("127.0.0.1:7890"),
            "http://127.0.0.1:7890",
        )
        self.assertEqual(
            self.provider._sanitize_proxy("socks5://127.0.0.1:1080"),
            "socks5://127.0.0.1:1080",
        )

        # 2. Control proxy
        with patch("app.providers.jm.JM_PROXY", "http://127.0.0.1:7890"):
            proxies = self.provider._get_control_proxies()
            self.assertEqual(
                proxies,
                {"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"},
            )

        with patch("app.providers.jm.JM_PROXY", ""):
            self.assertIsNone(self.provider._get_control_proxies())

        # 3. Image proxy modes (auto, direct)
        with patch("app.providers.jm.JM_PROXY", "http://127.0.0.1:7890"):
            # Auto: follows JM_PROXY
            with patch("app.providers.jm.JM_IMAGE_PROXY_MODE", "auto"):
                self.assertEqual(
                    self.provider._get_image_proxies(),
                    {"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"},
                )

            # Direct: forces None (direct connect even if JM_PROXY is set)
            with patch("app.providers.jm.JM_IMAGE_PROXY_MODE", "direct"):
                self.assertIsNone(self.provider._get_image_proxies())

        with patch("app.providers.jm.JM_PROXY", ""):
            # Without JM_PROXY, both auto and direct return None
            with patch("app.providers.jm.JM_IMAGE_PROXY_MODE", "auto"):
                self.assertIsNone(self.provider._get_image_proxies())
            with patch("app.providers.jm.JM_IMAGE_PROXY_MODE", "direct"):
                self.assertIsNone(self.provider._get_image_proxies())

    def test_magic_bytes_detection(self) -> None:
        # Valid image headers
        jpeg_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 20
        png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\x00" * 20
        webp_bytes = b"RIFF\x20\x00\x00\x00WEBPVP8 " + b"\x00" * 20
        gif_bytes = b"GIF89a\x01\x00\x01\x00" + b"\x00" * 20
        avif_bytes = b"\x00\x00\x00\x1cftypavif\x00\x00\x00\x00" + b"\x00" * 20

        self.assertTrue(self.provider._is_image_bytes(jpeg_bytes))
        self.assertTrue(self.provider._is_image_bytes(png_bytes))
        self.assertTrue(self.provider._is_image_bytes(webp_bytes))
        self.assertTrue(self.provider._is_image_bytes(gif_bytes))
        self.assertTrue(self.provider._is_image_bytes(avif_bytes))

        # Invalid payloads (WAF HTML challenge / error text / garbage)
        html_payload = b"<!DOCTYPE html><html><head><title>Cloudflare Just a moment...</title></head></html>"
        json_payload = b'{"code": 403, "message": "Access Denied"}'
        short_bytes = b"abc"

        self.assertFalse(self.provider._is_image_bytes(html_payload))
        self.assertFalse(self.provider._is_image_bytes(json_payload))
        self.assertFalse(self.provider._is_image_bytes(short_bytes))

    def test_session_cache_lifecycle(self) -> None:
        with patch("app.providers.jm.JM_USERNAME", "alice"):
            # Initial: no session cache
            self.assertIsNone(self.provider._load_session_cache())

            # Save cookies
            cookies = {"AVS": "token_123", "ipm5": "ipm_val"}
            self.provider._save_session_cache(cookies)

            # Check POSIX file permissions (chmod 0o600)
            if hasattr(os, "stat"):
                mode = self.provider._session_cache_file.stat().st_mode & 0o777
                self.assertEqual(mode, 0o600)

            # Load cookies: matches username and within TTL
            loaded = self.provider._load_session_cache()
            self.assertEqual(loaded, cookies)

            # Username mismatch invalidates cache
            with patch("app.providers.jm.JM_USERNAME", "bob"):
                self.assertIsNone(self.provider._load_session_cache())

            # Corrupted / null timestamp in session file must not raise TypeError/ValueError
            self.provider.save_secure_session(
                self.provider._session_cache_file,
                {"cookies": cookies, "username": "alice", "ts": None},
            )
            self.assertIsNone(self.provider._load_session_cache())

            self.provider.save_secure_session(
                self.provider._session_cache_file,
                {"cookies": cookies, "username": "alice", "ts": "not_a_number"},
            )
            self.assertIsNone(self.provider._load_session_cache())

            # Clear cache
            self.provider._clear_session_cache()
            self.assertIsNone(self.provider._load_session_cache())

    def test_get_valid_cookies_concurrent_refresh_grace_window(self) -> None:
        with patch("app.providers.jm.JM_USERNAME", "alice"), patch(
            "app.providers.jm.JM_PASSWORD", "secret123"
        ):
            # Simulate thread 1 just completed login and cached cookies 2 seconds ago
            cookies = {"AVS": "fresh_token_xyz"}
            self.provider._save_session_cache(cookies)

            with patch.object(self.provider, "_perform_login") as mock_login:
                # Thread 2 enters with force_refresh=True, but should reuse recently refreshed cookies
                res = self.provider._get_valid_cookies(force_refresh=True)
                self.assertEqual(res, cookies)
                mock_login.assert_not_called()

    def test_fetch_restricted_album_guidance_when_anonymous(self) -> None:
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.url = "https://18comic.vip/login"
        mock_resp.text = "<html>此本子需要登入後才能觀看</html>"
        mock_client.get.return_value = mock_resp

        with patch.object(self.provider, "_make_html_client", return_value=mock_client), patch(
            "app.providers.jm.JM_USERNAME", ""
        ), patch("app.providers.jm.JM_PASSWORD", ""):
            with self.assertRaises(ValueError) as ctx:
                self.provider.fetch("523607")
            self.assertIn("受权限保护（需登录查看）", str(ctx.exception))
            self.assertIn("JM_USERNAME", str(ctx.exception))

    def test_fetch_restricted_episode_guidance_when_anonymous(self) -> None:
        mock_client = MagicMock()
        mock_album_resp = MagicMock()
        mock_album_resp.url = "https://18comic.vip/album/523607"
        mock_album_resp.text = "<html>Valid Album HTML</html>"

        mock_photo_resp = MagicMock()
        mock_photo_resp.url = "https://18comic.vip/login"
        mock_photo_resp.text = "<html>需登入後才能觀看</html>"

        mock_client.get.side_effect = [mock_album_resp, mock_photo_resp]

        mock_detail = MagicMock()
        mock_detail.name = "单话受限本子"
        mock_detail.authors = ["测试作者"]
        mock_detail.works = []
        mock_detail.actors = []
        mock_detail.tags = []
        mock_detail.description = ""
        mock_detail.episode_list = [("523607", "1", "第 1 話")]
        mock_detail.page_count = 1
        mock_detail.pub_date = ""
        mock_detail.update_date = ""
        mock_detail.views = ""
        mock_detail.likes = ""
        mock_detail.comment_count = 0

        with patch.object(self.provider, "_make_html_client", return_value=mock_client), patch(
            "app.providers.jm.JM_USERNAME", ""
        ), patch("app.providers.jm.JM_PASSWORD", ""), patch(
            "jmcomic.JmcomicText.analyse_jm_album_html", return_value=mock_detail
        ):
            with self.assertRaises(ValueError) as ctx:
                self.provider.fetch("523607")
            self.assertIn("受权限保护（需登录查看）", str(ctx.exception))
            self.assertIn("JM_USERNAME", str(ctx.exception))

    def test_fetch_restricted_album_self_healing_with_credentials(self) -> None:
        mock_client1 = MagicMock()
        mock_resp_fail = MagicMock()
        mock_resp_fail.url = "https://18comic.vip/login"
        mock_resp_fail.text = "需要登入後才能觀看"
        mock_client1.get.return_value = mock_resp_fail

        mock_client2 = MagicMock()
        mock_resp_succ = MagicMock()
        mock_resp_succ.url = "https://18comic.vip/album/523607"
        mock_resp_succ.text = "<html>Valid Album HTML</html>"
        mock_client2.get.return_value = mock_resp_succ

        mock_detail = MagicMock()
        mock_detail.name = "测试受限本子"
        mock_detail.authors = ["测试作者"]
        mock_detail.works = []
        mock_detail.actors = []
        mock_detail.tags = ["限制级"]
        mock_detail.description = "测试描述"
        mock_detail.episode_list = []
        mock_detail.page_count = 10
        mock_detail.pub_date = "2026-09-18"
        mock_detail.update_date = "2026-09-18"
        mock_detail.views = "1000"
        mock_detail.likes = "500"
        mock_detail.comment_count = 10

        mock_photo = MagicMock()
        mock_photo.page_arr = ["1.jpg"]
        mock_photo.scramble_id = "220980"
        mock_photo.data_original_0 = "https://cdn-msp.jmapiproxy1.cc/media/photos/523607/1.jpg"
        mock_photo.data_original_domain = "cdn-msp.jmapiproxy1.cc"
        mock_photo.get_data_original_query_params.return_value = ""

        mock_img = MagicMock()
        mock_img.download_url = "https://cdn-msp.jmapiproxy1.cc/media/photos/523607/1.jpg"
        mock_img.img_file_suffix = ".jpg"
        mock_photo.create_image_detail.return_value = mock_img

        call_count = 0

        def client_factory(force_refresh_session: bool = False):
            nonlocal call_count
            call_count += 1
            return mock_client2 if force_refresh_session else mock_client1

        with patch.object(self.provider, "_make_html_client", side_effect=client_factory), patch(
            "app.providers.jm.JM_USERNAME", "my_jm_user"
        ), patch("app.providers.jm.JM_PASSWORD", "my_password"), patch(
            "jmcomic.JmcomicText.analyse_jm_album_html", return_value=mock_detail
        ), patch(
            "jmcomic.JmcomicText.analyse_jm_photo_html", return_value=mock_photo
        ):
            comic = self.provider.fetch("523607")
            self.assertEqual(comic.meta.title, "测试受限本子")
            self.assertEqual(comic.meta.display_id, "JM523607")
            self.assertEqual(call_count, 2)  # Refreshed session and retried

    def test_download_page_multi_cdn_failover_on_waf_html(self) -> None:
        meta = ComicMeta(
            source="jm",
            source_id="523607",
            display_id="JM523607",
            title="测试本子",
            cover_count=1,
            pages=[],
        )
        page = RemotePage(
            index=1,
            url="https://cdn-msp.jmapiproxy1.cc/media/photos/523607/00001.webp",
            file="00001.webp",
            ext=".webp",
            scramble_id="",
            chapter="",
            headers={},
        )
        comic = FetchedComic(meta=meta, remote_pages=[page])

        # First request to primary CDN returns WAF HTML 200 challenge
        waf_resp = MagicMock()
        waf_resp.status_code = 200
        waf_resp.content = b"<!DOCTYPE html><html><body>Captcha Required</body></html>"

        # Second request to failover candidate CDN returns valid JPEG bytes
        valid_img_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 64
        succ_resp = MagicMock()
        succ_resp.status_code = 200
        succ_resp.content = valid_img_bytes

        mock_session = MagicMock()
        mock_session.get.side_effect = [waf_resp, succ_resp]

        with patch.object(self.provider, "_session", return_value=mock_session), patch(
            "time.sleep", return_value=None
        ):
            decoded = self.provider.download_page(comic, page)
            self.assertEqual(decoded, valid_img_bytes)
            self.assertEqual(mock_session.get.call_count, 2)

            # Check URLs: first request was original domain, second was failover domain
            first_call_url = mock_session.get.call_args_list[0][0][0]
            second_call_url = mock_session.get.call_args_list[1][0][0]
            self.assertIn("cdn-msp.jmapiproxy1.cc", first_call_url)
            self.assertNotIn("cdn-msp.jmapiproxy1.cc", second_call_url)

    def test_download_page_blocks_unsafe_cdn_candidates(self) -> None:
        meta = ComicMeta(
            source="jm",
            source_id="523607",
            display_id="JM523607",
            title="测试本子",
            cover_count=1,
            pages=[],
        )
        # Injected SSRF / unsafe CDN URL
        page = RemotePage(
            index=1,
            url="http://127.0.0.1:8080/media/photos/523607/00001.webp",
            file="00001.webp",
            ext=".webp",
            scramble_id="",
            chapter="",
            headers={},
        )
        comic = FetchedComic(meta=meta, remote_pages=[page])

        with patch("jmcomic.JmModuleConfig.DOMAIN_IMAGE_LIST", ["10.0.0.1", "localhost"]):
            with self.assertRaises(RuntimeError) as ctx:
                self.provider.download_page(comic, page)
            self.assertIn("未找到可信安全的图片 CDN 域名", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
