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
  if [ -n "${COMIC_SHELF_DATA:-}" ] && [ -d "$COMIC_SHELF_DATA" ]; then
    IMSEARCH_DATA="$COMIC_SHELF_DATA/imsearch"
    LIBRARY_DATA="$COMIC_SHELF_DATA/library"
  elif [ -d "/mnt/nas_manga/library" ]; then
    IMSEARCH_DATA="/mnt/nas_manga/imsearch"
    LIBRARY_DATA="/mnt/nas_manga/library"
  else
    IMSEARCH_DATA="backend/data/imsearch"
    LIBRARY_DATA="backend/data/library"
  fi
  mkdir -p "$IMSEARCH_DATA"
  # Initialize index only if quantizer.bin or invlists.bin is missing
  if { [ ! -f "$IMSEARCH_DATA/quantizer.bin" ] || [ ! -f "$IMSEARCH_DATA/invlists.bin" ]; } && [ -d "$LIBRARY_DATA" ]; then
    echo "Initializing local imsearch index in $IMSEARCH_DATA..."
    "$IMSEARCH_BIN" -c "$IMSEARCH_DATA" add "$LIBRARY_DATA" >/dev/null 2>&1 || true
    if [ ! -f "$IMSEARCH_DATA/quantizer.bin" ]; then
      "$IMSEARCH_BIN" -c "$IMSEARCH_DATA" train -c 512 -i 800 -m 30 >/dev/null 2>&1 || true
    fi
    "$PYTHON" -c "import sqlite3; c=sqlite3.connect('$IMSEARCH_DATA/imsearch.db'); c.execute('UPDATE vector_stats SET indexed = 0'); c.commit(); c.close()" >/dev/null 2>&1 || true
    rm -f "$IMSEARCH_DATA/invlists.bin"
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
