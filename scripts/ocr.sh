#!/usr/bin/env bash
# 纸间 · 高性能机漫画台词 OCR 提取与伴生处理一键运维脚本
# 支持命令: status | run | sync | install | test | lines
#
# 算力环境两条线（**默认走 GPU**，没有卡的机器才回落 CPU，回落时脚本会说明原因）：
#   GPU（默认）   本脚本创建的项目内 .venv-ocr/，只装 pyproject.toml 的 ocr-gpu 依赖组
#   CPU（--cpu）  复用应用的 .venv，追加 ocr 依赖组
# 两条线互不干扰：GPU wheel 与 CPU wheel 共用同一个 onnxruntime 包目录，混装会静默失去 CUDA。
# 版本全部来自 uv.lock（含 opencv / numpy 等传递依赖），两台算力机装出来的是同一套。
set -euo pipefail
cd "$(dirname "$0")/.."

# 智能探测数据目录（优先顺序: 环境变量 COMIC_SHELF_DATA -> /mnt/nas_manga -> 本地 backend/data）
if [ -n "${COMIC_SHELF_DATA:-}" ] && [ -d "$COMIC_SHELF_DATA" ]; then
  DATA_DIR="$COMIC_SHELF_DATA"
elif [ -d "/mnt/nas_manga/library" ]; then
  DATA_DIR="/mnt/nas_manga"
else
  DATA_DIR="backend/data"
fi

# GPU 算力环境目录，可用 COMIC_SHELF_OCR_VENV 指到别处（如外置盘）。
# 这里把它规范成绝对路径并去掉尾斜杠：后面的守卫要拿它和 site-packages 前缀比对，
# 相对路径或 "path/" 会让比对误判（实测：先建完 venv 才在守卫处被拒，文案误导）。
OCR_VENV="${COMIC_SHELF_OCR_VENV:-$PWD/.venv-ocr}"
case "$OCR_VENV" in
  /*) ;;
  *) OCR_VENV="$PWD/$OCR_VENV" ;;
esac
while [ "${OCR_VENV%/}" != "$OCR_VENV" ]; do OCR_VENV="${OCR_VENV%/}"; done
# MODE 取值 gpu|cpu。默认走 GPU：只要 .venv-ocr 就绪就优先用它（装它本身就是 opt-in），
# 显式 --cpu 才回落。绝不让人在带卡的机器上默认烧 CPU 还浑然不觉。
MODE=""
MODE_PINNED=0

# 自动探测 Python 解释器（CPU 线，也是建 venv 的基座）
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

# 宿主有没有 NVIDIA 卡。WSL2 的 nvidia-smi 不在 PATH 里、只存在于 /usr/lib/wsl/lib，
# 只查 command -v 会把带显卡的机器误判成"纯 CPU 宿主机"（本项目踩过）。
host_gpu_smi() {
  if command -v nvidia-smi >/dev/null 2>&1; then
    echo "nvidia-smi"
  elif [ -x /usr/lib/wsl/lib/nvidia-smi ]; then
    echo "/usr/lib/wsl/lib/nvidia-smi"
  fi
}

# 选定本次跑批的算力线，并把选择理由说出来。
# 说明性文字一律走 stderr：resolve_python 是在 $( ) 里被取值用的，往 stdout 打会把
# 这句提示混进解释器路径（踩过：拼出来的"解释器"变成一整句话，命令直接挂掉）。
resolve_mode() {
  local smi
  if [ -n "$MODE" ]; then
    return 0
  fi
  if [ -x "$OCR_VENV/bin/python" ]; then
    MODE=gpu
    if [ "$MODE_PINNED" = 0 ]; then
      echo "   (自动选用 GPU 环境 $OCR_VENV；要用 CPU 请加 --cpu)" >&2
    fi
  else
    MODE=cpu
    smi="$(host_gpu_smi || true)"
    if [ -n "$smi" ]; then
      echo "   ⚠️ 检测到宿主有 NVIDIA 显卡，但 GPU 算力环境未创建，本轮按 CPU 跑。" >&2
      echo "      带卡机器请用一条命令建好（默认即走 GPU）: bash scripts/ocr.sh install" >&2
    fi
  fi
}

# --gpu 时一律走独立的 GPU 环境；环境不存在就直接拒绝，绝不静默退回 CPU 跑大批量
resolve_python() {
  resolve_mode
  if [ "$MODE" = "gpu" ]; then
    if [ ! -x "$OCR_VENV/bin/python" ]; then
      echo "❌ 错误: 要求 GPU 但算力环境不存在 ($OCR_VENV)" >&2
      echo "💡 先执行: bash scripts/ocr.sh install" >&2
      exit 1
    fi
    echo "$OCR_VENV/bin/python"
  else
    echo "$PYTHON"
  fi
}

# GPU wheel 里的 CUDA/cuDNN 运行库不在宿主上，必须挂进 LD_LIBRARY_PATH；
# WSL2 还要带上 /usr/lib/wsl/lib 的驱动侧 libcuda.so.1。路径按 venv 现算，不写死。
export_cuda_ld() {
  local py="$1" site ld="" d
  site="$("$py" -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')"
  for d in "$site"/nvidia/*/lib /usr/lib/wsl/lib; do
    [ -d "$d" ] && ld="${ld:+$ld:}$d"
  done
  export LD_LIBRARY_PATH="${ld}${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
}

