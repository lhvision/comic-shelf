#!/usr/bin/env bash
# 纸间 · 以图搜图本地特征库智能增量追加 / 全量重训脚本
# 默认行为（增量）：若已有 centroids.bin，仅提取新增图片特征并追加倒排索引（秒级完成，零重复计算）
# 全量重训模式：传入 --full 或 -f 参数时，重新训练 K-Means 聚类中心并重建全量倒排索引
set -euo pipefail
cd "$(dirname "$0")/.."

export PATH="$HOME/.cargo/bin:$PATH"

FORCE_FULL=false
for arg in "$@"; do
  case "$arg" in
    --full|-f|--retrain)
      FORCE_FULL=true
      ;;
  esac
done

IMSEARCH_BIN="$(which imsearch 2>/dev/null || echo "$HOME/.cargo/bin/imsearch")"
if [ ! -x "$IMSEARCH_BIN" ]; then
  echo "错误: 未找到 imsearch 可执行文件。"
  echo "如需使用以图搜图功能，请先安装或使用 Docker 镜像:"
  echo "  cargo install --git https://github.com/lolishinshi/imsearch --locked"
  exit 1
fi

PYTHON="../.venv/bin/python"
if [ ! -x "$PYTHON" ]; then
  PYTHON="python3"
fi

DATA_DIR="backend/data"
IMSEARCH_DATA="$DATA_DIR/imsearch"
LIBRARY_DATA="$DATA_DIR/library"
CENTROIDS_FILE="$IMSEARCH_DATA/centroids.bin"

mkdir -p "$IMSEARCH_DATA"

if [ ! -d "$LIBRARY_DATA" ]; then
  echo "提示: 尚未导入任何漫画 ($LIBRARY_DATA 不存在)，无需构建索引。"
  exit 0
fi

echo "=== 1/2 增量扫描漫画图片并提取特征点 (add) ==="
"$IMSEARCH_BIN" -c "$IMSEARCH_DATA" add "$LIBRARY_DATA"

if [ "$FORCE_FULL" = true ] || [ ! -f "$CENTROIDS_FILE" ]; then
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
