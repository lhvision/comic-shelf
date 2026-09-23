"""`ocr.sh lines` 离线实验台的用例：重点是"调聚类判据不需要推理引擎"。"""

from __future__ import annotations

import argparse
import io
import json
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

backend_dir = Path(__file__).resolve().parent.parent
root_dir = backend_dir.parent
for p in (str(root_dir), str(backend_dir)):
    if p not in sys.path:
        sys.path.insert(0, p)

from scripts import ocr_lines


def _png(path: Path, size: tuple[int, int] = (40, 60)) -> Path:
    from PIL import Image

    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, "white").save(path)
    return path


def _box(x0: float, y0: float, x1: float, y1: float) -> list[list[float]]:
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def _row(text: str, x0: float, y0: float, x1: float, y1: float, score: float = 0.9) -> tuple:
    return (_box(x0, y0, x1, y1), text, score)


class TestImagesScan(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.data_dir = self.tmp / "data"
        for src, sid, names in (("jm", "a", ("00001.webp", "00002.webp")), ("local", "b", ("00001.png",))):
            for n in names:
                _png(self.data_dir / "library" / src / sid / "pages" / n)
        # 非图片文件与缺 pages 目录的本都不得进清单
        (self.data_dir / "library" / "jm" / "a" / "pages" / "notes.txt").write_text("x", encoding="utf-8")
        (self.data_dir / "library" / "jm" / "no_pages" / "album.json").parent.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_scope_and_cap(self):
        all_imgs = ocr_lines._images(self.data_dir, None, None, 0)
        self.assertEqual(len(all_imgs), 3, f"全库清单应只含图片: {all_imgs}")
        self.assertEqual(len(ocr_lines._images(self.data_dir, "jm", None, 0)), 2, "只给 --source 却扫到了别的源")
        self.assertEqual(len(ocr_lines._images(self.data_dir, "jm", "a", 1)), 1, "--pages 没有截断每本页数")
        self.assertEqual(ocr_lines._images(self.data_dir, "jm", "missing", 0), [])


class TestDump(unittest.TestCase):
    def test_dump_keeps_only_credible_rows_and_writes_outside_the_library(self):
        """dump 只落临时目录：绝不能把实验产物写进 backend/data 现网侧车。"""
        tmp = Path(tempfile.mkdtemp())
        try:
            img = _png(tmp / "data" / "library" / "jm" / "a" / "pages" / "00001.webp", (800, 1200))
            out_dir = tmp / "dump"
            out_dir.mkdir()
            before = sorted(p.relative_to(tmp / "data") for p in (tmp / "data").rglob("*") if p.is_file())
            rows = [
                _row("有效台词", 10, 10, 90, 40),
                _row("低分噪声", 10, 60, 90, 90, score=ocr_lines.DEFAULT_MIN_SCORE - 0.1),
                _row("   ", 10, 100, 90, 130),
            ]
            with (
                mock.patch.object(ocr_lines, "_engine", return_value=object()),
                mock.patch.object(ocr_lines, "run_engine", return_value=rows),
            ):
                name, info = ocr_lines._dump_one(img, out_dir)
                self.assertEqual(ocr_lines._dump_one(img, out_dir)[1], "已存在，跳过", "重跑必须跳过已 dump 的页")

            self.assertEqual(info, "1 行")
            self.assertEqual(
                sorted(p.name for p in out_dir.glob("*.json")), ["a_00001.json"], f"输出文件名不对: {name}"
            )
            dumped = json.loads((out_dir / "a_00001.json").read_text(encoding="utf-8"))
            self.assertEqual((dumped["w"], dumped["h"]), (800, 1200), "页面尺寸没按原图记录，聚类比例会全错")
            self.assertEqual([b["text"] for b in dumped["blocks"]], ["有效台词"])
            self.assertEqual(dumped["blocks"][0]["xmin"], 10)
            after = sorted(p.relative_to(tmp / "data") for p in (tmp / "data").rglob("*") if p.is_file())
            self.assertEqual(after, before, "dump 往数据目录里写了东西")
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
            with mock.patch.object(ocr_lines, "build_engine", side_effect=boom), redirect_stdout(buf):
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
