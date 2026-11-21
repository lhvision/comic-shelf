#!/usr/bin/env python3
"""
纸间 (Paper Room) · 高性能机漫画台词 OCR 提取与聚类工作流 Worker
功能：
1. 智能探测数据目录（COMIC_SHELF_DATA -> /mnt/nas_manga -> backend/data）；
2. 批量扫描现有 Pillow 可读的光栅画页（动图 / 多页图片只取首帧），调用 RapidOCR 识别中日文分镜台词；
3. 气泡级多行文本几何聚类（Bubble-level Line Clustering），计算右向左（竖排）/上向下（横排）阅读流与 Union 归一化百分比坐标；
4. 产出伴生文件 {index}.ocr.json；
5. 支持普通图片目录、本地路径与映射盘路径；索引同步由命令入口单独执行。
"""

import argparse
import concurrent.futures
import math
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.file_io import file_stamp, open_regular, read_json, write_json_atomic
from app.ocr_files import (
    collect_comic_pages,
    collect_images,
    image_extensions,
    image_formats,
    image_output,
    list_comics,
    parse_directory_name,
    parse_path,
    resolve_data_dir,
)

# 尝试导入 OCR 与图像依赖
try:
    from PIL import Image
except ImportError:
    Image = None

# 唯一引擎：rapidocr 3.x（PP-OCRv6）。曾经的 v3 轨道（rapidocr-onnxruntime）已删除——
# 它的字符表 6623 字里只有 5 个假名，日文与繁体会被强行写成形似汉字的乱码，而"忘了带
# --engine"就会把这些乱码灌进语料且无人察觉。依赖见 pyproject.toml 的 ocr / ocr-gpu 依赖组。
try:
    from rapidocr import ModelType, OCRVersion, RapidOCR
except ImportError:
    RapidOCR = None
    ModelType = None
    OCRVersion = None


