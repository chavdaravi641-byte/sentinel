"""Part 4 — API security: rate limiting, CSRF, replay protection & validation.

Modular, testable helpers used by the HTTP middleware. Rate limiting and replay
nonces prefer Redis but degrade to an in-memory store so the behaviour is safe
both in the live stack (Redis) and in tests (no Redis).
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any

from src.core.config import settings
from src.security.core import compute_signature

_utcnow = lambda: datetime.now(timezone.utc)  # noqa: E731


class SlidingWindowStore:
    """In-memory sliding-window rate limiter (fallback when Redis is absent)."""

    def __init__(self) -> None:
        self._buckets: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def hit(self, key: str, limit: int, window: int) -> tuple[bool, int]:
        """Record a hit; return (allowed, remaining)."""
        now = time.monotonic()
        async with self._lock:
            dq = self._buckets[key]
            while dq and now - dq[0] > window:
                dq.popleft()
            if len(dq) >= limit:
                remaining = 0
                return False, remaining
            dq.append(now)
            return True, max(0, limit - len(dq))


# Shared in-memory fallback store.
_inmem_store = SlidingWindowStore()


async def rate_limit_hit(
    key: str,
    *,
    limit: int | None = None,
    window: int | None = None,
    login_path: bool = False,
) -> tuple[bool, int]:
    """Evaluate a rate-limit for a client key. Returns (allowed, remaining).

    Uses Redis when available, otherwise the in-memory fallback. The effective
    limit is the stricter login-specific limit when ``login_path`` is True.
    """
    if not settings.RATE_LIMIT_ENABLED:
        return True, limit or settings.RATE_LIMIT_BASE_REQUESTS
    limit = limit or settings.RATE_LIMIT_BASE_REQUESTS
    window = window or settings.RATE_LIMIT_WINDOW_SECONDS
    if login_path:
        limit = min(limit, settings.RATE_LIMIT_LOGIN_REQUESTS)

    try:
        from src.core.redis import redis_client

        now = int(time.time())
        bucket = now // window
        rkey = f"rl:{key}:{bucket}"
        async with _redis_lock(key):
            count = int(await redis_client.get(rkey) or 0)
            if count >= limit:
                return False, 0
            await redis_client.incr(rkey)
            if count == 0:
                await redis_client.expire(rkey, window * 2)
            return True, max(0, limit - (count + 1))
    except Exception:
        return await _inmem_store.hit(f"{key}:{window}", limit, window)


_redis_locks: dict[str, asyncio.Lock] = {}


def _redis_lock(key: str) -> asyncio.Lock:
    lock = _redis_locks.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _redis_locks[key] = lock
    return lock


def csrf_token(user_id: str, session_entropy: str) -> str:
    """Symmetric CSRF token bound to a user + session entropy."""
    return compute_signature(
        settings.SECRET_KEY,
        parts=["csrf", user_id, session_entropy],
    )


def validate_csrf(
    supplied: str, user_id: str, session_entropy: str
) -> bool:
    from src.security.core import constant_time_equals

    expected = csrf_token(user_id, session_entropy)
    return bool(supplied) and constant_time_equals(supplied, expected)


class ReplayProtector:
    """Guards against replay of signed/nonce-protected tokens within a window."""

    def __init__(self, window_seconds: int | None = None) -> None:
        self.window = window_seconds or settings.REPLAY_WINDOW_SECONDS
        self._seen: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def check(self, nonce: str, claim: str = "") -> bool:
        """Return True if the nonce has NOT been seen before (i.e. is new)."""
        if not settings.REPLAY_PROTECTION_ENABLED:
            return True
        key = f"{claim}:{nonce}"
        now = time.monotonic()
        async with self._lock:
            self._seen = {k: t for k, t in self._seen.items() if now - t <= self.window}
            if key in self._seen:
                return False
            self._seen[key] = now
            return True


# Shared replay protector instance.
_replay = ReplayProtector()


def replay_is_new(nonce: str, claim: str = "") -> bool:
    """Non-async wrapper used inside sync middleware paths if needed."""
    if not settings.REPLAY_PROTECTION_ENABLED:
        return True
    key = f"{claim}:{nonce}"
    now = time.monotonic()
    _replay._seen = {k: t for k, t in _replay._seen.items() if now - t <= _replay.window}
    if key in _replay._seen:
        return False
    _replay._seen[key] = now
    return True


def request_too_large(content_length: int | None, total_bytes: int = 0) -> bool:
    """True when a request body exceeds the configured size cap."""
    if content_length is not None and content_length > settings.MAX_BODY_BYTES:
        return True
    return total_bytes > settings.MAX_BODY_BYTES


def validate_required_fields(payload: dict[str, Any], required: list[str]) -> list[str]:
    """Return the list of required fields missing from a payload."""
    return [f for f in required if payload.get(f) in (None, "")]
