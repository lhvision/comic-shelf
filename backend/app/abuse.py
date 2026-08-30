"""Guest abuse prevention: Eviction cooling lock & token bucket rate limiting.
Implements ADR 0008.
"""
from __future__ import annotations

import threading
import time

# ----------------------------------------------------------------------
# 1. 设备置换频次熔断冷却锁 (Eviction Cooling Lock)
# 5 分钟内连续置换超过 3 次 -> 锁定 10 分钟
# ----------------------------------------------------------------------
_EVICTION_WINDOW_SECONDS = 300.0  # 5 minutes
_EVICTION_MAX_COUNT = 3           # max 3 evictions per 5 minutes
_COOLING_LOCK_SECONDS = 600.0     # 10 minutes lock

_eviction_history: dict[int, list[float]] = {}
_cooling_locks: dict[int, float] = {}  # pass_id -> locked_until timestamp
_cooling_mutex = threading.Lock()


def is_eviction_cooling_locked(pass_id: int) -> bool:
    now = time.time()
    with _cooling_mutex:
        locked_until = _cooling_locks.get(pass_id, 0.0)
        if locked_until > now:
            return True
        elif locked_until > 0.0:
            del _cooling_locks[pass_id]
        return False


def record_eviction_and_check_lock(pass_id: int) -> bool:
    """Record an eviction event. Activates cooling lock if threshold exceeded.
    Returns True if cooling lock is now active."""
    now = time.time()
    with _cooling_mutex:
        locked_until = _cooling_locks.get(pass_id, 0.0)
        if locked_until > now:
            return True

        history = _eviction_history.setdefault(pass_id, [])
        cutoff = now - _EVICTION_WINDOW_SECONDS
        history = [t for t in history if t > cutoff]
        history.append(now)
        _eviction_history[pass_id] = history

        if len(history) > _EVICTION_MAX_COUNT:
            _cooling_locks[pass_id] = now + _COOLING_LOCK_SECONDS
            return True
        return False


def clear_cooling_lock(pass_id: int) -> None:
    with _cooling_mutex:
        _cooling_locks.pop(pass_id, None)
        _eviction_history.pop(pass_id, None)


# ----------------------------------------------------------------------
# 2. 访客令牌桶静态图片请求限流 (Guest Image Rate Limiter)
# 120 页 / 分钟 (2.0 tokens/s) + 45 页瞬时突发容量
# ----------------------------------------------------------------------
_RATE_CAPACITY = 45.0
_RATE_REFILL_PER_SEC = 2.0  # 120 pages / 60 seconds


class _TokenBucket:
    __slots__ = ("tokens", "last_time")

    def __init__(self) -> None:
        self.tokens = _RATE_CAPACITY
        self.last_time = time.time()

    def consume(self, amount: float = 1.0) -> bool:
        now = time.time()
        elapsed = now - self.last_time
        self.last_time = now
        self.tokens = min(_RATE_CAPACITY, self.tokens + elapsed * _RATE_REFILL_PER_SEC)
        if self.tokens >= amount:
            self.tokens -= amount
            return True
        return False


_guest_rate_buckets: dict[int, _TokenBucket] = {}
_guest_rate_limited_until: dict[int, float] = {}  # pass_id -> timestamp
_rate_mutex = threading.Lock()


def check_guest_rate_limit(pass_id: int) -> bool:
    """Returns True if allowed, False if rate limited."""
    now = time.time()
    with _rate_mutex:
        bucket = _guest_rate_buckets.get(pass_id)
        if bucket is None:
            bucket = _TokenBucket()
            _guest_rate_buckets[pass_id] = bucket

        allowed = bucket.consume(1.0)
        if not allowed:
            _guest_rate_limited_until[pass_id] = now + 30.0  # flag as limited for 30s
        return allowed


def is_pass_rate_limited(pass_id: int) -> bool:
    now = time.time()
    with _rate_mutex:
        limited_until = _guest_rate_limited_until.get(pass_id, 0.0)
        if limited_until > now:
            return True
        elif limited_until > 0.0:
            del _guest_rate_limited_until[pass_id]
        return False


def clear_rate_limit(pass_id: int) -> None:
    with _rate_mutex:
        _guest_rate_buckets.pop(pass_id, None)
        _guest_rate_limited_until.pop(pass_id, None)
