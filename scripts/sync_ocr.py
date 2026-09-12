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


def detect_data_dir() -> Path:
    """Smartly detects data directory from env, NAS mount, or local backend."""
    env_val = os.getenv("COMIC_SHELF_DATA", "").strip()
    if env_val:
        p = Path(env_val).expanduser().resolve()
        if p.is_dir():
            return p

    nas_cand = Path("/mnt/nas_manga/library")
    if nas_cand.is_dir():
        return Path("/mnt/nas_manga")

    default_data = BACKEND_DIR / "data"
    default_data.mkdir(parents=True, exist_ok=True)
    return default_data


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sync sidecar *.ocr.json comic dialogues into SQLite FTS5 table"
    )
    parser.add_argument("--source", type=str, default=None, help="Target comic source (e.g. jm, local, picacg)")
    parser.add_argument("--id", type=str, default=None, help="Target comic ID")
    parser.add_argument("--data-dir", type=str, default=None, help="Explicit data directory path")
    parser.add_argument("--force", action="store_true", help="Force re-indexing even if OCR files are unchanged")
    parser.add_argument("--no-cleanup", action="store_true", help="Disable orphan dialogue cleanup")
    args = parser.parse_args()

    if args.data_dir:
        data_dir = Path(args.data_dir).expanduser().resolve()
    else:
        data_dir = detect_data_dir()

    print(f"📁 Using data directory: {data_dir}")

    # Set DB path and initialize
    os.environ["COMIC_SHELF_DATA"] = str(data_dir)
    from app.db import cleanup_orphan_comic_dialogues, get_db, init_db, set_db_path, sync_comic_dialogues

    db_file = data_dir / "comic_shelf.db"
    set_db_path(db_file)
    init_db(db_file)

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
    targets: list[tuple[str, str]] = []
    if args.source and args.id:
        targets.append((args.source, args.id))
    elif args.source:
        src_dir = library_dir / args.source
        if src_dir.is_dir():
            for comic_dir in sorted(src_dir.iterdir()):
                if comic_dir.is_dir() and not comic_dir.name.startswith("."):
                    targets.append((args.source, comic_dir.name))
    else:
        for src_dir in sorted(library_dir.iterdir()):
            if src_dir.is_dir() and not src_dir.name.startswith("."):
                source_name = src_dir.name
                for comic_dir in sorted(src_dir.iterdir()):
                    if comic_dir.is_dir() and not comic_dir.name.startswith("."):
                        targets.append((source_name, comic_dir.name))

    print(f"🔍 Discovered {len(targets)} comic(s) to scan...")
    total_indexed = 0
    comics_synced = 0
    fresh_indexed_count = 0

    # 预加载已有增量元数据
    with get_db() as conn:
        meta_rows = {
            (r["source"], r["source_id"]): (float(r["last_synced_mtime"]), int(r["dialogue_count"]))
            for r in conn.execute("SELECT source, source_id, last_synced_mtime, dialogue_count FROM comic_ocr_sync_meta")
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
