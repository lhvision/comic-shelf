"""Unit tests for PDF comic unpacking, dual-track chapter detection, and direct file import."""
from __future__ import annotations

import io
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pymupdf
from PIL import Image

from app.models import Chapter, LocalPathImportRequest, PdfChapterPreview
from app.storage.pdf import (
    _extract_chapters_from_toc,
    detect_pdf_chapters,
    is_pdf_file,
    unpack_pdf,
)
from app.storage import ComicStore


class TestPdfIngest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="test_pdf_"))
        self.store = ComicStore(root=self.tmp_dir)
        import os
        os.environ["COMIC_SHELF_ALLOWED_DIRS"] = str(self.tmp_dir)

    def tearDown(self) -> None:
        import os
        os.environ.pop("COMIC_SHELF_ALLOWED_DIRS", None)
        try:
            self.store._cover_executor.shutdown(wait=True)
        except Exception:
            pass
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _create_synthetic_pdf(self, path: Path, num_pages: int = 6, with_toc: bool = False) -> None:
        """Creates a small synthetic PDF with embedded JPEG images on each page."""
        doc = pymupdf.open()
        for i in range(1, num_pages + 1):
            img = Image.new("RGB", (200, 300), color=(i * 30 % 255, i * 50 % 255, i * 70 % 255))
            buf = io.BytesIO()
            img.save(buf, format="JPEG")
            img_bytes = buf.getvalue()

            page = doc.new_page(width=200, height=300)
            page.insert_image(page.rect, stream=img_bytes)

        if with_toc:
            # Table of contents: Front matter (1-2), Ch1 (3-4), Ch2 (5-6)
            toc = [
                [1, "第 1 话 初见", 3],
                [1, "第 2 话 启程", 5],
            ]
            doc.set_toc(toc)

        doc.save(str(path))
        doc.close()

    def test_is_pdf_file(self) -> None:
        self.assertTrue(is_pdf_file("test.pdf"))
        self.assertTrue(is_pdf_file(Path("/path/to/manga.PDF")))
        self.assertFalse(is_pdf_file("test.jpg"))
        self.assertFalse(is_pdf_file("test.pdf.zip"))

    def test_unpack_pdf_lossless(self) -> None:
        pdf_path = self.tmp_dir / "sample.pdf"
        self._create_synthetic_pdf(pdf_path, num_pages=5)

        unpack_dir = self.tmp_dir / "unpacked"
        extracted, meta = unpack_pdf(pdf_path, unpack_dir)

        self.assertEqual(len(extracted), 5)
        self.assertEqual(meta["total_pages"], 5)
        for idx, (pno, fpath, ext) in enumerate(extracted, start=1):
            self.assertEqual(pno, idx)
            self.assertTrue(fpath.exists())
            self.assertEqual(ext, ".jpg")

    def test_toc_chapter_detection(self) -> None:
        pdf_path = self.tmp_dir / "with_toc.pdf"
        self._create_synthetic_pdf(pdf_path, num_pages=8, with_toc=True)

        chapters, track = detect_pdf_chapters(pdf_path, total_pages=8, doc_title="测试书名")
        self.assertEqual(track, "toc")
        self.assertEqual(len(chapters), 3)

        # First chapter is front matter (1-2)
        self.assertEqual(chapters[0]["id"], "c0")
        self.assertEqual(chapters[0]["title"], "卷首 / 目录")
        self.assertEqual(chapters[0]["start"], 1)
        self.assertEqual(chapters[0]["page_count"], 2)

        # Second is Ch1 (3-4)
        self.assertEqual(chapters[1]["title"], "第 1 话 初见")
        self.assertEqual(chapters[1]["start"], 3)
        self.assertEqual(chapters[1]["page_count"], 2)

        # Third is Ch2 (5-8)
        self.assertEqual(chapters[2]["title"], "第 2 话 启程")
        self.assertEqual(chapters[2]["start"], 5)
        self.assertEqual(chapters[2]["page_count"], 4)

    def test_import_single_pdf_direct_path(self) -> None:
        pdf_path = self.tmp_dir / "comic.pdf"
        self._create_synthetic_pdf(pdf_path, num_pages=6, with_toc=True)

        req = LocalPathImportRequest(
            path=str(pdf_path),
            title="单文件导入测试",
            authors=["测试作者"],
        )
        meta = self.store.import_local_path(req)

        self.assertEqual(meta.source, "local")
        self.assertEqual(meta.title, "单文件导入测试")
        self.assertEqual(meta.page_count, 6)
        self.assertEqual(len(meta.chapters), 3)
        self.assertEqual(meta.chapters[0].title, "卷首 / 目录")
        self.assertEqual(meta.chapters[1].title, "第 1 话 初见")
        self.assertEqual(meta.chapters[2].title, "第 2 话 启程")

        # Verify pages are monotonic 1..6
        self.assertEqual([p.index for p in meta.pages], [1, 2, 3, 4, 5, 6])
        # Verify covers were created
        self.assertTrue(self.store.cover_path(meta, 1, ext="webp").exists())

    def test_import_multi_pdf_directory(self) -> None:
        manga_dir = self.tmp_dir / "manga_volumes"
        manga_dir.mkdir(parents=True, exist_ok=True)

        pdf1 = manga_dir / "第01话.pdf"
        pdf2 = manga_dir / "第02话.pdf"
        self._create_synthetic_pdf(pdf1, num_pages=3)
        self._create_synthetic_pdf(pdf2, num_pages=4)

        req = LocalPathImportRequest(
            path=str(manga_dir),
            title="多卷目录导入",
        )
        meta = self.store.import_local_path(req)

        self.assertEqual(meta.page_count, 7)
        self.assertEqual(len(meta.chapters), 2)
        self.assertEqual(meta.chapters[0].title, "第01话")
        self.assertEqual(meta.chapters[0].page_count, 3)
        self.assertEqual(meta.chapters[0].start, 1)

        self.assertEqual(meta.chapters[1].title, "第02话")
        self.assertEqual(meta.chapters[1].page_count, 4)
        self.assertEqual(meta.chapters[1].start, 4)

        self.assertEqual([p.index for p in meta.pages], [1, 2, 3, 4, 5, 6, 7])

    def test_delete_staged_pdf(self) -> None:
        from app.config import TMP_DIR

        pdf_path = self.tmp_dir / "inspect_del.pdf"
        self._create_synthetic_pdf(pdf_path, num_pages=2)

        resp = self.store.inspect_pdf_file(pdf_path)
        token = resp.staging_token
        self.assertTrue((TMP_DIR / token).exists())

        # Purge staging directory explicitly
        success = self.store.delete_staged_pdf(token)
        self.assertTrue(success)
        self.assertFalse((TMP_DIR / token).exists())

    def test_encrypted_pdf_detection(self) -> None:
        import pymupdf
        from app.storage.pdf import unpack_pdf

        pdf_path = self.tmp_dir / "encrypted.pdf"
        doc = pymupdf.open()
        page = doc.new_page(width=300, height=400)
        page.insert_text((50, 50), "Secret Content")
        # Save with user password
        doc.save(str(pdf_path), encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="secret123", owner_pw="owner123")
        doc.close()

        out_dir = self.tmp_dir / "enc_out"
        with self.assertRaises(ValueError) as ctx:
            unpack_pdf(pdf_path, out_dir)
        self.assertIn("加密", str(ctx.exception))


    def test_append_pages_with_pdf(self) -> None:
        pdf_path1 = self.tmp_dir / "base.pdf"
        self._create_synthetic_pdf(pdf_path1, num_pages=3)
        req = LocalPathImportRequest(path=str(pdf_path1), title="追加测试")
        meta = self.store.import_local_path(req)
        self.assertEqual(meta.page_count, 3)

        # Create a second PDF to append
        pdf_path2 = self.tmp_dir / "volume2.pdf"
        self._create_synthetic_pdf(pdf_path2, num_pages=4, with_toc=True)

        updated_meta = self.store.append_pages(
            source_id=meta.source_id,
            source="local",
            server_path=str(pdf_path2),
        )
        # Should now have 3 + 4 = 7 pages
        self.assertEqual(updated_meta.page_count, 7)
        self.assertEqual([p.index for p in updated_meta.pages], [1, 2, 3, 4, 5, 6, 7])
        self.assertTrue(len(updated_meta.chapters) >= 2)

    def test_replace_pages_with_pdf(self) -> None:
        pdf_path1 = self.tmp_dir / "to_replace.pdf"
        self._create_synthetic_pdf(pdf_path1, num_pages=5)
        req = LocalPathImportRequest(path=str(pdf_path1), title="替换测试")
        meta = self.store.import_local_path(req)
        self.assertEqual(meta.page_count, 5)

        # Create a new PDF to replace existing pages
        pdf_path2 = self.tmp_dir / "new_edition.pdf"
        self._create_synthetic_pdf(pdf_path2, num_pages=4)

        updated_meta = self.store.replace_pages(
            source="local",
            source_id=meta.source_id,
            server_path=str(pdf_path2),
        )
        self.assertEqual(updated_meta.page_count, 4)
        self.assertEqual([p.index for p in updated_meta.pages], [1, 2, 3, 4])


if __name__ == "__main__":
    unittest.main()

