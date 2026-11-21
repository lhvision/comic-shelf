"""气泡聚类判据的离线实验台。

三个模式：
1. dump（默认）：把指定画页的**原始识别行**（未聚类）导出成 JSON。推理只跑一次，
   之后调 `cluster_blocks` 的判据就在本地秒级迭代，不必每改一版就烧一轮 GPU。
2. `--recluster`：读回这些 dump，用**当前代码里的**聚类算法重跑，打印气泡数、字数
   与气泡面积分布，用来判断一版判据改动是拆开了误并、还是把真气泡也拆碎了。
3. `--image`：只识别一张图并打印聚类后的气泡，不写任何文件（`ocr.sh test` 走这里）。

侧车只存聚类后的气泡、不存原始行，所以这个 dump 就是唯一的离线复现入口。
引擎构造、置信度门槛与画页清单全部直接用 worker 的，实验台量到的就是实跑的那一套。
"""

from __future__ import annotations

import argparse
import math
import os
import stat
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.file_io import file_stamp, read_json, write_json_atomic
from app.ocr_files import (
    collect_comic_pages,
    list_comics,
    parse_directory_name,
    parse_path,
    resolve_data_dir,
    scan_files,
)
from scripts import ocr_worker
from scripts.ocr_worker import (
    DEFAULT_MIN_SCORE,
    cluster_blocks,
    get_engine,
    recognize_page,
    rows_to_blocks,
)


def _images(data_dir: Path, source: str | None, source_id: str | None, limit_pages: int) -> list[Path]:
    imgs: list[Path] = []
    # 选本与画页清单都与 worker 同源：只给 --source 不会退化成全库扫描；分章节的本把图放在 pages/ 的子目录里
    for _, _, book in list_comics(data_dir / "library", source, source_id):
        found = [img for img, _ in collect_comic_pages(book)]
        imgs.extend(found[:limit_pages] if limit_pages else found)
    return imgs


def _output_directory(path: Path, *, create: bool = True) -> Path:
    """输出目录及父路径不能由其他用户控制；root 管理的 sticky 临时目录允许使用。"""
    path = path.expanduser().absolute()
    for directory in (path, *path.parents):
        if directory.is_symlink():
            raise ValueError(f"dump 输出路径不能是符号链接: {directory}")
        if directory.exists():
            info = directory.stat()
            if not stat.S_ISDIR(info.st_mode) or info.st_uid not in {0, os.geteuid()}:
                raise ValueError(f"dump 输出路径不受当前用户控制: {directory}")
            if info.st_mode & 0o022 and not (info.st_uid == 0 and info.st_mode & stat.S_ISVTX):
                raise ValueError(f"dump 输出路径允许其他用户修改: {directory}")
    if not create:
        return path
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o022:
        raise ValueError(f"dump 输出目录不属于当前用户: {path}")
    return path


def _valid_dump(data: object) -> bool:
    """验证可用于离线重聚类的最小结构，不把空文件或残缺 JSON 当作完成。"""
    if not isinstance(data, dict) or not isinstance(data.get("image"), str):
        return False
    if any(not isinstance(data.get(key), int) or isinstance(data[key], bool) or data[key] <= 0 for key in ("w", "h")):
        return False
    blocks = data.get("blocks")
    if not isinstance(blocks, list):
        return False
    for block in blocks:
        if not isinstance(block, dict) or not isinstance(block.get("text"), str):
            return False
        for key in ("xmin", "xmax", "ymin", "ymax", "score"):
            value = block.get(key)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
                return False
    return True


def _cached_dump(img: Path, dst: Path, library_dir: Path, out_dir: Path) -> bool:
    try:
        data = read_json(dst, root=out_dir)
    except FileNotFoundError:
        return False
    if not _valid_dump(data) or data["image"] != str(img):
        raise ValueError(f"已有 dump 对应另一张画页或结构损坏，请使用新输出目录: {dst}")
    stamp = file_stamp(img, root=library_dir)
    if "source_image" in data:
        matches = data["source_image"] == {"size": stamp[2], "mtime_ns": stamp[3]}
    else:
        matches = file_stamp(dst, root=out_dir)[3] >= stamp[3]
    if not matches:
        raise ValueError(f"已有 dump 对应旧画页，请使用新输出目录: {dst}")
    return True