def sort_bubbles_by_reading_order(
    bubbles: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """按整页阅读顺序排定气泡：竖排页自右向左分栏，横排页自上而下分行。

    box 为归一化 [ymin, xmin, ymax, xmax]。
    """
    if len(bubbles) <= 1:
        return list(bubbles)

    vertical = sum(1 for b in bubbles if b["orientation"] == "vertical") * 2 >= len(bubbles)
    sweep_lo, sweep_hi, cross = (1, 3, 0) if vertical else (0, 2, 1)

    # 竖排从右往左读，扫描轴取 xmin 降序；横排从上往下读，取 ymin 升序
    if vertical:
        ordered = sorted(bubbles, key=lambda b: (-b["box"][sweep_lo], b["box"][cross]))
    else:
        ordered = sorted(bubbles, key=lambda b: (b["box"][sweep_lo], b["box"][cross]))

    # 扫描轴上大幅重叠的气泡并入同一栏/同一行，栏内再按交叉轴排。
    # 少了这一步，左右错落的分栏会被单轴排序打散成 Z 字形。
    bands: list[list[dict[str, Any]]] = []
    band_lo = band_hi = 0.0
    for b in ordered:
        lo, hi = b["box"][sweep_lo], b["box"][sweep_hi]
        if bands:
            min_extent = min(band_hi - band_lo, hi - lo)
            if min(band_hi, hi) - max(band_lo, lo) > min_extent * 0.5:
                bands[-1].append(b)
                band_lo, band_hi = min(band_lo, lo), max(band_hi, hi)
                continue
        band_lo, band_hi = lo, hi
        bands.append([b])

    out: list[dict[str, Any]] = []
    for band in bands:
        out.extend(sorted(band, key=lambda b: b["box"][cross]))
    return out


# 识别置信度下限（滤掉拟声词噪点、水印残块）。直接交给引擎的 `Global.text_score`：引擎出结果前
# 就按它丢弃低分行，事后再滤一遍只能把门槛调高、调不低
DEFAULT_MIN_SCORE = 0.5
# 同一气泡内多行的笔画粗细差上限（竖排比列宽、横排比行高）
BUBBLE_THICKNESS_RATIO = 2.0
# 单个气泡外接框占整页面积的上限，超过即判定为链条式误并
BUBBLE_MAX_PAGE_AREA = 0.20


def cluster_blocks(blocks: list[dict[str, Any]], img_w: int, img_h: int) -> list[dict[str, Any]]:
    """
    气泡级多行文本几何聚类算法 (Bubble-level Line Clustering)
    根据几何间距与重合度，将属于同一气泡的多行文字聚合为一条完整对白，并计算归一化坐标 [ymin, xmin, ymax, xmax]
    输出的气泡数组按整页阅读顺序排列，每个气泡带 1 起的 id 与 order。

    邻近判据之外还有三道否决闸，缺一道就会把整页糊成一个气泡（详见错题本 #142）：
    横竖不同的行不许同组（否则链条能在页面上拐角）、笔画粗细差 2 倍不许同组
    （拟声词与标题字号常是台词的 2~3 倍）、合并后的外接框占页面积有硬上限
    （间距判据是相对盒子自身的，大框之间可以无限手拉手，只有绝对面积上限能断链）。
    """
    n = len(blocks)
    if n == 0:
        return []

    parent = list(range(n))
    # comp[root] = [ymin, xmin, ymax, xmax]：该分量当前的外接框，用于合并后的面积上限判定
    comp: dict[int, list[float]] = {i: [b["ymin"], b["xmin"], b["ymax"], b["xmax"]] for i, b in enumerate(blocks)}
    area_cap = img_w * img_h * BUBBLE_MAX_PAGE_AREA

    def find(i: int) -> int:
        if parent[i] == i:
            return i
        parent[i] = find(parent[i])
        return parent[i]

    def union(i: int, j: int) -> None:
        pi, pj = find(i), find(j)
        if pi == pj:
            return
        a, b = comp[pi], comp[pj]
        merged = [min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])]
        if (merged[2] - merged[0]) * (merged[3] - merged[1]) > area_cap:
            return
        parent[pi] = pj
        comp[pj] = merged
        del comp[pi]

    for i in range(n):
        bi = blocks[i]
        wi = bi["xmax"] - bi["xmin"]
        hi = bi["ymax"] - bi["ymin"]
        vi = hi > wi * 1.1
        for j in range(i + 1, n):
            bj = blocks[j]
            wj = bj["xmax"] - bj["xmin"]
            hj = bj["ymax"] - bj["ymin"]
            vj = hj > wj * 1.1

            # 一竖一横不许同组：链条一旦允许拐角，整页面的字就会全部连成一体
            if vi != vj:
                continue
            # 竖排比列宽、横排比行高：拟声词/标题这类大号字与台词的"笔画粗细"差得很远
            ti, tj = (wi, wj) if vi else (hi, hj)
            if max(ti, tj) > min(ti, tj) * BUBBLE_THICKNESS_RATIO:
                continue

            # 1. 竖排文本邻近探测（漫画标准：分镜气泡内多列纵排文本从右向左排列）
            gap_x = max(0, max(bi["xmin"], bj["xmin"]) - min(bi["xmax"], bj["xmax"]))
            overlap_y = max(0, min(bi["ymax"], bj["ymax"]) - max(bi["ymin"], bj["ymin"]))
            min_h = min(hi, hj)
            max_col_w = max(wi, wj)

            # 若横向间距小于列宽的 1.5 倍，且纵向高度有重叠或起点对齐，判定属于同一竖排气泡
            is_adjacent_vertical = gap_x < max_col_w * 1.5 and (
                overlap_y > min_h * 0.3 or abs(bi["ymin"] - bj["ymin"]) < min_h * 0.8
            )

            # 2. 横排文本邻近探测（分镜下方横向对白或方框旁白，从上往下排列）
            gap_y = max(0, max(bi["ymin"], bj["ymin"]) - min(bi["ymax"], bj["ymax"]))
            overlap_x = max(0, min(bi["xmax"], bj["xmax"]) - max(bi["xmin"], bj["xmin"]))
            min_w = min(wi, wj)
            max_line_h = max(hi, hj)

            is_adjacent_horizontal = gap_y < max_line_h * 1.2 and (
                overlap_x > min_w * 0.3 or abs(bi["xmin"] - bj["xmin"]) < min_w * 0.8
            )

            if is_adjacent_vertical or is_adjacent_horizontal:
                union(i, j)

    groups: dict[int, list[dict[str, Any]]] = {}
    for i in range(n):
        root = find(i)
        groups.setdefault(root, []).append(blocks[i])

    results: list[dict[str, Any]] = []
    for g_blocks in groups.values():
        # 判断该气泡是否偏竖排
        v_count = sum(1 for b in g_blocks if (b["ymax"] - b["ymin"]) > (b["xmax"] - b["xmin"]) * 1.1)
        is_vertical = v_count >= len(g_blocks) / 2

        if is_vertical:
            # 竖排漫画阅读流：从右向左读（按 x 坐标降序）
            g_blocks.sort(key=lambda b: -b["xmin"])
        else:
            # 横排漫画阅读流：从上向下读（按 y 坐标升序）
            g_blocks.sort(key=lambda b: b["ymin"])

        full_text = "".join(b["text"] for b in g_blocks).strip()
        if not full_text:
            continue

        avg_score = sum(b["score"] for b in g_blocks) / len(g_blocks)

        ymin = max(0.0, min(1.0, min(b["ymin"] for b in g_blocks) / img_h))
        xmin = max(0.0, min(1.0, min(b["xmin"] for b in g_blocks) / img_w))
        ymax = max(ymin, min(1.0, max(b["ymax"] for b in g_blocks) / img_h))
        xmax = max(xmin, min(1.0, max(b["xmax"] for b in g_blocks) / img_w))

        results.append(
            {
                "box": [round(ymin, 4), round(xmin, 4), round(ymax, 4), round(xmax, 4)],
                "text": full_text,
                "confidence": round(avg_score, 2),
                "orientation": "vertical" if is_vertical else "horizontal",
                "type": "dialogue",
            }
        )

    bubbles = sort_bubbles_by_reading_order(results)
    for order, b in enumerate(bubbles, start=1):
        b["id"] = order
        b["order"] = order
    return bubbles


