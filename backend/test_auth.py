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
    assert auth_mod.is_auth_required() is False
    req = make_mock_request("/api/library")
    assert auth_mod.is_authenticated(req) is True

    # 2. Secret configured
    auth_mod.AUTH_SECRET = "my-secret-123"
    assert auth_mod.is_auth_required() is True

    # No credentials -> False
    req_empty = make_mock_request("/api/library")
    assert auth_mod.is_authenticated(req_empty) is False

    # Wrong Bearer token -> False
    req_wrong = make_mock_request(
        "/api/library",
        headers={"Authorization": "Bearer wrong-secret"},
    )
    assert auth_mod.is_authenticated(req_wrong) is False

    # Correct Bearer token -> True
    req_bearer = make_mock_request(
        "/api/library",
        headers={"Authorization": "Bearer my-secret-123"},
    )
    assert auth_mod.is_authenticated(req_bearer) is True

    # Correct X-Auth-Token -> True
    req_xtoken = make_mock_request(
        "/api/library",
        headers={"X-Auth-Token": "my-secret-123"},
    )
    assert auth_mod.is_authenticated(req_xtoken) is True

    # Correct Cookie -> True
    req_cookie = make_mock_request(
        "/api/library",
        cookies={"comic_shelf_token": "my-secret-123"},
    )
    assert auth_mod.is_authenticated(req_cookie) is True

    # Correct Query param -> True
    req_query = make_mock_request(
        "/api/library",
        query_params={"token": "my-secret-123"},
    )
    assert auth_mod.is_authenticated(req_query) is True


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
