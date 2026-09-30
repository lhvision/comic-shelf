import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

from app.config import get_proxy_for_source
from app.models import Chapter, ComicMeta, FetchedComic, PageRecord, RemotePage
from app.providers.copymanga import (
    CopyMangaProvider,
    _validate_download_host,
    aes_decrypt,
    is_valid_image,
)
from app.providers.registry import get_provider


class TestCopyMangaProvider(unittest.TestCase):
    def setUp(self) -> None:
        self.provider = CopyMangaProvider()
        if hasattr(self.provider._tls, "session"):
            delattr(self.provider._tls, "session")

    def test_normalize_id(self) -> None:
        valid_slug = "xiangyaochengweiyingzhishilizhe"

        # 1. Pure slug
        self.assertEqual(self.provider.normalize_id("xiangyaochengweiyingzhishilizhe"), valid_slug)
        self.assertEqual(self.provider.normalize_id("  xiangyaochengweiyingzhishilizhe  "), valid_slug)

        # 2. Prefixes
        self.assertEqual(self.provider.normalize_id("copy:xiangyaochengweiyingzhishilizhe"), valid_slug)
        self.assertEqual(self.provider.normalize_id("copymanga:xiangyaochengweiyingzhishilizhe"), valid_slug)
        self.assertEqual(self.provider.normalize_id("COPYMANGA:xiangyaochengweiyingzhishilizhe"), valid_slug)
        self.assertEqual(self.provider.normalize_id("copy_xiangyaochengweiyingzhishilizhe"), valid_slug)

        # 3. User web mirror URLs
        self.assertEqual(
            self.provider.normalize_id("https://www.mangacopy.com/comic/xiangyaochengweiyingzhishilizhe"),
            valid_slug,
        )
        self.assertEqual(
            self.provider.normalize_id("https://www.mangacopy.com/comic/xiangyaochengweiyingzhishilizhe/"),
            valid_slug,
        )
        self.assertEqual(
            self.provider.normalize_id("https://copymanga.tv/comic/xiangyaochengweiyingzhishilizhe?page=1"),
            valid_slug,
        )
        self.assertEqual(
            self.provider.normalize_id("https://copymanga.site/comic/xiangyaochengweiyingzhishilizhe#chapters"),
            valid_slug,
        )

        # 4. Invalid slugs
        with self.assertRaises(ValueError):
            self.provider.normalize_id("")
        with self.assertRaises(ValueError):
            self.provider.normalize_id("   ")
        with self.assertRaises(ValueError):
            self.provider.normalize_id("invalid slug with spaces!")

    def test_aes_decrypt(self) -> None:
        key_str = "op0zzpvv.nmn.00p"
        iv_str = "1234567890abcdef"
        raw_message = '{"status":"ok","msg":"hello copymanga"}'

        # Encrypt with pycryptodome AES-CBC
        cipher = AES.new(key_str.encode("utf-8"), AES.MODE_CBC, iv_str.encode("utf-8"))
        padded = pad(raw_message.encode("utf-8"), AES.block_size)
        ciphertext = cipher.encrypt(padded)

        # Build CopyManga payload: 16-char IV + hex ciphertext
        payload = iv_str + ciphertext.hex()

        decrypted = aes_decrypt(key_str, payload)
        self.assertEqual(decrypted, raw_message)

    def test_is_valid_image(self) -> None:
        # Valid JPEG
        self.assertTrue(is_valid_image(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00"))
        # Valid PNG
        self.assertTrue(is_valid_image(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"))
        # Valid WebP
        self.assertTrue(is_valid_image(b"RIFF\x20\x00\x00\x00WEBPVP8 "))
        # Valid GIF
        self.assertTrue(is_valid_image(b"GIF89a\x01\x00\x01\x00"))
        # Valid AVIF (avif and mif1 brands)
        self.assertTrue(is_valid_image(b"\x00\x00\x00\x1cftypavif\x00\x00\x00\x00"))
        self.assertTrue(is_valid_image(b"\x00\x00\x00\x1cftypmif1\x00\x00\x00\x00"))

        # Invalid formats / text / WAF errors
        self.assertFalse(is_valid_image(b""))
        self.assertFalse(is_valid_image(b"<html><head><title>403 Forbidden</title></head></html>"))
        self.assertFalse(is_valid_image(b'{"error": "rate limit"}'))
        self.assertFalse(is_valid_image(b"\x00\x01\x02"))

    def test_validate_download_host(self) -> None:
        # Normal public CDN hosts
        _validate_download_host("sx.mangafunb.fun")
        _validate_download_host("s3.mangafunb.fun")
        _validate_download_host("c.mangacopy.com")

        # SSRF malicious hosts and unauthorized domains
        with self.assertRaises(ValueError):
            _validate_download_host("evil-attacker.com")
        with self.assertRaises(ValueError):
            _validate_download_host("localhost")
        with self.assertRaises(ValueError):
            _validate_download_host("127.0.0.1")
        with self.assertRaises(ValueError):
            _validate_download_host("192.168.1.1")
        with self.assertRaises(ValueError):
            _validate_download_host("10.0.0.1")
        with self.assertRaises(ValueError):
            _validate_download_host("server.internal")
        with self.assertRaises(ValueError):
            _validate_download_host("evil.nip.io")

    def test_describe(self) -> None:
        desc = self.provider.describe()
        self.assertEqual(desc["key"], "copymanga")
        self.assertEqual(desc["label"], "拷贝漫画")
        self.assertEqual(desc["short_label"], "拷贝")
        self.assertEqual(desc["example"], "xiangyaochengweiyingzhishilizhe")

    def test_registry(self) -> None:
        provider = get_provider("copymanga")
        self.assertIsInstance(provider, CopyMangaProvider)
        self.assertEqual(provider.key, "copymanga")

    def test_proxy_cascading_resolution(self) -> None:
        # 1. When source-specific COPY_PROXY is set, it takes precedence
        with patch.dict("os.environ", {"COPY_PROXY": "http://10.0.0.1:8080", "COMIC_SHELF_PROXY": "http://127.0.0.1:7890"}):
            self.assertEqual(get_proxy_for_source("copymanga"), "http://10.0.0.1:8080")

        # 2. When COPY_PROXY is unset, it falls back to COMIC_SHELF_PROXY
        with patch.dict("os.environ", {"COPY_PROXY": "", "COMIC_SHELF_PROXY": "http://127.0.0.1:7890"}):
            self.assertEqual(get_proxy_for_source("copymanga"), "http://127.0.0.1:7890")

        # 3. Falls back to system ALL_PROXY / HTTPS_PROXY
        with patch.dict("os.environ", {"COPY_PROXY": "", "COMIC_SHELF_PROXY": "", "all_proxy": "socks5://127.0.0.1:1080"}):
            self.assertEqual(get_proxy_for_source("copymanga"), "socks5://127.0.0.1:1080")

        # 4. Falls back to empty string (direct connection)
        with patch.dict("os.environ", {"COPY_PROXY": "", "COMIC_SHELF_PROXY": "", "all_proxy": "", "ALL_PROXY": "", "https_proxy": "", "HTTPS_PROXY": "", "http_proxy": "", "HTTP_PROXY": ""}):
            self.assertEqual(get_proxy_for_source("copymanga"), "")

    @patch.object(CopyMangaProvider, "_session")
    def test_fetch_mocked(self, mock_session_fn: MagicMock) -> None:
        mock_sess = MagicMock()
        mock_session_fn.return_value = mock_sess

        key_str = "op0zzpvv.nmn.00p"
        iv_str = "1234567890abcdef"

        # Mock HTML detail page
        detail_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
          <title>想要成为影之实力者-拷貝漫畫</title>
          <meta itemprop="keywords" content="拷貝漫畫_奇幻,冒险,轻小说">
        </head>
        <body>
          <h6 title="想要成为影之实力者">想要成为影之实力者</h6>
          <span class="comicParticulars-right-txt">
            <a href="/author/fengze/comics">逢沢大介</a>
          </span>
          <img class="lazyload" data-src="https://sx.mangafunb.fun/x/cover/test.jpg">
          <p class="intro">中二病少年转生异世界的奇妙故事。</p>
          <span class="comicParticulars-tag">
            <a href="/comics?theme=qihuan">#奇幻</a>
            <a href="/comics?theme=qingxiaoshuo">#轻小说</a>
          </span>
          <li>
            <span>熱度：</span>
            <p class="comicParticulars-right-txt">
              <span class="flameIcon allIcon"></span>2245.9W
            </p>
          </li>
          <li>
            <span class="comicParticulars-sigezi">最後更新：</span>
            <span class="comicParticulars-right-txt">2026-08-30</span>
          </li>
          <li>
            <span>狀態：</span>
            <span class="comicParticulars-right-txt">連載中</span>
          </li>
          <script>
            var ccz = '{key_str}';
          </script>
          <span id="dnt" value="3"></span>
        </body>
        </html>
        """

        # Mock chapters JSON payload encrypted with AES
        chapters_raw = {
            "build": "1.0",
            "groups": {
                "default": {
                    "name": "默認",
                    "chapters": [
                        {"id": "ch1-uuid", "name": "第01话", "type": 1},
                        {"id": "ch2-uuid", "name": "第02话", "type": 1},
                    ],
                },
                "tankobon": {
                    "name": "单行本",
                    "chapters": [
                        {"id": "vol1-uuid", "name": "单行本01卷", "type": 1},
                    ],
                },
            },
        }

        # Encrypt chapters payload
        cipher1 = AES.new(key_str.encode("utf-8"), AES.MODE_CBC, iv_str.encode("utf-8"))
        ct1 = cipher1.encrypt(pad(json.dumps(chapters_raw).encode("utf-8"), AES.block_size))
        encrypted_chapters = iv_str + ct1.hex()

        # Mock chapter page payloads
        ch1_pages = [{"url": "https://sx.mangafunb.fun/pages/ch1/01.jpg"}, {"url": "https://sx.mangafunb.fun/pages/ch1/02.jpg"}]
        ch2_pages = [{"url": "https://sx.mangafunb.fun/pages/ch2/01.jpg"}]
        vol1_pages = [{"url": "https://sx.mangafunb.fun/pages/vol1/01.jpg"}, {"url": "https://sx.mangafunb.fun/pages/vol1/02.jpg"}]

        def make_chap_html(pages_list: list) -> str:
            cipher = AES.new(key_str.encode("utf-8"), AES.MODE_CBC, iv_str.encode("utf-8"))
            ct = cipher.encrypt(pad(json.dumps(pages_list).encode("utf-8"), AES.block_size))
            payload = iv_str + ct.hex()
            return f"""
            <html>
            <script>
              var cct = '{key_str}';
              var contentKey = '{payload}';
            </script>
            </html>
            """

        def mock_get(url: str, **kwargs):
            resp = MagicMock()
            resp.status_code = 200
            if "/comicdetail/" in url:
                resp.json.return_value = {"code": 200, "results": encrypted_chapters}
            elif "/chapter/ch1-uuid" in url:
                resp.text = make_chap_html(ch1_pages)
            elif "/chapter/ch2-uuid" in url:
                resp.text = make_chap_html(ch2_pages)
            elif "/chapter/vol1-uuid" in url:
                resp.text = make_chap_html(vol1_pages)
            else:
                resp.text = detail_html
            return resp

        mock_sess.get.side_effect = mock_get

        fetched = self.provider.fetch("xiangyaochengweiyingzhishilizhe")

        self.assertIsInstance(fetched, FetchedComic)
        self.assertEqual(fetched.meta.title, "想要成为影之实力者")
        self.assertEqual(fetched.meta.authors, ["逢沢大介"])
        self.assertIn("奇幻", fetched.meta.tags)
        self.assertEqual(fetched.meta.published_at, "")
        self.assertEqual(fetched.meta.updated_at, "2026-08-30")
        self.assertTrue(fetched.meta.imported_at)
        self.assertIn("T", fetched.meta.imported_at)
        self.assertEqual(fetched.meta.views, "2245.9W")

        # Check raw group metadata
        self.assertEqual(
            fetched.meta.raw.get("available_groups"),
            [
                {"key": "default", "name": "默認", "count": 2},
                {"key": "tankobon", "name": "单行本", "count": 1},
            ],
        )
        self.assertEqual(fetched.meta.raw.get("selected_groups"), ["default"])

        # By default policy, only "default" group is fetched (2 chapters instead of 3)
        self.assertEqual(len(fetched.meta.chapters), 2)
        self.assertEqual(fetched.meta.chapters[0].title, "第01话")
        self.assertEqual(fetched.meta.chapters[0].group, "default")
        self.assertEqual(fetched.meta.chapters[0].page_count, 2)
        self.assertEqual(fetched.meta.chapters[0].start, 1)

        self.assertEqual(fetched.meta.chapters[1].title, "第02话")
        self.assertEqual(fetched.meta.chapters[1].group, "default")
        self.assertEqual(fetched.meta.chapters[1].page_count, 1)
        self.assertEqual(fetched.meta.chapters[1].start, 3)

        # Check total pages for default selection
        self.assertEqual(fetched.meta.page_count, 3)
        self.assertEqual(len(fetched.remote_pages), 3)
        self.assertEqual(len(fetched.meta.pages), 3)

        for i, p in enumerate(fetched.remote_pages, start=1):
            self.assertEqual(p.index, i)
        for i, p in enumerate(fetched.meta.pages, start=1):
            self.assertEqual(p.index, i)

        self.assertEqual(fetched.meta.pages[0].chapter, "ch1-uuid")
        self.assertEqual(fetched.meta.pages[1].chapter, "ch1-uuid")
        self.assertEqual(fetched.meta.pages[2].chapter, "ch2-uuid")

        # Now test fetching with explicit multi-groups selection
        fetched_multi = self.provider.fetch(
            "xiangyaochengweiyingzhishilizhe",
            groups_to_fetch=["default", "tankobon"],
        )
        self.assertEqual(len(fetched_multi.meta.chapters), 3)
        self.assertEqual(fetched_multi.meta.raw.get("selected_groups"), ["default", "tankobon"])
        self.assertEqual(fetched_multi.meta.chapters[2].title, "[单行本] 单行本01卷")
        self.assertEqual(fetched_multi.meta.chapters[2].group, "tankobon")
        self.assertEqual(fetched_multi.meta.chapters[2].page_count, 2)
        self.assertEqual(fetched_multi.meta.chapters[2].start, 4)
        self.assertEqual(fetched_multi.meta.page_count, 5)
        self.assertEqual(fetched_multi.meta.pages[3].chapter, "vol1-uuid")
        self.assertEqual(fetched_multi.meta.pages[4].chapter, "vol1-uuid")

    @patch.object(CopyMangaProvider, "_session")
    def test_existing_chapters_reuse(self, mock_session_fn: MagicMock) -> None:
        mock_sess = MagicMock()
        mock_session_fn.return_value = mock_sess

        key_str = "op0zzpvv.nmn.00p"
        iv_str = "1234567890abcdef"

        detail_html = f"""
        <html><body>
          <h6 title="测试">测试</h6>
          <script>var ccz = '{key_str}';</script>
          <span id="dnt" value="3"></span>
        </body></html>
        """

        chapters_raw = {
            "groups": {
                "default": {
                    "name": "默認",
                    "chapters": [
                        {"id": "ch1", "name": "第01话", "type": 1},
                        {"id": "ch2", "name": "第02话", "type": 1},
                    ],
                }
            }
        }
        cipher = AES.new(key_str.encode("utf-8"), AES.MODE_CBC, iv_str.encode("utf-8"))
        ct = cipher.encrypt(pad(json.dumps(chapters_raw).encode("utf-8"), AES.block_size))
        encrypted_chapters = iv_str + ct.hex()

        # Existing comic already has ch1
        existing_ch1_pages = [
            RemotePage(index=1, url="https://cached/01.jpg", file="00001.jpg", ext="jpg", chapter="ch1")
        ]
        existing = FetchedComic(
            meta=ComicMeta(
                source="copymanga",
                source_id="test_slug",
                display_id="COPY_test_slug",
                title="测试",
                imported_at="2025-05-20T12:00:00+00:00",
                chapters=[Chapter(id="ch1", index=1, title="第01话", page_count=1, start=1)],
                pages=[PageRecord(index=1, file="00001.jpg", ext="jpg", chapter="ch1")],
            ),
            remote_pages=existing_ch1_pages,
        )

        ch2_pages = [{"url": "https://new/02.jpg"}]
        c2 = AES.new(key_str.encode("utf-8"), AES.MODE_CBC, iv_str.encode("utf-8"))
        ch2_payload = iv_str + c2.encrypt(pad(json.dumps(ch2_pages).encode("utf-8"), AES.block_size)).hex()

        def mock_get(url: str, **kwargs):
            resp = MagicMock()
            resp.status_code = 200
            if "/comicdetail/" in url:
                resp.json.return_value = {"code": 200, "results": encrypted_chapters}
            elif "/chapter/ch2" in url:
                resp.text = f"<html><script>var cct='{key_str}'; var contentKey='{ch2_payload}';</script></html>"
            elif "/chapter/ch1" in url:
                self.fail("ch1 should be reused from existing and NOT requested over network")
            else:
                resp.text = detail_html
            return resp

        mock_sess.get.side_effect = mock_get

        fetched = self.provider.fetch("test_slug", existing=existing)
        self.assertEqual(len(fetched.meta.chapters), 2)
        self.assertEqual(fetched.remote_pages[0].url, "https://cached/01.jpg")
        self.assertEqual(fetched.remote_pages[1].url, "https://new/02.jpg")
        self.assertEqual(fetched.meta.imported_at, "2025-05-20T12:00:00+00:00")

    @patch.object(CopyMangaProvider, "_session")
    def test_download_page(self, mock_session_fn: MagicMock) -> None:
        mock_sess = MagicMock()
        mock_session_fn.return_value = mock_sess

        jpeg_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = jpeg_bytes
        mock_sess.get.return_value = mock_resp

        comic = MagicMock()
        page = RemotePage(
            index=1,
            url="https://sx.mangafunb.fun/test.jpg",
            file="00001.jpg",
            ext="jpg",
            chapter="ch1",
        )

        data = self.provider.download_page(comic, page)
        self.assertEqual(data, jpeg_bytes)

        # Test download failure on invalid bytes
        mock_resp.content = b"<html>Error 500</html>"
        with self.assertRaises(ValueError):
            self.provider.download_page(comic, page)

        # Test invalid URL scheme rejected
        bad_scheme_page = RemotePage(
            index=1,
            url="file:///etc/passwd",
            file="00001.jpg",
            ext="jpg",
            chapter="ch1",
        )
        with self.assertRaises(ValueError):
            self.provider.download_page(comic, bad_scheme_page)

        # Test retry on first failure then success on second attempt
        fail_resp = MagicMock()
        fail_resp.status_code = 502
        ok_resp = MagicMock()
        ok_resp.status_code = 200
        ok_resp.content = jpeg_bytes
        mock_sess.get.side_effect = [fail_resp, ok_resp]
        data = self.provider.download_page(comic, page)
        self.assertEqual(data, jpeg_bytes)

    def test_download_page_security(self) -> None:
        p_bad_host = RemotePage(index=1, url="http://evil-attacker.com/test.jpg", file="00001.jpg", ext="jpg", chapter="ch1")
        p_bad_port = RemotePage(index=1, url="http://sx.mangafunb.fun:8080/test.jpg", file="00001.jpg", ext="jpg", chapter="ch1")
        p_ip_port = RemotePage(index=1, url="http://127.0.0.1:8000/test.jpg", file="00001.jpg", ext="jpg", chapter="ch1")

        fake_comic = MagicMock()
        with self.assertRaises(ValueError):
            self.provider.download_page(fake_comic, p_bad_host)
        with self.assertRaises(ValueError):
            self.provider.download_page(fake_comic, p_bad_port)
        with self.assertRaises(ValueError):
            self.provider.download_page(fake_comic, p_ip_port)

    @patch.object(CopyMangaProvider, "_session")
    def test_download_page_redirect_security(self, mock_session_fn: MagicMock) -> None:
        mock_sess = MagicMock()
        mock_session_fn.return_value = mock_sess

        fake_comic = MagicMock()
        page = RemotePage(index=1, url="https://sx.mangafunb.fun/01.jpg", file="00001.jpg", ext="jpg", chapter="ch1")

        # 1. Malicious 302 redirect to internal IP is blocked before request
        resp_redirect_evil = MagicMock()
        resp_redirect_evil.status_code = 302
        resp_redirect_evil.headers = {"Location": "http://127.0.0.1:8080/admin"}
        mock_sess.get.return_value = resp_redirect_evil

        with self.assertRaises(ValueError):
            self.provider.download_page(fake_comic, page)
        # Ensure only 1 request was made (the initial one); no request was made to 127.0.0.1
        self.assertEqual(mock_sess.get.call_count, 1)

        mock_sess.get.reset_mock()

        # 2. Legitimate 302 redirect within allowed CDN succeeds
        resp_redirect_ok = MagicMock()
        resp_redirect_ok.status_code = 302
        resp_redirect_ok.headers = {"Location": "https://s3.mangafunb.fun/real.jpg"}

        resp_final = MagicMock()
        resp_final.status_code = 200
        jpeg_bytes = b"\xff\xd8\xff\xe0" + b"\x00" * 20
        resp_final.content = jpeg_bytes

        mock_sess.get.side_effect = [resp_redirect_ok, resp_final]
        data = self.provider.download_page(fake_comic, page)
        self.assertEqual(data, jpeg_bytes)
        self.assertEqual(mock_sess.get.call_count, 2)

    @patch.object(CopyMangaProvider, "_session")
    def test_update_groups_workflow(self, mock_session_fn: MagicMock) -> None:
        import tempfile
        from fastapi import HTTPException
        from app.models import UpdateGroupsRequest
        from app.routers.chapters import update_comic_groups
        from app.storage import ComicStore

        mock_sess = MagicMock()
        mock_session_fn.return_value = mock_sess

        key_str = "op0zzpvv.nmn.00p"
        iv_str = "1234567890abcdef"

        detail_html = f"""
        <html><body>
          <h6 title="测试漫画">测试漫画</h6>
          <script>var ccz = '{key_str}';</script>
          <span id="dnt" value="3"></span>
        </body></html>
        """

        chapters_raw = {
            "build": "1.0",
            "groups": {
                "default": {
                    "name": "默認",
                    "chapters": [
                        {"id": "ch1", "name": "第01话", "type": 1},
                        {"id": "ch2", "name": "第02话", "type": 1},
                    ],
                },
                "tankobon": {
                    "name": "单行本",
                    "chapters": [
                        {"id": "vol1", "name": "单行本01卷", "type": 1},
                    ],
                },
            },
        }

        cipher1 = AES.new(key_str.encode("utf-8"), AES.MODE_CBC, iv_str.encode("utf-8"))
        ct1 = cipher1.encrypt(pad(json.dumps(chapters_raw).encode("utf-8"), AES.block_size))
        encrypted_chapters = iv_str + ct1.hex()

        def make_chap_html(pages_list: list) -> str:
            cipher = AES.new(key_str.encode("utf-8"), AES.MODE_CBC, iv_str.encode("utf-8"))
            ct = cipher.encrypt(pad(json.dumps(pages_list).encode("utf-8"), AES.block_size))
            payload = iv_str + ct.hex()
            return f"<html><script>var cct='{key_str}'; var contentKey='{payload}';</script></html>"

        def mock_get(url: str, **kwargs):
            resp = MagicMock()
            resp.status_code = 200
            if "/comicdetail/" in url:
                resp.json.return_value = {"code": 200, "results": encrypted_chapters}
            elif "/chapter/ch1" in url:
                resp.text = make_chap_html([{"url": "https://img/ch1_01.jpg"}])
            elif "/chapter/ch2" in url:
                resp.text = make_chap_html([{"url": "https://img/ch2_01.jpg"}])
            elif "/chapter/vol1" in url:
                resp.text = make_chap_html([{"url": "https://img/vol1_01.jpg"}])
            else:
                resp.text = detail_html
            return resp

        mock_sess.get.side_effect = mock_get

        with tempfile.TemporaryDirectory() as tmp_root:
            test_store = ComicStore(Path(tmp_root))
            with patch("app.routers.chapters.store", test_store), \
                 patch("app.routers.common.store", test_store), \
                 patch("app.routers.chapters.sync_comic_dialogues"), \
                 patch("app.routers.chapters.broadcast_event"):

                # 1. First fetch: default only (ch1 + ch2)
                initial_fetched = self.provider.fetch("test_slug")
                self.assertEqual(len(initial_fetched.meta.chapters), 2)
                self.assertEqual(initial_fetched.meta.raw.get("selected_groups"), ["default"])
                test_store.save_fetched(initial_fetched)

                # Simulate creating a file in ch1 and vol1
                ch1_dir = test_store.pages_dir("copymanga", "test_slug") / "ch1"
                ch1_dir.mkdir(parents=True, exist_ok=True)
                (ch1_dir / "00001.jpg").write_bytes(b"data1")

                # 2. Add tankobon group via endpoint
                req_add = UpdateGroupsRequest(selected_groups=["default", "tankobon"])
                detail1 = update_comic_groups("copymanga", "test_slug", req_add)
                self.assertEqual(len(detail1.meta.chapters), 3)
                self.assertEqual(detail1.meta.raw.get("selected_groups"), ["default", "tankobon"])

                # Create file in vol1 dir
                vol1_dir = test_store.pages_dir("copymanga", "test_slug") / "vol1"
                vol1_dir.mkdir(parents=True, exist_ok=True)
                (vol1_dir / "00003.jpg").write_bytes(b"data_vol")
                self.assertTrue(vol1_dir.exists())

                # 3. Remove tankobon group via endpoint
                req_remove = UpdateGroupsRequest(selected_groups=["default"])
                detail2 = update_comic_groups("copymanga", "test_slug", req_remove)
                self.assertEqual(len(detail2.meta.chapters), 2)
                self.assertEqual(detail2.meta.raw.get("selected_groups"), ["default"])
                # Confirm vol1 directory was physically deleted
                self.assertFalse(vol1_dir.exists())
                # Confirm ch1 still intact
                self.assertTrue((ch1_dir / "00001.jpg").exists())

                # 4. Reject non-supported source with 400
                with self.assertRaises(HTTPException) as ctx:
                    update_comic_groups("jm", "test_slug", req_add)
                self.assertEqual(ctx.exception.status_code, 400)

                # 5. Keep only tankobon (1 chapter total) - verify ch1 removed, vol1 retained
                vol1_dir.mkdir(parents=True, exist_ok=True)
                (vol1_dir / "00003.jpg").write_bytes(b"data_vol")
                req_single = UpdateGroupsRequest(selected_groups=["tankobon"])
                detail3 = update_comic_groups("copymanga", "test_slug", req_single)
                self.assertEqual(len(detail3.meta.chapters), 1)
                self.assertEqual(detail3.meta.chapters[0].id, "vol1")
                # vol1 file still intact and not wiped!
                self.assertTrue(vol1_dir.exists())
                self.assertTrue((vol1_dir / "00003.jpg").exists())
                # ch1 is now removed
                self.assertFalse(ch1_dir.exists())


if __name__ == "__main__":
    unittest.main()
