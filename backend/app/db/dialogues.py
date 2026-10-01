from __future__ import annotations

import json
import logging
import math
import re
import sqlite3
import string
import time
from pathlib import Path
from typing import Any

from ..formatting import normalize_title
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


def _normalize_box(raw: Any) -> list[float] | None:
    """把侧车里的 box 收敛成 4 个有限数值，形状不对就整条判废。

    只判长度拦不住 4 键 dict 与嵌套四点表，放过去会在响应模型校验时让检索端点 500。
    """
    if not isinstance(raw, list) or len(raw) != 4:
        return None
    out: list[float] = []
    for v in raw:
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            return None
        f = float(v)
        if not math.isfinite(f):
            return None
        out.append(f)
    return out


def _coerce_order_index(raw: Any, fallback: int) -> int:
    """把侧车里可能畸形（浮点、字符串、1e999、dict）的序号收敛成正整数。"""
    try:
        n = int(raw)
    except (TypeError, ValueError, OverflowError):
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


DIALOGUE_KIND = "dialogue"
PARATEXT_KIND = "paratext"

# 书名页与版权页在书头，后记与通告在书尾：页位 + 特征词比几何轮廓判据可靠（ADR 0017 决策 7）
FRONT_MATTER_PAGES = 2
BACK_MATTER_PAGES = 4
# 短篇整本都是正文，位置规则对它没有意义；册页数不足此数时只认特征词。
MIN_PAGES_FOR_POSITION_RULE = 10
# 后记是成段的长文，正文页平均每句只有十来字，用它兜住没有特征词的后记页
BACK_MATTER_MEAN_LINE_CHARS = 25

# 水印与页码：真台词一定有中日文字形，纯拉丁/数字且极短的就是噪声（站点名的 OCR 变体列举不完）
_CJK_RE = re.compile(r"[぀-ヿ一-鿿＀-￯]")
NOISE_MAX_CHARS = 12

# 汉化组/发布组/平台宣传专属强特征词（简繁双轨）：涵盖制作分工、招募、社交平台、赞助打赏、APP推广与水印
_SCANLATOR_RE = re.compile(
    r"(图源|圖源|翻校|嵌字|扫图|掃圖|校对|校對|压制|壓制|汉化|漢化|初翻|招募|招新"
    r"|爱发电|愛發電|赞助|贊助|打赏|打賞|仅供交流|僅供交流|禁止商用|禁止商業|严禁商用|嚴禁商用"
    r"|qq群|加群|加羣|微信群|微信羣|交流群|交流羣|群号|羣號|微博|邮箱|郵箱|@[A-Za-z0-9]|pixiv|fanbox|twitter"
    r"|禁漫天堂|禁漫食堂|禁漫娘|拷贝漫画|拷貝漫畫"
    r"|app正式启动|app正式啟動|永久免费|永久免費|不再迷路|二维码|二維碼|qrcode|扫码|掃碼|扫码下载|掃碼下載"
    r"|presented by|凳行|尧行|印刷)",
    re.IGNORECASE,
)

# 刻意不收「我是」「禁止」这类真台词里也常见的宽词；简繁双轨支持
_PARATEXT_RE = re.compile(
    r"(图源|圖源|翻校|嵌字|扫图|掃圖|校对|校對|压制|壓制|汉化|漢化|翻译|翻譯|初翻|仅供|僅供|转载|轉載|商业|商業|邮箱|郵箱|@[A-Za-z0-9]"
    r"|https?://|www\.|pixiv|fanbox|twitter|comiket|comic\s*market|qq群|群号|羣號|加群|加羣|微信群|微信羣|交流群|交流羣|微博|爱发电|愛發電|赞助|贊助|打赏|打賞"
    r"|禁漫天堂|禁漫食堂|禁漫娘|拷贝漫画|拷貝漫畫"
    r"|app正式启动|app正式啟動|永久免费|永久免費|不再迷路|二维码|二維碼|qrcode|扫码|掃碼|扫码下载|掃碼下載"
    r"|后记|後記|前言|附录|附錄|完结感言|完結感言|番外篇|特典|商业志|商業誌|presented by|凳行|尧行|印刷)",
    re.IGNORECASE,
)


def _is_noise_line(text: str) -> bool:
    return not _CJK_RE.search(text) and len(text) <= NOISE_MAX_CHARS


