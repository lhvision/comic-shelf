"""Local comic creation, server directory import, file uploads, page appending and replacement router."""
from __future__ import annotations

import asyncio
import os
import re
import time
import uuid
from pathlib import Path
from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile

from ..config import TMP_DIR
from ..db import sync_comic_dialogues
from ..events import broadcast_event
from ..models import (
    ComicAppendRequest,
    ComicDetail,
    ComicMeta,
    CreateFromStagedPdfRequest,
    LocalComicCreateRequest,
    LocalPathImportRequest,
    PdfInspectResponse,
    ReplacePathRequest,
)
from .common import _require_known_source, store

router = APIRouter(tags=["local_comic"])

MAX_UPLOAD_PAGE_SIZE = 50 * 1024 * 1024  # 50MB per single page
MAX_PDF_UPLOAD_SIZE = 1024 * 1024 * 1024  # 1GB per PDF upload


async def _read_uploaded_files(files: list[UploadFile]) -> list[tuple[str, bytes]]:
    """Reads uploaded files asynchronously into filename and byte-content tuples."""
    file_tuples: list[tuple[str, bytes]] = []
    for f in files:
        content = await f.read()
        if content:
            is_pdf = (f.filename or "").lower().endswith(".pdf")
            max_size = MAX_PDF_UPLOAD_SIZE if is_pdf else MAX_UPLOAD_PAGE_SIZE
            if len(content) > max_size:
                limit_str = "1GB" if is_pdf else "50MB"
                raise HTTPException(
                    status_code=413,
                    detail=f"文件过大（超过 {limit_str}）：{f.filename or 'upload'}",
                )
            file_tuples.append((f.filename or ("upload.pdf" if is_pdf else "page.webp"), content))
    return file_tuples


def _finish_pages_update(source: str, source_id: str, meta: ComicMeta) -> ComicDetail:
    """Syncs OCR dialogues, broadcasts library change event, and returns serialized ComicDetail."""
    sync_comic_dialogues(source, source_id)
    broadcast_event(
        "library_changed",
        {"action": "update_pages", "source": source, "source_id": source_id, "timestamp": time.time()},
    )
    return store.detail(meta)


@router.post("/api/library/local/create", response_model=ComicDetail)
def create_local_comic(req: LocalComicCreateRequest) -> ComicDetail:
    """Creates a new empty local comic entry in the library."""
    meta = store.create_local_comic(req)
    broadcast_event(
        "library_changed",
        {"action": "import", "source": "local", "source_id": meta.source_id, "timestamp": time.time()},
    )
    return store.detail(meta)


@router.post("/api/library/local/import-path", response_model=ComicDetail)
def import_local_path(req: LocalPathImportRequest) -> ComicDetail:
    """Imports an existing server-side image folder or archive into the local library."""
    meta = store.import_local_path(req)
    broadcast_event(
        "library_changed",
        {"action": "import", "source": "local", "source_id": meta.source_id, "timestamp": time.time()},
    )
    return store.detail(meta)


@router.post("/api/library/local/inspect-pdf", response_model=PdfInspectResponse)
async def inspect_pdf(
    server_path: str = Form(default=""),
    file: UploadFile | None = File(default=None),
) -> PdfInspectResponse:
    """Inspects a PDF from uploaded file or server path, unpacks pages to staging, and detects chapters."""
    if file and file.filename:
        raw_name = Path(file.filename).name
        safe_name = re.sub(r"[^a-zA-Z0-9._-]", "_", raw_name) or "upload.pdf"
        tmp_pdf = TMP_DIR / f".upload_{uuid.uuid4().hex[:12]}_{safe_name}"
        total_read = 0
        try:
            with open(tmp_pdf, "wb") as f:
                while chunk := await file.read(1024 * 1024):
                    total_read += len(chunk)
                    if total_read > MAX_PDF_UPLOAD_SIZE:
                        raise HTTPException(status_code=413, detail="PDF 文件体积过大（超过 1GB 上限）。")
                    f.write(chunk)
            return await asyncio.to_thread(store.inspect_pdf_file, tmp_pdf)
        finally:
            tmp_pdf.unlink(missing_ok=True)
    elif server_path and server_path.strip():
        resolved = store._resolve_and_verify_server_path(server_path.strip(), must_be_dir=False)
        if not resolved.is_file():
            raise HTTPException(status_code=400, detail=f"指定的路径不是文件：{server_path}")
        return await asyncio.to_thread(store.inspect_pdf_file, resolved)
    else:
        raise HTTPException(status_code=400, detail="请上传 PDF 文件或指定合法的服务器 PDF 路径。")


