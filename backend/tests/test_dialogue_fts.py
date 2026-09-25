from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

# Ensure backend package is importable
BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import app.config as config_mod
import app.db as db_mod
import app.auth as auth_mod
from app.main import (
    search_dialogue_endpoint,
    sync_ocr_endpoint,
    delete_comic,
    store,
)
from fastapi import HTTPException


def make_mock_request(
    path: str = "/api/search/dialogue",
    headers: dict[str, str] | None = None,
    cookies: dict[str, str] | None = None,
    query_params: dict[str, str] | None = None,
) -> MagicMock:
    req = MagicMock()
    req.state = type("State", (), {})()
    req.url.path = path
    headers_dict = {k.lower(): v for k, v in (headers or {}).items()}
    req.headers.get = lambda k, default="": headers_dict.get(k.lower(), default)
    req.cookies.get = lambda k, default="": (cookies or {}).get(k, default)
    req.query_params.get = lambda k, default="": (query_params or {}).get(k, default)
    return req


def make_comic_item(source: str, source_id: str, title: str, hidden_from_guest: int = 0) -> dict:
    return {
        "source": source,
        "source_id": source_id,
        "display_id": source_id,
        "title": title,
        "authors_json": "[]",
        "works_json": "[]",
        "actors_json": "[]",
        "tags_json": "[]",
        "chapter_titles_json": "[]",
        "page_count": 10,
        "cached_pages": 10,
        "cover_count": 1,
        "cover_indices_json": "[0]",
        "views": "0",
        "likes": "0",
        "uploaded_at": "2026-01-01",
        "published_at": "2026-01-01",
        "updated_at": "2026-01-01",
        "imported_at": "2026-01-01",
        "hidden_from_guest": hidden_from_guest,
        "mtime": 100.0,
        "auto_update_interval_days": 15,
        "last_auto_checked_at": "",
    }


