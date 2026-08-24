import sys
import asyncio
from pathlib import Path
from unittest.mock import MagicMock

# Ensure backend package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import HTTPException
import app.auth as auth_mod
import app.config as config_mod


def make_mock_request(
    path="/api/library",
    headers=None,
    cookies=None,
    query_params=None,
):
    req = MagicMock()
    req.url.path = path
    headers_dict = {k.lower(): v for k, v in (headers or {}).items()}
    req.headers.get = lambda k, default="": headers_dict.get(k.lower(), default)
    req.cookies.get = lambda k, default="": (cookies or {}).get(k, default)
    req.query_params.get = lambda k, default="": (query_params or {}).get(k, default)
    return req


def test_auth_logic():
    # 1. No secret configured -> open access
    auth_mod.AUTH_SECRET = ""
    auth_mod.GUEST_SECRET = ""
    assert auth_mod.is_auth_required() is False
    req = make_mock_request("/api/library")
    assert auth_mod.is_authenticated(req) is True
    assert auth_mod.is_curator(req) is True
    assert auth_mod.can_read(req) is True

    # 2. Dual secret configured (Curator + Guest)
    auth_mod.AUTH_SECRET = "admin-secret-123"
    auth_mod.GUEST_SECRET = "guest-secret-456"
    assert auth_mod.is_auth_required() is True

    req_empty = make_mock_request("/api/library")
    assert auth_mod.is_authenticated(req_empty) is False
    assert auth_mod.is_curator(req_empty) is False
    assert auth_mod.is_guest(req_empty) is False
    assert auth_mod.can_read(req_empty) is False

    # Wrong Bearer token -> False
    req_wrong = make_mock_request(
        "/api/library",
        headers={"Authorization": "Bearer wrong-secret"},
    )
    assert auth_mod.is_authenticated(req_wrong) is False
    assert auth_mod.can_read(req_wrong) is False

    # Guest Bearer token -> is_guest=True, is_curator=False, can_read=True
    req_guest = make_mock_request(
        "/api/library",
        headers={"Authorization": "Bearer guest-secret-456"},
    )
    assert auth_mod.is_authenticated(req_guest) is True
    assert auth_mod.is_guest(req_guest) is True
    assert auth_mod.is_curator(req_guest) is False
    assert auth_mod.can_read(req_guest) is True

    # Curator Bearer token -> is_curator=True, is_guest=False, can_read=True
    req_curator = make_mock_request(
        "/api/library",
        headers={"Authorization": "Bearer admin-secret-123"},
    )
    assert auth_mod.is_authenticated(req_curator) is True
    assert auth_mod.is_curator(req_curator) is True
    assert auth_mod.can_read(req_curator) is True

    # require_admin on guest raises 403 Forbidden
    try:
        auth_mod.require_admin(req_guest)
        assert False, "Should have raised 403 Forbidden"
    except HTTPException as exc:
        assert exc.status_code == 403
        assert "访客模式" in exc.detail

    # require_admin on unauthenticated raises 401 Unauthorized
    try:
        auth_mod.require_admin(req_empty)
        assert False, "Should have raised 401 Unauthorized"
    except HTTPException as exc:
        assert exc.status_code == 401

    # require_admin on curator passes
    auth_mod.require_admin(req_curator)

    # 3. Solo Curator mode (No guest secret configured)
    auth_mod.AUTH_SECRET = "admin-secret-123"
    auth_mod.GUEST_SECRET = ""
    assert auth_mod.can_read(req_guest) is False
    assert auth_mod.can_read(req_curator) is True




def test_hotlink_protection():
    auth_mod.ENABLE_HOTLINK_PROTECTION = True

    # 1. Sec-Fetch-Site: cross-site -> blocked
    req_cross = make_mock_request(
        "/api/library/jm/1/covers/1/file",
        headers={"Sec-Fetch-Site": "cross-site"},
    )
    try:
        auth_mod.check_hotlink_protection(req_cross)
        assert False, "Should have raised HTTPException 403"
    except HTTPException as exc:
        assert exc.status_code == 403
        assert "防盗链保护" in exc.detail

    # 2. Referer from unknown external domain -> blocked
    req_bad_ref = make_mock_request(
        "/api/library/jm/1/covers/1/file",
        headers={
            "Sec-Fetch-Site": "same-origin",
            "Referer": "https://malicious-thief.com/comic",
            "Host": "localhost:8000",
        },
    )
    try:
        auth_mod.check_hotlink_protection(req_bad_ref)
        assert False, "Should have raised HTTPException 403"
    except HTTPException as exc:
        assert exc.status_code == 403
        assert "防盗链保护" in exc.detail

    # 3. Referer from localhost dev -> allowed
    req_dev_ref = make_mock_request(
        "/api/library/jm/1/covers/1/file",
        headers={
            "Sec-Fetch-Site": "same-origin",
            "Referer": "http://localhost:5173/comic/jm/1",
            "Host": "localhost:8000",
        },
    )
    # Should not raise
    auth_mod.check_hotlink_protection(req_dev_ref)

    # 4. Same host referer -> allowed
    req_same_ref = make_mock_request(
        "/api/library/jm/1/covers/1/file",
        headers={
            "Sec-Fetch-Site": "same-origin",
            "Referer": "https://my-nas.lan:8000/comic/jm/1",
            "Host": "my-nas.lan:8000",
        },
    )
    # Should not raise
    auth_mod.check_hotlink_protection(req_same_ref)


if __name__ == "__main__":
    test_auth_logic()
    test_hotlink_protection()
    print("All backend auth & hotlink protection tests passed!")
