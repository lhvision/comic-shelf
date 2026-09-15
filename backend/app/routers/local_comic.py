"""Local comic creation, server directory import, file uploads, page appending and replacement router."""
from __future__ import annotations

import asyncio
import time
from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from ..db import delete_comic_dialogues, sync_comic_dialogues
from ..events import broadcast_event
from ..models import (
    ComicAppendRequest,
    ComicDetail,
    ComicMeta,
    LocalComicCreateRequest,
    LocalPathImportRequest,
    ReplacePathRequest,
)
from .common import _require_known_source, store

router = APIRouter(tags=["local_comic"])

MAX_UPLOAD_PAGE_SIZE = 50 * 1024 * 1024  # 50MB per single page


async def _read_uploaded_files(files: list[UploadFile]) -> list[tuple[str, bytes]]:
    """Reads uploaded files asynchronously into filename and byte-content tuples."""
    file_tuples: list[tuple[str, bytes]] = []
    for f in files:
        content = await f.read()
        if content:
            if len(content) > MAX_UPLOAD_PAGE_SIZE:
                raise HTTPException(
                    status_code=413,
                    detail=f"单个图片文件过大（超过 50MB）：{f.filename or 'upload'}",
                )
            file_tuples.append((f.filename or "page.webp", content))
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
    """Replaces comic or chapter pages with newly uploaded image files, purging prior OCR dialogues."""
    _require_known_source(source)
    delete_comic_dialogues(source, source_id)
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
    """Replaces comic or chapter pages with images from a server-side directory, purging prior OCR dialogues."""
    _require_known_source(source)
    delete_comic_dialogues(source, source_id)
    meta = store.replace_pages(
        source=source,
        source_id=source_id,
        server_path=req.server_path,
        target_chapter=req.target_chapter,
    )
    return _finish_pages_update(source, source_id, meta)
