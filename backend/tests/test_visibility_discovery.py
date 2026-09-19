import sys
from pathlib import Path
from unittest.mock import MagicMock

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

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
        source="jm",
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
    assert feed.source == "jm"
    assert feed.items[0].in_library is False

    feed_pica = DiscoveryFeed(
        source="picacg",
        timeframe="day",
        updated_at="2026-09-19 12:00:00",
        items=[
            DiscoveryItem(
                id="pica_654321",
                source_id="654321",
                source="picacg",
                title="PicAcg Top 1",
                author="Pica Artist",
                category="Pica Cat",
                in_library=True,
            )
        ],
    )
    assert feed_pica.source == "picacg"
    assert feed_pica.items[0].in_library is True

    jm_path = main_mod.store.discovery_path("week", "jm")
    pica_path = main_mod.store.discovery_path("week", "picacg")
    assert jm_path != pica_path
    assert "jm_week.json" in str(jm_path)
    assert "picacg_week.json" in str(pica_path)


def test_picacg_ranking_fetch():
    from app.providers.picacg import PicacgProvider
    from app.routers.library import discovery_ranking

    provider = PicacgProvider()
    mock_data = {
        "code": 200,
        "message": "success",
        "data": {
            "comics": [
                {
                    "_id": "6aa41d3bf7e21a74faf94e42",
                    "title": "测试哔咔周榜作品",
                    "author": "测试画师",
                    "categories": ["同人"],
                    "thumb": {
                        "fileServer": "https://storage-b.picacomic.com",
                        "path": "tobeimg/sample.jpg",
                    },
                }
            ]
        },
    }

    original_request = provider._request
    captured_params = {}

    def mock_req(method, endpoint, params=None, **kwargs):
        captured_params.update(params or {})
        return mock_data

    provider._request = mock_req  # type: ignore[assignment]
    try:
        items = provider.fetch_ranking("week")
        assert len(items) == 1
        assert items[0].id == "picacg_6aa41d3bf7e21a74faf94e42"
        assert items[0].source == "picacg"
        assert items[0].title == "测试哔咔周榜作品"
        assert items[0].category == "同人"
        assert items[0].cover_url == "https://storage-b.picacomic.com/static/tobeimg/sample.jpg"
        # Verify required ct parameter is passed to prevent 400 validation error
        assert captured_params.get("tt") == "D7"
        assert captured_params.get("ct") == "VC"
    finally:
        provider._request = original_request


if __name__ == "__main__":
    test_visibility_filtering()
    test_discovery_models()
    test_picacg_ranking_fetch()
    print("Visibility & Discovery unit tests passed successfully!")
