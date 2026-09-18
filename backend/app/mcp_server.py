"""Model Context Protocol (MCP) Stdio Server for Paper Room (纸间).

Standard stdio transport for local agent integration (Antigravity, Claude Desktop, Cursor, etc.).
Runs a lightweight async event loop reading line-delimited JSON-RPC from stdin and emitting to stdout.
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path

# Ensure package directory is in sys.path when invoked directly
backend_root = Path(__file__).resolve().parents[2]
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from backend.app.db import init_db
from backend.app.routers.mcp import process_jsonrpc_request

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("paper_room.mcp.stdio")


async def run_stdio_server() -> None:
    """Reads JSON-RPC 2.0 messages from stdin line by line and writes responses to stdout."""
    # Ensure database is initialized
    init_db()

    logger.info("Paper Room MCP stdio server started, listening on stdin...")

    loop = asyncio.get_running_loop()
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)

    while True:
        try:
            line_bytes = await reader.readline()
            if not line_bytes:
                break

            line_str = line_bytes.decode("utf-8").strip()
            if not line_str:
                continue

            try:
                req_data = json.loads(line_str)
            except json.JSONDecodeError as err:
                err_resp = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": f"Parse error: {err}"},
                }
                sys.stdout.write(json.dumps(err_resp, ensure_ascii=False) + "\n")
                sys.stdout.flush()
                continue

            resp_data = await process_jsonrpc_request(req_data)
            if resp_data is not None:
                sys.stdout.write(json.dumps(resp_data, ensure_ascii=False) + "\n")
                sys.stdout.flush()

        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.exception("Unexpected error in stdio loop: %s", exc)


def main() -> None:
    try:
        asyncio.run(run_stdio_server())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
