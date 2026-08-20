#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

PYTHON="../.venv/bin/python"
if [ ! -x "$PYTHON" ]; then
  PYTHON="python3"
fi

cleanup() {
  trap - INT TERM
  [ -n "${API_PID:-}" ] && kill "$API_PID" 2>/dev/null || true
  [ -n "${WEB_PID:-}" ] && kill "$WEB_PID" 2>/dev/null || true
}
trap cleanup INT TERM

"$PYTHON" backend/server.py &
API_PID=$!

pnpm run dev &
WEB_PID=$!

echo "Paper Room API: http://127.0.0.1:8000"
echo "Paper Room Web: https://127.0.0.1:5173 (HTTP/2 enabled)"
wait