def classify_dialogue_kind(
    page_index: int,
    page_count: int,
    page_texts: list[str],
    text: str,
    *,
    is_chapter_tail: bool = False,
    is_chapter_boundary: bool = False,
    is_recurring_template: bool = False,
    page_has_scanlator: bool | None = None,
    page_recurring_ratio: float = 0.0,
) -> str | None:
    """判定一条 OCR 文本的语料类别。

    Args:
        page_index: 全书拍平后的全局页号（1 起）。
        page_count: 该漫画总页数；取不到时传 0，位置规则自动失效。
        page_texts: 同一页上的全部文本，用于判断整页是否像后记。
        text: 待判定的单条文本。
        is_chapter_tail: 是否为所属章节末尾 1~2 页（兼容历史传参）。
        is_chapter_boundary: 是否为所属章节首尾 1~2 页（且该章页数 >= 8）。
        is_recurring_template: 该条文本是否为跨话/跨页高频重复模板。
        page_has_scanlator: 该页是否含有汉化组/平台广告强特征词（传入 None 时从 page_texts 现场计算）。
        page_recurring_ratio: 该页模板文本行占全页文本行的比例（0.0 ~ 1.0）。

    Returns:
        'dialogue' 分镜台词、'paratext' 书名页/版权页/后记等副文本，
        None 表示纯噪声（水印、页码、汉化组首尾页广告、重复模板），不该进索引。
    """
    if _is_noise_line(text):
        return None

    norm_text = to_simplified(text)
    # 噪声行不能替整页定性（ADR 0017 决策 7）
    meaningful_texts = [t for t in page_texts if not _is_noise_line(t)]
    norm_page_texts = [to_simplified(t) for t in meaningful_texts]

    is_boundary = is_chapter_boundary or is_chapter_tail
    has_scan = (
        page_has_scanlator
        if page_has_scanlator is not None
        else any(_SCANLATOR_RE.search(t) for t in norm_page_texts)
    )

    # 1. 单话首尾边界熔断：若处于单话首尾 1~2 页（全书封面第 1 页除外），且该页包含广告/汉化词或主要由模板构成，整页一律不入库
    if is_boundary and page_index != 1:
        if has_scan or page_recurring_ratio >= 0.5:
            return None
        if is_recurring_template:
            return None

    # 2. 纯广告海报全位置熔断：若整页所有有效行均由广告/汉化词构成（0 剧情正文），整页一律不入库
    if page_index != 1 and norm_page_texts and all(_SCANLATOR_RE.search(t) for t in norm_page_texts):
        return None

    # 3. 跨话高频重复的水印/广告模板（如全局重复出现的网站域名或赞助标语）直接丢弃
    if is_recurring_template and _SCANLATOR_RE.search(norm_text):
        return None

    # 4. 基础特征词匹配：优先识别副文本（如作者后记、版权信息、刊物说明等）
    if _PARATEXT_RE.search(norm_text):
        return PARATEXT_KIND

    # 5. 全书位置护栏（仅在全书页数 >= 10 时启用）
    if page_count >= MIN_PAGES_FOR_POSITION_RULE:
        if page_index <= FRONT_MATTER_PAGES:
            return PARATEXT_KIND
        if page_index > page_count - BACK_MATTER_PAGES and page_texts:
            mean_line_chars = sum(len(t) for t in meaningful_texts) / len(meaningful_texts) if meaningful_texts else 0
            long_form_page = mean_line_chars >= BACK_MATTER_MEAN_LINE_CHARS
            credit_page = any(_PARATEXT_RE.search(t) for t in norm_page_texts)
            if long_form_page or credit_page:
                return PARATEXT_KIND

    return DIALOGUE_KIND


def _dialogue_key(source: str, source_id: str) -> tuple[str, str]:
    """台词库的统一主键清洗：与存储层 `comic_dir()` 定位目录用的是同一套字符集。

    写行、增量元数据查表、删除三处必须走同一个函数，否则任一处用了未清洗的入参，
    同一本书就会在索引里挂到两个键上，删除时只清得掉一个。
    """

    def clean(v: object) -> str:
        s = re.sub(r"[^a-zA-Z0-9_\-\.]+", "_", str(v)).strip("._") or "_"
        while ".." in s:
            s = s.replace("..", "_")
        return s

    return clean(source), clean(source_id)


