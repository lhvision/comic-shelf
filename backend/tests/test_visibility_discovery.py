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
        assert items[0].url == "https://picawang.com/comic/6aa41d3bf7e21a74faf94e42"
        # Verify required ct parameter is passed to prevent 400 validation error
        assert captured_params.get("tt") == "D7"
        assert captured_params.get("ct") == "VC"
    finally:
        provider._request = original_request


def test_discovery_ranking_router():
    from app.routers.library import discovery_ranking
    from app.providers import get_provider

    provider = get_provider("picacg")
    mock_data = {
        "code": 200,
        "message": "success",
        "data": {
            "comics": [
                {
                    "_id": "6aa41d3bf7e21a74faf94e42",
                    "title": "测试哔咔路由作品",
                    "author": "测试画师",
                    "categories": ["同人"],
                    "thumb": {
                        "fileServer": "https://storage-b.picacomic.com",
                        "path": "static/sample.jpg",
                    },
                }
            ]
        },
    }
    original_req = provider._request
    provider._request = lambda method, endpoint, params=None, **kwargs: mock_data  # type: ignore[assignment]
    try:
        req = make_mock_request("/api/discovery/ranking", token="admin-secret-123")
        feed = discovery_ranking(req, source="picacg", timeframe="day", refresh=True)
        assert feed.source == "picacg"
        assert feed.timeframe == "day"
        assert len(feed.items) == 1
        assert feed.items[0].source_id == "6aa41d3bf7e21a74faf94e42"
    finally:
        provider._request = original_req


def test_legacy_discovery_cache_migration():
    import json
    legacy_file = main_mod.store.discovery_dir() / "test_legacy_migration.json"
    legacy_file.write_text(
        json.dumps({
            "source": "jm",
            "timeframe": "test_legacy_migration",
            "updated_at": "2026-09-19 12:00:00",
            "items": [],
        }),
        encoding="utf-8",
    )
    # Load via store
    feed = main_mod.store.load_discovery_feed("test_legacy_migration", source="jm")
    assert feed is not None
    assert feed.timeframe == "test_legacy_migration"
    # Verify migrated file exists and legacy file was unlinked
    new_path = main_mod.store.discovery_path("test_legacy_migration", "jm")
    assert new_path.exists()
    assert not legacy_file.exists()
    # Cleanup
    new_path.unlink(missing_ok=True)


def test_discovery_cover_router():
    from fastapi import HTTPException
    from app.routers.library import discovery_cover, _discovery_cover_cache, _discovery_cover_lock
    from app.providers import get_provider

    provider = get_provider("picacg")
    fake_img = b"\xff\xd8\xff\xe0" + b"\x00" * 32
    original_download = getattr(provider, "download_cover_by_url", None)
    provider.download_cover_by_url = lambda url: fake_img  # type: ignore[assignment]

    # Clear cache before test
    with _discovery_cover_lock:
        _discovery_cover_cache.clear()

    try:
        # 1. Guest request must be blocked
        req_guest = make_mock_request("/api/discovery/cover", token="guest-secret-456")
        try:
            discovery_cover(req_guest, source="picacg", source_id="test_pica_1", cover_url="https://storage-b.picacomic.com/static/cover.jpg")
            assert False, "Guest should not be allowed to fetch discovery cover"
        except HTTPException as exc:
            assert exc.status_code == 401

        # 2. Curator request should fetch and return MISS
        req_curator = make_mock_request("/api/discovery/cover", token="admin-secret-123")
        resp1 = discovery_cover(req_curator, source="picacg", source_id="test_pica_1", cover_url="https://storage-b.picacomic.com/static/cover.jpg")
        assert resp1.status_code == 200
        assert resp1.media_type == "image/jpeg"
        assert resp1.body == fake_img
        assert resp1.headers.get("X-Discovery-Cover-Cache") == "MISS"

        # 3. Second request should hit memory cache (HIT)
        resp2 = discovery_cover(req_curator, source="picacg", source_id="test_pica_1")
        assert resp2.status_code == 200
        assert resp2.media_type == "image/jpeg"
        assert resp2.body == fake_img
        assert resp2.headers.get("X-Discovery-Cover-Cache") == "HIT"

        # 4. Unknown item without cover_url raises 404
        try:
            discovery_cover(req_curator, source="picacg", source_id="nonexistent_id")
            assert False, "Should raise 404 for nonexistent cover"
        except HTTPException as exc:
            assert exc.status_code == 404
    finally:
        if original_download is not None:
            provider.download_cover_by_url = original_download  # type: ignore[assignment]
        with _discovery_cover_lock:
            _discovery_cover_cache.clear()


if __name__ == "__main__":
    test_visibility_filtering()
    test_discovery_models()
    test_picacg_ranking_fetch()
    test_discovery_ranking_router()
    test_legacy_discovery_cache_migration()
    test_discovery_cover_router()
    print("Visibility & Discovery unit tests passed successfully!")

