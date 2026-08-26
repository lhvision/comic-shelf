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

    # require_curator on guest raises 403 Forbidden
    try:
        auth_mod.require_curator(req_guest)
        assert False, "Should have raised 403 Forbidden"
    except HTTPException as exc:
        assert exc.status_code == 403
        assert "访客模式" in exc.detail

    # require_curator on unauthenticated raises 401 Unauthorized
    try:
        auth_mod.require_curator(req_empty)
        assert False, "Should have raised 401 Unauthorized"
    except HTTPException as exc:
        assert exc.status_code == 401

    # require_curator and require_admin alias on curator passes
    auth_mod.require_curator(req_curator)
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


def test_guest_visibility_and_discovery_auth():
    auth_mod.AUTH_SECRET = "admin-secret-123"
    auth_mod.GUEST_SECRET = "guest-secret-456"

    # Curator request
    req_curator = make_mock_request(
        "/api/discovery/ranking",
        headers={"Authorization": "Bearer admin-secret-123"},
    )
    assert auth_mod.is_curator(req_curator) is True
    # require_curator passes for curator
    auth_mod.require_curator(req_curator)

    # Guest request
    req_guest = make_mock_request(
        "/api/discovery/ranking",
        headers={"Authorization": "Bearer guest-secret-456"},
    )
    assert auth_mod.is_curator(req_guest) is False
    assert auth_mod.is_guest(req_guest) is True
    try:
        auth_mod.require_curator(req_guest)
        assert False, "Should have raised 403 Forbidden for guest"
    except HTTPException as exc:
        assert exc.status_code == 403


def test_auth_and_security_middleware():
    from app.main import auth_and_security_middleware
    from unittest.mock import AsyncMock

    async def run_cases():
        # Case 1: Open access (no secret configured)
        auth_mod.AUTH_SECRET = ""
        auth_mod.GUEST_SECRET = ""
        call_next = AsyncMock(return_value="OK")

        req_post = make_mock_request("/api/library/import")
        req_post.method = "POST"
        res = await auth_and_security_middleware(req_post, call_next)
        assert res == "OK", "Open access should allow POST /api/library/import"

        # Case 2: Protected mode (Curator + Guest)
        auth_mod.AUTH_SECRET = "curator-key-888"
        auth_mod.GUEST_SECRET = "guest-key-999"

        # 2a. Unauthenticated POST -> 401
        call_next.reset_mock()
        req_unauth_post = make_mock_request("/api/library/import")
        req_unauth_post.method = "POST"
        res_401 = await auth_and_security_middleware(req_unauth_post, call_next)
        assert getattr(res_401, "status_code", None) == 401

        # 2b. Guest attempting POST /api/library/import -> 403
        call_next.reset_mock()
        req_guest_post = make_mock_request(
            "/api/library/import",
            headers={"Authorization": "Bearer guest-key-999"},
        )
        req_guest_post.method = "POST"
        res_403 = await auth_and_security_middleware(req_guest_post, call_next)
        assert getattr(res_403, "status_code", None) == 403

        # 2c. Curator POST /api/library/import -> OK
        call_next.reset_mock()
        req_curator_post = make_mock_request(
            "/api/library/import",
            headers={"Authorization": "Bearer curator-key-888"},
        )
        req_curator_post.method = "POST"
        res_ok = await auth_and_security_middleware(req_curator_post, call_next)
        assert res_ok == "OK"

        # 2d. Guest GET /api/library -> OK
        call_next.reset_mock()
        req_guest_get = make_mock_request(
            "/api/library",
            headers={"Authorization": "Bearer guest-key-999"},
        )
        req_guest_get.method = "GET"
        res_get_ok = await auth_and_security_middleware(req_guest_get, call_next)
        assert res_get_ok == "OK"

        # 2e. Image search POST is allowed for guest
        call_next.reset_mock()
        req_img_search = make_mock_request(
            "/api/search/image",
            headers={"Authorization": "Bearer guest-key-999"},
        )
        req_img_search.method = "POST"
        res_search_ok = await auth_and_security_middleware(req_img_search, call_next)
        assert res_search_ok == "OK"

        # 2f. Public endpoints bypass auth
        for pub_path in ("/api/auth/status", "/api/health", "/api/auth/login"):
            call_next.reset_mock()
            req_pub = make_mock_request(pub_path)
            req_pub.method = "GET"
            res_pub = await auth_and_security_middleware(req_pub, call_next)
            assert res_pub == "OK"

    asyncio.run(run_cases())


if __name__ == "__main__":
    test_auth_logic()
    test_hotlink_protection()
    test_guest_visibility_and_discovery_auth()
    test_auth_and_security_middleware()
    print("All backend auth, middleware & hotlink protection tests passed!")

