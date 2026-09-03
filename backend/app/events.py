import asyncio
import json
import threading
import time
from typing import Any, AsyncGenerator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from .auth import get_client_ip

router = APIRouter(prefix="/api/events", tags=["events"])

# Concurrency limits for SSE stream protection
_MAX_TOTAL_LISTENERS = 200
_MAX_IP_LISTENERS = 10

# Stores (queue, event_loop) pairs to support thread-safe broadcasting from background threads
_listeners: set[tuple[asyncio.Queue[str | None], asyncio.AbstractEventLoop]] = set()
_ip_counts: dict[str, int] = {}
_pool_lock = threading.Lock()


def broadcast_event(event_type: str, data: dict[str, Any] | None = None) -> int:
    """Broadcast an SSE event payload to all connected clients in O(1) in-memory queues.

    Thread-safe: can be called from FastAPI coroutines or background worker threads.
    Returns the number of active listeners reached.
    """
    with _pool_lock:
        if not _listeners:
            return 0
        current_listeners = list(_listeners)

    payload_data = json.dumps(data or {})
    sse_message = f"event: {event_type}\ndata: {payload_data}\n\n"

    dead_entries: list[tuple[asyncio.Queue[str | None], asyncio.AbstractEventLoop]] = []
    delivered = 0

    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None

    for entry in current_listeners:
        queue, loop = entry
        if loop.is_closed():
            dead_entries.append(entry)
            continue
        try:
            if current_loop is loop:
                queue.put_nowait(sse_message)
            else:
                loop.call_soon_threadsafe(queue.put_nowait, sse_message)
            delivered += 1
        except (asyncio.QueueFull, RuntimeError):
            dead_entries.append(entry)

    if dead_entries:
        with _pool_lock:
            for dead in dead_entries:
                _listeners.discard(dead)

    return delivered


def get_active_listener_count() -> int:
    """Return the number of currently connected SSE clients."""
    with _pool_lock:
        return len(_listeners)


def shutdown_events() -> None:
    """Close and clear all active SSE listener queues on application shutdown."""
    with _pool_lock:
        current_listeners = list(_listeners)
        _listeners.clear()
        _ip_counts.clear()

    def _deliver_poison_pill(q: asyncio.Queue[str | None]) -> None:
        try:
            q.put_nowait(None)
        except asyncio.QueueFull:
            try:
                q.get_nowait()
                q.put_nowait(None)
            except Exception:
                pass

    for queue, loop in current_listeners:
        if not loop.is_closed():
            try:
                loop.call_soon_threadsafe(_deliver_poison_pill, queue)
            except Exception:
                pass


@router.get("/stream")
async def sse_event_stream(request: Request) -> StreamingResponse:
    """Persistent Server-Sent Events stream for real-time frontend notifications.

    Zero polling, 0 CPU idle load, per-IP connection limits and native auto-reconnect support.
    """
    client_ip = get_client_ip(request)
    loop = asyncio.get_running_loop()

    with _pool_lock:
        if len(_listeners) >= _MAX_TOTAL_LISTENERS:
            raise HTTPException(status_code=429, detail="系统并发连接已达上限，请稍后再试")
        if _ip_counts.get(client_ip, 0) >= _MAX_IP_LISTENERS:
            raise HTTPException(status_code=429, detail="单设备事件流连接数已达上限")

        queue: asyncio.Queue[str | None] = asyncio.Queue(maxsize=100)
        entry = (queue, loop)
        _listeners.add(entry)
        _ip_counts[client_ip] = _ip_counts.get(client_ip, 0) + 1

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            # Send initial connection handshake
            yield f"event: ping\ndata: {json.dumps({'status': 'connected', 'timestamp': time.time()})}\n\n"
            yield f"event: system_version\ndata: {json.dumps({'version': 'latest', 'timestamp': time.time()})}\n\n"

            while True:
                if await request.is_disconnected():
                    break
                try:
                    # Suspend with 0 CPU load until an event is pushed or timeout triggers
                    msg = await asyncio.wait_for(queue.get(), timeout=25.0)
                    if msg is None:
                        break
                    yield msg
                except asyncio.TimeoutError:
                    # 25s keepalive heartbeat preventing Cloudflare / Nginx proxy timeouts
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            with _pool_lock:
                _listeners.discard(entry)
                if client_ip in _ip_counts:
                    _ip_counts[client_ip] -= 1
                    if _ip_counts[client_ip] <= 0:
                        del _ip_counts[client_ip]

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
