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

get_port_pids() {
  local port="$1"
  lsof -ti ":$port" 2>/dev/null || fuser "$port/tcp" 2>/dev/null || true
}

check_and_free_port() {
  local port="$1"
  local match_pattern="${2:-backend/server\.py|comic-shelf|uvicorn}"
  local pids
  pids=$(get_port_pids "$port")
  [ -z "$pids" ] && return 0

  local zombie_pids=()
  local foreign_pids=()

  for p in $pids; do
    if [ -r "/proc/$p/cmdline" ] && grep -E -q "$match_pattern" "/proc/$p/cmdline" 2>/dev/null; then
      zombie_pids+=("$p")
    else
      foreign_pids+=("$p")
    fi
  done

  # Safety gate: If any foreign process is on this port, never touch it
  if [ ${#foreign_pids[@]} -gt 0 ]; then
    echo "❌ 端口 $port 已被其他外部进程占用 (PID: ${foreign_pids[*]}), 请先排查释放后重试。" >&2
    exit 1
  fi

  if [ ${#zombie_pids[@]} -gt 0 ]; then
    echo "⚠️  检测到端口 $port 被历史残留进程占用 (PID: ${zombie_pids[*]}), 正在平滑自愈回收..."
    # Phase 1: Graceful SIGTERM with up to 1 second wait
    for p in "${zombie_pids[@]}"; do
      kill -TERM "$p" 2>/dev/null || true
    done

    for _ in {1..10}; do
      local any_alive=0
      for p in "${zombie_pids[@]}"; do
        if kill -0 "$p" 2>/dev/null; then
          any_alive=1
          break
        fi
      done
      [ "$any_alive" -eq 0 ] && break
      sleep 0.1
    done

    # Phase 2: Forceful SIGKILL fallback if still alive
    for p in "${zombie_pids[@]}"; do
      if kill -0 "$p" 2>/dev/null; then
        kill -9 "$p" 2>/dev/null || true
      fi
    done

    sleep 0.2
    pids=$(get_port_pids "$port")
    if [ -n "$pids" ]; then
      echo "❌ 端口 $port 回收失败，仍被占用: $pids" >&2
      exit 1
    fi
    echo "✅ 端口 $port 已成功平滑回收。"
  fi
}

# Pre-flight ports self-healing check
check_and_free_port 8000 "backend/server\.py|comic-shelf|uvicorn"
check_and_free_port 5173 "vite|comic-shelf"
check_and_free_port 8765 "imsearch"

CLEANED_UP=0
API_PID=""
WEB_PID=""
IMSEARCH_PID=""

cleanup() {
  if [ "$CLEANED_UP" -eq 1 ]; then
    return
  fi
  CLEANED_UP=1
  trap - EXIT INT TERM HUP
  echo ""
  echo "正在停止 Paper Room 纸间服务..."

  local target_pids=()
  [ -n "${API_PID:-}" ] && target_pids+=("$API_PID")
  [ -n "${WEB_PID:-}" ] && target_pids+=("$WEB_PID")
  [ -n "${IMSEARCH_PID:-}" ] && target_pids+=("$IMSEARCH_PID")

  # 1. Send SIGTERM to process trees
  for pid in "${target_pids[@]}"; do
    if kill -0 "$pid" 2>/dev/null; then
      pkill -P "$pid" 2>/dev/null || true
      kill "$pid" 2>/dev/null || true
    fi
  done

  # 2. Wait up to 2 seconds for graceful shutdown
  for _ in {1..20}; do
    local any_alive=0
    for pid in "${target_pids[@]}"; do
      if kill -0 "$pid" 2>/dev/null; then
        any_alive=1
        break
      fi
    done
    [ "$any_alive" -eq 0 ] && break
    sleep 0.1
  done

  # 3. Force kill any remaining processes
  for pid in "${target_pids[@]}"; do
    if kill -0 "$pid" 2>/dev/null; then
      pkill -9 -P "$pid" 2>/dev/null || true
      kill -9 "$pid" 2>/dev/null || true
    fi
  done

  # 4. Final sweep on port 8000
  local stale_pids
  stale_pids=$(get_port_pids 8000)
  if [ -n "$stale_pids" ]; then
    for p in $stale_pids; do
      if [ -r "/proc/$p/cmdline" ] && grep -E -q "backend/server\.py|comic-shelf|uvicorn" "/proc/$p/cmdline" 2>/dev/null; then
        kill -9 "$p" 2>/dev/null || true
      fi
    done
  fi

  # 5. Final sweep on port 5173
  local stale_web_pids
  stale_web_pids=$(get_port_pids 5173)
  if [ -n "$stale_web_pids" ]; then
    for p in $stale_web_pids; do
      if [ -r "/proc/$p/cmdline" ] && grep -E -q "vite|comic-shelf" "/proc/$p/cmdline" 2>/dev/null; then
        kill -9 "$p" 2>/dev/null || true
      fi
    done
  fi

  # 6. Final sweep on port 8765
  local stale_imsearch_pids
  stale_imsearch_pids=$(get_port_pids 8765)
  if [ -n "$stale_imsearch_pids" ]; then
    for p in $stale_imsearch_pids; do
      if [ -r "/proc/$p/cmdline" ] && grep -E -q "imsearch" "/proc/$p/cmdline" 2>/dev/null; then
        kill -9 "$p" 2>/dev/null || true
      fi
    done
  fi

  echo "Paper Room 服务已安全退出。"
}
trap cleanup EXIT INT TERM HUP

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

  # Check if imsearch is already running on port 8765
  IMSEARCH_EXISTING_PIDS=$(get_port_pids 8765)
  if [ -n "$IMSEARCH_EXISTING_PIDS" ]; then
    IMSEARCH_PID="$(echo "$IMSEARCH_EXISTING_PIDS" | head -n 1)"
    echo "Imsearch Sidecar: 已在运行中 (PID: $IMSEARCH_PID, http://127.0.0.1:8765)"
  else
    "$IMSEARCH_BIN" -c "$IMSEARCH_DATA" server --addr 127.0.0.1:8765 --nprobe 32 --count 20 &
    IMSEARCH_PID=$!
    echo "Imsearch Sidecar: http://127.0.0.1:8765 (data: $IMSEARCH_DATA)"
  fi
fi

# 3. Start Frontend Web
pnpm run dev &
WEB_PID=$!

echo "Paper Room API: http://127.0.0.1:8000"
echo "Paper Room Web: http://127.0.0.1:5173"
wait
