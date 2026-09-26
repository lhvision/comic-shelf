from __future__ import annotations

import sys
import tempfile
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import app.db as db_mod


def _make_comic(source_id: str, title: str, tags: list[str], pages: int) -> dict:
    import json
    return {
        "source": "local",
        "source_id": source_id,
        "display_id": f"LOC_{source_id}",
        "title": title,
        "authors_json": "[]",
        "works_json": "[]",
        "actors_json": "[]",
        "tags_json": json.dumps(tags, ensure_ascii=False),
        "chapter_titles_json": "[]",
        "page_count": pages,
        "cached_pages": pages,
        "cover_count": 4,
        "cover_indices_json": "[]",
        "views": "0",
        "likes": "0",
        "uploaded_at": "2026-01-01",
        "published_at": "2026-01-01",
        "updated_at": "2026-01-01",
        "imported_at": "2026-01-01T10:00:00",
        "hidden_from_guest": 0,
        "mtime": 100.0,
        "auto_update_interval_days": 15,
        "last_auto_checked_at": "",
    }


def test_facets_cache_hit_and_invalidation():
    temp_dir = tempfile.mkdtemp()
    db_file = Path(temp_dir) / "test_facets_cache.db"
    db_mod.set_db_path(db_file)
    db_mod.init_db()

    # 1. 初始空库
    res1 = db_mod.get_library_facets(is_curator=True)
    assert res1["stats"]["total_books"] == 0

    # 2. 第二次读，命中缓存
    res2 = db_mod.get_library_facets(is_curator=True)
    assert res2["stats"]["total_books"] == 0

    # 3. 插入一部漫画
    db_mod.upsert_comic_index(_make_comic("c1", "测试漫画", ["纯爱", "校园"], 10))

    # 4. 强制清空防抖以模拟写后重新聚合
    db_mod.invalidate_facets_cache(force=True)
    res3 = db_mod.get_library_facets(is_curator=True)
    assert res3["stats"]["total_books"] == 1
    assert res3["stats"]["total_pages"] == 10
    tags = dict(res3["top_tags"])
    assert tags["纯爱"] == 1
    assert tags["校园"] == 1

    # 5. 测试防抖：快速连续写入且不强制清空
    db_mod.upsert_comic_index(_make_comic("c2", "测试漫画2", ["冒险"], 5))
    # 在 3 秒防抖保护期内，读操作复用刚刚算出的 res3（防并发风暴）
    res4 = db_mod.get_library_facets(is_curator=True)
    assert res4["stats"]["total_books"] == 1

    # 6. bypass_cache=True 跳过防抖和缓存强制重算
    res5 = db_mod.get_library_facets(is_curator=True, bypass_cache=True)
    assert res5["stats"]["total_books"] == 2
    assert res5["stats"]["total_pages"] == 15

    # 7. 删除漫画并验证即时更新
    db_mod.purge_comic_db_records("local", "c1")
    db_mod.invalidate_facets_cache(force=True)
    res6 = db_mod.get_library_facets(is_curator=True)
    assert res6["stats"]["total_books"] == 1
    assert "纯爱" not in dict(res6["top_tags"])


if __name__ == "__main__":
    test_facets_cache_hit_and_invalidation()
    print("Facets cache unit tests passed!")