def _dump_one(img: Path, out_dir: Path, library_dir: Path) -> tuple[str, str]:
    # 保留图源、书号和相对目录，删除有歧义的扁平文件名拼接。
    dst = out_dir / img.relative_to(library_dir).with_suffix(".json")
    if _cached_dump(img, dst, library_dir, out_dir):
        return str(dst.relative_to(out_dir)), "已存在，跳过"
    w, h, rows, stamp = recognize_page(img, get_engine(), root=library_dir)
    blocks = rows_to_blocks(rows)
    payload = {
        "image": str(img),
        "w": w,
        "h": h,
        "blocks": blocks,
        "source_image": {"size": stamp[2], "mtime_ns": stamp[3]},
    }
    dst.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if file_stamp(img, root=library_dir) != stamp:
        raise RuntimeError(f"发布 dump 前画页发生变化，请重试: {img}")
    try:
        write_json_atomic(dst, payload, root=out_dir, overwrite=False)
    except FileExistsError:
        if _cached_dump(img, dst, library_dir, out_dir):
            return str(dst.relative_to(out_dir)), "已存在，跳过"
        raise RuntimeError(f"并发 dump 被移除，请重试: {dst}")
    return str(dst.relative_to(out_dir)), f"{len(blocks)} 行"


def cmd_dump(args: argparse.Namespace) -> int:
    try:
        data_dir = resolve_data_dir(args.data_dir)
        library_dir = data_dir / "library"
        imgs = _images(data_dir, args.source, args.id, args.pages)
        if not imgs:
            raise ValueError("没有匹配到画页（检查 --source/--id）")
        if args.out:
            out_dir = _output_directory(Path(args.out))
        else:
            base = _output_directory(Path(tempfile.gettempdir()).resolve(), create=False)
            out_dir = Path(tempfile.mkdtemp(prefix="paper-room-ocr-lines-", dir=base))
    except (ValueError, OSError) as exc:
        print(f"❌ 错误: {exc}", file=sys.stderr)
        return 1
    print(f"🧪 dump {len(imgs)} 页原始识别行 → {out_dir} (推理设备: {'GPU' if ocr_worker.USE_GPU else 'CPU'})")
    workers = args.workers or (4 if ocr_worker.USE_GPU else 2)
    failed = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [(image, pool.submit(_dump_one, image, out_dir, library_dir)) for image in imgs]
        for image, future in futures:
            try:
                name, info = future.result()
                print(f"  {name}: {info}")
            except (OSError, ValueError, RuntimeError) as exc:
                failed += 1
                print(f"❌ dump 失败 {image}: {exc}", file=sys.stderr)
    return 1 if failed else 0


def cmd_image(args: argparse.Namespace) -> int:
    """单页试跑：与 run 同一套引擎构造、置信度门槛与聚类，只打印，不写盘。"""
    img = Path(args.image).expanduser().resolve()
    if not img.is_file():
        print(f"❌ 错误: 图片不存在 ({img})", file=sys.stderr)
        return 1
    try:
        t0 = time.perf_counter()
        w, h, rows, _ = recognize_page(img, get_engine(), root=img.parent)
        cost = time.perf_counter() - t0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"❌ 错误: {exc}", file=sys.stderr)
        return 1
    bubbles = cluster_blocks(rows_to_blocks(rows), w, h)
    print(f"🔧 推理设备: {'GPU' if ocr_worker.USE_GPU else 'CPU'}")
    print(
        f"📐 图像尺寸: {w}x{h}, 推理耗时: {cost:.2f}s, 识别行 {len(rows)} 行（引擎已滤掉置信度 <{DEFAULT_MIN_SCORE} 的行）"
    )
    print(f"💬 气泡几何聚类后获得: {len(bubbles)} 处对白")
    for b in bubbles:
        print(f"  - [{b['id']}] {b['orientation']} (置信度: {b['confidence']}) 归一化坐标: {b['box']}")
        print(f'    对白内容: "{b["text"]}"')
    return 0


