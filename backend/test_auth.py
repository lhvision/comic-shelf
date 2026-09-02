import sys
import asyncio
from pathlib import Path
from unittest.mock import MagicMock

# Ensure backend package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

import tempfile
from fastapi import HTTPException
import app.auth as auth_mod
import app.config as config_mod
import app.db as db_mod

# Point db to a temp sqlite database for tests
_temp_dir = tempfile.mkdtemp()
_temp_db = Path(_temp_dir) / "test_comic_shelf.db"
db_mod.init_db(_temp_db)


def make_mock_request(
    path="/api/library",
    headers=None,
    cookies=None,
    query_params=None,
):
    req = MagicMock()
    req.state = type("State", (), {})()
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
    assert auth_mod.is_curator(req) is True
    assert auth_mod.can_read(req) is True

    # 2. Curator + Guest Pass configured
    auth_mod.AUTH_SECRET = "admin-secret-123"
    assert auth_mod.is_auth_required() is True

    # Create active guest pass
    active_pass = db_mod.create_guest_pass("TestGuest", expires_days=30, custom_token="guest-secret-456")
    assert active_pass["token"] == "guest-secret-456"

    # Create expired guest pass
    db_mod.create_guest_pass("ExpiredGuest", expires_days=-1, custom_token="expired-secret-789")

    # Create disabled guest pass
    dis_pass = db_mod.create_guest_pass("DisabledGuest", expires_days=30, custom_token="disabled-secret-000")
    db_mod.update_guest_pass(dis_pass["id"], is_active=False)

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
    uid, uname, role = auth_mod.get_user_context(req_guest)
    assert uid == f"guest:{active_pass['id']}"
    assert uname == "TestGuest"
    assert role == "guest"

    # Expired token -> is_authenticated=False
    req_expired = make_mock_request(
        "/api/library",
        headers={"Authorization": "Bearer expired-secret-789"},
    )
    assert auth_mod.is_authenticated(req_expired) is False
    try:
        auth_mod.require_curator(req_expired)
        assert False, "Should raise 401 for expired token"
    except HTTPException as exc:
        assert exc.status_code == 401
        assert "过期" in exc.detail

    # Disabled token -> is_authenticated=False
    req_disabled = make_mock_request(
        "/api/library",
        headers={"Authorization": "Bearer disabled-secret-000"},
    )
    assert auth_mod.is_authenticated(req_disabled) is False

    # Curator Bearer token -> is_curator=True, is_guest=False, can_read=True
    req_curator = make_mock_request(
        "/api/library",
        headers={"Authorization": "Bearer admin-secret-123"},
    )
    assert auth_mod.is_authenticated(req_curator) is True
    assert auth_mod.is_curator(req_curator) is True
    assert auth_mod.can_read(req_curator) is True
    c_uid, c_name, c_role = auth_mod.get_user_context(req_curator)
    assert c_uid == "curator"
    assert c_role == "admin"

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

    # 3. Test user isolation for favorites and reading progress
    db_mod.set_user_favorite("curator", "jm", "12345", True)
    assert db_mod.is_user_favorite("curator", "jm", "12345") is True
    assert db_mod.is_user_favorite(f"guest:{active_pass['id']}", "jm", "12345") is False

    db_mod.set_user_progress(f"guest:{active_pass['id']}", "jm", "12345", 18, 100)
    prog_guest = db_mod.get_user_progress(f"guest:{active_pass['id']}", "jm", "12345")
    assert prog_guest is not None and prog_guest["last_page"] == 18
    assert db_mod.get_user_progress("curator", "jm", "12345") is None




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

    # Curator request
    req_curator = make_mock_request(
        "/api/discovery/ranking",
        headers={"Authorization": "Bearer admin-secret-123"},
    )
    assert auth_mod.is_curator(req_curator) is True
    # require_curator passes for curator
    auth_mod.require_curator(req_curator)

    # Guest request (using guest-secret-456 created in test_auth_logic)
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

    # Ensure guest-key-999 exists in test DB
    if not db_mod.get_guest_pass_by_token("guest-key-999"):
        db_mod.create_guest_pass("MidGuest", expires_days=30, custom_token="guest-key-999")

    async def run_cases():
        # Case 1: Open access (no secret configured)
        auth_mod.AUTH_SECRET = ""
        call_next = AsyncMock(return_value="OK")

        req_post = make_mock_request("/api/library/import")
        req_post.method = "POST"
        res = await auth_and_security_middleware(req_post, call_next)
        assert res == "OK", "Open access should allow POST /api/library/import"

        # Case 2: Protected mode (Curator + Guest Pass)
        auth_mod.AUTH_SECRET = "curator-key-888"

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
        for pub_path in ("/api/auth/status", "/api/health", "/api/auth/login", "/api/auth/claim", "/api/auth/logout"):
            call_next.reset_mock()
            req_pub = make_mock_request(pub_path)
            req_pub.method = "POST" if "login" in pub_path or "claim" in pub_path or "logout" in pub_path else "GET"
            res_pub = await auth_and_security_middleware(req_pub, call_next)
            assert res_pub == "OK", f"Endpoint {pub_path} should bypass middleware"
        # 2g. Image binary endpoints with static extension aliases trigger hotlink check
        for img_ext_path in (
            "/api/library/jm/1/covers/1/file.jpg",
            "/api/library/jm/1/pages/1/file.webp",
            "/api/library/jm/1/pages/1/thumbnail.jpg",
            "/api/library/jm/1/chapters/chap1/cover.jpg",
        ):
            call_next.reset_mock()
            req_img_cross = make_mock_request(
                img_ext_path,
                headers={
                    "Authorization": "Bearer guest-key-999",
                    "Sec-Fetch-Site": "cross-site",
                },
            )
            req_img_cross.method = "GET"
            res_cross = await auth_and_security_middleware(req_img_cross, call_next)
            assert getattr(res_cross, "status_code", None) == 403, f"Cross-site access to {img_ext_path} should be blocked (403)"

    asyncio.run(run_cases())


