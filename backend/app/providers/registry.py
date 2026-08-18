from __future__ import annotations

from .base import ComicProvider
from .jm import JMProvider

PROVIDERS: dict[str, ComicProvider] = {
    "jm": JMProvider(),
}


def get_provider(key: str) -> ComicProvider:
    try:
        return PROVIDERS[key]
    except KeyError as exc:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=404,
            detail=f"Unknown source '{key}'. Available sources: {', '.join(PROVIDERS)}",
        ) from exc


def provider_list() -> list[dict]:
    return [
        {
            **provider.describe(),
            "description": provider.__doc__ or "",
        }
        for provider in PROVIDERS.values()
    ]