def sync_comic_dialogues(source: str, source_id: str, force: bool = False) -> int:
    """Syncs comic page OCR dialogues (*.ocr.json) into the comic_dialogues_fts table.

    Security sandbox and atomicity guarantees:
    1. Strictly sanitizes directory path symbols and bounds traversal within DATA_DIR.
    2. Atomically clears prior index rows for this comic before inserting new records.

    入库时按 classify_dialogue_kind 打上 kind：副文本只登记不检索，水印与页码直接丢弃。

    Args:
        source: Provider key (e.g., 'jm', 'picacg', 'local').
        source_id: Unique comic identifier.
        force: If True, bypasses mtime check and forces a full re-index.

    Returns:
        The total number of dialogue bubble records indexed.
    """
    safe_source, safe_id = _dialogue_key(source, source_id)
    # 找目录、写库、查元数据、删除统一用清洗后的键，否则会留下删不掉的孤儿语料（见 _dialogue_key）
    source, source_id = safe_source, safe_id

    data_dir = get_data_dir()
    data_resolved = data_dir.resolve()
    candidates = [
        data_dir / "library" / safe_source / safe_id / "pages",
        data_dir / safe_source / safe_id / "pages",
        data_dir / "library" / safe_source / safe_id,
    ]
    target_dir: Path | None = None
    for cand in candidates:
        try:
            cand_resolved = cand.resolve()
            if cand_resolved.is_relative_to(data_resolved) and cand_resolved.is_dir():
                target_dir = cand_resolved
                break
        except Exception:
            continue

    ocr_files: list[Path] = []
    if target_dir is not None:
        if target_dir.name == "pages":
            ocr_files = sorted(target_dir.glob("**/*.ocr.json"))
        else:
            pages_sub = target_dir / "pages"
            if pages_sub.is_dir():
                ocr_files = sorted(pages_sub.glob("**/*.ocr.json"))
            else:
                ocr_files = sorted(target_dir.glob("*.ocr.json"))

    latest_mtime: float = 0.0
    for f in ocr_files:
        try:
            mt = f.stat().st_mtime
            if mt > latest_mtime:
                latest_mtime = mt
        except OSError:
            pass

    # 增量检查放在解析之前：OCR 文件自上次入库以来没变就直接返回已有计数，不读不解析
    if not force:
        with get_dialogue_db() as conn:
            row = conn.execute(
                "SELECT last_synced_mtime, dialogue_count FROM comic_ocr_sync_meta WHERE source = ? AND source_id = ?",
                (source, source_id),
            ).fetchone()
            if row:
                stored_mtime = float(row["last_synced_mtime"])
                stored_count = int(row["dialogue_count"])
                # 当 OCR 文件未变动（或原本就无 OCR 文件且已同步记录为 0）时直接命中增量缓存
                if stored_mtime >= latest_mtime and (latest_mtime > 0 or stored_count == 0):
                    return stored_count

    # 读取 album.json 以便建立多章节全局页号映射与单话边界上下文
    page_map: dict[str, int] = {}
    page_to_chapter: dict[int, str] = {}
    chapter_page_map: dict[str, list[int]] = {}
    page_count = 0
    album_candidates = []
    if target_dir is not None:
        if target_dir.name == "pages":
            album_candidates.append(target_dir.parent / "album.json")
        else:
            album_candidates.append(target_dir / "album.json")
    album_candidates.append(data_dir / "library" / safe_source / safe_id / "album.json")
    for ac in album_candidates:
        try:
            ac_resolved = ac.resolve()
            if not ac_resolved.is_relative_to(data_resolved):
                continue
            if ac_resolved.is_file():
                meta_dict = json.loads(ac_resolved.read_text(encoding="utf-8"))
                pages = meta_dict.get("pages", [])
                try:
                    page_count = int(meta_dict.get("page_count") or len(pages))
                except (TypeError, ValueError, OverflowError):
                    page_count = len(pages)
                for p in pages:
                    idx_val = p.get("index")
                    f_val = p.get("file", "")
                    chap_val = p.get("chapter", "")
                    if idx_val is not None:
                        try:
                            pid = int(idx_val)
                        except (ValueError, TypeError):
                            continue
                        s = Path(f_val).stem
                        page_map[s] = pid
                        if chap_val:
                            page_map[f"{chap_val}/{s}"] = pid
                        chap_str = str(chap_val or "")
                        page_to_chapter[pid] = chap_str
                        chapter_page_map.setdefault(chap_str, []).append(pid)
                break
        except Exception:
            pass

    # 统计单话首尾 1~2 页（仅当该话页数 >= 8 时判定，防止误杀极短单篇与番外）
    MIN_CHAPTER_PAGES = 8
    chapter_boundary_page_indices: set[int] = set()
    for chap_str, p_list in chapter_page_map.items():
        if len(p_list) >= MIN_CHAPTER_PAGES:
            chapter_boundary_page_indices.update(p_list[:2])
            chapter_boundary_page_indices.update(p_list[-2:])

    # 预先解析所有 OCR 文件并提取文本，用于全局模板频次去重与整页结构分析
    parsed_ocr_items: list[dict[str, Any]] = []
    text_chapters: dict[str, set[str]] = {}
    text_pages: dict[str, set[int]] = {}

    for f in ocr_files:
        try:
            payload = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue

        page_idx: int | None = None
        if payload.get("page_index") is not None:
            try:
                page_idx = int(payload["page_index"])
            except (ValueError, TypeError, OverflowError):
                pass
        elif payload.get("page") is not None:
            try:
                page_idx = int(payload["page"])
            except (ValueError, TypeError, OverflowError):
                pass

        if page_idx is None:
            stem = f.name[:-9] if f.name.endswith(".ocr.json") else f.stem
            chap_stem = f"{f.parent.name}/{stem}"
            if chap_stem in page_map:
                page_idx = page_map[chap_stem]
            elif stem in page_map:
                page_idx = page_map[stem]
            elif stem.isdigit():
                page_idx = int(stem)
            else:
                m = re.search(r"\d+", stem)
                page_idx = int(m.group(0)) if m else 1

        top_lang = payload.get("lang") or "zh"
        bubbles = payload.get("bubbles", [])
        if not isinstance(bubbles, list):
            continue

        chap_id = page_to_chapter.get(page_idx, f.parent.name)
        raw_texts = [str(b.get("text", "")).strip() for b in bubbles if isinstance(b, dict)]
        raw_texts = [t for t in raw_texts if t]

        for t in raw_texts:
            if len(t) >= 8 and len(set(c for c in t if c.isalnum())) >= 5:
                nt = to_simplified(t)
                text_chapters.setdefault(nt, set()).add(chap_id)
                text_pages.setdefault(nt, set()).add(page_idx)

        parsed_ocr_items.append({
            "page_idx": page_idx,
            "top_lang": top_lang,
            "bubbles": bubbles,
            "page_texts": raw_texts,
        })

    # 判定为跨话/跨页高频模板的文本集合（单本内跨 >= 3 话，或跨 >= 4 页出现）
    recurring_templates: set[str] = {
        nt for nt, chaps in text_chapters.items()
        if len(chaps) >= 3 or len(text_pages.get(nt, set())) >= 4
    }

    # 若无 album.json 章节划分，退回整本首尾各 2 页作为边界兜底（全本页数 >= 8 时生效）
    if not chapter_boundary_page_indices and parsed_ocr_items:
        all_pids = sorted(set(item["page_idx"] for item in parsed_ocr_items))
        if len(all_pids) >= MIN_CHAPTER_PAGES:
            chapter_boundary_page_indices.update(all_pids[:2])
            chapter_boundary_page_indices.update(all_pids[-2:])

    records: list[tuple[str, str, int, int | str, str, str, str, int, str, str]] = []
    for item in parsed_ocr_items:
        page_idx = item["page_idx"]
        top_lang = item["top_lang"]
        bubbles = item["bubbles"]
        page_texts = item["page_texts"]

        is_boundary = page_idx in chapter_boundary_page_indices
        norm_page_texts = [to_simplified(t) for t in page_texts]
        page_has_scanlator = any(_SCANLATOR_RE.search(t) for t in norm_page_texts)

        template_count = sum(1 for t in norm_page_texts if t in recurring_templates)
        page_recurring_ratio = (template_count / len(page_texts)) if page_texts else 0.0

        for b_idx, b in enumerate(bubbles, start=1):
            if not isinstance(b, dict):
                continue
            text = str(b.get("text", "")).strip()
            if not text:
                continue
            is_rec = to_simplified(text) in recurring_templates
            kind = classify_dialogue_kind(
                page_idx,
                page_count,
                page_texts,
                text,
                is_chapter_tail=is_boundary,
                is_chapter_boundary=is_boundary,
                is_recurring_template=is_rec,
                page_has_scanlator=page_has_scanlator,
                page_recurring_ratio=page_recurring_ratio,
            )
            if kind is None:
                continue
            bubble_id = b.get("id", b_idx)
            if isinstance(bubble_id, bool) or not isinstance(bubble_id, (int, str)):
                bubble_id = b_idx
            lang = b.get("lang") or top_lang
            # 形状不合法的 box 存空数组：宁可丢坐标，不能让一行脏侧车毒化整条检索链路
            box = _normalize_box(b.get("box")) or []
            box_json = json.dumps(box, ensure_ascii=False)
            # 旧伴生文件没有 order，只能退回数组下标（其顺序为检测模型输出，并非阅读顺序）；
            # 这类文件需用 ocr_worker --force 重跑，才能拿到真正的 reading_order
            reading_order = _coerce_order_index(b.get("order"), b_idx)
            records.append(
                (
                    source,
                    source_id,
                    page_idx,
                    bubble_id,
                    text,
                    str(lang),
                    box_json,
                    reading_order,
                    kind,
                    to_simplified(text),
                )
            )

    with get_dialogue_db() as conn:
        conn.execute(
            "DELETE FROM comic_dialogues_fts WHERE source = ? AND source_id = ?",
            (source, source_id),
        )
        if records:
            conn.executemany(
                """
                INSERT INTO comic_dialogues_fts (
                    source, source_id, page_index, bubble_id, text, lang, box_json, reading_order, kind, text_norm
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                records,
            )
        conn.execute(
            """
            INSERT OR REPLACE INTO comic_ocr_sync_meta (
                source, source_id, last_synced_mtime, dialogue_count, updated_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (source, source_id, latest_mtime, len(records), int(time.time())),
        )

    # 向量重建放在 FTS 事务**外面**：模型冷启动可达秒级，扣着写锁会卡住关键词入库。
    # 失败只记日志：关键词已经提交，可选的语义腿出错不能把这次同步报成 500
    try:
        embed_comic_dialogues(source, source_id)
    except Exception as exc:
        logger.warning("台词向量重编失败 %s/%s: %s", source, source_id, exc)
    return len(records)


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
    """把一本书的对白行重编成语义向量写进 `comic_dialogue_vectors`。

    Returns:
        实际写入的向量条数。编码器不可用（没放模型、缺 numpy）时返回 0，不打断关键词链路——
        语义检索是增量能力。
    """
    from .. import embedding

    dim = embedding.dim()
    source, source_id = _dialogue_key(source, source_id)
    rows: list[sqlite3.Row] = []
    if dim is not None:
        with get_dialogue_db() as conn:
            rows = conn.execute(
                "SELECT page_index, bubble_id, text FROM comic_dialogues_fts"
                " WHERE source = :source AND source_id = :source_id AND kind = :kind"
                "  AND length(text) >= :min_chars",
                {
                    "source": source,
                    "source_id": source_id,
                    "kind": DIALOGUE_KIND,
                    "min_chars": embedding.MIN_EMBED_CHARS,
                },
            ).fetchall()
    try:
        vectors = embedding.encode_documents([r["text"] for r in rows]) if rows else None
    except Exception as exc:
        # 编码中途出错按编码器不可用处理：旧向量同样对不上刚重写的 FTS 行，要一起删掉
        logger.warning("台词向量编码失败 %s/%s: %s", source, source_id, exc)
        vectors = None
    # 编不出新向量（编码器不可用、或这本书已没有可编的对白）就把旧的一并删掉：
    # FTS 行刚被重写，留着它们就是相似度按旧文本算、展示的却是新文本
    with get_dialogue_db() as conn:
        conn.execute(
            "DELETE FROM comic_dialogue_vectors WHERE source = ? AND source_id = ?",
            (source, source_id),
        )
        if vectors is not None:
            now = int(time.time())
            conn.executemany(
                "INSERT INTO comic_dialogue_vectors (source, source_id, page_index, bubble_id, dim, vec, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    (source, source_id, int(r["page_index"]), str(r["bubble_id"]), dim,
                     vectors[i].tobytes(), now)
                    for i, r in enumerate(rows)
                ],
            )
        _bump_vector_version(conn)
    return len(rows) if vectors is not None else 0


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
    encoded = 0
    for b in books:
        try:
            encoded += embed_comic_dialogues(b["source"], b["source_id"])
        except Exception as exc:
            logger.warning("台词向量重建失败 %s/%s: %s", b["source"], b["source_id"], exc)
    logger.info("台词向量重建完成：%d 本 / %d 条", len(books), encoded)
    return {"ok": True, "reason": "", "encoded": encoded, "comics": len(books), "dim": dim}


