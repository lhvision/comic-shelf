from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import sqlite3
import string
import threading
import time
from pathlib import Path
from typing import Any

from ..file_io import file_stamp, read_json
from ..ocr.assets import comic_asset_lock, normalize_box, read_sidecar, verify_source_image
from ..ocr.classification import (
    CLASSIFICATION_VERSION,
    DIALOGUE_KIND,
    advertisement_page_reason,
    classify_dialogue_kind,
)
from ..ocr.files import image_extensions, normalize_library_name, scan_files
from ..zh_conv import to_simplified
from .connection import _escape_like, get_data_dir, get_db, get_dialogue_db, get_dialogue_db_path

logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# 台词全文索引（comic_dialogues_fts）同步与检索
# ----------------------------------------------------------------------

# 阅读器一次最多画几个气泡（代表气泡 + 同页其余命中气泡）；超出的只计入 bubble_count，免得撑长 URL、糊满画面
MAX_PAGE_BOXES = 6

# 只折 ASCII 大小写，与 LIKE 和 SQLite lower() 同一口径。不用 str.lower()：它会把个别字符
# 变长（'İ' → 'i̇'），折完的下标就对不回原文了
_ASCII_LOWER = str.maketrans(string.ascii_uppercase, string.ascii_lowercase)


def _coerce_order_index(raw: Any, fallback: int) -> int:
    """把侧车里可能畸形（浮点、字符串、1e999、dict）的序号收敛成正整数。"""
    try:
        n = int(raw)
    except TypeError, ValueError, OverflowError:
        return fallback
    return n if n >= 0 else fallback


def _make_snippet(raw: str, norm: str, needle: str, max_chars: int = 60) -> str:
    """摘要与高亮：在归一列里定位，按 1:1 偏移切回原文再加 `<mark>`。

    Args:
        raw: 入库时保留的**原文**（页面上那套字形），也是最终展示的内容。
        norm: 该行的归一文本（`to_simplified(raw)`），只用来定位。
        needle: 归一后的查询串，与 norm 同一套字形。
        max_chars: 定位失败时前缀摘要的长度。

    Returns:
        带 `<mark>` 的纯文本片段，前后按需补 `...`；由前台安全声明式解析，不拼 HTML。

    `to_simplified` 是逐字符 1:1 映射，norm 上的下标可原样切回 raw（ADR 0017 2026-09-23 修订）。
    定位不分 ASCII 大小写，与 trigram、LIKE 同一口径。
    """
    if not raw:
        return ""
    start = norm.translate(_ASCII_LOWER).find(needle.translate(_ASCII_LOWER)) if needle else -1
    if start < 0:
        return raw[:max_chars] + ("..." if len(raw) > max_chars else "")
    end = start + len(needle)
    head = max(0, start - 15)
    tail = min(len(raw), end + 35)
    marked = f"{raw[head:start]}<mark>{raw[start:end]}</mark>{raw[end:tail]}"
    prefix = "..." if head > 0 else ""
    suffix = "..." if tail < len(raw) else ""
    return f"{prefix}{marked}{suffix}"


def _dialogue_key(source: str, source_id: str) -> tuple[str, str]:
    """台词库的统一主键清洗：与存储层 `comic_dir()` 定位目录用的是同一套字符集。

    写行、增量元数据查表、删除三处必须走同一个函数，否则任一处用了未清洗的入参，
    同一本书就会在索引里挂到两个键上，删除时只清得掉一个。
    """

    return normalize_library_name(source), normalize_library_name(source_id)


def _ocr_source_state(data_dir: Path, comic_dir: Path) -> tuple[list[Path], str, dict[Path, Path]]:
    """文件清单与 album 共同决定增量；删除、替换、保留旧 mtime 的复制也能感知。"""
    pages_dir = comic_dir / "pages"
    for directory in (data_dir / "library", comic_dir.parent, comic_dir, pages_dir):
        if directory.is_symlink():
            raise ValueError(f"台词同步目录不能是符号链接: {directory}")
    all_files = scan_files(pages_dir, (".ocr.json", *image_extensions()))
    files = [file for file in all_files if file.name.lower().endswith(".ocr.json")]
    entries = [(file.relative_to(comic_dir).as_posix(), file_stamp(file, root=data_dir)) for file in all_files]
    images: dict[Path, Path] = {}
    for image in all_files:
        if image.name.lower().endswith(".ocr.json"):
            continue
        sidecar = image.with_name(f"{image.stem}.ocr.json")
        if sidecar in images:
            raise ValueError(f"同名画页导致 OCR 原图有歧义: {image}")
        images[sidecar] = image
    album = comic_dir / "album.json"
    try:
        album_stamp = file_stamp(album, root=data_dir)
    except FileNotFoundError:
        album_stamp = None
    signature = hashlib.sha256(
        json.dumps([1, CLASSIFICATION_VERSION, entries, album_stamp], separators=(",", ":")).encode()
    ).hexdigest()
    return files, signature, images


def comic_dialogues_need_sync(source: str, source_id: str, *, sync_vectors: bool = True) -> bool:
    """给分批 CLI 判断待更新的本；已完成的本不占册数预算，未启用模型不反复排队。"""
    from .. import embedding

    source, source_id = _dialogue_key(source, source_id)
    data = get_data_dir().resolve()
    signature = _ocr_source_state(data, data / "library" / source / source_id)[1]
    with get_dialogue_db() as conn:
        row = conn.execute(
            "SELECT * FROM comic_ocr_sync_meta WHERE source = ? AND source_id = ?", (source, source_id)
        ).fetchone()
    if row is None or row["source_signature"] != signature:
        return True
    return (
        sync_vectors
        and embedding.dim() is not None
        and (
            row["vector_source_signature"] != signature or row["vector_model_signature"] != embedding.model_signature()
        )
    )


