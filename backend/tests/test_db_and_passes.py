import sys
import tempfile
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from starlette.exceptions import HTTPException
import app.db as db_mod


def test_db_and_passes_crud():
    temp_dir = tempfile.mkdtemp()
    temp_db = Path(temp_dir) / "test_passes.db"
    db_mod.init_db(temp_db)

    # 1. Create pass
    p1 = db_mod.create_guest_pass("Alice", expires_days=7)
    assert p1["id"] is not None
    assert p1["username"] == "Alice"
    assert p1["is_active"] is True
    assert p1["is_expired"] is False
    assert len(p1["token"]) == 32

    # 2. Get by token
    p1_found = db_mod.get_guest_pass_by_token(p1["token"])
    assert p1_found is not None
    assert p1_found["id"] == p1["id"]

    # 3. Update / Renew pass
    p1_renewed = db_mod.update_guest_pass(p1["id"], extend_days=30)
    assert p1_renewed is not None
    assert p1_renewed["expires_at"] > p1["expires_at"]

    # 4. Reset token
    p1_reset = db_mod.update_guest_pass(p1["id"], reset_token=True)
    assert p1_reset is not None
    assert p1_reset["token"] != p1["token"]
    assert db_mod.get_guest_pass_by_token(p1["token"]) is None
    assert db_mod.get_guest_pass_by_token(p1_reset["token"]) is not None

    # 5. Disable pass
    p1_dis = db_mod.update_guest_pass(p1["id"], is_active=False)
    assert p1_dis is not None
    assert p1_dis["is_active"] is False

    # 6. Reading progress upsert
    db_mod.set_user_progress("guest:1", "local", "demo1", last_page=5, total_pages=20)
    prog = db_mod.get_user_progress("guest:1", "local", "demo1")
    assert prog is not None
    assert prog["last_page"] == 5
    assert prog["total_pages"] == 20

    db_mod.set_user_progress("guest:1", "local", "demo1", last_page=12)
    prog2 = db_mod.get_user_progress("guest:1", "local", "demo1")
    assert prog2 is not None
    assert prog2["last_page"] == 12
    assert prog2["total_pages"] == 20

    # 7. Delete pass
    assert db_mod.delete_guest_pass(p1["id"]) is True
    assert db_mod.get_guest_pass_by_id(p1["id"]) is None

    # 8. Token conflict handling
    db_mod.create_guest_pass("Bob", custom_token="unique_token_xyz", max_devices=2)
    try:
        db_mod.create_guest_pass("Charlie", custom_token="unique_token_xyz")
        assert False, "Should raise ValueError for duplicate token"
    except ValueError as exc:
        assert "存在" in str(exc)

    # 9. Device slots & activation states lifecycle
    bob_pass = db_mod.get_guest_pass_by_token("unique_token_xyz")
    assert bob_pass is not None
    assert bob_pass["activation_status"] == "pending"  # 0 devices = pending
    assert bob_pass["device_count"] == 0

    # Register Device 1 (iPhone)
    d1 = db_mod.register_guest_device(
        bob_pass["id"],
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1",
        ip="192.168.1.100",
    )
    assert d1["device_name"] == "iPhone · Safari"
    bob_pass = db_mod.get_guest_pass_by_id(bob_pass["id"])
    assert bob_pass["activation_status"] == "active"  # 1 of 2 devices
    assert bob_pass["device_count"] == 1

    time.sleep(0.01)

    # Register Device 2 (Windows Chrome)
    d2 = db_mod.register_guest_device(
        bob_pass["id"],
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        ip="10.0.0.50",
    )
    assert d2["device_name"] == "Windows · Chrome"
    bob_pass = db_mod.get_guest_pass_by_id(bob_pass["id"])
    assert bob_pass["activation_status"] == "full"  # 2 of 2 devices (quota reached)
    assert bob_pass["device_count"] == 2

    time.sleep(0.01)

    # 10. LRU Eviction: Register Device 3 (MacBook Safari), d1 should be evicted automatically
    d3 = db_mod.register_guest_device(
        bob_pass["id"],
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15",
        ip="172.16.0.1",
    )
    assert d3["device_name"] == "macOS · Safari"
    bob_pass = db_mod.get_guest_pass_by_id(bob_pass["id"])
    assert bob_pass["device_count"] == 2  # Still 2
    assert bob_pass["activation_status"] == "full"

    # d1 should be gone from DB
    assert db_mod.get_device_by_token(d1["device_token"]) is None
    # d2 and d3 should still exist
    assert db_mod.get_device_by_token(d2["device_token"]) is not None
    assert db_mod.get_device_by_token(d3["device_token"]) is not None

    # 11. Delete single device (curator kicks d2)
    assert db_mod.delete_guest_device(d2["id"], pass_id=bob_pass["id"]) is True
    bob_pass = db_mod.get_guest_pass_by_id(bob_pass["id"])
    assert bob_pass["device_count"] == 1
    assert bob_pass["activation_status"] == "active"

    # 12. Reset token invalidates all devices
    bob_reset = db_mod.update_guest_pass(bob_pass["id"], reset_token=True)
    assert bob_reset is not None
    assert bob_reset["device_count"] == 0
    assert bob_reset["activation_status"] == "pending"
    assert db_mod.get_device_by_token(d3["device_token"]) is None

    # 13. Delete pass cleans up devices, favorites and reading progress
    guest_uid = f"guest:{bob_pass['id']}"
    db_mod.set_user_favorite(guest_uid, "jm", "12345", favorite=True)
    db_mod.set_user_progress(guest_uid, "jm", "12345", 5, 20)
    assert len(db_mod.get_user_favorites(guest_uid)) == 1
    assert db_mod.get_user_progress(guest_uid, "jm", "12345") is not None

    db_mod.delete_guest_pass(bob_pass["id"])
    assert len(db_mod.get_user_favorites(guest_uid)) == 0
    assert db_mod.get_user_progress(guest_uid, "jm", "12345") is None

    # 14. Eviction Cooling Lock: 5 min > 3 evictions triggers lock
    from app.abuse import check_guest_rate_limit, clear_cooling_lock, is_eviction_cooling_locked
    from app.gate import get_guest_hide_new_comics, set_guest_hide_new_comics

    p_test = db_mod.create_guest_pass(username="Eve", max_devices=1)
    pid = p_test["id"]
    clear_cooling_lock(pid)

    # Initial device (1 of 1)
    db_mod.register_guest_device(pid, user_agent="dev0")
    # Eviction 1
    db_mod.register_guest_device(pid, user_agent="dev1")
    assert not is_eviction_cooling_locked(pid)
    # Eviction 2
    db_mod.register_guest_device(pid, user_agent="dev2")
    assert not is_eviction_cooling_locked(pid)
    # Eviction 3
    db_mod.register_guest_device(pid, user_agent="dev3")
    assert not is_eviction_cooling_locked(pid)
    # Eviction 4 (> 3) triggers cooling lock
    db_mod.register_guest_device(pid, user_agent="dev4")
    assert is_eviction_cooling_locked(pid)

    # Subsequent eviction attempt is blocked while locked
    try:
        db_mod.register_guest_device(pid, user_agent="dev5_attacker")
        assert False, "Should have been blocked by cooling lock"
    except ValueError as exc:
        assert "频繁" in str(exc) or "安全保护锁定" in str(exc)

    # Pass status reflects cooling lock
    p_info = db_mod.get_guest_pass_by_id(pid)
    assert p_info["is_cooling_locked"] is True

    # Reset token clears cooling lock
    db_mod.update_guest_pass(pid, reset_token=True)
    assert not is_eviction_cooling_locked(pid)
    p_info = db_mod.get_guest_pass_by_id(pid)
    assert p_info["is_cooling_locked"] is False

    # 15. Guest Rate Limiting: 100 burst + refill
    assert check_guest_rate_limit(pid) is True
    # Consume remaining 99 tokens
    for _ in range(99):
        assert check_guest_rate_limit(pid) is True
    # 101st request exceeds burst capacity
    assert check_guest_rate_limit(pid) is False
    p_info = db_mod.get_guest_pass_by_id(pid)
    assert p_info["is_rate_limited"] is True

    # 16. Guest Privacy Settings
    orig_privacy = get_guest_hide_new_comics()
    set_guest_hide_new_comics(True)
    assert get_guest_hide_new_comics() is True
    set_guest_hide_new_comics(False)
    assert get_guest_hide_new_comics() is False
    set_guest_hide_new_comics(orig_privacy)

    db_mod.delete_guest_pass(pid)

    # 17. Client IP truncation in get_client_ip
    from app.auth import get_client_ip, get_user_context
    from unittest.mock import MagicMock

    req_long_ip = MagicMock()
    req_long_ip.headers.get = lambda k, default="": "192.168.1.1" + "a" * 100 if k.lower() == "x-forwarded-for" else ""
    client_ip = get_client_ip(req_long_ip)
    assert len(client_ip) <= 45
    assert client_ip.startswith("192.168.1.1")

    # 18. Concurrent Device Registration Race Prevention
    from concurrent.futures import ThreadPoolExecutor
    p_race = db_mod.create_guest_pass(username="RaceUser", max_devices=2)
    race_pid = p_race["id"]

    def _reg(idx: int):
        try:
            return db_mod.register_guest_device(race_pid, user_agent=f"agent_{idx}")
        except ValueError:
            return None

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(_reg, i) for i in range(5)]
        results = [f.result() for f in futures]

    race_pass = db_mod.get_guest_pass_by_id(race_pid)
    assert race_pass["device_count"] <= 2, f"Expected <= 2 devices, got {race_pass['device_count']}"
    assert len(race_pass["devices"]) <= 2

    # 19. Same-device Re-login Reuses Existing Device Token
    from app.main import auth_login
    from app.models import LoginRequest
    from fastapi import Response
    import app.auth as auth_mod

    auth_mod.AUTH_SECRET = "curator-test-secret"
    p_relogin = db_mod.create_guest_pass(username="ReloginUser", max_devices=2, pin="1234")
    relogin_token = p_relogin["token"]

    req_login1 = MagicMock()
    req_login1.headers.get = lambda k, default="": "Mozilla/5.0 (iPhone) Safari" if k.lower() == "user-agent" else ""
    req_login1.cookies.get = lambda k, default="": ""
    req_login1.client.host = "127.0.0.1"

    resp1 = Response()
    res1 = auth_login(LoginRequest(secret=relogin_token, pin="1234"), req_login1, resp1)
    dev1_token = res1.device_token
    assert dev1_token

    # Re-login with the same device cookie
    req_login2 = MagicMock()
    req_login2.headers.get = lambda k, default="": "Mozilla/5.0 (iPhone) Safari" if k.lower() == "user-agent" else ""
    req_login2.cookies.get = lambda k, default="": dev1_token if k == "comic_shelf_device" else ""
    req_login2.client.host = "127.0.0.1"

    resp2 = Response()
    res2 = auth_login(LoginRequest(secret=relogin_token), req_login2, resp2)
    assert res2.device_token == dev1_token, "Same-device re-login must reuse existing device token"
    p_after_relogin = db_mod.get_guest_pass_by_id(p_relogin["id"])
    assert p_after_relogin["device_count"] == 1, "Should not allocate extra device row on re-login"

    # 20. Direct Pass Token Access Without Device Session Is Blocked; Device Session Access Is Authorized
    req_unauth_pass = MagicMock()
    req_unauth_pass.state = type("State", (), {})()
    req_unauth_pass.url.path = "/api/library"
    req_unauth_pass.headers.get = lambda k, default="": f"Bearer {relogin_token}" if k.lower() == "authorization" else ""
    req_unauth_pass.cookies.get = lambda k, default="": ""
    req_unauth_pass.query_params.get = lambda k, default="": ""
    assert get_user_context(req_unauth_pass)[2] == "unauthorized"

    req_direct = MagicMock()
    req_direct.state = type("State", (), {})()
    req_direct.url.path = "/api/library"
    req_direct.headers.get = lambda k, default="": dev1_token if k.lower() == "x-device-token" else ""
    req_direct.cookies.get = lambda k, default="": ""
    req_direct.query_params.get = lambda k, default="": ""
    req_direct.client.host = "127.0.0.1"

    for _ in range(10):
        # Clear cached state on request to simulate separate requests
        req_direct.state = type("State", (), {})()
        ctx = get_user_context(req_direct)
        assert ctx[2] == "guest"
        assert ctx[0] == f"guest:{p_relogin['id']}"

    p_check = db_mod.get_guest_pass_by_id(p_relogin["id"])
    assert p_check["device_count"] == 1
    assert p_check["is_cooling_locked"] is False

    # 21. Reader Pass Claiming & PIN Verification
    p_pin = db_mod.create_guest_pass(username="PinUser", max_devices=2)
    assert p_pin["is_claimed"] is False
    assert p_pin["activation_status"] == "pending"
    assert db_mod.verify_guest_pass_pin(p_pin["id"], "1234") is False

    # First-time user claims with PIN "2026"
    p_claimed = db_mod.claim_guest_pass(p_pin["id"], "2026", username="PinUserCustom")
    assert p_claimed["is_claimed"] is True
    assert p_claimed["username"] == "PinUserCustom"
    assert db_mod.verify_guest_pass_pin(p_pin["id"], "2026") is True
    assert db_mod.verify_guest_pass_pin(p_pin["id"], "9999") is False

    # Cannot claim an already claimed pass
    try:
        db_mod.claim_guest_pass(p_pin["id"], "5678")
        assert False, "Should raise ValueError for claiming already claimed pass"
    except ValueError as exc:
        assert "已被认领" in str(exc)

    # 22. Anti-Group-Spam & PIN-Guarded Login
    req_stranger = MagicMock()
    req_stranger.headers.get = lambda k, default="": "Mozilla/5.0 (iPhone) Stranger" if k.lower() == "user-agent" else ""
    req_stranger.cookies.get = lambda k, default="": ""
    req_stranger.client.host = "1.2.3.4"
    resp_stranger = Response()

    # Stranger opens pass link without PIN -> returns requires_pin=True (cannot enter or evict!)
    res_stranger = auth_login(LoginRequest(secret=p_claimed["token"]), req_stranger, resp_stranger)
    assert res_stranger.ok is False
    assert res_stranger.requires_pin is True

    # Stranger tries wrong PIN -> 401
    try:
        auth_login(LoginRequest(secret=p_claimed["token"], pin="0000"), req_stranger, resp_stranger)
        assert False, "Should raise 401 for wrong PIN"
    except HTTPException as exc:
        assert exc.status_code == 401
        assert "PIN" in exc.detail

    # Legitimate owner enters correct PIN -> succeeds and registers device
    res_owner = auth_login(LoginRequest(secret=p_claimed["token"], pin="2026"), req_stranger, resp_stranger)
    assert res_owner.ok is True
    assert res_owner.device_token != ""

    # 23. Curator Reset PIN cleans all devices & restores pass to pending
    p_reset_pin = db_mod.update_guest_pass(p_claimed["id"], reset_pin=True)
    assert p_reset_pin is not None
    assert p_reset_pin["is_claimed"] is False
    assert p_reset_pin["activation_status"] == "pending"
    assert p_reset_pin["device_count"] == 0

    # 24. PIN Brute-force rate limiting: 5 wrong attempts trigger 429 lock
    p_brute = db_mod.create_guest_pass("BruteUser", max_devices=2, pin="8888")
    for _ in range(4):
        try:
            auth_login(LoginRequest(secret=p_brute["token"], pin="1111"), req_stranger, resp_stranger)
        except HTTPException as exc:
            assert exc.status_code == 401
    try:
        auth_login(LoginRequest(secret=p_brute["token"], pin="1111"), req_stranger, resp_stranger)
        assert False, "5th wrong attempt must trigger 429"
    except HTTPException as exc:
        assert exc.status_code == 429
        assert "锁定" in exc.detail

    # 25. Dual-Key Anti-DoS: Stranger IP (1.2.3.4) is locked, but Legitimate Owner IP (5.6.7.8) can still enter with correct PIN
    req_owner_device = MagicMock()
    req_owner_device.headers.get = lambda k, default="": "Mozilla/5.0 (iPhone) Owner" if k.lower() == "user-agent" else ""
    req_owner_device.cookies.get = lambda k, default="": ""
    req_owner_device.client.host = "5.6.7.8"
    resp_owner_device = Response()

    res_owner_brute = auth_login(LoginRequest(secret=p_brute["token"], pin="8888"), req_owner_device, resp_owner_device)
    assert res_owner_brute.ok is True, "Legitimate owner on different IP must not be DoS locked by stranger"

    # 26. IP-level Login Brute-Force Limiter: 10 wrong secrets from same IP trigger 429
    req_bot = MagicMock()
    req_bot.headers.get = lambda k, default="": ""
    req_bot.cookies.get = lambda k, default="": ""
    req_bot.client.host = "9.9.9.9"
    resp_bot = Response()

    for i in range(9):
        try:
            auth_login(LoginRequest(secret=f"bad-guess-{i}"), req_bot, resp_bot)
        except HTTPException as exc:
            assert exc.status_code == 401
    try:
        auth_login(LoginRequest(secret="bad-guess-10"), req_bot, resp_bot)
        assert False, "10th bad login from same IP must trigger 429"
    except HTTPException as exc:
        assert exc.status_code == 429
        assert "网络地址已临时锁定" in exc.detail

    # 27. Username XSS, Control Characters & Formula Injection Sanitization
    p_xss = db_mod.create_guest_pass(username="<script>alert(1)</script>Legit", max_devices=2)
    assert "<" not in p_xss["username"]
    assert ">" not in p_xss["username"]
    assert p_xss["username"] == "scriptalert(1)/scrip"

    p_claimed_xss = db_mod.claim_guest_pass(
        p_xss["id"],
        "2026",
        username="=cmd|' /C calc'!A0<img src=x onerror=alert(1)>Alice\r\n\x00\x08",
    )
    assert "<" not in p_claimed_xss["username"]
    assert ">" not in p_claimed_xss["username"]
    assert "\r" not in p_claimed_xss["username"]
    assert "\n" not in p_claimed_xss["username"]
    assert "\x00" not in p_claimed_xss["username"]
    assert not p_claimed_xss["username"].startswith("=")
    assert len(p_claimed_xss["username"]) <= 20
    db_mod.delete_guest_pass(p_xss["id"])

    db_mod.delete_guest_pass(race_pid)
    db_mod.delete_guest_pass(p_relogin["id"])
    db_mod.delete_guest_pass(p_pin["id"])
    db_mod.delete_guest_pass(p_brute["id"])


