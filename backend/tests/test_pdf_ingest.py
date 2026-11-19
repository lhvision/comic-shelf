"""Unit tests for PDF comic unpacking, dual-track chapter detection, and direct file import."""

from __future__ import annotations

import io
import shutil
import tempfile
import unittest
from pathlib import Path

import pymupdf
from fastapi import HTTPException
from PIL import Image

from app.models import CreateFromStagedPdfRequest, LocalPathImportRequest
from app.storage import ComicStore
from app.storage.pdf import (
    detect_pdf_chapters,
    is_blank_or_solid_page,
    is_pdf_file,
    unpack_pdf,
)


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

    def test_create_from_staged_pdf_multi_chapter(self) -> None:
        from app.config import TMP_DIR

        pdf_path = self.tmp_dir / "staged_multi.pdf"
        self._create_synthetic_pdf(pdf_path, num_pages=6, with_toc=True)
        resp = self.store.inspect_pdf_file(pdf_path)
        self.assertEqual(len(resp.chapters), 3)

        meta = self.store.create_from_staged_pdf(
            CreateFromStagedPdfRequest(
                staging_token=resp.staging_token,
                id="staged-multi",
                title="暂存分步建卷",
                tags=["测试"],
                chapters=resp.chapters,
            )
        )

        ids = [c.id for c in resp.chapters]
        self.assertEqual((meta.source, meta.source_id), ("local", "staged-multi"))
        self.assertEqual(
            (meta.title, meta.authors, meta.uploader, meta.tags), ("暂存分步建卷", ["自制"], "PDF导入", ["测试"])
        )
        self.assertEqual(
            [(c.id, c.start, c.page_count) for c in meta.chapters], [(ids[0], 1, 2), (ids[1], 3, 2), (ids[2], 5, 2)]
        )
        self.assertEqual([p.index for p in meta.pages], [1, 2, 3, 4, 5, 6])
        self.assertEqual([p.chapter for p in meta.pages], [ids[0], ids[0], ids[1], ids[1], ids[2], ids[2]])
        # 磁盘上是话内局域序号，与全局页码无关
        for page in meta.pages:
            self.assertTrue((self.store.pages_dir("local", "staged-multi") / page.chapter / page.file).is_file())
        self.assertEqual([p.file[:5] for p in meta.pages if p.chapter == ids[2]], ["00001", "00002"])

        # 落盘的两份清单与返回值一致，暂存区已释放
        fetched = self.store.load_fetched("local", "staged-multi")
        assert fetched is not None
        self.assertEqual(fetched.meta.page_count, 6)
        self.assertEqual([(rp.index, rp.url, rp.chapter) for rp in fetched.remote_pages][-1], (6, "", ids[2]))
        self.assertFalse((TMP_DIR / resp.staging_token).exists())

        # 显式指定的标识已被占用时拒绝，不覆盖已有画卷
        again = self.store.inspect_pdf_file(pdf_path)
        with self.assertRaises(HTTPException) as ctx:
            self.store.create_from_staged_pdf(
                CreateFromStagedPdfRequest(staging_token=again.staging_token, id="staged-multi", title="撞名")
            )
        self.assertEqual(ctx.exception.status_code, 409)
        loaded = self.store.load_meta("local", "staged-multi")
        assert loaded is not None
        self.assertEqual(loaded.title, "暂存分步建卷")
        self.store.delete_staged_pdf(again.staging_token)

    def test_create_from_staged_pdf_flat(self) -> None:
        pdf_path = self.tmp_dir / "staged_flat.pdf"
        self._create_synthetic_pdf(pdf_path, num_pages=3)
        resp = self.store.inspect_pdf_file(pdf_path)

        meta = self.store.create_from_staged_pdf(
            CreateFromStagedPdfRequest(staging_token=resp.staging_token, title="平铺建卷", authors=["某作者"])
        )

        self.assertEqual((meta.authors, meta.page_count, meta.chapters), (["某作者"], 3, []))
        self.assertEqual([(p.index, p.chapter) for p in meta.pages], [(1, ""), (2, ""), (3, "")])
        for page in meta.pages:
            self.assertTrue((self.store.pages_dir("local", meta.source_id) / page.file).is_file())

        with self.assertRaises(HTTPException) as ctx:
            self.store.create_from_staged_pdf(
                CreateFromStagedPdfRequest(staging_token=resp.staging_token, title="过期")
            )
        self.assertEqual(ctx.exception.status_code, 400)

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

    def test_append_pages_with_uploaded_pdf(self) -> None:
        pdf_path1 = self.tmp_dir / "base_up.pdf"
        self._create_synthetic_pdf(pdf_path1, num_pages=3)
        req = LocalPathImportRequest(path=str(pdf_path1), title="追加上传测试")
        meta = self.store.import_local_path(req)
        self.assertEqual(meta.page_count, 3)

        pdf_path2 = self.tmp_dir / "volume_upload.pdf"
        self._create_synthetic_pdf(pdf_path2, num_pages=4, with_toc=True)
        pdf_bytes = pdf_path2.read_bytes()

        updated_meta = self.store.append_pages(
            source_id=meta.source_id,
            source="local",
            files=[("volume_upload.pdf", pdf_bytes)],
        )
        self.assertEqual(updated_meta.page_count, 7)
        self.assertEqual([p.index for p in updated_meta.pages], [1, 2, 3, 4, 5, 6, 7])
        self.assertTrue(len(updated_meta.chapters) >= 2)

    def test_replace_pages_with_uploaded_pdf(self) -> None:
        pdf_path1 = self.tmp_dir / "to_replace_up.pdf"
        self._create_synthetic_pdf(pdf_path1, num_pages=5)
        req = LocalPathImportRequest(path=str(pdf_path1), title="替换上传测试")
        meta = self.store.import_local_path(req)
        self.assertEqual(meta.page_count, 5)

        pdf_path2 = self.tmp_dir / "new_edition_up.pdf"
        self._create_synthetic_pdf(pdf_path2, num_pages=4)
        pdf_bytes = pdf_path2.read_bytes()

        self.store.replace_pages(
            source="local",
            source_id=meta.source_id,
            files=[("new_edition_up.pdf", pdf_bytes)],
        )

    def test_solid_separator_page_detection(self) -> None:
        black_img = Image.new("RGB", (100, 100), color=(10, 10, 10))
        buf = io.BytesIO()
        black_img.save(buf, format="JPEG")
        self.assertTrue(is_blank_or_solid_page(buf.getvalue()))

        white_img = Image.new("RGB", (100, 100), color=(255, 255, 255))
        buf = io.BytesIO()
        white_img.save(buf, format="JPEG")
        self.assertTrue(is_blank_or_solid_page(buf.getvalue()))

        # Grayscale & RGBA
        gray_img = Image.new("L", (100, 100), color=255)
        buf = io.BytesIO()
        gray_img.save(buf, format="PNG")
        self.assertTrue(is_blank_or_solid_page(buf.getvalue()))

        rgba_black = Image.new("RGBA", (100, 100), color=(0, 0, 0, 255))
        buf = io.BytesIO()
        rgba_black.save(buf, format="PNG")
        self.assertTrue(is_blank_or_solid_page(buf.getvalue()))

        # Paletted (P mode)
        pal_img = Image.new("P", (100, 100), color=0)
        pal_img.putpalette([255, 255, 255] * 256)
        buf = io.BytesIO()
        pal_img.save(buf, format="PNG")
        self.assertTrue(is_blank_or_solid_page(buf.getvalue()))

        content_img = Image.new("RGB", (100, 100), color=(255, 255, 255))
        for y in range(30, 70):
            for x in range(30, 70):
                content_img.putpixel((x, y), (0, 0, 0))
        buf = io.BytesIO()
        content_img.save(buf, format="JPEG")
        self.assertFalse(is_blank_or_solid_page(buf.getvalue()))


if __name__ == "__main__":
    unittest.main()
