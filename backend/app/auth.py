from __future__ import annotations

import secrets
from urllib.parse import urlparse

from fastapi import HTTPException, Request, Response

from .config import AUTH_SECRET, ENABLE_HOTLINK_PROTECTION

COOKIE_NAME = "comic_shelf_token"


def is_auth_required() -> bool:
    return bool(AUTH_SECRET)


def is_authenticated(request: Request) -> bool:
    if not is_auth_required():
        return True

    # 1. Bearer token in Authorization header
    auth_header = request.headers.get("authorization", "").strip()
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
        if token and secrets.compare_digest(token, AUTH_SECRET):
            return True

    # 2. X-Auth-Token header
    x_token = request.headers.get("x-auth-token", "").strip()
    if x_token and secrets.compare_digest(x_token, AUTH_SECRET):
        return True

    # 3. Http Cookie (used by browser img tags and SPA)
    cookie_token = request.cookies.get(COOKIE_NAME, "").strip()
    if cookie_token and secrets.compare_digest(cookie_token, AUTH_SECRET):
        return True

    # 4. Query param (?token=xxx)
    query_token = request.query_params.get("token", "").strip()
    if query_token and secrets.compare_digest(query_token, AUTH_SECRET):
        return True

    return False


def require_auth(request: Request) -> None:
    if not is_authenticated(request):
        raise HTTPException(
            status_code=401,
            detail="未授权访问，需要提供有效的访问密钥",
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
            forwarded_host = request.headers.get("x-forwarded-host", "").strip().lower()

            allowed_hosts = {h for h in (host, forwarded_host) if h}
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
