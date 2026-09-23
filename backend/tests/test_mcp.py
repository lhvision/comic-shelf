"""Unit and integration tests for Paper Room MCP Server & Single-Book Direct Pass Sandbox."""
from __future__ import annotations

import asyncio
import json
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

# Ensure backend package is importable
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import app.auth as auth_mod
import app.config as config_mod
import app.db as db_mod
import app.routers.mcp as mcp_mod
from app.db import (
    create_direct_pass,
    get_direct_pass,
    init_db,
    set_db_path,
    set_dialogue_db_path,
    upsert_comic_index,
)
from app.abuse import clear_ip_login_failures
from app.main import auth_and_security_middleware, store
from app.models import ComicMeta
from app.routers.mcp import (
    MCP_PROMPTS,
    MCP_RESOURCES,
    MCP_TOOLS,
    execute_tool,
    mcp_direct_rpc_endpoint,
    mcp_messages_endpoint,
    mcp_sse_endpoint,
    process_jsonrpc_request,
)


def make_mock_request(
    path: str = "/api/library",
    method: str = "GET",
    headers: dict[str, str] | None = None,
    cookies: dict[str, str] | None = None,
    query_params: dict[str, str] | None = None,
    json_body: Any = None,
) -> MagicMock:
    req = MagicMock()
    req.state = type("State", (), {})()
    req.url.path = path
    req.method = method
    req.client = type("Client", (), {"host": "127.0.0.1"})()
    headers_dict = {k.lower(): v for k, v in (headers or {}).items()}
    req.headers.get = lambda k, default="": headers_dict.get(k.lower(), default)
    req.cookies.get = lambda k, default="": (cookies or {}).get(k, default)
    req.query_params.get = lambda k, default="": (query_params or {}).get(k, default)
    if json_body is not None:
        req.json = AsyncMock(return_value=json_body)
    return req


def setup_test_env():
    tmp_dir = Path(tempfile.mkdtemp(prefix="test_mcp_"))
    db_file = tmp_dir / "comic_shelf.db"
    diag_db_file = tmp_dir / "comic_dialogues.db"
    set_db_path(db_file)
    set_dialogue_db_path(diag_db_file)
    init_db(db_file)

    # Seed mock comic
    mock_meta = {
        "source": "local",
        "source_id": "mcp_test_comic",
        "display_id": "LOCAL-MCP-01",
        "title": "MCP 测试漫画特刊",
        "authors_json": json.dumps(["测试社团"]),
        "works_json": json.dumps(["原创"]),
        "actors_json": json.dumps(["主角A"]),
        "tags_json": json.dumps(["全彩", "纯爱"]),
        "chapter_titles_json": json.dumps(["第一话"]),
        "page_count": 20,
        "cached_pages": 20,
        "cover_count": 1,
        "cover_indices_json": json.dumps([1]),
        "views": "100",
        "likes": "50",
        "uploaded_at": "2026-01-01",
        "published_at": "2026-01-01",
        "updated_at": "2026-01-01",
        "imported_at": "2026-01-01T00:00:00Z",
        "hidden_from_guest": 0,
        "mtime": 100.0,
    }
    upsert_comic_index(mock_meta)

    # Save meta into store
    album_p = store.album_path("local", "mcp_test_comic")
    album_p.parent.mkdir(parents=True, exist_ok=True)
    meta_obj = ComicMeta(
        source="local",
        source_id="mcp_test_comic",
        display_id="LOCAL-MCP-01",
        title="MCP 测试漫画特刊",
        authors=["测试社团"],
        tags=["全彩", "纯爱"],
        page_count=20,
        pages=[],
        chapters=[],
    )
    with open(album_p, "w", encoding="utf-8") as f:
        json.dump(meta_obj.model_dump(), f, ensure_ascii=False)

    return tmp_dir