def sync_comic_dialogues(
    source: str, source_id: str, force: bool = False, *, sync_vectors: bool = True, strict_vectors: bool = False
) -> int:
    """逐页整理到临时 SQLite 表，再事务替换单本索引；坏资产不发布部分结果。

    关键词和向量分别记录完成状态。关键词增量命中也可补建失败向量，模型缺失保持
    关键词可用；实际编码或写库失败上抛，让 CLI 回报失败并允许普通重跑恢复。
    """
    source, source_id = _dialogue_key(source, source_id)
    data_resolved = get_data_dir().resolve()
    comic_dir = data_resolved / "library" / source / source_id
    ocr_files, source_signature, images = _ocr_source_state(data_resolved, comic_dir)
    with get_dialogue_db() as conn:
        conn.execute("BEGIN")
        row = conn.execute(
            "SELECT source_signature, dialogue_count FROM comic_ocr_sync_meta WHERE source = ? AND source_id = ?",
            (source, source_id),
        ).fetchone()
        expected_version = conn.execute("SELECT version FROM comic_dialogue_vectors_version WHERE id = 1").fetchone()[0]
    if not force and row and row["source_signature"] == source_signature:
        if sync_vectors:
            _sync_dialogue_vectors(source, source_id, source_signature, strict=strict_vectors)
        return int(row["dialogue_count"])

    page_map: dict[str, int] = {}
    album = comic_dir / "album.json"
    if album.exists():
        meta = read_json(album, root=data_resolved)
        if not isinstance(meta, dict) or not isinstance(meta.get("pages", []), list):
            raise ValueError(f"页码映射损坏，未更新索引: {album}")
        pages = meta.get("pages", [])
        stem_indices: dict[str, list[int]] = {}
        for page in pages:
            if not isinstance(page, dict) or page.get("index") is None:
                raise ValueError(f"画页映射损坏，未更新索引: {album}")
            index = int(page["index"])
            stem = Path(page.get("file", "")).stem
            chapter = page.get("chapter", "")
            page_map[f"{chapter}/{stem}" if chapter else stem] = index
            stem_indices.setdefault(stem, []).append(index)
        # 历史扁平目录可按唯一文件名定位；跨话同名页不允许猜测。
        for stem, indices in stem_indices.items():
            if len(indices) == 1:
                page_map[stem] = indices[0]

    # temp_store=FILE：按页暂存，避免保留整本 Python 对象；临时表与连接一起释放。
    with get_dialogue_db() as conn:
        conn.execute("PRAGMA temp_store = FILE")
        conn.execute("PRAGMA temp.cache_size = -2048")
        conn.execute(
            "CREATE TEMP TABLE staged_dialogues (source, source_id, page_index, bubble_id, text, lang, "
            "box_json, reading_order, kind, text_norm)"
        )
        count = unverified_pages = 0
        for file in ocr_files:
            payload = read_sidecar(file, root=data_resolved)
            unverified_pages += not verify_source_image(payload, images.get(file), root=data_resolved)
            bubbles = payload["bubbles"]
            stem = file.name[:-9]
            relative = file.relative_to(comic_dir / "pages").with_name(stem).as_posix()
            page_index = payload.get("page_index", payload.get("page"))
            if page_index is None:
                page_index = page_map.get(relative)
            if page_index is None:
                if page_map:
                    raise ValueError(f"伴生资产不在当前页码映射中，未更新索引: {file}")
                match = re.search(r"\d+", stem)
                page_index = int(match.group(0)) if match else 1
            page_index = int(page_index)
            if page_index < 1:
                raise ValueError(f"伴生资产页码必须大于 0: {file}")
            page_texts = [b["text"] for b in bubbles]
            advertisement = advertisement_page_reason(page_texts, bubbles)
            if advertisement:
                logger.info("台词分类 %s/%s 第 %d 页: %s", source, source_id, page_index, advertisement)
            records = []
            for fallback, bubble in enumerate(bubbles, start=1):
                text = bubble["text"].strip()
                kind = classify_dialogue_kind(text, is_advertisement=bool(advertisement))
                if kind is None:
                    continue
                bubble_id = bubble.get("id", fallback)
                if isinstance(bubble_id, bool) or not isinstance(bubble_id, (int, str)):
                    bubble_id = fallback
                records.append(
                    (
                        source,
                        source_id,
                        page_index,
                        bubble_id,
                        text,
                        str(bubble.get("lang") or payload.get("lang") or "zh"),
                        json.dumps(normalize_box(bubble.get("box")) or []),
                        _coerce_order_index(bubble.get("order"), fallback),
                        kind,
                        to_simplified(text),
                    )
                )
            conn.executemany("INSERT INTO staged_dialogues VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", records)
            count += len(records)
        conn.commit()
        with comic_asset_lock(data_resolved / "library", source, source_id):
            conn.execute("BEGIN IMMEDIATE")
            if (
                conn.execute("SELECT version FROM comic_dialogue_vectors_version WHERE id = 1").fetchone()[0]
                != expected_version
            ):
                raise RuntimeError(f"同步期间索引已有新提交，请重试: {source}/{source_id}")
            if _ocr_source_state(data_resolved, comic_dir)[1] != source_signature:
                raise RuntimeError(f"同步期间伴生资产、原图或页码映射发生变化，请重试: {source}/{source_id}")
            conn.execute("DELETE FROM comic_dialogues_fts WHERE source = ? AND source_id = ?", (source, source_id))
            conn.execute(
                "INSERT INTO comic_dialogues_fts (source, source_id, page_index, bubble_id, text, lang, box_json, "
                "reading_order, kind, text_norm) SELECT * FROM staged_dialogues"
            )
            conn.execute("DELETE FROM comic_dialogue_vectors WHERE source = ? AND source_id = ?", (source, source_id))
            _bump_vector_version(conn)
            conn.execute(
                "INSERT OR REPLACE INTO comic_ocr_sync_meta "
                "(source, source_id, dialogue_count, updated_at, source_signature, unverified_pages) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (source, source_id, count, int(time.time()), source_signature, unverified_pages),
            )
            conn.commit()
    if sync_vectors:
        _sync_dialogue_vectors(source, source_id, source_signature, strict=strict_vectors)
    return count