_thread_local = threading.local()

# --gpu 开关，由 main() 依命令行参数写入，只负责"必须用上 CUDA，否则直接退出"
USE_GPU = False
# --min-score，同样由 main() 写入，各线程建引擎时带上
MIN_SCORE = DEFAULT_MIN_SCORE
# 侧车里记录产出引擎，供混跑后溯源（历史数据里有 v3 与更早无此字段的文件）
ENGINE_TRACK = "v6"


def cuda_ready() -> tuple[bool, str]:
    """预检 GPU 构建装没装上，用不上时说明原因。

    rapidocr 的启用条件是 `use_cuda and get_device()=='GPU' and 'CUDAExecutionProvider'
    in get_available_providers()`，任一不满足都会**静默**退回 CPU；而只装 CPU 版
    onnxruntime 时后两项都不成立，所以这里提前判定，别等跑完几小时才发现是白跑。
    providers 列表是编译期的，这里通过不代表会话真在 GPU 上，那一关由 `build_engine(True)` 把。
    """
    try:
        import onnxruntime as ort
    except ImportError as exc:
        return False, f"当前环境未安装 onnxruntime: {exc}"
    if ort.get_device() != "GPU":
        return False, "onnxruntime 未报告 GPU 设备（多半装成了 CPU 版 onnxruntime）"
    if "CUDAExecutionProvider" not in ort.get_available_providers():
        return False, "onnxruntime 缺少 CUDAExecutionProvider（GPU 构建或 CUDA/cuDNN 运行库未装）"
    return True, ""


def get_engine() -> Any:
    """每个线程独享一个 OCR 推理引擎实例，杜绝多线程状态竞争"""
    if not hasattr(_thread_local, "engine"):
        _thread_local.engine = build_engine(USE_GPU, MIN_SCORE)
    return _thread_local.engine


