"""台词「按意思找」的查询侧编码器：ONNX + tokenizers，零 torch。

放在这里的原因：语义检索要在**服务进程里**把用户那句问题变成向量，这一步没法挪到算力机上
（问题是什么时候来的都有）。整库文本编码实测 184 行/秒（CPU），41 秒跑完 7544 行，所以
语料向量也直接在本机算，不必像画页 OCR 那样走算存分离。

模型缺失时所有函数返回 `None` 而不是抛异常：语义召回是增量能力，装不上模型的环境必须照常
提供关键词检索（与 `storage/pdf.py` 的扉页分话同一套降级口径）。numpy 同样用到才导入：
基础镜像不带它，模块级导入会让台词同步在关键词入库之后报错；缺了它就按编码器不可用处理。
"""

from __future__ import annotations

import hashlib
import logging
import os
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any, NamedTuple

from .config import DATA_DIR

if TYPE_CHECKING:
    import numpy as np

logger = logging.getLogger(__name__)

# bge-zh 系列官方口径：检索的 query 前加这句指令，文档侧不加。实测能让
# 「今天天气不错」排到「真是好天气！雨过天晴了呢！」而不是字面都含「今天」的碎句。
QUERY_INSTRUCTION = "为这个句子生成表示以用于检索相关文章："
MAX_TOKENS = 64
# 低于这个长度的台词不建向量：'下'、'对不起' 这类没有语义可谈，只会把余弦分布压平
MIN_EMBED_CHARS = 4

_DEFAULT_DIR = DATA_DIR / "models" / "bge-small-zh-v1.5"
MODEL_DIR = Path(os.getenv("COMIC_SHELF_EMBED_DIR", str(_DEFAULT_DIR))).expanduser()
_MODEL_PATH = MODEL_DIR / "model.onnx"
_TOKENIZER_PATH = MODEL_DIR / "tokenizer.json"


class _EncoderState(NamedTuple):
    """编码任务固定使用的模型状态；整体发布，推理期间不读取可变全局字段。"""

    session: Any
    tokenizer: Any
    dim: int
    signature: str


_LOCK = threading.Lock()
_STATE: _EncoderState | None = None
_FAILED_SIGNATURE = ""
_SIGNATURE_CACHE: tuple[object, str] | None = None


def model_present() -> bool:
    return _MODEL_PATH.is_file() and _TOKENIZER_PATH.is_file()


def model_signature() -> str:
    """模型与编码参数共同标识向量空间；文件缺失或不可读时返回空签名，保留关键词降级。"""
    global _SIGNATURE_CACHE
    try:
        if not model_present():
            return ""
        stamps = tuple(
            (path.stat().st_ino, path.stat().st_size, path.stat().st_mtime_ns, path.stat().st_ctime_ns)
            for path in (_MODEL_PATH, _TOKENIZER_PATH)
        )
        if _SIGNATURE_CACHE is not None and _SIGNATURE_CACHE[0] == stamps:
            return _SIGNATURE_CACHE[1]
        digest = hashlib.sha256(f"bge-cls-l2:{MAX_TOKENS}:{MIN_EMBED_CHARS}".encode())
        for path in (_MODEL_PATH, _TOKENIZER_PATH):
            with path.open("rb") as file:
                for chunk in iter(lambda: file.read(1024 * 1024), b""):
                    digest.update(chunk)
    except OSError as exc:
        _SIGNATURE_CACHE = None
        logger.warning("语义模型指纹不可用（%s）：关键词检索不受影响", exc)
        return ""
    signature = digest.hexdigest()
    _SIGNATURE_CACHE = stamps, signature
    return signature


