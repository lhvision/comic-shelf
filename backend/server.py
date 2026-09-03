import argparse
import logging
import os

from pathlib import Path

import uvicorn


class QuietAccessLogFilter(logging.Filter):
    """Filter out noisy 200 OK access logs for high-frequency health probes and status checks."""

    QUIET_PATHS = ("/api/health", "/api/search/image/status")

    def filter(self, record: logging.LogRecord) -> bool:
        if record.args and len(record.args) >= 5:
            try:
                # record.args: (client_addr, method, full_path, http_version, status_code)
                path = str(record.args[2]).split("?")[0]
                status_code = int(record.args[4])
                if path in self.QUIET_PATHS and status_code in (200, 304):
                    return False
            except (IndexError, ValueError, TypeError):
                pass
        return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Paper Room (纸间) Server")
    parser.add_argument("--host", default=os.getenv("COMIC_SHELF_HOST", "127.0.0.1"), help="Host to bind")
    parser.add_argument("--port", type=int, default=int(os.getenv("COMIC_SHELF_PORT", "8000")), help="Port to bind")
    parser.add_argument("--reload", action="store_true", default=os.getenv("COMIC_SHELF_RELOAD", "").lower() in {"1", "true", "yes"}, help="Auto-reload on code change")
    parser.add_argument("--workers", type=int, default=int(os.getenv("COMIC_SHELF_WORKERS", "1")), help="Number of worker processes")
    args = parser.parse_args()

    access_log_env = os.getenv("COMIC_SHELF_ACCESS_LOG", "true").lower()
    enable_access_log = access_log_env not in {"0", "false", "no", "off"}

    log_config = uvicorn.config.LOGGING_CONFIG.copy()
    if enable_access_log:
        log_config["filters"] = {
            "quiet_probe": {
                "()": QuietAccessLogFilter,
            }
        }
        if "access" in log_config.get("handlers", {}):
            handlers_access = log_config["handlers"]["access"]
            handlers_access["filters"] = handlers_access.get("filters", []) + ["quiet_probe"]

    app_dir = Path(__file__).resolve().parent / "app"
    reload_dirs = [str(app_dir)] if args.reload else None
    reload_includes = ["*.py"] if args.reload else None
    reload_excludes = ["*.db*", "*.sqlite*", "*data/*", "*__pycache__*", "*.log*"] if args.reload else None

    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        reload_dirs=reload_dirs,
        reload_includes=reload_includes,
        reload_excludes=reload_excludes,
        workers=args.workers if not args.reload else None,
        timeout_keep_alive=30,
        timeout_graceful_shutdown=3,
        backlog=2048,
        log_level=os.getenv("COMIC_SHELF_LOG_LEVEL", "info"),
        log_config=log_config,
        access_log=enable_access_log,
    )