def _sync_dialogue_vectors(source: str, source_id: str, source_signature: str, *, strict: bool = False) -> None:
    """模型可用时，只补当前源签名尚未完成或模型已变更的向量。"""
    from .. import embedding

    model_signature = embedding.model_signature()
    with get_dialogue_db() as conn:
        row = conn.execute(
            "SELECT vector_source_signature, vector_model_signature FROM comic_ocr_sync_meta "
            "WHERE source = ? AND source_id = ?",
            (source, source_id),
        ).fetchone()
    if row and row["vector_source_signature"] == source_signature and row["vector_model_signature"] == model_signature:
        return
    if embedding.dim() is None:
        return
    try:
        embed_comic_dialogues(source, source_id)
    except Exception as exc:
        try:
            with get_dialogue_db() as conn:
                conn.execute(
                    "UPDATE comic_ocr_sync_meta SET vector_error = ? WHERE source = ? AND source_id = ? "
                    "AND source_signature = ? AND vector_source_signature != source_signature",
                    (type(exc).__name__, source, source_id, source_signature),
                )
        except sqlite3.Error:
            logger.warning("向量失败状态未能写入 %s/%s", source, source_id, exc_info=True)
        if strict:
            raise
        logger.warning("关键词已同步，台词向量待重试 %s/%s", source, source_id, exc_info=True)


def delete_comic_dialogues(source: str, source_id: str) -> None:
    """删除指定漫画的所有台词全文索引与增量元数据。"""
    # 入参清洗与写入端对齐：调用方可能拿 URL 参数或 album.json 字段来删，不洗就删不掉
    source, source_id = _dialogue_key(source, source_id)
    with get_dialogue_db() as conn:
        conn.execute(
            "DELETE FROM comic_dialogues_fts WHERE source = ? AND source_id = ?",
            (source, source_id),
        )
        conn.execute(
            "DELETE FROM comic_ocr_sync_meta WHERE source = ? AND source_id = ?",
            (source, source_id),
        )
        conn.execute(
            "DELETE FROM comic_dialogue_vectors WHERE source = ? AND source_id = ?",
            (source, source_id),
        )
        _bump_vector_version(conn)


def _dialogue_comics_meta_map(keys: list[tuple[str, str]], user_id: str) -> dict[tuple[str, str], sqlite3.Row]:
    """跨库轻量关联：一次拿回这些书的元数据、访客隐藏标记与本人的收藏/阅读进度。

    关键词检索与语义检索共用同一份关联，两边返回的书名/封面/作者才不会长得不一样。
    收藏与进度走 LEFT JOIN 一次取全，与 `query_comics` 同一套写法。
    """
    comics_map: dict[tuple[str, str], sqlite3.Row] = {}
    if not keys:
        return comics_map
    where_or = " OR ".join(["(ci.source = ? AND ci.source_id = ?)"] * len(keys))
    flat_params: list[str] = [p for k in keys for p in k]
    sql_ci = f"""
        SELECT
            ci.source,
            ci.source_id,
            ci.display_id,
            ci.title,
            ci.cover_indices_json,
            ci.authors_json,
            ci.hidden_from_guest,
            ci.page_count,
            ci.views,
            ci.likes,
            (uf.user_id IS NOT NULL) AS is_favorite,
            COALESCE(urp.last_page, 0) AS last_page,
            urp.updated_at AS progress_at
        FROM comics_index ci
        LEFT JOIN user_favorites uf
            ON uf.source = ci.source AND uf.source_id = ci.source_id AND uf.user_id = ?
        LEFT JOIN user_reading_progress urp
            ON urp.source = ci.source AND urp.source_id = ci.source_id AND urp.user_id = ?
        WHERE {where_or}
    """
    with get_db() as shelf_conn:
        for row in shelf_conn.execute(sql_ci, [user_id, user_id, *flat_params]).fetchall():
            comics_map[(row["source"], row["source_id"])] = row
    return comics_map


def embed_comic_dialogues(source: str, source_id: str) -> int:
    """每批编码 64 条并暂存到磁盘；完成后验证源签名并事务发布，失败可单独重试。"""
    from .. import embedding

    dim = embedding.dim()
    source, source_id = _dialogue_key(source, source_id)
    if dim is None:
        return 0
    model_signature = embedding.model_signature()
    with get_dialogue_db() as conn:
        conn.execute("BEGIN")
        meta = conn.execute(
            "SELECT source_signature FROM comic_ocr_sync_meta WHERE source = ? AND source_id = ?", (source, source_id)
        ).fetchone()
        source_signature = meta["source_signature"] if meta else ""
        vector_version = conn.execute("SELECT version FROM comic_dialogue_vectors_version WHERE id = 1").fetchone()[0]
        conn.execute("PRAGMA temp_store = FILE")
        conn.execute("PRAGMA temp.cache_size = -2048")
        conn.execute(
            "CREATE TEMP TABLE staged_vectors (source, source_id, page_index, bubble_id, dim, vec, updated_at)"
        )
        cursor = conn.execute(
            "SELECT page_index, bubble_id, text FROM comic_dialogues_fts"
            " WHERE source = :source AND source_id = :source_id AND kind = :kind"
            "  AND length(text) >= :min_chars ORDER BY rowid",
            {
                "source": source,
                "source_id": source_id,
                "kind": DIALOGUE_KIND,
                "min_chars": embedding.MIN_EMBED_CHARS,
            },
        )
        count = 0
        while rows := cursor.fetchmany(64):
            vectors = embedding.encode_documents([row["text"] for row in rows])
            if vectors is None or vectors.shape != (len(rows), dim):
                raise RuntimeError(f"台词向量编码未完成，请重试: {source}/{source_id}")
            conn.executemany(
                "INSERT INTO staged_vectors VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    (
                        source,
                        source_id,
                        int(row["page_index"]),
                        str(row["bubble_id"]),
                        dim,
                        vectors[i].tobytes(),
                        int(time.time()),
                    )
                    for i, row in enumerate(rows)
                ),
            )
            count += len(rows)
        cursor.close()
        # 释放编码期间的读快照，再用短写事务校验并发布，旧任务不能覆盖新提交。
        conn.commit()
        conn.execute("BEGIN IMMEDIATE")
        current_meta = conn.execute(
            "SELECT source_signature FROM comic_ocr_sync_meta WHERE source = ? AND source_id = ?",
            (source, source_id),
        ).fetchone()
        if (current_meta["source_signature"] if current_meta else "") != source_signature:
            raise RuntimeError(f"编码期间台词索引发生变化，请重试: {source}/{source_id}")
        if embedding.model_signature() != model_signature:
            raise RuntimeError("编码期间语义模型发生变化，请重试")
        if (
            conn.execute("SELECT version FROM comic_dialogue_vectors_version WHERE id = 1").fetchone()[0]
            != vector_version
        ):
            raise RuntimeError(f"编码期间向量索引发生变化，请重试: {source}/{source_id}")
        conn.execute("DELETE FROM comic_dialogue_vectors WHERE source = ? AND source_id = ?", (source, source_id))
        conn.execute("INSERT INTO comic_dialogue_vectors SELECT * FROM staged_vectors")
        conn.execute(
            "UPDATE comic_ocr_sync_meta SET vector_source_signature = ?, vector_model_signature = ?, vector_error = '' "
            "WHERE source = ? AND source_id = ? AND source_signature = ?",
            (source_signature, model_signature, source, source_id, source_signature),
        )
        _bump_vector_version(conn)
    return count


