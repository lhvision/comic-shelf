from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent
for p in (str(BACKEND_DIR), str(PROJECT_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import app.auth as auth_mod
import app.config as config_mod
import app.db as db_mod
import app.main as main_mod
from app.main import app, store
from tests.test_dialogue_fts import make_comic_item


def _comic(dirs: Path, source_id: str, line: str) -> None:
    """写一页合法侧车并入库，供检索命中。"""
    pages_dir = dirs / "library" / "local" / source_id / "pages"
    pages_dir.mkdir(parents=True)
    (pages_dir / "00001.ocr.json").write_text(
        json.dumps(
            {
                "version": 1,
                "engine": "rapidocr",
                "bubbles": [{"id": 1, "order": 1, "box": [0.1, 0.1, 0.4, 0.4], "text": line}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    assert db_mod.sync_comic_dialogues("local", source_id) == 1


def test_dialogue_search_http_through_real_middleware_stack():
    """真 HTTP 打进来：相关度分数必须活着走出响应模型，no-store 必须由中间件补上。

    其余台词用例都是直接调端点函数，鉴权与缓存头两段中间件从没和检索出口接过一次。
    """
    from fastapi.testclient import TestClient

    temp_dir = Path(tempfile.mkdtemp())
    old_root = store.root
    old_library_dir = main_mod.LIBRARY_DIR
    try:
        temp_db = temp_dir / "stack.db"
        db_mod.set_db_path(temp_db)
        db_mod.init_db(temp_db)
        config_mod.DATA_DIR = temp_dir
        db_mod.DATA_DIR = temp_dir
        config_mod.LIBRARY_DIR = temp_dir / "library"
        # main.py 在 import 期把 LIBRARY_DIR 绑成了自己的名字，只改 config 改不到写锁落点
        main_mod.LIBRARY_DIR = temp_dir / "library"
        store.root = temp_dir / "library"
        config_mod.AUTH_SECRET = "stack-secret"
        config_mod.MACHINE_TOKEN = ""
        auth_mod.AUTH_SECRET = "stack-secret"
        auth_mod.MACHINE_TOKEN = ""

        # 长短两页相关度必然不同 → rank_score 有 1.0 也有 0.0，端点归一没被兜底值伪装
        _comic(temp_dir, "stack_hi", "我喜欢你")
        _comic(
            temp_dir,
            "stack_lo",
            "他在心里反复排练着喜欢你这句话，可是到了嘴边却变成了别的话题，那天夜里下了很大的雨。",
        )
        for sid in ("stack_hi", "stack_lo"):
            db_mod.upsert_comic_index(make_comic_item("local", sid, sid))

        url = "/api/search/dialogue"
        params = {"q": "喜欢你", "source": "local"}

        # 用 with 触发 lifespan，写锁必须落在临时书库里，否则会和开发中的那个 API 实例抢同一把锁
        with TestClient(app) as client:
            assert (temp_dir / "library" / ".writer.lock").exists(), "lifespan 的写锁没落在临时书库"

            unauth = client.get(url, params=params)
            assert unauth.status_code == 401, f"未授权请求应被中间件挡在门外，实际 {unauth.status_code}"

            curator = client.get(url, params=params, headers={"Authorization": "Bearer stack-secret"})
            assert curator.status_code == 200, curator.text
            # 个性化投影的出口：共享缓存一旦把馆长的排序端给下一个人，读偏好就漏了
            assert curator.headers["cache-control"] == "no-store", curator.headers

            body = curator.json()
            scores = {r["source_id"]: r["rank_score"] for r in body["results"]}
            assert set(scores) == {"stack_hi", "stack_lo"}, f"rank_score 在响应模型边界被吞掉: {body}"
            assert scores["stack_hi"] == 1.0 and scores["stack_lo"] == 0.0, scores

            g_pass = db_mod.create_guest_pass("StackGuest", expires_days=7, custom_token="stack-guest-token")
            dev = db_mod.register_guest_device(g_pass["id"], user_agent="StackDev")
            guest = client.get(url, params=params, headers={"X-Device-Token": dev["device_token"]})
            assert guest.status_code == 200, guest.text
            assert guest.headers["cache-control"] == "no-store", guest.headers
            assert {r["source_id"]: r["rank_score"] for r in guest.json()["results"]} == scores, (
                "访客与馆长的相关度标尺必须一致，只有顺序才允许随身份变（错题本 #139）"
            )
        print("  ✓ Dialogue search served through the real middleware stack passed")
    finally:
        store.root = old_root
        main_mod.LIBRARY_DIR = old_library_dir
        auth_mod.AUTH_SECRET = ""
        auth_mod.MACHINE_TOKEN = ""
        config_mod.AUTH_SECRET = ""
        config_mod.MACHINE_TOKEN = ""
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    test_dialogue_search_http_through_real_middleware_stack()
    print("All dialogue HTTP stack tests passed successfully!")
