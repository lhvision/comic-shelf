#!/usr/bin/env bash
# 纸间 · 以图搜图本地特征库智能增量追加 / 全量重训脚本
# 默认行为（增量）：若已有 centroids.bin，仅提取新增图片特征并追加倒排索引（秒级完成，零重复计算）
# 全量重训模式：传入 --full 或 -f 参数时，重新训练 K-Means 聚类中心并重建全量倒排索引
set -euo pipefail
cd "$(dirname "$0")/.."

export PATH="$HOME/.cargo/bin:$PATH"

FORCE_FULL=false
USE_DOCKER=false

for arg in "$@"; do
  case "$arg" in
    --full|-f|--retrain)
      FORCE_FULL=true
      ;;
    --docker|-d)
      USE_DOCKER=true
      ;;
  esac
done

IMSEARCH_BIN="$(which imsearch 2>/dev/null || echo "$HOME/.cargo/bin/imsearch")"

# 若显式指定 --docker 或宿主机未安装 imsearch，尝试探测 Docker 容器环境
if [ "$USE_DOCKER" = true ] || [ ! -x "$IMSEARCH_BIN" ]; then
  DOCKER_CMD=()
  if command -v docker &>/dev/null; then
    if docker compose ps --services --status running 2>/dev/null | grep -q "^imsearch$"; then
      DOCKER_CMD=(docker compose exec -T imsearch)
    elif docker ps --filter "name=paper-room-imsearch" --filter "status=running" -q 2>/dev/null | grep -q .; then
      DOCKER_CMD=(docker exec -i paper-room-imsearch)
    fi
  fi

  if [ ${#DOCKER_CMD[@]} -gt 0 ]; then
    echo "⚡ 检测到 Docker 运行中的 imsearch 容器，将通过容器执行索引任务..."
    if [ "$FORCE_FULL" = true ]; then
      echo "=== [容器全量重训] 增量提取特征 -> 重训聚类中心 -> 重建倒排索引 ==="
      "${DOCKER_CMD[@]}" sh -c "imsearch add /app/data/library && imsearch train -c 512 -i 800 -m 30 && rm -f /root/.config/imsearch/invlists.bin && imsearch build"
    else
      echo "=== [容器增量追加] 增量提取新图特征 -> 追加倒排索引（秒级完成） ==="
      "${DOCKER_CMD[@]}" sh -c "imsearch add /app/data/library && imsearch build"
    fi
    echo "🔄 重启 imsearch 服务以加载最新索引..."
    if command -v docker &>/dev/null && docker compose version &>/dev/null; then
      docker compose restart imsearch 2>/dev/null || docker restart paper-room-imsearch 2>/dev/null || true
    else
      docker restart paper-room-imsearch 2>/dev/null || true
    fi
    echo "🎉 容器内以图搜图特征库更新完成！"
    exit 0
  fi

  if [ ! -x "$IMSEARCH_BIN" ]; then
    echo "错误: 未找到本地 imsearch 可执行文件，且未检测到运行中的 Docker 识图容器。"
    echo ""
    echo "【场景 1：Docker Compose 部署】"
    echo "  请先启动容器服务："
    echo "    docker compose up -d"
    echo "  再在终端执行容器增量索引："
    echo "    docker compose exec imsearch sh -c \"imsearch add /app/data/library && imsearch build\""
    echo "    docker compose restart imsearch"
    echo ""
    echo "【场景 2：宿主机源码运行】"
    echo "  请先编译安装 imsearch："
    echo "    cargo install --git https://github.com/lolishinshi/imsearch --locked"
    exit 1
  fi
fi

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

# 目标数据目录：优先读取环境变量 COMIC_SHELF_DATA，默认指向本地工程目录 backend/data
DATA_DIR="${COMIC_SHELF_DATA:-backend/data}"

IMSEARCH_DATA="$DATA_DIR/imsearch"
LIBRARY_DATA="$DATA_DIR/library"
QUANTIZER_FILE="$IMSEARCH_DATA/quantizer.bin"

mkdir -p "$IMSEARCH_DATA"

if [ ! -d "$LIBRARY_DATA" ]; then
  echo "提示: 尚未导入任何漫画 ($LIBRARY_DATA 不存在)，无需构建索引。"
  exit 0
fi

# 检测是否有常驻服务正在运行，若有先优雅停止以释放 SMB/文件锁
WAS_RUNNING=false
if pgrep -f "imsearch.*server" >/dev/null 2>&1; then
  WAS_RUNNING=true
  echo "⏸️ 检测到 imsearch 服务正在运行，先停止服务以释放索引文件锁..."
  pkill -f "imsearch.*server" || true
  sleep 1
  if pgrep -f "imsearch.*server" >/dev/null 2>&1; then
    pkill -9 -f "imsearch.*server" || true
  fi
fi

echo "=== 1/2 增量扫描漫画图片并提取特征点 (add) ==="
"$IMSEARCH_BIN" -c "$IMSEARCH_DATA" add "$LIBRARY_DATA"

if [ "$FORCE_FULL" = true ] || [ ! -f "$QUANTIZER_FILE" ]; then
  if [ "$FORCE_FULL" = true ]; then
    echo "=== [全量模式] 重新训练聚类量化器 (train) ==="
  else
    echo "=== [首次初始化] 首次训练聚类量化器 (train) ==="
  fi
  "$IMSEARCH_BIN" -c "$IMSEARCH_DATA" train -c 512 -i 800 -m 30

  echo "=== 重置并构建全量倒排索引 (build) ==="
  "$PYTHON" -c "import sqlite3; c=sqlite3.connect('$IMSEARCH_DATA/imsearch.db'); c.execute('UPDATE vector_stats SET indexed = 0'); c.commit(); c.close()" 2>/dev/null || true
  rm -f "$IMSEARCH_DATA/invlists.bin"
  "$IMSEARCH_BIN" -c "$IMSEARCH_DATA" build
  echo "🎉 识图特征库【全量训练与构建】完成！数据已保存在 $IMSEARCH_DATA"
else
  echo "=== 2/2 复用已有聚类中心，增量追加倒排索引 (build) ==="
  "$IMSEARCH_BIN" -c "$IMSEARCH_DATA" build
  echo "⚡ 识图特征库【增量追加】完成（耗时数秒，旧特征与聚类完全保留）！数据保存在 $IMSEARCH_DATA"
fi

if [ "$WAS_RUNNING" = true ]; then
  echo "🔄 恢复启动 imsearch 服务..."
  setsid "$IMSEARCH_BIN" -c "$IMSEARCH_DATA" server --addr "0.0.0.0:8765" </dev/null > /tmp/imsearch.log 2>&1 &
  sleep 1
fi