def rebuild_dialogue_vectors() -> dict[str, Any]:
    """全库重建台词向量：编码器就绪时把每条对白重新过一遍模型。"""
    from .. import embedding

    dim = embedding.dim()
    if dim is None:
        return {"ok": False, "reason": "encoder_unavailable", "encoded": 0, "comics": 0}
    with get_dialogue_db() as conn:
        books = conn.execute(
            "SELECT DISTINCT source, source_id FROM comic_dialogues_fts WHERE kind = :kind",
            {"kind": DIALOGUE_KIND},
        ).fetchall()
    encoded = failed = 0
    for b in books:
        try:
            encoded += embed_comic_dialogues(b["source"], b["source_id"])
        except Exception as exc:
            failed += 1
            logger.warning("台词向量重建失败 %s/%s: %s", b["source"], b["source_id"], exc)
    logger.info("台词向量重建完成：%d 本 / %d 条", len(books), encoded)
    return {
        "ok": failed == 0,
        "reason": "partial_failure" if failed else "",
        "encoded": encoded,
        "comics": len(books),
        "dim": dim,
    }


def _vector_status(conn: sqlite3.Connection | None = None) -> tuple[dict[str, Any], tuple[Any, ...]]:
    """在同一读快照内读取版本和维度，缓存不跨向量提交版本复用。"""
    from .. import embedding

    if conn is None:
        with get_dialogue_db() as connection:
            return _vector_status(connection)
    dim = embedding.dim()
    row = conn.execute(
        "SELECT count(*) AS n, count(DISTINCT dim) AS dims, max(dim) AS dim,"
        " (SELECT version FROM comic_dialogue_vectors_version WHERE id = 1) AS version"
        " FROM comic_dialogue_vectors"
    ).fetchone()
    stored = int(row["n"] or 0)
    stored_dim = int(row["dim"] or 0) if stored else 0
    model_signature = embedding.model_signature()
    mismatched_model = (
        model_signature
        and conn.execute(
            "SELECT 1 FROM comic_ocr_sync_meta WHERE vector_source_signature != '' "
            "AND vector_model_signature != ? LIMIT 1",
            (model_signature,),
        ).fetchone()
    )
    if dim is None:
        reason = "encoder_unavailable"
    elif stored == 0:
        reason = "vectors_missing"
    elif row["dims"] > 1 or stored_dim != dim:
        reason = "dim_mismatch"
    elif mismatched_model:
        reason = "model_mismatch"
    else:
        reason = ""
    status = {"available": reason == "", "reason": reason, "vectors": stored, "dim": stored_dim or (dim or 0)}
    return status, (str(get_dialogue_db_path()), row["version"], stored_dim, model_signature)


def dialogue_vector_status() -> dict[str, Any]:
    """馆长/本机使用的编码进度；不向访客搜索响应暴露全库或隐藏本数量。"""
    from .. import embedding

    with get_dialogue_db() as conn:
        conn.execute("BEGIN")
        status = _vector_status(conn)[0]
        progress = conn.execute(
            "WITH eligible AS (SELECT DISTINCT source, source_id FROM comic_dialogues_fts "
            "WHERE kind = ? AND length(text) >= ?) "
            "SELECT count(*) AS eligible_comics, "
            "coalesce(sum(m.vector_source_signature != m.source_signature OR m.vector_model_signature != ? "
            "OR m.source_signature IS NULL), 0) AS pending_comics, "
            "coalesce(sum(m.vector_error != ''), 0) AS failed_comics, "
            "coalesce(sum(m.vector_model_signature != '' AND m.vector_model_signature != ?), 0) AS model_mismatch_comics "
            "FROM eligible e LEFT JOIN comic_ocr_sync_meta m USING (source, source_id)",
            (DIALOGUE_KIND, embedding.MIN_EMBED_CHARS, embedding.model_signature(), embedding.model_signature()),
        ).fetchone()
        unverified = conn.execute("SELECT coalesce(sum(unverified_pages), 0) FROM comic_ocr_sync_meta").fetchone()[0]
    status.update(dict(progress))
    status.update(complete=progress["pending_comics"] == 0, unverified_pages=unverified)
    return status


_VECTOR_CACHE: tuple[Any, ...] | None = None
_VECTOR_CACHE_LOCK = threading.Lock()
_VECTOR_CACHE_MAX_BYTES = 32 * 1024 * 1024
_VECTOR_SCAN_BATCH = 1024


def _bump_vector_version(conn: sqlite3.Connection) -> None:
    """向量和失效版本在同一事务提交。"""
    conn.execute("UPDATE comic_dialogue_vectors_version SET version = version + 1 WHERE id = 1")