# 按生产路径真建一次引擎，结论只认 build_engine：缺包抛错，GPU 线三段会话任一不在 CUDA 上也抛错
# （get_available_providers() 只证明 wheel 编译进了 CUDA EP，.so 缺失时照样列出，不算数）。
# 调用方负责先 export_cuda_ld。ORT 在 pybind 层打的告警早于任何日志级别设置，只能整段吞掉 stderr。
probe_engine_device() {
  local py="$1" label="$2" use_gpu=False msg
  if [ ! -x "$py" ]; then
    echo "   - 推理引擎 [$label]: ⚪ 环境不存在"
    return 0
  fi
  [ "$label" = "GPU" ] && use_gpu=True
  if msg="$("$py" -c "from scripts.ocr_worker import build_engine
try: build_engine($use_gpu)
except Exception as exc: print(exc); raise SystemExit(1)" 2>/dev/null)"; then
    echo "   - 推理引擎 [$label]: 🟢 引擎可用$([ "$use_gpu" = True ] && echo '，Det/Cls/Rec 三段会话都在 CUDA 上')"
  else
    echo "   - 推理引擎 [$label]: ⚠️ ${msg:-引擎建不起来（解释器异常退出）}"
    return 1
  fi
}

# 显卡状态播报：探测逻辑复用 host_gpu_smi，避免"PATH 里没有 nvidia-smi"被当成没显卡
report_host_gpu() {
  local smi info
  smi="$(host_gpu_smi || true)"
  if [ -z "$smi" ]; then
    # Apple 机器别说"纯 CPU 宿主机"：onnxruntime 的 macOS arm64 包其实带 CoreML EP，
    # 拿不到加速是因为 rapidocr 的加速通道只认 CUDA。说清楚才不像是探测坏了。
    if [ "$(uname -s)" = "Darwin" ]; then
      echo "   - 宿主物理 GPU: 🟡 Apple 机器有 GPU，但 rapidocr 这条依赖链只支持 CUDA 加速，按 CPU 跑"
    else
      echo "   - 宿主物理 GPU: ⚪ 未检测到 NVIDIA 设备（纯 CPU 宿主机）"
    fi
    return 0
  fi
  if [ "$smi" = "/usr/lib/wsl/lib/nvidia-smi" ]; then
    export LD_LIBRARY_PATH="/usr/lib/wsl/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
  fi
  info="$("$smi" --query-gpu=name,memory.used,memory.total --format=csv,noheader,nounits 2>/dev/null | head -n 1 || true)"
  if [ -n "$info" ]; then
    echo "   - 宿主物理 GPU: 🟢 $info (MiB 已用/总量)"
  else
    echo "   - 宿主物理 GPU: ⚠️ 检测到 nvidia-smi 但读取失败 ($smi)"
  fi
}