def test_dialogue_fts_lifecycle():
    temp_dir = Path(tempfile.mkdtemp())
    try:
        temp_db = temp_dir / "test_dialogue.db"
        db_mod.set_db_path(temp_db)
        db_mod.init_db(temp_db)

        # 1. Verify FTS5 virtual table exists in dedicated dialogue DB
        with db_mod.get_dialogue_db() as conn:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='comic_dialogues_fts'"
            ).fetchone()
            assert row is not None, "comic_dialogues_fts table must exist in dialogue db"

        # 2. Setup mock comic files
        library_dir = temp_dir / "library" / "local" / "c_jojo"
        pages_dir = library_dir / "pages"
        pages_dir.mkdir(parents=True, exist_ok=True)

        config_mod.DATA_DIR = temp_dir
        db_mod.DATA_DIR = temp_dir

        ocr_p1 = {
            "version": 1,
            "lang": "zh",
            "bubbles": [
                {
                    "id": 1,
                    "box": [0.12, 0.45, 0.28, 0.68],
                    "text": "这就是最后的波纹吗，JOJO！",
                    "confidence": 0.98,
                    "orientation": "vertical",
                    "type": "dialogue",
                },
                {
                    "id": 2,
                    "box": [0.55, 0.20, 0.65, 0.40],
                    "text": "收下吧！这是我最后的波纹了！",
                    "confidence": 0.95,
                },
            ],
        }
        (pages_dir / "00001.ocr.json").write_text(json.dumps(ocr_p1, ensure_ascii=False), encoding="utf-8")

        ocr_p2 = {
            "version": 1,
            "lang": "zh",
            "bubbles": [
                {
                    "id": 1,
                    "box": [0.30, 0.30, 0.70, 0.70],
                    "text": "西撒————！",
                    "confidence": 0.99,
                }
            ],
        }
        (pages_dir / "00002.ocr.json").write_text(json.dumps(ocr_p2, ensure_ascii=False), encoding="utf-8")

        # Insert comic into shadow index
        comic_item = make_comic_item("local", "c_jojo", "乔乔的奇妙冒险", 0)
        comic_item["display_id"] = "JOJO-01"
        comic_item["authors_json"] = json.dumps(["荒木飞吕彦"], ensure_ascii=False)
        db_mod.upsert_comic_index(comic_item)

        # 3. Sync dialogues
        synced_count = db_mod.sync_comic_dialogues("local", "c_jojo")
        assert synced_count == 3, f"Expected 3 dialogues, got {synced_count}"

        # 4. Search with simplified query (trigram >= 3)
        # 第 1 页两个气泡都含「最后的波纹」，聚合到页后必须只占 1 行
        res_simp = db_mod.search_dialogues(query="最后的波纹", source="local", limit=10, is_guest=False)
        assert len(res_simp) == 1, f"Expected 1 page for '最后的波纹', got {len(res_simp)}"
        assert res_simp[0]["bubble_count"] == 2, f"同页命中数统计错误: {res_simp[0]['bubble_count']}"
        assert res_simp[0]["display_id"] == "JOJO-01"
        assert res_simp[0]["title"] == "乔乔的奇妙冒险"
        assert res_simp[0]["page_index"] == 1
        assert res_simp[0]["box"], "页级结果必须带上代表气泡坐标，供阅读器高亮"
        assert "<mark>" in res_simp[0]["snippet"]
        assert "</mark>" in res_simp[0]["snippet"]

        # 5. Search with traditional query (bidirectional conversion test)
        res_trad = db_mod.search_dialogues(query="最後的波紋", source="local", limit=10, is_guest=False)
        assert len(res_trad) == 1, f"Expected 1 page for traditional '最後的波紋', got {len(res_trad)}"
        assert "<mark>" in res_trad[0]["snippet"]

        # 6. Search with short 2-character word (LIKE fallback test) & <2 chars guard
        assert db_mod.search_dialogues(query="波", source=None, limit=10, is_guest=False) == [], "Query < 2 chars must be blocked"
        res_short = db_mod.search_dialogues(query="波纹", source=None, limit=10, is_guest=False)
        assert len(res_short) == 1, f"Expected 1 page for '波纹', got {len(res_short)}"
        assert "<mark>波纹</mark>" in res_short[0]["snippet"]

        # 6.5. Wildcard escaping: pure SQL LIKE wildcards must not cause full-table scan match
        assert db_mod.search_dialogues(query="__", source=None, limit=10, is_guest=False) == []
        assert db_mod.search_dialogues(query="%%", source=None, limit=10, is_guest=False) == []

        # 7. Search page 2 dialogue
        res_p2 = db_mod.search_dialogues(query="西撒", source=None, limit=10, is_guest=False)
        assert len(res_p2) == 1
        assert res_p2[0]["page_index"] == 2
        assert res_p2[0]["text"] == "西撒————！"

        # 8. Ghost index prevention & atomic re-sync
        # Remove page 2, replace page 1 with single dialogue
        (pages_dir / "00002.ocr.json").unlink()
        (pages_dir / "00001.ocr.json").write_text(
            json.dumps({
                "version": 1,
                "bubbles": [{"id": 99, "box": [0.1, 0.1, 0.2, 0.2], "text": "人类的赞歌就是勇气的赞歌！"}],
            }),
            encoding="utf-8",
        )
        new_count = db_mod.sync_comic_dialogues("local", "c_jojo")
        assert new_count == 1, f"Expected 1 dialogue after re-sync, got {new_count}"

        # Old dialogues must be gone (no ghost indexes)
        assert len(db_mod.search_dialogues("波纹")) == 0
        assert len(db_mod.search_dialogues("西撒")) == 0
        # New dialogue must be found
        res_new = db_mod.search_dialogues("勇气的赞歌")
        assert len(res_new) == 1
        assert res_new[0]["bubble_id"] == 99

        # 9. Explicit delete_comic_dialogues
        db_mod.delete_comic_dialogues("local", "c_jojo")
        assert len(db_mod.search_dialogues("勇气的赞歌")) == 0

        print("  ✓ Dialogue FTS lifecycle, indexing, and bidirectional search passed")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_dialogue_guest_filtering_and_multi_chapter():
    temp_dir = Path(tempfile.mkdtemp())
    try:
        temp_db = temp_dir / "test_guest.db"
        db_mod.set_db_path(temp_db)
        db_mod.init_db(temp_db)

        config_mod.DATA_DIR = temp_dir
        db_mod.DATA_DIR = temp_dir

        # Comic A: public
        dir_a = temp_dir / "library" / "local" / "comic_a" / "pages"
        dir_a.mkdir(parents=True, exist_ok=True)
        (dir_a / "00001.ocr.json").write_text(
            json.dumps({"bubbles": [{"id": 1, "text": "秘密藏在深山中"}]}),
            encoding="utf-8",
        )
        db_mod.upsert_comic_index(make_comic_item("local", "comic_a", "公开作品", 0))
        db_mod.sync_comic_dialogues("local", "comic_a")

        # Comic B: hidden from guest
        dir_b = temp_dir / "library" / "local" / "comic_b" / "pages"
        dir_b.mkdir(parents=True, exist_ok=True)
        (dir_b / "00001.ocr.json").write_text(
            json.dumps({"bubbles": [{"id": 1, "text": "秘密藏在城堡中"}]}),
            encoding="utf-8",
        )
        db_mod.upsert_comic_index(make_comic_item("local", "comic_b", "私密作品", 1))
        db_mod.sync_comic_dialogues("local", "comic_b")

        # Curator searches "秘密": sees both A and B
        curator_res = db_mod.search_dialogues("秘密", is_guest=False)
        assert len(curator_res) == 2, f"Curator should see 2, got {len(curator_res)}"

        # Guest searches "秘密": only sees A
        guest_res = db_mod.search_dialogues("秘密", is_guest=True)
        assert len(guest_res) == 1, f"Guest should see 1, got {len(guest_res)}"
        assert guest_res[0]["source_id"] == "comic_a"

        # Multi-chapter with album.json global page mapping
        dir_multi = temp_dir / "library" / "local" / "comic_multi"
        chap1_dir = dir_multi / "pages" / "ch1"
        chap2_dir = dir_multi / "pages" / "ch2"
        chap1_dir.mkdir(parents=True, exist_ok=True)
        chap2_dir.mkdir(parents=True, exist_ok=True)

        album_json = {
            "source": "local",
            "source_id": "comic_multi",
            "title": "多章节漫画",
            "pages": [
                {"index": 1, "file": "00001.webp", "chapter": "ch1"},
                {"index": 2, "file": "00002.webp", "chapter": "ch1"},
                {"index": 3, "file": "00001.webp", "chapter": "ch2"},
            ],
        }
        (dir_multi / "album.json").write_text(json.dumps(album_json), encoding="utf-8")

        (chap1_dir / "00001.ocr.json").write_text(
            json.dumps({"bubbles": [{"id": 1, "text": "第一话台词"}]}),
            encoding="utf-8",
        )
        (chap2_dir / "00001.ocr.json").write_text(
            json.dumps({"bubbles": [{"id": 1, "text": "第二话台词"}]}),
            encoding="utf-8",
        )

        db_mod.upsert_comic_index(make_comic_item("local", "comic_multi", "多章节漫画", 0))
        count_multi = db_mod.sync_comic_dialogues("local", "comic_multi")
        assert count_multi == 2

        res_ch2 = db_mod.search_dialogues("第二话台词")
        assert len(res_ch2) == 1
        assert res_ch2[0]["page_index"] == 3, f"Expected global page 3 for ch2 page 1, got {res_ch2[0]['page_index']}"

        print("  ✓ Guest privacy filtering and multi-chapter page index mapping passed")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_dialogue_api_endpoints_and_auth():
    temp_dir = Path(tempfile.mkdtemp())
    old_root = store.root
    try:
        temp_db = temp_dir / "test_api.db"
        db_mod.set_db_path(temp_db)
        db_mod.init_db(temp_db)

        config_mod.DATA_DIR = temp_dir
        db_mod.DATA_DIR = temp_dir
        config_mod.LIBRARY_DIR = temp_dir / "library"
        store.root = temp_dir / "library"

        config_mod.AUTH_SECRET = "test-curator-secret"
        config_mod.MACHINE_TOKEN = "test-machine-token"
        auth_mod.AUTH_SECRET = "test-curator-secret"
        auth_mod.MACHINE_TOKEN = "test-machine-token"

        # Prepare comic with OCR
        c_dir = temp_dir / "library" / "local" / "comic_api"
        pages_dir = c_dir / "pages"
        pages_dir.mkdir(parents=True, exist_ok=True)
        (pages_dir / "00001.ocr.json").write_text(
            json.dumps({"bubbles": [{"id": 1, "box": [0.1, 0.2, 0.3, 0.4], "text": "API测试台词对话"}]}),
            encoding="utf-8",
        )
        (c_dir / "album.json").write_text(
            json.dumps({
                "source": "local",
                "source_id": "comic_api",
                "title": "API测试漫画",
                "pages": [{"index": 1, "file": "00001.webp", "chapter": ""}],
            }),
            encoding="utf-8",
        )
        db_mod.upsert_comic_index(make_comic_item("local", "comic_api", "API测试漫画", 0))

        # 1. Test POST /api/library/local/comic_api/ocr/sync with machine token
        req_machine = make_mock_request(
            "/api/library/local/comic_api/ocr/sync",
            headers={"X-Machine-Token": "test-machine-token"},
        )
        sync_resp = sync_ocr_endpoint("local", "comic_api", req_machine)
        assert sync_resp.ok is True
        assert sync_resp.count == 1

        # 2. Test sync without auth -> 401
        req_unauth = make_mock_request("/api/library/local/comic_api/ocr/sync")
        try:
            sync_ocr_endpoint("local", "comic_api", req_unauth)
            assert False, "Should raise 401"
        except HTTPException as exc:
            assert exc.status_code == 401

        # 3. Test GET /api/search/dialogue with curator auth
        req_curator = make_mock_request(
            "/api/search/dialogue",
            headers={"Authorization": "Bearer test-curator-secret"},
        )
        search_resp = search_dialogue_endpoint(req_curator, q="API测试台词")
        assert search_resp.total == 1
        assert search_resp.results[0].text == "API测试台词对话"

        # 4. Test GET /api/search/dialogue with guest device session
        g_pass = db_mod.create_guest_pass("ApiGuest", expires_days=7, custom_token="guest-token-1")
        dev = db_mod.register_guest_device(g_pass["id"], user_agent="TestDev")
        req_guest = make_mock_request(
            "/api/search/dialogue",
            headers={"X-Device-Token": dev["device_token"]},
        )
        guest_search_resp = search_dialogue_endpoint(req_guest, q="API测试台词")
        assert guest_search_resp.total == 1

        # 5. Test comic deletion clears dialogues
        del_resp = delete_comic("local", "comic_api")
        assert del_resp.ok is True
        # Verify dialogue is deleted
        search_after_del = search_dialogue_endpoint(req_curator, q="API测试台词")
        assert search_after_del.total == 0

        print("  ✓ Dialogue API endpoints, machine token auth, and deletion hooks passed")
    finally:
        store.root = old_root
        config_mod.AUTH_SECRET = ""
        config_mod.MACHINE_TOKEN = ""
        auth_mod.AUTH_SECRET = ""
        auth_mod.MACHINE_TOKEN = ""
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_classify_dialogue_kind_rules():
    """语料分类只靠页位与文本特征，不做任何像素运算。"""
    cls = db_mod.classify_dialogue_kind

    # 水印与页码：汉化组站点名的十几种 OCR 变体一律不入库
    for noise in ("jmcomic", "mcomic", "imcomic", "nenic", "20", "139", "R18", "..."):
        assert cls(10, 42, [noise], noise) is None, f"噪声未识别: {noise!r}"
    # 但长度超标或带中日文字形就不是噪声
    assert cls(10, 42, ["x"], "这是一句很长的纯拉丁台词吗显然不是") == db_mod.DIALOGUE_KIND

    # 特征词在任意页都生效
    assert cls(10, 42, ["本页其他文本"], "图源：七曜苏醒 翻校：有川") == db_mod.PARATEXT_KIND
    assert cls(10, 42, ["本页其他文本"], "诚聘嵌字，审核QQ群：690300374") == db_mod.PARATEXT_KIND
    assert cls(10, 42, ["本页其他文本"], "PixivId:5561441 @kon_ka827") == db_mod.PARATEXT_KIND

    # 书名页标题没有特征词，靠页位兜住（前 2 页）
    assert cls(1, 42, ["只属于老师的坏坏搞蛋鬼"], "只属于老师的坏坏搞蛋鬼") == db_mod.PARATEXT_KIND
    assert cls(3, 42, ["正常正文页的一句話"], "正常正文页的一句話") == db_mod.DIALOGUE_KIND

    # 尾页护栏：剧情常一直画到最后几页，整页像后记才连片判定
    afterword = "后记里的长段落会一直讲创作思路、角色关系与后续计划，句子普遍很长。"
    assert cls(41, 42, [afterword], afterword) == db_mod.PARATEXT_KIND
    short_lines = ["谢谢大家", "老师那个", "还有精神的样子"]
    assert cls(24, 27, short_lines, "谢谢大家") == db_mod.DIALOGUE_KIND, "剧情尾页不得被误判为后记"
    # 尾页里只要有一句带特征词，整页判为副文本（恶搞谢恩页场景）
    assert cls(25, 27, ["还远没到结束的时候", "Mascox:@masco_xxxx"], "还远没到结束的时候") == db_mod.PARATEXT_KIND
    # 但"噪声行"没有这个权力：水印与页码本来就单独不入库，而正文页上也满是水印。
    # 真库 jm/319445 p21 就是被一行认成 "888" 的 "？？？" 连累整页从台词检索里消失（误杀 26 页）
    tail_with_watermark = ["刚刚不是有说还没回礼吗", "圣诞礼物…？", "jmcomic", "888"]
    assert cls(21, 22, tail_with_watermark, "刚刚不是有说还没回礼吗") == db_mod.DIALOGUE_KIND, (
        "尾页有水印就整页判副文本 —— 噪声行不能替整页定性"
    )
    # 水印行自己仍然不入库（两件事互不牵连）
    assert cls(21, 22, tail_with_watermark, "jmcomic") is None

    # 册页数不足以谈"书头书尾"时，位置规则整体失效，只认特征词
    assert cls(1, 6, ["第一页的一句话"], "第一页的一句话") == db_mod.DIALOGUE_KIND
    assert cls(1, 0, ["无 album.json"], "无 album.json 的一句话") == db_mod.DIALOGUE_KIND
    print("  ✓ classify_dialogue_kind rules passed")