def _vector_chunks(conn: sqlite3.Connection, stamp: tuple[Any, ...], dim: int, count: int):
    """小库缓存受预算约束，大库每次只读取一个块；不用全库 BLOB 副本和分数数组。"""
    import numpy as np

    global _VECTOR_CACHE
    estimated = count * (dim * 4 + 256)
    if estimated <= _VECTOR_CACHE_MAX_BYTES:
        with _VECTOR_CACHE_LOCK:
            cache = _VECTOR_CACHE
            if cache is None or cache[0] != stamp:
                keys = []
                matrix = np.empty((count, dim), dtype=np.float32)
                cursor = conn.execute(
                    "SELECT rowid, source, source_id, page_index, bubble_id, vec FROM comic_dialogue_vectors "
                    "WHERE dim = ? ORDER BY rowid",
                    (dim,),
                )
                offset = 0
                while rows := cursor.fetchmany(_VECTOR_SCAN_BATCH):
                    for row in rows:
                        keys.append(
                            (
                                row["rowid"],
                                (row["source"], row["source_id"], int(row["page_index"]), str(row["bubble_id"])),
                            )
                        )
                        matrix[offset] = np.frombuffer(row["vec"], dtype=np.float32)
                        offset += 1
                cache = stamp, keys, matrix
                _VECTOR_CACHE = cache
        for offset in range(0, count, _VECTOR_SCAN_BATCH):
            yield cache[1][offset : offset + _VECTOR_SCAN_BATCH], cache[2][offset : offset + _VECTOR_SCAN_BATCH]
        return
    with _VECTOR_CACHE_LOCK:
        _VECTOR_CACHE = None
    cursor = conn.execute(
        "SELECT rowid, source, source_id, page_index, bubble_id, vec FROM comic_dialogue_vectors "
        "WHERE dim = ? ORDER BY rowid",
        (dim,),
    )
    while rows := cursor.fetchmany(_VECTOR_SCAN_BATCH):
        keys = [
            (row["rowid"], (row["source"], row["source_id"], int(row["page_index"]), str(row["bubble_id"])))
            for row in rows
        ]
        matrix = np.stack([np.frombuffer(row["vec"], dtype=np.float32) for row in rows])
        yield keys, matrix


def search_dialogues_semantic(
    query: str,
    source: str | None = None,
    limit: int = 20,
    is_guest: bool = False,
    user_id: str = "",
) -> dict[str, Any]:
    """分块精确余弦召回，先过滤权限，再有界保留最佳画页；同分按入库顺序。

    状态、向量扫描及文字回表共享一个 SQLite 读快照，防止并发同步混用旧分数和新文字。
    仅缓存小库矩阵，权限每请求重新读取；大库以内存块及候选页预算换取额外磁盘读取。
    """
    from .. import embedding

    with get_dialogue_db() as conn:
        conn.execute("BEGIN")
        status, stamp = _vector_status(conn)
        if not status["available"]:
            return {"results": [], "available": False, "reason": status["reason"]}
        clean_query = (query or "").strip()
        if len(clean_query) < 2:
            return {"results": [], "available": True, "reason": "query_too_short"}
        qv = embedding.encode_query(clean_query)
        if qv is None:
            return {"results": [], "available": False, "reason": "encoder_unavailable"}
        limit = max(1, min(int(limit), 100))
        fetch_limit = min(max(limit * 5, 50), 200)
        allowed = None
        if is_guest:
            with get_db() as shelf:
                allowed = {
                    (row["source"], row["source_id"])
                    for row in shelf.execute("SELECT source, source_id FROM comics_index WHERE hidden_from_guest = 0")
                }
        candidates: dict[tuple[str, str, int], tuple[float, int, tuple[str, str, int, str]]] = {}
        for keys, matrix in _vector_chunks(conn, stamp, int(qv.shape[0]), status["vectors"]):
            scores = matrix @ qv
            for (rowid, key), score in zip(keys, scores, strict=True):
                if source and key[0] != source:
                    continue
                if allowed is not None and key[:2] not in allowed:
                    continue
                item = float(score), rowid, key
                previous = candidates.get(key[:3])
                if previous is None or (item[0], -item[1]) > (previous[0], -previous[1]):
                    candidates[key[:3]] = item
            candidates = {
                item[2][:3]: item
                for item in sorted(candidates.values(), key=lambda item: (-item[0], item[1]))[:fetch_limit]
            }
        hits = sorted(candidates.values(), key=lambda item: (-item[0], item[1]))
        pages = {item[2][:3] for item in hits}
        texts = {}
        if pages:
            clause = " OR ".join(["(f.source = ? AND f.source_id = ? AND f.page_index = ?)"] * len(pages))
            flat = [part for key in pages for part in key]
            for row in conn.execute(
                "SELECT f.source, f.source_id, f.page_index, f.bubble_id, f.text, f.lang, f.box_json "
                f"FROM comic_dialogues_fts f WHERE ({clause}) AND f.kind = ?",
                [*flat, DIALOGUE_KIND],
            ):
                texts[(row["source"], row["source_id"], int(row["page_index"]), str(row["bubble_id"]))] = row
        comics_map = _dialogue_comics_meta_map(sorted({item[2][:2] for item in hits}), user_id)
        results = []
        for similarity, _, key in hits:
            row = texts.get(key)
            if row is None:
                continue
            ci = comics_map.get(key[:2])
            if is_guest and (ci is None or ci["hidden_from_guest"]):
                continue
            results.append(
                {
                    "source": key[0],
                    "source_id": key[1],
                    **_dialogue_book_fields(key[0], key[1], ci),
                    "page_index": key[2],
                    "bubble_id": row["bubble_id"],
                    "text": row["text"] or "",
                    "box": json.loads(row["box_json"]),
                    "lang": row["lang"] or "zh",
                    "similarity": round(similarity, 4),
                }
            )
            if len(results) >= limit:
                break
        return {"results": results, "available": True, "reason": ""}


def _safe_json_list(raw: Any) -> list[Any]:
    """元数据里的 JSON 数组字段：脏值一律退化成空表，不为了它把整次检索打断。"""
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except Exception:
        return []
    return value if isinstance(value, list) else []


def _dialogue_book_fields(src: str, sid: str, ci: sqlite3.Row | None) -> dict[str, Any]:
    """台词检索结果里按书派生的字段，关键词与语义两个出口共用；元数据缺失时退回书号本身。"""
    cover_indices = _safe_json_list(ci["cover_indices_json"]) if ci else []
    return {
        "display_id": ci["display_id"] if ci and ci["display_id"] else sid,
        "title": ci["title"] if ci and ci["title"] else sid,
        "cover": f"/api/library/{src}/{sid}/covers/{cover_indices[0] if cover_indices else 0}/file",
        "authors": _safe_json_list(ci["authors_json"]) if ci else [],
    }


