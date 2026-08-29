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
    db_mod.create_guest_pass("Bob", custom_token="unique_token_xyz")
    try:
        db_mod.create_guest_pass("Charlie", custom_token="unique_token_xyz")
        assert False, "Should raise ValueError for duplicate token"
    except ValueError as exc:
        assert "存在" in str(exc)


if __name__ == "__main__":
    test_db_and_passes_crud()
    print("Database and passes unit tests passed!")
