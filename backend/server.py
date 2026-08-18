from __future__ import annotations

import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=os.getenv("COMIC_SHELF_HOST", "127.0.0.1"),
        port=int(os.getenv("COMIC_SHELF_PORT", "8000")),
        reload=False,
        log_level="info",
    )