def cleanup_orphan_comic_dialogues(data_dir: Path | None = None) -> int:
    """清理已从磁盘物理删除但仍残留在 FTS5、向量与元数据中的孤儿对白索引。"""
    if data_dir is None:
        data_dir = get_data_dir()
    data_resolved = data_dir.resolve()
    with get_dialogue_db() as conn:
        rows = conn.execute("SELECT DISTINCT source, source_id FROM comic_dialogues_fts").fetchall()

    to_delete: list[tuple[str, str]] = []
    for r in rows:
        src, sid = r["source"], r["source_id"]
        candidates = [
            data_resolved / "library" / src / sid,
            data_resolved / src / sid,
        ]
        if not any(c.is_dir() for c in candidates):
            to_delete.append((src, sid))

    if not to_delete:
        return 0

    with get_dialogue_db() as conn:
        for src, sid in to_delete:
            conn.execute("DELETE FROM comic_dialogues_fts WHERE source = ? AND source_id = ?", (src, sid))
            conn.execute("DELETE FROM comic_ocr_sync_meta WHERE source = ? AND source_id = ?", (src, sid))
            conn.execute("DELETE FROM comic_dialogue_vectors WHERE source = ? AND source_id = ?", (src, sid))
            logger.info("Cleaned orphan dialogue index for deleted comic %s/%s", src, sid)
        _bump_vector_version(conn)
    return len(to_delete)


def _parse_metric_count(value: Any) -> int | None:
    """把 provider 侧的 "209K" / "9.9M" / "102" / "" 解析成整数；解析不出来回报 None。

    `comics_index.views` / `likes` 是上游站点的展示字符串，不是数字列。认不出就当"没有这个信号"，
    绝不当成 0：本地导入的本子没有站点热度，算成 0 阅读量等于替它们编一个。
    """
    text = str(value or "").strip().replace(",", "")
    if not text:
        return None
    m = re.fullmatch(r"(\d+(?:\.\d+)?)([km]?)", text, re.IGNORECASE)
    if not m:
        return None
    multiplier = {"": 1, "k": 1_000, "m": 1_000_000}[m.group(2).lower()]
    return int(float(m.group(1)) * multiplier)


def search_dialogues(
    query: str,
    source: str | None = None,
    limit: int = 20,
    is_guest: bool = False,
    user_id: str = "",
) -> list[dict[str, Any]]:
    """Search the dialogue FTS index, ordered by relevance fused with library signals and
    aggregated to page level.

    Short queries (< 2 chars) are blocked immediately to prevent unindexed table scans.
    Only `dialogue` rows surface here: 书名页/版权页/后记等副文本照样入库（kind='paratext'，
    供取料与语义召回使用），但它们不是台词，不该出现在台词检索结果里。

    Args:
        query: Full-text search string (folded once by `to_simplified`, matching the indexed `text_norm`).
        source: Optional source filter.
        limit: Maximum number of matched pages to return (1..100, default 20).
        is_guest: When True, filters out dialogue results from hidden_from_guest comics.
        user_id: Viewer identity used **for ordering only** — its favorites/reading progress
            feed the business signals below. Empty string or a user with no history simply
            yields zero lift, which is the "无信号退回纯相关度" case.

    Returns:
        One entry per matched page (at most `limit`), each carrying the page's best-scoring
        bubble as the representative snippet/box, `other_boxes` with up to `MAX_PAGE_BOXES - 1`
        further matched bubbles on that page for the reader to outline at once, plus
        `bubble_count` — how many bubbles on that page matched within the fetched candidate
        pool (not a corpus-wide total) — and `rank_score`, the representative bubble's relevance
        min-max normalized **within the caller-visible rows of this candidate pool** (0..1, higher
        is more relevant; only comparable inside one query, never across queries).
        3+ 字符的查询走 text_norm 上的 trigram 倒排并按 bm25 排序；2 字查询产不出任何
        trigram token，只能走 LIKE 扫描（按 词频 ÷ 文本长度 近似排序，即 bm25 中真正
        区分候选的那两项）。两条都在归一列上比，所以繁简输入命中同一批语料。

        截断留谁由 `rank_score` 加业务信号决定（推导见 `_rank_dialogue_pages` 与 ADR 0017 决策 9）。
        `bubble_count` 与身份无关；`rank_score` 的标尺只取调用者看得见的行，访客与馆长可能拿到
        不同的分数与顺序（错题本 #139 的保密例外）。
    """
    clean_query = query.strip()
    # 短词全表扫描防爆守卫：少于 2 个字符直接阻断，杜绝无索引全表扫描
    if len(clean_query) < 2:
        return []

    # 只认一个归一 needle：写入侧已折成简体，查询走同一张 1:1 表自然汇合（ADR 0017 2026-09-23 修订）
    needle = to_simplified(clean_query)
    limit = max(1, min(int(limit), 100))

    diag_rows: list[sqlite3.Row] = []
    # 候选池不按身份分档：bubble_count 是池内计数，池大小不同，同一页在两种身份下的命中数就不同
    fetch_limit = min(max(limit * 5, 50), 200)

    with get_dialogue_db() as conn:
        if len(needle) >= 3:
            # 只有走 MATCH 的这一支有 bm25 分数可用；trigram 索引键是三字窗口，
            # 故 2 字 needle 进不了倒排、只能走下面的 LIKE。3 字以上 MATCH 为空就是真没有：
            # trigram 覆盖全部三字子串，LIKE 再扫一遍全表也只会同样 0 行。
            # bm25 越相关越负，这里取负换成"越大越相关"，与 LIKE 那条同向，才能叠业务信号。
            # 命中的是归一列，摘要由 _make_snippet 在原文上定位，不用 SQL snippet()。
            sql_match = """
                SELECT
                    f.source,
                    f.source_id,
                    f.page_index,
                    f.bubble_id,
                    f.text,
                    f.text_norm,
                    f.lang,
                    f.box_json,
                    -bm25(comic_dialogues_fts) AS rank_score
                FROM comic_dialogues_fts f
                WHERE f.text_norm MATCH :needle
                  AND f.kind = :kind
                  AND (:source IS NULL OR f.source = :source)
                ORDER BY rank_score DESC, f.page_index, f.bubble_id
                LIMIT :fetch_limit
            """
            try:
                diag_rows = conn.execute(
                    sql_match,
                    {
                        "needle": '"' + needle.replace('"', '""') + '"',
                        "source": source,
                        "kind": DIALOGUE_KIND,
                        "fetch_limit": fetch_limit,
                    },
                ).fetchall()
            except sqlite3.OperationalError:
                # 含 NUL 这类 FTS5 解析不了的查询：当作无命中，不让检索端点 500
                diag_rows = []
        else:
            # :like 是带通配的匹配式，:term 是数出现次数的原串，不能共用一个绑定。
            # LIKE 不分 ASCII 大小写而 replace() 分，所以两边都折成小写再数（lower() 只折 ASCII，长度不变）。
            params: dict[str, Any] = {
                "like": f"%{_escape_like(needle)}%",
                "term": needle.translate(_ASCII_LOWER),
                "source": source,
                "kind": DIALOGUE_KIND,
                "fetch_limit": fetch_limit,
            }
            # 2 字查询没有 bm25 可用，手工补上其中真正区分候选的两项：词频 ÷ 文本长度
            # （IDF 对同一次查询是常数，省略）。词频按字符数计：length 差值 = 出现次数 × needle 长度。
            like_rank = (
                "(CAST(length(f.text_norm) - length(replace(lower(f.text_norm), :term, '')) AS REAL)"
                " / max(length(f.text_norm), 1))"
            )
            sql_like = f"""
                SELECT
                    f.source,
                    f.source_id,
                    f.page_index,
                    f.bubble_id,
                    f.text,
                    f.text_norm,
                    f.lang,
                    f.box_json,
                    {like_rank} AS rank_score
                FROM comic_dialogues_fts f
                WHERE (f.text_norm LIKE :like ESCAPE '\\')
                  AND f.kind = :kind
                  AND (:source IS NULL OR f.source = :source)
                ORDER BY {like_rank} DESC,
                         f.page_index, f.bubble_id
                LIMIT :fetch_limit
            """
            diag_rows = conn.execute(sql_like, params).fetchall()

    if not diag_rows:
        return []

    unique_keys = list({(r["source"], r["source_id"]) for r in diag_rows})
    comics_map = _dialogue_comics_meta_map(unique_keys, user_id)

    # 聚合到页：diag_rows 已按相关度降序，某页首次出现的那条即该页最高分代表句，
    # 之后再出现的同页气泡只累加命中数，不另起一行（检索单元是气泡，展示单元是页）。
    # bubble_count 因此是候选池（fetch_limit 行）内的计数，不是全库该页命中总数。
    # 这里不按 limit 收口：聚完的全部页才是排名的候选集，先截断再融合等于让 bm25 独裁。
    page_hits: dict[tuple[str, str, int], dict[str, Any]] = {}
    visible_scores: list[float] = []
    for r in diag_rows:
        src, sid = r["source"], r["source_id"]
        ci = comics_map.get((src, sid))
        if is_guest and ci and ci["hidden_from_guest"]:
            continue
        if is_guest and not ci:
            continue
        visible_scores.append(float(r["rank_score"]))

        page_idx = int(r["page_index"])
        # 唯一的写入口 sync_comic_dialogues 已把 box 归一成 4 个有限数值或空表，读侧不再重复校验
        box: list[float] = json.loads(r["box_json"])

        key = (src, sid, page_idx)
        hit = page_hits.get(key)
        if hit is not None:
            hit["bubble_count"] += 1
            # 同页其余命中气泡按相关度顺序补足，供阅读器一次画全；上限外的高频页只多算计数
            extra: list[list[float]] = hit["other_boxes"]
            if box and len(extra) < MAX_PAGE_BOXES - 1:
                extra.append(box)
            continue
        raw_text = r["text"] or ""
        page_hits[key] = {
            "source": src,
            "source_id": sid,
            **_dialogue_book_fields(src, sid, ci),
            "page_index": page_idx,
            "bubble_id": r["bubble_id"],
            "bubble_count": 1,
            "text": raw_text,
            "snippet": _make_snippet(raw_text, r["text_norm"] or "", needle),
            "box": box,
            "other_boxes": [],
            "lang": r["lang"] or "zh",
            "rank_score": float(r["rank_score"]),
        }

    pages = list(page_hits.values())
    if not pages:
        return []
    # 归一标尺只取调用者看得见的那些候选行的极值：若把隐藏本的行也算进去，访客看到的最高分
    # 一旦低于 1.0，就等于告诉他"某本对你隐藏的书里有更贴切的这句话"（错题本 #139 的保密例外）。
    # 代价是同一句查询，访客与馆长拿到的 rank_score 可能不同；它本就只在本次候选内部可比。
    pool_lo = min(visible_scores)
    pool_hi = max(visible_scores)
    return _rank_dialogue_pages(pages, comics_map, pool_lo, pool_hi)[:limit]


