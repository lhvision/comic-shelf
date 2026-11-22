"""单 API worker 的台词搜索限频与并发闸门；快速拒绝繁忙请求，不积压推理队列。"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from collections.abc import Generator
from contextlib import contextmanager

from fastapi import HTTPException, Request

from ..abuse import _TokenBucket
from ..auth import get_client_ip

_KEYWORD_SLOTS = threading.BoundedSemaphore(4)
_SEMANTIC_SLOTS = threading.BoundedSemaphore(1)
_RATE_LOCK = threading.Lock()
_BUCKETS: OrderedDict[tuple[str, bool], _TokenBucket] = OrderedDict()
_MAX_BUCKETS = 4096
_IDLE_SECONDS = 300


@contextmanager
def dialogue_search_slot(request: Request, *, semantic: bool = False) -> Generator[None]:
    """鉴权后按 IP/搜索类型限频，并发已满返回 429；结束或异常均归还槽位。

    关键词每秒补充 5 次、突发 10 次；语义每秒 1 次、突发 3 次。记录闲置五分钟
    后清理且总数不超过 4096，限制仅用于 HTTP，不改变本机 CLI 或 MCP 已有预算。
    """
    slots = _SEMANTIC_SLOTS if semantic else _KEYWORD_SLOTS
    if not slots.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="台词搜索繁忙，请稍后重试", headers={"Retry-After": "1"})
    try:
        key = get_client_ip(request), semantic
        with _RATE_LOCK:
            now = time.monotonic()
            while _BUCKETS and now - next(iter(_BUCKETS.values())).last_time > _IDLE_SECONDS:
                _BUCKETS.popitem(last=False)
            bucket = _BUCKETS.get(key)
            if bucket is None:
                if len(_BUCKETS) >= _MAX_BUCKETS:
                    _BUCKETS.popitem(last=False)
                bucket = _BUCKETS[key] = _TokenBucket(3 if semantic else 10, 1 if semantic else 5)
            _BUCKETS.move_to_end(key)
            if not bucket.consume():
                raise HTTPException(
                    status_code=429, detail="台词搜索频率过高，请稍后重试", headers={"Retry-After": "1"}
                )
        yield
    finally:
        slots.release()
