#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

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

check_and_free_port 8000 "backend/server\.py|comic-shelf|uvicorn"

PYTHON=""
for cand in ".venv/bin/python" "../.venv/bin/python" "backend/.venv/bin/python"; do
  if [ -x "$cand" ]; then
    PYTHON="$cand"
    break
  fi
done

PYTHON="${PYTHON:-$(command -v python3 || echo "python3")}"

exec "$PYTHON" backend/server.py "${@:---reload}"