def test_paratext_indexed_but_excluded_from_search():
    """副文本必须留在索引里（取料用），但默认台词检索一个字都不能露出来。"""
    import sqlite3

    temp_dir = Path(tempfile.mkdtemp())
    try:
        temp_db = temp_dir / "test_kind.db"
        db_mod.set_db_path(temp_db)
        db_mod.init_db(temp_db)
        config_mod.DATA_DIR = temp_dir
        db_mod.DATA_DIR = temp_dir

        pages_dir = temp_dir / "library" / "local" / "comic_kind" / "pages"
        pages_dir.mkdir(parents=True)
        (pages_dir.parent / "album.json").write_text(
            json.dumps({
                "source": "local",
                "source_id": "comic_kind",
                "page_count": 42,
                "pages": [{"index": i, "file": f"{i:05d}.webp"} for i in range(1, 43)],
            }),
            encoding="utf-8",
        )

        def write_page(page: int, texts: list[str]) -> None:
            (pages_dir / f"{page:05d}.ocr.json").write_text(
                json.dumps({
                    "version": 1,
                    "engine": "rapidocr",
                    "bubbles": [
                        {"id": i, "order": i, "box": [0.1 * i, 0.1, 0.1 * i + 0.05, 0.4], "text": t}
                        for i, t in enumerate(texts, start=1)
                    ],
                }, ensure_ascii=False),
                encoding="utf-8",
            )

        # 「喜欢你」同时出现在正文与副文本里，只有正文那条允许被搜到
        write_page(1, ["只属于老师的坏坏搞蛋鬼", "喜欢你这句话印在封面上"])
        write_page(20, ["我喜欢你", "jmcomic", "20"])
        write_page(41, ["后记α首先我想说的是、这次登场的老师跟之前不是同一个人，也就是平行世界的感觉。"])

        synced = db_mod.sync_comic_dialogues("local", "comic_kind")
        assert synced == 4, f"两条噪声（jmcomic / 20）必须丢弃，实际入库 {synced} 条"

        with db_mod.get_dialogue_db() as conn:
            by_kind = conn.execute(
                "SELECT kind, group_concat(text, ' | ') AS texts FROM comic_dialogues_fts GROUP BY kind"
            ).fetchall()
        kinds = {r["kind"]: r["texts"] for r in by_kind}
        assert kinds[db_mod.DIALOGUE_KIND] == "我喜欢你", f"正文侧混进了非台词: {kinds}"
        assert "后记α" in kinds[db_mod.PARATEXT_KIND] and "封面上" in kinds[db_mod.PARATEXT_KIND]

        res = db_mod.search_dialogues("喜欢你", source="local", limit=10)
        assert [r["page_index"] for r in res] == [20], f"检索露出了副文本页: {[r['page_index'] for r in res]}"

        # 噪声连一行都没有：整表 4 行，其中无 jmcomic
        with db_mod.get_dialogue_db() as conn:
            junk = conn.execute("SELECT count(*) AS c FROM comic_dialogues_fts WHERE text IN ('jmcomic','20')").fetchone()["c"]
        assert junk == 0

        # 旧八列表（有 reading_order、无 kind）同样要触发整表重建
        old_db = temp_dir / "legacy_kind.db"
        with sqlite3.connect(old_db) as old_conn:
            old_conn.execute(
                """
                CREATE VIRTUAL TABLE comic_dialogues_fts USING fts5(
                    source UNINDEXED, source_id UNINDEXED, page_index UNINDEXED,
                    bubble_id UNINDEXED, text, lang UNINDEXED, box_json UNINDEXED,
                    reading_order UNINDEXED, tokenize='trigram'
                )
                """
            )
            old_conn.execute(
                """
                CREATE TABLE comic_ocr_sync_meta (
                    source TEXT NOT NULL, source_id TEXT NOT NULL,
                    last_synced_mtime REAL NOT NULL DEFAULT 0.0,
                    dialogue_count INTEGER NOT NULL DEFAULT 0,
                    updated_at INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (source, source_id)
                )
                """
            )
            old_conn.execute("INSERT INTO comic_ocr_sync_meta VALUES ('local', 'comic_kind', 9e12, 4, 0)")
            old_conn.commit()
        db_mod.init_dialogue_db(old_db)
        with db_mod.get_dialogue_db() as conn:
            columns = {row[1] for row in conn.execute("PRAGMA table_info(comic_dialogues_fts)")}
            stale = conn.execute(
                "SELECT last_synced_mtime AS m FROM comic_ocr_sync_meta WHERE source_id = 'comic_kind'"
            ).fetchone()
        assert "kind" in columns, f"缺 kind 列没有触发重建: {columns}"
        # 9e12 的假 mtime 一旦被留下来，mtime 增量判断会永久跳过这本书的重灌
        assert stale is None or float(stale["m"]) < 9e12, f"残留增量元数据会短路重灌: {stale['m']}"
        # 重建自带回填：不必人工再 sync 就能检索，且分类规则照样生效
        assert [r["page_index"] for r in db_mod.search_dialogues("喜欢你")] == [20]
        assert db_mod.sync_comic_dialogues("local", "comic_kind") == 4
        print("  ✓ Paratext kept in index yet hidden from dialogue search passed")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_reading_order_roundtrip_and_legacy_rebuild():
    """reading_order 以 .ocr.json 的 order 为准入库；旧七列表结构能被自动重建。"""
    import sqlite3

    temp_dir = Path(tempfile.mkdtemp())
    try:
        temp_db = temp_dir / "test_order.db"
        db_mod.set_db_path(temp_db)
        db_mod.init_db(temp_db)
        config_mod.DATA_DIR = temp_dir
        db_mod.DATA_DIR = temp_dir

        pages_dir = temp_dir / "library" / "local" / "comic_order" / "pages"
        pages_dir.mkdir(parents=True, exist_ok=True)
        # 数组次序刻意与 order 相反：入库必须以显式 order 为准，不能靠下标猜
        (pages_dir / "00001.ocr.json").write_text(
            json.dumps({
                "version": 1,
                "engine": "rapidocr",
                "bubbles": [
                    {"id": 7, "order": 2, "box": [0.5, 0.1, 0.7, 0.4], "text": "第二句台词在这里"},
                    {"id": 3, "order": 1, "box": [0.1, 0.6, 0.3, 0.9], "text": "第一句台词在这里"},
                ],
            }, ensure_ascii=False),
            encoding="utf-8",
        )

        assert db_mod.sync_comic_dialogues("local", "comic_order") == 2

        with db_mod.get_dialogue_db() as conn:
            rows = conn.execute(
                "SELECT bubble_id, reading_order, text FROM comic_dialogues_fts"
                " ORDER BY page_index, reading_order"
            ).fetchall()
        assert [r["reading_order"] for r in rows] == [1, 2], f"Expected order 1,2 got {rows[:]}"
        assert [r["bubble_id"] for r in rows] == [3, 7], "顺序必须跟随 order，而非气泡 id 或数组下标"

        # 旧伴生文件缺 order 时退回数组下标，reading_order 永不为空
        legacy_pages = temp_dir / "library" / "local" / "comic_noorder" / "pages"
        legacy_pages.mkdir(parents=True, exist_ok=True)
        (legacy_pages / "00001.ocr.json").write_text(
            json.dumps({"bubbles": [{"id": 1, "box": [0.1, 0.1, 0.2, 0.2], "text": "无序号台词一条"}]}),
            encoding="utf-8",
        )
        db_mod.sync_comic_dialogues("local", "comic_noorder")
        with db_mod.get_dialogue_db() as conn:
            got = conn.execute(
                "SELECT reading_order FROM comic_dialogues_fts WHERE source_id = 'comic_noorder'"
            ).fetchone()
        assert got is not None and int(got["reading_order"]) == 1

        # 旧七列表 + 残留 sync 元数据：重建后必须补上列且清空元数据，
        # 否则 mtime 增量判断会认为已同步、跳过重灌，检索永久返空
        old_db = temp_dir / "legacy_dialogues.db"
        with sqlite3.connect(old_db) as old_conn:
            old_conn.execute(
                """
                CREATE VIRTUAL TABLE comic_dialogues_fts USING fts5(
                    source UNINDEXED, source_id UNINDEXED, page_index UNINDEXED,
                    bubble_id UNINDEXED, text, lang UNINDEXED, box_json UNINDEXED,
                    tokenize='trigram'
                )
                """
            )
            old_conn.execute(
                """
                CREATE TABLE comic_ocr_sync_meta (
                    source TEXT NOT NULL, source_id TEXT NOT NULL,
                    last_synced_mtime REAL NOT NULL DEFAULT 0.0,
                    dialogue_count INTEGER NOT NULL DEFAULT 0,
                    updated_at INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (source, source_id)
                )
                """
            )
            old_conn.execute(
                "INSERT INTO comic_ocr_sync_meta VALUES ('local', 'comic_order', 9e12, 2, 0)"
            )
            old_conn.commit()

        db_mod.init_dialogue_db(old_db)

        with db_mod.get_dialogue_db() as conn:
            columns = {row[1] for row in conn.execute("PRAGMA table_info(comic_dialogues_fts)")}
            stale = conn.execute(
                "SELECT last_synced_mtime AS m FROM comic_ocr_sync_meta WHERE source_id = 'comic_order'"
            ).fetchone()
        assert "reading_order" in columns, f"重建后仍缺列: {columns}"
        assert "kind" in columns, f"重建后仍缺列: {columns}"
        # 9e12 那个假 mtime 绝不能留着：它会认为「已同步」而永久跳过重灌。
        # 重建自带回填，所以元数据允许被重新写入，但必须是真实 mtime 量级
        assert stale is None or float(stale["m"]) < 9e12, f"残留的增量元数据会短路重灌: {stale['m']}"

        # 回填已经把索引灌回来了，不必人工再同步一次就能搜到
        assert len(db_mod.search_dialogues("台词在这里", source="local")) == 1
        assert db_mod.sync_comic_dialogues("local", "comic_order") == 2
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_bm25_relevance_ordering():
    """检索必须按 bm25 相关度返回，而不是 FTS5 的行号（写入）顺序。"""
    temp_dir = Path(tempfile.mkdtemp())
    try:
        temp_db = temp_dir / "test_rank.db"
        db_mod.set_db_path(temp_db)
        db_mod.init_db(temp_db)
        config_mod.DATA_DIR = temp_dir
        db_mod.DATA_DIR = temp_dir

        pages_dir = temp_dir / "library" / "local" / "comic_rank" / "pages"
        pages_dir.mkdir(parents=True, exist_ok=True)
        long_line = (
            "那天晚上他站在走廊尽头犹豫了很久，最终还是没有说出喜欢你，"
            "只是把所有话都咽了回去，让旁观的人替他把这份心意猜了半天。"
        )
        # 长句占第 1 页、短句占第 2 页：行号顺序偏向长句，相关度顺序必须偏向短句
        (pages_dir / "00001.ocr.json").write_text(
            json.dumps({
                "version": 1,
                "bubbles": [{"id": 1, "box": [0.1, 0.1, 0.4, 0.4], "text": long_line}],
            }, ensure_ascii=False),
            encoding="utf-8",
        )
        (pages_dir / "00002.ocr.json").write_text(
            json.dumps({
                "version": 1,
                "bubbles": [{"id": 1, "box": [0.6, 0.6, 0.7, 0.8], "text": "我喜欢你"}],
            }, ensure_ascii=False),
            encoding="utf-8",
        )
        assert db_mod.sync_comic_dialogues("local", "comic_rank") == 2

        # 前提：行号顺序与相关度顺序必须相反，否则这条断言没有鉴别力
        with db_mod.get_dialogue_db() as conn:
            by_rowid = conn.execute(
                "SELECT text FROM comic_dialogues_fts WHERE comic_dialogues_fts MATCH '\"喜欢你\"'"
            ).fetchall()
            by_rank = conn.execute(
                "SELECT text, bm25(comic_dialogues_fts) AS s FROM comic_dialogues_fts"
                " WHERE comic_dialogues_fts MATCH '\"喜欢你\"' ORDER BY s"
            ).fetchall()
        assert by_rowid[0]["text"] == long_line, "行序应当偏向长句，用来反证排序生效"
        assert [r["text"] for r in by_rank] == ["我喜欢你", long_line]
        assert by_rank[0]["s"] < by_rank[1]["s"] < 0, "bm25 为负数，越相关越负"

        res = db_mod.search_dialogues("喜欢你", source="local", limit=10)
        assert [r["text"] for r in res] == ["我喜欢你", long_line], (
            f"接口返回顺序未跟随相关度: {[r['text'] for r in res]}"
        )
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_dialogue_script_normalization_recall():
    """简繁归一必须落在索引侧：查询侧展开变体在"一简对多繁"上根本不够用。

    语料同时有繁体「頭髮」（头发的正字）与简体「头发」。zh_conv 的 s2t 表是逐字符 1:1，
    简体「头发」只能展开成「頭發」这一个写法，旧路径的两个 MATCH 项都对不上「頭髮」，
    于是简体输入永远搜不到繁体那一行。索引侧把两边都折成简体之后，互搜与字形无关。
    """
    temp_dir = Path(tempfile.mkdtemp())
    try:
        temp_db = temp_dir / "test_script.db"
        db_mod.set_db_path(temp_db)
        db_mod.init_db(temp_db)
        config_mod.DATA_DIR = temp_dir
        db_mod.DATA_DIR = temp_dir

        pages_dir = temp_dir / "library" / "local" / "comic_script" / "pages"
        pages_dir.mkdir(parents=True, exist_ok=True)
        (pages_dir / "00001.ocr.json").write_text(
            json.dumps({
                "version": 1,
                "bubbles": [{"id": 1, "order": 1, "box": [0.1, 0.1, 0.4, 0.4], "text": "他的頭髮很長"}],
            }, ensure_ascii=False),
            encoding="utf-8",
        )
        (pages_dir / "00002.ocr.json").write_text(
            json.dumps({
                "version": 1,
                "bubbles": [{"id": 1, "order": 1, "box": [0.6, 0.2, 0.9, 0.5], "text": "他的头发很短"}],
            }, ensure_ascii=False),
            encoding="utf-8",
        )
        assert db_mod.sync_comic_dialogues("local", "comic_script") == 2

        from app.zh_conv import expand_search_variants

        # 前提探针：查询侧变体确实覆盖不到「頭髮」。哪天表补上一对多展开，这条会响，
        # 提醒本用例的对照组已经不存在，而不是让检索回归时静默通过。
        assert "頭髮" not in expand_search_variants("头发"), (
            "查询侧变体已能覆盖一简对多繁，本用例的前提与对照组需要一并改写"
        )

        # 2 字查询走 LIKE 兜底，3+ 字走 trigram 倒排：两条路径都必须折合同一份语料
        for query in ("头发", "頭髮", "他的头发", "他的頭髮"):
            res = sorted(
                db_mod.search_dialogues(query, source="local", limit=10),
                key=lambda r: r["page_index"],
            )
            assert [r["page_index"] for r in res] == [1, 2], f"{query!r} 未做到简繁互搜: {res}"
            assert [r["text"] for r in res] == ["他的頭髮很長", "他的头发很短"], (
                f"{query!r} 的返回被归一化污染，展示必须保留页面上的原字形: {[r['text'] for r in res]}"
            )
            # 高亮同样要吃原文：拿归一串去标注的话，繁体行会显示成简体
            assert "頭髮" in res[0]["snippet"], f"{query!r} 繁体行高亮漏了原文字形: {res[0]['snippet']}"
            assert "头发" in res[1]["snippet"], f"{query!r} 简体行未高亮: {res[1]['snippet']}"
            for r in res:
                assert "<mark>" in r["snippet"] and "</mark>" in r["snippet"], (
                    f"{query!r} 未定位到命中区间: {r['snippet']}"
                )

        # 归一列只做匹配，不许顺着响应模型漏到调用方手里
        assert all("text_norm" not in r for r in res), "响应里泄漏了归一列"
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_page_level_aggregation():
    """检索单元是气泡，展示单元必须是页：同页多气泡收成一行，total 随之变成页数。"""
    temp_dir = Path(tempfile.mkdtemp())
    try:
        temp_db = temp_dir / "test_agg.db"
        db_mod.set_db_path(temp_db)
        db_mod.init_db(temp_db)
        config_mod.DATA_DIR = temp_dir
        db_mod.DATA_DIR = temp_dir

        pages_dir = temp_dir / "library" / "local" / "comic_agg" / "pages"
        pages_dir.mkdir(parents=True, exist_ok=True)
        (pages_dir / "00001.ocr.json").write_text(
            json.dumps({
                "version": 1,
                "bubbles": [
                    {"id": 1, "order": 1, "box": [0.1, 0.1, 0.3, 0.3],
                     "text": "他在心里反复排练着喜欢你这句话，可是到了嘴边却变成了别的话题，那天夜里下了很大的雨。"},
                    {"id": 2, "order": 2, "box": [0.4, 0.4, 0.5, 0.5], "text": "我喜欢你"},
                    {"id": 3, "order": 3, "box": [0.6, 0.6, 0.7, 0.7], "text": "我真的好喜欢你啊"},
                ],
            }, ensure_ascii=False),
            encoding="utf-8",
        )
        (pages_dir / "00002.ocr.json").write_text(
            json.dumps({
                "version": 1,
                "bubbles": [
                    {"id": 1, "order": 1, "box": [0.2, 0.2, 0.35, 0.35], "text": "喜欢你，不是一天两天了"},
                ],
            }, ensure_ascii=False),
            encoding="utf-8",
        )
        assert db_mod.sync_comic_dialogues("local", "comic_agg") == 4

        res = db_mod.search_dialogues("喜欢你", source="local", limit=10)
        assert len(res) == 2, f"同页 3 个气泡必须收成 1 行，实际 {len(res)} 行"
        assert [r["page_index"] for r in res] == [1, 2], f"页序应按代表句相关度排: {[r['page_index'] for r in res]}"

        # 代表句取该页最高分那条（最短、命中占比最大），不是数组里第一个
        assert res[0]["bubble_count"] == 3
        assert res[0]["text"] == "我喜欢你", f"代表句未取最高分气泡: {res[0]['text']}"
        assert res[0]["bubble_id"] == 2
        assert res[0]["box"] == [0.4, 0.4, 0.5, 0.5]
        assert "<mark>喜欢你</mark>" in res[0]["snippet"]
        assert res[1]["bubble_count"] == 1

        # limit 是页坑位上限不是配额：只留 1 个坑位时，占坑的必须是最相关那一页。
        # bubble_count 仍是候选池（fetch_limit 行）内的计数，但池大小不再按身份分档
        # （旧写法馆长 limit*3、访客 max(limit*5,50)，同一页在两种身份下会报出不同命中数）；
        # 池与身份无关之后，小 limit 下也能拿全该页的 3 条。
        capped = db_mod.search_dialogues("喜欢你", source="local", limit=1)
        assert len(capped) == 1
        assert capped[0]["page_index"] == 1
        assert capped[0]["bubble_count"] == 3, f"统一候选池后小 limit 也应拿全: {capped[0]['bubble_count']}"

        # 同一查询在访客态与馆长态必须报出完全一样的页与命中数。访客侧会回表 comics_index
        # 过滤隐藏本与未收录本，所以这里必须先把这本书登记进影子索引，否则比的是收录差异
        # 而不是候选池口径（那种不等是对的，不该拿在这里断言）。
        db_mod.upsert_comic_index(make_comic_item("local", "comic_agg", "聚合测试"))
        as_guest = db_mod.search_dialogues("喜欢你", source="local", limit=1, is_guest=True)
        assert [(r["page_index"], r["bubble_count"], r["text"]) for r in as_guest] == [
            (r["page_index"], r["bubble_count"], r["text"]) for r in capped
        ], "bubble_count 不该随访问者身份变化"

        # 2 字短词：trigram 产不出任何 token（实测 MATCH 恒 0 行），只能落 LIKE 兜底。
        # 近似相关度排序在这条路上照样生效——第 1 页代表句必须是密度最高的「我喜欢你」，
        # 而不是行号最靠前的那句长话；这正是加 ORDER BY 之前会失败的地方。
        loose = db_mod.search_dialogues("喜欢", source="local", limit=10)
        assert [r["page_index"] for r in loose] == [1, 2], f"2 字路径页序异常: {[r['page_index'] for r in loose]}"
        assert loose[0]["text"] == "我喜欢你", f"2 字路径未做近似排序: {loose[0]['text']}"
        assert loose[0]["bubble_count"] == 3, "两条路径现在都可报命中数"
        assert "<mark>喜欢</mark>" in loose[0]["snippet"]

        # 序列化边界：计数必须原样穿过响应模型。models.py 一旦写成必填带默认值，
        # db 层单测抓不到字段被篡改，必须过一遍 model_dump 才算锁住
        from app.models import DialogueSearchItem

        assert DialogueSearchItem(**res[0]).model_dump()["bubble_count"] == 3, "相关度路径计数被响应模型篡改"
        assert DialogueSearchItem(**loose[0]).model_dump()["bubble_count"] == 3, "LIKE 路径计数被响应模型篡改"

        # 单页高频命中：描边框必须封顶在 MAX_PAGE_BOXES-1，计数仍数全
        many_dir = temp_dir / "library" / "local" / "comic_many" / "pages"
        many_dir.mkdir(parents=True, exist_ok=True)
        (many_dir / "00001.ocr.json").write_text(
            json.dumps({
                "version": 1,
                "bubbles": [
                    {
                        "id": i,
                        "order": i,
                        "box": [0.02 * i, 0.05, 0.02 * i + 0.02, 0.3],
                        "text": f"老师说过第{i}句要记住",
                    }
                    for i in range(1, 9)
                ],
            }, ensure_ascii=False),
            encoding="utf-8",
        )
        assert db_mod.sync_comic_dialogues("local", "comic_many") == 8

        many = db_mod.search_dialogues("老师说过", source="local", limit=10)
        page = next(r for r in many if r["source_id"] == "comic_many")
        assert page["bubble_count"] == 8, f"计数应数全，不受封顶影响: {page['bubble_count']}"
        assert len(page["other_boxes"]) == db_mod.MAX_PAGE_BOXES - 1, (
            f"描边必须封顶，不能把整页灌进 URL: {page['other_boxes']}"
        )
        assert len(page["box"]) == 4
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_dialogue_heat_parsing():
    """views/likes 是上游站点的展示字符串：认得出的才算热度，认不出当"没有这个信号"。

    空串必须解析成 None 而不是 0：本地导入的本子没有站点阅读量，把它当成 0 阅读等于替它编一个。
    """
    parse = db_mod._parse_metric_count
    assert parse("209K") == 209_000
    assert parse("999k") == 999_000, "大小写混着来，上游没约定"
    assert parse("9.9M") == 9_900_000
    assert parse("102") == 102
    assert parse("1,234") == 1_234
    assert parse("") is None
    assert parse("—") is None
    assert parse(None) is None
    print("  ✓ Provider heat strings parsed into signals passed")


