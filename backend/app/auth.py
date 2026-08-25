from __future__ import annotations

import secrets
from urllib.parse import urlparse

from fastapi import HTTPException, Request, Response

from .config import AUTH_SECRET, ENABLE_HOTLINK_PROTECTION, GUEST_SECRET

COOKIE_NAME = "comic_shelf_token"


def is_auth_required() -> bool:
    """True if any secret (curator or guest) is configured."""
    return bool(AUTH_SECRET or GUEST_SECRET)


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


def is_curator(request: Request) -> bool:
    """True if caller has full curator write/management permissions."""
    if not is_auth_required():
        return True
    if not AUTH_SECRET:
        return False
    token = extract_token(request)
    return bool(token and secrets.compare_digest(token, AUTH_SECRET))


def is_guest(request: Request) -> bool:
    """True if caller provided the valid guest reading secret."""
    if not is_auth_required() or not GUEST_SECRET:
        return False
    token = extract_token(request)
    return bool(token and secrets.compare_digest(token, GUEST_SECRET))


def is_authenticated(request: Request) -> bool:
    """True if caller provided either a valid curator or guest token."""
    if not is_auth_required():
        return True
    return is_curator(request) or is_guest(request)


def is_admin(request: Request) -> bool:
    """Alias for is_curator."""
    return is_curator(request)


def can_read(request: Request) -> bool:
    """True if caller is allowed to browse and read comics."""
    if not is_auth_required():
        return True
    return is_curator(request) or is_guest(request)


def get_user_role(request: Request) -> str:
    """Returns 'admin', 'guest', or 'unauthorized'."""
    if not is_auth_required() or is_curator(request):
        return "admin"
    if is_guest(request):
        return "guest"
    return "unauthorized"


def require_admin(request: Request) -> None:
    """Ensure caller has curator write permissions."""
    if is_admin(request):
        return

    if is_guest(request):
        raise HTTPException(
            status_code=403,
            detail="访客模式下禁止执行修改操作，请先解锁馆长权限",
        )

    raise HTTPException(
        status_code=401,
        detail="未授权访问，需要提供有效的通行口令",
        headers={"WWW-Authenticate": "Bearer"},
    )





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
            ref_netloc = ref_parsed.netloc.lower()

            host = request.headers.get("host", "").strip().lower()

            allowed_hosts = {host} if host else set()
            for dev_host in ("localhost", "127.0.0.1", "0.0.0.0"):
                allowed_hosts.add(dev_host)
                allowed_hosts.add(f"{dev_host}:5173")
                allowed_hosts.add(f"{dev_host}:4173")
                allowed_hosts.add(f"{dev_host}:8000")

            if ref_netloc and ref_netloc not in allowed_hosts and not any(
                ref_netloc.startswith(f"{h}:") or ref_netloc == h for h in allowed_hosts
            ):
                raise HTTPException(
                    status_code=403,
                    detail=f"防盗链保护：来源域名未经允许 ({ref_netloc})",
                )
        except HTTPException:
            raise
        except Exception:
            pass


def set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=2592000,  # 30 days
        httponly=True,
        samesite="lax",
        path="/",
    )


def clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(
        key=COOKIE_NAME,
        path="/",
    )