def _vector_status() -> tuple[dict[str, Any], tuple[Any, ...]]:
    """语义腿的状态与向量矩阵的缓存戳子，一次查询同时给出。

    戳子是 (台词库路径, 写入版本号, 维度)：库路径让测试与"换库"读不到上一个库的矩阵；
    版本号记在库里，和向量写在同一个事务里推进，所以 `ocr.sh sync` 这类别的进程写完，
    服务不重启也能看到新矩阵，同一秒内重编、条数不变也不会读到旧矩阵。
    """
    from .. import embedding

    dim = embedding.dim()
    with get_dialogue_db() as conn:
        row = conn.execute(
            "SELECT count(*) AS n, count(DISTINCT dim) AS dims, max(dim) AS dim,"
            " (SELECT version FROM comic_dialogue_vectors_version) AS version"
            " FROM comic_dialogue_vectors"
        ).fetchone()
    stored = int(row["n"] or 0)
    stored_dim = int(row["dim"] or 0) if stored else 0
    if dim is None:
        reason = "encoder_unavailable"
    elif stored == 0:
        reason = "vectors_missing"
    elif row["dims"] > 1 or stored_dim != dim:
        # 换过模型（维度不同）却没重建：新旧向量混在一堆里算余弦，分数会莫名其妙
        reason = "dim_mismatch"
    else:
        reason = ""
    status = {"available": reason == "", "reason": reason, "vectors": stored, "dim": stored_dim or (dim or 0)}
    return status, (str(get_dialogue_db_path()), row["version"], stored_dim)


