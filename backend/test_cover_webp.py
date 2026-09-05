import io
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.models import ComicMeta, PageRecord, FetchedComic, Chapter
from app.storage import ComicStore
from app.main import cover_file, chapter_cover, store as global_store


def make_mock_request(
    path="/api/library",
    headers=None,
    cookies=None,
    query_params=None,
):
    req = MagicMock()
    req.state = type("State", (), {})()
    req.url.path = path
    headers_dict = {k.lower(): v for k, v in (headers or {}).items()}
    req.headers.get = lambda k, default="": headers_dict.get(k.lower(), default)
    req.cookies.get = lambda k, default="": (cookies or {}).get(k, default)
    req.query_params.get = lambda k, default="": (query_params or {}).get(k, default)
    return req


class TestWebPCover(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="test_cover_webp_"))
        self.store = ComicStore(root=self.tmp_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _create_sample_img(self, color="red", size=(800, 1200)) -> bytes:
        im = Image.new("RGB", size, color=color)
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=85)
        return buf.getvalue()

    def _setup_sample_comic(self, source="local", source_id="test_webp_01") -> FetchedComic:
        comic_dir = self.store.comic_dir(source, source_id)
        comic_dir.mkdir(parents=True, exist_ok=True)
        pages_dir = self.store.pages_dir(source, source_id)
        pages_dir.mkdir(parents=True, exist_ok=True)

        pages = []
        for i in range(1, 5):
            fn = f"{i:05d}.jpg"
            (pages_dir / fn).write_bytes(self._create_sample_img(color="blue", size=(800, 1200)))
            pages.append(PageRecord(index=i, file=fn, ext=".jpg", cached=True))

        chapter = Chapter(id="ch1", index=1, title="第1话", page_count=4, start=1)
        meta = ComicMeta(
            source=source,
            source_id=source_id,
            display_id=f"{source}:{source_id}",
            title="WebP Test Comic",
            page_count=4,
            pages=pages,
            cover_count=4,
            chapters=[chapter],
        )
        fetched = FetchedComic(meta=meta, remote_pages=[])
        self.store.save_fetched(fetched)
        return fetched

    def test_ensure_webp_cover_generation_and_fast_path(self):
        fetched = self._setup_sample_comic("local", "c1")
        meta = fetched.meta

        # 1. First time requesting 360px WebP: generated from page directly
        webp_360 = self.store.ensure_webp_cover(meta, fetched, index=1, width=360)
        self.assertTrue(webp_360.exists())
        self.assertEqual(webp_360.suffix, ".webp")
        self.assertTrue(webp_360.name.endswith("_360.webp"))

        # Verify image dimensions
        with Image.open(webp_360) as im:
            self.assertEqual(im.format, "WEBP")
            self.assertEqual(im.width, 360)

        # 2. Fast-path test: when .jpg already exists, convert to .webp without resize
        jpg_360 = self.store.cover_path(meta, 2, width=360, ext="jpg")
        self.store._save_cover(self.store.page_path(meta, 2), jpg_360, target_width=360, fmt="JPEG")
        self.assertTrue(jpg_360.exists())

        webp_2 = self.store.ensure_webp_cover(meta, fetched, index=2, width=360)
        self.assertTrue(webp_2.exists())
        self.assertEqual(webp_2.suffix, ".webp")
        with Image.open(webp_2) as im:
            self.assertEqual(im.format, "WEBP")
            self.assertEqual(im.width, 360)

    def test_ensure_webp_chapter_cover(self):
        fetched = self._setup_sample_comic("local", "c2")
        meta = fetched.meta
        chapter = meta.chapters[0]

        webp_chap = self.store.ensure_webp_chapter_cover(meta, fetched, chapter, width=360)
        self.assertTrue(webp_chap.exists())
        self.assertEqual(webp_chap.suffix, ".webp")
        with Image.open(webp_chap) as im:
            self.assertEqual(im.format, "WEBP")
            self.assertEqual(im.width, 360)

    def test_cover_indices_active_prewarming(self):
        fetched = self._setup_sample_comic("local", "c3")
        meta = fetched.meta

        # Update cover_indices to [3, 4]
        new_meta = self.store.update_metadata("local", "c3", {"cover_indices": [3, 4]})
        self.assertEqual(new_meta.cover_indices, [3, 4])

        covers_dir = self.store.covers_dir("local", "c3")
        # Pre-warmed files should include 001.webp, 001_360.webp, 002.webp, 002_360.webp
        self.assertTrue((covers_dir / "001.webp").exists())
        self.assertTrue((covers_dir / "001_360.webp").exists())
        self.assertTrue((covers_dir / "002.webp").exists())
        self.assertTrue((covers_dir / "002_360.webp").exists())

    def test_http_content_negotiation(self):
        # Temporarily wire global_store to our isolated test store
        old_root = global_store.root
        try:
            global_store.root = self.tmp_dir
            global_store._invalidate_cache("local", "c4")
            fetched = self._setup_sample_comic("local", "c4")
            meta = fetched.meta

            # 1. Browser client supporting WebP
            req_webp = make_mock_request(
                path="/api/library/local/c4/covers/1/file",
                headers={"accept": "text/html,application/xhtml+xml,image/webp,*/*;q=0.8"},
            )
            resp_webp = cover_file(source="local", source_id="c4", index=1, request=req_webp, w=360)
            self.assertEqual(resp_webp.media_type, "image/webp")
            self.assertEqual(resp_webp.headers.get("Vary"), "Accept")
            self.assertTrue(str(resp_webp.path).endswith("_360.webp"))
            self.assertTrue(Path(resp_webp.path).exists())

            # 2. Subsequent request (cache hit)
            resp_hit = cover_file(source="local", source_id="c4", index=1, request=req_webp, w=360)
            self.assertEqual(resp_hit.media_type, "image/webp")
            self.assertEqual(resp_hit.path, resp_webp.path)

            # 3. Client not supporting WebP (e.g. curl or old client)
            req_jpeg = make_mock_request(
                path="/api/library/local/c4/covers/1/file",
                headers={"accept": "image/jpeg,image/png,*/*"},
            )
            resp_jpeg = cover_file(source="local", source_id="c4", index=1, request=req_jpeg, w=360)
            self.assertEqual(resp_jpeg.media_type, "image/jpeg")
            self.assertTrue(str(resp_jpeg.path).endswith("_360.jpg"))
            self.assertTrue(Path(resp_jpeg.path).exists())

            # 4. Explicit .webp URL request
            req_explicit = make_mock_request(path="/api/library/local/c4/covers/1/file.webp")
            resp_explicit = cover_file(source="local", source_id="c4", index=1, request=req_explicit, ext="webp", w=360)
            self.assertEqual(resp_explicit.media_type, "image/webp")

            # 5. Chapter cover content negotiation
            req_chap_webp = make_mock_request(headers={"accept": "image/webp"})
            resp_chap = chapter_cover(source="local", source_id="c4", chapter_id="ch1", request=req_chap_webp, w=360)
            self.assertEqual(resp_chap.media_type, "image/webp")
            self.assertTrue(str(resp_chap.path).endswith("_360.webp"))

        finally:
            global_store.root = old_root


if __name__ == "__main__":
    unittest.main()
