"""本机台词索引同步入口：python -m app.ocr.sync，不依赖画页 OCR 推理环境。"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .files import (
    image_comic_key,
    image_extensions,
    list_comics,
    parse_directory_name,
    parse_path,
    resolve_data_dir,
)


def main() -> int:
    """校验所选书库、初始化独立台词库，复用现有按本增量同步。"""
    parser = argparse.ArgumentParser(allow_abbrev=False, description="把本机书库的 *.ocr.json 增量同步至独立台词索引库")
    parser.add_argument("--source", type=parse_directory_name, help="限定 library/ 下的图源目录")
    parser.add_argument("--id", type=parse_directory_name, help="限定书号；配合 --source 可清理已删除的单本索引")
    parser.add_argument("--image", type=parse_path, help="只同步所选书库中这张画页所属的漫画")
    parser.add_argument("--data-dir", type=parse_path, help="目标 data 目录（默认环境变量或自动探测）")
    parser.add_argument("--force", action="store_true", help="即使伴生文件未变化也重新入库")
    parser.add_argument("--no-cleanup", action="store_true", help="禁用全库孤儿索引清理")
    parser.add_argument("--limit", type=int, default=0, help="本轮最多更新的漫画册数；已完成的本不占名额（0 为不限）")
    parser.add_argument("--skip-vectors", action="store_true", help="本轮只更新关键词，向量留待后续普通同步补建")
    parser.add_argument(
        "--status", action="store_true", help="查看本机索引的待建/失败向量和历史未核验原图页数，不执行同步"
    )
    parser.add_argument("--check", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.limit < 0:
        parser.error("--limit 必须大于或等于 0")
    if args.image and (args.source is not None or args.id is not None):
        parser.error("--image 不能与 --source / --id 混用")
    try:
        data_dir = resolve_data_dir(args.data_dir)
        library_dir = data_dir / "library"
        if not library_dir.is_dir():
            raise ValueError(f"Library directory not found at {library_dir}")
        if args.image:
            image = Path(args.image).expanduser()
            if not image.is_file() or image.is_symlink() or image.suffix.lower() not in image_extensions():
                raise ValueError(f"指定的图片不存在、是符号链接或格式不受支持: {image}")
            targets = [image_comic_key(image, data_dir)]
            if not list_comics(library_dir, *targets[0]):
                raise ValueError("所选图片的图源或漫画目录是隐藏目录或符号链接")
        elif args.source and args.id:
            # 目录已删除时仍允许显式清理这一本；存在但经符号链接访问时拒绝。
            comic = library_dir / args.source / args.id
            if (library_dir / args.source).is_symlink() or comic.is_symlink():
                raise ValueError("同步目标不能是符号链接")
            if args.source.startswith(".") or args.id.startswith("."):
                raise ValueError("同步目标不能是隐藏目录")
            targets = [(args.source, args.id)]
        else:
            if args.source and not (library_dir / args.source).is_dir():
                raise ValueError(f"Source directory not found: {args.source}")
            targets = [(src, sid) for src, sid, _ in list_comics(library_dir, args.source, args.id)]
            if (args.source or args.id) and not targets:
                raise ValueError(f"Comic not found: {args.source or '*'}/{args.id or '*'}")
    except (ValueError, OSError) as exc:
        parser.error(str(exc))

    # 配置在后端 import 时读取；GPU 进程只提取，应用解释器在这个独立进程里入库。
    os.environ["COMIC_SHELF_DATA"] = str(data_dir)
    try:
        from ..db.connection import get_dialogue_db
        from ..db.dialogues import cleanup_orphan_comic_dialogues, comic_dialogues_need_sync, sync_comic_dialogues
        from ..db.schema import init_dialogue_db

        init_dialogue_db()
    except Exception as exc:
        print(f"❌ 初始化本机台词索引失败 ({data_dir}): {exc}", file=sys.stderr)
        return 1
    if args.check:
        return 0

    print(f"📁 同步目标: {data_dir}，共 {len(targets)} 本")
    if args.status:
        from ..db.dialogues import dialogue_vector_status

        status = dialogue_vector_status()
        print(
            f"语义可用: {status['available']}；编码完成: {status['complete']}；"
            f"待建 {status['pending_comics']} 本，失败 {status['failed_comics']} 本，"
            f"模型不匹配 {status['model_mismatch_comics']} 本，历史未核验 {status['unverified_pages']} 页"
        )
        return 0
    failed = 0
    total = 0
    # 点名同步不能顺带删除其他书籍的索引；全库同步保留原有孤儿清理。
    if not args.no_cleanup and not (args.source or args.id or args.image):
        try:
            purged = cleanup_orphan_comic_dialogues(data_dir)
            if purged:
                print(f"🧹 清理 {purged} 本已删除漫画的索引")
        except Exception as exc:
            failed += 1
            print(f"❌ 孤儿索引清理失败: {exc}", file=sys.stderr)
    updated = 0
    for source, sid in targets:
        try:
            if not args.force and not comic_dialogues_need_sync(source, sid, sync_vectors=not args.skip_vectors):
                continue
            if args.limit and updated >= args.limit:
                print(f"⏹ 已更新 {updated} 本，其余留待下次运行")
                break
            count = sync_comic_dialogues(
                source, sid, force=args.force, sync_vectors=not args.skip_vectors, strict_vectors=True
            )
            updated += 1
            total += count
            with get_dialogue_db() as conn:
                unverified = conn.execute(
                    "SELECT unverified_pages FROM comic_ocr_sync_meta WHERE source = ? AND source_id = ?", (source, sid)
                ).fetchone()[0]
            print(
                f"  {source}/{sid}: {count} 条文字（含副文本；{'向量待建' if args.skip_vectors else '关键词与可用向量已同步'}）"
                f"；历史原图对应关系未核验 {unverified} 页"
            )
        except Exception as exc:
            failed += 1
            print(f"❌ 同步失败 {source}/{sid}: {exc}", file=sys.stderr)
    print(f"{'⚠️ 同步有失败' if failed else '✅ 同步完成'}：更新 {updated} 本、{total} 条文字，{failed} 项失败")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
