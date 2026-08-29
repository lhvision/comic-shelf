#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

PYTHON=""
for cand in ".venv/bin/python" "../.venv/bin/python" "backend/.venv/bin/python"; do
  if [ -x "$cand" ]; then
    PYTHON="$cand"
    break
  fi
done

PYTHON="${PYTHON:-$(command -v python3 || echo "python3")}"

exec "$PYTHON" backend/server.py "${@:---reload}"
