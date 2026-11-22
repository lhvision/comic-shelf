"""OCR 伴生资产与图片输入预算；提取及索引同步共用，不初始化模型或数据库。"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from ..file_io import exclusive_file_lock, file_stamp, read_json

MAX_SIDECAR_BYTES = 2 * 1024 * 1024
MAX_PAGE_BUBBLES = 1024
MAX_TEXT_CHARS = 8192
MAX_IMAGE_BYTES = 50 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000


def normalize_box(raw: Any) -> list[float] | None:
    """有限且有序的归一化外接框；历史坏坐标丢框但不丢文字。"""
    if not isinstance(raw, list) or len(raw) != 4:
        return None
    if any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not 0 <= value <= 1
        for value in raw
    ):
        return None
    if raw[0] > raw[2] or raw[1] > raw[3]:
        return None
    return [float(value) for value in raw]


def validate_sidecar(data: Any) -> dict[str, Any]:
    """校验结构及条数/文本预算；允许历史无 engine 字段和无效坐标，坐标由入库侧降级。"""
    if not isinstance(data, dict) or not isinstance(data.get("bubbles"), list):
        raise TypeError("OCR 伴生资产必须包含 bubbles 数组")
    if len(data["bubbles"]) > MAX_PAGE_BUBBLES:
        raise ValueError(f"单页气泡数超过 {MAX_PAGE_BUBBLES} 条预算")
    for bubble in data["bubbles"]:
        if not isinstance(bubble, dict) or not isinstance(bubble.get("text"), str):
            raise TypeError("OCR 气泡必须包含文字字符串")
        if len(bubble["text"]) > MAX_TEXT_CHARS:
            raise ValueError(f"单条文字超过 {MAX_TEXT_CHARS} 字符预算")
    return data


def read_sidecar(path: Path, *, root: Path | None = None) -> dict[str, Any]:
    """先按字节预算读取，再校验单页结构，保留源文件不作裁剪或修复。"""
    return validate_sidecar(read_json(path, root=root, max_bytes=MAX_SIDECAR_BYTES))


def verify_source_image(data: dict[str, Any], image: Path | None, *, root: Path) -> bool:
    """新资产必须匹配原图；历史没有 source_image 返回 False，表示未核验而非已过期。"""
    if "source_image" not in data:
        return False
    source = data["source_image"]
    if not isinstance(source, dict) or any(type(source.get(key)) is not int for key in ("size", "mtime_ns")):
        raise ValueError("OCR source_image 状态损坏")
    if image is None:
        raise ValueError("OCR 原图缺失，需要补齐原图后重新提取")
    stamp = file_stamp(image, root=root)
    if source != {"size": stamp[2], "mtime_ns": stamp[3]}:
        raise ValueError(f"OCR 已过期，原图变化后需要重新提取: {image}")
    return True


@contextmanager
def comic_asset_lock(library: Path, source: str, source_id: str) -> Generator[None]:
    """同步提交与存储画页修改共用本机书籍锁；目录独立于可删除的漫画目录。"""
    directory = library / ".ocr-locks"
    directory.mkdir(parents=True, exist_ok=True)
    name = hashlib.sha256(f"{source}\0{source_id}".encode()).hexdigest() + ".lock"
    with exclusive_file_lock(directory / name, root=library):
        yield
