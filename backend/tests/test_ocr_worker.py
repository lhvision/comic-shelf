import sys
import unittest
from pathlib import Path

# Add project root and backend to sys.path
backend_dir = Path(__file__).resolve().parent.parent
root_dir = backend_dir.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from scripts import ocr_worker
from scripts.ocr_worker import (
    cluster_blocks,
    collect_comic_pages,
    cuda_ready,
    get_library_stats,
    is_valid_ocr_sidecar,
    parse_page_filter,
    run_engine,
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

    def test_cluster_blocks_pages_sort_bubbles_right_to_left(self):
        """测试竖排页内气泡按自右向左分栏排序，且 id/order 与输出次序一致"""
        img_w, img_h = 1000, 1000
        # 检测模型先输出左栏、再输出右栏：入库顺序必须以右栏为先
        blocks = [
            {"text": "左栏台词", "score": 0.9, "xmin": 100, "xmax": 200, "ymin": 400, "ymax": 600},
            {"text": "右栏台词", "score": 0.88, "xmin": 600, "xmax": 700, "ymin": 100, "ymax": 300},
        ]

        bubbles = cluster_blocks(blocks, img_w, img_h)
        self.assertEqual([b["text"] for b in bubbles], ["右栏台词", "左栏台词"])
        self.assertEqual([b["id"] for b in bubbles], [1, 2])
        self.assertEqual([b["order"] for b in bubbles], [1, 2])

    def test_cluster_blocks_pages_sort_bubbles_top_to_bottom(self):
        """测试横排页内气泡按自上而下分行排序"""
        img_w, img_h = 1000, 1000
        blocks = [
            {"text": "下行", "score": 0.9, "xmin": 100, "xmax": 400, "ymin": 500, "ymax": 560},
            {"text": "上行", "score": 0.9, "xmin": 100, "xmax": 400, "ymin": 100, "ymax": 160},
        ]

        bubbles = cluster_blocks(blocks, img_w, img_h)
        self.assertEqual([b["text"] for b in bubbles], ["上行", "下行"])

    def test_cluster_blocks_same_column_staggered_x_keeps_vertical_order(self):
        """同一竖栏内 xmin 彼此错开时，必须仍按自上而下读，而非被单轴 x 排序打散"""
        img_w, img_h = 1000, 1000
        # 三个气泡同处右侧一栏（x 区间大幅重叠），纵向自上排布且 xmin 各异
        blocks = [
            {"text": "栏底", "score": 0.9, "xmin": 610, "xmax": 660, "ymin": 800, "ymax": 950},
            {"text": "栏中", "score": 0.9, "xmin": 620, "xmax": 720, "ymin": 450, "ymax": 600},
            {"text": "栏顶", "score": 0.9, "xmin": 600, "xmax": 700, "ymin": 100, "ymax": 250},
        ]

        bubbles = cluster_blocks(blocks, img_w, img_h)
        self.assertEqual(len(bubbles), 3)
        self.assertEqual([b["text"] for b in bubbles], ["栏顶", "栏中", "栏底"])
        self.assertEqual([b["order"] for b in bubbles], [1, 2, 3])

    def test_cluster_blocks_rejects_oversized_sound_effect(self):
        """拟声词字号远大于台词时不许并进气泡（真库：jm/1022074 p66 的"章"糊进对白）。"""
        img_w, img_h = 1280, 1808
        blocks = [
            # 大号拟声词：列宽 140
            {"text": "轰", "score": 0.9, "xmin": 900, "xmax": 1040, "ymin": 300, "ymax": 560},
            # 普通台词列：列宽 50，与拟声词横向紧邻且纵向重叠
            {"text": "台词行", "score": 0.9, "xmin": 780, "xmax": 830, "ymin": 300, "ymax": 560},
        ]

        bubbles = cluster_blocks(blocks, img_w, img_h)
        self.assertEqual(len(bubbles), 2)
        self.assertEqual({b["text"] for b in bubbles}, {"轰", "台词行"})

    def test_cluster_blocks_rejects_mixed_orientation(self):
        """一竖一横不许同组：允许拐角的链条会把整页面的字串成一个气泡。"""
        img_w, img_h = 1280, 1808
        blocks = [
            {"text": "竖排对白", "score": 0.9, "xmin": 700, "xmax": 740, "ymin": 300, "ymax": 560},
            {"text": "横排标题", "score": 0.9, "xmin": 760, "xmax": 1000, "ymin": 320, "ymax": 360},
        ]

        bubbles = cluster_blocks(blocks, img_w, img_h)
        self.assertEqual(len(bubbles), 2)

    def test_cluster_blocks_caps_merged_bubble_area(self):
        """间距判据是相对盒子自身的，等距排开的列会无限链下去，必须有绝对面积上限断链。"""
        img_w, img_h = 1000, 1000
        blocks = [
            {
                "text": f"第{n}列",
                "score": 0.9,
                "xmin": 100 + 90 * n,
                "xmax": 140 + 90 * n,
                "ymin": 100,
                "ymax": 800,
            }
            for n in range(6)
        ]

        bubbles = cluster_blocks(blocks, img_w, img_h)
        self.assertGreater(len(bubbles), 1)
        joined = "".join(b["text"] for b in bubbles)
        for n in range(6):
            self.assertIn(f"第{n}列", joined)
        for b in bubbles:
            ymin, xmin, ymax, xmax = b["box"]
            self.assertLessEqual((ymax - ymin) * (xmax - xmin), 0.21)

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


class TestGPURuntime(unittest.TestCase):
    """CUDA 通道契约（错题本 #137 记的 v3 假通道已随那个包一起删除）"""

    @staticmethod
    def _fake_v6(captured):
        """造一个替身引擎，把 build_engine 传给 rapidocr 的 params 扣下来。"""
        from unittest import mock

        class Fake:
            def __init__(self, params=None):
                captured["params"] = dict(params or {})

        return (
            mock.patch.object(ocr_worker, "RapidOCRV6", Fake),
            mock.patch.object(ocr_worker, "V6OCRVersion", mock.MagicMock(PPOCRV6="v6")),
            mock.patch.object(ocr_worker, "V6ModelType", mock.MagicMock(SMALL="small")),
        )

    def test_gpu_flag_uses_the_real_channel(self):
        """要求 GPU 必须走 `EngineConfig.onnxruntime.use_cuda`；不要求时不许偷开。"""
        from unittest import mock

        captured = {}
        patches = self._fake_v6(captured)
        with patches[0], patches[1], patches[2]:
            ocr_worker.build_engine(True)
            self.assertTrue(captured["params"]["EngineConfig.onnxruntime.use_cuda"])
            captured.clear()
            ocr_worker.build_engine(False)
            self.assertNotIn("EngineConfig.onnxruntime.use_cuda", captured["params"])

    def test_missing_engine_raises_instead_of_returning_none(self):
        """缺包必须抛错：返回 None 会被上层当成"这页 0 气泡"，整本书安静跑完结果全空。"""
        from unittest import mock

        with mock.patch.object(ocr_worker, "RapidOCRV6", None):
            with self.assertRaises(RuntimeError):
                ocr_worker.build_engine(False)

    def test_cuda_ready_states_reason_when_unavailable(self):
        """不可用时必须给出原因，否则 --gpu 静默降级成 CPU 跑几个小时无人察觉。"""
        ok, reason = cuda_ready()
        self.assertIsInstance(ok, bool)
        self.assertIsInstance(reason, str)
        if not ok:
            self.assertTrue(reason, "判定 CUDA 不可用时必须说明原因")


class TestEngineAdapter(unittest.TestCase):
    """引擎返回结构必须在这一层吃掉（本轮实测连着炸过两次：numpy 真值判断、float32 序列化）。"""

    class _ArrayLike:
        """模拟 numpy 数组：能迭代、能索引，但真值判断直接抛。"""

        def __init__(self, rows):
            self._rows = rows

        def __iter__(self):
            return iter(self._rows)

        def __getitem__(self, i):
            return self._rows[i]

        def __bool__(self):
            raise ValueError("The truth value of an array with more than one element is ambiguous")

    class _Float32:
        """模拟 numpy float32：不是 JSON 可序列化类型，只能显式 float()。"""

        def __init__(self, v):
            self.v = v

        def __float__(self):
            return float(self.v)

    def test_v6_output_normalizes_boxes_and_scores(self):
        import json

        F = TestEngineAdapter._Float32

        class Output:
            txts = ["你好呀", "再見"]
            # 真实形状：每个气泡是一串 [x, y] 角点，角点分量是 numpy 标量
            boxes = TestEngineAdapter._ArrayLike(
                [
                    [[F(1.5), F(2.5)], [F(3.5), F(4.5)]],
                    [[F(5.0), F(6.0)], [F(7.0), F(8.0)]],
                ]
            )
            scores = TestEngineAdapter._ArrayLike([F(0.91), 0.42])

        class Engine:
            def __call__(self, _path):
                return Output()

        rows = run_engine(Engine(), Path("x.webp"))
        self.assertEqual([t for _, t, _ in rows], ["你好呀", "再見"])
        self.assertEqual(rows[0][1], "你好呀")
        self.assertAlmostEqual(rows[0][2], 0.91, places=3)
        # numpy 类型没被拍平的话，这一行就会抛——侧车写入用的正是 json.dumps
        json.dumps(rows[0][0])
        self.assertEqual(rows[0][0], [[1.5, 2.5], [3.5, 4.5]])

    def test_tuple_output_is_rejected_not_swallowed(self):
        """v3 那种 (results, elapse) 返回值必须当场报错：按对象取属性会拿到 None，
        于是整本书"安静地跑完、结果全空"，这是本轮踩过的那类失败。"""
        with self.assertRaises(TypeError):
            run_engine(lambda _p: ([([[0.0, 0.0], [1.0, 1.0]], "老句子", 0.8)], [0.1]), Path("x.webp"))

    def test_empty_v6_result_yields_no_rows(self):
        class Empty:
            txts = None
            boxes = None
            scores = None

        self.assertEqual(run_engine(lambda _p: Empty(), Path("x.webp")), [])


class TestCommandLine(unittest.TestCase):
    def test_no_engine_track_option_remains(self):
        """引擎必须只剩一条线：只要还留着"轨道"开关，忘了带参数就会把 v3 那种 5 个假名
        的字符表产出的乱码灌进语料，而且没人会察觉。历史 v3 侧车仍合法，不需迁移。
        """
        parser = ocr_worker.build_arg_parser()
        self.assertNotIn("engine", {a.dest for a in parser._actions})
        self.assertEqual("v6", ocr_worker.ENGINE_TRACK)

    def test_help_strings_are_well_formed(self):
        """argparse 会把 help 当格式化串，文案里一个孤零零的 % 就让 worker 启动即崩。

        真实事故：当年 `--engine` 的 help 写了 "+29%"，`ocr.sh run` 直接
        `ValueError: badly formed help string`，而单测从没构造过 parser 所以全绿。
        那个开关已删除，但这条对所有新增 help 文案都成立，故用例留下。
        """
        import contextlib
        import io
        from unittest import mock

        with mock.patch.object(sys, "argv", ["ocr_worker.py", "--help"]):
            with contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as ctx:
                    ocr_worker.main()
        self.assertEqual(0, ctx.exception.code, "--help 应正常渲染（help 文案里的 % 要写成 %%）")


if __name__ == "__main__":
    unittest.main()
