import sys
import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure backend package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.models import ComicMeta, FetchedComic, RemotePage, Chapter, PageRecord
from app.providers.jm import JMProvider
from app.storage import ComicStore


def create_sample_fetched(multi: bool = True) -> FetchedComic:
    if multi:
        chapters = [
            Chapter(id="101", index=1, title="第 1 話", page_count=2, start=1),
            Chapter(id="102", index=2, title="第 2 話", page_count=2, start=3),
        ]
        pages = [
            PageRecord(index=1, file="00001.webp", ext=".webp", cached=True, chapter="101"),
            PageRecord(index=2, file="00002.webp", ext=".webp", cached=True, chapter="101"),
            PageRecord(index=3, file="00001.webp", ext=".webp", cached=True, chapter="102"),
            PageRecord(index=4, file="00002.webp", ext=".webp", cached=True, chapter="102"),
        ]
        remote_pages = [
            RemotePage(index=1, url="http://img/1.webp", file="00001.webp", ext=".webp", scramble_id="220000", chapter="101"),
            RemotePage(index=2, url="http://img/2.webp", file="00002.webp", ext=".webp", scramble_id="220000", chapter="101"),
            RemotePage(index=3, url="http://img/3.webp", file="00001.webp", ext=".webp", scramble_id="220000", chapter="102"),
            RemotePage(index=4, url="http://img/4.webp", file="00002.webp", ext=".webp", scramble_id="220000", chapter="102"),
        ]
        page_count = 4
    else:
        chapters = []
        pages = [
            PageRecord(index=1, file="00001.webp", ext=".webp", cached=True, chapter=""),
            PageRecord(index=2, file="00002.webp", ext=".webp", cached=True, chapter=""),
        ]
        remote_pages = [
            RemotePage(index=1, url="http://img/1.webp", file="00001.webp", ext=".webp", scramble_id="220000", chapter=""),
            RemotePage(index=2, url="http://img/2.webp", file="00002.webp", ext=".webp", scramble_id="220000", chapter=""),
        ]
        page_count = 2

    meta = ComicMeta(
        source="jm",
        source_id="500000",
        display_id="JM500000",
        title="测试漫画",
        authors=["作者A"],
        works=[],
        actors=[],
        tags=["标签A"],
        description="",
        page_count=page_count,
        published_at="2026-01-01",
        updated_at="2026-01-01",
        views="100",
        likes="50",
        comment_count=0,
        cover_count=1,
        source_url="https://jm/album/500000",
        pages=pages,
        chapters=chapters,
        imported_at="2026-01-01T00:00:00Z",
        last_checked_at="2026-01-01T00:00:00Z",
        favorite=True,
    )
    return FetchedComic(meta=meta, remote_pages=remote_pages)


from types import SimpleNamespace


def test_incremental_fetch_unchanged():
    provider = JMProvider()
    existing = create_sample_fetched(multi=True)

    mock_client = MagicMock()
    mock_album_resp = MagicMock()
    mock_album_resp.text = "<html>album html</html>"
    mock_album_resp.url = "https://18comic.vip/album/500000"
    mock_client.get.return_value = mock_album_resp

    mock_detail = SimpleNamespace(
        name="测试漫画",
        authors=["作者A"],
        works=[],
        actors=[],
        tags=["标签A"],
        description="",
        pub_date="2026-01-01",
        update_date="2026-01-02",
        views="150",
        likes="60",
        comment_count=0,
        page_count="4",
        episode_list=[("101", "1", "第 1 話"), ("102", "2", "第 2 話")],
    )

    with patch.object(provider, "_make_html_client", return_value=mock_client), \
         patch("jmcomic.JmcomicText.analyse_jm_album_html", return_value=mock_detail):
        fetched = provider.fetch("500000", existing=existing)

        # Should only request album page, 0 photo page requests
        assert mock_client.get.call_count == 1
        assert mock_client.get.call_args[0][0] == "/album/500000"
        assert len(fetched.remote_pages) == 4
        assert len(fetched.meta.chapters) == 2
        assert fetched.meta.views == "150"
        print("  ✓ test_incremental_fetch_unchanged passed (0 photo requests)")