def dialogue_vector_status() -> dict[str, Any]:
    """语义检索这条腿现在能不能走，以及为什么不能。"""
    return _vector_status()[0]


_VECTOR_CACHE: tuple[Any, ...] | None = None


def _bump_vector_version(conn: sqlite3.Connection) -> None:
    """写或删向量的事务里调用：版本号与向量一起提交，读者不会把旧矩阵记在新版本号下。"""
    conn.execute("UPDATE comic_dialogue_vectors_version SET version = version + 1")


def _vector_store(stamp: tuple[Any, ...], dim: int) -> tuple[list[tuple[str, str, int, str]], Any]:
    """取回 (键列表, 向量矩阵)，按 `_vector_status` 给的戳子做进程内缓存。

    不缓存的话每次检索都要重读全部 BLOB 再 np.stack，这是语义检索里最大的一笔开销。
    整体一次性赋值，不留"半个新矩阵被别的线程看见"的窗口。
    """
    global _VECTOR_CACHE
    if _VECTOR_CACHE is not None and _VECTOR_CACHE[0] == stamp:
        return _VECTOR_CACHE[1], _VECTOR_CACHE[2]
    with get_dialogue_db() as conn:
        rows = conn.execute(
            "SELECT source, source_id, page_index, bubble_id, vec FROM comic_dialogue_vectors WHERE dim = ?",
            (dim,),
        ).fetchall()

    import numpy as np

    keys = [(r["source"], r["source_id"], int(r["page_index"]), str(r["bubble_id"])) for r in rows]
    matrix = (
        np.stack([np.frombuffer(r["vec"], dtype=np.float32) for r in rows])
        if rows
        else np.zeros((0, dim), dtype=np.float32)
    )
    _VECTOR_CACHE = (stamp, keys, matrix)
    return keys, matrix


