"""共享文件读写：普通文件校验、限定目录内的读取及原子发布；仅使用标准库。"""

from __future__ import annotations

import json
import os
import stat
import uuid
from collections.abc import Generator
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import Any, BinaryIO


@contextmanager
def _parent_fd(path: Path, root: Path | None) -> Generator[int | None]:
    """指定根目录时逐级打开目录，拒绝符号链接；描述符固定实际目录身份。"""
    if root is None:
        yield None
        return
    relative = path.relative_to(root)
    if not relative.parts or any(part in {".", ".."} for part in relative.parts):
        raise ValueError(f"文件不在指定根目录内: {path}")
    with ExitStack() as stack:
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        directory = os.open(root, flags)
        stack.callback(os.close, directory)
        for part in relative.parts[:-1]:
            directory = os.open(part, flags, dir_fd=directory)
            stack.callback(os.close, directory)
        yield directory


@contextmanager
def open_regular(path: Path, *, root: Path | None = None) -> Generator[BinaryIO]:
    """只打开普通文件，不跟随叶子链接，不阻塞在命名管道上。"""
    with _parent_fd(path, root) as directory:
        flags = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW
        fd = os.open(path if directory is None else path.name, flags, dir_fd=directory)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise ValueError(f"不是普通文件: {path}")
            file = os.fdopen(fd, "rb")
        except BaseException:
            os.close(fd)
            raise
        with file:
            yield file


def file_stamp(path: Path, *, root: Path | None = None) -> tuple[int, int, int, int, int]:
    """文件身份与变化标记，用于识别期间的替换检测和索引增量判断。"""
    with open_regular(path, root=root) as file:
        info = os.fstat(file.fileno())
        return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def read_json(path: Path, *, root: Path | None = None) -> Any:
    """从经过普通文件及目录边界校验的文件读取 JSON。"""
    with open_regular(path, root=root) as file:
        return json.load(file)


def write_bytes_atomic(path: Path, payload: bytes, *, root: Path | None = None, overwrite: bool = True) -> None:
    """独占创建同目录临时文件、刷盘后发布；overwrite=False 不覆盖已有目标。"""
    if root is None:
        path.parent.mkdir(parents=True, exist_ok=True)
    with _parent_fd(path, root) as directory:
        temp = f".{path.name}.{uuid.uuid4().hex}.tmp"
        temp_path = path.parent / temp if directory is None else temp
        target = path if directory is None else path.name
        fd = os.open(temp_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o666, dir_fd=directory)
        try:
            file = os.fdopen(fd, "wb")
            fd = None
            with file:
                file.write(payload)
                file.flush()
                os.fsync(file.fileno())
            if overwrite:
                os.replace(temp_path, target, src_dir_fd=directory, dst_dir_fd=directory)
            else:
                os.link(temp_path, target, src_dir_fd=directory, dst_dir_fd=directory, follow_symlinks=False)
        finally:
            if fd is not None:
                os.close(fd)
            try:
                os.unlink(temp_path, dir_fd=directory)
            except FileNotFoundError:
                pass


def write_json_atomic(path: Path, data: Any, *, root: Path | None = None, overwrite: bool = True) -> None:
    """共享 JSON 序列化与原子发布，保持既有伴生格式。"""
    write_bytes_atomic(
        path, json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"), root=root, overwrite=overwrite
    )
