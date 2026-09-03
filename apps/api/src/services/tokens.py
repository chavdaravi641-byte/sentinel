"""Token lifecycle service: issue, rotate and revoke refresh sessions."""

from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.logging import log
from src.core.redis import redis_client
from src.core.security import (
    create_access_token,
    default_refresh_ttl,
    generate_refresh_token,
    hash_refresh_token,
)
from src.models.refresh_token import RefreshToken
from src.models.user import User

COOKIE_NAME = "sentinel_refresh"
ACCESS_BLACKLIST_PREFIX = "jti:blacklist:"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def make_refresh_cookie(token: str, max_age_seconds: int) -> dict:
    """Return kwargs for Response.set_cookie."""
    return {
        "key": COOKIE_NAME,
        "value": token,
        "max_age": max_age_seconds,
        "httponly": True,
        "secure": settings.COOKIE_SECURE,
        "samesite": "lax",
        "path": "/",
        "domain": settings.COOKIE_DOMAIN or None,
    }


async def issue_refresh_session(
    db: AsyncSession,
    user: User,
    *,
    user_agent: str | None,
    ip_address: str | None,
) -> tuple[str, int]:
    """Create a new refresh-token session. Returns (raw_token, max_age)."""
    raw = generate_refresh_token()
    ttl = default_refresh_ttl()
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_refresh_token(raw),
            expires_at=_utcnow() + ttl,
            user_agent=user_agent,
            ip_address=ip_address,
        )
    )
    await db.commit()
    return raw, int(ttl.total_seconds())


async def rotate_refresh_session(
    db: AsyncSession,
    refresh_token: str,
    *,
    user_agent: str | None,
    ip_address: str | None,
) -> tuple[User, str, int] | None:
    """Validate a refresh token, revoke it and mint a replacement.

    Returns (user, new_raw_token, max_age) or None if invalid.
    """
    token_hash = hash_refresh_token(refresh_token)
    stmt = (
        select(RefreshToken)
        .where(RefreshToken.token_hash == token_hash)
        .where(RefreshToken.revoked_at.is_(None))
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing is None:
        return None
    if existing.expires_at.replace(tzinfo=timezone.utc) < _utcnow():
        return None

    user_stmt = select(User).where(User.id == existing.user_id)
    user = (await db.execute(user_stmt)).scalar_one_or_none()
    if user is None or not user.is_active:
        return None

    # Rotate: revoke the old session, issue a fresh one.
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.id == existing.id)
        .values(revoked_at=_utcnow())
    )

    raw, max_age = await issue_refresh_session(
        db, user, user_agent=user_agent, ip_address=ip_address
    )
    return user, raw, max_age


async def revoke_refresh_session(db: AsyncSession, refresh_token: str) -> bool:
    token_hash = hash_refresh_token(refresh_token)
    result = await db.execute(
        update(RefreshToken)
        .where(RefreshToken.token_hash == token_hash)
        .where(RefreshToken.revoked_at.is_(None))
        .values(revoked_at=_utcnow())
    )
    await db.commit()
    return (result.rowcount or 0) > 0


# In-memory fallback used when Redis is unavailable (matches the graceful
# degradation pattern in security/api.py: rate limiting and replay protection
# fall back to in-memory stores so authentication keeps working without Redis).
_inmem_blacklist: set[str] = set()


async def blacklist_access_jti(jti: str, expires: datetime) -> None:
    """Blacklist an access token jti until its natural expiry."""
    ttl = max(1, int((expires - _utcnow()).total_seconds()))
    try:
        await redis_client.set(f"{ACCESS_BLACKLIST_PREFIX}{jti}", "1", ex=ttl)
    except Exception:  # noqa: BLE001 - Redis outage degrades to in-memory
        _inmem_blacklist.add(jti)


async def is_access_blacklisted(jti: str) -> bool:
    try:
        return bool(await redis_client.exists(f"{ACCESS_BLACKLIST_PREFIX}{jti}"))
    except Exception:  # noqa: BLE001 - Redis outage degrades to in-memory
        return jti in _inmem_blacklist


async def create_token_pair(
    db: AsyncSession,
    user: User,
    *,
    user_agent: str | None,
    ip_address: str | None,
) -> tuple[str, str, int, int]:
    """Issue an access token and a persisted refresh session.

    Returns (access_token, refresh_raw, access_expires_in, refresh_max_age).
    """
    access_token, _jti, expires = create_access_token(
        subject=str(user.id), role=user.role.value
    )
    refresh_raw, refresh_max_age = await issue_refresh_session(
        db, user, user_agent=user_agent, ip_address=ip_address
    )
    access_max_age = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    return access_token, refresh_raw, access_max_age, refresh_max_age


async def purge_user_sessions(db: AsyncSession, user_id) -> int:
    """Revoke every session belonging to a user (logout from all devices)."""
    result = await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id)
        .where(RefreshToken.revoked_at.is_(None))
        .values(revoked_at=_utcnow())
    )
    await db.commit()
    return result.rowcount or 0


def log_token_event(event: str, **kwargs) -> None:
    log.info(f"token.{event}", **kwargs)