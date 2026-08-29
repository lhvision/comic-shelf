#!/usr/bin/env bash
# 纸间 · 以图搜图（imsearch）宿主机/WSL2 服务一键运维脚本
# 支持命令: start | stop | restart | status | reindex | train | logs
set -euo pipefail
cd "$(dirname "$0")/.."

export PATH="$HOME/.cargo/bin:$PATH"
IMSEARCH_BIN="$(which imsearch 2>/dev/null || echo "$HOME/.cargo/bin/imsearch")"

if [ ! -x "$IMSEARCH_BIN" ]; then
  echo "❌ 错误: 未找到可执行的 imsearch 二进制文件 ($IMSEARCH_BIN)。"
  echo "请先在本地安装: cargo install --git https://github.com/lolishinshi/imsearch --locked"
  exit 1
fi

# 智能探测数据目录（优先顺序: 环境变量 COMIC_SHELF_DATA -> /mnt/nas_manga -> 本地 backend/data）
if [ -n "${COMIC_SHELF_DATA:-}" ] && [ -d "$COMIC_SHELF_DATA" ]; then
  DATA_DIR="$COMIC_SHELF_DATA"
elif [ -d "/mnt/nas_manga/library" ]; then
  DATA_DIR="/mnt/nas_manga"
elif [ -d "backend/data/library" ]; then
  DATA_DIR="backend/data"
else
  DATA_DIR="backend/data"
fi

IMSEARCH_CONF="$DATA_DIR/imsearch"
LIBRARY_DATA="$DATA_DIR/library"
LOG_FILE="/tmp/imsearch.log"
PORT=8765

# Auto-detect Python interpreter
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

mkdir -p "$IMSEARCH_CONF"

get_pid() {
  pgrep -f "imsearch.*server" || true
}

is_running() {
  local pid
  pid="$(get_pid)"
  [ -n "$pid" ]
}

cmd_start() {
  if is_running; then
    echo "⚠️ imsearch 服务已在运行中 (PID: $(get_pid))，监听端口 :$PORT"
    return 0
  fi

  echo "🚀 正在启动 imsearch 识图服务..."
  echo "   - 特征库路径: $IMSEARCH_CONF"
  echo "   - 运行日志:   $LOG_FILE"
  echo "   - 监听端口:   0.0.0.0:$PORT"

  setsid "$IMSEARCH_BIN" -c "$IMSEARCH_CONF" server --addr "0.0.0.0:$PORT" </dev/null > "$LOG_FILE" 2>&1 &
  local new_pid=$!

  # 等待启动探测
  sleep 2
  if is_running; then
    echo "✅ imsearch 服务启动成功！(PID: $(get_pid))"
    echo "   健康检查: http://127.0.0.1:$PORT/metrics"
    echo "   查看实时日志: bash scripts/imsearch.sh logs"
  else
    echo "❌ 启动失败，请查看日志:"
    tail -n 20 "$LOG_FILE"
    return 1
  fi
}

cmd_stop() {
  if ! is_running; then
    echo "ℹ️ imsearch 服务未运行。"
    return 0
  fi

  local pid
  pid="$(get_pid)"
  echo "🛑 正在停止 imsearch 服务 (PID: $pid)..."
  pkill -f "imsearch.*server" || true
  sleep 1
  if is_running; then
    pkill -9 -f "imsearch.*server" || true
  fi
  echo "✅ imsearch 服务已停止。"
}

cmd_restart() {
  cmd_stop
  sleep 1
  cmd_start
}

cmd_status() {
  if is_running; then
    local pid
    pid="$(get_pid)"
    echo "🟢 状态: 运行中 (PID: $pid)"
    echo "   - 监听端口: :$PORT"
    echo "   - 数据目录: $IMSEARCH_CONF"
    echo "   - 进程资源: $(ps -p "$pid" -o %cpu,%mem,cmd --no-headers 2>/dev/null || echo 'N/A')"
    if curl -s --noproxy "127.0.0.1,localhost" -o /dev/null -w "%{http_code}" "http://127.0.0.1:$PORT/metrics" 2>/dev/null | grep -q "200"; then
      echo "   - 健康状态: 正常 (HTTP 200 OK)"
    else
      echo "   - 健康状态: 响应异常"
    fi
    if [ -f "$IMSEARCH_CONF/quantizer.bin" ] && [ -f "$IMSEARCH_CONF/invlists.bin" ]; then
      local q_mtime i_mtime
      q_mtime=$(stat -c %Y "$IMSEARCH_CONF/quantizer.bin" 2>/dev/null || echo 0)
      i_mtime=$(stat -c %Y "$IMSEARCH_CONF/invlists.bin" 2>/dev/null || echo 0)
      if [ "$q_mtime" -gt "$((i_mtime + 10))" ]; then
        echo "   - ⚠️ 警告: quantizer.bin 比 invlists.bin 新，可能存在索引失步风险！建议执行 pnpm imsearch train"
      else
        echo "   - 索引同步: 正常（聚类模型与倒排列表已对齐）"
      fi
    fi
  else
    echo "🔴 状态: 未运行"
    echo "   启动命令: bash scripts/imsearch.sh start"
  fi
}

