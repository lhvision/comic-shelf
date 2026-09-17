"""PDF comic extraction, lossless image stream unpacking, and dual-track chapter detection."""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import pymupdf

logger = logging.getLogger(__name__)

# Extensions supported for raw image extraction
EXT_MAP = {
    "jpeg": ".jpg",
    "jpg": ".jpg",
    "png": ".png",
    "webp": ".webp",
    "jpx": ".jpx",
    "jp2": ".jp2",
    "gif": ".gif",
}


MAX_PDF_PAGES = 5000


def is_pdf_file(path_or_name: str | Path) -> bool:
    """Returns True if the path or filename ends with .pdf (case-insensitive)."""
    return str(path_or_name).lower().endswith(".pdf")


def unpack_pdf(pdf_path: Path, output_dir: Path) -> tuple[list[tuple[int, Path, str]], dict[str, Any]]:
    """Unpacks a PDF into raw image files inside output_dir with minimal CPU overhead.

    Uses PyMuPDF's direct stream extraction when a single primary raster image exists,
    falling back to 200 DPI rasterization for vector or composite pages.
    Returns a list of (page_index_1_based, file_path, extension) and PDF metadata.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        doc = pymupdf.open(pdf_path)
    except Exception as exc:
        raise ValueError(f"无法读取或解析 PDF 文件：{exc}") from exc

    with doc:
        if doc.needs_pass:
            raise ValueError(f"PDF 文件已加密（需要密码解密）：{pdf_path.name}")
        total_pages = len(doc)
        if total_pages == 0:
            raise ValueError(f"PDF 文件未包含任何有效页面：{pdf_path.name}")
        if total_pages > MAX_PDF_PAGES:
            raise ValueError(f"PDF 总页数（{total_pages}P）超出安全上限（{MAX_PDF_PAGES}P），请先分割后导入。")

        extracted: list[tuple[int, Path, str]] = []

        for idx, page in enumerate(doc, start=1):
            imgs = page.get_images()
            done = False

            if len(imgs) == 1:
                try:
                    xref = imgs[0][0]
                    base_img = doc.extract_image(xref)
                    raw_ext = base_img.get("ext", "jpg").lower()
                    ext = EXT_MAP.get(raw_ext, f".{raw_ext}")
                    dest_file = output_dir / f"{idx:05d}{ext}"
                    dest_file.write_bytes(base_img["image"])
                    extracted.append((idx, dest_file, ext))
                    done = True
                except Exception as exc:
                    logger.warning("Failed raw extraction for page %d in %s: %s, falling back to render", idx, pdf_path, exc)

            if not done:
                # Fallback: rasterize page to high-quality pixmap (200 DPI, capped for memory safety)
                rect = page.rect
                max_dim_pt = max(rect.width, rect.height)
                dpi = 200
                if max_dim_pt > 0 and (max_dim_pt * dpi / 72) > 3500:
                    dpi = max(72, int(3500 * 72 / max_dim_pt))
                pix = page.get_pixmap(dpi=dpi)
                ext = ".png"
                dest_file = output_dir / f"{idx:05d}{ext}"
                pix.save(str(dest_file))
                extracted.append((idx, dest_file, ext))

        doc_meta = doc.metadata or {}
        meta = {
            "title": (doc_meta.get("title") or "").strip() or pdf_path.stem,
            "author": (doc_meta.get("author") or "").strip(),
            "total_pages": total_pages,
            "format": doc_meta.get("format", "PDF"),
        }
    return extracted, meta


def _extract_chapters_from_toc(toc: list[list[Any]], total_pages: int) -> list[dict[str, Any]] | None:
    """Parses PDF electronic bookmarks (TOC) into structured chapters."""
    if not toc:
        return None

    valid_entries: list[tuple[str, int]] = []
    for item in toc:
        if len(item) >= 3 and isinstance(item[2], int) and item[2] >= 1:
            title = str(item[1]).strip()
            pno = item[2]
            if title and pno <= total_pages:
                valid_entries.append((title, pno))

    if not valid_entries:
        return None

    valid_entries.sort(key=lambda x: x[1])
    unique_entries: list[tuple[str, int]] = []
    for title, pno in valid_entries:
        if not unique_entries or unique_entries[-1][1] != pno:
            unique_entries.append((title, pno))

    chapters: list[dict[str, Any]] = []
    first_pno = unique_entries[0][1]
    chap_idx = 1

    if first_pno > 1:
        chapters.append({
            "id": "c0",
            "index": chap_idx,
            "title": "卷首 / 目录",
            "start": 1,
            "page_count": first_pno - 1,
        })
        chap_idx += 1

    for i, (title, pno) in enumerate(unique_entries):
        next_pno = unique_entries[i + 1][1] if i + 1 < len(unique_entries) else total_pages + 1
        page_count = max(1, next_pno - pno)
        chapters.append({
            "id": f"c{chap_idx}",
            "index": chap_idx,
            "title": title,
            "start": pno,
            "page_count": page_count,
        })
        chap_idx += 1

    return chapters if len(chapters) >= 1 else None


def _extract_chapters_from_ocr(
    doc: pymupdf.Document, total_pages: int, doc_title: str = ""
) -> list[dict[str, Any]] | None:
    """Heuristically detects chapter boundaries using local RapidOCR on contents pages & chapter title cards."""
    try:
        from rapidocr_onnxruntime import RapidOCR
        ocr = RapidOCR()
    except Exception as exc:
        logger.info("RapidOCR not available for PDF chapter detection: %s", exc)
        return None

    chap_pattern = re.compile(
        r"^(?:第\s*([0-9一二三四五六七八九十]+)\s*(?:话|話|回|卷|期)?|(?:c|ch|ep)\s*([0-9]+)|([0-9]+)\s*(?:话|話|回|卷|期))[.:\s]*(.*)$",
        re.IGNORECASE,
    )
    extra_pattern = re.compile(r"^(?:加筆|附錄|番外|後記|后记|新畫|新画)")

    splits: dict[int, str] = {}
    contents_page_found = False

    # 1. Fast probe early pages (1..15) for a Table of Contents (Contents / 目录)
    toc_limit = min(15, total_pages)
    for pno in range(toc_limit):
        page = doc[pno]
        imgs = page.get_images()
        if not imgs:
            continue
        try:
            base_img = doc.extract_image(imgs[0][0])
            res, _ = ocr(base_img["image"])
        except Exception:
            continue
        if not res:
            continue

        lines = [r[1].strip() for r in res if r[1].strip()]
        matched_lines = [l for l in lines if chap_pattern.match(l) or extra_pattern.match(l)]
        if len(matched_lines) >= 3:
            contents_page_found = True
            contents_pno = pno + 1
            logger.info("Detected Contents page at PDF page %d with %d items", contents_pno, len(matched_lines))

            # Parse lines from the contents page to extract titles and printed page hints
            for idx_l, line in enumerate(lines):
                if chap_pattern.match(line) or extra_pattern.match(line):
                    title = line
                    # Look ahead for a page number token in the next 1-2 lines or at line end
                    page_num = None
                    m_num = re.search(r"(\d+)\s*$", line)
                    if m_num:
                        page_num = int(m_num.group(1))
                    elif idx_l + 1 < len(lines):
                        next_line = lines[idx_l + 1]
                        if next_line.isdigit() and int(next_line) <= total_pages:
                            page_num = int(next_line)

                    # For chapter 1 (first item), if no explicit page or page <= contents page, it starts right after contents page
                    if not splits and (page_num is None or page_num <= contents_pno):
                        splits[contents_pno + 1] = title
                    elif page_num and 1 <= page_num <= total_pages:
                        # Printed page numbers in manga volumes typically correlate with PDF page +1 or 0
                        # Try exact candidate or candidate + 1
                        target_pno = page_num if page_num > contents_pno else page_num + contents_pno
                        if target_pno <= total_pages:
                            splits[target_pno] = title
            break

    # 2. If table of contents gave us >= 2 chapters, we are done! No need to blind-scan all pages.
    # Otherwise, scan candidate pages (up to 40 pages maximum) to discover standalone chapter title cards.
    if len(splits) < 2:
        max_ocr_pages = min(40, total_pages)
        if total_pages <= max_ocr_pages:
            scan_indices = list(range(total_pages))
        else:
            early = list(range(min(15, total_pages)))
            step = max(1, (total_pages - 15) // max(1, max_ocr_pages - len(early)))
            remaining = list(range(15, total_pages, step))[: max_ocr_pages - len(early)]
            scan_indices = sorted(set(early + remaining))

        for pno in scan_indices:
            page_idx = pno + 1
            if contents_page_found and page_idx <= toc_limit and page_idx not in splits:
                continue

            page = doc[pno]
            imgs = page.get_images()
            if not imgs:
                continue
            try:
                base_img = doc.extract_image(imgs[0][0])
                res, _ = ocr(base_img["image"])
            except Exception:
                continue
            if not res:
                continue

            for _, text, _ in res:
                t = text.strip()
                if len(t) <= 20 and not any(p in t for p in ("，", "。", "！", "？", "…", "的", "不是", "她是")):
                    m = chap_pattern.match(t)
                    if m and not t.startswith("第一次") and not t.startswith("第二天") and not t.startswith("第1名"):
                        splits[page_idx] = t
                        break
                    elif extra_pattern.match(t) and len(t) <= 12:
                        splits[page_idx] = t
                        break

    if len(splits) < 2:
        return None

    # Merge splits that are too close (within 3 pages of each other) to avoid duplicate titles
    sorted_pnos = sorted(splits.keys())
    filtered_splits: dict[int, str] = {}
    last_pno = -999
    for pno in sorted_pnos:
        if pno - last_pno >= 4:
            filtered_splits[pno] = splits[pno]
            last_pno = pno
        else:
            # If current has a better title, update previous
            if len(splits[pno]) > len(filtered_splits.get(last_pno, "")):
                title = splits[pno]
                del filtered_splits[last_pno]
                filtered_splits[pno] = title
                last_pno = pno

    if len(filtered_splits) < 2:
        return None

    final_pnos = sorted(filtered_splits.keys())
    chapters: list[dict[str, Any]] = []
    chap_idx = 1

    first_pno = final_pnos[0]
    if first_pno > 1:
        chapters.append({
            "id": "c0",
            "index": chap_idx,
            "title": "卷首 / 目录",
            "start": 1,
            "page_count": first_pno - 1,
        })
        chap_idx += 1

    for i, pno in enumerate(final_pnos):
        next_pno = final_pnos[i + 1] if i + 1 < len(final_pnos) else total_pages + 1
        page_count = max(1, next_pno - pno)
        title = filtered_splits[pno]
        if not title or len(title) < 2:
            title = f"第 {chap_idx} 话"
        chapters.append({
            "id": f"c{chap_idx}",
            "index": chap_idx,
            "title": title,
            "start": pno,
            "page_count": page_count,
        })
        chap_idx += 1

    return chapters


def detect_pdf_chapters(pdf_path: Path, total_pages: int, doc_title: str = "") -> tuple[list[dict[str, Any]], str]:
    """Dual-track chapter detector: tries PDF outlines first, then OCR heuristic, falling back to single chapter.

    Returns (chapters, detection_track) where detection_track is 'toc', 'ocr', or 'fallback'.
    """
    try:
        doc = pymupdf.open(pdf_path)
    except Exception as exc:
        logger.warning("Failed to open PDF %s for chapter detection: %s", pdf_path, exc)
        return [
            {
                "id": "c1",
                "index": 1,
                "title": doc_title or pdf_path.stem or "全一卷",
                "start": 1,
                "page_count": total_pages,
            }
        ], "fallback"

    with doc:
        if doc.needs_pass:
            logger.warning("PDF %s is password encrypted, falling back to single chapter", pdf_path)
            return [
                {
                    "id": "c1",
                    "index": 1,
                    "title": doc_title or pdf_path.stem or "全一卷",
                    "start": 1,
                    "page_count": total_pages,
                }
            ], "fallback"

        # Track 1: Electronic bookmarks
        toc = doc.get_toc()
        chapters = _extract_chapters_from_toc(toc, total_pages)
        if chapters and len(chapters) >= 2:
            return chapters, "toc"

        # Track 2: OCR heuristic
        ocr_chapters = _extract_chapters_from_ocr(doc, total_pages, doc_title)
        if ocr_chapters and len(ocr_chapters) >= 2:
            return ocr_chapters, "ocr"

    # Fallback: Single chapter encompassing all pages
    fallback_chapters = [
        {
            "id": "c1",
            "index": 1,
            "title": doc_title or pdf_path.stem or "全一卷",
            "start": 1,
            "page_count": total_pages,
        }
    ]
    return fallback_chapters, "fallback"
