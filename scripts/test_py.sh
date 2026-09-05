#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# Auto-detect Python interpreter in order: project .venv -> parent .venv -> backend .venv -> PATH
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

TEST_FILES=(
  "backend/check_backend.py"
  "backend/test_auth.py"
  "backend/test_incremental_update.py"
  "backend/test_visibility_discovery.py"
  "backend/test_imsearch.py"
  "backend/test_spa_fallback.py"
  "backend/test_replace_pages.py"
  "backend/test_db_and_passes.py"
  "backend/test_events.py"
  "backend/test_cover_webp.py"
)

# Support running specific tests (e.g. pnpm test:py auth) or all by default
if [ $# -gt 0 ]; then
  for arg in "$@"; do
    matched=false
    for t in "${TEST_FILES[@]}"; do
      if [[ "$t" == *"$arg"* ]]; then
        "$PYTHON" "$t"
        matched=true
      fi
    done
    if [ "$matched" = false ]; then
      echo "Error: No backend test matching '$arg' found."
      exit 1
    fi
  done
else
  for t in "${TEST_FILES[@]}"; do
    "$PYTHON" "$t"
  done
fi
