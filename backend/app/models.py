from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PageRecord(BaseModel):
    """A cached page descriptor (no remote URL leaked to the UI).

    ``chapter`` identifies the chapter this page belongs to. For legacy
    single-chapter albums (and new single-chapter imports) it is empty, so
    the on-disk layout stays the flat ``pages/<file>`` we've always used.
    Multi-chapter albums set it to the chapter id, and storage routes the page
    into ``pages/<chapter>/<file>`` (and ``thumbs/<chapter>/``).
    """

    index: int
    file: str
    ext: str
    cached: bool = False
    chapter: str = ""


class Chapter(BaseModel):
    """One chapter/section inside a multi-chapter album.

    ``start`` is the 1-based *global* page index at which this chapter begins,
    so the whole album can still be addressed as one flat ``pages`` list
    (uniform reader page numbers, covers from the first chapter, etc.).
    """

    id: str = Field(description="Chapter/section id, e.g. JM photo id")
    index: int = Field(description="1-based chapter ordinal within the album")
    title: str = Field(default="", description="Chapter title, e.g. 第 1 話")
    page_count: int = Field(default=0, description="Pages inside this chapter")
    start: int = Field(ge=1, description="1-based global page index of the first page")


class ComicMeta(BaseModel):
    """Provider-neutral comic metadata.

    Providers translate their native format into this shape, so the UI and the
    on-disk cache never need to know about a specific comic site.
    """

    source: str = Field(description="Provider key, e.g. 'jm'")
    source_id: str = Field(description="Original id, e.g. '523607'")
    display_id: str = Field(description="Human id, e.g. 'JM523607'")
    title: str
    authors: list[str] = Field(default_factory=list)
    works: list[str] = Field(default_factory=list)
    actors: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    description: str = ""
    uploader: str | None = None
    page_count: int = 0
    published_at: str = ""
    updated_at: str = ""
    views: str = ""
    likes: str = ""
    comment_count: int = 0
    favorite: bool = False
    hidden_from_guest: bool = Field(
        default=False,
        description="True if comic is visible to curator only and hidden from guests",
    )
    cover_count: int = 4
    cover_indices: list[int] = Field(
        default_factory=list,
        description="Explicit 1-based page indices to use as covers (up to 4 items); empty defaults to 1..min(cover_count, page_count)",
    )
    custom_pages: bool = Field(
        default=False,
        description="True if pages were manually replaced by curator, preventing remote auto-overwrite",
    )
    source_url: str = ""
    pages: list[PageRecord] = Field(default_factory=list)
    imported_at: str = ""
    last_checked_at: str = ""
    raw: dict[str, Any] = Field(default_factory=dict)
    chapters: list[Chapter] = Field(
        default_factory=list,
        description="Chapter/section list for multi-chapter albums; empty for single-chapter",
    )

    @property
    def is_multi_chapter(self) -> bool:
        return len(self.chapters) > 1

    def cover_paths(self) -> list[str]:
        if self.page_count == 0:
            return []
        count = len(self.cover_indices) if self.cover_indices else min(self.cover_count, self.page_count)
        v_tag = ""
        if self.updated_at:
            import hashlib
            v_tag = f"?v={hashlib.md5(self.updated_at.encode()).hexdigest()[:8]}"
        return [
            f"/api/library/{self.source}/{self.source_id}/covers/{index}/file.jpg{v_tag}"
            for index in range(1, max(1, count) + 1)
        ]


class RemotePage(BaseModel):
    """Where a page can be downloaded from. Kept server-side only."""

    index: int
    url: str
    file: str
    ext: str
    headers: dict[str, str] = Field(default_factory=dict)
    scramble_id: str = ""
    """JM-specific scramble key. Other providers can leave it empty."""
    chapter: str = ""
    """Chapter id this page belongs to (multi-chapter albums); empty otherwise."""


class FetchedComic(BaseModel):
    meta: ComicMeta
    remote_pages: list[RemotePage] = Field(default_factory=list)


class ImportRequest(BaseModel):
    id: str
    source: str = "jm"
    prefetch_covers: int = 4
    prefetch_all: bool = False
    refresh: bool = False


class ImportResult(BaseModel):
    meta: ComicMeta
    from_cache: bool
    prefetched: int = 0
    warnings: list[str] = Field(default_factory=list)
    background: bool = False
    """True when page caching is still running in the background."""


class JobInfo(BaseModel):
    source: str
    source_id: str
    running: bool
    done: bool
    total: int
    prefetched: int
    warnings: list[str] = Field(default_factory=list)
    error: str = ""
    started_at: float | None = None
    finished_at: float | None = None


class ConcurrencyInfo(BaseModel):
    limit: int
    min: int
    max: int
    env_controlled: bool


class ConcurrencyRequest(BaseModel):
    limit: int = Field(ge=1, le=16)


class LibrarySummary(BaseModel):
    source: str
    source_id: str
    display_id: str
    title: str
    authors: list[str]
    works: list[str]
    actors: list[str]
    tags: list[str]
    favorite: bool = False
    hidden_from_guest: bool = False
    page_count: int
    views: str
    likes: str
    uploaded_at: str = ""
    published_at: str = ""
    updated_at: str = ""
    imported_at: str = ""
    cover_paths: list[str]
    cached_pages: int
    cover_count: int
    chapter_titles: list[str] = Field(
        default_factory=list,
        description="Chapter titles, so the shelf search can match '第 5 话' too",
    )


