"""Unit tests for comic deletion cascade purge and immediate shelf sync."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import app.db as db_mod
from app.models import ComicMeta
from app.storage.base import ComicStoreBase


class TestDeleteCascade(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.temp_db = Path(self.tmp_dir.name) / "test_shelf.db"
        db_mod.init_db(self.temp_db)
        self.storage = ComicStoreBase(root=Path(self.tmp_dir.name))

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_delete_comic_cascade_purges_all_records(self):
        source = "testsrc"
        source_id = "comic999"

        # 1. Prepare comic on disk and in DB
        comic_dir = self.storage.comic_dir(source, source_id)
        comic_dir.mkdir(parents=True, exist_ok=True)
        (comic_dir / "album.json").write_text("{}", encoding="utf-8")

        meta = ComicMeta(
            source=source,
            source_id=source_id,
            display_id=source_id,
            title="测试删除漫画",
            page_count=10,
            chapters=[],
            pages=[],
        )
        db_mod.upsert_comic_index({
            "source": meta.source,
            "source_id": meta.source_id,
            "display_id": meta.display_id,
            "title": meta.title,
            "authors_json": json.dumps(meta.authors, ensure_ascii=False),
            "works_json": json.dumps(meta.works, ensure_ascii=False),
            "actors_json": json.dumps(meta.actors, ensure_ascii=False),
            "tags_json": json.dumps(meta.tags, ensure_ascii=False),
            "chapter_titles_json": json.dumps([c.title for c in meta.chapters], ensure_ascii=False),
            "page_count": meta.page_count,
            "cached_pages": 10,
            "cover_count": meta.cover_count,
            "cover_indices_json": json.dumps(meta.cover_indices, ensure_ascii=False),
            "views": "0",
            "likes": "0",
            "uploaded_at": "",
            "published_at": "",
            "updated_at": "",
            "imported_at": "",
            "hidden_from_guest": 0,
            "mtime": 12345.0,
            "auto_update_interval_days": 15,
            "last_auto_checked_at": "",
        })

        # 2. Add user favorite, progress, direct pass
        db_mod.set_user_favorite("curator", source, source_id, True)
        db_mod.set_user_progress("curator", source, source_id, 5, 10)
        db_mod.create_direct_pass(source, source_id, page_index=1, ttl_seconds=86400)

        # Verify DB records exist
        self.assertTrue(db_mod.is_user_favorite("curator", source, source_id))
        self.assertIsNotNone(db_mod.get_user_progress("curator", source, source_id))
        rows, total = db_mod.query_library_index(user_id="curator", is_curator=True, page=1, page_size=20)
        self.assertTrue(any(r["source_id"] == source_id for r in rows))

        # 3. Execute storage delete (which should trigger cascade purge and delete disk files)
        ok = self.storage.delete(source, source_id)
        self.assertTrue(ok)
        self.assertFalse(comic_dir.exists())

        # 4. Verify everything in DB is completely removed in ONE single operation
        self.assertFalse(db_mod.is_user_favorite("curator", source, source_id))
        self.assertIsNone(db_mod.get_user_progress("curator", source, source_id))

        with db_mod.get_db() as conn:
            dp_count = conn.execute(
                "SELECT COUNT(*) as cnt FROM direct_passes WHERE source = ? AND source_id = ?",
                (source, source_id),
            ).fetchone()["cnt"]
            self.assertEqual(dp_count, 0)

            idx_count = conn.execute(
                "SELECT COUNT(*) as cnt FROM comics_index WHERE source = ? AND source_id = ?",
                (source, source_id),
            ).fetchone()["cnt"]
            self.assertEqual(idx_count, 0)

        rows_after, total_after = db_mod.query_library_index(
            user_id="curator", is_curator=True, page=1, page_size=20
        )
        self.assertFalse(any(r["source_id"] == source_id for r in rows_after))
        print("  ✓ test_delete_comic_cascade_purges_all_records passed")


if __name__ == "__main__":
    unittest.main()
