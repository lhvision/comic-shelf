"""`ocr.sh lines` 离线实验台的用例：重点是"调聚类判据不需要推理引擎"。"""

from __future__ import annotations

import argparse
import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from scripts import ocr_lines, ocr_worker


def _png(path: Path, size: tuple[int, int] = (40, 60)) -> Path:
    from PIL import Image

    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, "white").save(path)
    return path


def _box(x0: float, y0: float, x1: float, y1: float) -> list[list[float]]:
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def _row(text: str, x0: float, y0: float, x1: float, y1: float, score: float = 0.9) -> tuple:
    return (_box(x0, y0, x1, y1), text, score)


def _files(root: Path) -> list[Path]:
    return sorted(p.relative_to(root) for p in root.rglob("*") if p.is_file())


class TestImagesScan(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.data_dir = self.tmp / "data"
        for src, sid, names in (
            ("jm", "a", ("00001.webp", "00002.webp")),
            ("local", "b", ("00001.png",)),
            # 分章节的本：画页在 pages/ 下的子目录里
            ("local", "c", ("c1/00001.png", "c2/00001.png")),
        ):
            for n in names:
                _png(self.data_dir / "library" / src / sid / "pages" / n)
        # 非图片文件与缺 pages 目录的本都不得进清单
        (self.data_dir / "library" / "jm" / "a" / "pages" / "notes.txt").write_text("x", encoding="utf-8")
        (self.data_dir / "library" / "jm" / "no_pages" / "album.json").parent.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_scope_and_cap(self):
        all_imgs = ocr_lines._images(self.data_dir, None, None, 0)
        self.assertEqual(len(all_imgs), 5, f"全库清单应只含图片: {all_imgs}")
        self.assertEqual(len(ocr_lines._images(self.data_dir, "jm", None, 0)), 2, "只给 --source 却扫到了别的源")
        self.assertEqual(len(ocr_lines._images(self.data_dir, "jm", "a", 1)), 1, "--pages 没有截断每本页数")
        self.assertEqual(len(ocr_lines._images(self.data_dir, "local", "c", 0)), 2, "分章节子目录里的画页被漏扫")
        self.assertEqual(ocr_lines._images(self.data_dir, "jm", "missing", 0), [])


class TestDump(unittest.TestCase):
    def test_dump_drops_blank_rows_and_writes_outside_the_library(self):
        """dump 只落临时目录：绝不能把实验产物写进 backend/data 现网侧车。"""
        tmp = Path(tempfile.mkdtemp())
        try:
            pages = tmp / "data" / "library" / "jm" / "a" / "pages"
            img = _png(pages / "00001.webp", (800, 1200))
            chapter_img = _png(pages / "c2" / "00001.webp")
            out_dir = tmp / "dump"
            out_dir.mkdir()
            before = _files(tmp / "data")
            rows = [_row("有效台词", 10, 10, 90, 40), _row("   ", 10, 100, 90, 130)]
            with (
                mock.patch.object(ocr_lines, "get_engine", return_value=object()),
                mock.patch.object(ocr_worker, "run_engine", return_value=rows),
            ):
                name, info = ocr_lines._dump_one(img, out_dir, tmp / "data/library")
                self.assertEqual(
                    ocr_lines._dump_one(img, out_dir, tmp / "data/library")[1],
                    "已存在，跳过",
                    "重跑必须跳过已 dump 的页",
                )
                # 各话的同名页不许撞成同一个文件，否则后一话会被当成"已存在"整话跳过
                self.assertEqual(
                    ocr_lines._dump_one(chapter_img, out_dir, tmp / "data/library")[0], "jm/a/pages/c2/00001.json"
                )

            self.assertEqual(info, "1 行")
            self.assertEqual(name, "jm/a/pages/00001.json")
            dumped = json.loads((out_dir / "jm/a/pages/00001.json").read_text(encoding="utf-8"))
            self.assertEqual((dumped["w"], dumped["h"]), (800, 1200), "页面尺寸没按原图记录，聚类比例会全错")
            self.assertEqual([b["text"] for b in dumped["blocks"]], ["有效台词"])
            self.assertEqual(dumped["blocks"][0]["xmin"], 10)
            self.assertEqual(_files(tmp / "data"), before, "dump 往数据目录里写了东西")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_same_book_and_page_names_across_sources_do_not_collide(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            library = root / "library"
            out = root / "dump"
            out.mkdir()
            images = [_png(library / source / "same/pages/00001.png") for source in ("jm", "local")]
            with (
                mock.patch.object(ocr_lines, "get_engine", return_value=object()),
                mock.patch.object(ocr_worker, "run_engine", return_value=[]),
            ):
                names = [ocr_lines._dump_one(image, out, library)[0] for image in images]
            self.assertEqual(["jm/same/pages/00001.json", "local/same/pages/00001.json"], names)
            self.assertEqual(2, len(list(out.rglob("*.json"))))

    def test_invalid_cached_dump_and_links_are_rejected_without_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            library = root / "library"
            image = _png(library / "jm/book/pages/00001.png")
            out = root / "dump"
            destination = out / "jm/book/pages/00001.json"
            destination.parent.mkdir(parents=True)
            for content in ("", "null", "{}", "broken json"):
                destination.write_text(content)
                with self.subTest(content=content), self.assertRaises(ValueError):
                    ocr_lines._dump_one(image, out, library)
                self.assertEqual(content, destination.read_text())
            destination.unlink()
            victim = root / "victim.json"
            destination.symlink_to(victim)
            with self.assertRaises(OSError):
                ocr_lines._dump_one(image, out, library)
            self.assertFalse(victim.exists())

    def test_default_dump_directory_is_private_and_unique(self):
        import os

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "data"
            _png(data / "library/jm/book/pages/00001.png")
            args = argparse.Namespace(data_dir=str(data), source="jm", id="book", pages=0, out=None, workers=1)
            with (
                mock.patch.object(ocr_lines.tempfile, "gettempdir", return_value=str(root)),
                mock.patch.object(ocr_lines, "get_engine", return_value=object()),
                mock.patch.object(ocr_worker, "run_engine", return_value=[]),
                redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(0, ocr_lines.cmd_dump(args))
                self.assertEqual(0, ocr_lines.cmd_dump(args))
            outputs = sorted(root.glob("paper-room-ocr-lines-*"))
            self.assertEqual(2, len(outputs))
            for directory in outputs:
                self.assertEqual(os.geteuid(), directory.stat().st_uid)
                self.assertEqual(0o700, directory.stat().st_mode & 0o777)

    def test_untrusted_output_permissions_and_directory_links_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shared = root / "shared"
            shared.mkdir(mode=0o777)
            shared.chmod(0o777)
            with self.assertRaisesRegex(ValueError, "其他用户修改"):
                ocr_lines._output_directory(shared)
            link = root / "link"
            link.symlink_to(shared, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "符号链接"):
                ocr_lines._output_directory(link)

    def test_directory_replaced_by_link_during_creation_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "output"
            victim = root / "victim"
            victim.mkdir()
            original_mkdir = Path.mkdir

            def substitute_link(path, *args, **kwargs):
                if path == output:
                    path.symlink_to(victim, target_is_directory=True)
                else:
                    original_mkdir(path, *args, **kwargs)

            with mock.patch.object(Path, "mkdir", substitute_link), self.assertRaises(ValueError):
                ocr_lines._output_directory(output)
            self.assertEqual([], list(victim.iterdir()))

    def test_concurrent_dump_publication_is_atomic_and_does_not_overwrite(self):
        from concurrent.futures import ThreadPoolExecutor

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            library = root / "library"
            image = _png(library / "jm/book/pages/00001.png")
            out = root / "dump"
            out.mkdir()
            with (
                mock.patch.object(ocr_lines, "get_engine", return_value=object()),
                mock.patch.object(ocr_worker, "run_engine", return_value=[]),
                ThreadPoolExecutor(max_workers=2) as pool,
            ):
                futures = [pool.submit(ocr_lines._dump_one, image, out, library) for _ in range(2)]
                results = [future.result(timeout=10) for future in futures]
            self.assertEqual({"0 行", "已存在，跳过"}, {result[1] for result in results})
            destination = out / "jm/book/pages/00001.json"
            self.assertEqual(str(image), json.loads(destination.read_text())["image"])
            self.assertEqual([], list(out.rglob("*.tmp")))


class TestImage(unittest.TestCase):
    def test_image_prints_bubbles_and_writes_nothing(self):
        """`ocr.sh test` 走这里：只打印聚类结果，画页旁边不许多出侧车或任何文件。"""
        tmp = Path(tempfile.mkdtemp())
        try:
            img = _png(tmp / "pages" / "00001.webp", (1000, 1000))
            before = _files(tmp)
            buf = io.StringIO()
            with (
                mock.patch.object(ocr_lines, "get_engine", return_value=object()),
                mock.patch.object(ocr_worker, "run_engine", return_value=[_row("老师", 100, 60, 120, 120)]),
                redirect_stdout(buf),
            ):
                rc = ocr_lines.cmd_image(argparse.Namespace(image=str(img)))
            self.assertEqual(rc, 0)
            self.assertIn("老师", buf.getvalue())
            self.assertEqual(_files(tmp), before, "单页试跑往磁盘写了东西")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestRecluster(unittest.TestCase):
    def _dump(self, out_dir: Path, name: str, w: int, h: int, blocks: list[dict]) -> None:
        (out_dir / name).write_text(
            json.dumps({"image": f"/nowhere/{name}", "w": w, "h": h, "blocks": blocks}, ensure_ascii=False),
            encoding="utf-8",
        )

    def test_recluster_needs_no_engine_and_reports_conservation(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            src = tmp / "dump"
            src.mkdir()
            vertical = [
                {"text": "老师", "score": 0.9, "xmin": 100, "xmax": 120, "ymin": 60, "ymax": 120},
                {"text": "请快看", "score": 0.9, "xmin": 70, "xmax": 90, "ymin": 100, "ymax": 250},
                {"text": "这个孩子", "score": 0.9, "xmin": 40, "xmax": 60, "ymin": 110, "ymax": 280},
            ]
            self._dump(src, "a_p1.json", 1000, 1000, vertical)
            # 单条横扫半页高的横幅：不合并，但必须被记成疑似误并供人工复核
            self._dump(
                src,
                "a_p2.json",
                1000,
                1000,
                [{"text": "超大字", "score": 0.9, "xmin": 100, "xmax": 900, "ymin": 100, "ymax": 600}],
            )
            chars = sum(len(b["text"]) for b in vertical) + len("超大字")

            def boom(*_a, **_kw):
                raise AssertionError("recluster 模式不许构造推理引擎")

            buf = io.StringIO()
            with mock.patch.object(ocr_worker, "build_engine", side_effect=boom), redirect_stdout(buf):
                rc = ocr_lines.cmd_recluster(argparse.Namespace(recluster=str(src)))
            out = buf.getvalue()
            self.assertEqual(rc, 0)
            self.assertIn(f"2 页 / 原始行 4 → 气泡 2，字数 {chars}", out, f"字数不守恒或拆并不对:\n{out}")
            self.assertIn("疑似误并: 1", out, out)
            self.assertIn(">35%", out, f"面积分档没打印:\n{out}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_recluster_refuses_empty_dir(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = ocr_lines.cmd_recluster(argparse.Namespace(recluster=str(tmp)))
            self.assertEqual(rc, 1, "空目录必须报错退出，而不是打印一份 0 页的假报告")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