# 业务信号权重：四项合计封顶 0.5，也就是相关度差 0.5 以上翻不了盘（见 _rank_dialogue_pages）
DIALOGUE_SIGNAL_WEIGHTS = {"heat": 0.15, "favorite": 0.15, "finished": 0.10, "recent": 0.10}
# "最近阅读"的衰减窗口：30 天前读过的就不再算新
DIALOGUE_RECENT_WINDOW_DAYS = 30.0


def _comic_signals(ci: sqlite3.Row | None, now: float) -> tuple[float | None, float, float, float]:
    """从 comics_index 的一行读出四项业务信号的原始值：热度原始分、完读率、收藏、最近阅读衰减。

    返回的热度是 `log10(1+views) + log10(1+likes)` 的未归一原始值，`None` 表示这本没有热度可谈
    （本地导入的本子 views/likes 都是空串）；后三项天然是 0..1，不需要再归一。
    """
    if ci is None:
        return None, 0.0, 0.0, 0.0
    views = _parse_metric_count(ci["views"])
    likes = _parse_metric_count(ci["likes"])
    heat = None if (views is None and likes is None) else math.log10(1 + (views or 0)) + math.log10(1 + (likes or 0))
    page_count = int(ci["page_count"] or 0)
    last_page = int(ci["last_page"] or 0)
    finished = min(1.0, last_page / page_count) if page_count > 0 and last_page > 0 else 0.0
    favorite = 1.0 if ci["is_favorite"] else 0.0
    progress_at = ci["progress_at"]
    recent = 0.0
    if progress_at:
        days = max(0.0, (now - float(progress_at)) / 86400.0)
        recent = max(0.0, 1.0 - days / DIALOGUE_RECENT_WINDOW_DAYS)
    return heat, finished, favorite, recent


