import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

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

    # 15. Guest Rate Limiting: 45 burst + refill
    assert check_guest_rate_limit(pid) is True
    # Consume remaining 44 tokens
    for _ in range(44):
        assert check_guest_rate_limit(pid) is True
    # 46th request exceeds burst capacity
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

    # 20. Direct Pass Token Access Does Not Churn Devices or Trigger Cooling Lock
    req_direct = MagicMock()
    req_direct.state = type("State", (), {})()
    req_direct.url.path = "/api/library"
    req_direct.headers.get = lambda k, default="": f"Bearer {relogin_token}" if k.lower() == "authorization" else ""
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

    db_mod.delete_guest_pass(race_pid)
    db_mod.delete_guest_pass(p_relogin["id"])
    db_mod.delete_guest_pass(p_pin["id"])
    db_mod.delete_guest_pass(p_brute["id"])


if __name__ == "__main__":
    test_db_and_passes_crud()
    print("Database and passes unit tests passed!")