def _load() -> _EncoderState | None:
    """在锁内取得或发布完整模型状态；失败的同一模型不重复初始化，文件变化后可恢复。"""
    global _STATE, _FAILED_SIGNATURE
    with _LOCK:
        signature = model_signature()
        if not signature:
            _STATE = None
            _FAILED_SIGNATURE = ""
            return None
        if _STATE is not None and signature == _STATE.signature:
            return _STATE
        if signature == _FAILED_SIGNATURE:
            return None
        _STATE = None
        try:
            import numpy as np
            import onnxruntime as ort
            from tokenizers import Tokenizer

            sess = ort.InferenceSession(str(_MODEL_PATH), providers=["CPUExecutionProvider"])
            tok = Tokenizer.from_file(str(_TOKENIZER_PATH))
            tok.enable_truncation(MAX_TOKENS)
            tok.enable_padding(pad_id=0, direction="right")
            probe = tok.encode_batch(["探针"])
            feed = _feed(sess, probe)
            out = sess.run(None, feed)[0]
            if not isinstance(out, np.ndarray):
                raise TypeError(f"模型输出不是稠密张量：{type(out).__name__}")
            dim = int(out.shape[-1])
            if model_signature() != signature:
                logger.warning("初始化期间语义模型发生变化，稍后重试")
                return None
            state = _EncoderState(sess, tok, dim, signature)
            _STATE = state
            _FAILED_SIGNATURE = ""
            logger.info("语义检索编码器就绪：%s（%d 维）", _MODEL_PATH, dim)
            return state
        except Exception as exc:
            _FAILED_SIGNATURE = signature
            logger.warning(
                "语义检索编码器不可用（%s）：关键词检索不受影响。启用方法见 DEPLOYMENT.md §5.1.2（模型放 %s）",
                exc,
                MODEL_DIR,
            )
            return None


def _feed(sess, encoded):
    """把 tokenizers 的输出铺成 numpy 批次，并按模型实际声明的输入组装 feed。

    `_load` 的探针也走这里，所以缺 numpy 会在它的 try 里被接住，记成编码器不可用。
    """
    import numpy as np

    n = max(len(e.ids) for e in encoded)
    ids = np.zeros((len(encoded), n), dtype="int64")
    mask = np.zeros((len(encoded), n), dtype="int64")
    for i, e in enumerate(encoded):
        ids[i, : len(e.ids)] = e.ids
        mask[i, : len(e.attention_mask)] = e.attention_mask
    feed = {"input_ids": ids, "attention_mask": mask}
    declared = {i.name for i in sess.get_inputs()}
    if "token_type_ids" in declared:
        feed["token_type_ids"] = np.zeros_like(ids)
    return {k: v for k, v in feed.items() if k in declared}


def dim() -> int | None:
    """返回本次取得的模型维度，不与其他线程随后发布的状态混用。"""
    state = _load()
    return state.dim if state is not None else None


def encode_documents(texts: list[str], batch: int = 64, *, expected_signature: str | None = None) -> np.ndarray | None:
    """用固定状态编码整批台词；编码器缺失或与调用方预期的模型签名不符时返回 None。"""
    state = _load()
    if state is None or not texts or (expected_signature is not None and state.signature != expected_signature):
        return None
    import numpy as np

    out = np.empty((len(texts), state.dim), dtype=np.float32)
    for i in range(0, len(texts), batch):
        chunk = texts[i : i + batch]
        encoded = state.tokenizer.encode_batch(chunk)
        cls = state.session.run(None, _feed(state.session, encoded))[0][:, 0, :]
        norms = np.clip(np.linalg.norm(cls, axis=1, keepdims=True), 1e-9, None)
        out[i : i + len(chunk)] = cls / norms
    return out


def encode_query(text: str, *, expected_signature: str | None = None) -> np.ndarray | None:
    """用固定状态编码问题；只向调用方返回与预期向量空间一致的结果。"""
    clean = (text or "").strip()
    if not clean:
        return None
    state = _load()
    if state is None or (expected_signature is not None and state.signature != expected_signature):
        return None
    import numpy as np

    encoded = state.tokenizer.encode_batch([QUERY_INSTRUCTION + clean])
    cls = state.session.run(None, _feed(state.session, encoded))[0][:, 0, :]
    return (cls[0] / max(float(np.linalg.norm(cls[0])), 1e-9)).astype(np.float32)
