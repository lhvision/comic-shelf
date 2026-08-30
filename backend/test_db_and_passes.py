import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

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
    assert bob_pass["first_used_at"] is None

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
    assert bob_pass["first_used_at"] is not None

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


if __name__ == "__main__":
    test_db_and_passes_crud()
    print("Database and passes unit tests passed!")
