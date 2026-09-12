#!/usr/bin/env python3
"""
纸间 (Paper Room) · 高性能机漫画台词 OCR 提取与聚类工作流 Worker
功能：
1. 智能探测数据目录（COMIC_SHELF_DATA -> /mnt/nas_manga -> backend/data）；
2. 批量扫描画页（.webp, .jpg, .png），调用 RapidOCR 识别中日文分镜台词；
3. 气泡级多行文本几何聚类（Bubble-level Line Clustering），计算右向左（竖排）/上向下（横排）阅读流与 Union 归一化百分比坐标；
4. 产出伴生文件 {index}.ocr.json；
5. 支持通过 HTTP API 自动通知远程 NAS 纸间服务或同步本地 SQLite FTS5 索引。
"""

import argparse
import concurrent.futures
import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import urllib.request
import urllib.error

# 尝试导入 OCR 与图像依赖
try:
    from PIL import Image
except ImportError:
    Image = None

try:
    from rapidocr_onnxruntime import RapidOCR
except ImportError:
    RapidOCR = None


def resolve_data_dir(custom_path: Optional[str] = None) -> Path:
    """按优先级解析有效漫画数据目录"""
    if custom_path:
        p = Path(custom_path).resolve()
        if p.is_dir():
            return p
        print(f"⚠️ 指定的数据目录不存在: {custom_path}，转入自动探测...", file=sys.stderr)

    env_dir = os.environ.get("COMIC_SHELF_DATA")
    if env_dir and Path(env_dir).is_dir():
        return Path(env_dir).resolve()

    nas_mount = Path("/mnt/nas_manga")
    if (nas_mount / "library").is_dir():
        return nas_mount.resolve()

    local_data = Path(__file__).resolve().parent.parent / "backend" / "data"
    if local_data.is_dir():
        return local_data.resolve()

    return Path("backend/data").resolve()


def cluster_blocks(
    blocks: List[Dict[str, Any]], img_w: int, img_h: int
) -> List[Dict[str, Any]]:
    """
    气泡级多行文本几何聚类算法 (Bubble-level Line Clustering)
    根据几何间距与重合度，将属于同一气泡的多行文字聚合为一条完整对白，并计算归一化坐标 [ymin, xmin, ymax, xmax]
    """
    n = len(blocks)
    if n == 0:
        return []

    parent = list(range(n))

    def find(i: int) -> int:
        if parent[i] == i:
            return i
        parent[i] = find(parent[i])
        return parent[i]

    def union(i: int, j: int) -> None:
        pi, pj = find(i), find(j)
        if pi != pj:
            parent[pi] = pj

    for i in range(n):
        bi = blocks[i]
        wi = bi["xmax"] - bi["xmin"]
        hi = bi["ymax"] - bi["ymin"]
        for j in range(i + 1, n):
            bj = blocks[j]
            wj = bj["xmax"] - bj["xmin"]
            hj = bj["ymax"] - bj["ymin"]

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

    groups: Dict[int, List[Dict[str, Any]]] = {}
    for i in range(n):
        root = find(i)
        groups.setdefault(root, []).append(blocks[i])

    results: List[Dict[str, Any]] = []
    bubble_id = 1
    for _, g_blocks in groups.items():
        # 判断该气泡是否偏竖排
        v_count = sum(
            1 for b in g_blocks if (b["ymax"] - b["ymin"]) > (b["xmax"] - b["xmin"]) * 1.1
        )
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
                "id": bubble_id,
                "box": [round(ymin, 4), round(xmin, 4), round(ymax, 4), round(xmax, 4)],
                "text": full_text,
                "confidence": round(avg_score, 2),
                "orientation": "vertical" if is_vertical else "horizontal",
                "type": "dialogue",
            }
        )
        bubble_id += 1

    return results


_thread_local = threading.local()


def get_engine() -> Any:
    """每个线程独享一个 RapidOCR 推理引擎实例，杜绝多线程状态竞争"""
    if not hasattr(_thread_local, "engine"):
        if RapidOCR is not None:
            _thread_local.engine = RapidOCR()
        else:
            _thread_local.engine = None
    return _thread_local.engine


