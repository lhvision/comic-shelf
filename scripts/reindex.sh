#!/usr/bin/env bash
# 纸间 · 以图搜图本地特征库训练与增量索引脚本
# 该脚本会自动扫描 backend/data/library 下的全部漫画图片，提取 ORB 特征点并训练/构建索引
# 所有数据均存储在 backend/data/imsearch 下，随 data 目录一同持久化与迁移
set -euo pipefail
cd "$(dirname "$0")/.."

export PATH="$HOME/.cargo/bin:$PATH"

IMSEARCH_BIN="$(which imsearch 2>/dev/null || echo "$HOME/.cargo/bin/imsearch")"
if [ ! -x "$IMSEARCH_BIN" ]; then
  echo "错误: 未找到 imsearch 可执行文件。"
  echo "如需使用以图搜图功能，请先安装或使用 Docker 镜像:"
  echo "  cargo install --git https://github.com/lolishinshi/imsearch --locked"
  exit 1
fi

DATA_DIR="backend/data"
IMSEARCH_DATA="$DATA_DIR/imsearch"
LIBRARY_DATA="$DATA_DIR/library"

mkdir -p "$IMSEARCH_DATA"

if [ ! -d "$LIBRARY_DATA" ]; then
  echo "提示: 尚未导入任何漫画 ($LIBRARY_DATA 不存在)，无需构建索引。"
  exit 0
fi

echo "=== 1/3 扫描漫画图片并提取特征点 ==="
"$IMSEARCH_BIN" -c "$IMSEARCH_DATA" add "$LIBRARY_DATA"

echo "=== 2/3 训练聚类量化器 (centers=2048) ==="
"$IMSEARCH_BIN" -c "$IMSEARCH_DATA" train -c 2048 -i 400

echo "=== 3/3 构建/更新倒排索引 ==="
"$IMSEARCH_BIN" -c "$IMSEARCH_DATA" build

echo "🎉 识图特征库训练与索引构建完成！数据已保存在 $IMSEARCH_DATA"
