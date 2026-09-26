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

    # 3. 插入一部漫画，自然写失效
    db_mod.upsert_comic_index(_make_comic("c1", "测试漫画", ["纯爱", "校园"], 10))

    # 4. 写后读取立即获取最新真实数据（即时强一致性，无延迟）
    res3 = db_mod.get_library_facets(is_curator=True)
    assert res3["stats"]["total_books"] == 1
    assert res3["stats"]["total_pages"] == 10
    tags = dict(res3["top_tags"])
    assert tags["纯爱"] == 1
    assert tags["校园"] == 1

    # 5. 再次写入漫画，下一次读自然更新
    db_mod.upsert_comic_index(_make_comic("c2", "测试漫画2", ["冒险"], 5))
    res4 = db_mod.get_library_facets(is_curator=True)
    assert res4["stats"]["total_books"] == 2
    assert res4["stats"]["total_pages"] == 15
    tags4 = dict(res4["top_tags"])
    assert tags4["冒险"] == 1

    # 6. bypass_cache=True 跳过缓存强制重算
    res5 = db_mod.get_library_facets(is_curator=True, bypass_cache=True)
    assert res5["stats"]["total_books"] == 2
    assert res5["stats"]["total_pages"] == 15

    # 7. 删除漫画自然触发写失效并即时生效
    db_mod.purge_comic_db_records("local", "c1")
    res6 = db_mod.get_library_facets(is_curator=True)
    assert res6["stats"]["total_books"] == 1
    assert "纯爱" not in dict(res6["top_tags"])


def test_facets_cache_toctou_write_during_compute():
    """验证重算期间并发写操作时，TOCTOU 竞态保护生效，不会造成永久脏读。"""
    temp_dir = tempfile.mkdtemp()
    db_file = Path(temp_dir) / "test_facets_toctou.db"
    db_mod.set_db_path(db_file)
    db_mod.init_db()

    # 初始有一本书
    db_mod.upsert_comic_index(_make_comic("c1", "漫画1", ["标签1"], 10))
    res1 = db_mod.get_library_facets(is_curator=True)
    assert res1["stats"]["total_books"] == 1

    # 模拟计算中途发生写操作
    original_compute = db_mod._compute_library_facets

    def _simulated_compute(is_curator: bool, source: str | None = None):
        # 在计算开始后模拟并发写入新书
        db_mod.upsert_comic_index(_make_comic("c2", "并发漫画", ["并发标签"], 20))
        return original_compute(is_curator=is_curator, source=source)

    db_mod._compute_library_facets = _simulated_compute
    try:
        # bypass_cache 触发重算
        res2 = db_mod.get_library_facets(is_curator=True, bypass_cache=True)
    finally:
        db_mod._compute_library_facets = original_compute

    # 下一次正常读必须能够发现缓存失效并拿到最新结果（包含并发写入的书）
    res3 = db_mod.get_library_facets(is_curator=True)
    assert res3["stats"]["total_books"] == 2


def test_facets_incremental_updates_and_scopes():
    temp_dir = tempfile.mkdtemp()
    db_file = Path(temp_dir) / "test_facets_scopes.db"
    db_mod.set_db_path(db_file)
    db_mod.init_db()

    # 1. 插入 JM 书 (公开)
    jm_comic = _make_comic("jm1", "JM漫画", ["jm_tag", "shared_tag"], 20)
    jm_comic["source"] = "jm"
    jm_comic["cached_pages"] = 10
    jm_comic["hidden_from_guest"] = 0
    db_mod.upsert_comic_index(jm_comic)

    # 2. 插入 PicAcg 书 (访客隐藏)
    pic_comic = _make_comic("pic1", "哔咔漫画", ["pic_tag", "shared_tag"], 30)
    pic_comic["source"] = "picacg"
    pic_comic["cached_pages"] = 30
    pic_comic["hidden_from_guest"] = 1
    db_mod.upsert_comic_index(pic_comic)

    # 3. 馆长视角全库
    admin_all = db_mod.get_library_facets(is_curator=True)
    assert admin_all["stats"]["total_books"] == 2
    assert admin_all["stats"]["total_pages"] == 50
    assert admin_all["stats"]["cached_pages"] == 40
    admin_tags = dict(admin_all["top_tags"])
    assert admin_tags["shared_tag"] == 2
    assert admin_tags["jm_tag"] == 1
    assert admin_tags["pic_tag"] == 1

    # 4. 访客视角全库 (hidden_from_guest = 1 的被排除)
    guest_all = db_mod.get_library_facets(is_curator=False)
    assert guest_all["stats"]["total_books"] == 1
    assert guest_all["stats"]["total_pages"] == 20
    assert guest_all["stats"]["cached_pages"] == 10
    guest_tags = dict(guest_all["top_tags"])
    assert guest_tags["shared_tag"] == 1
    assert guest_tags["jm_tag"] == 1
    assert "pic_tag" not in guest_tags

    # 5. 分源过滤 (JM 源)
    jm_facets = db_mod.get_library_facets(is_curator=True, source="jm")
    assert jm_facets["stats"]["total_books"] == 1
    assert jm_facets["stats"]["total_pages"] == 20
    jm_tags = dict(jm_facets["top_tags"])
    assert jm_tags["jm_tag"] == 1
    assert "pic_tag" not in jm_tags

    # 6. 编辑 JM 书：修改标签与页数
    jm_comic_edit = dict(jm_comic)
    import json
    jm_comic_edit["tags_json"] = json.dumps(["new_tag"], ensure_ascii=False)
    jm_comic_edit["page_count"] = 25
    db_mod.upsert_comic_index(jm_comic_edit)

    admin_after_edit = db_mod.get_library_facets(is_curator=True)
    assert admin_after_edit["stats"]["total_books"] == 2
    assert admin_after_edit["stats"]["total_pages"] == 55
    tags_after = dict(admin_after_edit["top_tags"])
    assert "jm_tag" not in tags_after
    assert tags_after["new_tag"] == 1
    assert tags_after["shared_tag"] == 1

    # 7. 单页缓存推进
    db_mod.update_comic_cached_pages("jm", "jm1", 20)
    admin_after_cache = db_mod.get_library_facets(is_curator=True)
    assert admin_after_cache["stats"]["cached_pages"] == 50

    # 8. 访客可见性切换：将哔咔漫画设为公开
    pic_comic_unhide = dict(pic_comic)
    pic_comic_unhide["hidden_from_guest"] = 0
    db_mod.upsert_comic_index(pic_comic_unhide)

    guest_after_unhide = db_mod.get_library_facets(is_curator=False)
    assert guest_after_unhide["stats"]["total_books"] == 2
    assert guest_after_unhide["stats"]["total_pages"] == 55


if __name__ == "__main__":
    test_facets_cache_hit_and_invalidation()
    test_facets_cache_toctou_write_during_compute()
    test_facets_incremental_updates_and_scopes()
    print("Facets cache unit tests passed!")
