#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

export PATH="$HOME/.cargo/bin:$PATH"

PYTHON="../.venv/bin/python"
if [ ! -x "$PYTHON" ]; then
  PYTHON="python3"
fi

cleanup() {
  trap - INT TERM
  [ -n "${API_PID:-}" ] && kill "$API_PID" 2>/dev/null || true
  [ -n "${WEB_PID:-}" ] && kill "$WEB_PID" 2>/dev/null || true
  [ -n "${IMSEARCH_PID:-}" ] && kill "$IMSEARCH_PID" 2>/dev/null || true
}
trap cleanup INT TERM

# 1. Start Python Backend
"$PYTHON" backend/server.py &
API_PID=$!

# 2. Check and start local imsearch binary if present (optional)
IMSEARCH_BIN="$(which imsearch 2>/dev/null || echo "$HOME/.cargo/bin/imsearch")"
if [ -x "$IMSEARCH_BIN" ]; then
  IMSEARCH_DATA="backend/data/imsearch"
  mkdir -p "$IMSEARCH_DATA"
  # Initialize index if quantizer.bin is not present yet
  if [ ! -f "$IMSEARCH_DATA/quantizer.bin" ] && [ -d "backend/data/library" ]; then
    echo "Initializing local imsearch index in $IMSEARCH_DATA..."
    "$IMSEARCH_BIN" -c "$IMSEARCH_DATA" add backend/data/library >/dev/null 2>&1 || true
    "$IMSEARCH_BIN" -c "$IMSEARCH_DATA" train -c 2048 -i 400 >/dev/null 2>&1 || true
    "$IMSEARCH_BIN" -c "$IMSEARCH_DATA" build >/dev/null 2>&1 || true
  fi
  "$IMSEARCH_BIN" -c "$IMSEARCH_DATA" server --addr 127.0.0.1:8765 --nprobe 32 --count 20 &
  IMSEARCH_PID=$!
  echo "Imsearch Sidecar: http://127.0.0.1:8765 (data: $IMSEARCH_DATA)"
fi

# 3. Start Frontend Web
pnpm run dev &
WEB_PID=$!

echo "Paper Room API: http://127.0.0.1:8000"
echo "Paper Room Web: https://127.0.0.1:5173"
wait
