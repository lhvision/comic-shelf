import secrets
import time
from urllib.parse import urlparse

from fastapi import HTTPException, Request, Response

from .config import (
    AUTH_SECRET,
    COOKIE_NAME,
    DEVICE_COOKIE_NAME,
    ENABLE_HOTLINK_PROTECTION,
)
from .db import (
    get_device_by_token,
    get_guest_pass_by_token,
    register_guest_device,
    touch_device_active,
)


def is_auth_required() -> bool:
    """True if curator secret is configured."""
    return bool(AUTH_SECRET)


def get_client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff and isinstance(xff, str):
        return xff.split(",")[0].strip()[:45]
    client = getattr(request, "client", None)
    if client and hasattr(client, "host") and isinstance(client.host, str):
        return client.host[:45]
    return ""


def extract_token(request: Request) -> str:
    # 1. Bearer token in Authorization header
    auth_header = request.headers.get("authorization", "").strip()
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()

    # 2. X-Auth-Token header
    x_token = request.headers.get("x-auth-token", "").strip()
    if x_token:
        return x_token

    # 3. Http Cookie (used by browser img tags and SPA)
    cookie_token = request.cookies.get(COOKIE_NAME, "").strip()
    if cookie_token:
        return cookie_token

    # 4. Query param (?token=xxx)
    query_token = request.query_params.get("token", "").strip()
    if query_token:
        return query_token

    return ""


def extract_device_token(request: Request) -> str:
    # 1. Header X-Device-Token
    x_dev = request.headers.get("x-device-token", "").strip()
    if x_dev:
        return x_dev

    # 2. Cookie
    cookie_dev = request.cookies.get(DEVICE_COOKIE_NAME, "").strip()
    if cookie_dev:
        return cookie_dev

    return ""


def get_user_context(request: Request) -> tuple[str, str, str]:
    """Returns (user_id, username, role) where role is 'admin' | 'guest' | 'unauthorized' | 'expired'."""
    if hasattr(request.state, "user_context"):
        return request.state.user_context  # type: ignore[no-any-return]

    if not is_auth_required():
        ctx = ("curator", "馆长", "admin")
        request.state.user_context = ctx
        return ctx

    token = extract_token(request)
    device_token = extract_device_token(request)

    # 1. Curator token check
    if token and AUTH_SECRET and secrets.compare_digest(token, AUTH_SECRET):
        ctx = ("curator", "馆长", "admin")
        request.state.user_context = ctx
        return ctx

    # 2. Device token check (fast path for established device sessions)
    if device_token:
        dev = get_device_by_token(device_token)
        if dev is not None:
            now = int(time.time())
            if not dev["pass_is_active"]:
                ctx = ("anonymous", "已停用", "unauthorized")
            elif dev["pass_expires_at"] and now > dev["pass_expires_at"]:
                ctx = ("anonymous", "已过期", "expired")
            else:
                client_ip = get_client_ip(request)
                # Throttle database write: touch device active only if > 60s elapsed or IP changed
                last_active = int(dev.get("last_active_at", 0) or 0)
                if (now - last_active > 60) or (client_ip and dev.get("last_ip") != client_ip):
                    touch_device_active(dev["id"], client_ip)
                ctx = (f"guest:{dev['pass_id']}", dev["username"], "guest")
                request.state.device_id = dev["id"]
            request.state.user_context = ctx
            return ctx
        else:
            # Device token was provided but evicted or deleted
            ctx = ("anonymous", "设备已失效或已被踢下线", "unauthorized")
            request.state.user_context = ctx
            return ctx

    # 3. Pass token check
    # Under ADR 0008, all guest access to protected endpoints MUST be authenticated via an active
    # device session (device_token). A bare pass token cannot grant 'guest' role without PIN verification.
    if token:
        pass_item = get_guest_pass_by_token(token)
        if pass_item is not None:
            if not pass_item["is_active"]:
                ctx = ("anonymous", "已停用", "unauthorized")
            elif pass_item["is_expired"]:
                ctx = ("anonymous", "已过期", "expired")
            elif pass_item.get("is_claimed") or pass_item.get("pin_hash"):
                ctx = ("anonymous", "需要 PIN 码验证", "unauthorized")
            else:
                ctx = ("anonymous", "待认领通行证", "unauthorized")
            request.state.user_context = ctx
            return ctx

    ctx = ("anonymous", "未授权", "unauthorized")
    request.state.user_context = ctx
    return ctx


def get_current_user_id(request: Request) -> str:
    return get_user_context(request)[0]


def is_curator(request: Request) -> bool:
    """True if caller has full curator write/management permissions."""
    return get_user_context(request)[2] == "admin"