@router.delete("/api/library/local/staged-pdf/{staging_token}")
def delete_staged_pdf(staging_token: str) -> dict[str, bool]:
    """Cancels and purges staged PDF temporary assets."""
    success = store.delete_staged_pdf(staging_token)
    return {"ok": success}


@router.post("/api/library/local/create-from-staged-pdf", response_model=ComicDetail)
def create_from_staged_pdf(req: CreateFromStagedPdfRequest) -> ComicDetail:
    """Creates a local comic from staged PDF pages using confirmed chapters."""
    meta = store.create_from_staged_pdf(req)
    broadcast_event(
        "library_changed",
        {"action": "import", "source": "local", "source_id": meta.source_id, "timestamp": time.time()},
    )
    return store.detail(meta)


@router.post("/api/library/{source}/{source_id}/upload-pages", response_model=ComicDetail)
async def upload_comic_pages(
    source: str,
    source_id: str,
    chapter_id: str = Query(default="", description="目标章节 id"),
    new_chapter_title: str = Query(default="", description="若创建新章节，传入新章节标题"),
    files: list[UploadFile] = File(...),
) -> ComicDetail:
    """Uploads and appends image files to an existing chapter or a newly created chapter."""
    _require_known_source(source)
    file_tuples = await _read_uploaded_files(files)
    meta = await asyncio.to_thread(
        store.append_pages,
        source_id=source_id,
        source=source,
        files=file_tuples,
        target_chapter=chapter_id,
        new_chapter_title=new_chapter_title,
    )
    return _finish_pages_update(source, source_id, meta)


@router.post("/api/library/{source}/{source_id}/append", response_model=ComicDetail)
def append_comic(
    source: str,
    source_id: str,
    req: ComicAppendRequest,
) -> ComicDetail:
    """Appends pages from a server-side directory to an existing or new chapter."""
    _require_known_source(source)
    meta = store.append_pages(
        source_id=source_id,
        source=source,
        server_path=req.server_path,
        target_chapter=req.target_chapter,
        new_chapter_title=req.new_chapter_title,
    )
    return _finish_pages_update(source, source_id, meta)


@router.post("/api/library/{source}/{source_id}/replace-pages", response_model=ComicDetail)
async def replace_comic_pages(
    source: str,
    source_id: str,
    chapter_id: str = Query(default="", description="目标章节 id（多章节漫画可选）"),
    files: list[UploadFile] = File(...),
) -> ComicDetail:
    """Replaces comic or chapter pages with newly uploaded image files, purging prior OCR dialogues upon success."""
    _require_known_source(source)
    file_tuples = await _read_uploaded_files(files)
    meta = await asyncio.to_thread(
        store.replace_pages,
        source=source,
        source_id=source_id,
        files=file_tuples,
        target_chapter=chapter_id,
    )
    return _finish_pages_update(source, source_id, meta)


@router.post("/api/library/{source}/{source_id}/replace-path", response_model=ComicDetail)
def replace_comic_pages_from_path(
    source: str,
    source_id: str,
    req: ReplacePathRequest,
) -> ComicDetail:
    """Replaces comic or chapter pages with images from a server-side directory, purging prior OCR dialogues upon success."""
    _require_known_source(source)
    meta = store.replace_pages(
        source=source,
        source_id=source_id,
        server_path=req.server_path,
        target_chapter=req.target_chapter,
    )
    return _finish_pages_update(source, source_id, meta)