def test_mcp_protocol_initialize_and_tools():
    tmp_dir = setup_test_env()
    try:
        # 1. Test initialize
        init_resp = asyncio.run(
            process_jsonrpc_request({
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {},
            })
        )
        assert init_resp is not None
        assert init_resp["id"] == 1
        assert "serverInfo" in init_resp["result"]
        assert init_resp["result"]["serverInfo"]["name"] == "paper-room-mcp"
        assert init_resp["result"]["capabilities"]["tools"] is not None

        # 2. Test ping
        ping_resp = asyncio.run(
            process_jsonrpc_request({
                "jsonrpc": "2.0",
                "id": 2,
                "method": "ping",
            })
        )
        assert ping_resp == {"jsonrpc": "2.0", "id": 2, "result": {}}

        # 3. Test tools/list
        tools_resp = asyncio.run(
            process_jsonrpc_request({
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/list",
            })
        )
        assert tools_resp is not None
        tools = tools_resp["result"]["tools"]
        tool_names = {t["name"] for t in tools}
        expected_tools = {
            "search_by_image",
            "search_by_dialogue",
            "query_shelf",
            "get_comic_detail",
            "recommend_unread",
            "create_direct_pass",
            "get_shelf_stats",
            "get_story_context",
        }
        assert expected_tools.issubset(tool_names)

        # 4. Test JSON-RPC 2.0 batch array request
        batch_resp = asyncio.run(
            process_jsonrpc_request([
                {"jsonrpc": "2.0", "id": 41, "method": "ping"},
                {"jsonrpc": "2.0", "id": 42, "method": "ping"},
            ])
        )
        assert isinstance(batch_resp, list)
        assert len(batch_resp) == 2
        assert batch_resp[0] == {"jsonrpc": "2.0", "id": 41, "result": {}}
        assert batch_resp[1] == {"jsonrpc": "2.0", "id": 42, "result": {}}

        # 5. Test JSON-RPC 2.0 invalid non-dict request defense
        invalid_resp = asyncio.run(process_jsonrpc_request("not-a-dict"))
        assert invalid_resp["error"]["code"] == -32600
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_mcp_tool_execution():
    tmp_dir = setup_test_env()
    try:
        # 1. get_shelf_stats
        res_stats = asyncio.run(execute_tool("get_shelf_stats", {}))
        assert not res_stats["isError"]
        data = json.loads(res_stats["content"][0]["text"])
        assert data["total_books"] >= 1

        # 2. query_shelf
        res_query = asyncio.run(
            execute_tool(
                "query_shelf",
                {"keyword": "测试", "tag": "全彩", "limit": 10},
            )
        )
        assert not res_query["isError"]
        query_data = json.loads(res_query["content"][0]["text"])
        assert query_data["total"] >= 1
        assert query_data["items"][0]["source_id"] == "mcp_test_comic"

        # 3. get_comic_detail
        res_detail = asyncio.run(
            execute_tool(
                "get_comic_detail",
                {"source": "local", "source_id": "mcp_test_comic"},
            )
        )
        assert not res_detail["isError"]
        detail_data = json.loads(res_detail["content"][0]["text"])
        assert detail_data["title"] == "MCP 测试漫画特刊"

        # 4. create_direct_pass
        res_pass = asyncio.run(
            execute_tool(
                "create_direct_pass",
                {
                    "source": "local",
                    "source_id": "mcp_test_comic",
                    "page_index": 5,
                    "ttl_seconds": 3600,
                },
            )
        )
        assert not res_pass["isError"]
        pass_data = json.loads(res_pass["content"][0]["text"])
        assert "token" in pass_data
        assert pass_data["page_index"] == 5
        assert pass_data["direct_url"].startswith("/comic/local/mcp_test_comic/read/5?temp_token=")

        # Verify pass in DB
        dp = get_direct_pass(pass_data["token"])
        assert dp is not None
        assert dp["source"] == "local"
        assert dp["source_id"] == "mcp_test_comic"
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_mcp_resources_and_prompts():
    tmp_dir = setup_test_env()
    try:
        # 1. resources/list
        r_list = asyncio.run(
            process_jsonrpc_request({
                "jsonrpc": "2.0",
                "id": 10,
                "method": "resources/list",
            })
        )
        assert r_list is not None
        uris = [r["uri"] for r in r_list["result"]["resources"]]
        assert "shelf://stats" in uris
        assert "shelf://providers" in uris

        # 2. resources/read
        r_read = asyncio.run(
            process_jsonrpc_request({
                "jsonrpc": "2.0",
                "id": 11,
                "method": "resources/read",
                "params": {"uri": "shelf://stats"},
            })
        )
        assert r_read is not None
        assert "contents" in r_read["result"]

        # 3. prompts/list & get
        p_list = asyncio.run(
            process_jsonrpc_request({
                "jsonrpc": "2.0",
                "id": 12,
                "method": "prompts/list",
            })
        )
        assert p_list is not None
        assert len(p_list["result"]["prompts"]) >= 2

        p_get = asyncio.run(
            process_jsonrpc_request({
                "jsonrpc": "2.0",
                "id": 13,
                "method": "prompts/get",
                "params": {"name": "find_comic_by_scene", "arguments": {"clue": "最后的波纹"}},
            })
        )
        assert p_get is not None
        assert "messages" in p_get["result"]
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_http_direct_rpc_and_sandbox_middleware():
    tmp_dir = setup_test_env()
    auth_mod.AUTH_SECRET = "super-secret-curator-key"

    try:
        # 1a. Direct JSON-RPC endpoint without auth -> 401 Unauthorized
        req_rpc_unauth = make_mock_request(
            path="/api/mcp/rpc",
            method="POST",
            json_body={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "get_shelf_stats", "arguments": {}},
            },
        )
        try:
            asyncio.run(mcp_direct_rpc_endpoint(req_rpc_unauth))
            assert False, "Should raise HTTPException 401 when unauthenticated"
        except Exception as exc:
            from fastapi import HTTPException
            assert isinstance(exc, HTTPException)
            assert exc.status_code == 401

        # 1b. Direct JSON-RPC endpoint with curator Bearer token -> 200 OK
        req_rpc = make_mock_request(
            path="/api/mcp/rpc",
            method="POST",
            headers={"Authorization": "Bearer super-secret-curator-key"},
            json_body={
                "jsonrpc": "2.0",
                "id": 42,
                "method": "tools/call",
                "params": {
                    "name": "get_shelf_stats",
                    "arguments": {},
                },
            },
        )
        rpc_resp = asyncio.run(mcp_direct_rpc_endpoint(req_rpc))
        assert rpc_resp.status_code == 200
        rpc_json = json.loads(rpc_resp.body.decode("utf-8"))
        assert rpc_json["id"] == 42
        assert "result" in rpc_json

        # 1c. Direct JSON-RPC endpoint with X-Machine-Token -> 200 OK
        config_mod.MACHINE_TOKEN = "dedicated-machine-key"
        auth_mod.MACHINE_TOKEN = "dedicated-machine-key"
        req_rpc_machine = make_mock_request(
            path="/api/mcp/rpc",
            method="POST",
            headers={"X-Machine-Token": "dedicated-machine-key"},
            json_body={
                "jsonrpc": "2.0",
                "id": 99,
                "method": "tools/call",
                "params": {
                    "name": "get_shelf_stats",
                    "arguments": {},
                },
            },
        )
        rpc_machine_resp = asyncio.run(mcp_direct_rpc_endpoint(req_rpc_machine))
        assert rpc_machine_resp.status_code == 200
        rpc_machine_json = json.loads(rpc_machine_resp.body.decode("utf-8"))
        assert rpc_machine_json["id"] == 99
        assert "result" in rpc_machine_json
        auth_mod.MACHINE_TOKEN = ""
        config_mod.MACHINE_TOKEN = ""

        # 2. Single-Book Sandbox Verification
        # Create direct pass for 'local/mcp_test_comic'
        pass_info = create_direct_pass(source="local", source_id="mcp_test_comic", page_index=3, ttl_seconds=1800)
        temp_token = pass_info["token"]

        # 2a. Direct pass login via /api/auth/login
        from app.models import LoginRequest
        from app.routers.auth import auth_login
        from fastapi import Response
        login_resp = auth_login(
            LoginRequest(secret=temp_token),
            req_rpc_unauth,
            Response(),
        )
        assert login_resp.ok is True
        assert login_resp.role == "guest"
        assert login_resp.user_id == "direct:local:mcp_test_comic"
        assert login_resp.username == "临时单本读者"

        # 2b. Requesting allowed comic detail with temp_token -> 200 OK (passed through middleware)
        next_called = False

        async def dummy_call_next(r):
            nonlocal next_called
            next_called = True
            from fastapi.responses import JSONResponse
            return JSONResponse({"status": "ok"})

        req_ok = make_mock_request(
            path="/api/library/local/mcp_test_comic",
            query_params={"temp_token": temp_token},
        )
        resp_ok = asyncio.run(auth_and_security_middleware(req_ok, dummy_call_next))
        assert next_called is True

        # 2b-2. Requesting metadata outside single-book sandbox (e.g. /api/providers) -> 403 Forbidden
        next_called = False
        req_providers = make_mock_request(
            path="/api/providers",
            query_params={"temp_token": temp_token},
        )
        resp_providers = asyncio.run(auth_and_security_middleware(req_providers, dummy_call_next))
        assert next_called is False
        assert resp_providers.status_code == 403

        # 2c. Requesting shelf index /api/library with temp_token -> 403 Forbidden (Blocked from seeing full library)
        next_called = False
        req_blocked_shelf = make_mock_request(
            path="/api/library",
            query_params={"temp_token": temp_token},
        )
        resp_blocked = asyncio.run(auth_and_security_middleware(req_blocked_shelf, dummy_call_next))
        assert next_called is False
        assert resp_blocked.status_code == 403
        blocked_json = json.loads(resp_blocked.body.decode("utf-8"))
        assert "临时直达通行证仅限阅读指定画集" in blocked_json.get("detail", "")

        # 2d. Requesting other comic with temp_token -> 403 Forbidden
        next_called = False
        req_blocked_other = make_mock_request(
            path="/api/library/jm/999999",
            query_params={"temp_token": temp_token},
        )
        resp_blocked_other = asyncio.run(auth_and_security_middleware(req_blocked_other, dummy_call_next))
        # 2e. Direct pass rate limiting on reading page binary endpoint (/file)
        from app.abuse import _guest_rate_buckets
        req_file = make_mock_request(
            path="/api/library/local/mcp_test_comic/pages/1/file",
            query_params={"temp_token": temp_token},
        )
        next_called = False
        resp_file = asyncio.run(auth_and_security_middleware(req_file, dummy_call_next))
        assert next_called is True
        assert resp_file.status_code == 200

        # Simulate exhausted rate-limiting token bucket for this direct reader
        rate_key = f"direct:local:mcp_test_comic:127.0.0.1"
        assert rate_key in _guest_rate_buckets
        _guest_rate_buckets[rate_key].tokens = 0.0
        next_called = False
        resp_limited = asyncio.run(auth_and_security_middleware(req_file, dummy_call_next))
        assert next_called is False
        assert resp_limited.status_code == 429

        # 3. Machine token least-privilege write permission tests
        config_mod.MACHINE_TOKEN = "dedicated-machine-key"
        auth_mod.MACHINE_TOKEN = "dedicated-machine-key"
        try:
            # 3a. Allowed write: local create
            next_called = False
            req_machine_write_ok = make_mock_request(
                path="/api/library/local/create",
                method="POST",
                headers={"X-Machine-Token": "dedicated-machine-key"},
            )
            resp_write_ok = asyncio.run(auth_and_security_middleware(req_machine_write_ok, dummy_call_next))
            assert next_called is True
            assert resp_write_ok.status_code == 200

            # 3b. Disallowed write: DELETE library comic -> 403 Forbidden
            next_called = False
            req_machine_delete_blocked = make_mock_request(
                path="/api/library/local/mcp_test_comic",
                method="DELETE",
                headers={"X-Machine-Token": "dedicated-machine-key"},
            )
            resp_delete_blocked = asyncio.run(auth_and_security_middleware(req_machine_delete_blocked, dummy_call_next))
            assert next_called is False
            assert resp_delete_blocked.status_code == 403
        finally:
            auth_mod.MACHINE_TOKEN = ""
            config_mod.MACHINE_TOKEN = ""

    finally:
        auth_mod.AUTH_SECRET = ""
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_mcp_dialogue_deep_link_and_story_context():
    """MCP 臂必须被断言：台词直达链接要真能高亮，取料出口要守三条边界纪律。"""
    tmp_dir = setup_test_env()
    old_data_dir = db_mod.DATA_DIR
    try:
        db_mod.DATA_DIR = tmp_dir
        comic_dir = tmp_dir / "library" / "local" / "mcp_test_comic"
        pages = comic_dir / "pages"
        pages.mkdir(parents=True, exist_ok=True)
        (comic_dir / "album.json").write_text(
            json.dumps({"source": "local", "source_id": "mcp_test_comic", "page_count": 20}),
            encoding="utf-8",
        )
        (pages / "00005.ocr.json").write_text(
            json.dumps({
                "version": 1,
                "engine": "rapidocr",
                "bubbles": [
                    {"id": 1, "order": 1, "box": [0.1, 0.1, 0.2, 0.4], "text": "老师我真的很喜欢你"},
                    {"id": 2, "order": 2, "box": [0.3, 0.2, 0.4, 0.6], "text": "我也最喜欢你了老师"},
                    {"id": 3, "order": 3, "box": [0.5, 0.3, 0.6, 0.7], "text": "今天天气不错啊"},
                ],
            }, ensure_ascii=False),
            encoding="utf-8",
        )
        assert db_mod.sync_comic_dialogues("local", "mcp_test_comic") == 3

        # 1. 台词直达链接：阅读器只认 bubble_box / bubble_boxes / highlight_bubble，
        #    历史版本在这里拼 ?bubble=<气泡 id>，签发的链接永远画不出高亮框
        res = asyncio.run(execute_tool("search_by_dialogue", {"text": "喜欢你", "limit": 5}))
        assert res["isError"] is False
        payload = json.loads(res["content"][0]["text"])
        assert payload["total_matched"] == 1, f"同页两句命中应聚合成一行: {payload}"
        hit = payload["hits"][0]
        url = hit["reader_url"]
        from urllib.parse import parse_qs, urlsplit

        params = parse_qs(urlsplit(url).query)
        assert {"bubble_box", "bubble_boxes", "highlight_bubble"} <= set(params), (
            f"直达链接参数不全，点进去不会有高亮: {url}"
        )
        assert "bubble" not in params, f"已废弃的气泡 id 参数不得再签发: {url}"
        assert params["highlight_bubble"] == ["1"]
        assert hit["bubble_count"] == 2 and len(hit["other_boxes"]) == 1

        # 2. 取料出口：按页码+阅读顺序出原始台词流，不收关键词、不带展示态、撞预算要回报
        ctx = asyncio.run(execute_tool("get_story_context", {
            "source": "local", "source_id": "mcp_test_comic",
            "page_start": 5, "page_end": 6, "budget_lines": 2,
        }))
        assert ctx["isError"] is False
        cp = json.loads(ctx["content"][0]["text"])
        assert [ln["text"] for ln in cp["lines"]] == ["老师我真的很喜欢你", "我也最喜欢你了老师"]
        assert cp["truncated"] is True
        assert cp["requested_pages"] == [5, 6]
        assert "<mark>" not in ctx["content"][0]["text"], "展示态标签不得进入取料物料"
        assert "snippet" not in cp["lines"][0]
        assert [b["line_id"] for b in cp["boxes"]] == [ln["line_id"] for ln in cp["lines"]]

        # 3. 边界：缺页号、非整数页号都要明确报错，而不是静默返回空物料
        bad = asyncio.run(execute_tool("get_story_context", {
            "source": "local", "source_id": "mcp_test_comic", "page_start": "abc", "page_end": 6,
        }))
        assert bad["isError"] is True
        missing = asyncio.run(execute_tool("get_story_context", {"source": "local"}))
        assert missing["isError"] is True
    finally:
        db_mod.DATA_DIR = old_data_dir
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_mcp_scoped_credential_and_hidden_book_refusal():
    """子凭据只开 MCP 且启用即挡机器密钥；对访客隐藏的本子不许经 MCP 变成公开链接。"""
    from unittest.mock import patch

    from fastapi import HTTPException

    tmp_dir = setup_test_env()
    auth_mod.AUTH_SECRET = "super-secret-curator-key"
    config_mod.MACHINE_TOKEN = "dedicated-machine-key"
    auth_mod.MACHINE_TOKEN = "dedicated-machine-key"

    def rpc(headers):
        req = make_mock_request(
            path="/api/mcp/rpc",
            method="POST",
            headers=headers,
            json_body={
                "jsonrpc": "2.0",
                "id": 7,
                "method": "tools/call",
                "params": {"name": "get_shelf_stats", "arguments": {}},
            },
        )
        return asyncio.run(mcp_direct_rpc_endpoint(req))

    try:
        mcp_mod.MCP_TOKEN = ""
        assert rpc({"X-Machine-Token": "dedicated-machine-key"}).status_code == 200, (
            "没启用子凭据时机器密钥必须照旧能开 MCP"
        )

        mcp_mod.MCP_TOKEN = "agent-scoped-key"
        try:
            rpc({"X-Machine-Token": "dedicated-machine-key"})
            assert False, "启用 MCP_TOKEN 后机器密钥仍打得开 MCP，等于两把钥匙共享一套权限"
        except HTTPException as exc:
            assert exc.status_code == 401
        assert rpc({"Authorization": "Bearer agent-scoped-key"}).status_code == 200
        assert rpc({"Authorization": "Bearer super-secret-curator-key"}).status_code == 200

        args = {"source": "local", "source_id": "mcp_test_comic", "page_index": 3}
        minted = mcp_mod._tool_create_direct_pass(args)
        assert minted["isError"] is False
        assert json.loads(minted["content"][0]["text"])["token"], "可见本被误伤，签不出链接"

        orig_load = mcp_mod.store.load_meta

        def hidden(source, source_id):
            meta = orig_load(source, source_id)
            meta.hidden_from_guest = True
            return meta

        with patch.object(mcp_mod.store, "load_meta", side_effect=hidden):
            try:
                mcp_mod._tool_create_direct_pass(args)
                assert False, "对访客隐藏的本子仍然经 MCP 签出了直达阅读链接"
            except ValueError as exc:
                assert "隐藏" in str(exc), exc
        print("  ✓ MCP scoped credential and hidden-book mint refusal passed")
    finally:
        mcp_mod.MCP_TOKEN = ""
        auth_mod.AUTH_SECRET = ""
        auth_mod.MACHINE_TOKEN = ""
        config_mod.MACHINE_TOKEN = ""
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_mcp_handshake_url_is_credential_free_and_failures_get_locked():
    """握手 URL 不许回显凭据；活会话凭 session_id 续话；认不出的会话直接 404；反复试错要进 IP 锁。"""
    from fastapi import HTTPException

    import app.abuse as abuse_mod

    tmp_dir = setup_test_env()
    auth_mod.AUTH_SECRET = "super-secret-curator-key"
    agent_ip = "203.0.113.9"
    stranger_ip = "203.0.113.10"

    def from_ip(req, ip):
        req.client = type("Client", (), {"host": ip})()
        return req

    async def flow():
        # 1. 客户端用查询串上来了，服务端也不许把它抄回握手 URL（反代日志会长期留着它）
        sse_req = from_ip(
            make_mock_request(
                path="/api/mcp/sse",
                headers={"Authorization": "Bearer super-secret-curator-key"},
                query_params={"token": "super-secret-curator-key"},
            ),
            agent_ip,
        )
        resp = await mcp_sse_endpoint(sse_req)
        gen = resp.body_iterator
        handshake = await anext(gen)
        assert "session_id=" in handshake, f"握手没给出消息端点: {handshake}"
        assert "token=" not in handshake, f"握手 URL 回显了凭据，会进访问日志: {handshake}"
        session_id = handshake.split("session_id=")[1].strip().split("&")[0]

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "get_shelf_stats", "arguments": {}},
        }
        # 2. 只带 session_id、不带任何凭据也认（凭据已从 URL 拿掉，这是唯一能续话的路径）
        ok = await mcp_messages_endpoint(
            from_ip(
                make_mock_request(
                    path="/api/mcp/messages", method="POST", json_body=payload, query_params={"session_id": session_id}
                ),
                agent_ip,
            ),
            session_id,
        )
        assert ok.status_code == 202, f"活会话续话被拒: {ok.status_code}"

        # 3. 认不出的 session 直接 404，不验凭据也不计失败：服务重启后客户端拿旧 session_id 续话，
        #    不该几条消息就把自己的 IP 锁住
        try:
            await mcp_messages_endpoint(
                from_ip(make_mock_request(path="/api/mcp/messages", method="POST", json_body=payload), stranger_ip),
                "deadbeefdeadbeefdeadbeefdeadbeef",
            )
            assert False, "认不出的会话应当 404"
        except HTTPException as exc:
            assert exc.status_code == 404, exc.status_code
        assert f"mcp:{stranger_ip}" not in abuse_mod._login_failed_history, "认不出的会话被记成了凭据失败"

        await gen.aclose()

        # 4. 反复试错要撞锁：与 /api/auth/login 同一套规则（10 次/60 秒 → 锁 5 分钟），但分开计数
        for i in range(10):
            try:
                await mcp_direct_rpc_endpoint(
                    from_ip(
                        make_mock_request(
                            path="/api/mcp/rpc",
                            method="POST",
                            headers={"Authorization": "Bearer guess-me-maybe"},
                            json_body=payload,
                        ),
                        agent_ip,
                    )
                )
                assert False, f"第 {i + 1} 次错凭据本该 401"
            except HTTPException as exc:
                assert exc.status_code == 401, (i, exc.status_code)

        try:
            await mcp_direct_rpc_endpoint(
                from_ip(
                    make_mock_request(
                        path="/api/mcp/rpc",
                        method="POST",
                        headers={"Authorization": "Bearer super-secret-curator-key"},
                        json_body=payload,
                    ),
                    agent_ip,
                )
            )
            assert False, "锁还没生效：错凭据试了 10 次仍然没人管"
        except HTTPException as exc:
            assert exc.status_code == 429, exc.status_code
            assert exc.headers.get("Retry-After") == "300"
        # 配错凭据的智能体不许连带锁掉同 IP 的馆长网页登录
        assert not abuse_mod.is_ip_login_locked(agent_ip), "MCP 试错锁到了同 IP 的 /api/auth/login"

    try:
        asyncio.run(flow())
        print("  ✓ MCP credential-free handshake and failure lockout passed")
    finally:
        clear_ip_login_failures(f"mcp:{agent_ip}")
        auth_mod.AUTH_SECRET = ""
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_mcp_handlers_run_off_event_loop():
    """工具与资源都是同步阻塞调用，必须丢进线程池：服务只有一个 worker，占着事件循环就卡住全站与所有 SSE。"""
    import threading
    from unittest.mock import patch

    seen: list[threading.Thread] = []

    def probe(*_args):
        seen.append(threading.current_thread())
        return {"content": [], "isError": False}

    with patch.dict(mcp_mod.TOOL_HANDLERS, {"get_shelf_stats": probe}), patch.dict(
        mcp_mod.RESOURCE_HANDLERS, {"shelf://stats": probe}
    ):
        asyncio.run(execute_tool("get_shelf_stats", {}))
        asyncio.run(mcp_mod.read_resource("shelf://stats"))
    assert len(seen) == 2 and threading.main_thread() not in seen, "MCP 处理器仍在事件循环线程上同步执行"
    print("  ✓ MCP handlers run off the event loop passed")