def build_engine(use_gpu: bool, min_score: float = DEFAULT_MIN_SCORE) -> Any:
    """构造 PP-OCRv6 引擎。CUDA 走 `EngineConfig.onnxruntime.use_cuda` 真通道——
    旧 v3 轨道那个"传参不生效、只能改包内 config.yaml"的假通道已随包一起删除。

    模型固定 small：官方 model_list 列明 tiny 不含日文，而本语料是简繁日三体混排。

    要求 GPU 时，建完逐段读会话实际跑在哪个 provider 上，任一段不在 CUDA 就抛错。这是 GPU 的
    唯一判据：缺 .so 时 providers 列表照样列出 CUDA，建会话也不报错，只是静默退回 CPU；依赖
    报"退回 CPU"用的是 logging，又被下面的 log_level=error 静音。
    """
    if RapidOCR is None:
        raise RuntimeError("该环境未安装 rapidocr 3.x（跑 bash scripts/ocr.sh install 补装）")
    params = {
        "Rec.ocr_version": OCRVersion.PPOCRV6,
        "Rec.model_type": ModelType.SMALL,
        "Global.log_level": "error",
        "Global.text_score": min_score,
    }
    if use_gpu:
        params["EngineConfig.onnxruntime.use_cuda"] = True
    engine = RapidOCR(params=params)
    if use_gpu:
        for label, part in (("Det", engine.text_det), ("Cls", engine.text_cls), ("Rec", engine.text_rec)):
            providers = part.session.session.get_providers()
            if not providers or providers[0] != "CUDAExecutionProvider":
                raise RuntimeError(
                    f"要求 GPU，但 {label} 段会话跑在 {providers}：多半是 CPU 版 onnxruntime 覆盖了 GPU 版，"
                    "或 LD_LIBRARY_PATH 没带上 venv 内的 nvidia/*/lib（经 bash scripts/ocr.sh 启动会自动挂进去）"
                )
    return engine


def _load_ocr_sidecar(out_path: Path, root: Path | None = None) -> dict[str, Any] | None:
    """合法空页允许无气泡；非空页至少有文字及四个有限、顺序正确的坐标。"""
    try:
        data = read_json(out_path, root=root)
    except OSError, ValueError:
        return None
    if not isinstance(data, dict) or data.get("engine") != "rapidocr" or not isinstance(data.get("bubbles"), list):
        return None
    for bubble in data["bubbles"]:
        if not isinstance(bubble, dict) or not isinstance(bubble.get("text"), str) or not bubble["text"].strip():
            return None
        box = bubble.get("box")
        if not isinstance(box, list) or len(box) != 4:
            return None
        if not all(
            isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) for value in box
        ):
            return None
        if box[0] > box[2] or box[1] > box[3]:
            return None
        if "confidence" in bubble and (
            not isinstance(bubble["confidence"], (int, float))
            or isinstance(bubble["confidence"], bool)
            or not 0 <= bubble["confidence"] <= 1
        ):
            return None
    return data


def is_valid_ocr_sidecar(out_path: Path) -> bool:
    """检查可解析及基本气泡结构，保留历史 v3 伴生文件兼容性。"""
    return _load_ocr_sidecar(out_path) is not None


def sidecar_is_fresh(img_path: Path, out_path: Path, *, root: Path | None = None) -> bool:
    """新结果绑定识别时的源图状态；历史伴生文件仍使用修改时间判断。"""
    data = _load_ocr_sidecar(out_path, root)
    if data is None:
        return False
    try:
        stamp = file_stamp(img_path, root=root)
        if "source_image" in data:
            return data["source_image"] == {"size": stamp[2], "mtime_ns": stamp[3]}
        return stamp[3] <= file_stamp(out_path, root=root)[3]
    except OSError, ValueError:
        return False


