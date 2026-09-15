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

CHECK_SCRIPT="backend/check_backend.py"

# Auto-discover all test files in backend/tests/
TEST_FILES=()
if [ -f "$CHECK_SCRIPT" ]; then
  TEST_FILES+=("$CHECK_SCRIPT")
fi

while IFS= read -r f; do
  [ -n "$f" ] && TEST_FILES+=("$f")
done < <(find backend/tests -maxdepth 1 -name 'test_*.py' | sort)

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
