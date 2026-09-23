"""气泡聚类判据的离线实验台。

两个模式：
1. dump（默认）：把指定画页的**原始识别行**（未聚类）导出成 JSON。推理只跑一次，
   之后调 `cluster_blocks` 的判据就在本地秒级迭代，不必每改一版就烧一轮 GPU。
2. `--recluster`：读回这些 dump，用**当前代码里的**聚类算法重跑，打印气泡数、字数
   与气泡面积分布，用来判断一版判据改动是拆开了误并、还是把真气泡也拆碎了。

侧车本身不存原始行（体积要考虑阅读器每页解析），所以这个 dump 就是唯一的离线复现入口。
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.ocr_worker import (  # noqa: E402
    DEFAULT_MIN_SCORE,
    build_engine,
    cluster_blocks,
    resolve_data_dir,
    run_engine,
)

_tls = threading.local()


def _engine() -> Any:
    if not hasattr(_tls, "engine"):
        _tls.engine = build_engine(_tls_gpu)
    return _tls.engine


_tls_gpu = False


def _images(data_dir: Path, source: str | None, source_id: str | None, limit_pages: int) -> list[Path]:
    root = data_dir / "library"
    if source and source_id:
        books = [root / source / source_id]
    elif source:
        # 只给 --source 时不许退化成全库扫描，否则一轮无谓推理藏在"我只跑 jm"这句话里
        books = sorted((root / source).glob("*")) if (root / source).is_dir() else []
    else:
        books = sorted(root.glob("*/*"))
    imgs: list[Path] = []
    for book in books:
        pages = book / "pages"
        if not pages.is_dir():
            continue
        found = [
            p
            for p in sorted(pages.iterdir())
            if p.suffix.lower() in (".webp", ".jpg", ".jpeg", ".png")
        ]
        imgs.extend(found[:limit_pages] if limit_pages else found)
    return imgs


def _dump_one(img: Path, out_dir: Path) -> tuple[str, str]:
    from PIL import Image

    dst = out_dir / f"{img.parent.parent.name}_{img.name.rsplit('.', 1)[0]}.json"
    if dst.exists():
        return dst.name, "已存在，跳过"
    with Image.open(img) as im:
        w, h = im.size
    blocks = []
    for box, text, score in run_engine(_engine(), img):
        text_str = str(text).strip()
        score_f = float(score)
        if not text_str or score_f < DEFAULT_MIN_SCORE:
            continue
        xs = [pt[0] for pt in box]
        ys = [pt[1] for pt in box]
        blocks.append(
            {
                "text": text_str,
                "score": score_f,
                "xmin": min(xs),
                "xmax": max(xs),
                "ymin": min(ys),
                "ymax": max(ys),
            }
        )
    dst.write_text(
        json.dumps({"image": str(img), "w": w, "h": h, "blocks": blocks}, ensure_ascii=False),
        encoding="utf-8",
    )
    return dst.name, f"{len(blocks)} 行"


def cmd_dump(args: argparse.Namespace) -> int:
    data_dir = resolve_data_dir(args.data_dir)
    imgs = _images(data_dir, args.source, args.id, args.pages)
    if not imgs:
        print("❌ 错误: 没有匹配到画页（检查 --source/--id）", file=sys.stderr)
        return 1
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"🧪 dump {len(imgs)} 页原始识别行 → {out_dir} (推理设备: {'GPU' if _tls_gpu else 'CPU'})")
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        for name, info in ex.map(lambda p: _dump_one(p, out_dir), imgs):
            print(f"  {name}: {info}")
    return 0


def cmd_recluster(args: argparse.Namespace) -> int:
    src = Path(args.recluster)
    files = sorted(src.glob("*.json"))
    if not files:
        print(f"❌ 错误: {src} 里没有 dump 文件，先跑一次 dump 模式", file=sys.stderr)
        return 1
    total_pages = rows = bubbles = chars = suspects = 0
    buckets = {"<=10%": 0, "10-20%": 0, "20-35%": 0, ">35%": 0}
    worst: list[tuple[float, str, int, str]] = []
    for f in files:
        d = json.loads(f.read_text(encoding="utf-8"))
        rows += len(d["blocks"])
        for b in cluster_blocks(d["blocks"], d["w"], d["h"]):
            ymin, xmin, ymax, xmax = b["box"]
            area = max(0.0, ymax - ymin) * max(0.0, xmax - xmin)
            ln = len(b["text"])
            bubbles += 1
            chars += ln
            buckets["<=10%" if area <= 0.1 else "10-20%" if area <= 0.2 else "20-35%" if area <= 0.35 else ">35%"] += 1
            # 可疑合并：框很大而字很少，说明把分散在页面各处的行串成了一串
            if (area > 0.45 and ln < 200) or (area > 0.25 and ln < 60) or area > 0.35:
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
    global _tls_gpu
    parser = argparse.ArgumentParser(description="气泡聚类离线实验台（dump 原始行 / 离线重聚类）")
    parser.add_argument("--data-dir", help="漫画数据目录（默认智能探测）")
    parser.add_argument("--source", help="数据源 (jm)")
    parser.add_argument("--id", help="漫画 ID，配合 --source 限定单本")
    parser.add_argument("--pages", type=int, default=0, help="每本最多取多少页（0 为全部）")
    parser.add_argument("--out", default="/tmp/paper-room-ocr-lines", help="dump 输出目录")
    parser.add_argument("--workers", type=int, default=4, help="dump 时的并发线程数（GPU 建议 4）")
    parser.add_argument("--gpu", action="store_true", help="dump 时用 CUDA 推理")
    parser.add_argument("--recluster", help="不跑推理：读该目录下的 dump，用当前聚类算法重跑并打印分布")
    args = parser.parse_args()

    if args.recluster:
        return cmd_recluster(args)
    _tls_gpu = args.gpu
    return cmd_dump(args)


if __name__ == "__main__":
    raise SystemExit(main())
