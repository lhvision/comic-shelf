from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path
from unittest import mock

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent
for p in (str(BACKEND_DIR), str(PROJECT_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import numpy as np

import app.config as config_mod
import app.db as db_mod
import app.embedding as embedding_mod
from tests.test_dialogue_fts import make_comic_item

# 手写一个 2 维玩具语义空间：断言的是"字面不通也能连着走"这条链路，不是模型质量。
# 「告白」与「我喜欢你」没有任何共同字符，只有向量能把它们拉到一起。
SEMANTIC = {
    "我喜欢你": (1.0, 0.0),
    # 与「告白」也近、但不如「我喜欢你」近：同页两句都像时，代表句必须是最像的那句
    "我也喜欢你": (0.9, 0.1),
    "告白": (0.98, 0.02),
    "今天天气不错": (0.02, 1.0),
    "外面下雨了吧": (0.0, 1.0),
    "短": (0.5, 0.5),
}


def _norm(pair: tuple[float, float]) -> np.ndarray:
    v = np.array(pair, dtype=np.float32)
    return v / max(float(np.linalg.norm(v)), 1e-9)


def _fake_dim() -> int:
    return 2


def _fake_docs(texts: list[str], batch: int = 64) -> np.ndarray:
    # 表里没有的行给零向量：余弦恒为 0，断言"只有语义相近那条排上来"才干净
    return np.stack([_norm(SEMANTIC.get(t, (0.0, 0.0))) for t in texts])


def _fake_query(text: str) -> np.ndarray:
    return _norm(SEMANTIC.get(text, (0.0, 0.0)))


def _patched_encoder():
    return (
        mock.patch.object(embedding_mod, "dim", _fake_dim),
        mock.patch.object(embedding_mod, "encode_documents", _fake_docs),
        mock.patch.object(embedding_mod, "encode_query", _fake_query),
    )


def _setup(temp_dir: Path) -> None:
    temp_db = temp_dir / "semantic.db"
    # 顺序不能反：set_db_path 会按主库文件名反推台词库路径（错题本 #145），
    # 先设台词库再设主库的话，迁移与向量会写到另一个文件里去。
    db_mod.set_db_path(temp_db)
    db_mod.set_dialogue_db_path(temp_dir / "dialogues.db")
    db_mod.init_db(temp_db)
    config_mod.DATA_DIR = temp_dir
    db_mod.DATA_DIR = temp_dir


def _comic(temp_dir: Path, source_id: str, lines: list[tuple[int, str]]) -> None:
    pages_dir = temp_dir / "library" / "local" / source_id / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    per_page: dict[int, list[str]] = {}
    for page_index, text in lines:
        per_page.setdefault(page_index, []).append(text)
    for page_index, texts in per_page.items():
        bubbles = [
            {"id": i + 1, "order": i + 1, "box": [0.1, 0.1, 0.4, 0.4], "text": t}
            for i, t in enumerate(texts)
        ]
        (pages_dir / f"{page_index:05d}.ocr.json").write_text(
            json.dumps({"version": 1, "engine": "rapidocr", "bubbles": bubbles}, ensure_ascii=False),
            encoding="utf-8",
        )
    assert db_mod.sync_comic_dialogues("local", source_id) == len(lines)


def _vector_count(source_id: str) -> int:
    with db_mod.get_dialogue_db() as conn:
        return int(conn.execute(
            "SELECT count(*) FROM comic_dialogue_vectors WHERE source_id = ?", (source_id,)
        ).fetchone()[0])


def test_semantic_vectors_built_with_sync_and_searchable():
    """向量必须跟着 sync 一起长出来，否则新书永远进不了语义出口（静默落后的索引最难查）。"""
    temp_dir = Path(tempfile.mkdtemp())
    try:
        _setup(temp_dir)
        dims, docs, query = _patched_encoder()
        with dims, docs, query:
            _comic(temp_dir, "c_semi", [(1, "我喜欢你"), (2, "今天天气不错"), (3, "短")])
            assert _vector_count("c_semi") == 2, "少于 4 字的台词不该建向量，长句必须建"

            status = db_mod.dialogue_vector_status()
            assert status["available"] and status["vectors"] == 2, status

            # 字面完全不通：「告白」与「我喜欢你」没有一个共同字符，关键词出口必然 0 命中
            assert db_mod.search_dialogues("告白", source="local") == [], "前提不成立：关键词竟然搜到了"
            out = db_mod.search_dialogues_semantic("告白", source="local", limit=10)
            assert out["available"] is True and out["reason"] == "", out
            hits = out["results"]
            assert [h["text"] for h in hits] == ["我喜欢你", "今天天气不错"], hits
            assert hits[0]["similarity"] > 0.99 and hits[1]["similarity"] < 0.1, hits
            assert hits[0]["page_index"] == 1 and hits[0]["box"], hits[0]
            # 语义命中没有字面区间可高亮，也不该借用 rank_score 那把池内标尺
            assert "snippet" not in hits[0] and "rank_score" not in hits[0], hits[0].keys()

            weather = db_mod.search_dialogues_semantic("今天天气不错", source="local", limit=10)["results"]
            assert weather[0]["text"] == "今天天气不错" and weather[0]["similarity"] > 0.99, weather
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_semantic_one_row_per_page_and_short_query():
    """同一页的几句不许挤占前几名：一页只留最像的那句；问题太短要明说，不能装成"库里没有"。"""
    temp_dir = Path(tempfile.mkdtemp())
    try:
        _setup(temp_dir)
        dims, docs, query = _patched_encoder()
        with dims, docs, query:
            _comic(temp_dir, "c_page", [(1, "我也喜欢你"), (1, "我喜欢你"), (2, "今天天气不错")])
            assert _vector_count("c_page") == 3, "同页两句都该建向量，去重发生在检索时"

            out = db_mod.search_dialogues_semantic("告白", source="local", limit=10)
            got = [(h["page_index"], h["text"]) for h in out["results"]]
            assert got == [(1, "我喜欢你"), (2, "今天天气不错")], f"同页命中没按页去重、或代表句不是最像的那句: {got}"

            short = db_mod.search_dialogues_semantic("告", source="local")
            assert short == {"results": [], "available": True, "reason": "query_too_short"}, short
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_semantic_guest_filter_and_delete_hook():
    """访客视角必须挡掉隐藏本，删书必须连向量一起删。"""
    temp_dir = Path(tempfile.mkdtemp())
    try:
        _setup(temp_dir)
        dims, docs, query = _patched_encoder()
        with dims, docs, query:
            _comic(temp_dir, "c_pub", [(1, "我喜欢你")])
            _comic(temp_dir, "c_hidden", [(1, "今天天气不错")])
            db_mod.upsert_comic_index(make_comic_item("local", "c_pub", "公开本"))
            db_mod.upsert_comic_index(make_comic_item("local", "c_hidden", "隐藏本", hidden_from_guest=1))

            curator = db_mod.search_dialogues_semantic("告白", limit=10)["results"]
            assert {h["source_id"] for h in curator} == {"c_pub", "c_hidden"}, curator
            guest = db_mod.search_dialogues_semantic("告白", limit=10, is_guest=True)["results"]
            assert {h["source_id"] for h in guest} == {"c_pub"}, "访客看到了隐藏本的台词"

            db_mod.delete_comic_dialogues("local", "c_pub")
            assert _vector_count("c_pub") == 0, "删书后向量成了孤儿，语义出口会报出不存在的本"
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_semantic_guest_hidden_books_do_not_eat_quota():
    """隐藏本的高分页多于候选池时，访客仍要拿满 limit 条公开结果。"""
    temp_dir = Path(tempfile.mkdtemp())
    try:
        _setup(temp_dir)
        dims, docs, query = _patched_encoder()
        with dims, docs, query:
            _comic(temp_dir, "c_hidden", [(p, "我喜欢你") for p in range(1, 61)])
            _comic(temp_dir, "c_pub", [(p, "我也喜欢你") for p in range(1, 4)])
            db_mod.upsert_comic_index(make_comic_item("local", "c_pub", "公开本"))
            db_mod.upsert_comic_index(make_comic_item("local", "c_hidden", "隐藏本", hidden_from_guest=1))

            guest = db_mod.search_dialogues_semantic("告白", limit=3, is_guest=True)["results"]
            assert [(h["source_id"], h["page_index"]) for h in guest] == [("c_pub", p) for p in (1, 2, 3)], guest
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_semantic_degrades_without_encoder():
    """没放模型时必须干净地退回"只有关键词"，不能抛异常、也不能留下半套向量。"""
    temp_dir = Path(tempfile.mkdtemp())
    try:
        _setup(temp_dir)
        with mock.patch.object(embedding_mod, "dim", lambda: None):
            # 关键词入库必须照常跑完 —— 语义腿缺席不许把主链路一起打断
            _comic(temp_dir, "c_none", [(1, "我喜欢你")])
            assert db_mod.search_dialogues("我喜欢你", source="local"), "缺模型时关键词检索被打断了"
            assert _vector_count("c_none") == 0, "没有编码器却留下了向量"
            status = db_mod.dialogue_vector_status()
            assert not status["available"] and status["reason"] == "encoder_unavailable", status
            # 检索函数自己认状态：调用方不先查 status 也拿不到一个装成"没找到"的空列表
            off = db_mod.search_dialogues_semantic("告白")
            assert off == {"results": [], "available": False, "reason": "encoder_unavailable"}, off
            rebuilt = db_mod.rebuild_dialogue_vectors()
            assert rebuilt["ok"] is False and rebuilt["reason"] == "encoder_unavailable", rebuilt
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_semantic_reports_stale_vector_store():
    """模型就绪但向量没建（或换了模型）必须报出来，不能把空结果说成"没有相近的台词"。"""
    temp_dir = Path(tempfile.mkdtemp())
    try:
        _setup(temp_dir)
        dims, docs, _ = _patched_encoder()
        with dims, docs:
            _comic(temp_dir, "c_stale", [(1, "我喜欢你")])
            with db_mod.get_dialogue_db() as conn:
                conn.execute("DELETE FROM comic_dialogue_vectors")
            status = db_mod.dialogue_vector_status()
            assert not status["available"] and status["reason"] == "vectors_missing", status
            stale = db_mod.search_dialogues_semantic("告白")
            assert stale["available"] is False and stale["reason"] == "vectors_missing", stale

            db_mod.embed_comic_dialogues("local", "c_stale")
            with db_mod.get_dialogue_db() as conn:
                conn.execute("UPDATE comic_dialogue_vectors SET dim = 512")
            status = db_mod.dialogue_vector_status()
            assert not status["available"] and status["reason"] == "dim_mismatch", status
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_rebuild_vectors_counts_whole_library():
    temp_dir = Path(tempfile.mkdtemp())
    try:
        _setup(temp_dir)
        dims, docs, query = _patched_encoder()
        with dims, docs, query:
            _comic(temp_dir, "r1", [(1, "我喜欢你")])
            _comic(temp_dir, "r2", [(1, "今天天气不错")])
            with db_mod.get_dialogue_db() as conn:
                conn.execute("DELETE FROM comic_dialogue_vectors")
            out = db_mod.rebuild_dialogue_vectors()
            assert out["ok"] and out["comics"] == 2 and out["encoded"] == 2, out
            assert _vector_count("r1") == 1 and _vector_count("r2") == 1
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_semantic_http_endpoints_through_middleware():
    """两个新出口必须穿过真中间件栈：鉴权、no-store、以及"没装模型"时的 200+available=false。"""
    from fastapi.testclient import TestClient

    import app.auth as auth_mod
    import app.main as main_mod

    temp_dir = Path(tempfile.mkdtemp())
    old_root = main_mod.store.root
    old_library = main_mod.LIBRARY_DIR
    try:
        _setup(temp_dir)
        config_mod.LIBRARY_DIR = temp_dir / "library"
        main_mod.LIBRARY_DIR = temp_dir / "library"
        main_mod.store.root = temp_dir / "library"
        config_mod.AUTH_SECRET = "semi-secret"
        config_mod.MACHINE_TOKEN = ""
        auth_mod.AUTH_SECRET = "semi-secret"
        auth_mod.MACHINE_TOKEN = ""

        dims, docs, query = _patched_encoder()
        with dims, docs, query:
            _comic(temp_dir, "c_http", [(1, "我喜欢你")])
            db_mod.upsert_comic_index(make_comic_item("local", "c_http", "语义测试"))
            with TestClient(main_mod.app) as client:
                url = "/api/search/dialogue-semantic"
                assert client.get(url, params={"q": "告白"}).status_code == 401
                res = client.get(url, params={"q": "告白"}, headers={"Authorization": "Bearer semi-secret"})
                assert res.status_code == 200, res.text
                assert res.headers["cache-control"] == "no-store", res.headers
                body = res.json()
                assert body["available"] and body["total"] == 1, body
                assert body["results"][0]["text"] == "我喜欢你", body
                assert "similarity" in body["results"][0]

                # 编码器缺失：不是 500、不是空结果装成"搜不到"，而是明确说这条腿没装
                with mock.patch.object(embedding_mod, "dim", lambda: None):
                    off = client.get(url, params={"q": "告白"}, headers={"Authorization": "Bearer semi-secret"})
                assert off.status_code == 200 and off.json()["available"] is False, off.text
                assert off.json()["reason"] == "encoder_unavailable", off.json()

                rebuild = "/api/search/dialogue-vectors/rebuild"
                curator_rebuild = client.post(rebuild, headers={"Authorization": "Bearer semi-secret"})
                assert curator_rebuild.status_code == 200, curator_rebuild.text
                assert curator_rebuild.json()["encoded"] == 1, curator_rebuild.json()
                assert client.post(rebuild).status_code == 401

                # 整库重编只归馆长：机器密钥与访客都是 403（ADR 0028）
                auth_mod.MACHINE_TOKEN = "semi-machine"
                machine = client.post(rebuild, headers={"X-Machine-Token": "semi-machine"})
                assert machine.status_code == 403, machine.text
                guest_pass = db_mod.create_guest_pass("SemiGuest", expires_days=1)
                device = db_mod.register_guest_device(guest_pass["id"])
                guest = client.post(rebuild, headers={"X-Device-Token": device["device_token"]})
                assert guest.status_code == 403, guest.text
    finally:
        auth_mod.MACHINE_TOKEN = ""
        main_mod.store.root = old_root
        main_mod.LIBRARY_DIR = old_library
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    print("Running dialogue semantic retrieval tests...")
    test_semantic_vectors_built_with_sync_and_searchable()
    test_semantic_one_row_per_page_and_short_query()
    test_semantic_guest_filter_and_delete_hook()
    test_semantic_guest_hidden_books_do_not_eat_quota()
    test_semantic_degrades_without_encoder()
    test_semantic_reports_stale_vector_store()
    test_rebuild_vectors_counts_whole_library()
    test_semantic_http_endpoints_through_middleware()
    print("All dialogue semantic retrieval tests passed successfully!")
