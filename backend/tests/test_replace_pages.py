import shutil
import tempfile
import unittest
from pathlib import Path
from PIL import Image
import io

import sys
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
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
        for idx, p in enumerate(fetched.meta.pages[2:], start=1):
            p.chapter = "c2"
            p.file = f"{idx:05d}.webp"

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
                self.assertIn("未提供有效的图片或 PDF 画卷文件", str(ctx.exception))
            finally:
                os.environ.pop("COMIC_SHELF_ALLOWED_DIRS", None)

    def test_composite_filename_auto_grouping(self):
        # Setup sample comic with 2 legacy chapters
        from app.models import Chapter
        fetched = self._setup_sample_comic("picacg", "5f80b1234567890abcdef123")
        fetched.meta.chapters = [
            Chapter(id="c1", index=1, title="第1话：青梅竹马", page_count=2, start=1),
            Chapter(id="c2", index=2, title="第2话：雨后", page_count=2, start=3),
        ]
        self.store.save_fetched(fetched)

        # Downloaded images in a single folder with composite filenames: 1-1.avif, 1-2.avif, 2-1.avif, 3-1.avif
        img = self._create_sample_img("green")
        files = [
            ("2-1.avif", img),
            ("1-2.avif", img),
            ("3-1.avif", img),
            ("1-1.avif", img),
        ]

        new_meta = self.store.replace_pages("picacg", "5f80b1234567890abcdef123", files=files)
        self.assertTrue(new_meta.custom_pages)
        self.assertEqual(new_meta.page_count, 4)
        self.assertEqual(len(new_meta.chapters), 3)

        # Chapter 1: inherited title, 2 pages
        self.assertEqual(new_meta.chapters[0].title, "第1话：青梅竹马")
        self.assertEqual(new_meta.chapters[0].page_count, 2)
        self.assertEqual(new_meta.chapters[0].start, 1)

        # Chapter 2: inherited title, 1 page
        self.assertEqual(new_meta.chapters[1].title, "第2话：雨后")
        self.assertEqual(new_meta.chapters[1].page_count, 1)
        self.assertEqual(new_meta.chapters[1].start, 3)

        # Chapter 3: new chapter, 1 page
        self.assertEqual(new_meta.chapters[2].title, "第 3 话")
        self.assertEqual(new_meta.chapters[2].page_count, 1)
        self.assertEqual(new_meta.chapters[2].start, 4)

    def test_composite_grouping_zero_data_loss_preserves_unmatched_files(self):
        fetched = self._setup_sample_comic("local", "zero_loss_test")
        img = self._create_sample_img("blue")
        # 10 files total: 8 composite, 2 non-composite (00_cover.avif and extra.avif)
        files = [
            ("00_cover.avif", img),
            ("1-1.avif", img),
            ("1-2.avif", img),
            ("1-3.avif", img),
            ("1-4.avif", img),
            ("2-1.avif", img),
            ("2-2.avif", img),
            ("2-3.avif", img),
            ("2-4.avif", img),
            ("extra.avif", img),
        ]

        new_meta = self.store.replace_pages("local", "zero_loss_test", files=files)
        self.assertEqual(new_meta.page_count, 10)
        self.assertEqual(len(new_meta.chapters), 2)
        # Chapter 1 has 00_cover + 4 pages = 5 pages
        self.assertEqual(new_meta.chapters[0].page_count, 5)
        self.assertEqual(new_meta.chapters[0].start, 1)
        # Chapter 2 has 4 pages + extra = 5 pages
        self.assertEqual(new_meta.chapters[1].page_count, 5)
        self.assertEqual(new_meta.chapters[1].start, 6)

    def test_composite_single_chapter_remains_flat(self):
        self._setup_sample_comic("local", "single_ch_flat")
        img = self._create_sample_img("yellow")
        files = [
            ("1-1.avif", img),
            ("1-2.avif", img),
        ]

        new_meta = self.store.replace_pages("local", "single_ch_flat", files=files)
        # Only 1 chapter detected, must remain flat single volume
        self.assertEqual(len(new_meta.chapters), 0)
        self.assertEqual(new_meta.page_count, 2)

    def test_scoped_thumbnail_invalidation_preserves_other_chapters(self):
        from app.models import Chapter
        fetched = self._setup_sample_comic("local", "multi_scoped")
        fetched.meta.chapters = [
            Chapter(id="c1", index=1, title="第 1 话", page_count=2, start=1),
            Chapter(id="c2", index=2, title="第 2 话", page_count=2, start=3),
        ]
        self.store.save_fetched(fetched)

        # Populate thumbnails for chapter 1 and chapter 2
        thumbs_c1 = self.store.thumbs_dir("local", "multi_scoped") / "c1"
        thumbs_c2 = self.store.thumbs_dir("local", "multi_scoped") / "c2"
        thumbs_c1.mkdir(parents=True, exist_ok=True)
        thumbs_c2.mkdir(parents=True, exist_ok=True)
        (thumbs_c1 / "00001.webp").write_bytes(b"c1_thumb")
        (thumbs_c2 / "00001.webp").write_bytes(b"c2_thumb")

        # Replace only chapter 1
        img = self._create_sample_img("cyan")
        self.store.replace_pages("local", "multi_scoped", files=[("01.jpg", img)], target_chapter="c1")

        # Chapter 2 thumbnail MUST still be preserved!
        self.assertTrue((thumbs_c2 / "00001.webp").exists())
        self.assertEqual((thumbs_c2 / "00001.webp").read_bytes(), b"c2_thumb")

    def test_append_pages_to_remote_comic_sets_custom_pages(self):
        fetched = self._setup_sample_comic("picacg", "5f80b1234567890abcdef999")
        self.assertFalse(fetched.meta.custom_pages)

        img = self._create_sample_img("pink")
        new_meta = self.store.append_pages(
            source_id="5f80b1234567890abcdef999",
            source="picacg",
            files=[("new_01.webp", img)],
            new_chapter_title="第 2 话：手动补录",
        )

        self.assertTrue(new_meta.custom_pages)
        self.assertEqual(len(new_meta.chapters), 2)
        self.assertEqual(new_meta.chapters[1].title, "第 2 话：手动补录")
        self.assertEqual(new_meta.page_count, 5)

    def test_append_pages_multi_chapter_composite_grouping(self):
        fetched = self._setup_sample_comic("local", "append_composite")
        img = self._create_sample_img("purple")
        files = [
            ("2-1.avif", img),
            ("2-2.avif", img),
            ("3-1.avif", img),
        ]
        new_meta = self.store.append_pages(
            source_id="append_composite",
            source="local",
            files=files,
            new_chapter_title="第 2 话",
        )
        # Should create chapter 1 (existing promoted), chapter 2 (2 pages), and chapter 3 (1 page)
        self.assertEqual(len(new_meta.chapters), 3)
        self.assertEqual(new_meta.chapters[0].page_count, 4)
        self.assertEqual(new_meta.chapters[1].page_count, 2)
        self.assertEqual(new_meta.chapters[2].page_count, 1)
        self.assertEqual(new_meta.page_count, 7)

    def test_delete_and_title_update_sets_custom_pages(self):
        from app.models import Chapter
        fetched = self._setup_sample_comic("picacg", "5f80b1234567890abcdef777")
        fetched.meta.chapters = [
            Chapter(id="c1", index=1, title="第 1 话", page_count=2, start=1),
            Chapter(id="c2", index=2, title="第 2 话", page_count=2, start=3),
        ]
        self.store.save_fetched(fetched)
        self.assertFalse(fetched.meta.custom_pages)

        # Title update on remote comic sets custom_pages
        updated = self.store.update_chapter_title("picacg", "5f80b1234567890abcdef777", "c1", "全新改名")
        self.assertTrue(updated.custom_pages)

        # Delete chapter on remote comic preserves custom_pages
        after_del = self.store.delete_chapter("picacg", "5f80b1234567890abcdef777", "c2")
        self.assertTrue(after_del.custom_pages)
        self.assertEqual(len(after_del.chapters), 1)

    def test_save_fetched_defense_in_depth_preserves_custom_pages(self):
        fetched = self._setup_sample_comic("picacg", "5f80b1234567890abcdef888")
        fetched.meta.custom_pages = True
        self.store.save_fetched(fetched)

        # Simulated remote refresh with fresh meta (where custom_pages is False)
        from app.models import PageRecord
        fresh_meta = ComicMeta(
            source="picacg",
            source_id="5f80b1234567890abcdef888",
            display_id="picacg:5f80b1234567890abcdef888",
            title="Fresh Remote Comic",
            page_count=10,
            pages=[PageRecord(index=1, file="00001.webp", ext=".webp", cached=False)],
            cover_count=4,
            custom_pages=False,
        )
        simulated_remote = FetchedComic(meta=fresh_meta, remote_pages=[])

        saved = self.store.save_fetched(simulated_remote, refresh=True)
        self.assertTrue(saved.custom_pages)
        self.assertEqual(saved.page_count, 4)  # Preserved original 4 pages

    def test_picacg_replaced_pages_page_path_and_ensure_page(self):
        from app.models import Chapter
        source = "picacg"
        source_id = "5f80b1234567890abcdef999"
        fetched = self._setup_sample_comic(source, source_id)
        fetched.meta.chapters = [
            Chapter(id="c1", index=1, title="第 1 话", page_count=2, start=1),
            Chapter(id="c2", index=2, title="第 2 话", page_count=2, start=3),
        ]
        self.store.save_fetched(fetched)

        # Replace with composite chapters (2 chapters, 2 pages each)
        img1 = self._create_sample_img("pink", size=(150, 200))
        img2 = self._create_sample_img("cyan", size=(150, 200))
        img3 = self._create_sample_img("orange", size=(150, 200))
        img4 = self._create_sample_img("black", size=(150, 200))
        files = [
            ("ch1_01.jpg", img1),
            ("ch1_02.jpg", img2),
            ("ch2_01.jpg", img3),
            ("ch2_02.jpg", img4),
        ]
        new_meta = self.store.replace_pages(source, source_id, files=files)
        self.assertTrue(new_meta.custom_pages)
        self.assertEqual(len(new_meta.chapters), 2)
        self.assertEqual(new_meta.page_count, 4)

        fetched = self.store.load_fetched(source, source_id)
        self.assertIsNotNone(fetched)

        # Verify page_path for Chapter 1 (page 1) and Chapter 2 (page 3)
        p1_path = self.store.page_path(new_meta, 1)
        p3_path = self.store.page_path(new_meta, 3)
        self.assertTrue(p1_path.exists())
        self.assertTrue(p3_path.exists())
        self.assertEqual(p1_path.name, "00001.jpg")
        self.assertEqual(p3_path.name, "00001.jpg")
        self.assertEqual(p3_path.parent.name, "c2")

        # Verify ensure_page does not call remote provider or raise ValueError
        ensured_p3 = self.store.ensure_page(fetched, 3)
        self.assertEqual(ensured_p3, p3_path)

        # Verify thumbnail generation works cleanly for chapter 2
        thumb_p3 = self.store.ensure_page_thumb(new_meta, fetched, 3)
        self.assertTrue(thumb_p3.exists())

    def test_picacg_replaced_with_flat_pages(self):
        source = "picacg"
        source_id = "5f80b1234567890abcdefflat"
        self._setup_sample_comic(source, source_id)

        # Replace full comic with flat 3 pages
        img1 = self._create_sample_img("red", size=(120, 160))
        img2 = self._create_sample_img("green", size=(120, 160))
        img3 = self._create_sample_img("blue", size=(120, 160))
        files = [("p1.png", img1), ("p2.png", img2), ("p3.png", img3)]

        new_meta = self.store.replace_pages(source, source_id, files=files)
        self.assertTrue(new_meta.custom_pages)
        self.assertEqual(new_meta.page_count, 3)
        self.assertEqual(len(new_meta.chapters), 0)

        fetched = self.store.load_fetched(source, source_id)
        self.assertIsNotNone(fetched)

        for i in range(1, 4):
            path = self.store.page_path(new_meta, i)
            self.assertTrue(path.exists())
            self.assertEqual(path.name, f"{i:05d}.png")
            ensured = self.store.ensure_page(fetched, i)
            self.assertEqual(ensured, path)
            thumb = self.store.ensure_page_thumb(new_meta, fetched, i)
            self.assertTrue(thumb.exists())


if __name__ == "__main__":
    unittest.main()


