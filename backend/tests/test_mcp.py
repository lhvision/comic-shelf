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
from app.db import (
    create_direct_pass,
    get_direct_pass,
    init_db,
    set_db_path,
    set_dialogue_db_path,
    upsert_comic_index,
)
from app.main import auth_and_security_middleware, store
from app.models import ComicMeta
from app.routers.mcp import (
    MCP_PROMPTS,
    MCP_RESOURCES,
    MCP_TOOLS,
    execute_tool,
    mcp_direct_rpc_endpoint,
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
        }
        assert expected_tools.issubset(tool_names)
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
        assert next_called is False
        assert resp_blocked_other.status_code == 403

    finally:
        auth_mod.AUTH_SECRET = ""
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    print("Running MCP Server unit tests...")
    test_mcp_protocol_initialize_and_tools()
    print("  ✓ MCP initialize and tools/list passed")
    test_mcp_tool_execution()
    print("  ✓ MCP tool execution and direct pass creation passed")
    test_mcp_resources_and_prompts()
    print("  ✓ MCP resources and prompts passed")
    test_http_direct_rpc_and_sandbox_middleware()
    print("  ✓ MCP HTTP direct RPC and Single-Book Sandbox passed")
    print("All MCP Server tests passed successfully!")