def run_engine(engine: Any, img_path: Any) -> list[tuple[Any, str, float]]:
    """把引擎返回拍平成 `[(box, text, score), ...]`，行序即检测器的输出序。

    `rapidocr` 3.x 返回 `RapidOCROutput` 对象，`boxes`/`txts`/`scores` 是三个并列字段。
    两个坑必须在这一层挡掉：boxes 是 numpy 数组、对它做真值判断会抛
    "The truth value of an array with more than one element is ambiguous"（所以不能写
    `getattr(...) or []`）；boxes 里的角点是 float32、直接进侧车会让 json.dumps 抛
    "Object of type float32 is not JSON serializable"。
    """
    out = engine(str(img_path) if isinstance(img_path, Path) else img_path)
    texts = getattr(out, "txts", None)
    if texts is None:
        return []
    boxes = getattr(out, "boxes", None)
    scores = getattr(out, "scores", None)
    boxes = list(boxes) if boxes is not None else []
    scores = list(scores) if scores is not None else []
    rows: list[tuple[Any, str, float]] = []
    for i, text in enumerate(texts):
        raw_box = boxes[i] if i < len(boxes) else []
        box = [[float(pt[0]), float(pt[1])] for pt in raw_box]
        rows.append((box, str(text), float(scores[i]) if i < len(scores) else 1.0))
    return rows


def rows_to_blocks(rows: list[tuple[Any, str, float]]) -> list[dict[str, Any]]:
    """识别行 → 聚类输入：丢掉空白文本，角点收成外接框。

    不再按置信度过滤：低分行已由引擎按 `Global.text_score` 滤掉（见 `build_engine`）。
    """
    blocks: list[dict[str, Any]] = []
    for box, text, score in rows:
        text_str = str(text).strip()
        if not text_str:
            continue
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        blocks.append(
            {
                "text": text_str,
                "score": float(score),
                "xmin": min(xs),
                "xmax": max(xs),
                "ymin": min(ys),
                "ymax": max(ys),
            }
        )
    return blocks


def recognize_page(
    img_path: Path, engine: Any, *, root: Path | None = None
) -> tuple[int, int, list[tuple[Any, str, float]], tuple[int, int, int, int, int]]:
    """提取、预览和原始行 dump 共用解码：第 0 帧、EXIF 方位及识别期间源图变化检查。"""
    from PIL import ImageOps

    with open_regular(img_path, root=root) as file:
        info = os.fstat(file.fileno())
        stamp = info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns
        with Image.open(file) as page:
            if page.format not in image_formats():
                raise ValueError(f"不是可直接读取的光栅图片: {img_path} ({page.format})")
            decoded = ImageOps.exif_transpose(page)
            if decoded.mode == "P":
                decoded = decoded.convert("RGBA" if "transparency" in decoded.info else "RGB")
            elif decoded.mode not in {"RGB", "RGBA", "L", "LA"}:
                decoded = decoded.convert("RGB")
            w, h = decoded.size
            rows = run_engine(engine, decoded)
        if file_stamp(img_path, root=root) != stamp:
            raise RuntimeError(f"识别期间画页发生变化，结果未发布，请重试: {img_path}")
    return w, h, rows, stamp


def process_image(img_path: Path, out_path: Path, *, root: Path | None = None) -> int:
    """识别并原子发布；任何失败均保留旧结果，后续通过源图状态决定是否重提。"""
    w, h, rows, stamp = recognize_page(img_path, get_engine(), root=root)
    bubbles = cluster_blocks(rows_to_blocks(rows), w, h)
    payload = {
        "version": 1,
        "lang": "zh",
        "engine": "rapidocr",
        "engine_track": ENGINE_TRACK,
        "source_image": {"size": stamp[2], "mtime_ns": stamp[3]},
        "bubbles": bubbles,
    }
    if file_stamp(img_path, root=root) != stamp:
        raise RuntimeError(f"发布前画页发生变化，结果未发布，请重试: {img_path}")
    write_json_atomic(out_path, payload, root=root)
    return len(bubbles)


def parse_page_filter(page_spec: str) -> set[int]:
    """解析 --page：单页 (3)、多页 (1,3,5) 或范围 (10-20)，页码从 1 起。

    有一段解析不了就整体拒绝（argparse 据此报错退出）。以前是忽略坏片段，于是 `--page abc` 得到空集、
    被当成"没给过滤条件"，再带上 --force 就成了全库重提。
    """
    pages: set[int] = set()
    for part in page_spec.replace(" ", "").split(","):
        lo, sep, hi = part.partition("-")
        try:
            first, last = int(lo), int(hi) if sep else int(lo)
        except ValueError:
            first, last = 0, 0
        if not 1 <= first <= last:
            raise argparse.ArgumentTypeError(f"页码片段 {part!r} 无法解析（写法示例: 3、1,3,5、10-20）")
        pages.update(range(first, last + 1))
    return pages


