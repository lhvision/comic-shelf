#!/usr/bin/env python3
"""本机台词索引同步的仓库脚本入口；容器内使用 python -m app.ocr.sync。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.ocr.sync import main

if __name__ == "__main__":
    raise SystemExit(main())
