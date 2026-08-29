import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.models import ComicMeta, DiscoveryFeed, DiscoveryItem
from app.storage import ComicStore
import app.auth as auth_mod
import app.main as main_mod


import app.db as db_mod


def make_mock_request(path="/api/library", token=""):
    req = MagicMock()
    req.state = type("State", (), {})()
    req.url.path = path
    headers_dict = {"authorization": f"Bearer {token}"} if token else {}
    req.headers.get = lambda k, default="": headers_dict.get(k.lower(), default)
    req.cookies.get = lambda k, default="": ""
    req.query_params.get = lambda k, default="": ""
    return req


def test_visibility_filtering():
    # Setup test store
    meta_public = ComicMeta(
        source="local",
        source_id="pub_1",
        display_id="LOC_pub_1",
        title="Public Book",
        hidden_from_guest=False,
        page_count=10,
    )
    meta_private = ComicMeta(
        source="local",
        source_id="priv_1",
        display_id="LOC_priv_1",
        title="Secret Book",
        hidden_from_guest=True,
        page_count=5,
    )

    auth_mod.AUTH_SECRET = "admin-secret-123"
    if not db_mod.get_guest_pass_by_token("guest-secret-456"):
        db_mod.create_guest_pass("VisGuest", expires_days=30, custom_token="guest-secret-456")

    # Guest request
    req_guest = make_mock_request("/api/library", token="guest-secret-456")
    assert auth_mod.is_curator(req_guest) is False

    # Curator request
    req_curator = make_mock_request("/api/library", token="admin-secret-123")
    assert auth_mod.is_curator(req_curator) is True

    # Test summary
    sum_pub = main_mod.store.summary(meta_public)
    sum_priv = main_mod.store.summary(meta_private)
    assert sum_pub.hidden_from_guest is False
    assert sum_priv.hidden_from_guest is True


def test_discovery_models():
    feed = DiscoveryFeed(
        timeframe="week",
        updated_at="2026-08-26 00:00:00",
        items=[
            DiscoveryItem(
                id="JM123456",
                source_id="123456",
                source="jm",
                title="Test Ranking Manga",
                author="Artist",
                category="Single",
                in_library=False,
            )
        ],
    )
    assert len(feed.items) == 1
    assert feed.items[0].in_library is False


if __name__ == "__main__":
    test_visibility_filtering()
    test_discovery_models()
    print("Visibility & Discovery unit tests passed successfully!")