def test_quiet_access_log_filter():
    import logging
    from server import QuietAccessLogFilter

    f = QuietAccessLogFilter()

    # Health probe 200 OK should be silenced regardless of client IP (e.g. 10.0.0.1, 192.168.x, 172.x, IPv6)
    for probe_ip in ("10.0.0.1", "192.168.1.100", "172.20.0.2", "127.0.0.1", "::1"):
        rec_health = logging.LogRecord(
            "uvicorn.access", logging.INFO, "", 0,
            '%s - "%s %s HTTP/%s" %d',
            (probe_ip, "GET", "/api/health", "1.1", 200),
            None,
        )
        assert f.filter(rec_health) is False, f"Probe from {probe_ip} should be silenced"

    # Image search status probe 200 OK should be silenced
    rec_status_200 = logging.LogRecord(
        "uvicorn.access", logging.INFO, "", 0,
        '%s - "%s %s HTTP/%s" %d',
        ("192.168.1.50", "GET", "/api/search/image/status", "1.1", 200),
        None,
    )
    assert f.filter(rec_status_200) is False

    # Health probe with 500 error should be preserved
    rec_health_500 = logging.LogRecord(
        "uvicorn.access", logging.INFO, "", 0,
        '%s - "%s %s HTTP/%s" %d',
        ("10.0.0.2", "GET", "/api/health", "1.1", 500),
        None,
    )
    assert f.filter(rec_health_500) is True

    # Real image request 200 OK should be preserved
    rec_img_200 = logging.LogRecord(
        "uvicorn.access", logging.INFO, "", 0,
        '%s - "%s %s HTTP/%s" %d',
        ("192.168.1.200", "GET", "/api/library/jm/148952/pages/23/thumbnail.jpg", "1.1", 200),
        None,
    )
    assert f.filter(rec_img_200) is True


if __name__ == "__main__":
    test_auth_logic()
    test_hotlink_protection()
    test_guest_visibility_and_discovery_auth()
    test_auth_and_security_middleware()
    test_quiet_access_log_filter()
    print("All backend auth, middleware & hotlink protection tests passed!")


