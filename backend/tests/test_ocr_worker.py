import sys
import unittest
from pathlib import Path

from scripts import ocr_worker
from scripts.ocr_worker import (
    cluster_blocks,
    cuda_ready,
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
        self.assertEqual(parse_page_filter("3"), {3})
        self.assertEqual(parse_page_filter("1, 3, 5"), {1, 3, 5})
        self.assertEqual(parse_page_filter("10-13"), {10, 11, 12, 13})
        self.assertEqual(parse_page_filter("1, 5-7, 10"), {1, 5, 6, 7, 10})

    def test_parse_page_filter_rejects_garbage(self):
        """坏片段必须整体拒绝：忽略它会得到空集，空集又被当成"没给过滤条件"，带 --force 就是全库重提。"""
        import argparse

        for bad in ("abc", "", "1,x", "3-", "-3", "5-2", "0", "1,,2"):
            with self.assertRaises(argparse.ArgumentTypeError, msg=f"--page {bad!r} 不该被接受"):
                parse_page_filter(bad)

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
            empty_file.write_text("", encoding="utf-8")
            self.assertFalse(is_valid_ocr_sidecar(empty_file))

            # 不存在的文件
            self.assertFalse(is_valid_ocr_sidecar(tmp / "nonexistent.ocr.json"))


class TestGPURuntime(unittest.TestCase):
    """CUDA 通道契约（错题本 #137 记的 v3 假通道已随那个包一起删除）"""

    @staticmethod
    def _fake_rapidocr(captured, cpu_part=None):
        """造一个替身引擎：扣下 build_engine 传给 rapidocr 的 params；三段会话默认都在 CUDA 上，
        `cpu_part` 指定的那段模拟"缺 .so 静默退回 CPU"。"""
        from types import SimpleNamespace
        from unittest import mock

        def part(name):
            providers = (
                ["CPUExecutionProvider"] if name == cpu_part else ["CUDAExecutionProvider", "CPUExecutionProvider"]
            )
            return SimpleNamespace(session=SimpleNamespace(session=SimpleNamespace(get_providers=lambda: providers)))

        class Fake:
            def __init__(self, params=None):
                captured["params"] = dict(params or {})
                self.text_det, self.text_cls, self.text_rec = part("det"), part("cls"), part("rec")

        return (
            mock.patch.object(ocr_worker, "RapidOCR", Fake),
            mock.patch.object(ocr_worker, "OCRVersion", mock.MagicMock(PPOCRV6="v6")),
            mock.patch.object(ocr_worker, "ModelType", mock.MagicMock(SMALL="small")),
        )

    def test_gpu_flag_uses_the_real_channel(self):
        """要求 GPU 必须走 `EngineConfig.onnxruntime.use_cuda`；不要求时不许偷开。"""
        captured = {}
        patches = self._fake_rapidocr(captured)
        with patches[0], patches[1], patches[2]:
            ocr_worker.build_engine(True)
            self.assertTrue(captured["params"]["EngineConfig.onnxruntime.use_cuda"])
            captured.clear()
            ocr_worker.build_engine(False)
            self.assertNotIn("EngineConfig.onnxruntime.use_cuda", captured["params"])

    def test_gpu_request_fails_when_any_session_falls_back_to_cpu(self):
        """providers 列表与会话创建都不报错、只有会话实际落在哪才算数：任一段退回 CPU 就必须抛错，
        否则横幅印着 GPU、整批实际跑 CPU（审查实测过的静默降级）。"""
        for part in ("det", "cls", "rec"):
            patches = self._fake_rapidocr({}, cpu_part=part)
            with patches[0], patches[1], patches[2]:
                with self.assertRaises(RuntimeError) as ctx:
                    ocr_worker.build_engine(True)
                self.assertIn(part.capitalize(), str(ctx.exception), "报错必须指明是哪一段没在 GPU 上")
                # 不要求 GPU 时不做这道校验：CPU 线本来就该跑在 CPU 上
                ocr_worker.build_engine(False)

    def test_min_score_goes_to_the_engine(self):
        """阈值必须交给引擎：引擎出结果前先按 Global.text_score 滤一遍，事后再滤只能调高、调不低。"""
        captured = {}
        patches = self._fake_rapidocr(captured)
        with patches[0], patches[1], patches[2]:
            ocr_worker.build_engine(False, 0.3)
            self.assertEqual(captured["params"]["Global.text_score"], 0.3)
            ocr_worker.build_engine(False)
            self.assertEqual(captured["params"]["Global.text_score"], ocr_worker.DEFAULT_MIN_SCORE)

    def test_missing_engine_raises_instead_of_returning_none(self):
        """缺包必须抛错：返回 None 会被上层当成"这页 0 气泡"，整本书安静跑完结果全空。"""
        from unittest import mock

        with mock.patch.object(ocr_worker, "RapidOCR", None), self.assertRaises(RuntimeError):
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
            txts = ["你好呀", "再見"]  # noqa: RUF012 - 模拟引擎输出对象的形状，不会被跨实例共享修改
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

    def test_empty_v6_result_yields_no_rows(self):
        class Empty:
            txts = None
            boxes = None
            scores = None

        self.assertEqual(run_engine(lambda _p: Empty(), Path("x.webp")), [])

    def test_rows_to_blocks_drops_blank_text_but_not_low_scores(self):
        """空白文本丢掉、角点收成外接框；低分行原样保留——门槛归引擎，这里再滤一遍阈值就调不低了。"""
        rows = [
            ([[10.0, 20.0], [90.0, 20.0], [90.0, 60.0], [10.0, 60.0]], " 台词 ", 0.31),
            ([[0.0, 0.0], [1.0, 1.0]], "   ", 0.99),
        ]
        self.assertEqual(
            ocr_worker.rows_to_blocks(rows),
            [{"text": "台词", "score": 0.31, "xmin": 10.0, "xmax": 90.0, "ymin": 20.0, "ymax": 60.0}],
        )


class TestBatchRun(unittest.TestCase):
    """批量主流程：用假引擎跑真实的 main()，书库是一次性临时目录。"""

    def setUp(self):
        import tempfile

        self.data_dir = Path(tempfile.mkdtemp())
        self.library = self.data_dir / "library"

    def tearDown(self):
        import shutil

        shutil.rmtree(self.data_dir, ignore_errors=True)

    def _page(self, rel: str) -> Path:
        from PIL import Image

        path = self.library / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (40, 60), "white").save(path)
        return path

    def _run(self, *argv, fail_on=()):
        """跑一次 main()，返回 (退出码, 建引擎次数)。`fail_on` 里的文件名推理时抛错。"""
        import contextlib
        import io
        import threading
        from unittest import mock

        builds = []
        original_recognize = ocr_worker.recognize_page

        def fake_recognize(img_path, engine, **kwargs):
            if img_path.name in fail_on:
                raise RuntimeError("模拟推理失败")
            return original_recognize(img_path, engine, **kwargs)

        def fake_run_engine(_engine, img_path):
            return [([[1.0, 1.0], [9.0, 1.0], [9.0, 30.0], [1.0, 30.0]], "台词", 0.9)]

        with (
            mock.patch.object(sys, "argv", ["ocr_worker.py", "--data-dir", str(self.data_dir), *argv]),
            mock.patch.object(ocr_worker, "RapidOCR", object()),
            mock.patch.object(ocr_worker, "_thread_local", threading.local()),
            mock.patch.object(ocr_worker, "build_engine", lambda *a: builds.append(1) or object()),
            mock.patch.object(ocr_worker, "run_engine", fake_run_engine),
            mock.patch.object(ocr_worker, "recognize_page", fake_recognize),
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            code = ocr_worker.main()
        return code, len(builds)

    def test_every_source_directory_is_scanned(self):
        """图源按 library/ 下的实际目录遍历：清单写死时，后接入的 copymanga 批量跑永远扫不到。"""
        self._page("jm/1/pages/00001.png")
        page = self._page("copymanga/slug/pages/c1/00001.png")
        self.assertEqual(0, self._run()[0])
        self.assertTrue(page.with_name("00001.ocr.json").is_file(), "copymanga 的画页没有被提取")
        self.assertEqual(
            [("copymanga", "slug"), ("jm", "1")],
            [(src, sid) for src, sid, _ in ocr_worker.list_comics(self.library)],
        )
        # 限定一个不存在的图源要报错，而不是安静地"未发现待处理漫画"
        self.assertEqual(1, self._run("--source", "nope")[0])

    def test_multi_chapter_pages_keep_chapter_order_and_refuse_page_filter(self):
        """多章节本各话都有 00001：只按文件名排会把两话交错，页码也指不到唯一一页。"""
        for rel in ("c1/00001.png", "c1/00002.png", "c2/00001.png"):
            self._page(f"local/multi/pages/{rel}")
        comic = self.library / "local" / "multi"
        order = [f"{img.parent.name}/{img.name}" for img, _ in ocr_worker.collect_comic_pages(comic)]
        self.assertEqual(["c1/00001.png", "c1/00002.png", "c2/00001.png"], order)
        with self.assertRaises(ValueError):
            ocr_worker.collect_comic_pages(comic, page_filter={1})

        # 批量带 --page 遇到多章节本：这一本不处理、整批以失败退出，单章节本照常
        single = self._page("jm/1/pages/00001.png")
        self.assertEqual(1, self._run("--page", "1")[0])
        self.assertTrue(single.with_name("00001.ocr.json").is_file())
        self.assertEqual([], list(comic.rglob("*.ocr.json")), "多章节本不该被按错的页码提取")

    def test_failed_page_leaves_no_sidecar_and_fails_the_run(self):
        """推理失败的页不许记成"0 条对白"：不留侧车（下次重试），整批退出码非 0。"""
        good = self._page("jm/1/pages/00001.png")
        bad = self._page("jm/1/pages/00002.png")
        code, _ = self._run(fail_on={"00002.png"})
        self.assertEqual(1, code)
        self.assertTrue(good.with_name("00001.ocr.json").is_file())
        self.assertFalse(bad.with_name("00002.ocr.json").exists())
        self.assertEqual([], list(self.library.rglob("*.tmp")))
        # 重跑同一条命令只补失败的那一页
        self.assertEqual(0, self._run()[0])
        self.assertTrue(bad.with_name("00002.ocr.json").is_file())

    def test_limit_counts_only_comics_with_pending_pages(self):
        """--limit 只数确有待提取画页的本：先截断再跳过的话，反复跑 --limit 1 永远卡在已完成的第一本。"""
        for sid in ("1", "2", "3"):
            self._page(f"jm/{sid}/pages/00001.png")
        for expected in (1, 2, 3, 3):
            self.assertEqual(0, self._run("--limit", "1")[0])
            self.assertEqual(expected, len(list(self.library.rglob("*.ocr.json"))))

    def test_limit_continues_past_comics_with_only_failed_pages(self):
        """永久失败的第一页不占产出名额，重跑 --limit 1 仍能逐批处理后面的书。"""
        self._page("jm/1/pages/bad.png")
        for sid in ("2", "3"):
            self._page(f"jm/{sid}/pages/good.png")
        for expected in (1, 2, 2):
            self.assertEqual(1, self._run("--limit", "1", fail_on={"bad.png"})[0])
            self.assertEqual(expected, len(list(self.library.rglob("*.ocr.json"))))

    def test_limit_counts_a_comic_that_produces_pages_despite_partial_failure(self):
        """部分成功的本占一个名额；下一轮只剩失败页时不再挡住后续书籍。"""
        self._page("jm/1/pages/bad.png")
        self._page("jm/1/pages/good.png")
        next_page = self._page("jm/2/pages/good.png")
        self.assertEqual(1, self._run("--limit", "1", fail_on={"bad.png"})[0])
        self.assertFalse(next_page.with_name("good.ocr.json").exists())
        self.assertEqual(1, self._run("--limit", "1", fail_on={"bad.png"})[0])
        self.assertTrue(next_page.with_name("good.ocr.json").is_file())

    def test_invalid_scope_is_rejected_before_engine_initialization(self):
        from unittest import mock

        self._page("jm/1/pages/00001.png")
        for argv in (
            ("--data-dir", str(self.data_dir / "missing")),
            ("--source", "missing"),
            ("--source", "jm", "--id", "missing"),
            ("--id", "missing"),
        ):
            with self.subTest(argv=argv), mock.patch.dict(sys.modules, {"app.db": None}):
                code, builds = self._run(*argv, "--force")
                self.assertEqual(1, code)
                self.assertEqual(0, builds)
                self.assertEqual([], list(self.library.rglob("*.ocr.json")))

    def test_engines_are_built_once_per_thread_not_per_comic(self):
        """线程池全程只有一个：每本各建一个池，就等于每本都重建一轮引擎。"""
        for sid in ("1", "2", "3", "4"):
            for name in ("00001.png", "00002.png"):
                self._page(f"jm/{sid}/pages/{name}")
        code, builds = self._run("--workers", "2")
        self.assertEqual(0, code)
        self.assertEqual(8, len(list(self.library.rglob("*.ocr.json"))))
        self.assertLessEqual(builds, 3, "主线程预热 1 次 + 2 个工作线程各 1 次")

    def test_malformed_bubble_structure_is_reextracted(self):
        import json

        page = self._page("jm/1/pages/page.png")
        output = page.with_name("page.ocr.json")
        for bubble in (None, {}, {"text": "台词", "box": [0, 1]}, {"text": "台词", "box": [0, 0, float("nan"), 1]}):
            with self.subTest(bubble=bubble):
                output.write_text(json.dumps({"engine": "rapidocr", "bubbles": [bubble]}))
                self.assertFalse(ocr_worker.is_valid_ocr_sidecar(output))
                self.assertEqual(0, self._run()[0])
                self.assertTrue(ocr_worker.sidecar_is_fresh(page, output))

    def test_extraction_threshold_and_revision_invalidate_cached_sidecars(self):
        import json
        from unittest import mock

        page = self._page("jm/1/pages/page.png")
        output = page.with_name("page.ocr.json")
        self.assertEqual(0, self._run()[0])
        self.assertTrue(ocr_worker.sidecar_is_fresh(page, output))
        self.assertFalse(ocr_worker.sidecar_is_fresh(page, output, min_score=0.3))
        with mock.patch.object(ocr_worker, "EXTRACTION_VERSION", 999):
            self.assertFalse(ocr_worker.sidecar_is_fresh(page, output))
        legacy = json.loads(output.read_text())
        legacy.pop("extraction_config")
        output.write_text(json.dumps(legacy))
        self.assertFalse(ocr_worker.sidecar_is_fresh(page, output))

    def test_image_budgets_reject_before_decoding_or_inference(self):
        from unittest import mock

        page = self._page("jm/1/pages/budget.png")
        for budget in (
            mock.patch.object(ocr_worker, "MAX_IMAGE_BYTES", 1),
            mock.patch.object(ocr_worker, "MAX_IMAGE_PIXELS", 1),
        ):
            with (
                budget,
                mock.patch.object(ocr_worker, "run_engine") as engine,
                self.assertRaisesRegex(ValueError, "预算"),
            ):
                ocr_worker.recognize_page(page, object())
            engine.assert_not_called()

    def test_oversized_ocr_output_preserves_existing_sidecar(self):
        from unittest import mock

        page = self._page("jm/1/pages/output.png")
        self.assertEqual(0, self._run()[0])
        output = page.with_name("output.ocr.json")
        before = output.read_bytes()
        with mock.patch.object(ocr_worker, "MAX_SIDECAR_BYTES", 1):
            self.assertEqual(1, self._run("--force")[0])
        self.assertEqual(before, output.read_bytes())

    def test_image_replaced_during_inference_keeps_old_output(self):
        from unittest import mock

        from PIL import Image

        page = self._page("jm/1/pages/page.png")
        self.assertEqual(0, self._run()[0])
        output = page.with_name("page.ocr.json")
        before = output.read_bytes(), output.stat().st_mtime_ns

        def replace_during_inference(*_args):
            Image.new("RGB", (80, 90), "black").save(page)
            return []

        with (
            mock.patch.object(ocr_worker, "get_engine", return_value=object()),
            mock.patch.object(ocr_worker, "run_engine", side_effect=replace_during_inference),
            self.assertRaisesRegex(RuntimeError, "画页发生变化"),
        ):
            ocr_worker.process_image(page, output, root=self.data_dir)
        self.assertEqual(before, (output.read_bytes(), output.stat().st_mtime_ns))
        self.assertFalse(ocr_worker.sidecar_is_fresh(page, output))

    def test_late_image_change_cannot_make_old_results_fresh(self):
        from unittest import mock

        from PIL import Image

        from app.file_io import write_json_atomic

        page = self._page("jm/1/pages/page.png")
        output = page.with_name("page.ocr.json")

        def change_before_publish(path, payload, **kwargs):
            Image.new("RGB", (80, 90), "black").save(page)
            write_json_atomic(path, payload, **kwargs)

        with (
            mock.patch.object(ocr_worker, "get_engine", return_value=object()),
            mock.patch.object(ocr_worker, "run_engine", return_value=[]),
            mock.patch.object(ocr_worker, "write_json_atomic", side_effect=change_before_publish),
        ):
            self.assertEqual(0, ocr_worker.process_image(page, output, root=self.data_dir))
        self.assertFalse(ocr_worker.sidecar_is_fresh(page, output))

    def test_ambiguous_library_names_fail_before_extraction(self):
        self._page("jm/book..1/pages/page.png")
        self._page("jm/book_1/pages/page.png")
        self.assertEqual((1, 0), self._run())
        self.assertEqual([], list(self.library.rglob("*.ocr.json")))
        self.assertEqual(0, self._run("--source", "jm", "--id", "book_1")[0])

    def test_additional_formats_use_the_current_pillow_decoders(self):
        from app.ocr.files import image_extensions

        extensions = image_extensions()
        for extension in (".gif", ".bmp", ".avif", ".tif", ".tiff", ".ico", ".jfif"):
            self.assertIn(extension, extensions)
            self._page(f"plain/image-{extension[1:]}{extension}")
        self.assertEqual(0, self._run("--directory", str(self.library / "plain"))[0])
        self.assertEqual(7, len(list((self.library / "plain").glob("*.ocr.json"))))
        self.assertTrue({".pdf", ".svg", ".eps", ".ps", ".wmf", ".emf", ".mpeg", ".h5"}.isdisjoint(extensions))

    def test_multiframe_images_use_only_the_first_frame(self):
        from unittest import mock

        from PIL import Image

        first = Image.new("RGB", (30, 40), "white")
        second = Image.new("RGB", (30, 40), "black")
        for extension in (".gif", ".tiff"):
            path = self.data_dir / f"frames{extension}"
            first.save(path, save_all=True, append_images=[second])

            def check_first_frame(_engine, image):
                self.assertEqual((255, 255, 255), image.convert("RGB").getpixel((0, 0)))
                return []

            with mock.patch.object(ocr_worker, "run_engine", side_effect=check_first_frame):
                self.assertEqual((30, 40), ocr_worker.recognize_page(path, object())[0:2])

    def test_exif_orientation_is_applied_before_coordinate_normalization(self):
        from unittest import mock

        from PIL import Image

        path = self.data_dir / "rotated.jpg"
        exif = Image.Exif()
        exif[274] = 6
        Image.new("RGB", (30, 40), "white").save(path, exif=exif)
        with mock.patch.object(ocr_worker, "run_engine", return_value=[]):
            self.assertEqual((40, 30), ocr_worker.recognize_page(path, object())[0:2])

    def test_document_disguised_as_image_is_rejected_before_rendering(self):
        from unittest import mock

        from PIL import Image

        path = self.data_dir / "disguised.jpg"
        Image.new("RGB", (30, 40), "white").save(path, format="EPS")
        with mock.patch.object(ocr_worker, "run_engine") as infer, self.assertRaisesRegex(ValueError, "光栅图片"):
            ocr_worker.recognize_page(path, object())
        infer.assert_not_called()

    def test_plain_directory_is_recursive_incremental_and_skips_hidden_and_symlink_items(self):
        good = self._page("plain/chapter/page.png")
        hidden = self._page("plain/.hidden/page.png")
        outside = self._page("outside/page.png")
        plain = self.library / "plain"
        (plain / "linked-directory").symlink_to(outside.parent, target_is_directory=True)
        (plain / "linked-image.png").symlink_to(outside)
        self.assertEqual(0, self._run("--directory", str(plain))[0])
        output = good.with_name("page.ocr.json")
        self.assertTrue(output.is_file())
        self.assertEqual(good.stat().st_mode & 0o777, output.stat().st_mode & 0o777)
        self.assertFalse(hidden.with_name("page.ocr.json").exists())
        self.assertFalse(outside.with_name("page.ocr.json").exists())
        before = output.read_bytes(), output.stat().st_mtime_ns
        code, builds = self._run("--directory", str(plain))
        self.assertEqual((0, 0), (code, builds))
        self.assertEqual(before, (output.read_bytes(), output.stat().st_mtime_ns))
        self.assertFalse((plain / "album.json").exists(), "普通目录提取不能自动收录漫画")
        self.assertEqual([], list(self.data_dir.glob("*.db")))

    def test_plain_directory_does_not_require_a_library_or_valid_data_environment(self):
        import contextlib
        import io
        import os
        from unittest import mock

        page = self._page("plain/page.png")
        with (
            mock.patch.dict(os.environ, {"COMIC_SHELF_DATA": str(self.data_dir / "missing")}),
            mock.patch.object(sys, "argv", ["ocr", "--directory", str(page.parent), "--check"]),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(0, ocr_worker.main())

    def test_same_stem_images_are_rejected_before_inference(self):
        png = self._page("jm/1/pages/page.png")
        self._page("jm/1/pages/page.jpg")
        for args in ((), ("--directory", str(png.parent)), ("--image", str(png))):
            with self.subTest(args=args):
                self.assertEqual((1, 0), self._run(*args))
                self.assertEqual([], list(png.parent.glob("*.ocr.json")))

    def test_force_failure_preserves_valid_output_and_cleans_partial_temp_files(self):
        from unittest import mock

        page = self._page("jm/1/pages/page.png")
        self.assertEqual(0, self._run()[0])
        output = page.with_name("page.ocr.json")
        before = output.read_bytes(), output.stat().st_mtime_ns

        with mock.patch("app.file_io.os.fsync", side_effect=OSError("模拟刷盘失败")):
            self.assertEqual(1, self._run("--force")[0])
        self.assertEqual(before, (output.read_bytes(), output.stat().st_mtime_ns))
        self.assertEqual([], list(page.parent.glob("*.tmp")))
        with mock.patch("app.file_io.os.replace", side_effect=OSError("模拟替换失败")):
            self.assertEqual(1, self._run("--force")[0])
        self.assertEqual(before, (output.read_bytes(), output.stat().st_mtime_ns))
        self.assertEqual([], list(page.parent.glob("*.tmp")))

    def test_concurrent_writers_use_distinct_temp_files(self):
        import os
        import threading
        from concurrent.futures import ThreadPoolExecutor
        from unittest import mock

        page = self._page("jm/1/pages/page.png")
        output = page.with_name("page.ocr.json")
        barrier = threading.Barrier(2)
        names = []
        original_open, original_replace = os.open, os.replace

        def spy_open(path, flags, *args, **kwargs):
            if flags & os.O_EXCL:
                names.append(str(path))
            return original_open(path, flags, *args, **kwargs)

        def synchronized_replace(*args, **kwargs):
            barrier.wait(timeout=5)
            return original_replace(*args, **kwargs)

        with (
            mock.patch.object(ocr_worker, "get_engine", return_value=object()),
            mock.patch.object(ocr_worker, "run_engine", return_value=[]),
            mock.patch("app.file_io.os.open", spy_open),
            mock.patch("app.file_io.os.replace", synchronized_replace),
            ThreadPoolExecutor(max_workers=2) as pool,
        ):
            futures = [pool.submit(ocr_worker.process_image, page, output) for _ in range(2)]
            self.assertEqual([0, 0], [future.result(timeout=10) for future in futures])
        self.assertEqual(2, len(set(names)))
        self.assertTrue(ocr_worker.is_valid_ocr_sidecar(output))
        self.assertEqual([], list(page.parent.glob("*.tmp")))


class TestOCRInstall(unittest.TestCase):
    """用真实解释器和 uv 替身运行安装脚本，验证路径保护，不安装任何包。"""

    def test_gpu_install_rejects_application_environment_aliases(self):
        import os
        import shutil
        import subprocess
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "scripts").mkdir()
            shutil.copyfile(Path(__file__).resolve().parents[2] / "scripts/ocr.sh", root / "scripts/ocr.sh")
            (root / ".venv").symlink_to(sys.prefix, target_is_directory=True)
            (root / "application-link").symlink_to(root / ".venv", target_is_directory=True)
            bin_dir = root / "stub-bin"
            bin_dir.mkdir()
            uv = bin_dir / "uv"
            uv.write_text('#!/bin/sh\nprintf "%s" "$UV_PROJECT_ENVIRONMENT" > "$OCR_TEST_UV_LOG"\nexit 73\n')
            uv.chmod(0o755)
            log = root / "uv-called"
            env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}", "OCR_TEST_UV_LOG": str(log)}
            for target in (".venv", ".venv/../.venv", "application-link", str(root / "application-link") + "/"):
                with self.subTest(target=target):
                    result = subprocess.run(
                        ["bash", "scripts/ocr.sh", "install", "--gpu"],
                        cwd=root,
                        env={**env, "COMIC_SHELF_OCR_VENV": target},
                        capture_output=True,
                        text=True,
                        timeout=10,
                        check=False,
                    )
                    self.assertEqual(1, result.returncode, result.stdout + result.stderr)
                    self.assertIn("指向了应用环境本身", result.stderr)
                    self.assertFalse(log.exists(), "路径保护失效，已调用 uv 修改应用环境")

            # 对照：允许一个尚不存在的独立环境进入安装步骤，替身在改环境之前停止。
            result = subprocess.run(
                ["bash", "scripts/ocr.sh", "install", "--gpu"],
                cwd=root,
                env={**env, "COMIC_SHELF_OCR_VENV": ".venv-ocr/"},
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            self.assertEqual(73, result.returncode, result.stdout + result.stderr)
            self.assertEqual(str(root / ".venv-ocr"), log.read_text())

    def test_test_command_uses_the_worker_data_directory_resolver(self):
        """自动试跑选图必须调用共享探测函数，不能另按 shell 环境变量选一个书库。"""
        import os
        import shutil
        import subprocess
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scripts = root / "scripts"
            scripts.mkdir()
            shutil.copyfile(Path(__file__).resolve().parents[2] / "scripts/ocr.sh", scripts / "ocr.sh")
            (root / ".venv").symlink_to(sys.prefix, target_is_directory=True)
            (root / "backend/app").mkdir(parents=True)
            (root / "backend/app/__init__.py").touch()
            (root / "backend/app/ocr").mkdir()
            (root / "backend/app/ocr/__init__.py").touch()
            (root / "backend/app/ocr/files.py").write_text(
                'from pathlib import Path\ndef resolve_data_dir(): return Path("chosen-data").resolve()\ndef image_extensions(): return {".png"}\ndef scan_files(root, exts): return sorted(root.rglob("*.png"))\n'
            )
            (scripts / "ocr_lines.py").write_text('import sys\nprint("IMAGE=" + sys.argv[-1])\n')
            page = root / "chosen-data/library/jm/1/pages/00001.png"
            page.parent.mkdir(parents=True)
            page.touch()
            wrong_data = root / "other-data"
            wrong_data.mkdir()
            result = subprocess.run(
                ["bash", "scripts/ocr.sh", "test", "--cpu"],
                cwd=root,
                env={**os.environ, "COMIC_SHELF_DATA": str(wrong_data)},
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertIn(f"IMAGE={page}", result.stdout)


class TestDependencyIsolation(unittest.TestCase):
    """OCR 提取是算力机上的离线工具，不是运行时：它的依赖不许进生产镜像（docs/PITFALLS.md #168）。"""

    ROOT = Path(__file__).resolve().parents[2]
    HEAVY = ("onnxruntime", "rapidocr", "opencv", "nvidia", "numpy")

    def _closure(self, group: str | None) -> set[str]:
        """按 uv.lock 展开一组依赖的全部传递依赖。`group=None` 即运行时依赖（Dockerfile 装的那一份）。"""
        import tomllib

        lock = tomllib.loads((self.ROOT / "uv.lock").read_text(encoding="utf-8"))
        packages: dict[str, list[dict]] = {}
        for pkg in lock["package"]:
            packages.setdefault(pkg["name"], []).append(pkg)
        root = packages["paper-room"][0]
        todo = list(root["dev-dependencies"][group] if group else root["dependencies"])
        seen: set[str] = set()
        while todo:
            dep = todo.pop()
            for pkg in packages[dep["name"]]:
                todo.extend(pkg.get("dependencies", []))
                for extra in dep.get("extra", []):
                    todo.extend(pkg.get("optional-dependencies", {}).get(extra, []))
            seen.add(dep["name"])
        return seen

    def test_runtime_image_carries_no_ocr_dependency(self):
        runtime = self._closure(None)
        heavy = sorted(n for n in runtime if n.startswith(self.HEAVY))
        self.assertEqual([], heavy, "推理依赖漏进了运行时依赖表，生产镜像会跟着变大")
        # 对照：同一套展开逻辑在 OCR 组上确实找得到这些包，上面的"没有"才算数
        self.assertTrue({"rapidocr", "onnxruntime", "opencv-python"} <= self._closure("ocr"))
        self.assertTrue({"rapidocr", "onnxruntime-gpu", "nvidia-cudnn-cu13"} <= self._closure("ocr-gpu"))

    def test_image_and_dev_setup_never_install_the_ocr_groups(self):
        """两个 OCR 组必须保持"点名才装"：不是默认组，Dockerfile 与 setup:py 的同步命令也不带组。"""
        import json
        import tomllib

        pyproject = tomllib.loads((self.ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertNotIn("default-groups", pyproject["tool"]["uv"], "默认组一旦含 ocr，每次同步都会装上推理依赖")
        dockerfile = (self.ROOT / "Dockerfile").read_text(encoding="utf-8")
        setup_py = json.loads((self.ROOT / "package.json").read_text(encoding="utf-8"))["scripts"]["setup:py"]
        for where, text in (("Dockerfile", dockerfile), ("setup:py", setup_py)):
            self.assertIn("uv sync", text)
            self.assertNotRegex(text, r"--(only-)?group|--all-groups", f"{where} 的同步命令不许带依赖组")

    def test_cpu_and_gpu_groups_cannot_be_installed_together(self):
        """两个 onnxruntime wheel 共用一个包目录，混装后 CUDA 静默失效；互斥声明让 uv 直接拒绝。"""
        import tomllib

        conflicts = tomllib.loads((self.ROOT / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["uv"]["conflicts"]
        self.assertIn([{"group": "ocr"}, {"group": "ocr-gpu"}], conflicts)
        self.assertNotIn("onnxruntime", self._closure("ocr-gpu"), "GPU 组里混进了 CPU 版 onnxruntime")

    def test_cpu_and_gpu_shared_dependencies_have_identical_pins(self):
        """共用直接依赖升级必须同步，不能靠互斥组让 uv 各锁一个识别版本。"""
        import tomllib

        groups = tomllib.loads((self.ROOT / "pyproject.toml").read_text(encoding="utf-8"))["dependency-groups"]
        versions = {}
        for group in ("ocr", "ocr-gpu"):
            versions[group] = {}
            for requirement in groups[group]:
                name, equal, version = requirement.partition("==")
                self.assertEqual("==", equal, f"{group} 的依赖必须精确锁定: {requirement}")
                versions[group][name.split("[", 1)[0]] = version
        shared = versions["ocr"].keys() & versions["ocr-gpu"].keys()
        self.assertTrue({"pillow", "rapidocr"} <= shared)
        for name in shared:
            self.assertEqual(versions["ocr"][name], versions["ocr-gpu"][name], f"两条线的 {name} 版本不一致")


class TestDataDirectory(unittest.TestCase):
    """书库目录解析的错误与优先级，所有目录都只读或来自一次性目录。"""

    def test_explicit_invalid_directory_never_falls_back(self):
        import os
        import tempfile
        from unittest import mock

        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"COMIC_SHELF_DATA": tmp}):
            file = Path(tmp) / "file"
            file.touch()
            for path in ("", "  ", str(Path(tmp) / "missing"), str(file)):
                with self.subTest(path=path), self.assertRaises(ValueError):
                    ocr_worker.resolve_data_dir(path)

    def test_explicit_directory_overrides_invalid_environment(self):
        import os
        import tempfile
        from unittest import mock

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"COMIC_SHELF_DATA": str(Path(tmp) / "missing")}):
                with self.assertRaises(ValueError):
                    ocr_worker.resolve_data_dir()
                self.assertEqual(Path(tmp).resolve(), ocr_worker.resolve_data_dir(tmp))
                self.assertEqual(Path.home().resolve(), ocr_worker.resolve_data_dir("~"))


class TestCommandLine(unittest.TestCase):
    def test_sync_preserves_single_book_selection_and_deleted_book_cleanup(self):
        """同步脚本只给 --id 也必须限定书号，点名已删除的本仍可清理其残留索引。"""
        import subprocess
        import tempfile
        import textwrap

        script = textwrap.dedent("""
            import shutil
            import sys
            from unittest import mock
            from scripts import sync_ocr
            from tests.test_ocr_worker import TestBatchRun

            case = TestBatchRun()
            case.setUp()
            try:
                for sid in ("1", "2"):
                    case._page(f"jm/{sid}/pages/00001.png")
                assert case._run()[0] == 0
                with mock.patch.object(sys, "argv", ["sync", "--data-dir", str(case.data_dir), "--id", "1"]):
                    sync_ocr.main()
                from app.db import get_dialogue_db
                with get_dialogue_db() as conn:
                    assert conn.execute("SELECT source_id FROM comic_dialogues_fts").fetchone()[0] == "1"
                    assert conn.execute("SELECT count(*) FROM comic_dialogues_fts").fetchone()[0] == 1
                shutil.rmtree(case.library / "jm/1")
                with mock.patch.object(sys, "argv", [
                    "sync", "--data-dir", str(case.data_dir), "--source", "jm", "--id", "1", "--no-cleanup"
                ]):
                    sync_ocr.main()
                with get_dialogue_db() as conn:
                    assert conn.execute("SELECT count(*) FROM comic_dialogues_fts").fetchone()[0] == 0
            finally:
                case.tearDown()
        """)
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [sys.executable, "-c", script],
                cwd=tmp,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_all_ocr_commands_reject_empty_scope_and_path_arguments(self):
        import contextlib
        import io
        from unittest import mock

        from scripts import ocr_lines, sync_ocr

        commands = (
            (ocr_worker.main, ("--source", "--id", "--data-dir", "--image", "--directory")),
            (ocr_lines.main, ("--source", "--id", "--data-dir", "--image", "--recluster", "--out")),
            (sync_ocr.main, ("--source", "--id", "--data-dir")),
        )
        for main, flags in commands:
            for flag in flags:
                for value in ("", " \t "):
                    with (
                        self.subTest(command=main.__module__, flag=flag, value=value),
                        mock.patch.object(sys, "argv", ["ocr", flag, value]),
                        contextlib.redirect_stderr(io.StringIO()),
                        self.assertRaises(SystemExit) as error,
                    ):
                        main()
                    self.assertEqual(2, error.exception.code)

    def test_scope_arguments_cannot_escape_the_library(self):
        import contextlib
        import io
        from unittest import mock

        for flag in ("--source", "--id"):
            for value in (".", "..", "../jm", "jm/1", "jm\\1", "book..1", "中文", "book name", "_book", "book_"):
                with (
                    self.subTest(flag=flag, value=value),
                    mock.patch.object(sys, "argv", ["ocr", flag, value, "--force"]),
                    contextlib.redirect_stderr(io.StringIO()),
                    self.assertRaises(SystemExit) as error,
                ):
                    ocr_worker.main()
                self.assertEqual(2, error.exception.code)

    def test_all_ocr_commands_reject_invalid_explicit_directory(self):
        import contextlib
        import io
        import os
        import tempfile
        from unittest import mock

        from scripts import ocr_lines, sync_ocr

        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"COMIC_SHELF_DATA": tmp}):
            (Path(tmp) / "library").mkdir()
            for main in (ocr_worker.main, ocr_lines.main, sync_ocr.main):
                with (
                    self.subTest(command=main.__module__),
                    mock.patch.object(sys, "argv", ["ocr", "--data-dir", str(Path(tmp) / "missing")]),
                    contextlib.redirect_stdout(io.StringIO()),
                    contextlib.redirect_stderr(io.StringIO()),
                ):
                    if main is sync_ocr.main:
                        with self.assertRaises(SystemExit) as error:
                            main()
                        self.assertEqual(2, error.exception.code)
                    else:
                        self.assertEqual(1, main())
                self.assertEqual([], list(Path(tmp).glob("*.db")))

    def test_bad_page_spec_stops_before_any_work(self):
        """--page 写错要在参数解析阶段就退出，不进入任何处理。"""
        import contextlib
        import io
        from unittest import mock

        with mock.patch.object(sys, "argv", ["ocr_worker.py", "--page", "abc", "--force"]):
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as ctx:
                    ocr_worker.main()
        self.assertEqual(2, ctx.exception.code)

    def test_removed_http_parameters_are_rejected(self):
        import contextlib
        import io

        for argv in (("--api-url", "http://nas.invalid"), ("--token", "secret")):
            with (
                self.subTest(argv=argv),
                contextlib.redirect_stderr(io.StringIO()),
                self.assertRaises(SystemExit) as error,
            ):
                ocr_worker.build_arg_parser().parse_args(argv)
            self.assertEqual(2, error.exception.code)

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
