import argparse
import os

import uvicorn

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Paper Room (纸间) Server")
    parser.add_argument("--host", default=os.getenv("COMIC_SHELF_HOST", "127.0.0.1"), help="Host to bind")
    parser.add_argument("--port", type=int, default=int(os.getenv("COMIC_SHELF_PORT", "8000")), help="Port to bind")
    parser.add_argument("--reload", action="store_true", default=os.getenv("COMIC_SHELF_RELOAD", "").lower() in {"1", "true", "yes"}, help="Auto-reload on code change")
    parser.add_argument("--workers", type=int, default=int(os.getenv("COMIC_SHELF_WORKERS", "1")), help="Number of worker processes")
    args = parser.parse_args()

    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=args.workers if not args.reload else None,
        timeout_keep_alive=30,
        backlog=2048,
        log_level=os.getenv("COMIC_SHELF_LOG_LEVEL", "info"),
    )
