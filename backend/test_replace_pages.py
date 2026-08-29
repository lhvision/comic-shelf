import shutil
import tempfile
import unittest
from pathlib import Path
from PIL import Image
import io

import sys
sys.path.insert(0, "backend")
from app.models import ComicMeta, PageRecord, FetchedComic
from app.storage import ComicStore
from fastapi import HTTPException

class TestReplacePages(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="test_replace_pages_"))
        self.store = ComicStore(root=self.tmp_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _create_sample_img(self, color="red", size=(100, 100)) -> bytes:
        im = Image.new("RGB", size, color=color)
        buf = io.BytesIO()
        im.save(buf, format="WEBP")
        return buf.getvalue()

    def _setup_sample_comic(self, source="test", source_id="123") -> FetchedComic:
        comic_dir = self.store.pages_dir(source, source_id).parent
        comic_dir.mkdir(parents=True, exist_ok=True)
        pages_dir = self.store.pages_dir(source, source_id)
        pages_dir.mkdir(parents=True, exist_ok=True)

        pages = []
        for i in range(1, 5):
            fn = f"{i:05d}.webp"
            (pages_dir / fn).write_bytes(self._create_sample_img(color="blue"))
            pages.append(PageRecord(index=i, file=fn, ext=".webp", cached=True))

        meta = ComicMeta(
            source=source,
            source_id=source_id,
            display_id=f"{source}:{source_id}",
            title="Sample Comic",
            page_count=4,
            pages=pages,
            cover_count=4,
        )
        fetched = FetchedComic(meta=meta, remote_pages=[])
        self.store.save_fetched(fetched)
        return fetched

    def test_full_replacement_success(self):
        self._setup_sample_comic("test", "123")
        img1 = self._create_sample_img("green", size=(200, 300))
        img2 = self._create_sample_img("yellow", size=(200, 300))

        files = [("02.jpg", img2), ("01.jpg", img1)]
        new_meta = self.store.replace_pages("test", "123", files=files)

        self.assertTrue(new_meta.custom_pages)
        self.assertEqual(new_meta.page_count, 2)
        self.assertEqual(len(new_meta.pages), 2)

        # Check pages directory
        pages_dir = self.store.pages_dir("test", "123")
        self.assertTrue((pages_dir / "00001.jpg").exists())
        self.assertTrue((pages_dir / "00002.jpg").exists())
        self.assertFalse((pages_dir / "00003.webp").exists())

    def test_replacement_transactional_rollback_on_corrupt_file(self):
        self._setup_sample_comic("test", "456")
        valid_img = self._create_sample_img("green")
        corrupt_img = b"Not an image at all"

        files = [("01.jpg", valid_img), ("02.jpg", corrupt_img)]
        with self.assertRaises(HTTPException) as ctx:
            self.store.replace_pages("test", "456", files=files)

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("损坏", ctx.exception.detail)

        # Check that original 4 pages are completely untouched!
        fetched = self.store.load_fetched("test", "456")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.meta.page_count, 4)
        self.assertFalse(fetched.meta.custom_pages)
        pages_dir = self.store.pages_dir("test", "456")
        self.assertTrue((pages_dir / "00004.webp").exists())

    def test_multi_chapter_replacement(self):
        # Setup multi-chapter comic: 2 chapters, 2 pages each
        from app.models import Chapter
        fetched = self._setup_sample_comic("test", "multi")
        ch1 = Chapter(id="c1", index=1, title="第 1 话", page_count=2, start=1)
        ch2 = Chapter(id="c2", index=2, title="第 2 话", page_count=2, start=3)
        fetched.meta.chapters = [ch1, ch2]
        for p in fetched.meta.pages[:2]:
            p.chapter = "c1"
        for p in fetched.meta.pages[2:]:
            p.chapter = "c2"

        # Organize physical directory for chapters
        pages_dir = self.store.pages_dir("test", "multi")
        c1_dir = pages_dir / "c1"
        c2_dir = pages_dir / "c2"
        c1_dir.mkdir(parents=True, exist_ok=True)
        c2_dir.mkdir(parents=True, exist_ok=True)
        (pages_dir / "00001.webp").rename(c1_dir / "00001.webp")
        (pages_dir / "00002.webp").rename(c1_dir / "00002.webp")
        (pages_dir / "00003.webp").rename(c2_dir / "00001.webp")
        (pages_dir / "00004.webp").rename(c2_dir / "00002.webp")
        self.store.save_fetched(fetched)

        # Replace only chapter 1 with 3 new images
        img1 = self._create_sample_img("purple")
        img2 = self._create_sample_img("purple")
        img3 = self._create_sample_img("purple")
        new_meta = self.store.replace_pages("test", "multi", files=[("p1.jpg", img1), ("p2.jpg", img2), ("p3.jpg", img3)], target_chapter="c1")

        self.assertTrue(new_meta.custom_pages)
        self.assertEqual(new_meta.page_count, 5) # 3 in c1 + 2 in c2 = 5
        self.assertEqual(len(new_meta.chapters), 2)
        self.assertEqual(new_meta.chapters[0].page_count, 3)
        self.assertEqual(new_meta.chapters[0].start, 1)
        self.assertEqual(new_meta.chapters[1].page_count, 2)
        self.assertEqual(new_meta.chapters[1].start, 4) # shifted from 3 to 4!

    def test_replacement_from_server_path(self):
        self._setup_sample_comic("test", "server_path_test")
        import os
        scan_dir = self.tmp_dir / "external_scan"
        scan_dir.mkdir(parents=True, exist_ok=True)
        img1 = self._create_sample_img("orange")
        img2 = self._create_sample_img("cyan")
        (scan_dir / "page_01.png").write_bytes(img1)
        (scan_dir / "page_02.png").write_bytes(img2)

        os.environ["COMIC_SHELF_ALLOWED_DIRS"] = str(self.tmp_dir)
        try:
            new_meta = self.store.replace_pages("test", "server_path_test", server_path=str(scan_dir))
            self.assertTrue(new_meta.custom_pages)
            self.assertEqual(new_meta.page_count, 2)
            pages_dir = self.store.pages_dir("test", "server_path_test")
            self.assertTrue((pages_dir / "00001.png").exists())
            self.assertTrue((pages_dir / "00002.png").exists())
        finally:
            os.environ.pop("COMIC_SHELF_ALLOWED_DIRS", None)

    def test_symlink_escape_protection(self):
        self._setup_sample_comic("test", "symlink_test")
        import os
        scan_dir = self.tmp_dir / "safe_scan"
        scan_dir.mkdir(parents=True, exist_ok=True)

        # Create a file outside allowed dirs
        import tempfile
        with tempfile.TemporaryDirectory() as forbidden_dir:
            forbidden_img = Path(forbidden_dir) / "secret.png"
            forbidden_img.write_bytes(self._create_sample_img("pink"))

            # Create symlink inside scan_dir pointing to forbidden_img
            symlink_file = scan_dir / "symlink_escape.png"
            try:
                symlink_file.symlink_to(forbidden_img)
            except OSError:
                return  # Skip if OS / permissions don't allow symlink creation

            os.environ["COMIC_SHELF_ALLOWED_DIRS"] = str(scan_dir)
            try:
                # The symlink should NOT be included, and since scan_dir has no other images, it should raise 400
                with self.assertRaises(Exception) as ctx:
                    self.store.replace_pages("test", "symlink_test", server_path=str(scan_dir))
                self.assertIn("未提供有效的图片文件", str(ctx.exception))
            finally:
                os.environ.pop("COMIC_SHELF_ALLOWED_DIRS", None)

if __name__ == "__main__":
    unittest.main()