def test_comics_index_and_pagination():
    temp_dir = tempfile.mkdtemp()
    temp_db = Path(temp_dir) / "test_comics_index.db"
    db_mod.init_db(temp_db)

    # 1. Upsert 3 comics
    db_mod.upsert_comic_index({
        "source": "local",
        "source_id": "c1",
        "display_id": "LOC_c1",
        "title": "Alpha Comic",
        "authors_json": '["Author A"]',
        "works_json": '[]',
        "actors_json": '[]',
        "tags_json": '["同人", "全彩", "t1", "t2", "t3"]',
        "chapter_titles_json": '["第 1 话"]',
        "page_count": 20,
        "cached_pages": 20,
        "cover_count": 4,
        "cover_indices_json": '[]',
        "views": "100",
        "likes": "50",
        "uploaded_at": "2026-01-01",
        "published_at": "2026-01-01",
        "updated_at": "2026-01-01",
        "imported_at": "2026-01-01T10:00:00",
        "hidden_from_guest": 0,
        "mtime": 100.0,
    })

    db_mod.upsert_comic_index({
        "source": "local",
        "source_id": "c2",
        "display_id": "LOC_c2",
        "title": "Beta Comic",
        "authors_json": '["Author B"]',
        "works_json": '[]',
        "actors_json": '[]',
        "tags_json": '["同人"]',
        "chapter_titles_json": '[]',
        "page_count": 30,
        "cached_pages": 30,
        "cover_count": 4,
        "cover_indices_json": '[]',
        "views": "200",
        "likes": "60",
        "uploaded_at": "2026-01-02",
        "published_at": "2026-01-02",
        "updated_at": "2026-01-02",
        "imported_at": "2026-01-02T10:00:00",
        "hidden_from_guest": 0,
        "mtime": 200.0,
    })

    db_mod.upsert_comic_index({
        "source": "local",
        "source_id": "c3",
        "display_id": "LOC_c3",
        "title": "Gamma Secret",
        "authors_json": '["Author C"]',
        "works_json": '[]',
        "actors_json": '[]',
        "tags_json": '["短篇"]',
        "chapter_titles_json": '[]',
        "page_count": 15,
        "cached_pages": 15,
        "cover_count": 4,
        "cover_indices_json": '[]',
        "views": "50",
        "likes": "10",
        "uploaded_at": "2026-01-03",
        "published_at": "2026-01-03",
        "updated_at": "2026-01-03",
        "imported_at": "2026-01-03T10:00:00",
        "hidden_from_guest": 1,
        "mtime": 300.0,
    })

    # Set reading progress: c2 is reading (page 10 / 30), c3 is completed (page 15 / 15)
    db_mod.set_user_progress("u1", "local", "c2", last_page=10, total_pages=30)
    db_mod.set_user_progress("u1", "local", "c3", last_page=15, total_pages=15)
    db_mod.set_user_favorite("u1", "local", "c1", favorite=True)

    # 2. Query as curator
    items, total = db_mod.query_library_index("u1", is_curator=True, page=1, page_size=10, status="all")
    assert total == 3
    assert len(items) == 3

    # Guest query (c3 is hidden_from_guest)
    items_guest, total_guest = db_mod.query_library_index("u1", is_curator=False, page=1, page_size=10)
    assert total_guest == 2
    assert all(it["source_id"] in ("c1", "c2") for it in items_guest)

    # Status: reading -> only c2
    items_reading, total_reading = db_mod.query_library_index("u1", is_curator=True, status="reading")
    assert total_reading == 1
    assert items_reading[0]["source_id"] == "c2"

    # Status: completed -> only c3
    items_comp, total_comp = db_mod.query_library_index("u1", is_curator=True, status="completed")
    assert total_comp == 1
    assert items_comp[0]["source_id"] == "c3"

    # Status: unread -> only c1
    items_unread, total_unread = db_mod.query_library_index("u1", is_curator=True, status="unread")
    assert total_unread == 1
    assert items_unread[0]["source_id"] == "c1"

    # Tag filter
    items_tag, total_tag = db_mod.query_library_index("u1", is_curator=True, tag="全彩")
    assert total_tag == 1
    assert items_tag[0]["source_id"] == "c1"

    # Multi-tag compound filter (AND intersection: c1 has 同人 + 全彩, c2 has only 同人)
    items_multi, total_multi = db_mod.query_library_index("u1", is_curator=True, tags="同人,全彩")
    assert total_multi == 1
    assert items_multi[0]["source_id"] == "c1"

    items_multi_list, total_multi_list = db_mod.query_library_index("u1", is_curator=True, tags=["同人", "全彩"])
    assert total_multi_list == 1
    assert items_multi_list[0]["source_id"] == "c1"

    # No comic has both 同人 and 短篇
    items_multi_miss, total_multi_miss = db_mod.query_library_index("u1", is_curator=True, tags=["同人", "短篇"])
    assert total_multi_miss == 0

    # Defensive truncation: passing > 5 tags truncates to first 5 tags (6th tag '短篇' is dropped)
    items_truncated, _ = db_mod.query_library_index(
        "u1", is_curator=True, tags=["同人", "全彩", "t1", "t2", "t3", "短篇"]
    )
    assert len(items_truncated) == 1
    assert items_truncated[0]["source_id"] == "c1"

    # Keyword search
    items_search, total_search = db_mod.query_library_index("u1", is_curator=True, q="Beta")
    assert total_search == 1
    assert items_search[0]["source_id"] == "c2"

    # Chapter title search
    items_chap, total_chap = db_mod.query_library_index("u1", is_curator=True, q="第 1 话")
    assert total_chap == 1
    assert items_chap[0]["source_id"] == "c1"

    # Wildcard search with literal % and _: should not act as arbitrary match-all
    items_wildcard, total_wildcard = db_mod.query_library_index("u1", is_curator=True, q="%nonexistent%")
    assert total_wildcard == 0
    assert len(items_wildcard) == 0

    # 简繁双向归一：c1 的章节标题存的是简体「第 1 话」，用繁体「第 1 話」也必须命中。
    # 台词检索一直展开变体，书架这条以前只 LIKE 原样输入 —— 于是"元数据恰好存了哪种字形"
    # 决定搜不搜得到（真库实测「咲恋」1 本 / 「咲戀」4 本，合起来 5 本谁都不全）。
    items_trad, total_trad = db_mod.query_library_index("u1", is_curator=True, q="第 1 話")
    assert total_trad == 1 and items_trad[0]["source_id"] == "c1", f"书架关键词搜索没做简繁归一: {total_trad}"

    # Favorite filter
    items_fav, total_fav = db_mod.query_library_index("u1", is_curator=True, favorite=True)
    assert total_fav == 1
    assert items_fav[0]["source_id"] == "c1"

    # Sorting recent: c2 (in-progress) and c1 (unread) come first, c3 (completed) sinks to bottom
    items_sort, _ = db_mod.query_library_index("u1", is_curator=True, sort="recent")
    assert items_sort[-1]["source_id"] == "c3"

    # Pagination: page 1 (size 2) -> 2 items, page 2 (size 2) -> 1 item
    p1_items, p1_total = db_mod.query_library_index("u1", is_curator=True, page=1, page_size=2)
    assert p1_total == 3
    assert len(p1_items) == 2
    p2_items, p2_total = db_mod.query_library_index("u1", is_curator=True, page=2, page_size=2)
    assert p2_total == 3
    assert len(p2_items) == 1

    # Facets
    facets = db_mod.get_library_facets(is_curator=True)
    assert facets["stats"]["total_books"] == 3
    assert facets["stats"]["total_pages"] == 65
    assert facets["stats"]["cached_pages"] == 65
    tags_dict = dict(facets["top_tags"])
    assert tags_dict["同人"] == 2
    assert tags_dict["全彩"] == 1
    assert tags_dict["短篇"] == 1

    # Delete
    db_mod.delete_comic_index("local", "c3")
    assert db_mod.get_comic_index_count() == 2


if __name__ == "__main__":
    test_db_and_passes_crud()
    test_comics_index_and_pagination()
    print("Database and passes unit tests passed!")


