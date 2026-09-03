"""Redis-backed caching for the vehicle intelligence engine (Phase 5)."""

from __future__ import annotations

import json
from typing import Any

from src.core.redis import redis_client


def _key(prefix: str, *parts: Any) -> str:
    return "p5:" + prefix + ":" + ":".join(str(p) for p in parts)


async def cache_get_json(prefix: str, *parts: Any) -> Any | None:
    """Get a JSON value from cache, or None on miss / connectivity failure."""
    try:
        raw = await redis_client.get(_key(prefix, *parts))
    except Exception:  # noqa: BLE001 - cache must never break the request
        return None
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):  # noqa: BLE001
        return None


async def cache_set_json(
    prefix: str, value: Any, *parts: Any, ttl: int = 300
) -> None:
    """Set a JSON value in cache, ignoring connectivity failures."""
    try:
        await redis_client.set(_key(prefix, *parts), json.dumps(value), ex=ttl)
    except Exception:  # noqa: BLE001
        pass
