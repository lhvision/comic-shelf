#!/usr/bin/env python3
"""CLI script to synchronize sidecar OCR dialogues (*.ocr.json) into SQLite FTS5."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Add project root and backend dir to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(BACKEND_DIR))

from scripts.ocr_worker import list_comics, resolve_data_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync sidecar *.ocr.json comic dialogues into SQLite FTS5 table")
    parser.add_argument(
        "--source",
        type=str,
        default=None,
        help="Target comic source, a directory under library/ (e.g. jm, local, picacg, copymanga)",
    )
    parser.add_argument("--id", type=str, default=None, help="Target comic ID")
    parser.add_argument("--data-dir", type=str, default=None, help="Explicit data directory path")
    parser.add_argument("--force", action="store_true", help="Force re-indexing even if OCR files are unchanged")
    parser.add_argument("--no-cleanup", action="store_true", help="Disable orphan dialogue cleanup")
    args = parser.parse_args()

    # 自动探测与 worker 共用一份，两边认的永远是同一个书库
    data_dir = Path(args.data_dir).expanduser().resolve() if args.data_dir else resolve_data_dir()

    print(f"📁 Using data directory: {data_dir}")

    # 后端在 import 时按这个变量定数据目录与两个库文件的位置，所以必须先设再导入
    os.environ["COMIC_SHELF_DATA"] = str(data_dir)
    from app.db import cleanup_orphan_comic_dialogues, get_dialogue_db, init_db, sync_comic_dialogues

    init_db()

    # 1. 自动清理已从磁盘删除的孤儿漫画索引
    if not args.no_cleanup:
        orphans_purged = cleanup_orphan_comic_dialogues(data_dir)
        if orphans_purged > 0:
            print(f"🧹 Cleaned {orphans_purged} orphan comic index(es) deleted from disk.")

    library_dir = data_dir / "library"
    if not library_dir.is_dir():
        print(f"⚠️  Library directory not found at {library_dir}")
        return

    # Collect target comics (source, source_id)
    # 点名单本时不要求目录还在：书已删除的话，这一步会把它残留的索引清掉
    if args.source and args.id:
        targets = [(args.source, args.id)]
    else:
        targets = [(src, cid) for src, cid, _ in list_comics(library_dir, args.source)]

    print(f"🔍 Discovered {len(targets)} comic(s) to scan...")
    total_indexed = 0
    comics_synced = 0
    fresh_indexed_count = 0

    # 预加载已有增量元数据
    with get_dialogue_db() as conn:
        meta_rows = {
            (r["source"], r["source_id"]): (float(r["last_synced_mtime"]), int(r["dialogue_count"]))
            for r in conn.execute(
                "SELECT source, source_id, last_synced_mtime, dialogue_count FROM comic_ocr_sync_meta"
            )
        }

    for idx, (src, cid) in enumerate(targets, start=1):
        cached_meta = meta_rows.get((src, cid))
        count = sync_comic_dialogues(src, cid, force=args.force)
        if count > 0:
            comics_synced += 1
            total_indexed += count
            if args.force or cached_meta is None or cached_meta[1] != count:
                print(f"  [{idx}/{len(targets)}] {src}/{cid}: {count} dialogues indexed (updated)")
                fresh_indexed_count += 1
            else:
                # 增量命中
                pass

    print(
        f"✅ Sync complete: {comics_synced}/{len(targets)} comic(s) with OCR ({fresh_indexed_count} updated, "
        f"{comics_synced - fresh_indexed_count} incremental cache hits). Total indexed: {total_indexed} dialogues."
    )


if __name__ == "__main__":
    main()