class ComicDetail(BaseModel):
    meta: ComicMeta
    cached_pages: int
    cache_complete: bool
    cover_paths: list[str]


class PageResponse(BaseModel):
    index: int
    url: str
    cached: bool


class CacheProgress(BaseModel):
    cached: int
    total: int
    complete: bool


class DeleteResponse(BaseModel):
    ok: bool
    source: str
    source_id: str


class FavoriteRequest(BaseModel):
    favorite: bool = True


class FavoriteResponse(BaseModel):
    ok: bool
    favorite: bool


class ProviderInfo(BaseModel):
    key: str
    label: str
    short_label: str = ""
    id_pattern: str
    example: str
    description: str


class ImageSearchItem(BaseModel):
    source: str
    source_id: str
    page_index: int
    is_cover: bool
    score: float


class ImageSearchResponse(BaseModel):
    results: list[ImageSearchItem]


class ImageSearchStatusResponse(BaseModel):
    available: bool
    url: str


class AuthStatusResponse(BaseModel):
    auth_required: bool
    authenticated: bool
    can_write: bool = True
    role: str = "admin"  # "admin" | "guest" | "unauthorized"
    username: str = ""
    user_id: str = ""


class LoginRequest(BaseModel):
    secret: str


class LoginResponse(BaseModel):
    ok: bool
    token: str
    role: str = "admin"  # "admin" | "guest"
    username: str = ""
    user_id: str = ""
    device_token: str = ""


class GuestDeviceItem(BaseModel):
    id: int
    pass_id: int
    device_token: str
    device_name: str
    user_agent: str = ""
    last_ip: str = ""
    created_at: int
    last_active_at: int


class GuestPassItem(BaseModel):
    id: int
    username: str
    token: str
    expires_at: int | None = None
    is_active: bool
    is_expired: bool
    max_devices: int = 2
    device_count: int = 0
    devices: list[GuestDeviceItem] = Field(default_factory=list)
    activation_status: str = "pending"  # "pending" | "active" | "full" | "disabled" | "expired"
    is_cooling_locked: bool = False
    is_rate_limited: bool = False
    created_at: int
    updated_at: int


class GuestPrivacySettings(BaseModel):
    guest_hide_new_comics: bool = False


class CreateGuestPassRequest(BaseModel):
    username: str
    expires_days: int | None = Field(default=None, gt=0)
    custom_token: str | None = None
    max_devices: int = Field(default=2, ge=1, le=5)


class UpdateGuestPassRequest(BaseModel):
    username: str | None = None
    is_active: bool | None = None
    extend_days: int | None = Field(default=None, gt=0)
    reset_token: bool = False
    expires_days: int | None = Field(default=None, gt=0)
    max_devices: int | None = Field(default=None, ge=1, le=5)


class ReadingProgressRequest(BaseModel):
    page: int = Field(ge=1)
    total_pages: int = 0


class ReadingProgressResponse(BaseModel):
    ok: bool = True
    last_page: int
    total_pages: int
    updated_at: int


class MetadataUpdateRequest(BaseModel):
    title: str | None = None
    authors: list[str] | None = None
    works: list[str] | None = None
    actors: list[str] | None = None
    tags: list[str] | None = None
    description: str | None = None
    uploader: str | None = None
    cover_indices: list[int] | None = None
    hidden_from_guest: bool | None = None
    custom_pages: bool | None = None


class LocalChapterInput(BaseModel):
    id: str
    title: str = ""


class LocalComicCreateRequest(BaseModel):
    id: str = ""
    title: str
    authors: list[str] = Field(default_factory=list)
    works: list[str] = Field(default_factory=list)
    actors: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    description: str = ""
    uploader: str = "自制"
    chapters: list[LocalChapterInput] = Field(default_factory=list)
    cover_indices: list[int] = Field(default_factory=list)
    hidden_from_guest: bool = False


class LocalPathImportRequest(BaseModel):
    path: str
    id: str = ""
    title: str = ""
    authors: list[str] = Field(default_factory=list)
    works: list[str] = Field(default_factory=list)
    actors: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    description: str = ""
    uploader: str = "本地导入"
    cover_indices: list[int] = Field(default_factory=list)
    hidden_from_guest: bool = False


class LocalAppendRequest(BaseModel):
    target_chapter: str = ""
    new_chapter_title: str = ""
    server_path: str = ""


class ReplacePathRequest(BaseModel):
    server_path: str = ""
    target_chapter: str = ""


class ChapterUpdateRequest(BaseModel):
    title: str = ""


class DiscoveryItem(BaseModel):
    id: str
    source_id: str
    source: str = "jm"
    title: str
    author: str = ""
    category: str = ""
    cover_url: str = ""
    url: str = ""
    updated_at: str = ""
    in_library: bool = False


class DiscoveryFeed(BaseModel):
    timeframe: str  # "week" | "month" | "day"
    updated_at: str = ""
    items: list[DiscoveryItem] = Field(default_factory=list)



