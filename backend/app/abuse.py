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
_cooling_mutex = threading.RLock()


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
# 180 页 / 分钟 (3.0 tokens/s) + 100 页瞬时突发容量
# ----------------------------------------------------------------------
_RATE_CAPACITY = 100.0
_RATE_REFILL_PER_SEC = 3.0  # 180 pages / 60 seconds


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
_rate_mutex = threading.RLock()


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


# ----------------------------------------------------------------------
# 3. 双重限流键 PIN 码防暴力破解限制器 (Dual-Key PIN Rate Limiter)
# - 单 IP + Pass: 1 分钟内输错 5 次 -> 仅该 IP 锁定 5 分钟 (杜绝恶意群友 DoS 号主)
# - 全局 Pass: 1 小时内全网累计输错 20 次 -> 全局锁定 30 分钟 (防分布式撞库)
# ----------------------------------------------------------------------
_PIN_ATTEMPT_WINDOW_SECONDS = 60.0   # 1 minute per IP
_PIN_MAX_FAILED_ATTEMPTS = 5         # max 5 failed attempts per IP
_PIN_LOCK_SECONDS = 300.0            # 5 minutes lock

_PIN_GLOBAL_WINDOW_SECONDS = 3600.0  # 1 hour global
_PIN_GLOBAL_MAX_ATTEMPTS = 20        # max 20 attempts global
_PIN_GLOBAL_LOCK_SECONDS = 1800.0    # 30 minutes lock

_pin_ip_failed_history: dict[str, list[float]] = {}      # "ip:pass_id" -> timestamps
_pin_ip_locks: dict[str, float] = {}                    # "ip:pass_id" -> locked_until
_pin_global_failed_history: dict[int, list[float]] = {} # pass_id -> timestamps
_pin_global_locks: dict[int, float] = {}                 # pass_id -> locked_until
_pin_mutex = threading.RLock()


def is_pin_locked(pass_id: int, ip: str = "") -> tuple[bool, str]:
    now = time.time()
    with _pin_mutex:
        # 1. Check global pass lockout first
        global_locked_until = _pin_global_locks.get(pass_id, 0.0)
        if global_locked_until > now:
            return True, "通行证 PIN 码全网尝试次数过多，已保护性锁定 30 分钟，请稍后再试或联系馆长重置"
        elif global_locked_until > 0.0:
            del _pin_global_locks[pass_id]

        # 2. Check IP-specific lockout
        key = f"{ip}:{pass_id}" if ip else f":{pass_id}"
        ip_locked_until = _pin_ip_locks.get(key, 0.0)
        if ip_locked_until > now:
            return True, "PIN 码连续输错次数过多，该设备已临时锁定 5 分钟，请稍后再试"
        elif ip_locked_until > 0.0:
            del _pin_ip_locks[key]

        return False, ""


def record_pin_failure_and_check_lock(pass_id: int, ip: str = "") -> tuple[bool, str]:
    """Records a wrong PIN attempt. Returns (is_now_locked, message)."""
    now = time.time()
    with _pin_mutex:
        # Check existing lock first
        locked, reason = is_pin_locked(pass_id, ip)
        if locked:
            return True, reason

        # 1. Record for IP key
        key = f"{ip}:{pass_id}" if ip else f":{pass_id}"
        ip_history = _pin_ip_failed_history.setdefault(key, [])
        cutoff_ip = now - _PIN_ATTEMPT_WINDOW_SECONDS
        ip_history = [t for t in ip_history if t > cutoff_ip]
        ip_history.append(now)
        _pin_ip_failed_history[key] = ip_history

        # 2. Record for global pass key
        global_history = _pin_global_failed_history.setdefault(pass_id, [])
        cutoff_global = now - _PIN_GLOBAL_WINDOW_SECONDS
        global_history = [t for t in global_history if t > cutoff_global]
        global_history.append(now)
        _pin_global_failed_history[pass_id] = global_history

        if len(ip_history) >= _PIN_MAX_FAILED_ATTEMPTS:
            _pin_ip_locks[key] = now + _PIN_LOCK_SECONDS
            return True, "PIN 码连续输错达到上限，该设备已临时锁定 5 分钟"

        if len(global_history) >= _PIN_GLOBAL_MAX_ATTEMPTS:
            _pin_global_locks[pass_id] = now + _PIN_GLOBAL_LOCK_SECONDS
            return True, "通行证 PIN 码全网尝试次数超限，已保护性锁定 30 分钟"

        return False, ""


def clear_pin_failures(pass_id: int, ip: str = "") -> None:
    with _pin_mutex:
        _pin_global_locks.pop(pass_id, None)
        _pin_global_failed_history.pop(pass_id, None)
        if ip:
            _pin_ip_locks.pop(f"{ip}:{pass_id}", None)
            _pin_ip_failed_history.pop(f"{ip}:{pass_id}", None)
        else:
            suffix = f":{pass_id}"
            keys_to_del = [k for k in _pin_ip_locks if k.endswith(suffix)]
            for k in keys_to_del:
                _pin_ip_locks.pop(k, None)
            hist_keys_to_del = [k for k in _pin_ip_failed_history if k.endswith(suffix)]
            for k in hist_keys_to_del:
                _pin_ip_failed_history.pop(k, None)


# ----------------------------------------------------------------------
# 4. 全局口令碰撞防爆破限制器 (IP Login Brute-Force Limiter)
# 单 IP 1 分钟内口令错误达到 10 次 -> 锁定该 IP 5 分钟
# ----------------------------------------------------------------------
_LOGIN_ATTEMPT_WINDOW_SECONDS = 60.0  # 1 minute
_LOGIN_MAX_FAILED_ATTEMPTS = 10       # max 10 failed attempts per IP
_LOGIN_LOCK_SECONDS = 300.0           # 5 minutes lock

_login_failed_history: dict[str, list[float]] = {}  # ip -> timestamps
_login_ip_locks: dict[str, float] = {}             # ip -> locked_until
_login_mutex = threading.RLock()


def is_ip_login_locked(ip: str) -> bool:
    if not ip:
        return False
    now = time.time()
    with _login_mutex:
        locked_until = _login_ip_locks.get(ip, 0.0)
        if locked_until > now:
            return True
        elif locked_until > 0.0:
            del _login_ip_locks[ip]
        return False


def record_ip_login_failure_and_check_lock(ip: str) -> bool:
    """Records an invalid secret login attempt. Returns True if IP is now locked."""
    if not ip:
        return False
    now = time.time()
    with _login_mutex:
        locked_until = _login_ip_locks.get(ip, 0.0)
        if locked_until > now:
            return True

        history = _login_failed_history.setdefault(ip, [])
        cutoff = now - _LOGIN_ATTEMPT_WINDOW_SECONDS
        history = [t for t in history if t > cutoff]
        history.append(now)
        _login_failed_history[ip] = history

        if len(history) >= _LOGIN_MAX_FAILED_ATTEMPTS:
            _login_ip_locks[ip] = now + _LOGIN_LOCK_SECONDS
            return True
        return False


def clear_ip_login_failures(ip: str) -> None:
    if not ip:
        return
    with _login_mutex:
        _login_ip_locks.pop(ip, None)
        _login_failed_history.pop(ip, None)