def is_guest(request: Request) -> bool:
    """True if caller provided a valid active, unexpired guest pass."""
    return get_user_context(request)[2] == "guest"


def is_authenticated(request: Request) -> bool:
    """True if caller provided either a valid curator secret or active guest pass."""
    return get_user_context(request)[2] in ("admin", "guest")


def can_read(request: Request) -> bool:
    """True if caller is allowed to browse and read comics."""
    return is_authenticated(request)


def get_user_role(request: Request) -> str:
    """Returns 'admin', 'guest', or 'unauthorized'."""
    role = get_user_context(request)[2]
    return role if role in ("admin", "guest") else "unauthorized"


def require_curator(request: Request) -> None:
    """Ensure caller has curator write permissions."""
    _uid, _name, role = get_user_context(request)
    if role == "admin":
        return

    if role == "guest":
        raise HTTPException(
            status_code=403,
            detail="访客模式下禁止执行修改操作，请先解锁馆长权限",
        )

    if role == "expired":
        raise HTTPException(
            status_code=401,
            detail="通行证已过期，请联系馆长续期",
            headers={"WWW-Authenticate": "Bearer"},
        )

    raise HTTPException(
        status_code=401,
        detail="未授权访问，需要提供有效的通行口令",
        headers={"WWW-Authenticate": "Bearer"},
    )


# Alias for backward compatibility
require_admin = require_curator


def is_request_secure(request: Request | None) -> bool:
    """Check if the incoming HTTP request is over HTTPS (including Cloudflare/reverse proxy)."""
    if not request:
        return False
    if getattr(request, "url", None) and request.url.scheme == "https":
        return True
    x_proto = request.headers.get("x-forwarded-proto", "").strip().lower()
    if x_proto and x_proto.split(",")[0].strip() == "https":
        return True
    x_scheme = request.headers.get("x-forwarded-scheme", "").strip().lower()
    if x_scheme and x_scheme.split(",")[0].strip() == "https":
        return True
    cf_visitor = request.headers.get("cf-visitor", "")
    if '"scheme":"https"' in cf_visitor.lower():
        return True
    return False


def check_hotlink_protection(request: Request) -> None:
    """Verify that image requests are not cross-site hotlinks or storage abuse."""
    if not ENABLE_HOTLINK_PROTECTION:
        return

    # 1. Sec-Fetch-Site check (Supported by modern browsers: Chrome, Safari, Firefox, Edge)
    sec_fetch_site = request.headers.get("sec-fetch-site", "").strip().lower()
    if sec_fetch_site == "cross-site":
        raise HTTPException(
            status_code=403,
            detail="防盗链保护：禁止跨站直接引用图片资源 (Cross-site hotlinking blocked)",
        )

    # 2. Referer check
    referer = request.headers.get("referer", "").strip()
    if referer:
        try:
            ref_parsed = urlparse(referer)
            ref_host = (ref_parsed.hostname or "").lower()
            ref_netloc = ref_parsed.netloc.lower()

            host = request.headers.get("host", "").strip().lower()
            xf_host = request.headers.get("x-forwarded-host", "").strip().lower()

            allowed_hosts: set[str] = set()
            for raw_h in (host, xf_host):
                if not raw_h:
                    continue
                for item in raw_h.split(","):
                    h = item.strip()
                    if h:
                        allowed_hosts.add(h)
                        if ":" in h:
                            allowed_hosts.add(h.split(":", 1)[0])

            for dev_host in ("localhost", "127.0.0.1", "0.0.0.0"):
                allowed_hosts.add(dev_host)
                allowed_hosts.add(f"{dev_host}:5173")
                allowed_hosts.add(f"{dev_host}:4173")
                allowed_hosts.add(f"{dev_host}:8000")

            is_allowed = (
                ref_netloc in allowed_hosts
                or ref_host in allowed_hosts
                or any(ref_netloc.startswith(f"{h}:") or ref_netloc == h for h in allowed_hosts)
            )

            if not is_allowed:
                raise HTTPException(
                    status_code=403,
                    detail=f"防盗链保护：来源域名未经允许 ({ref_netloc})",
                )
        except HTTPException:
            raise
        except Exception:
            pass


def set_auth_cookie(response: Response, token: str, secure: bool = False) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=2592000,  # 30 days
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )


def set_device_cookie(response: Response, device_token: str, secure: bool = False) -> None:
    response.set_cookie(
        key=DEVICE_COOKIE_NAME,
        value=device_token,
        max_age=2592000,  # 30 days
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )


def clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(
        key=COOKIE_NAME,
        path="/",
    )


def clear_device_cookie(response: Response) -> None:
    response.delete_cookie(
        key=DEVICE_COOKIE_NAME,
        path="/",
    )
