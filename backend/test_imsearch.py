import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.imsearch import check_imsearch_status, parse_imsearch_path, search_imsearch


def test_parse_imsearch_path():
    # Cover image path
    res = parse_imsearch_path("/app/data/library/jm/1242163/covers/001.jpg")
    assert res == ("jm", "1242163", 1, True)

    res_webp = parse_imsearch_path("/app/data/library/jm/1242163/covers/001.webp")
    assert res_webp == ("jm", "1242163", 1, True)

    # Page image path
    res = parse_imsearch_path("/app/data/library/jm/1242163/pages/00005.webp")
    assert res == ("jm", "1242163", 5, False)

    # Thumbnail image path
    res = parse_imsearch_path("/app/data/library/jm/1242163/thumbs/00005.jpg")
    assert res == ("jm", "1242163", 5, False)

    # Multi-chapter page image path
    res = parse_imsearch_path("/app/data/library/jm/1242163/pages/chapter_1/00012.webp")
    assert res == ("jm", "1242163", 12, False)

    # Invalid path
    res = parse_imsearch_path("/some/other/path/image.jpg")
    assert res is None


def test_check_imsearch_status():
    with patch("app.imsearch._opener.open") as mock_open:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_open.return_value.__enter__.return_value = mock_resp

        status = check_imsearch_status("http://localhost:8765")
        assert status["available"] is True

        mock_open.side_effect = Exception("Connection refused")
        status = check_imsearch_status("http://localhost:8765")
        assert status["available"] is False


def test_search_imsearch():
    with patch("app.imsearch._opener.open") as mock_open:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps(
            {
                "time": 25,
                "result": [
                    [94.0, "backend/data/library/jm/1242163/pages/00005.webp"],
                    [82.0, "backend/data/library/jm/1242163/covers/001.jpg"],
                ],
            }
        ).encode("utf-8")
        mock_open.return_value.__enter__.return_value = mock_resp

        results = search_imsearch(b"fake-image-bytes", base_url="http://localhost:8765")
        assert len(results) == 2
        assert results[0].source == "jm"
        assert results[0].source_id == "1242163"
        assert results[0].page_index == 5
        assert results[0].is_cover is False
        assert results[0].score == 0.94


def test_fastapi_endpoints():
    from app.main import image_search, image_search_status

    with patch("app.main.check_imsearch_status") as mock_status:
        mock_status.return_value = {"available": True, "url": "http://localhost:8765"}
        res = image_search_status()
        assert res.available is True
        assert res.url == "http://localhost:8765"

    with patch("app.main.search_imsearch") as mock_search:
        from app.models import ImageSearchItem

        mock_search.return_value = [
            ImageSearchItem(
                source="jm", source_id="1242163", page_index=5, is_cover=False, score=0.94
            )
        ]
        mock_upload = MagicMock()
        mock_upload.filename = "test.jpg"
        mock_upload.read = AsyncMock(return_value=b"fake-bytes")

        mock_req = MagicMock()
        mock_req.headers.get = lambda k, default="": ""
        mock_req.cookies.get = lambda k, default="": ""
        mock_req.query_params.get = lambda k, default="": ""

        res = asyncio.run(image_search(mock_req, mock_upload))
        assert len(res) == 1
        assert res[0].page_index == 5
        assert res[0].score == 0.94


if __name__ == "__main__":
    test_parse_imsearch_path()
    test_check_imsearch_status()
    test_search_imsearch()
    test_fastapi_endpoints()
    print("All backend imsearch tests passed!")
