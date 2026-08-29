#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

export PATH="$HOME/.cargo/bin:$PATH"

# Auto-detect Python interpreter in order: project .venv -> parent .venv -> backend .venv -> PATH python3/python
PYTHON=""
for cand in ".venv/bin/python" "../.venv/bin/python" "backend/.venv/bin/python"; do
  if [ -x "$cand" ]; then
    PYTHON="$cand"
    break
  fi
done

if [ -z "$PYTHON" ]; then
  PYTHON="$(command -v python3 || command -v python || echo "python3")"
fi

cleanup() {
  trap - INT TERM
  [ -n "${API_PID:-}" ] && kill "$API_PID" 2>/dev/null || true
  [ -n "${WEB_PID:-}" ] && kill "$WEB_PID" 2>/dev/null || true
  [ -n "${IMSEARCH_PID:-}" ] && kill "$IMSEARCH_PID" 2>/dev/null || true
}
trap cleanup INT TERM

# 1. Start Python Backend (with auto-reload enabled in dev mode)
"$PYTHON" backend/server.py --reload &
API_PID=$!

# 2. Check and start local imsearch binary if present (optional)
IMSEARCH_BIN="$(which imsearch 2>/dev/null || echo "$HOME/.cargo/bin/imsearch")"
if [ -x "$IMSEARCH_BIN" ]; then
  IMSEARCH_DATA="backend/data/imsearch"
  mkdir -p "$IMSEARCH_DATA"
  # Initialize index if centroids.bin is not present yet
  if [ ! -f "$IMSEARCH_DATA/centroids.bin" ] && [ -d "backend/data/library" ]; then
    echo "Initializing local imsearch index in $IMSEARCH_DATA..."
    "$IMSEARCH_BIN" -c "$IMSEARCH_DATA" add backend/data/library >/dev/null 2>&1 || true
    "$IMSEARCH_BIN" -c "$IMSEARCH_DATA" train -c 512 -i 800 -m 30 >/dev/null 2>&1 || true
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
echo "Paper Room Web: http://127.0.0.1:5173"
wait