def _rank_dialogue_pages(
    pages: list[dict[str, Any]],
    comics_map: dict[tuple[str, str], sqlite3.Row],
    pool_lo: float,
    pool_hi: float,
    now: float | None = None,
) -> list[dict[str, Any]]:
    """先把相关度按候选池极值 min-max 归一，再叠业务信号，按最终分降序回报（同分保持原次序）。

    为什么必须叠：2 字查询的"词频 ÷ 文本长度"很粗，前几十名常整片打平，不叠信号的话截断留谁
    只由偶然次序决定（ADR 0017 决策 9）。

    `pool_lo` / `pool_hi` 是调用者**看得见的候选行**的极值（调用方已按身份过滤，理由见调用处），
    页级代表分恒落在该区间内，所以 `rank_score` 稳定在 0..1。

    四项信号（权重见 `DIALOGUE_SIGNAL_WEIGHTS`）：热度取 `views`/`likes` 对数后在**本次池内出现过的
    那些书**之间 min-max（跨池、跨查询的绝对值没有可比性）；完读率与收藏来自本人的阅读进度与收藏；
    最近阅读按 30 天线性衰减。全部是非负抬升且合计 ≤ 0.5，所以业务信号只在相关度接近时决定成败，
    不会把一本明显不相关的本子顶上来；没有任何信号时抬升恒为 0，顺序就退回纯相关度。
    """
    if not pages:
        return pages
    if now is None:
        now = time.time()

    span = pool_hi - pool_lo
    for p in pages:
        # 两条检索路径的原始分量纲完全不同（MATCH 支是取负后的 bm25，LIKE 支是词频÷文本长度），
        # 只有先在同一池内归一，才加得动后面那些 0..1 的信号
        p["rank_score"] = 1.0 if span <= 0 else (p["rank_score"] - pool_lo) / span

    weights = DIALOGUE_SIGNAL_WEIGHTS
    book_signals: dict[tuple[str, str], tuple[float | None, float, float, float]] = {}
    for p in pages:
        key = (p["source"], p["source_id"])
        book_signals.setdefault(key, _comic_signals(comics_map.get(key), now))
    heat_values = [s[0] for s in book_signals.values() if s[0] is not None]
    heat_lo = min(heat_values) if heat_values else 0.0
    heat_span = (max(heat_values) - heat_lo) if heat_values else 0.0

    ranked: list[tuple[float, int, dict[str, Any]]] = []
    for i, p in enumerate(pages):
        heat, finished, favorite, recent = book_signals[(p["source"], p["source_id"])]
        heat_norm = 0.0 if heat is None or heat_span <= 0 else (heat - heat_lo) / heat_span
        lift = (
            weights["heat"] * heat_norm
            + weights["favorite"] * favorite
            + weights["finished"] * finished
            + weights["recent"] * recent
        )
        ranked.append((p["rank_score"] + lift, i, p))
    # 显式带原次序做第二键：sort 稳定，但这里要的是"同分 = 归一前谁先到谁在前"
    ranked.sort(key=lambda t: (-t[0], t[1]))
    return [t[2] for t in ranked]


STORY_CONTEXT_MAX_LINES = 400
STORY_CONTEXT_MAX_PAGES = 200


def get_story_context(
    source: str,
    source_id: str,
    page_start: int,
    page_end: int,
    budget_lines: int = 120,
) -> dict[str, Any]:
    """按页码区间取原始台词物料，供下游生成管线使用（与台词检索同为一份索引的另一个出口）。

    按 `(page_index, reading_order)` 的剧情原序给连续切片：不收关键词、不吐展示态字段，撞预算必须回报
    `truncated`；`reading_order` 有空洞、不输出 `speaker`。边界纪律与已知限制见 ADR 0017 决策 8。

    Args:
        source: 图源平台标识（如 'jm' | 'local' | 'picacg'）。
        source_id: 作品唯一 ID；与 source 组成复合键，单靠它不唯一定位一本书。
        page_start: 起始全局页号（1 起，含）。
        page_end: 结束全局页号（含）。
        budget_lines: 预算行数，即本次最多返回多少条台词。

    Returns:
        {'lines': [{'line_id', 'page_index', 'reading_order', 'text'}],
         'boxes': [{'line_id', 'box'}],
         'truncated': bool, 'budget_lines': int, 'requested_pages': [p0, p1]}
        `truncated` 为真表示区间内还有没返回的内容：要么预算用尽，要么页跨度被夹到 200 页。
        `requested_pages` 是实际覆盖的页区间，跨度被夹时比请求的短，下游据它接着往后取。
    """
    source, source_id = _dialogue_key(source, source_id)
    p0 = max(1, int(page_start))
    p1 = max(p0, int(page_end))
    # 区间上限先夹页号，再夹预算：一次取料最多跨 200 页 / 400 行，杜绝"整本书一把梭"
    pages_clamped = p1 > p0 + STORY_CONTEXT_MAX_PAGES - 1
    p1 = min(p1, p0 + STORY_CONTEXT_MAX_PAGES - 1)
    budget = max(1, min(int(budget_lines), STORY_CONTEXT_MAX_LINES))

    with get_dialogue_db() as conn:
        rows = conn.execute(
            """
            SELECT page_index, bubble_id, reading_order, text, box_json
            FROM comic_dialogues_fts
            WHERE source = :source AND source_id = :source_id
              AND page_index BETWEEN :p0 AND :p1
              AND kind = :kind
            ORDER BY page_index, reading_order, bubble_id
            LIMIT :cap
            """,
            {
                "source": source,
                "source_id": source_id,
                "p0": p0,
                "p1": p1,
                "kind": DIALOGUE_KIND,
                "cap": budget + 1,
            },
        ).fetchall()

    truncated = len(rows) > budget or pages_clamped
    lines: list[dict[str, Any]] = []
    boxes: list[dict[str, Any]] = []
    for r in rows[:budget]:
        page_index = int(r["page_index"])
        line_id = f"{page_index}:{r['bubble_id']}"
        lines.append(
            {
                "line_id": line_id,
                "page_index": page_index,
                "reading_order": int(r["reading_order"]),
                "text": r["text"],
            }
        )
        box = json.loads(r["box_json"])
        if box:
            boxes.append({"line_id": line_id, "box": box})

    return {
        "lines": lines,
        "boxes": boxes,
        "truncated": truncated,
        "budget_lines": budget,
        "requested_pages": [p0, p1],
    }
