#!/usr/bin/env bash
# 纸间 · 高性能机漫画台词 OCR 提取与伴生处理一键运维脚本
# 支持命令: status | run | sync | install | test
set -euo pipefail
cd "$(dirname "$0")/.."

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

# 自动探测 Python 解释器
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

cmd_status() {
  echo "📊 纸间 · 漫画台词 OCR 处理与索引状态"
  echo "   - 当前生效数据目录: $DATA_DIR"
  if command -v nvidia-smi >/dev/null 2>&1; then
    local gpu_info
    gpu_info="$(nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader,nounits 2>/dev/null | head -n 1 || echo "")"
    if [ -n "$gpu_info" ]; then
      echo "   - 宿主物理 GPU: 🟢 NVIDIA 检测到 ($gpu_info MiB)"
    fi
  else
    echo "   - 宿主物理 GPU: ⚪ 未检测到独立 GPU (纯 CPU 宿主机)"
  fi
  # 真实探测当前 Python 环境中 ONNXRuntime 的 ExecutionProvider
  "$PYTHON" -c "
try:
    import onnxruntime as ort
    provs = ort.get_available_providers()
    if 'CUDAExecutionProvider' in provs:
        print('   - 推理引擎加速: 🟢 ONNXRuntime CUDAExecutionProvider (GPU 加速运行中)')
    else:
        print('   - 推理引擎加速: ⚪ ONNXRuntime CPUExecutionProvider (CPU 多核模式)')
        print('     (💡 提示: 如需启用 NVIDIA GPU 加速，请安装: pip install onnxruntime-gpu)')
except ImportError:
    print('   - 推理引擎加速: ⚠️ 未安装 onnxruntime (请运行: bash scripts/ocr.sh install)')
"
  "$PYTHON" scripts/ocr_worker.py --data-dir "$DATA_DIR" --status
}

cmd_run() {
  echo "🚀 开始执行漫画台词 OCR 批量提取 (目标目录: $DATA_DIR)..."
  "$PYTHON" scripts/ocr_worker.py --data-dir "$DATA_DIR" "$@"
}

cmd_sync() {
  echo "🔄 正在同步 OCR 伴生文件至 SQLite FTS5 索引 (目标目录: $DATA_DIR)..."
  "$PYTHON" scripts/sync_ocr.py "$@"
}

cmd_install() {
  echo "📦 正在为当前环境安装 OCR 算力依赖 (scripts/requirements-ocr.txt)..."
  "$PYTHON" -m pip install -r scripts/requirements-ocr.txt
  echo "✅ 依赖安装完成！"
}

cmd_test() {
  local target_img="${1:-}"
  if [ -z "$target_img" ]; then
    # 自动探测第一张画页用于测试
    target_img="$(find "$DATA_DIR/library" -type f \( -name "*.webp" -o -name "*.jpg" -o -name "*.png" \) 2>/dev/null | head -n 1 || true)"
  fi

  if [ -z "$target_img" ] || [ ! -f "$target_img" ]; then
    echo "❌ 错误: 未指定测试画页，且在 $DATA_DIR 未找到测试图片。"
    echo "用法: bash scripts/ocr.sh test <图片路径>"
    exit 1
  fi

  echo "🧪 正在对单张测试画页运行 OCR 识别: $target_img"
  "$PYTHON" -c "
import sys
from PIL import Image
from rapidocr_onnxruntime import RapidOCR
from scripts.ocr_worker import cluster_blocks

engine = RapidOCR()
with Image.open('$target_img') as im:
    w, h = im.size

raw, elapse = engine('$target_img')
print(f'📐 图像尺寸: {w}x{h}, 推理耗时: {sum(elapse):.2f}s, 检出基础字块: {len(raw) if raw else 0} 个')

blocks = []
if raw:
    for item in raw:
        box, text, score = item
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        blocks.append({
            'text': str(text).strip(),
            'score': float(score),
            'xmin': min(xs),
            'xmax': max(xs),
            'ymin': min(ys),
            'ymax': max(ys)
        })

bubbles = cluster_blocks(blocks, w, h)
print(f'💬 气泡几何聚类后获得: {len(bubbles)} 处对白:')
for b in bubbles:
    print(f'  - [{b[\"id\"]}] {b[\"orientation\"]} (置信度: {b[\"confidence\"]}) 归一化坐标: {b[\"box\"]}')
    print(f'    对白内容: \"{b[\"text\"]}\"')
"
}

ACTION="${1:-status}"
shift || true

case "$ACTION" in
  status)
    cmd_status
    ;;
  run)
    cmd_run "$@"
    ;;
  sync)
    cmd_sync "$@"
    ;;
  install)
    cmd_install
    ;;
  test)
    cmd_test "$@"
    ;;
  *)
    echo "使用方法: $0 {status|run|sync|install|test} [参数...]"
    echo ""
    echo "  status                  - 查看书库 OCR 伴生覆盖率、硬件状态与 FTS5 统计"
    echo "  run [options]           - 批量或定向对画页提取 OCR 伴生文件 ({index}.ocr.json)"
    echo "     --workers <N>        - 并发线程数 (默认 2，推荐 2~4 充分释放多核算力)"
    echo "     --source <src>       - 限定数据源 (jm / local / picacg)"
    echo "     --id <comic_id>      - 限定单本漫画 ID"
    echo "     --page <pages>       - 限定提取特定页码 (如 --page 3 或 --page 1,3,5 或 --page 10-20)"
    echo "     --image <path>       - 直接指定单张画页图片路径进行单页处理"
    echo "     --min-score <float>  - OCR 置信度过滤阈值 (默认 0.5，过滤拟声词与背景噪点)"
    echo "     --force              - 强制重新处理已存在的伴生文件"
    echo "     --limit <N>          - 最多处理册数"
    echo "     --api-url <URL>      - 远程 NAS 纸间 API 地址 (如 http://192.168.1.100:8000)，处理后自动通知入库"
    echo "     --token <TOKEN>      - 纸间 Machine API Token"
    echo "     --sync-local         - 处理完毕后直接同步本地 SQLite 索引"
    echo "  sync [options]          - 将已存在的伴生文件全量/增量扫入 SQLite FTS5"
    echo "  install                 - 一键安装 OCR 推理必要依赖 (rapidocr_onnxruntime)"
    echo "  test [image_path]       - 针对单张画页运行测试并输出格式化气泡"
    exit 1
    ;;
esac
