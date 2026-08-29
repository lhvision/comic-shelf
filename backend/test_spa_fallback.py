"""Unit test for SPAStaticFiles fallback and file extension filtering."""

import asyncio
import tempfile
from pathlib import Path
from fastapi import FastAPI
from starlette.staticfiles import StaticFiles
from starlette.exceptions import HTTPException


def create_test_spa_app(dist_dir: Path) -> FastAPI:
    import mimetypes

    mimetypes.add_type("application/manifest+json", ".webmanifest")

    class SPAStaticFiles(StaticFiles):
        """SPA-aware static file handler: falls back to index.html for client routes on 404."""

        async def get_response(self, path: str, scope):
            try:
                response = await super().get_response(path, scope)
            except HTTPException as ex:
                if ex.status_code == 404:
                    filename = Path(path).name
                    is_file_request = "." in filename and not filename.startswith(".")
                    if not is_file_request:
                        response = await super().get_response("index.html", scope)
                        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
                        return response
                raise

            clean_path = path.strip("/")
            if clean_path in ("", "index.html", "sw.js", "registerSW.js", "manifest.webmanifest"):
                response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            elif clean_path.startswith("assets/"):
                response.headers["Cache-Control"] = "public, max-age=31536000, immutable"

            return response

    app = FastAPI()

    @app.get("/api/ping")
    def ping():
        return {"pong": True}

    app.mount("/", SPAStaticFiles(directory=str(dist_dir), html=True), name="spa")
    return app


async def run_request_with_headers(app: FastAPI, path: str):
    status_code = 0
    headers = {}

    async def send(msg):
        nonlocal status_code, headers
        if msg["type"] == "http.response.start":
            status_code = msg["status"]
            headers = {k.decode().lower(): v.decode() for k, v in msg.get("headers", [])}

    scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "headers": [],
        "query_string": b"",
    }
    await app(scope, None, send)
    return status_code, headers


async def run_request(app: FastAPI, path: str) -> int:
    status_code, _ = await run_request_with_headers(app, path)
    return status_code


async def test_spa_fallback():
    with tempfile.TemporaryDirectory() as tmpdir:
        dist = Path(tmpdir)
        (dist / "index.html").write_text("<!DOCTYPE html><html><body>SPA</body></html>")
        assets = dist / "assets"
        assets.mkdir()
        (assets / "app.js").write_text("console.log('app');")

        app = create_test_spa_app(dist)

        # 1. API routes should not be intercepted by SPA
        assert await run_request(app, "/api/ping") == 200, "API route failed"

        # 2. Existing static files should be served directly
        assert await run_request(app, "/index.html") == 200, "Existing index.html failed"
        assert await run_request(app, "/assets/app.js") == 200, "Existing app.js failed"

        # 3. Client routes should fall back to index.html (status 200)
        assert await run_request(app, "/") == 200, "Root path failed"
        assert await run_request(app, "/discovery") == 200, "/discovery route failed"
        assert await run_request(app, "/comic/jm/523607") == 200, "/comic/:source/:id failed"
        assert await run_request(app, "/comic/jm/523607/chapter/c1") == 200, "Chapter route failed"

        # 4. Missing static assets with extensions should return 404 (not HTML)
        assert await run_request(app, "/assets/missing.js") == 404, "Missing .js should 404"
        assert await run_request(app, "/missing.png") == 404, "Missing .png should 404"
        assert await run_request(app, "/missing.PNG") == 404, "Missing uppercase .PNG should 404"
        assert await run_request(app, "/manifest.json") == 404, "Missing .json should 404"
        assert await run_request(app, "/fonts/icon.woff2") == 404, "Missing .woff2 should 404"

        # 5. PWA deployment requirements: Cache-Control and MIME types
        (dist / "sw.js").write_text("/* sw */")
        (dist / "manifest.webmanifest").write_text("{}")

        code, headers = await run_request_with_headers(app, "/sw.js")
        assert code == 200 and "no-cache" in headers.get("cache-control", ""), "sw.js cache-control failed"

        code, headers = await run_request_with_headers(app, "/manifest.webmanifest")
        assert code == 200 and "no-cache" in headers.get("cache-control", ""), "manifest cache-control failed"
        assert "application/manifest+json" in headers.get("content-type", ""), "manifest content-type failed"

        code, headers = await run_request_with_headers(app, "/assets/app.js")
        assert code == 200 and "immutable" in headers.get("cache-control", ""), "assets cache-control failed"

        code, headers = await run_request_with_headers(app, "/discovery")
        assert code == 200 and "no-cache" in headers.get("cache-control", ""), "SPA fallback cache-control failed"

        print("All SPAStaticFiles fallback unit tests passed successfully!")


if __name__ == "__main__":
    asyncio.run(test_spa_fallback())