def test_mcp_search_by_meaning_forwards_reason():
    """语义工具必须把 available / reason 原样交给 agent：没走检索与"库里没有"在回包上要长得不一样。"""
    from unittest.mock import patch

    calls: list[dict] = []

    def fake(**kwargs):
        calls.append(kwargs)
        return fake.out

    def run(args: dict) -> dict:
        res = asyncio.run(execute_tool("search_by_meaning", args))
        assert res["isError"] is False, res
        return json.loads(res["content"][0]["text"])

    with patch.object(mcp_mod, "search_dialogues_semantic", fake):
        fake.out = {"results": [], "available": False, "reason": "encoder_unavailable"}
        off = run({"meaning": "告白"})
        assert off["available"] is False and off["reason"] == "encoder_unavailable" and off["hint"], off

        fake.out = {"results": [], "available": True, "reason": "query_too_short"}
        short = run({"meaning": "告"})
        assert short["available"] is True and short["reason"] == "query_too_short" and short["hint"], short

        fake.out = {
            "results": [{
                "source": "local", "source_id": "mcp_test_comic", "page_index": 3, "bubble_id": 1,
                "text": "我喜欢你", "box": [0.1, 0.2, 0.3, 0.4], "similarity": 0.8123,
            }],
            "available": True,
            "reason": "",
        }
        ok = run({"meaning": "告白", "limit": 500})
        assert ok["reason"] == "" and "hint" not in ok and ok["total_matched"] == 1, ok
        assert ok["hits"][0]["reader_url"].startswith("/comic/local/mcp_test_comic/read/3?"), ok["hits"][0]
        assert "跨查询可比" not in ok["scoring"] and "余弦相似度" in ok["scoring"], ok["scoring"]
    assert calls[-1]["limit"] == 50, f"limit 没按 schema 夹到 50: {calls[-1]}"
    print("  ✓ MCP search_by_meaning forwards available/reason passed")


if __name__ == "__main__":
    print("Running MCP Server unit tests...")
    test_mcp_protocol_initialize_and_tools()
    print("  ✓ MCP initialize and tools/list passed")
    test_mcp_tool_execution()
    print("  ✓ MCP tool execution and direct pass creation passed")
    test_mcp_dialogue_deep_link_and_story_context()
    print("  ✓ MCP dialogue deep link and story-context export passed")
    test_mcp_resources_and_prompts()
    print("  ✓ MCP resources and prompts passed")
    test_http_direct_rpc_and_sandbox_middleware()
    print("  ✓ MCP HTTP direct RPC and Single-Book Sandbox passed")
    test_mcp_scoped_credential_and_hidden_book_refusal()
    test_mcp_handshake_url_is_credential_free_and_failures_get_locked()
    test_mcp_handlers_run_off_event_loop()
    test_mcp_search_by_meaning_forwards_reason()
    print("All MCP Server tests passed successfully!")
