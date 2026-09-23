import asyncio
import json
import sys
import threading
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

# Ensure backend package is importable
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import app.auth as auth_mod
from app.events import broadcast_event, get_active_listener_count, shutdown_events, sse_event_stream
from fastapi import HTTPException


def make_request(authorization: str | None = None, cookies: dict[str, str] | None = None) -> MagicMock:
    """构造一个 `state` 是普通对象、headers/cookies 是真 dict 的请求替身。

    裸 MagicMock 的 `request.state.user_context` 会自动造出属性，让 `get_user_context`
    抄近道读到一个假身份，鉴权断言就此失去鉴别力。
    """
    req = MagicMock()
    req.state = type("State", (), {})()
    req.is_disconnected = AsyncMock(return_value=False)
    req.client = type("Client", (), {"host": "127.0.0.1"})()
    headers = {"authorization": authorization} if authorization else {}
    jar = cookies or {}
    req.headers.get = lambda k, default="": headers.get(k.lower(), default)
    req.cookies.get = lambda k, default="": jar.get(k, default)
    req.query_params.get = lambda k, default="": default
    return req


async def run_events_tests():
    print("Running backend SSE events unit tests...")

    # 1. Listener count when empty
    shutdown_events()
    assert get_active_listener_count() == 0, "Initial listener count should be 0"

    # 2. Broadcasting when no listeners -> returns 0
    delivered = broadcast_event("test_event", {"hello": "world"})
    assert delivered == 0, "Broadcast to empty listeners should return 0"

    # 3. Connect mock SSE client（内网免密模式：AUTH_SECRET 留空即人人可读）
    mock_request = make_request()

    response = await sse_event_stream(mock_request)
    assert response.media_type == "text/event-stream"
    assert response.headers["Cache-Control"] == "no-cache, no-transform"
    assert response.headers["Connection"] == "keep-alive"

    # Verify listener was added during stream
    assert get_active_listener_count() == 1, "Should have 1 active listener"

    # 4. Broadcast event from a background OS thread (simulating _prefetch_worker)
    worker_delivered = 0

    def background_worker():
        nonlocal worker_delivered
        worker_delivered = broadcast_event("library_changed", {"action": "cache_complete"})

    t = threading.Thread(target=background_worker)
    t.start()
    t.join()

    assert worker_delivered == 1, f"Expected 1 delivered event from worker thread, got {worker_delivered}"

    # 5. Read from the generator
    gen = response.body_iterator
    first_chunk = await anext(gen)
    assert "event: ping" in first_chunk
    assert "connected" in first_chunk

    version_chunk = await anext(gen)
    assert "event: system_version" in version_chunk

    third_chunk = await anext(gen)
    assert "event: library_changed" in third_chunk
    assert "cache_complete" in third_chunk

    # 6. Stream finishes and cleanly releases listener on close
    await gen.aclose()

    # Listener should be removed in finally block
    assert get_active_listener_count() == 0, "Listener count should return to 0 after disconnect"

    # 7. Test graceful shutdown terminating active SSE stream immediately
    response2 = await sse_event_stream(mock_request)
    assert get_active_listener_count() == 1
    gen2 = response2.body_iterator
    await anext(gen2)  # ping
    await anext(gen2)  # version

    # Trigger application shutdown
    shutdown_events()
    assert get_active_listener_count() == 0

    # Generator should stop immediately (raising StopAsyncIteration) rather than blocking for 30s
    stopped = False
    try:
        await anext(gen2)
    except StopAsyncIteration:
        stopped = True
    assert stopped, "Active SSE generator should exit immediately upon shutdown_events()"

    # 8. 事件流自带门禁：/api/events 在全站中间件里是提前放行的，长连接又不能被拦截器打断
    auth_mod.AUTH_SECRET = "stream-secret"
    try:
        try:
            await sse_event_stream(make_request())
            assert False, "匿名请求必须被事件流自己挡在门外"
        except HTTPException as exc:
            assert exc.status_code == 401, f"匿名应收到 401，实际 {exc.status_code}"
        assert get_active_listener_count() == 0, "被拒的连接不该占住监听槽"

        await sse_event_stream(make_request(authorization="Bearer stream-secret"))
        assert get_active_listener_count() == 1, "馆长口令连不进来"
        shutdown_events()

        # 浏览器 EventSource 不能带自定义请求头，只能靠 HttpOnly Cookie——这条路不许被门禁挡死
        await sse_event_stream(make_request(cookies={auth_mod.COOKIE_NAME: "stream-secret"}))
        assert get_active_listener_count() == 1, "网页端 Cookie 会话被事件流门禁挡住，实时流会静默失效"
        shutdown_events()
    finally:
        auth_mod.AUTH_SECRET = ""

    print("All backend SSE events unit tests passed successfully!")


if __name__ == "__main__":
    asyncio.run(run_events_tests())

