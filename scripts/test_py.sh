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

# 唯一的导入根配置：backend/ 供 `app.*` 与 `tests.*`，仓库根供 `scripts.*`（测试文件不再各自改 sys.path）
export PYTHONPATH="$PWD/backend:$PWD${PYTHONPATH:+:$PYTHONPATH}"

# Auto-discover all test files in backend/tests/（静态检查已拆到 vpr check:py）
TEST_FILES=()
while IFS= read -r f; do
  [ -n "$f" ] && TEST_FILES+=("$f")
done < <(find backend/tests -maxdepth 1 -name 'test_*.py' | sort)

# 每个测试文件一个进程、一个一次性数据目录：app.config 在 import 期读取 COMIC_SHELF_DATA，
# 不重定向的话测试会写进真实书库 backend/data/（不变量 1）。
# 目录从一份已建好表的模板复制而来：应用启动时由 lifespan 调 init_db()，测试直接用 store 时没有这一步。
DATA_TEMPLATE="$(mktemp -d "${TMPDIR:-/tmp}/paper-room-test-template.XXXXXX")"
trap 'rm -rf "$DATA_TEMPLATE"' EXIT
COMIC_SHELF_DATA="$DATA_TEMPLATE" "$PYTHON" -c 'from app.db import init_db; init_db()'

run_test() {
  local data_dir status=0
  data_dir="$(mktemp -d "${TMPDIR:-/tmp}/paper-room-test.XXXXXX")"
  cp -R "$DATA_TEMPLATE/." "$data_dir"
  COMIC_SHELF_DATA="$data_dir" "$PYTHON" "$1" || status=$?
  rm -rf "$data_dir"
  return "$status"
}

# Support running specific tests (e.g. vpr test:py auth) or all by default
if [ $# -gt 0 ]; then
  for arg in "$@"; do
    matched=false
    for t in "${TEST_FILES[@]}"; do
      if [[ "$t" == *"$arg"* ]]; then
        run_test "$t"
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
    run_test "$t"
  done
fi