cmd_status() {
  echo "📊 纸间 · 漫画台词 OCR 处理与索引状态"
  resolve_mode
  echo "   - 当前生效数据目录: $DATA_DIR"
  echo "   - 本轮默认算力线: $MODE"
  echo "   - CPU 解释器: $PYTHON"
  echo "   - GPU 算力环境: $OCR_VENV $([ -x "$OCR_VENV/bin/python" ] && echo '(已就绪)' || echo '(未创建)')"
  report_host_gpu
  probe_engine_device "$PYTHON" "CPU" || true
  if [ -x "$OCR_VENV/bin/python" ]; then
    export_cuda_ld "$OCR_VENV/bin/python"
  fi
  probe_engine_device "$OCR_VENV/bin/python" "GPU" || true
  "$(resolve_python)" scripts/ocr_worker.py --data-dir "$DATA_DIR" --status
}

# run/lines/test 共用：定算力线、取解释器；GPU 线挂上 CUDA 库并把 --gpu 透传给脚本——
# 显式写 --gpu 还是自动选中 GPU 环境都带上，GPU 实际用不上时由 build_engine 当场报错。
# resolve_mode 必须在当前 shell 先跑：resolve_python 在 $( ) 子 shell 里执行，在那里定下的 MODE
# 传不回来，后面 [ "$MODE" = gpu ] 永远不成立，GPU 环境会被当成 CPU 用（不挂 LD、不传 --gpu）。
run_py() {
  local script="$1" py gpu_arg=()
  shift
  resolve_mode
  py="$(resolve_python)"
  if [ "$MODE" = "gpu" ]; then
    export_cuda_ld "$py"
    gpu_arg=(--gpu)
  fi
  "$py" "$script" ${gpu_arg+"${gpu_arg[@]}"} ${@+"$@"}
}

cmd_run() {
  resolve_mode
  echo "🚀 开始执行漫画台词 OCR 批量提取 (目标目录: $DATA_DIR · 算力线: $MODE)..."
  run_py scripts/ocr_worker.py --data-dir "$DATA_DIR" ${@+"$@"}
}

# 聚类判据的离线实验台：dump 画页的原始识别行 / 读回 dump 重跑当前聚类。
# 改 cluster_blocks 的判据不必再"每改一版烧一轮 GPU"——推理只跑一次，之后都在本地量。
cmd_lines() {
  run_py scripts/ocr_lines.py --data-dir "$DATA_DIR" ${@+"$@"}
}

cmd_sync() {
  echo "🔄 正在同步 OCR 伴生文件至 SQLite FTS5 索引 (目标目录: $DATA_DIR)..."
  echo "   (入库走应用 .venv：需要 backend 依赖，与 OCR 算力环境无关)"
  "$PYTHON" scripts/sync_ocr.py --data-dir "$DATA_DIR" ${@+"$@"}
}

