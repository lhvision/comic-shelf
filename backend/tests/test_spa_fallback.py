"""Unit test for SPAStaticFiles fallback and file extension filtering."""

import asyncio
import sys
import tempfile
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi import FastAPI
from app.main import SPAStaticFiles, app as main_app


def create_test_spa_app(dist_dir: Path) -> FastAPI:
    app = FastAPI()

    @app.get("/api/ping")
    def ping():
        return {"pong": True}

    app.mount("/", SPAStaticFiles(directory=str(dist_dir), html=True), name="spa")
    return app


async def run_request_with_headers(app: FastAPI, path: str):
    status_code = 0
    headers = {}
    body = b""

    async def send(msg):
        nonlocal status_code, headers, body
        if msg["type"] == "http.response.start":
            status_code = msg["status"]
            headers = {k.decode().lower(): v.decode() for k, v in msg.get("headers", [])}
        elif msg["type"] == "http.response.body":
            body += msg.get("body", b"")

    scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "headers": [],
        "query_string": b"",
    }
    await app(scope, None, send)
    return status_code, headers, body


async def run_request(app: FastAPI, path: str) -> int:
    status_code, _, _ = await run_request_with_headers(app, path)
    return status_code


async def test_spa_fallback():
    # --- Part 1: Isolated custom dist directory test using real SPAStaticFiles class ---
    with tempfile.TemporaryDirectory() as tmpdir:
        dist = Path(tmpdir)
        (dist / "index.html").write_text("<!DOCTYPE html><html><body>SPA</body></html>")
        assets = dist / "assets"
        assets.mkdir()
        (assets / "app.js").write_text("console.log('app');")

        test_app = create_test_spa_app(dist)

        # 1. API routes should not be intercepted by SPA
        assert await run_request(test_app, "/api/ping") == 200, "API route failed"

        # 2. Existing static files should be served directly
        assert await run_request(test_app, "/index.html") == 200, "Existing index.html failed"
        assert await run_request(test_app, "/assets/app.js") == 200, "Existing app.js failed"

        # 3. Client routes should fall back to index.html (status 200)
        assert await run_request(test_app, "/") == 200, "Root path failed"
        assert await run_request(test_app, "/discovery") == 200, "/discovery route failed"
        assert await run_request(test_app, "/comic/jm/547901") == 200, "/comic/:source/:id failed"
        assert await run_request(test_app, "/comic/jm/547901/chapter/c1") == 200, "Chapter route failed"

        # 4. Missing static assets with extensions should return 404 (not HTML)
        assert await run_request(test_app, "/assets/missing.js") == 404, "Missing .js should 404"
        assert await run_request(test_app, "/missing.png") == 404, "Missing .png should 404"
        assert await run_request(test_app, "/missing.PNG") == 404, "Missing uppercase .PNG should 404"
        assert await run_request(test_app, "/manifest.json") == 404, "Missing .json should 404"
        assert await run_request(test_app, "/fonts/icon.woff2") == 404, "Missing .woff2 should 404"

        # 5. PWA deployment requirements: Cache-Control and MIME types
        (dist / "sw.js").write_text("/* sw */")
        (dist / "manifest.webmanifest").write_text("{}")

        code, headers, _ = await run_request_with_headers(test_app, "/sw.js")
        assert code == 200 and "no-cache" in headers.get("cache-control", ""), "sw.js cache-control failed"

        code, headers, _ = await run_request_with_headers(test_app, "/manifest.webmanifest")
        assert code == 200 and "no-cache" in headers.get("cache-control", ""), "manifest cache-control failed"
        assert "application/manifest+json" in headers.get("content-type", ""), "manifest content-type failed"

        code, headers, _ = await run_request_with_headers(test_app, "/assets/app.js")
        assert code == 200 and "immutable" in headers.get("cache-control", ""), "assets cache-control failed"

        code, headers, _ = await run_request_with_headers(test_app, "/discovery")
        assert code == 200 and "no-cache" in headers.get("cache-control", ""), "SPA fallback cache-control failed"

    # --- Part 2: End-to-end test directly on main_app ---
    # When dist/ exists in workspace, verify main_app directly
    code, headers, body = await run_request_with_headers(main_app, "/comic/jm/547901")
    assert code == 200, f"main_app direct route refresh failed with status {code}"
    assert "text/html" in headers.get("content-type", ""), "main_app should return text/html for SPA route"
    assert b"<html" in body.lower() or b"<!doctype" in body.lower(), "main_app should return HTML document body"

    code_missing, _, _ = await run_request_with_headers(main_app, "/assets/definitely_missing_12345.js")
    assert code_missing == 404, "main_app missing asset should return 404"

    print("All SPAStaticFiles fallback unit tests passed successfully!")


if __name__ == "__main__":
    asyncio.run(test_spa_fallback())