def test_dialogue_business_signal_ranking():
    """截断留谁：相关度打平时业务信号顶上，差得远时顶不动，且顺序变而计数不变。

    实测语料里 2 字查询前 20 名的相关度**全部同分**（LIKE 兜底的"词频÷文本长度"是个很粗的
    比值），谁被截断纯靠偶然次序；这个用例就是把那段偶然变成可断言的规则。
    """
    temp_dir = Path(tempfile.mkdtemp())
    try:
        temp_db = temp_dir / "test_signal.db"
        db_mod.set_db_path(temp_db)
        db_mod.init_db(temp_db)
        config_mod.DATA_DIR = temp_dir
        db_mod.DATA_DIR = temp_dir

        # A / B 气泡文本逐字相同 → bm25 必然相同 → 相关度打平；C 是同词的长句 → 密度最低
        same_line = "我喜欢你"
        long_line = "他在心里反复排练着喜欢你这句话，可是到了嘴边却变成了别的话题，那天夜里下了很大的雨。"
        for sid, text in (("sig_a", same_line), ("sig_b", same_line), ("sig_long", long_line)):
            pages_dir = temp_dir / "library" / "local" / sid / "pages"
            pages_dir.mkdir(parents=True)
            (pages_dir / "00001.ocr.json").write_text(
                json.dumps(
                    {"version": 1, "bubbles": [{"id": 1, "order": 1, "box": [0.1, 0.1, 0.4, 0.4], "text": text}]},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            assert db_mod.sync_comic_dialogues("local", sid) == 1
            db_mod.upsert_comic_index(
                {
                    **make_comic_item("local", sid, sid),
                    "views": {"sig_a": "1K", "sig_b": "2K", "sig_long": "209K"}[sid],
                    "likes": {"sig_a": "1K", "sig_b": "1K", "sig_long": "9.9M"}[sid],
                }
            )

        query = "喜欢你"
        plain = db_mod.search_dialogues(query, source="local", limit=10, user_id="")
        by_id = {r["source_id"]: r for r in plain}
        assert set(by_id) == {"sig_a", "sig_b", "sig_long"}
        assert by_id["sig_a"]["rank_score"] == by_id["sig_b"]["rank_score"] == 1.0, (
            f"前提不成立：同文本没打平 {[r['rank_score'] for r in plain]}"
        )
        assert by_id["sig_long"]["rank_score"] == 0.0
        assert plain[-1]["source_id"] == "sig_long", "无信号时纯按相关度，长句垫底"
        assert sorted(r["source_id"] for r in plain[:2]) == ["sig_a", "sig_b"], (
            "前两名必须是那对同分页——它们之间的先后属于偶然次序，下面不锁死"
        )

        # 只有热度：池内 min-max 之后 sig_b 略高于 sig_a（热度垫底的那本抬升 0），
        # 而热度顶到池内最大的 sig_long 也只有 0.15 抬升，补不回 0 与 1.0 的相关度差
        heated = db_mod.search_dialogues(query, source="local", limit=10, user_id="curator")
        heated_ids = [r["source_id"] for r in heated]
        assert heated_ids == ["sig_b", "sig_a", "sig_long"], (
            f"热度未按池内 min-max 生效: {heated_ids} {[(round(r['rank_score'], 3)) for r in heated]}"
        )

        # 本人收藏 + 读完 + 刚读过：sig_a 靠 0.35 抬升反超同分的 sig_b，
        # 而四项信号全开的 sig_long 合计 0.60，仍然压不过一本毫无信号但明显更相关的
        for sid in ("sig_a", "sig_long"):
            db_mod.set_user_favorite("curator", "local", sid, True)
            db_mod.set_user_progress("curator", "local", sid, last_page=10, total_pages=10)
        mine = db_mod.search_dialogues(query, source="local", limit=10, user_id="curator")
        mine_ids = [r["source_id"] for r in mine]
        assert mine_ids == ["sig_a", "sig_b", "sig_long"], (
            f"业务信号要么没抬起来、要么把明显不相关的顶上了: {mine_ids}"
        )
        assert mine[-1]["rank_score"] == 0.0, "rank_score 必须还是纯相关度，不能被融合分污染"

        # 序列化边界同 §64.4：字段在后端恒发，响应模型就不许给它兜底默认值
        from app.models import DialogueSearchItem

        assert DialogueSearchItem(**mine[0]).rank_score == 1.0, "相关度字段在响应模型边界被吞掉或改写"

        # 错题本 #139：顺序可以随身份变，命中的页与计数不行
        baseline = sorted(
            (r["source_id"], r["page_index"], r["bubble_count"], r["rank_score"]) for r in plain
        )
        for other in ("", "curator", "guest:9"):
            as_other = db_mod.search_dialogues(query, source="local", limit=10, user_id=other)
            assert sorted(
                (r["source_id"], r["page_index"], r["bubble_count"], r["rank_score"]) for r in as_other
            ) == baseline, f"user_id={other!r} 改变了命中集合或计数，不只是顺序"
        print("  ✓ Business signals break relevance ties yet never bury passed")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_dialogue_rank_score_scale_hides_hidden_books():
    """归一标尺只取调用者看得见的行：隐藏本占住池内最高分时，访客的最高分仍须是 1.0。

    若标尺连隐藏行一起取，访客看到的最高分低于 1.0 就等于泄露"某本隐藏书里有更贴切的这句"。
    这是错题本 #139「数值与身份无关」的保密例外：宁可同一页在两种身份下分数不同。
    """
    temp_dir = Path(tempfile.mkdtemp())
    try:
        temp_db = temp_dir / "test_scale.db"
        db_mod.set_db_path(temp_db)
        db_mod.init_db(temp_db)
        config_mod.DATA_DIR = temp_dir
        db_mod.DATA_DIR = temp_dir

        # 三本文字长度递增 → 相关度严格递减；最相关的那本对访客隐藏
        long_line = "他在心里反复排练着喜欢你这句话，可是到了嘴边却变成了别的话题，那天夜里下了很大的雨。"
        for sid, text, hidden in (
            ("scale_hidden", "我喜欢你", 1),
            ("scale_mid", "我真的好喜欢你啊", 0),
            ("scale_lo", long_line, 0),
        ):
            pages_dir = temp_dir / "library" / "local" / sid / "pages"
            pages_dir.mkdir(parents=True)
            (pages_dir / "00001.ocr.json").write_text(
                json.dumps(
                    {"version": 1, "bubbles": [{"id": 1, "order": 1, "box": [0.1, 0.1, 0.4, 0.4], "text": text}]},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            assert db_mod.sync_comic_dialogues("local", sid) == 1
            db_mod.upsert_comic_index(make_comic_item("local", sid, sid, hidden_from_guest=hidden))

        curator = db_mod.search_dialogues("喜欢你", source="local", limit=10)
        guest = db_mod.search_dialogues("喜欢你", source="local", limit=10, is_guest=True)
        assert {r["source_id"] for r in curator} == {"scale_hidden", "scale_mid", "scale_lo"}
        assert "scale_hidden" not in {r["source_id"] for r in guest}, "隐藏本漏给了访客"

        cs = {r["source_id"]: r["rank_score"] for r in curator}
        gs = {r["source_id"]: r["rank_score"] for r in guest}
        assert cs["scale_hidden"] == 1.0 and 0.0 < cs["scale_mid"] < 1.0, (
            f"前提不成立：隐藏本须是馆长池内最高分、可见最高分须低于 1.0，否则下面没有鉴别力: {cs}"
        )
        assert gs == {"scale_mid": 1.0, "scale_lo": 0.0}, (
            f"访客的分数被隐藏本拉低了，等于泄露隐藏书里有更贴切的同句: {gs}"
        )
        print("  ✓ rank_score scale ignores books hidden from the caller passed")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_story_context_export_slice():
    """取料出口：按页码+阅读顺序给原始台词流，不排序、不高亮、副文本不露，撞预算要回报。"""
    temp_dir = Path(tempfile.mkdtemp())
    try:
        temp_db = temp_dir / "test_ctx.db"
        db_mod.set_db_path(temp_db)
        db_mod.init_db(temp_db)
        config_mod.DATA_DIR = temp_dir
        db_mod.DATA_DIR = temp_dir

        pages_dir = temp_dir / "library" / "local" / "comic_ctx" / "pages"
        pages_dir.mkdir(parents=True)
        (pages_dir.parent / "album.json").write_text(
            json.dumps({"source": "local", "source_id": "comic_ctx", "page_count": 42}),
            encoding="utf-8",
        )

        def write_bubbles(page: int, items: list[tuple[int, int, str]]) -> None:
            """items 为 (数组下标序里的 id, reading order, text)，刻意让两者不一致。"""
            (pages_dir / f"{page:05d}.ocr.json").write_text(
                json.dumps({
                    "version": 1,
                    "engine": "rapidocr",
                    "bubbles": [
                        {
                            "id": bid,
                            "order": order,
                            "box": [round(0.1 * (i + 1), 4), 0.2, round(0.1 * (i + 1) + 0.08, 4), 0.5],
                            "text": text,
                        }
                        for i, (bid, order, text) in enumerate(items)
                    ],
                }, ensure_ascii=False),
                encoding="utf-8",
            )

        # 数组次序与 order 完全相反：取料若跟写下走的顺序，结果会整篇倒过来
        write_bubbles(12, [
            (9, 3, "第十二页第三句台词"),
            (5, 2, "第十二页第二句台词"),
            (7, 1, "第十二页第一句台词"),
        ])
        write_bubbles(13, [(2, 2, "第十三页次句台词"), (1, 1, "第十三页首句台词")])
        # 第 1 页是书名页（前 2 页规则）：取料也不该把 credits 当剧情喂给模型
        write_bubbles(1, [(1, 1, "封面书名与汉化组credits信息")])
        assert db_mod.sync_comic_dialogues("local", "comic_ctx") == 6

        ctx = db_mod.get_story_context("local", "comic_ctx", 12, 13)
        assert [ln["text"] for ln in ctx["lines"]] == [
            "第十二页第一句台词",
            "第十二页第二句台词",
            "第十二页第三句台词",
            "第十三页首句台词",
            "第十三页次句台词",
        ], "取料必须按 (页码, 阅读顺序) 的剧情原序返回"
        assert ctx["truncated"] is False
        assert ctx["budget_lines"] == 120
        # 物料态：既没有 <mark>，也没有 snippet 这种给眼睛看的加工痕迹
        assert all("<mark>" not in ln["text"] and "snippet" not in ln for ln in ctx["lines"])

        # 坐标与台词分两份、靠 line_id 关联，模型侧那份不含坐标
        assert list(ctx["lines"][0].keys()) == ["line_id", "page_index", "reading_order", "text"]
        assert [bx["line_id"] for bx in ctx["boxes"]] == [ln["line_id"] for ln in ctx["lines"]]
        # 阅读顺序第 1 句是数组里最后写的那条，坐标跟着气泡走、不跟着数组走
        assert ctx["boxes"][0]["box"] == [0.3, 0.2, 0.38, 0.5]

        # 预算截断：只给 3 行，必须回报 truncated 让下游知道该续取
        tight = db_mod.get_story_context("local", "comic_ctx", 12, 13, budget_lines=3)
        assert len(tight["lines"]) == 3
        assert tight["truncated"] is True
        assert len(tight["boxes"]) == 3

        # 页跨度超 200 被夹：行数没撞预算也要回报 truncated，并回显实际覆盖到的页区间
        wide = db_mod.get_story_context("local", "comic_ctx", 1, 500)
        assert wide["truncated"] is True, "页跨度被静默夹短，下游会把片段当全书"
        assert wide["requested_pages"] == [1, 200]
        assert ctx["requested_pages"] == [12, 13]

        # 页区间外的内容不得混入；区间外没有的行返回空而非报错
        empty = db_mod.get_story_context("local", "comic_ctx", 30, 31)
        assert empty["lines"] == [] and empty["truncated"] is False
        assert db_mod.get_story_context("local", "comic_ctx", 13, 12)["lines"][0]["page_index"] == 13

        # 书名页 credits 既不进检索，也不进取料
        front = db_mod.get_story_context("local", "comic_ctx", 1, 2)
        assert front["lines"] == [], "副文本不得作为台词物料喂给下游"

        # 跨来源复合键：同名 id 的另一来源不得串台
        other = temp_dir / "library" / "picacg" / "comic_ctx" / "pages"
        other.mkdir(parents=True)
        (other / "00012.ocr.json").write_text(
            json.dumps({"bubbles": [{"id": 1, "order": 1, "box": [0.1, 0.1, 0.2, 0.2],
                                     "text": "哔咔同名作品台词一条"}]}),
            encoding="utf-8",
        )
        db_mod.sync_comic_dialogues("picacg", "comic_ctx")
        jm_lines = db_mod.get_story_context("local", "comic_ctx", 12, 12)["lines"]
        assert all("哔咔" not in ln["text"] for ln in jm_lines), "取料漏了 source 维度会跨来源串台"
        print("  ✓ Story-context export slicing passed")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_dirty_sidecar_values_stay_contained():
    """畸形侧车（4 键 dict 坐标、1e999 序号、对象 id）不得炸掉入库或检索端点。"""
    from app.models import DialogueSearchItem

    temp_dir = Path(tempfile.mkdtemp())
    try:
        temp_db = temp_dir / "test_dirty.db"
        db_mod.set_db_path(temp_db)
        db_mod.init_db(temp_db)
        config_mod.DATA_DIR = temp_dir
        db_mod.DATA_DIR = temp_dir

        pages_dir = temp_dir / "library" / "local" / "comic_dirty" / "pages"
        pages_dir.mkdir(parents=True)
        (pages_dir / "00007.ocr.json").write_text(
            json.dumps({
                "version": 1,
                "engine": "rapidocr",
                "bubbles": [
                    # 只判 len(box)==4 会放过 4 键 dict，它能在响应模型上炸出 500
                    {"id": 1, "order": 1, "box": {"a": 0.1, "b": 0.2, "c": 0.3, "d": 0.4},
                     "text": "坐标写成字典的一句畸形台词"},
                    # 1e999 转 int 抛的是 OverflowError，不在原捕获清单里
                    {"id": 2, "order": 1e999, "box": [[1, 2], [3, 4], [5, 6], [7, 8]],
                     "text": "序号是天文数字且坐标是四点嵌套的一句"},
                    # id 是对象会让 executemany 抛 InterfaceError，整本书都灌不进去
                    {"id": {"x": 1}, "order": 3, "box": [0.1, 0.2, 0.3, "nope"],
                     "text": "气泡标识是对象且坐标含非数字的一句"},
                    {"id": 4, "order": 4, "box": [0.3, 0.1, 0.5, 0.4],
                     "text": "这一句完全正常应当稳稳被搜到"},
                ],
            }, ensure_ascii=False),
            encoding="utf-8",
        )

        assert db_mod.sync_comic_dialogues("local", "comic_dirty") == 4, "四句都该入库（只有坐标该丢）"

        res = db_mod.search_dialogues("一句", source="local", limit=10)
        assert len(res) == 1, f"同页四句必须聚合成一行: {len(res)}"
        assert res[0]["bubble_count"] == 4, "四句都该入库（只丢坐标，不丢文本）"
        for item in res:
            dumped = DialogueSearchItem(**item).model_dump()
            box = dumped["box"]
            assert box == [] or (
                isinstance(box, list) and len(box) == 4 and all(isinstance(v, float) for v in box)
            ), f"脏坐标漏到响应里: {box!r}"

        page = res[0]
        valid = [0.3, 0.1, 0.5, 0.4]
        drawn = ([page["box"]] if page["box"] else []) + page["other_boxes"]
        assert drawn == [valid], f"四句里只有第 4 句坐标合法，描边集合不该掺空框: {drawn}"
        # reading_order 永不为空：畸形序号退回数组下标，取料排序不能因此断链
        ctx = db_mod.get_story_context("local", "comic_dirty", 7, 7)
        assert [ln["reading_order"] for ln in ctx["lines"]] == [1, 2, 3, 4]
        assert len(ctx["boxes"]) == 1, "只有四点有限数值的坐标能进 boxes"
        print("  ✓ Malformed sidecar values contained passed")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_dialogue_index_backfills_after_rebuild():
    """整表重建后必须就地回填，否则台词检索静默返 0、与「没有这句」不可区分。"""
    import sqlite3

    temp_dir = Path(tempfile.mkdtemp())
    try:
        config_mod.DATA_DIR = temp_dir
        db_mod.DATA_DIR = temp_dir

        pages_dir = temp_dir / "library" / "jm" / "88001" / "pages"
        pages_dir.mkdir(parents=True)
        (pages_dir / "00003.ocr.json").write_text(
            json.dumps({
                "version": 1,
                "engine": "rapidocr",
                "bubbles": [{"id": 1, "order": 1, "box": [0.2, 0.1, 0.4, 0.5],
                             "text": "重建之后这条台词必须还在"}],
            }, ensure_ascii=False),
            encoding="utf-8",
        )
        # 没有任何 OCR 文件的本子：回填必须跳过它，不去空跑
        (temp_dir / "library" / "jm" / "88002" / "pages").mkdir(parents=True)

        old_db = temp_dir / "legacy_backfill.db"
        # 主库必须正常建好：search_dialogues 会回表查 comics_index 拿标题与访客标记
        shelf_db = temp_dir / "comic_shelf.db"
        db_mod.set_db_path(shelf_db)
        db_mod.init_db(shelf_db)
        with sqlite3.connect(old_db) as old_conn:
            old_conn.execute(
                """
                CREATE VIRTUAL TABLE comic_dialogues_fts USING fts5(
                    source UNINDEXED, source_id UNINDEXED, page_index UNINDEXED,
                    bubble_id UNINDEXED, text, lang UNINDEXED, box_json UNINDEXED,
                    reading_order UNINDEXED, tokenize='trigram'
                )
                """
            )
            old_conn.execute(
                """
                CREATE TABLE comic_ocr_sync_meta (
                    source TEXT NOT NULL, source_id TEXT NOT NULL,
                    last_synced_mtime REAL NOT NULL DEFAULT 0.0,
                    dialogue_count INTEGER NOT NULL DEFAULT 0,
                    updated_at INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (source, source_id)
                )
                """
            )
            # 残留的"已同步"元数据正是让重灌被 mtime 短路跳过的东西
            old_conn.execute("INSERT INTO comic_ocr_sync_meta VALUES ('jm', '88001', 9e12, 1, 0)")
            old_conn.commit()

        db_mod.init_dialogue_db(old_db)

        hits = db_mod.search_dialogues("必须还在", source="jm")
        assert len(hits) == 1, f"重建后索引无人回填，检索静默返空: {hits}"
        assert hits[0]["source_id"] == "88001"
        assert db_mod.get_story_context("jm", "88001", 3, 3)["lines"], "取料出口同样要能拿到回填后的行"
        with db_mod.get_dialogue_db() as conn:
            meta = conn.execute(
                "SELECT dialogue_count FROM comic_ocr_sync_meta WHERE source_id = '88001'"
            ).fetchone()
        assert meta and int(meta["dialogue_count"]) == 1, "回填必须写下新的增量元数据"
        print("  ✓ Dialogue index auto-backfills after schema rebuild passed")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_half_synced_rows_resynced_on_startup():
    """错题本 #145：列是齐的、行却是旧 INSERT 写的（新列为 NULL），元数据还说已同步——启动时必须认出来按书重灌。"""
    temp_dir = Path(tempfile.mkdtemp())
    try:
        config_mod.DATA_DIR = temp_dir
        db_mod.DATA_DIR = temp_dir
        shelf_db = temp_dir / "comic_shelf.db"
        db_mod.set_db_path(shelf_db)
        db_mod.init_db(shelf_db)

        text = "半截迁移的书也得搜得到"
        pages_dir = temp_dir / "library" / "jm" / "88003" / "pages"
        pages_dir.mkdir(parents=True)
        (pages_dir / "00002.ocr.json").write_text(
            json.dumps(
                {"version": 1, "bubbles": [{"id": 1, "order": 1, "box": [0.2, 0.1, 0.4, 0.5], "text": text}]},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        # 常驻的旧进程拿旧 INSERT 往新表里写：kind / text_norm / reading_order 全是 NULL，
        # 列却是齐的，整表重建不会触发；元数据又记着"已最新"，增量同步也会跳过它
        with db_mod.get_dialogue_db() as conn:
            conn.execute(
                "INSERT INTO comic_dialogues_fts (source, source_id, page_index, bubble_id, text, lang, box_json)"
                " VALUES ('jm', '88003', 2, 1, ?, 'zh', '[0.2, 0.1, 0.4, 0.5]')",
                (text,),
            )
            conn.execute("INSERT OR REPLACE INTO comic_ocr_sync_meta VALUES ('jm', '88003', 9e12, 1, 0)")
        assert db_mod.search_dialogues("也得搜得到", source="jm") == [], "前提不成立：新列为 NULL 的行本就搜得到"

        db_mod.init_dialogue_db()

        hits = db_mod.search_dialogues("也得搜得到", source="jm")
        assert [h["source_id"] for h in hits] == ["88003"], f"半截迁移的书没被重灌: {hits}"
        with db_mod.get_dialogue_db() as conn:
            nulls = conn.execute(
                "SELECT count(*) FROM comic_dialogues_fts WHERE kind IS NULL OR text_norm IS NULL"
            ).fetchone()[0]
        assert nulls == 0, "重灌后仍留着新列为 NULL 的行"
        print("  ✓ Half-synced dialogue rows resynced on startup passed")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_dialogue_key_normalization_roundtrip():
    """脏 id 进来时，写库、增量元数据、删除必须落在同一个清洗键上，不许留下删不掉的孤儿。"""
    temp_dir = Path(tempfile.mkdtemp())
    try:
        temp_db = temp_dir / "keys.db"
        db_mod.set_db_path(temp_db)
        db_mod.init_db(temp_db)
        config_mod.DATA_DIR = temp_dir
        db_mod.DATA_DIR = temp_dir

        # 目录名就是存储层清洗后的形态；"Foo Bar!" 经 re.sub + strip 恰好得到 Foo_Bar
        pages_dir = temp_dir / "library" / "local" / "Foo_Bar" / "pages"
        pages_dir.mkdir(parents=True)
        (pages_dir.parent / "album.json").write_text(
            json.dumps({"source": "local", "source_id": "Foo_Bar", "page_count": 20}),
            encoding="utf-8",
        )
        (pages_dir / "00005.ocr.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "engine": "rapidocr",
                    "bubbles": [{"id": 1, "order": 1, "box": [0.1, 0.2, 0.3, 0.4], "text": "今天也想见到你"}],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        dirty = "Foo Bar!"
        assert db_mod.sync_comic_dialogues("local", dirty) == 1, "按清洗键应能找到目录并入库"
        with db_mod.get_dialogue_db() as conn:
            rows = {(r["source"], r["source_id"]) for r in conn.execute("SELECT DISTINCT source, source_id FROM comic_dialogues_fts")}
            meta = {(r["source"], r["source_id"]) for r in conn.execute("SELECT source, source_id FROM comic_ocr_sync_meta")}
        assert rows == {("local", "Foo_Bar")}, f"写库键没有清洗: {rows}"
        assert meta == {("local", "Foo_Bar")}, f"增量元数据键没有清洗: {meta}"

        # 调用方拿原始脏 id 来删（HTTP 路径参数就是这种形态），必须删得干净
        db_mod.delete_comic_dialogues("local", dirty)
        with db_mod.get_dialogue_db() as conn:
            left = conn.execute("SELECT count(*) AS c FROM comic_dialogues_fts").fetchone()["c"]
            left_meta = conn.execute("SELECT count(*) AS c FROM comic_ocr_sync_meta").fetchone()["c"]
        assert left == 0 and left_meta == 0, f"写删键不一致，留下孤儿: fts={left} meta={left_meta}"
        print("  ✓ Dialogue key normalization write/delete roundtrip passed")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_dialogue_context_http_endpoint():
    """取料端点：访客必须被挡在外面，馆长拿到的必须是剧情原序且不带展示态字段。"""
    from types import SimpleNamespace
    from unittest import mock

    from fastapi import HTTPException

    from app.models import StoryContextResponse
    from app.routers import search as search_router

    temp_dir = Path(tempfile.mkdtemp())
    try:
        temp_db = temp_dir / "ctx_http.db"
        db_mod.set_db_path(temp_db)
        db_mod.init_db(temp_db)
        config_mod.DATA_DIR = temp_dir
        db_mod.DATA_DIR = temp_dir

        pages_dir = temp_dir / "library" / "local" / "comic_http" / "pages"
        pages_dir.mkdir(parents=True)
        (pages_dir.parent / "album.json").write_text(
            json.dumps({"source": "local", "source_id": "comic_http", "page_count": 20}),
            encoding="utf-8",
        )
        # 数组顺序与 order 相反，用来确认端点吐的是阅读顺序而不是磁盘顺序
        (pages_dir / "00005.ocr.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "engine": "rapidocr",
                    "bubbles": [
                        {"id": 2, "order": 1, "box": [0.1, 0.1, 0.2, 0.2], "text": "先说的话"},
                        {"id": 1, "order": 2, "box": [0.3, 0.3, 0.4, 0.4], "text": "后说的话"},
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        assert db_mod.sync_comic_dialogues("local", "comic_http") == 2

        with mock.patch.object(search_router, "is_curator", lambda r: False), \
            mock.patch.object(search_router, "is_machine", lambda r: False), \
            mock.patch.object(search_router, "require_curator", side_effect=HTTPException(403, "拒绝")):
            try:
                search_router.dialogue_context_endpoint(
                    request=None, source="local", source_id="comic_http", page_start=1, page_end=9, budget_lines=10
                )
                raise AssertionError("访客态必须被端点拒掉")
            except HTTPException as exc:
                assert exc.status_code == 403, f"访客应收到 403，实际 {exc.status_code}"

        with mock.patch.object(search_router, "is_curator", lambda r: True), mock.patch.object(
            search_router, "_require_meta", lambda s, i, request=None: SimpleNamespace(title="测试本")
        ):
            resp = search_router.dialogue_context_endpoint(
                request=None, source="local", source_id="comic_http", page_start=1, page_end=9, budget_lines=10
            )
        assert isinstance(resp, StoryContextResponse)
        assert resp.title == "测试本"
        assert [l.text for l in resp.lines] == ["先说的话", "后说的话"], "必须按阅读原序"
        assert resp.truncated is False
        assert [l.model_dump().keys() for l in resp.lines] == [{"line_id", "page_index", "reading_order", "text"}] * 2, (
            "取料出口不得吐 <mark>、snippet 等展示态字段"
        )

        # 机器密钥与访客一样看不到隐藏本：取料不能成为它唯一能读隐藏本台词的口子
        from app.routers import common as common_router

        hidden_meta = SimpleNamespace(title="隐藏本", hidden_from_guest=True)
        with mock.patch.object(search_router, "is_curator", lambda r: False), \
            mock.patch.object(search_router, "is_machine", lambda r: True), \
            mock.patch.object(common_router, "is_curator", lambda r: False), \
            mock.patch.object(common_router.store, "load_meta", lambda s, i: hidden_meta):
            try:
                search_router.dialogue_context_endpoint(
                    request=object(), source="local", source_id="comic_http", page_start=1, page_end=9, budget_lines=10
                )
                raise AssertionError("机器密钥读到了隐藏本的台词")
            except HTTPException as exc:
                assert exc.status_code == 404, f"隐藏本对机器密钥应表现为不存在，实际 {exc.status_code}"
        print("  ✓ Story-context HTTP endpoint gating passed")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_ascii_case_folding_and_unparsable_query():
    """LIKE 与 trigram 都不分 ASCII 大小写，词频与高亮也得跟着不分；FTS5 解析不了的查询回空不回 500。"""
    temp_dir = Path(tempfile.mkdtemp())
    try:
        temp_db = temp_dir / "test_case.db"
        db_mod.set_db_path(temp_db)
        db_mod.init_db(temp_db)
        config_mod.DATA_DIR = temp_dir
        db_mod.DATA_DIR = temp_dir

        pages_dir = temp_dir / "library" / "local" / "comic_case" / "pages"
        pages_dir.mkdir(parents=True)
        # 页序偏向稀的那句、词频偏向密的那句：词频若恒为 0，两页同分就会按页号排。
        # 第 1 页以 OK 收尾是给下面的 NUL 查询设的套：LIKE 会在 NUL 处截断模式串，
        # 旧的 LIKE 兜底拿 "%ok" 去扫就会误中这一句
        for page, text in ((1, "我觉得这样也OK"), (2, "OK啦")):
            (pages_dir / f"{page:05d}.ocr.json").write_text(
                json.dumps(
                    {"version": 1, "bubbles": [{"id": 1, "box": [0.1, 0.1, 0.4, 0.4], "text": text}]},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
        assert db_mod.sync_comic_dialogues("local", "comic_case") == 2

        res = db_mod.search_dialogues("ok", source="local", limit=10)
        assert [r["page_index"] for r in res] == [2, 1], f"两字查询的词频没折大小写: {res}"
        assert res[0]["rank_score"] > res[1]["rank_score"], res
        assert "<mark>OK</mark>" in res[0]["snippet"], f"命中了 OK 却高亮不出来: {res[0]['snippet']}"

        # 3 字以上 MATCH 为空就是真没有，不再拿 LIKE 全表重扫；NUL 让 FTS5 解析失败，也只当无命中
        assert db_mod.search_dialogues("ok\x00啦", source="local") == []
        print("  ✓ ASCII case folding and unparsable query passed")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    print("Running dialogue FTS & API unit tests...")
    test_dialogue_fts_lifecycle()
    test_dialogue_guest_filtering_and_multi_chapter()
    test_dialogue_api_endpoints_and_auth()
    test_reading_order_roundtrip_and_legacy_rebuild()
    test_bm25_relevance_ordering()
    test_dialogue_script_normalization_recall()
    test_page_level_aggregation()
    test_dialogue_heat_parsing()
    test_dialogue_business_signal_ranking()
    test_dialogue_rank_score_scale_hides_hidden_books()
    test_classify_dialogue_kind_rules()
    test_paratext_indexed_but_excluded_from_search()
    test_story_context_export_slice()
    test_dirty_sidecar_values_stay_contained()
    test_dialogue_index_backfills_after_rebuild()
    test_half_synced_rows_resynced_on_startup()
    test_dialogue_key_normalization_roundtrip()
    test_dialogue_context_http_endpoint()
    test_ascii_case_folding_and_unparsable_query()
    print("All dialogue FTS & API unit tests passed successfully!")