def search_dialogues_semantic(
    query: str,
    source: str | None = None,
    limit: int = 20,
    is_guest: bool = False,
    user_id: str = "",
) -> dict[str, Any]:
    """按意思找台词：把问题编码成向量，与语料向量取余弦近邻。

    与 `search_dialogues` 刻意分成两个出口（ADR 0028）：每页只留最相似的气泡、不吐 snippet；
    分数是 `similarity`（余弦，只在同一次查询内比高低），不复用 `rank_score`，也不掺业务信号。
    访客隐藏本与未收录本的过滤规则与关键词出口一致。

    Returns:
        `{"results": [...], "available": bool, "reason": str}`。没有分数下限，能检索时总会给出
        最近的若干页，所以"没走检索"只能靠 `reason` 说：`encoder_unavailable` /
        `vectors_missing` / `dim_mismatch` 时 `available` 为 False（这台机器走不了语义腿）；
        `query_too_short` 时 `available` 为 True（腿是好的，问题太短）；正常检索为空串。
    """
    from .. import embedding

    status, stamp = _vector_status()
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

    keys_all, matrix = _vector_store(stamp, int(qv.shape[0]))
    import numpy as np

    # 书级过滤先于取前 K：访客隐藏本若等到取完才剔除，会白占名额让访客拿到的结果少于 limit
    book_keys = sorted({(k[0], k[1]) for k in keys_all if not source or k[0] == source})
    comics_map = _dialogue_comics_meta_map(book_keys, user_id)
    allowed = {
        b for b in book_keys
        if not is_guest or (comics_map.get(b) is not None and not comics_map[b]["hidden_from_guest"])
    }
    mask = np.fromiter(((k[0], k[1]) in allowed for k in keys_all), dtype=bool, count=len(keys_all))
    sims = np.where(mask, matrix @ qv, -np.inf)
    valid = int(mask.sum())

    # 同页只留相似度最高的气泡；按页去重后不够数就把 K 翻倍重取，直到够数或候选取尽
    hits: list[tuple[tuple[str, str, int, str], float]] = []
    pages: set[tuple[str, str, int]] = set()
    k = min(fetch_limit, valid)
    while k > 0:
        # 先按下标排再稳定排序：同分时保持入库顺序，与全量 argsort 的结果一致
        top = np.sort(np.argpartition(-sims, k - 1)[:k])
        hits, pages = [], set()
        for i in top[np.argsort(-sims[top], kind="stable")]:
            key = keys_all[int(i)]
            if key[:3] in pages:
                continue
            pages.add(key[:3])
            hits.append((key, float(sims[int(i)])))
            if len(hits) >= fetch_limit:
                break
        if len(hits) >= fetch_limit or k >= valid:
            break
        k = min(k * 2, valid)
    # 原文按气泡回表：向量表只存坐标外的最小信息，文本/框仍以 FTS 那行为准，
    # 避免两个表说同一句话的不同版本。
    texts: dict[tuple[str, str, int, str], sqlite3.Row] = {}
    if pages:
        clause = " OR ".join(["(f.source = ? AND f.source_id = ? AND f.page_index = ?)"] * len(pages))
        flat: list[Any] = [p for k in pages for p in k]
        with get_dialogue_db() as conn:
            for r in conn.execute(
                f"SELECT f.source, f.source_id, f.page_index, f.bubble_id, f.text, f.lang, f.box_json"
                f" FROM comic_dialogues_fts f WHERE ({clause}) AND f.kind = ?",
                [*flat, DIALOGUE_KIND],
            ).fetchall():
                texts[(r["source"], r["source_id"], int(r["page_index"]), str(r["bubble_id"]))] = r

    results: list[dict[str, Any]] = []
    for key, sim in hits:
        r = texts.get(key)
        if r is None:
            continue
        ci = comics_map.get((key[0], key[1]))
        results.append(
            {
                "source": key[0],
                "source_id": key[1],
                **_dialogue_book_fields(key[0], key[1], ci),
                "page_index": key[2],
                "bubble_id": r["bubble_id"],
                "text": r["text"] or "",
                # 与关键词出口同理：写入口已归一，读侧不再重复校验
                "box": json.loads(r["box_json"]),
                "lang": r["lang"] or "zh",
                "similarity": round(sim, 4),
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
            conn.execute(
                "DELETE FROM comic_dialogue_vectors WHERE source = ? AND source_id = ?", (src, sid)
            )
            logger.info("Cleaned orphan dialogue index for deleted comic %s/%s", src, sid)
        _bump_vector_version(conn)
    return len(to_delete)


def _escape_like(text: str) -> str:
    """转义 SQLite LIKE 查询中的特殊通配符 %、_ 与转义符自身。"""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


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


