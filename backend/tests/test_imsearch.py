import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

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

        status = check_imsearch_status("http://localhost:8765", use_cache=False)
        assert status["available"] is True

        # Verify caching returns previous result without hitting opener again
        cached = check_imsearch_status("http://localhost:8765", use_cache=True)
        assert cached["available"] is True
        assert mock_open.call_count == 1

        mock_open.side_effect = Exception("Connection refused")
        status = check_imsearch_status("http://localhost:8765", use_cache=False)
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
    from fastapi import HTTPException
    from app.routers.search import image_search, image_search_status, store

    mock_req = MagicMock()
    mock_req.headers.get = lambda k, default="": ""
    mock_req.cookies.get = lambda k, default="": ""
    mock_req.query_params.get = lambda k, default="": ""

    with patch("app.routers.search.check_imsearch_status") as mock_status:
        mock_status.return_value = {"available": True}
        res = image_search_status()
        assert res.available is True

        # Test 503 fast-fail when sidecar is unavailable
        mock_status.return_value = {"available": False}
        mock_offline = MagicMock()
        mock_offline.close = AsyncMock()
        try:
            asyncio.run(image_search(mock_req, mock_offline))
            assert False, "Should raise HTTPException 503 when sidecar is unavailable"
        except HTTPException as exc:
            assert exc.status_code == 503

        # Re-enable mock status for remaining checks
        mock_status.return_value = {"available": True}

        # Test empty file rejection
        mock_empty = MagicMock()
        mock_empty.filename = "empty.jpg"
        mock_empty.read = AsyncMock(return_value=b"")
        mock_empty.close = AsyncMock()
        try:
            asyncio.run(image_search(mock_req, mock_empty))
            assert False, "Should raise HTTPException for empty upload"
        except HTTPException as exc:
            assert exc.status_code == 400
        assert mock_empty.close.call_count == 1

        # Test invalid format rejection
        mock_invalid = MagicMock()
        mock_invalid.filename = "bad.exe"
        mock_invalid.read = AsyncMock(return_value=b"MZ\x90\x00not-an-image")
        mock_invalid.close = AsyncMock()
        try:
            asyncio.run(image_search(mock_req, mock_invalid))
            assert False, "Should raise HTTPException for invalid image format"
        except HTTPException as exc:
            assert exc.status_code == 400
        assert mock_invalid.close.call_count == 1

        # Test oversized file rejection
        mock_oversized = MagicMock()
        mock_oversized.filename = "huge.jpg"
        mock_oversized.read = AsyncMock(return_value=b"x" * (15 * 1024 * 1024 + 10))
        mock_oversized.close = AsyncMock()
        try:
            asyncio.run(image_search(mock_req, mock_oversized))
            assert False, "Should raise HTTPException for oversized upload"
        except HTTPException as exc:
            assert exc.status_code == 413
        assert mock_oversized.close.call_count == 1

        # 端点会按书库里的 meta 过滤命中，这条断言只能对着真书跑；临时数据目录或别的机器上没有这本就跳过
        if store.load_meta("jm", "1242163") is None:
            print("  - skip image_search visibility filter: jm/1242163 is not in this library")
            return

        with patch("app.routers.search.search_imsearch") as mock_search:
            from app.models import ImageSearchItem

            mock_search.return_value = [
                ImageSearchItem(
                    source="jm", source_id="1242163", page_index=5, is_cover=False, score=0.94
                )
            ]
            mock_upload = MagicMock()
            mock_upload.filename = "test.jpg"
            mock_upload.read = AsyncMock(return_value=b"\xff\xd8\xff\xe0" + b"fake-bytes")
            mock_upload.close = AsyncMock()

            res = asyncio.run(image_search(mock_req, mock_upload))
            assert len(res) == 1
            assert res[0].page_index == 5
            assert res[0].score == 0.94
            assert mock_upload.close.call_count == 1


if __name__ == "__main__":
    test_parse_imsearch_path()
    test_check_imsearch_status()
    test_search_imsearch()
    test_fastapi_endpoints()
    print("All backend imsearch tests passed!")
