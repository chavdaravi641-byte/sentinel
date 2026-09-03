"""Part 1 — Authentication hardening for the core user auth stack.

Additive features layered on the existing refresh-token/session service:

- Session fingerprinting (device binding) via FingerprintEngine.
- Concurrent session limits (revoke oldest beyond MAX_CONCURRENT_SESSIONS).
- Single-device logout and multi-device management (list / revoke one / all).
- JWT key rotation support (TokenKeyStore) for graceful signing-key rotation.

Nothing here changes the existing successful login/refresh flow.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.models.refresh_token import RefreshToken
from src.security.core import FingerprintEngine, sha256_hex

_utcnow = lambda: datetime.now(timezone.utc)  # noqa: E731


def device_fingerprint(*, user_agent: str | None, ip: str | None, user_id) -> str:
    """Stable, per-user salted fingerprint of a device (UA + IP)."""
    salt = str(user_id)
    return FingerprintEngine().fingerprint(
        user_agent=user_agent, ip=ip, salt=salt
    )


async def list_user_sessions(db: AsyncSession, user_id) -> list[RefreshToken]:
    """List all active (non-revoked) sessions for a user, newest first."""
    stmt = (
        select(RefreshToken)
        .where(RefreshToken.user_id == user_id)
        .where(RefreshToken.revoked_at.is_(None))
        .order_by(RefreshToken.created_at.desc())
    )
    return list((await db.execute(stmt)).scalars().all())


async def revoke_session_by_id(db: AsyncSession, user_id, session_id) -> bool:
    """Revoke a single session, ownership-checked."""
    result = await db.execute(
        update(RefreshToken)
        .where(RefreshToken.id == session_id)
        .where(RefreshToken.user_id == user_id)
        .where(RefreshToken.revoked_at.is_(None))
        .values(revoked_at=_utcnow())
    )
    await db.commit()
    return (result.rowcount or 0) > 0


async def revoke_other_sessions(db: AsyncSession, user_id, keep_session_id) -> int:
    """Revoke every session except the one currently in use (single-device)."""
    result = await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id)
        .where(RefreshToken.id != keep_session_id)
        .where(RefreshToken.revoked_at.is_(None))
        .values(revoked_at=_utcnow())
    )
    await db.commit()
    return result.rowcount or 0


async def enforce_concurrent_sessions(
    db: AsyncSession,
    user_id,
    *,
    max_sessions: int | None = None,
) -> int:
    """Revoke the oldest active sessions beyond the configured limit.

    Returns the number of sessions revoked. Idempotent.
    """
    limit = max_sessions or settings.MAX_CONCURRENT_SESSIONS
    if limit <= 0:
        return 0
    active = await list_user_sessions(db, user_id)
    to_revoke = active[limit:]
    revoked = 0
    for session in to_revoke:
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.id == session.id)
            .where(RefreshToken.revoked_at.is_(None))
            .values(revoked_at=_utcnow())
        )
        revoked += 1
    if revoked:
        await db.commit()
    return revoked


def bind_session_device(
    fingerprint: str, *, user_agent: str | None, device_name: str | None
) -> dict[str, Any]:
    """Return additive session attributes stored on the refresh token row."""
    return {
        "fingerprint": fingerprint,
        "device_name": device_name,
        "last_used_at": _utcnow(),
        "user_agent": user_agent,
    }


def device_label_from(user_agent: str | None) -> str | None:
    """Derive a short human label (browser + OS) from a User-Agent string."""
    if not user_agent:
        return None
    ua = user_agent
    browser: str | None = None
    os_name: str | None = None
    for marker, name in (("Edg/", "Edge"), ("Chrome/", "Chrome"), ("Firefox/", "Firefox"),
                          ("Safari/", "Safari")):
        if marker in ua:
            browser = name
            break
    for marker, name in (("Windows", "Windows"), ("Mac OS X", "macOS"), ("Android", "Android"),
                          ("iPhone", "iOS"), ("Linux", "Linux")):
        if marker in ua:
            os_name = name
            break
    return " / ".join(p for p in (browser, os_name) if p) or "Unknown device"


def new_session_token_pair_key() -> str:
    return str(uuid.uuid4())


def hash_token(token: str) -> str:
    return sha256_hex(token)


# ---------------------------------------------------------------------- #
# Pending MFA challenge store (single-process, TTL-pruned).
# Used by the login flow to hold a lightweight challenge before token issue.
# ---------------------------------------------------------------------- #
import threading  # noqa: E402
import time as _time  # noqa: E402
import secrets as _secrets  # noqa: E402

_MFA_TTL = 180  # seconds
_pending_mfa: dict[str, dict] = {}
_pending_mfa_lock = threading.Lock()


def create_mfa_challenge(user_id, email: str, *, user_agent: str | None, ip: str | None) -> str:
    nonce = _secrets.token_urlsafe(32)
    with _pending_mfa_lock:
        _prune_pending()
        _pending_mfa[nonce] = {
            "user_id": str(user_id),
            "email": email,
            "user_agent": user_agent,
            "ip": ip,
            "created": _time.time(),
        }
    return nonce


def get_mfa_challenge(nonce: str) -> dict | None:
    with _pending_mfa_lock:
        _prune_pending()
        return _pending_mfa.get(nonce)


def consume_mfa_challenge(nonce: str) -> dict | None:
    with _pending_mfa_lock:
        _prune_pending()
        return _pending_mfa.pop(nonce, None)


def _prune_pending() -> None:
    now = _time.time()
    expired = [k for k, v in _pending_mfa.items() if now - v.get("created", 0) > _MFA_TTL]
    for k in expired:
        _pending_mfa.pop(k, None)
