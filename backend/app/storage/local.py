"""Local comic mixin handling local album creation, server-path imports, page appending, and replacements."""
from __future__ import annotations

import datetime
import io
import logging
import os
import re
import shutil
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from PIL import Image

from ..config import COVER_THUMB_WIDTH, TMP_DIR
from ..gate import get_guest_hide_new_comics
from ..models import (
    Chapter,
    ComicMeta,
    CreateFromStagedPdfRequest,
    FetchedComic,
    PageRecord,
    PdfChapterPreview,
    PdfInspectResponse,
    RemotePage,
)
from ..providers.local import LocalProvider
from .pdf import detect_pdf_chapters, is_pdf_file, unpack_pdf
from .utils import (
    CURRENT_DECODE_VERSION,
    IMAGE_EXTS,
    _NATURAL_SPLIT,
    _is_path_allowed,
    _write_json_atomic,
)

logger = logging.getLogger(__name__)


class ComicStoreLocalMixin:
    """Provides local comic creation, folder/archive scanning, page appending, and page replacements."""

    @staticmethod
    def _natural_key(s: str) -> list[int | str]:
        return [int(text) if text.isdigit() else text.lower() for text in _NATURAL_SPLIT.split(s)]

    @classmethod
    def _group_by_composite_chapter_pattern(
        cls, items: list[tuple[str, str, Any]]
    ) -> dict[int, list[tuple[str, str, Any]]] | None:
        """Detect if items follow a composite chapter-page pattern (e.g. `1-1.avif`, `02_001.jpg`, `第1话_01.png`, `c1-1.webp`)."""
        if not items or len(items) < 2:
            return None

        composite_re = re.compile(
            r"^(?:\[?(?:c|ch|ep|vol|第)?\s*(\d+)\s*(?:话|話|回|卷|期)?\]?)[-_.#\s]+(\d+)",
            re.IGNORECASE,
        )

        sorted_items = sorted(items, key=lambda x: cls._natural_key(x[0]))
        matched_items: list[tuple[int, tuple[str, str, Any]]] = []

        for item in sorted_items:
            stem = Path(item[0]).stem
            m = composite_re.match(stem)
            if m:
                matched_items.append((int(m.group(1)), item))

        unique_chaps = sorted({cnum for cnum, _ in matched_items})
        if len(unique_chaps) < 2 or len(matched_items) < max(2, int(len(items) * 0.8)):
            return None

        groups: dict[int, list[tuple[str, str, Any]]] = {c: [] for c in unique_chaps}

        curr_chap = unique_chaps[0]
        for item in sorted_items:
            stem = Path(item[0]).stem
            m = composite_re.match(stem)
            if m:
                curr_chap = int(m.group(1))
            groups[curr_chap].append(item)

        for cnum in groups:
            groups[cnum].sort(key=lambda x: cls._natural_key(x[0]))

        return groups

    @staticmethod
    def _link_or_copy_file(src: Path, dest: Path) -> None:
        """优先使用硬链接实现零拷贝极速导入，若跨盘/跨文件系统(EXDEV)则优雅降级为复制。"""
        try:
            if src.resolve() == dest.resolve():
                return
        except OSError:
            pass

        if dest.exists():
            try:
                if dest.is_file() and os.path.samefile(src, dest):
                    return
                dest.unlink()
            except OSError:
                pass
        try:
            os.link(src, dest)
        except OSError:
            shutil.copy2(src, dest)

    @staticmethod
    def _resolve_and_verify_server_path(server_path: str, must_be_dir: bool = False) -> Path:
        """Resolve a user-specified server path relative to project root or cwd and verify security allowlists."""
        raw_path = Path(server_path).expanduser()
        if not raw_path.is_absolute():
            proj_root = Path(__file__).resolve().parents[3]
            cand1 = proj_root / raw_path
            cand2 = Path.cwd() / raw_path
            raw_path = cand1 if cand1.exists() else cand2

        if not raw_path.exists():
            raise HTTPException(status_code=400, detail=f"指定路径不存在：{server_path}")
        if must_be_dir and not raw_path.is_dir():
            raise HTTPException(status_code=400, detail=f"指定目录不存在或不是文件夹：{server_path}")
        if not _is_path_allowed(raw_path):
            raise HTTPException(
                status_code=400,
                detail=f"出于安全考虑，禁止从指定目录导入（{raw_path}）。如需导入，请配置 COMIC_SHELF_ALLOWED_DIRS 环境变量。",
            )
        return raw_path

    @staticmethod
    def _verify_image_item(data_or_path: bytes | Path, filename: str) -> None:
        """Verify that image data or file is uncorrupted and parseable by PIL."""
        try:
            if isinstance(data_or_path, Path):
                with Image.open(data_or_path) as img:
                    img.verify()
            else:
                with Image.open(io.BytesIO(data_or_path)) as img:
                    img.verify()
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail=f"图片文件损坏或不是有效图片（{filename}）：{exc}",
            ) from exc

    def _schedule_initial_and_auxiliary_covers(self: Any, meta: ComicMeta, fetched: FetchedComic) -> None:
        """Generates primary cover synchronously and schedules auxiliary and chapter covers in background."""
        source_id = meta.source_id
        if meta.page_count > 0:
            try:
                self.ensure_webp_cover(meta, fetched, 1)
                self.ensure_webp_cover(meta, fetched, 1, COVER_THUMB_WIDTH)
            except Exception as e:
                logger.warning("Failed to generate initial primary cover for %s: %s", source_id, e)

        def _bg_generate_auxiliary_covers() -> None:
            for i in range(2, min(meta.cover_count, meta.page_count) + 1):
                try:
                    self.ensure_webp_cover(meta, fetched, i)
                    self.ensure_webp_cover(meta, fetched, i, COVER_THUMB_WIDTH)
                except Exception as e:
                    logger.warning("Background cover generation %d for %s skipped: %s", i, source_id, e)

            if meta.chapters:
                for ch in meta.chapters:
                    try:
                        self.ensure_webp_chapter_cover(meta, fetched, ch)
                        self.ensure_webp_chapter_cover(meta, fetched, ch, COVER_THUMB_WIDTH)
                    except Exception as e:
                        logger.warning("Background chapter cover generation %s for %s skipped: %s", ch.id, source_id, e)

        self._cover_executor.submit(_bg_generate_auxiliary_covers)

    def _allocate_local_id(self: Any, req_id: str | None = None, fallback_name: str | None = None) -> tuple[str, str]:
        """Allocates a unique (source_id, display_id) pair for a local comic.

        Avoids disk collisions and strips redundant 'loc_' prefixes to prevent 'LOC_loc_...' stutter.
        """
        provider = LocalProvider()
        source_id = ""
        if req_id:
            source_id = provider.normalize_id(req_id)
        elif fallback_name:
            cand = provider.normalize_id(fallback_name)
            if cand and cand != "collection":
                source_id = cand

        if not source_id:
            base_id = provider.generate_id()
            source_id = base_id
            counter = 1
            while self.album_path("local", source_id).exists():
                source_id = f"{base_id}_{counter}"
                counter += 1
        elif not req_id:
            base_id = source_id
            counter = 1
            while self.album_path("local", source_id).exists():
                source_id = f"{base_id}_{counter}"
                counter += 1

        display_id = provider.display_id(source_id)
        return source_id, display_id

    def create_local_comic(self: Any, req: Any) -> ComicMeta:
        provider = LocalProvider()
        source_id, display_id = self._allocate_local_id(req.id)

        with self._lock_for("local", source_id):
            if req.id and self.load_meta("local", source_id) is not None:
                raise HTTPException(
                    status_code=409,
                    detail=f"已存在唯一标识为「{source_id}」的漫画，请指定新的标识或留空由系统自动生成。",
                )

            comic_dir = self.comic_dir("local", source_id)
            comic_dir.mkdir(parents=True, exist_ok=True)
            self.pages_dir("local", source_id).mkdir(parents=True, exist_ok=True)

            chapters: list[Chapter] = []
            if getattr(req, "chapters", None):
                for idx, c in enumerate(req.chapters, start=1):
                    cid = provider.normalize_id(c.id) if getattr(c, "id", "") else f"c{idx}"
                    title = getattr(c, "title", "") or f"第 {idx} 话"
                    chapters.append(Chapter(id=cid, index=idx, title=title, page_count=0, start=1))

            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            meta = ComicMeta(
                source="local",
                source_id=source_id,
                display_id=display_id,
                title=req.title,
                authors=req.authors or ["自制"],
                works=req.works or [],
                actors=req.actors or [],
                tags=req.tags or [],
                description=req.description or "",
                uploader=req.uploader or "自制",
                page_count=0,
                cover_count=4,
                cover_indices=getattr(req, "cover_indices", []) or [],
                published_at=now_str,
                updated_at=now_str,
                imported_at=now_str,
                chapters=chapters,
                hidden_from_guest=getattr(req, "hidden_from_guest", False) or get_guest_hide_new_comics(),
            )

            _write_json_atomic(self.album_path("local", source_id), meta.model_dump())
            _write_json_atomic(
                self.remote_path("local", source_id),
                {"decode_version": CURRENT_DECODE_VERSION, "remote_pages": []},
            )
            self._invalidate_cache("local", source_id)
            return meta

    def _import_single_pdf(self: Any, pdf_path: Path, req: Any) -> ComicMeta:
        provider = LocalProvider()
        source_id, display_id = self._allocate_local_id(req.id, pdf_path.stem)

        with self._lock_for("local", source_id):
            if req.id and self.load_meta("local", source_id) is not None:
                raise HTTPException(
                    status_code=409,
                    detail=f"已存在唯一标识为「{source_id}」的漫画，请指定新的标识或留空由系统自动生成。",
                )

            staging_dir = TMP_DIR / f".pdf_tmp_{source_id}_{int(time.time() * 1000)}"
            try:
                extracted_pages, pdf_meta = unpack_pdf(pdf_path, staging_dir)
                total_pages = len(extracted_pages)
                if total_pages == 0:
                    raise HTTPException(status_code=400, detail=f"PDF 中未发现有效画卷内容：{pdf_path.name}")

                doc_title = req.title.strip() if req.title and req.title.strip() else (pdf_meta.get("title") or pdf_path.stem)

                if getattr(req, "chapters", None) and len(req.chapters) > 0:
                    chap_specs = [c.model_dump() if hasattr(c, "model_dump") else dict(c) for c in req.chapters]
                else:
                    chap_specs, _ = detect_pdf_chapters(pdf_path, total_pages, doc_title)

                target_pages_dir = self.pages_dir("local", source_id)
                target_pages_dir.mkdir(parents=True, exist_ok=True)

                pages: list[PageRecord] = []
                remote_pages: list[RemotePage] = []
                chapters: list[Chapter] = []

                if len(chap_specs) > 1:
                    global_idx = 1
                    for chap_idx, ch_spec in enumerate(chap_specs, start=1):
                        raw_cid = ch_spec.get("id") or f"c{chap_idx}"
                        chap_id = provider.normalize_id(raw_cid)
                        chap_title = ch_spec.get("title") or f"第 {chap_idx} 话"
                        c_start = ch_spec.get("start", global_idx)
                        c_count = ch_spec.get("page_count", 0)

                        chap_pages_dir = target_pages_dir / self._safe(chap_id)
                        chap_pages_dir.mkdir(parents=True, exist_ok=True)

                        chap_files = [item for item in extracted_pages if c_start <= item[0] < c_start + c_count]
                        if not chap_files:
                            continue

                        chap_start_page = global_idx
                        for local_i, (_, src_file, ext) in enumerate(chap_files, start=1):
                            dest_name = f"{local_i:05d}{ext}"
                            dest_path = chap_pages_dir / dest_name
                            shutil.move(str(src_file), str(dest_path))

                            pages.append(PageRecord(index=global_idx, file=dest_name, ext=ext, cached=True, chapter=chap_id))
                            remote_pages.append(RemotePage(index=global_idx, url="", file=dest_name, ext=ext, chapter=chap_id))
                            global_idx += 1

                        chapters.append(
                            Chapter(
                                id=chap_id,
                                index=chap_idx,
                                title=chap_title,
                                page_count=len(chap_files),
                                start=chap_start_page,
                            )
                        )
                else:
                    global_idx = 1
                    for local_i, (_, src_file, ext) in enumerate(extracted_pages, start=1):
                        dest_name = f"{local_i:05d}{ext}"
                        dest_path = target_pages_dir / dest_name
                        shutil.move(str(src_file), str(dest_path))

                        pages.append(PageRecord(index=global_idx, file=dest_name, ext=ext, cached=True, chapter=""))
                        remote_pages.append(RemotePage(index=global_idx, url="", file=dest_name, ext=ext, chapter=""))
                        global_idx += 1

                now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                author_val = req.authors if req.authors else ([pdf_meta["author"]] if pdf_meta.get("author") else ["自制"])

                meta = ComicMeta(
                    source="local",
                    source_id=source_id,
                    display_id=display_id,
                    title=doc_title,
                    authors=author_val,
                    works=req.works or [],
                    actors=req.actors or [],
                    tags=req.tags or [],
                    description=req.description or "",
                    uploader=req.uploader or "PDF导入",
                    page_count=len(pages),
                    cover_count=4,
                    cover_indices=getattr(req, "cover_indices", []) or [],
                    published_at=now_str,
                    updated_at=now_str,
                    imported_at=now_str,
                    pages=pages,
                    chapters=chapters,
                    hidden_from_guest=getattr(req, "hidden_from_guest", False) or get_guest_hide_new_comics(),
                )

                fetched = FetchedComic(meta=meta, remote_pages=remote_pages)
                self.save_fetched(fetched, refresh=False)

                self._schedule_initial_and_auxiliary_covers(meta, fetched)
                return meta
            finally:
                shutil.rmtree(staging_dir, ignore_errors=True)

    def _import_multi_pdfs(self: Any, pdf_files: list[Path], req: Any, base_dir: Path) -> ComicMeta:
        provider = LocalProvider()
        source_id, display_id = self._allocate_local_id(req.id, base_dir.name)

        with self._lock_for("local", source_id):
            if req.id and self.load_meta("local", source_id) is not None:
                raise HTTPException(
                    status_code=409,
                    detail=f"已存在唯一标识为「{source_id}」的漫画，请指定新的标识或留空由系统自动生成。",
                )

            pdf_files.sort(key=lambda f: self._natural_key(f.name))
            target_pages_dir = self.pages_dir("local", source_id)
            target_pages_dir.mkdir(parents=True, exist_ok=True)

            pages: list[PageRecord] = []
            remote_pages: list[RemotePage] = []
            chapters: list[Chapter] = []

            global_idx = 1
            for chap_idx, pdf_f in enumerate(pdf_files, start=1):
                chap_id = provider.normalize_id(f"c{chap_idx}")
                chap_title = pdf_f.stem
                chap_pages_dir = target_pages_dir / self._safe(chap_id)
                chap_pages_dir.mkdir(parents=True, exist_ok=True)

                chap_extracted, _ = unpack_pdf(pdf_f, chap_pages_dir)
                start_page = global_idx
                chap_count = len(chap_extracted)

                for local_i, (_, dest_file, ext) in enumerate(chap_extracted, start=1):
                    dest_name = f"{local_i:05d}{ext}"
                    final_path = chap_pages_dir / dest_name
                    if dest_file != final_path:
                        dest_file.rename(final_path)

                    pages.append(PageRecord(index=global_idx, file=dest_name, ext=ext, cached=True, chapter=chap_id))
                    remote_pages.append(RemotePage(index=global_idx, url="", file=dest_name, ext=ext, chapter=chap_id))
                    global_idx += 1

                chapters.append(
                    Chapter(
                        id=chap_id,
                        index=chap_idx,
                        title=chap_title,
                        page_count=chap_count,
                        start=start_page,
                    )
                )

            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            title = req.title.strip() if req.title and req.title.strip() else base_dir.name

            meta = ComicMeta(
                source="local",
                source_id=source_id,
                display_id=display_id,
                title=title,
                authors=req.authors or ["自制"],
                works=req.works or [],
                actors=req.actors or [],
                tags=req.tags or [],
                description=req.description or "",
                uploader=req.uploader or "PDF合集导入",
                page_count=len(pages),
                cover_count=4,
                cover_indices=getattr(req, "cover_indices", []) or [],
                published_at=now_str,
                updated_at=now_str,
                imported_at=now_str,
                pages=pages,
                chapters=chapters,
                hidden_from_guest=getattr(req, "hidden_from_guest", False) or get_guest_hide_new_comics(),
            )

            fetched = FetchedComic(meta=meta, remote_pages=remote_pages)
            self.save_fetched(fetched, refresh=False)

            self._schedule_initial_and_auxiliary_covers(meta, fetched)
            return meta

    def _cleanup_staged_pdfs(self: Any, max_age_seconds: int = 3600) -> None:
        """Sweeps and deletes expired temporary staging directories in TMP_DIR."""
        now = time.time()
        try:
            for item in TMP_DIR.iterdir():
                if item.is_dir() and item.name.startswith("staged_pdf_"):
                    try:
                        mtime = item.stat().st_mtime
                        if now - mtime > max_age_seconds:
                            shutil.rmtree(item, ignore_errors=True)
                    except Exception:
                        pass
                elif item.is_file() and (item.name.startswith(".upload_") or item.name.startswith(".pdf_tmp_")):
                    try:
                        mtime = item.stat().st_mtime
                        if now - mtime > max_age_seconds:
                            item.unlink(missing_ok=True)
                    except Exception:
                        pass
        except Exception as e:
            logger.debug("Staged PDF cleanup failed: %s", e)

    def delete_staged_pdf(self: Any, staging_token: str) -> bool:
        """Explicitly purges a staged PDF directory upon user cancel/reset."""
        safe_token = re.sub(r"[^a-zA-Z0-9_]", "", staging_token)
        if not safe_token.startswith("staged_pdf_"):
            return False
        staging_dir = TMP_DIR / safe_token
        if staging_dir.exists() and staging_dir.is_dir():
            shutil.rmtree(staging_dir, ignore_errors=True)
            return True
        return False

    def inspect_pdf_file(self: Any, pdf_path: Path) -> PdfInspectResponse:
        self._cleanup_staged_pdfs()
        staging_token = f"staged_pdf_{uuid.uuid4().hex[:12]}"
        staging_dir = TMP_DIR / staging_token
        staging_dir.mkdir(parents=True, exist_ok=True)

        try:
            extracted_pages, pdf_meta = unpack_pdf(pdf_path, staging_dir)
            total_pages = len(extracted_pages)
            if total_pages == 0:
                raise HTTPException(status_code=400, detail=f"PDF 中未发现有效画页：{pdf_path.name}")

            title = (pdf_meta.get("title") or "").strip() or pdf_path.stem
            author = (pdf_meta.get("author") or "").strip()
            chapters_data, track = detect_pdf_chapters(pdf_path, total_pages, title)

            _write_json_atomic(
                staging_dir / "meta.json",
                {
                    "title": title,
                    "author": author,
                    "total_pages": total_pages,
                    "detection_track": track,
                    "chapters": chapters_data,
                    "extracted_count": len(extracted_pages),
                },
            )

            return PdfInspectResponse(
                staging_token=staging_token,
                title=title,
                authors=[author] if author else [],
                total_pages=total_pages,
                chapters=[PdfChapterPreview(**ch) for ch in chapters_data],
                detection_track=track,
            )
        except ValueError as exc:
            shutil.rmtree(staging_dir, ignore_errors=True)
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception:
            shutil.rmtree(staging_dir, ignore_errors=True)
            raise

    def create_from_staged_pdf(self: Any, req: CreateFromStagedPdfRequest) -> ComicMeta:
        safe_token = re.sub(r"[^a-zA-Z0-9_]", "", req.staging_token)
        if not safe_token.startswith("staged_pdf_"):
            raise HTTPException(status_code=400, detail="非法或无效的暂存令牌。")
        staging_dir = (TMP_DIR / safe_token).resolve()
        if not staging_dir.is_relative_to(TMP_DIR.resolve()) or not staging_dir.is_dir():
            raise HTTPException(status_code=400, detail="暂存的 PDF 数据已过期或不存在，请重新上传。")

        provider = LocalProvider()
        source_id, display_id = self._allocate_local_id(req.id)

        with self._lock_for("local", source_id):
            if req.id and self.load_meta("local", source_id) is not None:
                raise HTTPException(
                    status_code=409,
                    detail=f"已存在唯一标识为「{source_id}」的漫画，请指定新的标识或留空由系统自动生成。",
                )

            all_files = [f for f in staging_dir.iterdir() if f.is_file() and f.suffix.lower() in IMAGE_EXTS]
            all_files.sort(key=lambda f: self._natural_key(f.name))
            if not all_files:
                shutil.rmtree(staging_dir, ignore_errors=True)
                raise HTTPException(status_code=400, detail="暂存目录中未找到解包画页文件。")

            target_pages_dir = self.pages_dir("local", source_id)
            comic_dir = self.comic_dir("local", source_id)
            comic_dir.mkdir(parents=True, exist_ok=True)
            album_path = self.album_path("local", source_id)
            remote_path = self.remote_path("local", source_id)
            backup_dir = self._begin_metadata_backup(album_path, remote_path)
            staging_work_dir = self._new_work_item(".tmp_create_pages")

            pages: list[PageRecord] = []
            remote_pages: list[RemotePage] = []
            chapters: list[Chapter] = []

            chap_specs = [c.model_dump() for c in req.chapters] if req.chapters else []

            try:
                if len(chap_specs) > 1:
                    global_idx = 1
                    for chap_idx, ch_spec in enumerate(chap_specs, start=1):
                        raw_cid = ch_spec.get("id") or f"c{chap_idx}"
                        chap_id = provider.normalize_id(raw_cid)
                        chap_title = ch_spec.get("title") or f"第 {chap_idx} 话"
                        c_start = ch_spec.get("start", global_idx)
                        c_count = ch_spec.get("page_count", 0)

                        chap_pages_dir = staging_work_dir / self._safe(chap_id)
                        chap_pages_dir.mkdir(parents=True, exist_ok=True)

                        start_idx = max(0, c_start - 1)
                        end_idx = min(len(all_files), start_idx + c_count)
                        chap_files = all_files[start_idx:end_idx]
                        if not chap_files:
                            continue

                        chap_start_page = global_idx
                        for local_i, src_file in enumerate(chap_files, start=1):
                            ext = src_file.suffix.lower()
                            dest_name = f"{local_i:05d}{ext}"
                            dest_path = chap_pages_dir / dest_name
                            shutil.move(str(src_file), str(dest_path))

                            pages.append(PageRecord(index=global_idx, file=dest_name, ext=ext, cached=True, chapter=chap_id))
                            remote_pages.append(RemotePage(index=global_idx, url="", file=dest_name, ext=ext, chapter=chap_id))
                            global_idx += 1

                        chapters.append(
                            Chapter(
                                id=chap_id,
                                index=chap_idx,
                                title=chap_title,
                                page_count=len(chap_files),
                                start=chap_start_page,
                            )
                        )
                else:
                    global_idx = 1
                    for local_i, src_file in enumerate(all_files, start=1):
                        ext = src_file.suffix.lower()
                        dest_name = f"{local_i:05d}{ext}"
                        dest_path = staging_work_dir / dest_name
                        shutil.move(str(src_file), str(dest_path))

                        pages.append(PageRecord(index=global_idx, file=dest_name, ext=ext, cached=True, chapter=""))
                        remote_pages.append(RemotePage(index=global_idx, url="", file=dest_name, ext=ext, chapter=""))
                        global_idx += 1

                self._replace_live_with_staging(backup_dir, staging_work_dir, target_pages_dir)
            except Exception:
                self._rollback_metadata_backup(
                    backup_dir, (remote_path, album_path), "local", source_id
                )
                shutil.rmtree(staging_work_dir, ignore_errors=True)
                raise
            finally:
                shutil.rmtree(staging_dir, ignore_errors=True)

            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            meta = ComicMeta(
                source="local",
                source_id=source_id,
                display_id=display_id,
                title=req.title,
                authors=req.authors or ["自制"],
                works=req.works or [],
                actors=req.actors or [],
                tags=req.tags or [],
                description=req.description or "",
                uploader=req.uploader or "PDF导入",
                page_count=len(pages),
                cover_count=4,
                cover_indices=getattr(req, "cover_indices", []) or [],
                published_at=now_str,
                updated_at=now_str,
                imported_at=now_str,
                pages=pages,
                chapters=chapters,
                hidden_from_guest=getattr(req, "hidden_from_guest", False) or get_guest_hide_new_comics(),
            )

            fetched = FetchedComic(meta=meta, remote_pages=remote_pages)
            try:
                self.save_fetched(fetched, refresh=False, backup_dir=backup_dir)
            except Exception:
                shutil.rmtree(staging_work_dir, ignore_errors=True)
                raise

            self._schedule_initial_and_auxiliary_covers(meta, fetched)
            return meta

    def import_local_path(self: Any, req: Any) -> ComicMeta:
        raw_path = self._resolve_and_verify_server_path(req.path, must_be_dir=False)

        if raw_path.is_file():
            if is_pdf_file(raw_path):
                return self._import_single_pdf(raw_path, req)
            raise HTTPException(status_code=400, detail=f"指定文件不是支持的漫画格式或 PDF：{raw_path.name}")

        subdirs = [d for d in raw_path.iterdir() if d.is_dir() and not d.name.startswith(".")]
        subdirs.sort(key=lambda d: self._natural_key(d.name))

        pdf_files = [f for f in raw_path.iterdir() if f.is_file() and is_pdf_file(f)]
        if pdf_files and not subdirs:
            img_files = [f for f in raw_path.iterdir() if f.is_file() and f.suffix.lower() in IMAGE_EXTS]
            if not img_files:
                if len(pdf_files) == 1:
                    return self._import_single_pdf(pdf_files[0], req)
                return self._import_multi_pdfs(pdf_files, req, raw_path)

        provider = LocalProvider()
        source_id, display_id = self._allocate_local_id(req.id, raw_path.name)

        with self._lock_for("local", source_id):
            if req.id and self.load_meta("local", source_id) is not None:
                raise HTTPException(
                    status_code=409,
                    detail=f"已存在唯一标识为「{source_id}」的漫画，请指定新的标识或留空由系统自动生成。",
                )

            multi_chap_dirs: list[tuple[str, str, list[Path]]] = []
            for d in subdirs:
                imgs = [f for f in d.iterdir() if f.is_file() and f.suffix.lower() in IMAGE_EXTS]
                if imgs:
                    imgs.sort(key=lambda f: self._natural_key(f.name))
                    multi_chap_dirs.append((provider.normalize_id(d.name), d.name, imgs))

            target_pages_dir = self.pages_dir("local", source_id)
            target_pages_dir.mkdir(parents=True, exist_ok=True)

            pages: list[PageRecord] = []
            remote_pages: list[RemotePage] = []
            chapters: list[Chapter] = []

            global_idx = 1
            if multi_chap_dirs:
                for chap_idx, (chap_id, chap_title, img_files) in enumerate(multi_chap_dirs, start=1):
                    chap_pages_dir = target_pages_dir / self._safe(chap_id)
                    chap_pages_dir.mkdir(parents=True, exist_ok=True)
                    start_page = global_idx
                    chap_page_count = len(img_files)

                    for local_i, img_file in enumerate(img_files, start=1):
                        ext = img_file.suffix.lower()
                        dest_name = f"{local_i:05d}{ext}"
                        dest_path = chap_pages_dir / dest_name
                        self._link_or_copy_file(img_file, dest_path)

                        pages.append(PageRecord(index=global_idx, file=dest_name, ext=ext, cached=True, chapter=chap_id))
                        remote_pages.append(RemotePage(index=global_idx, url="", file=dest_name, ext=ext, chapter=chap_id))
                        global_idx += 1

                    chapters.append(
                        Chapter(
                            id=chap_id,
                            index=chap_idx,
                            title=chap_title,
                            page_count=chap_page_count,
                            start=start_page,
                        )
                    )
            else:
                img_files = [f for f in raw_path.iterdir() if f.is_file() and f.suffix.lower() in IMAGE_EXTS]
                img_files.sort(key=lambda f: self._natural_key(f.name))
                if not img_files:
                    raise HTTPException(status_code=400, detail=f"目录中未找到支持的图片文件（支持 {', '.join(IMAGE_EXTS)}）")

                composite_groups = self._group_by_composite_chapter_pattern(
                    [(f.name, f.suffix.lower(), f) for f in img_files]
                )
                if composite_groups:
                    sorted_chap_nums = sorted(composite_groups.keys())
                    for chap_idx, chap_num in enumerate(sorted_chap_nums, start=1):
                        chap_id = provider.normalize_id(f"c{chap_num}")
                        chap_pages_dir = target_pages_dir / self._safe(chap_id)
                        chap_pages_dir.mkdir(parents=True, exist_ok=True)
                        start_page = global_idx
                        chap_items = composite_groups[chap_num]

                        for local_i, (filename, ext, img_file) in enumerate(chap_items, start=1):
                            dest_name = f"{local_i:05d}{ext}"
                            dest_path = chap_pages_dir / dest_name
                            self._link_or_copy_file(img_file, dest_path)

                            pages.append(PageRecord(index=global_idx, file=dest_name, ext=ext, cached=True, chapter=chap_id))
                            remote_pages.append(RemotePage(index=global_idx, url="", file=dest_name, ext=ext, chapter=chap_id))
                            global_idx += 1

                        chapters.append(
                            Chapter(
                                id=chap_id,
                                index=chap_idx,
                                title=f"第 {chap_num} 话",
                                page_count=len(chap_items),
                                start=start_page,
                            )
                        )
                else:
                    for local_i, img_file in enumerate(img_files, start=1):
                        ext = img_file.suffix.lower()
                        dest_name = f"{local_i:05d}{ext}"
                        dest_path = target_pages_dir / dest_name
                        self._link_or_copy_file(img_file, dest_path)

                        pages.append(PageRecord(index=global_idx, file=dest_name, ext=ext, cached=True, chapter=""))
                        remote_pages.append(RemotePage(index=global_idx, url="", file=dest_name, ext=ext, chapter=""))
                        global_idx += 1

            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            title = req.title.strip() if req.title and req.title.strip() else raw_path.name

            meta = ComicMeta(
                source="local",
                source_id=source_id,
                display_id=display_id,
                title=title,
                authors=req.authors or ["自制"],
                works=req.works or [],
                actors=req.actors or [],
                tags=req.tags or [],
                description=req.description or "",
                uploader=req.uploader or "本地导入",
                page_count=len(pages),
                cover_count=4,
                cover_indices=getattr(req, "cover_indices", []) or [],
                published_at=now_str,
                updated_at=now_str,
                imported_at=now_str,
                pages=pages,
                chapters=chapters,
                hidden_from_guest=getattr(req, "hidden_from_guest", False) or get_guest_hide_new_comics(),
            )

            fetched = FetchedComic(meta=meta, remote_pages=remote_pages)
            self.save_fetched(fetched, refresh=False)

            self._schedule_initial_and_auxiliary_covers(meta, fetched)
            return meta

    def _append_multi_chapter_pdf(
        self: Any,
        source: str,
        source_id: str,
        fetched: FetchedComic,
        extracted_pages: list[tuple[int, Path, str]],
        ch_data: list[dict[str, Any]],
        new_chapter_title: str = "",
    ) -> ComicMeta:
        meta = fetched.meta
        if not meta.chapters and meta.pages:
            first_chap_id = "c1"
            self._migrate_flat_to_chapter(meta, first_chap_id)
            old_count = len(meta.pages)
            for p in meta.pages:
                p.chapter = first_chap_id
            for rp in fetched.remote_pages:
                rp.chapter = first_chap_id
            first_chap = Chapter(
                id=first_chap_id,
                index=1,
                title="第 1 话",
                page_count=old_count,
                start=1,
            )
            meta.chapters = [first_chap]
            try:
                self.ensure_webp_chapter_cover(meta, fetched, first_chap)
            except Exception:
                pass

        target_pages_dir = self.pages_dir(source, source_id)
        target_pages_dir.mkdir(parents=True, exist_ok=True)
        provider = LocalProvider()

        all_page_files = [item for item in extracted_pages]
        all_page_files.sort(key=lambda x: x[0])

        for c_order, ch_spec in enumerate(ch_data):
            new_chap_idx = len(meta.chapters) + 1
            raw_cid = ch_spec.get("id") or f"c{new_chap_idx}"
            new_chap_id = provider.normalize_id(f"{raw_cid}_{datetime.datetime.now().strftime('%M%S')}_{c_order}")
            chap_title = ch_spec.get("title") or f"第 {new_chap_idx} 话"
            c_start = ch_spec.get("start", 1)
            c_count = ch_spec.get("page_count", 0)

            chap_dir = target_pages_dir / self._safe(new_chap_id)
            chap_dir.mkdir(parents=True, exist_ok=True)

            chap_files = [item for item in all_page_files if c_start <= item[0] < c_start + c_count]
            if not chap_files:
                continue

            start_idx = meta.page_count + 1
            for local_i, (_pno, src_file, ext) in enumerate(chap_files, start=1):
                dest_name = f"{local_i:05d}{ext}"
                dest_path = chap_dir / dest_name
                shutil.move(str(src_file), str(dest_path))

                cur_idx = meta.page_count + local_i
                meta.pages.append(PageRecord(index=cur_idx, file=dest_name, ext=ext, cached=True, chapter=new_chap_id))
                fetched.remote_pages.append(RemotePage(index=cur_idx, url="", file=dest_name, ext=ext, chapter=new_chap_id))

            meta.page_count += len(chap_files)
            new_chap = Chapter(
                id=new_chap_id,
                index=new_chap_idx,
                title=chap_title,
                page_count=len(chap_files),
                start=start_idx,
            )
            meta.chapters.append(new_chap)
            try:
                self.ensure_webp_chapter_cover(meta, fetched, new_chap)
                self.ensure_webp_chapter_cover(meta, fetched, new_chap, COVER_THUMB_WIDTH)
            except Exception as e:
                logger.warning("Failed to generate cover for new chapter %s: %s", new_chap_id, e)

        meta.updated_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.save_fetched(fetched, refresh=False)
        return meta

    def append_pages(
        self: Any,
        source_id: str,
        source: str = "local",
        files: list[tuple[str, bytes]] | None = None,
        server_path: str = "",
        target_chapter: str = "",
        new_chapter_title: str = "",
    ) -> ComicMeta:
        with self._lock_for(source, source_id):
            fetched = self.load_fetched(source, source_id)
            if fetched is None:
                raise HTTPException(status_code=404, detail="漫画不存在")

            meta = fetched.meta
            items: list[tuple[str, str, bytes | Path]] = []
            pdf_temp_dirs: list[Path] = []
            try:
                if files:
                    sorted_files = sorted(files, key=lambda f: self._natural_key(f[0]))
                    for filename, content in sorted_files:
                        ext = Path(filename).suffix.lower() or ".webp"
                        if ext == ".pdf" and content:
                            pdf_staging = TMP_DIR / f".append_pdf_{uuid.uuid4().hex[:12]}"
                            pdf_staging.mkdir(parents=True, exist_ok=True)
                            tmp_pdf = pdf_staging / "upload.pdf"
                            tmp_pdf.write_bytes(content)
                            extracted_pages, pdf_meta = unpack_pdf(tmp_pdf, pdf_staging / "pages")
                            pdf_temp_dirs.append(pdf_staging)

                            if not target_chapter:
                                total_pages = len(extracted_pages)
                                detected_chaps, _ = detect_pdf_chapters(
                                    tmp_pdf,
                                    total_pages,
                                    new_chapter_title or pdf_meta.get("title") or Path(filename).stem,
                                )
                                if len(detected_chaps) > 1:
                                    return self._append_multi_chapter_pdf(
                                        source, source_id, fetched, extracted_pages, detected_chaps, new_chapter_title
                                    )

                            tmp_pdf.unlink(missing_ok=True)

                            for _pno, f_path, p_ext in extracted_pages:
                                items.append((f_path.name, p_ext, f_path))
                        elif ext in IMAGE_EXTS:
                            items.append((filename, ext, content))
                elif server_path:
                    raw_path = self._resolve_and_verify_server_path(server_path, must_be_dir=False)
                    if raw_path.is_file() and raw_path.suffix.lower() == ".pdf":
                        pdf_staging = TMP_DIR / f".append_pdf_{uuid.uuid4().hex[:12]}"
                        extracted_pages, pdf_meta = unpack_pdf(raw_path, pdf_staging)
                        pdf_temp_dirs.append(pdf_staging)

                        if not target_chapter:
                            total_pages = len(extracted_pages)
                            detected_chaps, _ = detect_pdf_chapters(
                                raw_path,
                                total_pages,
                                new_chapter_title or pdf_meta.get("title") or raw_path.stem,
                            )
                            if len(detected_chaps) > 1:
                                return self._append_multi_chapter_pdf(
                                    source, source_id, fetched, extracted_pages, detected_chaps, new_chapter_title
                                )

                        for _pno, f_path, p_ext in extracted_pages:
                            items.append((f_path.name, p_ext, f_path))
                    elif raw_path.is_dir():
                        pdf_files = [f for f in raw_path.iterdir() if f.is_file() and f.suffix.lower() == ".pdf"]
                        if pdf_files:
                            pdf_files.sort(key=lambda f: self._natural_key(f.name))
                            for pf in pdf_files:
                                pdf_staging = TMP_DIR / f".append_pdf_{uuid.uuid4().hex[:12]}"
                                extracted_pages, _ = unpack_pdf(pf, pdf_staging)
                                pdf_temp_dirs.append(pdf_staging)
                                for _pno, f_path, p_ext in extracted_pages:
                                    items.append((f_path.name, p_ext, f_path))
                        else:
                            img_files = [f for f in raw_path.iterdir() if f.is_file() and f.suffix.lower() in IMAGE_EXTS]
                            img_files.sort(key=lambda f: self._natural_key(f.name))
                            for f in img_files:
                                items.append((f.name, f.suffix.lower(), f))
                    else:
                        raise HTTPException(status_code=400, detail=f"指定路径不是有效的图片/PDF文件或目录：{server_path}")

                if not items:
                    raise HTTPException(status_code=400, detail="未提供有效的图片或 PDF 画卷文件")

                for _idx, (filename, _ext, data_or_path) in enumerate(items, start=1):
                    self._verify_image_item(data_or_path, filename)

                target_pages_dir = self.pages_dir(source, source_id)
                target_pages_dir.mkdir(parents=True, exist_ok=True)

                is_new_chapter = bool(new_chapter_title)
                if is_new_chapter:
                    if not meta.chapters and meta.pages:
                        first_chap_id = "c1"
                        self._migrate_flat_to_chapter(meta, first_chap_id)
                        old_count = len(meta.pages)
                        for p in meta.pages:
                            p.chapter = first_chap_id
                        for rp in fetched.remote_pages:
                            rp.chapter = first_chap_id
                        first_chap = Chapter(
                            id=first_chap_id,
                            index=1,
                            title="第 1 话",
                            page_count=old_count,
                            start=1,
                        )
                        meta.chapters = [first_chap]
                        try:
                            self.ensure_webp_chapter_cover(meta, fetched, first_chap)
                        except Exception as e:
                            logger.warning("Failed to generate cover for synthesized Chapter 1 %s: %s", source_id, e)

                    composite_groups = self._group_by_composite_chapter_pattern(items)
                    if composite_groups:
                        sorted_chap_nums = sorted(composite_groups.keys())
                        for c_order, chap_num in enumerate(sorted_chap_nums):
                            group_items = composite_groups[chap_num]
                            new_chap_idx = len(meta.chapters) + 1
                            new_chap_id = f"c{new_chap_idx}_{datetime.datetime.now().strftime('%M%S')}_{c_order}"
                            chap_dir = target_pages_dir / self._safe(new_chap_id)
                            chap_dir.mkdir(parents=True, exist_ok=True)

                            start_idx = meta.page_count + 1
                            for local_i, (fname, ext, data_to_write) in enumerate(group_items, start=1):
                                dest_name = f"{local_i:05d}{ext}"
                                dest_path = chap_dir / dest_name
                                if isinstance(data_to_write, Path):
                                    self._link_or_copy_file(data_to_write, dest_path)
                                else:
                                    dest_path.write_bytes(data_to_write)

                                cur_idx = meta.page_count + local_i
                                meta.pages.append(PageRecord(index=cur_idx, file=dest_name, ext=ext, cached=True, chapter=new_chap_id))
                                fetched.remote_pages.append(RemotePage(index=cur_idx, url="", file=dest_name, ext=ext, chapter=new_chap_id))

                            meta.page_count += len(group_items)
                            chap_title = f"第 {new_chap_idx} 话"
                            if c_order == 0 and new_chapter_title.strip() and f"第 {new_chap_idx}" not in new_chapter_title:
                                chap_title = new_chapter_title.strip()
                            new_chap = Chapter(
                                id=new_chap_id,
                                index=new_chap_idx,
                                title=chap_title,
                                page_count=len(group_items),
                                start=start_idx,
                            )
                            meta.chapters.append(new_chap)
                            try:
                                self.ensure_webp_chapter_cover(meta, fetched, new_chap)
                                self.ensure_webp_chapter_cover(meta, fetched, new_chap, COVER_THUMB_WIDTH)
                            except Exception as e:
                                logger.warning("Failed to generate cover for new chapter %s: %s", new_chap_id, e)
                    else:
                        new_chap_idx = len(meta.chapters) + 1
                        new_chap_id = f"c{new_chap_idx}_{datetime.datetime.now().strftime('%M%S')}"
                        chap_dir = target_pages_dir / self._safe(new_chap_id)
                        chap_dir.mkdir(parents=True, exist_ok=True)

                        start_idx = meta.page_count + 1
                        for local_i, (_fname, ext, data_or_path) in enumerate(items, start=1):
                            dest_name = f"{local_i:05d}{ext}"
                            dest_path = chap_dir / dest_name
                            if isinstance(data_or_path, Path):
                                self._link_or_copy_file(data_or_path, dest_path)
                            else:
                                dest_path.write_bytes(data_or_path)

                            cur_idx = meta.page_count + local_i
                            meta.pages.append(PageRecord(index=cur_idx, file=dest_name, ext=ext, cached=True, chapter=new_chap_id))
                            fetched.remote_pages.append(RemotePage(index=cur_idx, url="", file=dest_name, ext=ext, chapter=new_chap_id))

                        meta.page_count += len(items)
                        new_chap = Chapter(
                            id=new_chap_id,
                            index=new_chap_idx,
                            title=new_chapter_title.strip() or f"第 {new_chap_idx} 话",
                            page_count=len(items),
                            start=start_idx,
                        )
                        meta.chapters.append(new_chap)
                        try:
                            self.ensure_webp_chapter_cover(meta, fetched, new_chap)
                            self.ensure_webp_chapter_cover(meta, fetched, new_chap, COVER_THUMB_WIDTH)
                        except Exception as e:
                            logger.warning("Failed to generate cover for new chapter %s: %s", new_chap_id, e)
                else:
                    chap_id = target_chapter or (meta.chapters[0].id if meta.chapters else "")
                    chap_dir = (target_pages_dir / self._safe(chap_id)) if chap_id else target_pages_dir
                    chap_dir.mkdir(parents=True, exist_ok=True)

                    existing_in_chap = [p for p in meta.pages if p.chapter == chap_id]
                    offset = len(existing_in_chap)

                    new_chap_pages: list[tuple[str, str]] = []
                    for local_i, (_fname, ext, data_or_path) in enumerate(items, start=1):
                        dest_name = f"{offset + local_i:05d}{ext}"
                        dest_path = chap_dir / dest_name
                        if isinstance(data_or_path, Path):
                            self._link_or_copy_file(data_or_path, dest_path)
                        else:
                            dest_path.write_bytes(data_or_path)
                        new_chap_pages.append((dest_name, ext))

                    if not meta.chapters:
                        for local_i, (dest_name, ext) in enumerate(new_chap_pages, start=1):
                            cur_idx = offset + local_i
                            meta.pages.append(PageRecord(index=cur_idx, file=dest_name, ext=ext, cached=True, chapter=""))
                            fetched.remote_pages.append(RemotePage(index=cur_idx, url="", file=dest_name, ext=ext, chapter=""))
                        meta.page_count = len(meta.pages)
                    else:
                        chap_page_map: dict[str, list[PageRecord]] = {}
                        for ch in meta.chapters:
                            chap_page_map[ch.id] = [p for p in meta.pages if p.chapter == ch.id]

                        if chap_id not in chap_page_map:
                            chap_page_map[chap_id] = []

                        for dest_name, ext in new_chap_pages:
                            chap_page_map[chap_id].append(
                                PageRecord(index=0, file=dest_name, ext=ext, cached=True, chapter=chap_id)
                            )

                        rebuilt_pages: list[PageRecord] = []
                        rebuilt_remote: list[RemotePage] = []
                        global_idx = 1
                        for ch in meta.chapters:
                            ch.start = global_idx
                            ch_pages = chap_page_map.get(ch.id, [])
                            ch.page_count = len(ch_pages)
                            for p in ch_pages:
                                p.index = global_idx
                                rebuilt_pages.append(p)
                                rebuilt_remote.append(
                                    RemotePage(index=global_idx, url="", file=p.file, ext=p.ext, chapter=ch.id)
                                )
                                global_idx += 1

                        meta.pages = rebuilt_pages
                        fetched.remote_pages = rebuilt_remote
                        meta.page_count = len(meta.pages)

                if source != "local":
                    meta.custom_pages = True

                meta.updated_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self.save_fetched(fetched, refresh=False)
                return meta
            finally:
                for d in pdf_temp_dirs:
                    shutil.rmtree(d, ignore_errors=True)

    def replace_pages(
        self: Any,
        source: str,
        source_id: str,
        files: list[tuple[str, bytes]] | None = None,
        server_path: str = "",
        target_chapter: str = "",
    ) -> ComicMeta:
        with self._lock_for(source, source_id):
            fetched = self.load_fetched(source, source_id)
            if fetched is None:
                raise HTTPException(status_code=404, detail="漫画不存在")

            meta = fetched.meta
            valid_items: list[tuple[str, str, bytes | Path]] = []
            pdf_temp_dirs: list[Path] = []
            try:
                if files:
                    sorted_files = sorted(files, key=lambda f: self._natural_key(f[0]))
                    for filename, content in sorted_files:
                        ext = Path(filename).suffix.lower()
                        if ext == ".pdf" and content:
                            pdf_staging = TMP_DIR / f".replace_pdf_{uuid.uuid4().hex[:12]}"
                            pdf_staging.mkdir(parents=True, exist_ok=True)
                            tmp_pdf = pdf_staging / "upload.pdf"
                            tmp_pdf.write_bytes(content)
                            extracted_pages, _ = unpack_pdf(tmp_pdf, pdf_staging / "pages")
                            tmp_pdf.unlink(missing_ok=True)
                            pdf_temp_dirs.append(pdf_staging)
                            for _pno, f_path, p_ext in extracted_pages:
                                valid_items.append((f_path.name, p_ext, f_path))
                        elif ext in IMAGE_EXTS and content:
                            valid_items.append((filename, ext, content))
                elif server_path:
                    raw_path = self._resolve_and_verify_server_path(server_path, must_be_dir=False)
                    if raw_path.is_file() and raw_path.suffix.lower() == ".pdf" and _is_path_allowed(raw_path.resolve()):
                        pdf_staging = TMP_DIR / f".replace_pdf_{uuid.uuid4().hex[:12]}"
                        extracted_pages, _ = unpack_pdf(raw_path, pdf_staging)
                        pdf_temp_dirs.append(pdf_staging)
                        for _pno, f_path, p_ext in extracted_pages:
                            valid_items.append((f_path.name, p_ext, f_path))
                    elif raw_path.is_dir():
                        img_files = [
                            f
                            for f in raw_path.iterdir()
                            if f.is_file() and f.suffix.lower() in IMAGE_EXTS and _is_path_allowed(f.resolve())
                        ]
                        img_files.sort(key=lambda f: self._natural_key(f.name))
                        for f in img_files:
                            valid_items.append((f.name, f.suffix.lower(), f))
                    elif raw_path.is_file() and raw_path.suffix.lower() in IMAGE_EXTS and _is_path_allowed(raw_path.resolve()):
                        valid_items.append((raw_path.name, raw_path.suffix.lower(), raw_path))
                    else:
                        raise HTTPException(status_code=400, detail=f"指定路径不是有效的图片/PDF文件或目录：{server_path}")

                if not valid_items:
                    raise HTTPException(status_code=400, detail="未提供有效的图片或 PDF 画卷文件")

                staging_dir = self._new_work_item(".tmp_replace")

                for _idx, (filename, _ext, content_or_path) in enumerate(valid_items, start=1):
                    try:
                        self._verify_image_item(content_or_path, filename)
                    except Exception:
                        shutil.rmtree(staging_dir, ignore_errors=True)
                        raise

                target_pages_dir = self.pages_dir(source, source_id)
                target_pages_dir.mkdir(parents=True, exist_ok=True)

                if target_chapter and meta.chapters:
                    target_ch = next((c for c in meta.chapters if c.id == target_chapter), None)
                    if not target_ch:
                        shutil.rmtree(staging_dir, ignore_errors=True)
                        raise HTTPException(status_code=404, detail=f"章节 {target_chapter} 不存在")

                    staged_names: list[tuple[str, str]] = []
                    for idx, (_filename, ext, content_or_path) in enumerate(valid_items, start=1):
                        dest_name = f"{idx:05d}{ext}"
                        dest_path = staging_dir / dest_name
                        if isinstance(content_or_path, Path):
                            self._link_or_copy_file(content_or_path, dest_path)
                        else:
                            dest_path.write_bytes(content_or_path)
                        staged_names.append((dest_name, ext))

                    chap_dir = target_pages_dir / self._safe(target_chapter)
                    album_path = self.album_path(source, source_id)
                    remote_path = self.remote_path(source, source_id)
                    backup_dir = self._begin_metadata_backup(album_path, remote_path)
                    installed = False
                    try:
                        self._replace_live_with_staging(backup_dir, staging_dir, chap_dir)
                        installed = True
                    except Exception:
                        if not installed:
                            self._rollback_metadata_backup(
                                backup_dir, (remote_path, album_path), source, source_id
                            )
                        shutil.rmtree(staging_dir, ignore_errors=True)
                        raise

                    chap_page_map: dict[str, list[PageRecord]] = {}
                    for ch in meta.chapters:
                        if ch.id == target_chapter:
                            chap_page_map[ch.id] = [
                                PageRecord(index=0, file=dest_name, ext=ext, cached=True, chapter=ch.id)
                                for dest_name, ext in staged_names
                            ]
                        else:
                            chap_page_map[ch.id] = [p for p in meta.pages if p.chapter == ch.id]

                    rebuilt_pages: list[PageRecord] = []
                    rebuilt_remote: list[RemotePage] = []
                    global_idx = 1
                    for ch in meta.chapters:
                        ch.start = global_idx
                        ch_pages = chap_page_map.get(ch.id, [])
                        ch.page_count = len(ch_pages)
                        for p in ch_pages:
                            p.index = global_idx
                            rebuilt_pages.append(p)
                            rebuilt_remote.append(
                                RemotePage(index=global_idx, url="", file=p.file, ext=p.ext, chapter=ch.id)
                            )
                            global_idx += 1

                    meta.pages = rebuilt_pages
                    fetched.remote_pages = rebuilt_remote
                    meta.page_count = len(meta.pages)
                    meta.custom_pages = True

                    meta.updated_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    try:
                        self.save_fetched(fetched, refresh=False, backup_dir=backup_dir)
                    except Exception:
                        shutil.rmtree(staging_dir, ignore_errors=True)
                        raise

                    chap_thumbs_dir = self.thumbs_dir(source, source_id) / self._safe(target_chapter)
                    if chap_thumbs_dir.exists():
                        shutil.rmtree(chap_thumbs_dir, ignore_errors=True)

                    try:
                        self.ensure_webp_chapter_cover(meta, fetched, target_ch)
                        self.ensure_webp_chapter_cover(meta, fetched, target_ch, COVER_THUMB_WIDTH)
                    except Exception as e:
                        logger.warning("Failed to regenerate cover for chapter %s: %s", target_chapter, e)

                    if target_ch.start <= 4:
                        for i in range(1, min(5, meta.page_count + 1)):
                            try:
                                self.ensure_webp_cover(meta, fetched, i)
                                self.ensure_webp_cover(meta, fetched, i, COVER_THUMB_WIDTH)
                            except Exception as e:
                                logger.warning("Failed to regenerate cover %d for %s/%s: %s", i, source, source_id, e)
                    return meta

                else:
                    composite_groups = self._group_by_composite_chapter_pattern(valid_items)
                    if composite_groups:
                        sorted_chap_nums = sorted(composite_groups.keys())
                        existing_chaps = meta.chapters or []
                        new_chapters: list[Chapter] = []
                        rebuilt_pages: list[PageRecord] = []
                        rebuilt_remote: list[RemotePage] = []
                        global_idx = 1

                        try:
                            for chap_idx, chap_num in enumerate(sorted_chap_nums, start=1):
                                chap_items = composite_groups[chap_num]
                                matched_ch = None
                                for old_c in existing_chaps:
                                    if old_c.index == chap_num or old_c.id == str(chap_num) or old_c.id == f"c{chap_num}":
                                        matched_ch = old_c
                                        break
                                if not matched_ch and chap_idx <= len(existing_chaps):
                                    matched_ch = existing_chaps[chap_idx - 1]

                                chap_title = matched_ch.title if matched_ch else f"第 {chap_num} 话"
                                chap_id = matched_ch.id if matched_ch else f"c{chap_num}"
                                chap_staging_dir = staging_dir / self._safe(chap_id)
                                chap_staging_dir.mkdir(parents=True, exist_ok=True)

                                start_page = global_idx
                                for local_i, (_filename, ext, content_or_path) in enumerate(chap_items, start=1):
                                    dest_name = f"{local_i:05d}{ext}"
                                    dest_path = chap_staging_dir / dest_name
                                    if isinstance(content_or_path, Path):
                                        self._link_or_copy_file(content_or_path, dest_path)
                                    else:
                                        dest_path.write_bytes(content_or_path)
                                    rebuilt_pages.append(
                                        PageRecord(index=global_idx, file=dest_name, ext=ext, cached=True, chapter=chap_id)
                                    )
                                    rebuilt_remote.append(
                                        RemotePage(index=global_idx, url="", file=dest_name, ext=ext, chapter=chap_id)
                                    )
                                    global_idx += 1

                                new_chapters.append(
                                    Chapter(
                                        id=chap_id,
                                        index=chap_idx,
                                        title=chap_title,
                                        page_count=len(chap_items),
                                        start=start_page,
                                    )
                                )
                        except Exception:
                            shutil.rmtree(staging_dir, ignore_errors=True)
                            raise

                        album_path = self.album_path(source, source_id)
                        remote_path = self.remote_path(source, source_id)
                        backup_dir = self._begin_metadata_backup(album_path, remote_path)
                        installed = False
                        try:
                            self._replace_live_with_staging(backup_dir, staging_dir, target_pages_dir)
                            installed = True
                        except Exception:
                            if not installed:
                                self._rollback_metadata_backup(
                                    backup_dir, (remote_path, album_path), source, source_id
                                )
                            shutil.rmtree(staging_dir, ignore_errors=True)
                            raise

                        meta.pages = rebuilt_pages
                        fetched.remote_pages = rebuilt_remote
                        meta.page_count = len(rebuilt_pages)
                        meta.chapters = new_chapters

                    else:
                        staged_names: list[tuple[str, str]] = []
                        for idx, (_filename, ext, content_or_path) in enumerate(valid_items, start=1):
                            dest_name = f"{idx:05d}{ext}"
                            dest_path = staging_dir / dest_name
                            if isinstance(content_or_path, Path):
                                self._link_or_copy_file(content_or_path, dest_path)
                            else:
                                dest_path.write_bytes(content_or_path)
                            staged_names.append((dest_name, ext))

                        album_path = self.album_path(source, source_id)
                        remote_path = self.remote_path(source, source_id)
                        backup_dir = self._begin_metadata_backup(album_path, remote_path)
                        installed = False
                        try:
                            self._replace_live_with_staging(backup_dir, staging_dir, target_pages_dir)
                            installed = True
                        except Exception:
                            if not installed:
                                self._rollback_metadata_backup(
                                    backup_dir, (remote_path, album_path), source, source_id
                                )
                            shutil.rmtree(staging_dir, ignore_errors=True)
                            raise

                        new_pages = [
                            PageRecord(index=i, file=dest_name, ext=ext, cached=True, chapter="")
                            for i, (dest_name, ext) in enumerate(staged_names, start=1)
                        ]
                        new_remote = [
                            RemotePage(index=i, url="", file=dest_name, ext=ext, chapter="")
                            for i, (dest_name, ext) in enumerate(staged_names, start=1)
                        ]
                        meta.pages = new_pages
                        fetched.remote_pages = new_remote
                        meta.page_count = len(new_pages)
                        meta.chapters = []

                    meta.custom_pages = True
                    meta.cover_count = min(4, meta.page_count)
                    meta.cover_indices = []
                    meta.updated_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    try:
                        self.save_fetched(fetched, refresh=False, backup_dir=backup_dir)
                    except Exception:
                        shutil.rmtree(staging_dir, ignore_errors=True)
                        raise

                    thumbs_dir = self.thumbs_dir(source, source_id)
                    covers_dir = self.covers_dir(source, source_id)
                    shutil.rmtree(thumbs_dir, ignore_errors=True)
                    shutil.rmtree(covers_dir, ignore_errors=True)
                    thumbs_dir.mkdir(parents=True, exist_ok=True)
                    covers_dir.mkdir(parents=True, exist_ok=True)

                    if meta.chapters:
                        for ch in meta.chapters:
                            try:
                                self.ensure_webp_chapter_cover(meta, fetched, ch)
                                self.ensure_webp_chapter_cover(meta, fetched, ch, COVER_THUMB_WIDTH)
                            except Exception as e:
                                logger.warning("Failed to generate chapter cover for %s: %s", ch.id, e)

                    for i in range(1, min(5, meta.page_count + 1)):
                        try:
                            self.ensure_webp_cover(meta, fetched, i)
                            self.ensure_webp_cover(meta, fetched, i, COVER_THUMB_WIDTH)
                        except Exception as e:
                            logger.warning("Failed to regenerate cover %d for %s/%s: %s", i, source, source_id, e)
                    return meta
            finally:
                for d in pdf_temp_dirs:
                    shutil.rmtree(d, ignore_errors=True)