def get_library_stats(data_dir: Path) -> dict[str, Any]:
    """扫描统计当前书库的 OCR 伴生覆盖率"""
    library_dir = data_dir / "library"
    stats = {
        "total_comics": 0,
        "ocr_comics": 0,
        "total_pages": 0,
        "ocr_pages": 0,
    }
    if not library_dir.is_dir():
        return stats

    for _, _, c in list_comics(library_dir):
        stats["total_comics"] += 1
        comic_has_ocr = False
        for _, out_path in collect_comic_pages(c):
            stats["total_pages"] += 1
            if out_path.exists():
                stats["ocr_pages"] += 1
                comic_has_ocr = True
        if comic_has_ocr:
            stats["ocr_comics"] += 1

    return stats


def build_arg_parser() -> argparse.ArgumentParser:
    """构造 worker 命令行。单列成函数是为了让"默认轨道/默认阈值"这类契约能被单测钉住。"""
    parser = argparse.ArgumentParser(
        allow_abbrev=False,
        description="纸间 (Paper Room) · 高性能机漫画台词 OCR 提取与伴生处理 Worker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=2,
        help="并发推理线程数（默认 2。CPU 模式别往上加：单引擎已吃满多核，v6 同页实测 2 线程 37.3 页/分、"
        "4 线程反而掉到 32.4；GPU 模式给 4。全库口径与复测方法见 DEPLOYMENT.md §5.1）",
    )
    parser.add_argument(
        "--gpu",
        action="store_true",
        help="要求用 CUDA 推理：环境用不上 CUDA 时直接报错退出，而不是静默按 CPU 跑完大批量"
        "（GPU 环境由 bash scripts/ocr.sh install 创建，之后 run/test 默认就带上本参数）",
    )
    parser.add_argument("--data-dir", type=parse_path, help="指定漫画数据目录（默认智能探测 NAS 或本地目录）")
    parser.add_argument(
        "--source",
        type=parse_directory_name,
        help="限定数据源（library/ 下的目录名，如 jm / local / picacg / copymanga）",
    )
    parser.add_argument("--id", type=parse_directory_name, help="限定单本漫画 ID（如 1059521）")
    parser.add_argument(
        "--page",
        type=parse_page_filter,
        help="限定处理特定页码（支持单页 3、列表 1,3,5、范围 10-20；多章节本请改用 --image）",
    )
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument("--image", type=parse_path, help="直接指定单张画页图片路径进行定向提取")
    inputs.add_argument(
        "--directory", type=parse_path, help="递归处理普通图片目录（本地或映射盘）；仅提取，不推断作品身份"
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=DEFAULT_MIN_SCORE,
        help=f"识别置信度下限，直接交给引擎（默认 {DEFAULT_MIN_SCORE}，调低调高都生效；过滤拟声词噪点）",
    )
    parser.add_argument("--force", action="store_true", help="强制重新提取已存在的 OCR 伴生文件")
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="最多产出新页的漫画册数（0 为无限制）；全页失败的本不占名额，本轮尝试册数可能更多",
    )
    parser.add_argument("--check", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--status", action="store_true", help="仅查看书库 OCR 伴生文件覆盖统计")
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()
    if args.limit < 0 or args.workers < 1:
        parser.error("--limit 必须大于或等于 0，--workers 必须大于 0")
    if args.image or args.directory:
        if args.source is not None or args.id is not None or args.page is not None or args.limit or args.status:
            parser.error("--image / --directory 不能与 --source、--id、--page、--limit、--status 混用")
    if not 0 <= args.min_score <= 1:
        parser.error("--min-score 必须在 0 到 1 之间")

    img_p = None
    file_root = None
    target_jobs = []
    failed_comics: list[str] = []
    try:
        # 普通文件作业不依赖书库，也不读取数据目录的默认环境变量。
        if args.image or args.directory:
            if args.data_dir is not None:
                resolve_data_dir(args.data_dir)
            target = Path(args.image or args.directory).expanduser()
            if args.image:
                if not target.is_file() or target.is_symlink() or target.suffix.lower() not in image_extensions():
                    raise ValueError(f"指定图片不存在、是符号链接或格式不受支持: {target}")
                img_p = target.resolve()
                file_root = img_p.parent
                image_output(img_p)
            else:
                if not target.is_dir():
                    raise ValueError(f"指定的图片目录不存在或不是目录: {target}")
                file_root = target.resolve()
                target_jobs = [(str(target), collect_images(file_root))]
        else:
            data_dir = resolve_data_dir(args.data_dir)
            file_root = data_dir
            library_dir = data_dir / "library"
            if not library_dir.is_dir():
                raise ValueError(f"未在数据目录中找到 library 子目录: {library_dir}")
            if args.source is not None and not (library_dir / args.source).is_dir():
                raise ValueError(f"书库里没有图源目录 {args.source}")
            target_comics = list_comics(library_dir, args.source, args.id)
            if not target_comics and (args.source is not None or args.id is not None):
                raise ValueError(f"书库里没有指定的漫画 {args.source or '*'}/{args.id or '*'}")
            print(f"📁 目标漫画数据目录: {data_dir}")
            if args.status:
                stats = get_library_stats(data_dir)
                print(f"📚 藏书: {stats['total_comics']} 本，已有 OCR 伴生: {stats['ocr_comics']} 本")
                print(f"📄 画页: {stats['total_pages']} 页，已有 OCR 伴生: {stats['ocr_pages']} 页")
                return 0
            for source, sid, comic in target_comics:
                label = f"{source}/{sid}"
                try:
                    target_jobs.append((label, collect_comic_pages(comic, args.page)))
                except ValueError as exc:
                    print(f"❌ 跳过 {label}: {exc}", file=sys.stderr)
                    failed_comics.append(label)
    except (ValueError, OSError) as exc:
        print(f"❌ 错误: {exc}", file=sys.stderr)
        return 1
    if args.check:
        return 1 if failed_comics else 0

    # 全部增量命中时不需要推理环境；本机同步仍由 shell 在提取返回后执行。
    pending_jobs = []
    total_skipped_pages = 0
    for label, pages in target_jobs:
        pending = pages if args.force else [pair for pair in pages if not sidecar_is_fresh(*pair, root=file_root)]
        total_skipped_pages += len(pages) - len(pending)
        if pending:
            pending_jobs.append((label, pending))
    if (
        img_p is not None
        and not args.force
        and sidecar_is_fresh(img_p, img_p.with_name(f"{img_p.stem}.ocr.json"), root=file_root)
    ):
        print("⚡ 画页伴生文件已是最新且合法，无需更新。")
        return 0
    if img_p is None and not pending_jobs:
        print(f"⚡ 无待提取画页，增量跳过 {total_skipped_pages} 页。")
        return 1 if failed_comics else 0

    # 依赖预检：只剩一条引擎线，缺包就说清楚缺哪个
    if RapidOCR is None or Image is None:
        print("❌ 错误: 当前 Python 环境缺少 OCR 必要依赖 (rapidocr>=3.9 / Pillow)。", file=sys.stderr)
        print("💡 请在算力机上运行一键安装命令:", file=sys.stderr)
        print("   bash scripts/ocr.sh install", file=sys.stderr)
        print("   注：只装过旧 v3 依赖的 CPU 环境必须重跑一次 install 才会拿到 rapidocr 3.x", file=sys.stderr)
        return 1

    global USE_GPU, MIN_SCORE
    MIN_SCORE = args.min_score
    USE_GPU = args.gpu
    # 要求 GPU 就必须真用上，否则宁可拒跑——静默按 CPU 跑完几千页是这套脚本最贵的失败方式。
    if args.gpu:
        ok, reason = cuda_ready()
        if not ok:
            print(f"❌ 错误: 命令行指定了 --gpu，但当前环境用不上 CUDA: {reason}", file=sys.stderr)
            print("💡 请重跑 bash scripts/ocr.sh install 重建 GPU 环境（或显式改用 --cpu 跑）", file=sys.stderr)
            return 1
    else:
        # 环境装的是 GPU 构建却没带 --gpu，几乎只可能是绕开 ocr.sh 直接调解释器
        # （这时 LD_LIBRARY_PATH 没挂上，推理会悄悄退回 CPU）。不挡路，但要说出来。
        if cuda_ready()[0]:
            print(
                "⚠️ 该环境的 onnxruntime 是 GPU 构建，却没带 --gpu：本次按 CPU 跑。"
                "批量提取请用 bash scripts/ocr.sh run，它会自动带上 --gpu。",
                file=sys.stderr,
            )

    # 初始化 OCR 引擎（主线程预热验证）
    device = "GPU · CUDAExecutionProvider" if USE_GPU else "CPU 多核"
    print(f"⚡ 正在初始化 RapidOCR 深度学习推理引擎 (推理设备: {device} · 并发线程数: {args.workers})...")
    t0 = time.time()
    # GPU 用不上时 build_engine 当场抛错：在主线程先撞上，不等线程池里一页页各自失败
    try:
        get_engine()
    except RuntimeError as exc:
        print(f"❌ 错误: {exc}", file=sys.stderr)
        return 1
    print(f"✅ OCR 引擎初始化就绪 ({time.time() - t0:.2f}s)")

    # 1. 单张画页定向处理模式
    if img_p is not None:
        out_p = img_p.with_name(f"{img_p.stem}.ocr.json")
        print(f"🎯 单张画页定向处理: {img_p.name}")
        t1 = time.time()
        try:
            res = process_image(img_p, out_p, root=file_root)
            print(f"✅ 处理完成 ({time.time() - t1:.2f}s): 提取对白 {res} 条 ➔ {out_p.name}")
        except Exception as e:
            print(f"❌ 处理画页失败 {img_p.name}: {e}", file=sys.stderr)
            return 1
        return 0

    print(f"🎯 扫描作业: 共 {len(target_jobs)} 项，{len(pending_jobs)} 项待提取")
    total_extracted_dialogues = total_processed_pages = processed_comics = failed_pages = 0
    # 线程池全程只建一次，引擎在线程上复用。
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        for label, pending_pages in pending_jobs:
            if args.limit and processed_comics >= args.limit:
                print(f"⏹ 已有 {args.limit} 本产出新页（--limit），其余留待下次运行。")
                break
            comic_dialogues = comic_new_pages = comic_failed_pages = 0
            print(f"开始提取 {label}: {len(pending_pages)} 页")
            futures = {
                executor.submit(process_image, image, output, root=file_root): image for image, output in pending_pages
            }
            for done_count, future in enumerate(concurrent.futures.as_completed(futures), start=1):
                try:
                    comic_dialogues += future.result()
                    comic_new_pages += 1
                except Exception as exc:
                    comic_failed_pages += 1
                    print(f"\n⚠️ 处理画页失败 {futures[future]}: {exc}", file=sys.stderr)
                print(f"\r  进度: {done_count}/{len(pending_pages)} 页", end="", flush=True)
            total_processed_pages += comic_new_pages
            total_extracted_dialogues += comic_dialogues
            failed_pages += comic_failed_pages
            processed_comics += bool(comic_new_pages)
            if comic_failed_pages:
                failed_comics.append(label)
            print(
                f"\n  完成 {label}: 新提取 {comic_new_pages} 页，失败 {comic_failed_pages} 页，{comic_dialogues} 条对白"
            )
    failed = bool(failed_pages or failed_comics)
    print(
        f"{'⚠️ 批处理有失败' if failed else '🎉 批处理完成'}：新处理 {total_processed_pages} 页，"
        f"增量跳过 {total_skipped_pages} 页，提取对白 {total_extracted_dialogues} 条"
    )
    if failed_comics:
        print(f"❌ 失败作业: {', '.join(failed_comics)}；重跑会补失败页，已有有效伴生文件保留。", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
