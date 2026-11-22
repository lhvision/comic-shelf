"""共享文件读写：普通文件校验、限定目录内的读取及原子发布；仅使用标准库。"""

from __future__ import annotations

import json
import os
import stat
import threading
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


def read_json(path: Path, *, root: Path | None = None, max_bytes: int | None = None) -> Any:
    """从普通文件读取 JSON；有预算时先有界读取，超限不进入解析器。"""
    with open_regular(path, root=root) as file:
        if max_bytes is None:
            return json.load(file)
        content = file.read(max_bytes + 1)
        if len(content) > max_bytes:
            raise ValueError(f"JSON 文件超过 {max_bytes} 字节预算: {path}")
        try:
            return json.loads(content)
        except RecursionError as exc:
            raise ValueError(f"JSON 嵌套过深: {path}") from exc


_LOCKED_FILES = threading.local()


@contextmanager
def exclusive_file_lock(path: Path, *, root: Path) -> Generator[None]:
    """本机进程及线程共享、同线程可重入的文件锁；锁文件必须位于可信根目录内。

    仅用于持久化目录的本机操作，不通过网络文件系统实现分布式锁。路径固定在书库
    的隐藏锁目录中，书籍删除或重装订不能替换锁的身份。
    """
    import fcntl

    key = str(path.absolute())
    held = getattr(_LOCKED_FILES, "held", None)
    if held is None:
        held = _LOCKED_FILES.held = set()
    if key in held:
        yield
        return
    with _parent_fd(path, root) as directory:
        fd = os.open(path.name, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=directory)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise ValueError(f"锁文件不是普通文件: {path}")
            fcntl.flock(fd, fcntl.LOCK_EX)
            held.add(key)
            try:
                yield
            finally:
                held.remove(key)
        finally:
            os.close(fd)


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