def test_incremental_fetch_new_chapter():
    provider = JMProvider()
    existing = create_sample_fetched(multi=True)

    mock_client = MagicMock()
    requested_urls = []

    def fake_get(url):
        requested_urls.append(url)
        resp = MagicMock()
        resp.text = "<html>html</html>"
        resp.url = f"https://18comic.vip{url}"
        return resp

    mock_client.get.side_effect = fake_get

    mock_album_detail = SimpleNamespace(
        name="测试漫画",
        authors=["作者A"],
        works=[],
        actors=[],
        tags=["标签A"],
        description="",
        pub_date="2026-01-01",
        update_date="2026-01-03",
        views="200",
        likes="80",
        comment_count=0,
        page_count="6",
        episode_list=[
            ("101", "1", "第 1 話"),
            ("102", "2", "第 2 話"),
            ("103", "3", "第 3 話"),
        ],
    )

    mock_photo_detail = MagicMock()
    mock_photo_detail.name = "第 3 話"
    mock_photo_detail.scramble_id = "220000"
    mock_photo_detail.page_arr = ["p1", "p2"]
    mock_photo_detail.data_original_0 = "https://cdn/0.webp"
    mock_photo_detail.data_original_domain = "cdn.domain"
    mock_photo_detail.get_data_original_query_params.return_value = {}

    def fake_create_image_detail(idx):
        img = MagicMock()
        img.download_url = f"https://cdn/{idx+1}.webp"
        img.img_file_suffix = ".webp"
        return img

    mock_photo_detail.create_image_detail.side_effect = fake_create_image_detail

    with patch.object(provider, "_make_html_client", return_value=mock_client), \
         patch("jmcomic.JmcomicText.analyse_jm_album_html", return_value=mock_album_detail), \
         patch("jmcomic.JmcomicText.analyse_jm_photo_html", return_value=mock_photo_detail):
        fetched = provider.fetch("500000", existing=existing)

        # Expected requests: /album/500000 and ONLY /photo/103 (101 and 102 are reused!)
        assert requested_urls == ["/album/500000", "/photo/103"]
        assert len(fetched.remote_pages) == 6
        assert len(fetched.meta.chapters) == 3
        # Check global indexes
        assert [p.index for p in fetched.remote_pages] == [1, 2, 3, 4, 5, 6]
        # Check chapter start indexes
        assert fetched.meta.chapters[0].start == 1
        assert fetched.meta.chapters[1].start == 3
        assert fetched.meta.chapters[2].start == 5
        assert fetched.meta.chapters[2].id == "103"
        assert fetched.remote_pages[4].chapter == "103"
        assert fetched.remote_pages[5].chapter == "103"
        print("  ✓ test_incremental_fetch_new_chapter passed (reused 2 chapters, fetched only 1)")


def test_storage_flat_to_chapter_migration():
    temp_dir = Path(tempfile.mkdtemp())
    try:
        store = ComicStore(root=temp_dir)
        source = "jm"
        source_id = "500000"

        # 1. Simulate existing single-chapter comic on disk
        single_fetched = create_sample_fetched(multi=False)
        store.save_fetched(single_fetched)

        # Create dummy cached page files in flat pages/ and thumbs/
        pages_dir = store.pages_dir(source, source_id)
        thumbs_dir = store.thumbs_dir(source, source_id)
        pages_dir.mkdir(parents=True, exist_ok=True)
        thumbs_dir.mkdir(parents=True, exist_ok=True)

        p1 = pages_dir / "00001.webp"
        p2 = pages_dir / "00002.webp"
        p1.write_bytes(b"dummy page 1 content")
        p2.write_bytes(b"dummy page 2 content")

        t1 = thumbs_dir / "00001.jpg"
        t2 = thumbs_dir / "00002.jpg"
        t1.write_bytes(b"dummy thumb 1")
        t2.write_bytes(b"dummy thumb 2")

        # 2. Upgrade to multi-chapter comic with 2 chapters (Ep 101 has 2 pages, Ep 102 has 2 pages)
        multi_fetched = create_sample_fetched(multi=True)
        meta = store.save_fetched(multi_fetched, refresh=True)

        # Verify physical files migrated to pages/101/ and thumbs/101/
        chap1_p1 = pages_dir / "101" / "00001.webp"
        chap1_p2 = pages_dir / "101" / "00002.webp"
        chap1_t1 = thumbs_dir / "101" / "00001.jpg"
        chap1_t2 = thumbs_dir / "101" / "00002.jpg"

        assert chap1_p1.exists(), "pages/101/00001.webp should exist after migration"
        assert chap1_p2.exists(), "pages/101/00002.webp should exist after migration"
        assert chap1_t1.exists(), "thumbs/101/00001.jpg should exist after migration"
        assert chap1_t2.exists(), "thumbs/101/00002.jpg should exist after migration"

        # Check cached status on meta.pages
        # Pages 1 & 2 (Ep 101) exist on disk -> cached=True
        # Pages 3 & 4 (Ep 102) not yet downloaded -> cached=False
        assert meta.pages[0].cached is True
        assert meta.pages[1].cached is True
        assert meta.pages[2].cached is False
        assert meta.pages[3].cached is False
        assert meta.favorite is True  # preserved

        print("  ✓ test_storage_flat_to_chapter_migration passed (migrated flat files to chapter 101)")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    print("Running incremental update backend tests...")
    test_incremental_fetch_unchanged()
    test_incremental_fetch_new_chapter()
    test_storage_flat_to_chapter_migration()
    print("All incremental update backend tests passed successfully!")