cmd_reindex() {
  if [ ! -d "$LIBRARY_DATA" ]; then
    echo "❌ 错误: 未找到漫画目录 ($LIBRARY_DATA)。"
    exit 1
  fi

  local was_running=false
  if is_running; then
    was_running=true
    echo "⏸️ 检测到 imsearch 服务正在运行，先停止服务以释放 SMB 索引文件锁..."
    cmd_stop
  fi

  echo "=== 1/2 扫描漫画图片并提取新增特征点 (add) ==="
  "$IMSEARCH_BIN" -c "$IMSEARCH_CONF" add "$LIBRARY_DATA"

  echo "=== 2/2 复用已有聚类模型，增量追加倒排索引 (build) ==="
  "$IMSEARCH_BIN" -c "$IMSEARCH_CONF" build

  echo "🎉 识图特征库【增量追加】完成！"

  if [ "$was_running" = true ]; then
    echo "🔄 恢复启动 imsearch 服务以热加载新索引..."
    cmd_start
  fi
}

cmd_train() {
  if [ ! -d "$LIBRARY_DATA" ]; then
    echo "❌ 错误: 未找到漫画目录 ($LIBRARY_DATA)。"
    exit 1
  fi

  local was_running=false
  if is_running; then
    was_running=true
    echo "⏸️ 检测到 imsearch 服务正在运行，先停止服务以释放 SMB 索引文件锁..."
    cmd_stop
  fi

  echo "⚠️ 即将开始【全量重新训练】（适用于聚类模型重构或首次初始化）"
  echo "=== 1/3 扫描漫画图片提取全部特征点 (add) ==="
  "$IMSEARCH_BIN" -c "$IMSEARCH_CONF" add "$LIBRARY_DATA"

  echo "=== 2/3 重新训练 512 聚类中心 (train) ==="
  "$IMSEARCH_BIN" -c "$IMSEARCH_CONF" train -c 512 -i 800 -m 30

  echo "=== 3/3 重置并构建全量倒排索引 (build) ==="
  # 重新训练量化模型后必须重置 indexed=0，确保所有特征向量与新聚类中心重新对齐构建倒排列表
  "$PYTHON" -c "import sqlite3; c=sqlite3.connect('$IMSEARCH_CONF/imsearch.db'); c.execute('UPDATE vector_stats SET indexed = 0'); c.commit(); c.close()" 2>/dev/null || true
  rm -f "$IMSEARCH_CONF/invlists.bin"
  "$IMSEARCH_BIN" -c "$IMSEARCH_CONF" build

  echo "🎉 识图特征库【全量训练与构建】完成！"

  if [ "$was_running" = true ]; then
    echo "🔄 恢复启动 imsearch 服务加载新索引..."
    cmd_start
  fi
}

cmd_logs() {
  if [ ! -f "$LOG_FILE" ]; then
    echo "ℹ️ 暂无日志文件 ($LOG_FILE)"
    exit 0
  fi
  echo "📜 正在追踪实时日志 ($LOG_FILE) - 按 Ctrl+C 退出:"
  tail -n 50 -f "$LOG_FILE"
}

ACTION="${1:-status}"
case "$ACTION" in
  start)
    cmd_start
    ;;
  stop)
    cmd_stop
    ;;
  restart)
    cmd_restart
    ;;
  status)
    cmd_status
    ;;
  reindex)
    cmd_reindex
    ;;
  train)
    cmd_train
    ;;
  logs)
    cmd_logs
    ;;
  *)
    echo "使用方法: $0 {start|stop|restart|status|reindex|train|logs}"
    echo ""
    echo "  start    - 后台启动 imsearch 识图服务 (:8765)"
    echo "  stop     - 停止运行中的 imsearch 进程"
    echo "  restart  - 重启 imsearch 服务"
    echo "  status   - 查看当前运行状态与健康度"
    echo "  reindex  - 日常增量追加新本子特征点并重建索引（秒级）"
    echo "  train    - 全量重新训练 512 聚类中心并重建索引"
    echo "  logs     - 跟踪查看实时运行日志"
    exit 1
    ;;
esac
