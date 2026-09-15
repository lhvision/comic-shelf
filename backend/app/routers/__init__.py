"""Modular API Routers for Paper Room backend."""
from __future__ import annotations

from .auth import router as auth_router
from .chapters import router as chapters_router
from .library import router as library_router
from .local_comic import router as local_comic_router
from .media import router as media_router
from .search import router as search_router
from .system import router as system_router

__all__ = [
    "auth_router",
    "chapters_router",
    "library_router",
    "local_comic_router",
    "media_router",
    "search_router",
    "system_router",
]
