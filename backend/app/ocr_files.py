"""OCR 文件作业共用的路径解析、文件清单和现有 Pillow 可读格式；不依赖 OCR 引擎。"""

from __future__ import annotations

import argparse
import os
import re
import stat
from collections.abc import Collection
from pathlib import Path


def image_formats() -> frozenset[str]:
    """现有 Pillow 的光栅读取格式，排除文档渲染器及只有识别能力的占位插件。"""
    from PIL import Image

    Image.init()
    return frozenset(Image.OPEN) - {"EPS", "WMF", "MPEG", "HDF5", "GRIB", "BUFR"}


def image_extensions() -> frozenset[str]:
    """扫描后缀与实际解码格式使用同一份 Pillow 注册表。"""
    from PIL import Image

    formats = image_formats()
    return frozenset(
        extension.lower() for extension, format_name in Image.registered_extensions().items() if format_name in formats
    )


def normalize_library_name(value: object) -> str:
    """与存储目录及台词主键一致的规范化规则；CLI 拒绝会被该规则改写的名称。"""
    name = re.sub(r"[^a-zA-Z0-9_\-\.]+", "_", str(value)).strip("._") or "_"
    while ".." in name:
        name = name.replace("..", "_")
    return name


def resolve_data_dir(custom_path: str | None = None) -> Path:
    """显式数据目录优先于环境变量；指定无效路径时拒绝，不能改扫另一个书库。"""
    selected = custom_path if custom_path is not None else os.environ.get("COMIC_SHELF_DATA") or None
    if selected is not None:
        path = Path(selected).expanduser().resolve()
        if not selected.strip() or not path.is_dir():
            raise ValueError(f"指定的数据目录不存在或不是目录: {selected!r}")
        return path
    nas_mount = Path("/mnt/nas_manga")
    if (nas_mount / "library").is_dir():
        return nas_mount.resolve()
    return Path(__file__).resolve().parents[1] / "data"


def parse_path(value: str) -> str:
    """路径保留原文，拒绝空白值。"""
    if not value.strip():
        raise argparse.ArgumentTypeError("路径不能为空")
    return value


def parse_directory_name(value: str) -> str:
    """图源、书号必须是非空单个目录名，不能指向父目录。"""
    value = value.strip()
    if not value or normalize_library_name(value) != value:
        raise argparse.ArgumentTypeError(
            "必须填写规范的图源或书号：字母、数字、下划线、短横线或点，且不能被目录清洗改写"
        )
    return value


def scan_files(directory: Path, suffixes: Collection[str]) -> list[Path]:
    """递归扫描普通文件；提取、同步、实验回放共用隐藏项和符号链接规则。"""
    if directory.is_symlink():
        raise ValueError(f"扫描目录不能是符号链接: {directory}")
    if not directory.is_dir():
        return []
    found: list[Path] = []

    def on_error(exc: OSError) -> None:
        raise exc

    for root, dirs, files in os.walk(directory, onerror=on_error, followlinks=False):
        base = Path(root)
        dirs[:] = sorted(d for d in dirs if not d.startswith(".") and not (base / d).is_symlink())
        for name in sorted(files):
            path = base / name
            if name.startswith(".") or not name.lower().endswith(tuple(suffixes)):
                continue
            if stat.S_ISREG(path.stat(follow_symlinks=False).st_mode):
                found.append(path)
    return sorted(found)


def _image_outputs(images: list[Path]) -> list[tuple[Path, Path]]:
    """一次遍历校验目标，大小写不同的同名页也拒绝，避免映射盘上的覆盖。"""
    outputs: dict[tuple[Path, str], Path] = {}
    pairs: list[tuple[Path, Path]] = []
    for image in images:
        output = image.with_name(f"{image.stem}.ocr.json")
        key = output.parent, output.name.casefold()
        if key in outputs:
            raise ValueError(f"伴生文件冲突: {outputs[key]} 与 {image}")
        if output.is_symlink():
            raise ValueError(f"伴生文件不能是符号链接: {output}")
        outputs[key] = image
        pairs.append((image, output))
    return pairs


def image_output(image: Path) -> Path:
    """单页与批量共用同名图片及符号链接检查。"""
    extensions = image_extensions()
    siblings = [
        p
        for p in image.parent.iterdir()
        if p.stem.casefold() == image.stem.casefold()
        and p.suffix.lower() in extensions
        and not p.is_symlink()
        and p.is_file()
    ]
    _image_outputs(siblings)
    return image.with_name(f"{image.stem}.ocr.json")


def collect_images(directory: Path) -> list[tuple[Path, Path]]:
    """递归列出可读格式图片及其伴生文件，提前拒绝输出冲突。"""
    return _image_outputs(scan_files(directory, image_extensions()))


def collect_comic_pages(comic_dir: Path, page_filter: set[int] | None = None) -> list[tuple[Path, Path]]:
    """按章节、文件名收集画页；多章节本的 --page 无法唯一定位，因此拒绝。"""
    pages_dir = comic_dir / "pages"
    if not pages_dir.is_dir() or pages_dir.is_symlink():
        return []
    pages = collect_images(pages_dir)
    if not page_filter:
        return pages
    if len({image.parent for image, _ in pages}) > 1:
        raise ValueError("多章节本不支持 --page（各话都有同名页，页码指不到唯一一页），请改用 --image <画页路径>")
    return [
        pair
        for index, pair in enumerate(pages, start=1)
        if index in page_filter or (pair[0].stem.isdecimal() and int(pair[0].stem) in page_filter)
    ]


def list_comics(
    library_dir: Path, source: str | None = None, comic_id: str | None = None
) -> list[tuple[str, str, Path]]:
    """图源以实际目录为准；过滤隐藏目录、符号链接，允许按图源或书号限定。"""

    def subdirs(directory: Path, name: str | None) -> list[Path]:
        if not directory.is_dir() or directory.is_symlink():
            return []
        candidates = [directory / name] if name is not None else directory.iterdir()
        return sorted(p for p in candidates if p.is_dir() and not p.is_symlink() and not p.name.startswith("."))

    comics: list[tuple[str, str, Path]] = []
    for source_dir in subdirs(library_dir, source):
        if normalize_library_name(source_dir.name) != source_dir.name:
            raise ValueError(f"图源目录名会被后端改写，拒绝处理: {source_dir.name}")
        for comic_dir in subdirs(source_dir, comic_id):
            if normalize_library_name(comic_dir.name) != comic_dir.name:
                raise ValueError(f"书号目录名会被后端改写，拒绝处理: {comic_dir.name}")
            comics.append((source_dir.name, comic_dir.name, comic_dir))
    return comics


def image_comic_key(image: Path, data_dir: Path) -> tuple[str, str]:
    """相对所选书库定位单张画页所属本；不从任意路径里的 library 字样猜测。"""
    try:
        parts = image.resolve().relative_to((data_dir / "library").resolve()).parts
    except ValueError as exc:
        raise ValueError("同步单张画页时，图片必须位于所选 data-dir 的 library/<图源>/<书号>/pages/ 中") from exc
    if len(parts) < 4 or parts[2] != "pages":
        raise ValueError("同步单张画页时，图片必须位于 library/<图源>/<书号>/pages/ 中")
    return parse_directory_name(parts[0]), parse_directory_name(parts[1])
