"""台词「按意思找」的查询侧编码器：ONNX + tokenizers，零 torch。

放在这里的原因：语义检索要在**服务进程里**把用户那句问题变成向量，这一步没法挪到算力机上
（问题是什么时候来的都有）。整库文本编码实测 184 行/秒（CPU），41 秒跑完 7544 行，所以
语料向量也直接在本机算，不必像画页 OCR 那样走算存分离。

模型缺失时所有函数返回 `None` 而不是抛异常：语义召回是增量能力，装不上模型的环境必须照常
提供关键词检索（与 `storage/pdf.py` 的扉页分话同一套降级口径）。numpy 同样用到才导入：
基础镜像不带它，模块级导入会让 `*/ocr/sync` 在关键词入库之后抛 500；缺了它就按编码器不可用处理。
"""
from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import TYPE_CHECKING

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

_LOCK = threading.Lock()
_SESSION = None
_TOKENIZER = None
_DIM: int | None = None
_FAILED = False


def model_present() -> bool:
    return _MODEL_PATH.is_file() and _TOKENIZER_PATH.is_file()


def _load():
    """惰性建会话。装不上就记住"这次进程里别再试了"，避免每次检索都重跑一遍失败路径。"""
    global _SESSION, _TOKENIZER, _DIM, _FAILED
    if _SESSION is not None:
        return _SESSION, _TOKENIZER
    if _FAILED or not model_present():
        return None, None
    with _LOCK:
        if _SESSION is not None or _FAILED:
            return _SESSION, _TOKENIZER
        try:
            import onnxruntime as ort
            from tokenizers import Tokenizer

            sess = ort.InferenceSession(str(_MODEL_PATH), providers=["CPUExecutionProvider"])
            tok = Tokenizer.from_file(str(_TOKENIZER_PATH))
            tok.enable_truncation(MAX_TOKENS)
            tok.enable_padding(pad_id=0, direction="right")
            probe = tok.encode_batch(["探针"])
            feed = _feed(sess, probe)
            dim = int(sess.run(None, feed)[0].shape[-1])
            _SESSION, _TOKENIZER, _DIM = sess, tok, dim
            logger.info("语义检索编码器就绪：%s（%d 维）", _MODEL_PATH, dim)
        except Exception as exc:
            _FAILED = True
            logger.warning(
                "语义检索编码器不可用（%s）：关键词检索不受影响。启用方法见 DEPLOYMENT.md §5.1.2（模型放 %s）",
                exc,
                MODEL_DIR,
            )
    return _SESSION, _TOKENIZER


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
    _load()
    return _DIM


def encode_documents(texts: list[str], batch: int = 64) -> np.ndarray | None:
    """把整句台词编成已归一化的向量矩阵（行内积即余弦）；编码器不可用时返回 None。"""
    sess, tok = _load()
    if sess is None or not texts:
        return None
    import numpy as np

    out = np.empty((len(texts), _DIM or 0), dtype=np.float32)
    for i in range(0, len(texts), batch):
        chunk = texts[i : i + batch]
        encoded = tok.encode_batch(chunk)
        cls = sess.run(None, _feed(sess, encoded))[0][:, 0, :]
        norms = np.clip(np.linalg.norm(cls, axis=1, keepdims=True), 1e-9, None)
        out[i : i + len(chunk)] = cls / norms
    return out


def encode_query(text: str) -> np.ndarray | None:
    """编码一条检索问题（带 bge 指令前缀）；编码器不可用时返回 None。"""
    clean = (text or "").strip()
    if not clean:
        return None
    sess, tok = _load()
    if sess is None:
        return None
    import numpy as np

    encoded = tok.encode_batch([QUERY_INSTRUCTION + clean])
    cls = sess.run(None, _feed(sess, encoded))[0][:, 0, :]
    return (cls[0] / max(float(np.linalg.norm(cls[0])), 1e-9)).astype(np.float32)
