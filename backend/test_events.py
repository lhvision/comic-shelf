import asyncio
import json
import sys
import threading
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

# Ensure backend package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.events import broadcast_event, get_active_listener_count, shutdown_events, sse_event_stream


async def run_events_tests():
    print("Running backend SSE events unit tests...")

    # 1. Listener count when empty
    shutdown_events()
    assert get_active_listener_count() == 0, "Initial listener count should be 0"

    # 2. Broadcasting when no listeners -> returns 0
    delivered = broadcast_event("test_event", {"hello": "world"})
    assert delivered == 0, "Broadcast to empty listeners should return 0"

    # 3. Connect mock SSE client
    mock_request = MagicMock()
    mock_request.is_disconnected = AsyncMock(return_value=False)

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

    # Generator should stop immediately (raising StopAsyncIteration) rather than blocking for 15s
    stopped = False
    try:
        await anext(gen2)
    except StopAsyncIteration:
        stopped = True
    assert stopped, "Active SSE generator should exit immediately upon shutdown_events()"

    print("All backend SSE events unit tests passed successfully!")


if __name__ == "__main__":
    asyncio.run(run_events_tests())

