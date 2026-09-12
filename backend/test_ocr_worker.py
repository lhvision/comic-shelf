import sys
import unittest
from pathlib import Path

# Add project root and backend to sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))
sys.path.insert(0, str(root_dir / "backend"))

from scripts.ocr_worker import (
    cluster_blocks,
    collect_comic_pages,
    get_library_stats,
    is_valid_ocr_sidecar,
    parse_page_filter,
)


class TestOCRWorker(unittest.TestCase):
    def test_cluster_blocks_vertical_manga_order(self):
        """测试漫画竖排对白气泡的从右向左阅读顺序与坐标聚合"""
        img_w, img_h = 1000, 1000
        # 3 列竖排文本，同属一个气泡：
        # Line 1 (右侧): "老师" -> x: [100, 120]
        # Line 2 (中间): "请快看" -> x: [70, 90]
        # Line 3 (左侧): "这个孩子" -> x: [40, 60]
        blocks = [
            {"text": "请快看", "score": 0.8, "xmin": 70, "xmax": 90, "ymin": 100, "ymax": 250},
            {"text": "老师", "score": 0.9, "xmin": 100, "xmax": 120, "ymin": 60, "ymax": 120},
            {"text": "这个孩子", "score": 0.85, "xmin": 40, "xmax": 60, "ymin": 110, "ymax": 280},
        ]

        bubbles = cluster_blocks(blocks, img_w, img_h)
        self.assertEqual(len(bubbles), 1)
        b = bubbles[0]
        # 必须从右到左拼接为 "老师请快看这个孩子"
        self.assertEqual(b["text"], "老师请快看这个孩子")
        self.assertEqual(b["orientation"], "vertical")
        self.assertEqual(b["type"], "dialogue")
        # 归一化百分比坐标检查：ymin=60/1000=0.06, xmin=40/1000=0.04, ymax=280/1000=0.28, xmax=120/1000=0.12
        self.assertEqual(b["box"], [0.06, 0.04, 0.28, 0.12])
        self.assertAlmostEqual(b["confidence"], (0.8 + 0.9 + 0.85) / 3, places=2)

    def test_cluster_blocks_horizontal_narration(self):
        """测试横排旁白/说明文字的从上向下阅读顺序与聚合"""
        img_w, img_h = 1000, 1000
        # 2 行横排文字：
        # Line 1 (上): "第一行旁白" -> y: [500, 520]
        # Line 2 (下): "第二行继续" -> y: [530, 550]
        blocks = [
            {"text": "第二行继续", "score": 0.9, "xmin": 200, "xmax": 400, "ymin": 530, "ymax": 550},
            {"text": "第一行旁白", "score": 0.95, "xmin": 200, "xmax": 400, "ymin": 500, "ymax": 520},
        ]

        bubbles = cluster_blocks(blocks, img_w, img_h)
        self.assertEqual(len(bubbles), 1)
        b = bubbles[0]
        # 必须从上到下拼接为 "第一行旁白第二行继续"
        self.assertEqual(b["text"], "第一行旁白第二行继续")
        self.assertEqual(b["orientation"], "horizontal")
        self.assertEqual(b["box"], [0.5, 0.2, 0.55, 0.4])

    def test_cluster_blocks_separate_bubbles(self):
        """测试空间距离较远的多个气泡保持独立"""
        img_w, img_h = 1000, 1000
        # 气泡 1 (左上角) 与 气泡 2 (右下角)
        blocks = [
            {"text": "左上气泡", "score": 0.9, "xmin": 50, "xmax": 150, "ymin": 50, "ymax": 150},
            {"text": "右下气泡", "score": 0.88, "xmin": 800, "xmax": 900, "ymin": 800, "ymax": 900},
        ]

        bubbles = cluster_blocks(blocks, img_w, img_h)
        self.assertEqual(len(bubbles), 2)
        texts = {b["text"] for b in bubbles}
        self.assertIn("左上气泡", texts)
        self.assertIn("右下气泡", texts)

    def test_parse_page_filter(self):
        """测试单页、列表与连续范围页码解析"""
        self.assertIsNone(parse_page_filter(None))
        self.assertIsNone(parse_page_filter(""))
        self.assertEqual(parse_page_filter("3"), {3})
        self.assertEqual(parse_page_filter("1, 3, 5"), {1, 3, 5})
        self.assertEqual(parse_page_filter("10-13"), {10, 11, 12, 13})
        self.assertEqual(parse_page_filter("1, 5-7, 10"), {1, 5, 6, 7, 10})

    def test_is_valid_ocr_sidecar(self):
        """测试伴生文件合法性与脏缓存自愈判定"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            valid_file = tmp / "valid.ocr.json"
            valid_file.write_text('{"version": 1, "engine": "rapidocr", "bubbles": []}', encoding="utf-8")
            self.assertTrue(is_valid_ocr_sidecar(valid_file))

            # 缺少 engine: rapidocr 的 mock 文件视为非法脏缓存
            mock_file = tmp / "mock.ocr.json"
            mock_file.write_text('{"version": 1, "bubbles": []}', encoding="utf-8")
            self.assertFalse(is_valid_ocr_sidecar(mock_file))

            # 空文件视为非法脏缓存
            empty_file = tmp / "empty.ocr.json"
            empty_file.write_text('', encoding="utf-8")
            self.assertFalse(is_valid_ocr_sidecar(empty_file))

            # 不存在的文件
            self.assertFalse(is_valid_ocr_sidecar(tmp / "nonexistent.ocr.json"))


if __name__ == "__main__":
    unittest.main()
