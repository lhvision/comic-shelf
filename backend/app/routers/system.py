"""System health, provider enumeration, download concurrency, and guest privacy settings router."""
from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Request

from ..auth import is_auth_required, require_curator
from ..gate import (
    _env_explicit,
    get_download_concurrency,
    get_guest_hide_new_comics,
    set_download_concurrency,
    set_guest_hide_new_comics,
)
from ..jobs import list_running
from ..models import (
    ConcurrencyInfo,
    ConcurrencyRequest,
    GuestPrivacySettings,
    JobInfo,
    ProviderInfo,
)
from ..providers import provider_list

router = APIRouter(tags=["system"])


@router.get("/api/health")
def health() -> dict[str, Any]:
    """Liveness probe. 这个端点在免鉴权白名单里，所以只报能力、不报宿主机路径。"""
    return {
        "ok": True,
        "providers": [p["key"] for p in provider_list()],
        "auth_required": is_auth_required(),
    }


@router.get("/api/providers", response_model=list[ProviderInfo])
def providers() -> list[ProviderInfo]:
    """Lists registered comic metadata and image download providers."""
    return [ProviderInfo(**p) for p in provider_list()]


@router.get("/api/cache/jobs", response_model=list[JobInfo])
def running_cache_jobs() -> list[JobInfo]:
    """Running background prefetch jobs, for live shelf-card progress."""
    return [JobInfo(**job) for job in list_running()]


@router.get("/api/settings/download-concurrency", response_model=ConcurrencyInfo)
def download_concurrency_get() -> ConcurrencyInfo:
    """Returns current active image download concurrency limits."""
    return ConcurrencyInfo(
        limit=get_download_concurrency(),
        min=1,
        max=16,
        env_controlled=_env_explicit(),
    )


@router.put("/api/settings/download-concurrency", response_model=ConcurrencyInfo)
def download_concurrency_put(req: ConcurrencyRequest) -> ConcurrencyInfo:
    """Dynamically updates image download concurrency limit."""
    limit = set_download_concurrency(req.limit)
    return ConcurrencyInfo(
        limit=limit,
        min=1,
        max=16,
        env_controlled=_env_explicit(),
    )


@router.get("/api/settings/guest-privacy", response_model=GuestPrivacySettings)
def guest_privacy_get() -> GuestPrivacySettings:
    """Queries guest privacy default configuration for newly imported comics."""
    return GuestPrivacySettings(guest_hide_new_comics=get_guest_hide_new_comics())


@router.put("/api/settings/guest-privacy", response_model=GuestPrivacySettings)
def guest_privacy_put(req: GuestPrivacySettings, request: Request) -> GuestPrivacySettings:
    """Updates guest privacy default configuration (curator only)."""
    require_curator(request)
    val = set_guest_hide_new_comics(req.guest_hide_new_comics)
    return GuestPrivacySettings(guest_hide_new_comics=val)