def is_valid_ocr_sidecar(out_path: Path) -> bool:
    """检查伴生文件是否合法。
    需满足：文件存在、体积大于 10 字节、为合法 JSON 且带有 engine: rapidocr。
    不合法、残缺或手工 mock 的旧数据将被视为脏缓存，自动触发自愈重提。
    """
    if not out_path.is_file():
        return False
    try:
        if out_path.stat().st_size < 10:
            return False
        with open(out_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return (
                isinstance(data, dict)
                and data.get("engine") == "rapidocr"
                and isinstance(data.get("bubbles"), list)
            )
    except Exception:
        return False


def process_image(
    img_path: Path,
    out_path: Path,
    force: bool = False,
    min_score: float = 0.5,
    engine: Optional[Any] = None,
) -> Optional[int]:
    """处理单张画页的 OCR 提取与写入伴生文件。
    智能增量与自愈机制：
    1. 若未开启 force 且伴生文件有效、修改时间更新，直接跳过 (return None)；
    2. 若伴生文件损坏、为空、为旧 mock 数据（缺少 engine: rapidocr），或原图更新，自动触发增量提取。
    """
    if not force and out_path.exists():
        try:
            if is_valid_ocr_sidecar(out_path) and img_path.stat().st_mtime <= out_path.stat().st_mtime:
                return None
        except OSError:
            pass

    if engine is None:
        engine = get_engine()
    if engine is None:
        return 0

    try:
        with Image.open(img_path) as im:
            w, h = im.size
    except Exception as e:
        print(f"⚠️ 读取画页失败 {img_path.name}: {e}", file=sys.stderr)
        return 0

    try:
        raw_results, _ = engine(str(img_path))
    except Exception as e:
        print(f"⚠️ OCR 推理失败 {img_path.name}: {e}", file=sys.stderr)
        return 0

    blocks: List[Dict[str, Any]] = []
    if raw_results:
        for item in raw_results:
            box, text, score = item
            score_f = float(score)
            if score_f < min_score:
                continue
            text_str = str(text).strip()
            if not text_str:
                continue
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
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

    bubbles = cluster_blocks(blocks, w, h)

    payload = {
        "version": 1,
        "lang": "zh",
        "engine": "rapidocr",
        "bubbles": bubbles,
    }

    try:
        temp_path = out_path.with_suffix(".tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        temp_path.replace(out_path)
    except Exception as e:
        print(f"⚠️ 写入伴生文件失败 {out_path.name}: {e}", file=sys.stderr)
        return 0

    return len(bubbles)


def parse_page_filter(page_spec: Optional[str]) -> Optional[set[int]]:
    """解析页面过滤参数，支持单页 (3)、多页 (1,3,5) 或范围 (10-20)"""
    if not page_spec:
        return None
    res: set[int] = set()
    parts = page_spec.replace(" ", "").split(",")
    for part in parts:
        if "-" in part:
            seg = part.split("-", 1)
            try:
                res.update(range(int(seg[0]), int(seg[1]) + 1))
            except ValueError:
                pass
        else:
            try:
                res.add(int(part))
            except ValueError:
                pass
    return res


def collect_comic_pages(
    comic_dir: Path, page_filter: Optional[set[int]] = None
) -> List[Tuple[Path, Path]]:
    """收集指定漫画目录下的全部有效画页图片及对应伴生文件路径。
    若指定 page_filter，仅保留匹配该页码（1-based 序号或文件名数字）的画页。
    """
    pages_dir = comic_dir / "pages"
    if not pages_dir.is_dir():
        return []

    exts = {".webp", ".jpg", ".jpeg", ".png"}
    all_pages: List[Tuple[Path, Path]] = []

    # 支持单话平铺或分章节 c1/c2
    for root, _, files in os.walk(pages_dir):
        root_path = Path(root)
        for f in sorted(files):
            p = root_path / f
            if p.suffix.lower() in exts and not p.name.startswith("."):
                out_name = f"{p.stem}.ocr.json"
                out_path = root_path / out_name
                all_pages.append((p, out_path))

    all_pages.sort(key=lambda x: x[0].name)

    if not page_filter:
        return all_pages

    filtered: List[Tuple[Path, Path]] = []
    for seq_idx, (img_path, out_path) in enumerate(all_pages, start=1):
        stem_num = None
        try:
            stem_num = int(img_path.stem)
        except ValueError:
            pass
        if seq_idx in page_filter or (stem_num is not None and stem_num in page_filter):
            filtered.append((img_path, out_path))

    return filtered


def notify_nas_sync(api_url: str, source: str, source_id: str, token: Optional[str] = None) -> bool:
    """通过 HTTP API 通知 NAS 纸间服务更新 SQLite FTS5 索引"""
    url = f"{api_url.rstrip('/')}/api/library/{source}/{source_id}/ocr/sync"
    req = urllib.request.Request(url, method="POST")
    if token:
        req.add_header("Authorization", f"Bearer {token}")

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                indexed_count = data.get("count", data.get("indexed_count", 0))
                print(f"  📡 NAS 索引同步响应: 成功入库 {indexed_count} 条对白")
                return True
    except urllib.error.HTTPError as e:
        print(f"  ❌ 通知 NAS 同步失败 (HTTP {e.code}): {e.reason}", file=sys.stderr)
    except Exception as e:
        print(f"  ❌ 通知 NAS 同步网络异常: {e}", file=sys.stderr)
    return False


def get_library_stats(data_dir: Path) -> Dict[str, Any]:
    """扫描统计当前书库的 OCR 伴生覆盖率"""
    library_dir = data_dir / "library"
    stats = {
        "total_comics": 0,
        "ocr_comics": 0,
        "total_pages": 0,
        "ocr_pages": 0,
        "fts_dialogues": 0,
    }
    if not library_dir.is_dir():
        return stats

    for source in ["jm", "local", "picacg"]:
        s_dir = library_dir / source
        if not s_dir.is_dir():
            continue
        for c in s_dir.iterdir():
            if c.is_dir() and not c.name.startswith("."):
                stats["total_comics"] += 1
                pages = collect_comic_pages(c)
                comic_has_ocr = False
                for _, out_path in pages:
                    stats["total_pages"] += 1
                    if out_path.exists():
                        stats["ocr_pages"] += 1
                        comic_has_ocr = True
                if comic_has_ocr:
                    stats["ocr_comics"] += 1

    # 检查独立的 comic_dialogues.db 数据库条目数
    diag_db_path = data_dir / "comic_dialogues.db"
    if diag_db_path.is_file():
        try:
            import sqlite3
            conn = sqlite3.connect(diag_db_path)
            cur = conn.cursor()
            cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='comic_dialogues_fts'")
            if cur.fetchone()[0]:
                cur.execute("SELECT count(*) FROM comic_dialogues_fts")
                stats["fts_dialogues"] = cur.fetchone()[0]
            conn.close()
        except Exception:
            pass

    return stats


def main() -> int:
    parser = argparse.ArgumentParser(
        description="纸间 (Paper Room) · 高性能机漫画台词 OCR 提取与伴生处理 Worker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--workers", type=int, default=2, help="并发推理线程数（默认 2，推荐 2~4 充分释放多核算力）")
    parser.add_argument("--data-dir", help="指定漫画数据目录（默认智能探测 NAS 或本地目录）")
    parser.add_argument("--source", choices=["jm", "local", "picacg"], help="限定数据源")
    parser.add_argument("--id", help="限定单本漫画 ID（如 1059521）")
    parser.add_argument("--page", help="限定处理特定页码（支持单页 3、列表 1,3,5、范围 10-20）")
    parser.add_argument("--image", help="直接指定单张画页图片路径进行定向提取")
    parser.add_argument("--min-score", type=float, default=0.5, help="OCR 置信度过滤阈值（默认 0.5，过滤拟声词噪点）")
    parser.add_argument("--force", action="store_true", help="强制重新提取已存在的 OCR 伴生文件")
    parser.add_argument("--limit", type=int, default=0, help="最多处理漫画册数（0 为无限制）")
    parser.add_argument("--api-url", help="NAS 纸间服务 API 地址（如 http://192.168.31.233:8000），处理完毕后自动远程通知入库")
    parser.add_argument("--token", help="纸间 Machine API Token 认证口令")
    parser.add_argument("--sync-local", action="store_true", help="处理完成后直接同步本地 SQLite 索引（同机/本地测试适用）")
    parser.add_argument("--status", action="store_true", help="仅查看书库 OCR 伴生文件覆盖统计")

    args = parser.parse_args()
    data_dir = resolve_data_dir(args.data_dir)

    print(f"📁 目标漫画数据目录: {data_dir}")

    if args.status:
        print("🔍 正在统计全库漫画 OCR 伴生文件覆盖率...")
        st = get_library_stats(data_dir)
        total_c = st["total_comics"]
        ocr_c = st["ocr_comics"]
        total_p = st["total_pages"]
        ocr_p = st["ocr_pages"]
        pct_c = (ocr_c / total_c * 100) if total_c else 0
        pct_p = (ocr_p / total_p * 100) if total_p else 0
        print("=" * 56)
        print(f"📚 藏书册数:     {total_c} 本 (已有 OCR 伴生: {ocr_c} 本, 覆盖率 {pct_c:.1f}%)")
        print(f"📄 画页总数:     {total_p} 页 (已有 OCR 伴生: {ocr_p} 页, 覆盖率 {pct_p:.1f}%)")
        print(f"💬 FTS5 索引台词: {st['fts_dialogues']} 条")
        print("=" * 56)
        return 0

    if RapidOCR is None or Image is None:
        print("❌ 错误: 当前 Python 环境缺少 OCR 必要依赖 (rapidocr_onnxruntime / Pillow)。", file=sys.stderr)
        print("💡 请在算力机上运行一键安装命令:", file=sys.stderr)
        print("   bash scripts/ocr.sh install (或 pip install -r scripts/requirements-ocr.txt)", file=sys.stderr)
        return 1

    # 初始化 OCR 引擎（主线程预热验证）
    print(f"⚡ 正在初始化 RapidOCR 深度学习推理引擎 (并发线程数: {args.workers})...")
    t0 = time.time()
    get_engine()
    print(f"✅ OCR 引擎初始化就绪 ({time.time() - t0:.2f}s)")

    # 1. 单张画页定向处理模式
    if args.image:
        img_p = Path(args.image).resolve()
        if not img_p.is_file():
            print(f"❌ 错误: 指定的图片文件不存在 ({args.image})", file=sys.stderr)
            return 1
        out_p = img_p.with_name(f"{img_p.stem}.ocr.json")
        print(f"🎯 单张画页定向处理: {img_p.name}")
        t1 = time.time()
        res = process_image(img_p, out_p, force=args.force, min_score=args.min_score)
        if res is None:
            print(f"⚡ 画页伴生文件已是最新且合法，无需更新 ({out_p.name})。如需强制重提请加 --force")
        else:
            print(f"✅ 处理完成 ({time.time() - t1:.2f}s): 提取对白 {res} 条 ➔ {out_p.name}")
            parts = img_p.parts
            if "library" in parts:
                lib_idx = parts.index("library")
                if len(parts) > lib_idx + 2:
                    src, sid = parts[lib_idx + 1], parts[lib_idx + 2]
                    if args.api_url:
                        notify_nas_sync(args.api_url, src, sid, token=args.token)
                    elif args.sync_local:
                        try:
                            sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
                            from app.db import sync_comic_dialogues
                            synced = sync_comic_dialogues(src, sid, force=True)
                            print(f"  💾 本地 SQLite 索引已同步 ({src}/{sid}: {synced} 条)")
                        except Exception as e:
                            print(f"  ⚠️ 本地 SQLite 同步异常: {e}", file=sys.stderr)
        return 0

    # 2. 批量扫描待处理漫画
    library_dir = data_dir / "library"
    if not library_dir.is_dir():
        print(f"❌ 错误: 未在数据目录中找到 library 子目录 ({library_dir})", file=sys.stderr)
        return 1

    page_filter = parse_page_filter(args.page)
    if page_filter:
        print(f"🎯 页码过滤模式已启用: 限定提取页码 {sorted(page_filter)}")

    target_comics: List[Tuple[str, str, Path]] = []
    sources = [args.source] if args.source else ["jm", "local", "picacg"]

    for src in sources:
        s_dir = library_dir / src
        if not s_dir.is_dir():
            continue
        if args.id:
            c_dir = s_dir / args.id
            if c_dir.is_dir():
                target_comics.append((src, args.id, c_dir))
        else:
            for c in sorted(s_dir.iterdir()):
                if c.is_dir() and not c.name.startswith("."):
                    target_comics.append((src, c.name, c))

    if not target_comics:
        print("ℹ️ 未发现符合条件的待处理漫画。")
        return 0

    if args.limit and args.limit > 0:
        target_comics = target_comics[: args.limit]

    print(f"🎯 待处理漫画: 共 {len(target_comics)} 本")

    total_extracted_dialogues = 0
    total_processed_pages = 0
    total_skipped_pages = 0

    for idx, (src, sid, c_dir) in enumerate(target_comics, start=1):
        pages = collect_comic_pages(c_dir, page_filter=page_filter)
        if not pages:
            continue

        # 🚀 漫画级预检快速跳过 (Comic-level instant bypass)
        # 若未指定 force，快速扫描画页修改时间与伴生文件合法性
        if not args.force:
            pending_pages = [
                (img_p, out_p)
                for img_p, out_p in pages
                if not out_p.exists()
                or not is_valid_ocr_sidecar(out_p)
                or img_p.stat().st_mtime > out_p.stat().st_mtime
            ]
        else:
            pending_pages = pages

        if not pending_pages:
            total_skipped_pages += len(pages)
            print(f"[{idx}/{len(target_comics)}] ⚡ 跳过 {src}/{sid}: 全部 {len(pages)} 页伴生文件已是最新 (0ms 增量命中)")
            continue

        skipped_in_comic = len(pages) - len(pending_pages)
        total_skipped_pages += skipped_in_comic
        print(f"\n[{idx}/{len(target_comics)}] 开始提取 {src}/{sid} (待处理 {len(pending_pages)}/{len(pages)} 页, 线程数: {args.workers})...")
        comic_dialogues = 0
        comic_new_pages = 0

        # 多线程并发处理待提取画页
        workers_count = max(1, min(args.workers, len(pending_pages)))
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers_count) as executor:
            future_to_page = {
                executor.submit(process_image, img_p, out_p, args.force, args.min_score): (img_p, out_p)
                for img_p, out_p in pending_pages
            }
            done_count = 0
            for future in concurrent.futures.as_completed(future_to_page):
                done_count += 1
                img_p, out_p = future_to_page[future]
                try:
                    res = future.result()
                    if res is not None:
                        comic_new_pages += 1
                        comic_dialogues += res
                        total_extracted_dialogues += res
                        total_processed_pages += 1
                except Exception as e:
                    print(f"\n⚠️ 处理画页异常 {img_p.name}: {e}", file=sys.stderr)

                sys.stdout.write(f"\r  - 进度: {done_count}/{len(pending_pages)} 页完成 (本册累计检出 {comic_dialogues} 处对白)")
                sys.stdout.flush()

        print(f"\r  ✓ 完成 {src}/{sid}: 新提取 {comic_new_pages} 页, 增量跳过 {skipped_in_comic} 页, 获得 {comic_dialogues} 处对白")

        # 触发同步回调 (当有新画页提取或开启 force 时)
        if comic_new_pages > 0 or args.force:
            if args.api_url:
                notify_nas_sync(args.api_url, src, sid, token=args.token)
            elif args.sync_local:
                try:
                    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
                    from app.db import sync_comic_dialogues
                    synced = sync_comic_dialogues(src, sid)
                    print(f"  💾 本地 SQLite 索引已同步 ({synced} 条)")
                except Exception as e:
                    print(f"  ⚠️ 本地 SQLite 同步异常: {e}", file=sys.stderr)

    print("\n" + "=" * 56)
    print(f"🎉 批处理完成！新处理画页: {total_processed_pages} 页, 增量跳过: {total_skipped_pages} 页, 提取对白: {total_extracted_dialogues} 条")
    if not args.api_url and not args.sync_local:
        print("💡 提示: 伴生文件已安全落盘至漫画画页目录。若要写入 SQLite FTS5，请执行:")
        print("   bash scripts/ocr.sh sync (或通过 HTTP 通知 NAS API)")
    print("=" * 56)

    return 0


if __name__ == "__main__":
    sys.exit(main())