cmd_install() {
  # 装哪条线看宿主有没有卡：有卡默认就装 GPU 环境，不再要求用户记住 --gpu
  if [ -z "$MODE" ]; then
    if [ -n "$(host_gpu_smi || true)" ]; then
      MODE=gpu
      echo "   (检测到 NVIDIA 显卡，默认安装 GPU 算力环境；只想装 CPU 依赖请加 --cpu)"
    else
      MODE=cpu
      echo "   (未检测到 NVIDIA 显卡，安装 CPU 多核依赖)"
      if [ "$(uname -s)" = "Darwin" ]; then
        echo "   Apple 机器不必再试 --gpu：onnxruntime 没有 macOS 的 CUDA 构建，"
        echo "   而 rapidocr 的加速通道只认 CUDA，装不出可用加速器。跑批量大的话交给带卡的算力机。"
      fi
    fi
  fi

  if ! command -v uv >/dev/null 2>&1; then
    echo "❌ 错误: 找不到 uv。OCR 依赖按 uv.lock 安装，请先装 uv 并跑过 vpr setup:py。" >&2
    exit 1
  fi

  if [ "$MODE" = "cpu" ]; then
    echo "📦 正在往应用环境 .venv 追加 OCR 算力依赖 (pyproject.toml 的 ocr 依赖组)..."
    # --inexact：只装不卸，保留 .venv 里手动追加的可选推理依赖（docs/PITFALLS.md #180）
    uv sync --locked --inexact --group ocr
    echo "✅ 依赖安装完成！"
    echo "   带 NVIDIA 显卡的算力机直接 bash scripts/ocr.sh install 即装 GPU 环境（默认就走 GPU）"
    return 0
  fi

  if [ -z "$(host_gpu_smi || true)" ]; then
    echo "   ⚠️ 未检测到 NVIDIA 显卡，仍按要求装 GPU 环境；末尾自检大概率失败，无卡机器请改用 install --cpu。"
  fi

  local vpy="$OCR_VENV/bin/python"
  # 绝不允许把 GPU 栈装进应用环境：下面是精确同步，会把 ocr-gpu 组之外的包全部卸掉，
  # 指到应用 .venv 就等于把后端依赖卸光。
  local app_prefix
  app_prefix="$("$PYTHON" -c 'import sys; print(sys.prefix)')"
  if [ "$app_prefix" = "$OCR_VENV" ]; then
    echo "❌ 错误: COMIC_SHELF_OCR_VENV 指向了应用环境本身 ($OCR_VENV)，拒绝在其中装 GPU 依赖" >&2
    exit 1
  fi
  # 同理：目录已存在却不是虚拟环境（没有 pyvenv.cfg）时不碰它，多半是路径写错了
  if [ -e "$OCR_VENV" ] && [ ! -f "$OCR_VENV/pyvenv.cfg" ]; then
    echo "❌ 错误: $OCR_VENV 已存在但不是 Python 虚拟环境，拒绝在其中安装" >&2
    exit 1
  fi

  echo "📦 正在同步 GPU 算力环境: $OCR_VENV (ocr-gpu 依赖组，装完约占 2.8GB)"
  # --only-group：环境里只有 ocr-gpu 组，不带后端依赖；精确同步会卸掉组外的包，包括误装进来的 CPU 版 onnxruntime。
  # --reinstall-package：CPU 与 GPU 两个 wheel 共用 site-packages/onnxruntime/ 目录，卸掉 CPU 版会连带删走共用文件，
  # 而 uv 只看安装记录、仍认为 GPU 版"已装好"，留下一个残缺的包（docs/PITFALLS.md #140）。每次重装它即可根治。
  UV_PROJECT_ENVIRONMENT="$OCR_VENV" uv sync --locked --only-group ocr-gpu --reinstall-package onnxruntime-gpu

  echo "🔎 自检 CUDA 是否真的生效..."
  export_cuda_ld "$vpy"
  if probe_engine_device "$vpy" "GPU"; then
    echo "✅ GPU 算力环境就绪，此后 run/test 默认走 GPU。跑批示例："
    echo "   bash scripts/ocr.sh run --source jm --workers 4"
  else
    echo "❌ 自检未通过：环境装完了但 GPU 没真正生效，run 会被 worker 预检挡下。" >&2
    echo "   请按上面那行 ⚠️ 的原因排查（最常见的两条：CPU 版 onnxruntime 覆盖了 GPU 版、" >&2
    echo "   LD_LIBRARY_PATH 没带上 venv 内的 nvidia/*/lib）。" >&2
    exit 1
  fi
}

cmd_test() {
  local target_img="${1:-}"
  if [ -z "$target_img" ]; then
    # 自动探测第一张画页用于测试
    target_img="$(find "$DATA_DIR/library" -type f \( -name "*.webp" -o -name "*.jpg" -o -name "*.png" \) 2>/dev/null | head -n 1 || true)"
  fi

  if [ -z "$target_img" ] || [ ! -f "$target_img" ]; then
    echo "❌ 错误: 未指定测试画页，且在 $DATA_DIR 未找到测试图片。"
    echo "用法: bash scripts/ocr.sh test [--cpu] <图片路径>"
    exit 1
  fi

  echo "🧪 正在对单张测试画页运行 OCR 识别: $target_img"
  # 与 run 同一套引擎构造、置信度门槛与聚类，只打印、不写盘
  run_py scripts/ocr_lines.py --image "$target_img"
}

ACTION="${1:-status}"
shift || true

ARGS=()
GPU_PIN=0
CPU_PIN=0
for arg in "$@"; do
  case "$arg" in
    --gpu) GPU_PIN=1 ;;
    --cpu) CPU_PIN=1 ;;
    *) ARGS+=("$arg") ;;
  esac
done
if [ "$GPU_PIN" = 1 ] && [ "$CPU_PIN" = 1 ]; then
  echo "❌ 错误: --gpu 与 --cpu 互斥，不能同时给出。" >&2
  exit 1