def cmd_recluster(args: argparse.Namespace) -> int:
    src = Path(args.recluster).expanduser().resolve()
    files = scan_files(src, (".json",))
    if not files:
        print(f"❌ 错误: {src} 里没有 dump 文件，先跑一次 dump 模式", file=sys.stderr)
        return 1
    total_pages = rows = bubbles = chars = suspects = 0
    buckets = {"<=10%": 0, "10-20%": 0, "20-35%": 0, ">35%": 0}
    worst: list[tuple[float, str, int, str]] = []
    for f in files:
        try:
            d = read_json(f, root=src)
            if not _valid_dump(d):
                raise ValueError(f"dump 结构损坏: {f}")
        except (OSError, ValueError) as exc:
            print(f"❌ 错误: {exc}", file=sys.stderr)
            return 1
        rows += len(d["blocks"])
        for b in cluster_blocks(d["blocks"], d["w"], d["h"]):
            ymin, xmin, ymax, xmax = b["box"]
            area = max(0.0, ymax - ymin) * max(0.0, xmax - xmin)
            ln = len(b["text"])
            bubbles += 1
            chars += ln
            buckets["<=10%" if area <= 0.1 else "10-20%" if area <= 0.2 else "20-35%" if area <= 0.35 else ">35%"] += 1
            # 可疑合并：框很大而字很少，说明把分散在页面各处的行串成了一串
            if (area > 0.25 and ln < 60) or area > 0.35:
                suspects += 1
                worst.append((area, f.name, b["order"], b["text"]))
        total_pages += 1
    print(f"📊 {total_pages} 页 / 原始行 {rows} → 气泡 {bubbles}，字数 {chars}")
    print(f"   面积分布: {buckets}")
    print(f"   疑似误并: {suspects}")
    for area, name, order, text in sorted(worst, reverse=True)[:10]:
        print(f"     {area:5.1%} {name} #{order} | {text[:60]}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        allow_abbrev=False, description="气泡聚类离线实验台（dump 原始行 / 离线重聚类 / 单页试跑）"
    )
    parser.add_argument("--data-dir", type=parse_path, help="漫画数据目录（默认智能探测）")
    parser.add_argument("--source", type=parse_directory_name, help="数据源 (jm)")
    parser.add_argument("--id", type=parse_directory_name, help="漫画 ID，配合 --source 限定单本")
    parser.add_argument("--pages", type=int, default=0, help="每本最多取多少页（0 为全部）")
    parser.add_argument("--out", type=parse_path, help="dump 输出目录（默认创建随机私有临时目录，实际路径会打印）")
    parser.add_argument("--workers", type=int, default=0, help="dump 时的并发线程数（默认 GPU 4、CPU 2）")
    parser.add_argument("--gpu", action="store_true", help="用 CUDA 推理；三段会话任一不在 GPU 上就直接报错")
    parser.add_argument(
        "--recluster", type=parse_path, help="不跑推理：读该目录下的 dump，用当前聚类算法重跑并打印分布"
    )
    parser.add_argument("--image", type=parse_path, help="只识别这一张图并打印聚类后的气泡，不写任何文件")
    args = parser.parse_args()
    if args.pages < 0 or args.workers < 0:
        parser.error("--pages 与 --workers 必须大于或等于 0")

    if args.recluster:
        return cmd_recluster(args)
    ocr_worker.USE_GPU = args.gpu
    if args.image:
        return cmd_image(args)
    return cmd_dump(args)


if __name__ == "__main__":
    raise SystemExit(main())
