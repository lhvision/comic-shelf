from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

# Ensure backend package is importable
BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))
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
        res_simp = db_mod.search_dialogues(query="最后的波纹", source="local", limit=10, is_guest=False)
        assert len(res_simp) == 2, f"Expected 2 matches for '最后的波纹', got {len(res_simp)}"
        assert res_simp[0]["display_id"] == "JOJO-01"
        assert res_simp[0]["title"] == "乔乔的奇妙冒险"
        assert res_simp[0]["page_index"] == 1
        assert res_simp[0]["box"] == [0.12, 0.45, 0.28, 0.68]
        assert "<mark>" in res_simp[0]["snippet"]
        assert "</mark>" in res_simp[0]["snippet"]

        # 5. Search with traditional query (bidirectional conversion test)
        res_trad = db_mod.search_dialogues(query="最後的波紋", source="local", limit=10, is_guest=False)
        assert len(res_trad) == 2, f"Expected 2 matches for traditional '最後的波紋', got {len(res_trad)}"
        assert "<mark>" in res_trad[0]["snippet"]

        # 6. Search with short 2-character word (LIKE fallback test) & <2 chars guard
        assert db_mod.search_dialogues(query="波", source=None, limit=10, is_guest=False) == [], "Query < 2 chars must be blocked"
        res_short = db_mod.search_dialogues(query="波纹", source=None, limit=10, is_guest=False)
        assert len(res_short) == 2, f"Expected 2 matches for '波纹', got {len(res_short)}"
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


if __name__ == "__main__":
    print("Running dialogue FTS & API unit tests...")
    test_dialogue_fts_lifecycle()
    test_dialogue_guest_filtering_and_multi_chapter()
    test_dialogue_api_endpoints_and_auth()
    print("All dialogue FTS & API unit tests passed successfully!")