fi
if [ "$GPU_PIN" = 1 ]; then
  MODE=gpu
  MODE_PINNED=1
elif [ "$CPU_PIN" = 1 ]; then
  MODE=cpu
  MODE_PINNED=1
fi

case "$ACTION" in
  status)
    cmd_status
    ;;
  run)
    cmd_run ${ARGS+"${ARGS[@]}"}
    ;;
  sync)
    cmd_sync ${ARGS+"${ARGS[@]}"}
    ;;
  install)
    cmd_install
    ;;
  test)
    cmd_test ${ARGS+"${ARGS[@]}"}
    ;;
  lines)
    cmd_lines ${ARGS+"${ARGS[@]}"}
    ;;
  *)
    echo "使用方法: $0 {status|run|sync|install|test|lines} [--gpu|--cpu] [参数...]"
    echo ""
    echo "  默认走 GPU：装好 .venv-ocr 后 run/test/status 自动选它；--cpu 强制回落应用 .venv。"
    echo ""
    echo "  install [--gpu|--cpu]   - 装 OCR 推理依赖。检测到 NVIDIA 显卡即装 GPU 环境 (.venv-ocr/)，"
    echo "                              无卡机器加 --cpu 只装 CPU 依赖"
    echo "  status                  - 查看书库 OCR 伴生覆盖率、硬件与双环境实际推理设备、FTS5 统计"
    echo "  run [options]           - 批量或定向对画页提取 OCR 伴生文件 ({index}.ocr.json)"
    echo "     --workers <N>        - 并发线程数 (GPU 推荐 4；CPU 线保持 2，再加会因抢核反而变慢)"
    echo "     --source <src>       - 限定数据源，即 library/ 下的目录名 (jm / local / picacg / copymanga)"
    echo "     --id <comic_id>      - 限定单本漫画 ID"
    echo "     --page <pages>       - 限定提取特定页码 (如 --page 3 或 --page 1,3,5 或 --page 10-20；多章节本请改用 --image)"
    echo "     --image <path>       - 直接指定单张画页图片路径进行单页处理"
    echo "     --min-score <float>  - 识别置信度下限，直接交给引擎 (默认 0.5，调低调高都生效；过滤拟声词与背景噪点)"
    echo "     --force              - 强制重新处理已存在的伴生文件"
    echo "     --limit <N>          - 最多处理册数（只数确有待提取画页的本，已完成的不占名额）"
    echo "     --api-url <URL>      - 远程 NAS 纸间 API 地址 (如 http://192.168.1.100:8000)，处理后自动通知入库"
    echo "     --token <TOKEN>      - 纸间 Machine API Token（建议改设环境变量 COMIC_SHELF_MACHINE_TOKEN，不写在命令行）"
    echo "     --sync-local         - 处理完毕后直接同步本地 SQLite 索引（环境里要有后端依赖，GPU 环境没有，请改用 sync）"
    echo "  sync [options]          - 将已存在的伴生文件全量/增量扫入 SQLite FTS5"
    echo "  test [image]            - 单张画页试跑并打印气泡（与 run 同一套引擎与过滤，只打印不写盘）"
    echo "  lines [options]         - 气泡聚类判据的离线实验台，改 cluster_blocks 前先用它："
    echo "     --source <src> [--id <id>] [--pages N] [--out DIR]"
    echo "                            - dump 该批画页的**原始识别行**到 DIR（默认 /tmp/paper-room-ocr-lines），"
    echo "                              只跑一次推理，**绝不写 backend/data**；省掉 --id 即该源全部画页"
    echo "     --recluster DIR       - 不跑推理：读回 dump，用当前聚类重跑并打印气泡数/字数/面积分布/疑似误并"
    echo "     --image <path>        - 只识别这一张并打印聚类后的气泡，不写任何文件（test 走的就是它）"
    echo ""
    echo "  示例: bash scripts/ocr.sh install                      # 有卡即装 GPU 环境"
    echo "        bash scripts/ocr.sh run --source jm --workers 4  # 默认就走 GPU"
    echo "        bash scripts/ocr.sh sync --source jm"
    exit 1
    ;;
esac
