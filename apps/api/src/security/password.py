"""Part 2 — Password security.

Additive enforcement over the core auth login flow:

- Password history (reuse prevention) — stored in password_history.
- Password expiry policy (force change after PASSWORD_EXPIRY_DAYS).
- Account lockout after LOGIN_FAILURE_LIMIT failures.
- Progressive backoff (delay grows with consecutive failures).
- Brute-force protection helper.

None of these change the shape of a successful login; they gate failures.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.security import hash_password, verify_password
from src.models.security import LoginAttempt, PasswordHistory, UserSecurity
from src.models.user import User
from src.security.core import ensure_utc

_utcnow = lambda: datetime.now(timezone.utc)  # noqa: E731


def password_strength_issues(password: str) -> list[str]:
    """Return a list of unmet policy rules (empty means the password is OK)."""
    issues: list[str] = []
    if len(password) < settings.PASSWORD_MIN_LENGTH:
        issues.append(
            f"must be at least {settings.PASSWORD_MIN_LENGTH} characters"
        )
    if settings.PASSWORD_REQUIRE_UPPER and not any(c.isupper() for c in password):
        issues.append("must include an uppercase letter")
    if settings.PASSWORD_REQUIRE_LOWER and not any(c.islower() for c in password):
        issues.append("must include a lowercase letter")
    if settings.PASSWORD_REQUIRE_DIGIT and not any(c.isdigit() for c in password):
        issues.append("must include a digit")
    if settings.PASSWORD_REQUIRE_SYMBOL and not any(
        not c.isalnum() for c in password
    ):
        issues.append("must include a symbol")
    return issues


def meets_password_policy(password: str) -> bool:
    return not password_strength_issues(password)


def _backoff_seconds(failed_count: int) -> int:
    """Progressive backoff: grows quadratically with consecutive failures."""
    if settings.LOGIN_PROGRESSIVE_BACKOFF:
        return min(300, (failed_count ** 2) * 2)
    return 0


async def get_user_security(db: AsyncSession, user_id) -> UserSecurity | None:
    stmt = select(UserSecurity).where(UserSecurity.user_id == user_id)
    return (await db.execute(stmt)).scalar_one_or_none()


async def get_or_create_user_security(
    db: AsyncSession, user_id
) -> UserSecurity:
    sec = await get_user_security(db, user_id)
    if sec is None:
        sec = UserSecurity(user_id=user_id)
        db.add(sec)
        await db.flush()
    return sec


async def register_failed_attempt(
    db: AsyncSession,
    *,
    identifier: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
    user_id=None,
) -> int:
    """Record a login failure; returns the updated consecutive-failure count."""
    db.add(
        LoginAttempt(
            identifier=identifier,
            ip_address=ip_address,
            user_agent=user_agent,
            success=False,
            kind="password",
        )
    )
    count = 0
    if user_id is not None:
        sec = await get_or_create_user_security(db, user_id)
        sec.failed_login_count = (sec.failed_login_count or 0) + 1
        sec.last_failed_at = _utcnow()
        if sec.failed_login_count >= settings.LOGIN_FAILURE_LIMIT:
            sec.locked_until = _utcnow() + timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES)
        count = sec.failed_login_count
    await db.commit()
    return count


async def register_successful_attempt(
    db: AsyncSession,
    *,
    identifier: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
    user_id=None,
) -> None:
    db.add(
        LoginAttempt(
            identifier=identifier,
            ip_address=ip_address,
            user_agent=user_agent,
            success=True,
            kind="password",
        )
    )
    if user_id is not None:
        sec = await get_or_create_user_security(db, user_id)
        sec.failed_login_count = 0
        sec.locked_until = None
    await db.commit()


async def is_account_locked(db: AsyncSession, user_id) -> tuple[bool, int]:
    """Return (locked, retry_after_seconds)."""
    sec = await get_user_security(db, user_id)
    if sec is None or sec.locked_until is None:
        return False, 0
    now = _utcnow()
    locked_until = ensure_utc(sec.locked_until)
    if locked_until is None or locked_until <= now:
        return False, 0
    return True, int((locked_until - now).total_seconds())


async def lockout_probe(db: AsyncSession, user_id) -> tuple[bool, int]:
    """Probe for lockout AND return current backoff delay for this user."""
    locked, retry_after = await is_account_locked(db, user_id)
    sec = await get_user_security(db, user_id)
    backoff = _backoff_seconds(sec.failed_login_count) if sec else 0
    return locked, max(retry_after, backoff)


async def password_is_reused(
    db: AsyncSession, user_id, new_password: str
) -> bool:
    """Check the new password against recent history (reuse prevention)."""
    stmt = (
        select(PasswordHistory)
        .where(PasswordHistory.user_id == user_id)
        .order_by(PasswordHistory.changed_at.desc())
        .limit(settings.PASSWORD_HISTORY_LIMIT)
    )
    rows = list((await db.execute(stmt)).scalars().all())
    return any(verify_password(new_password, r.password_hash) for r in rows)


async def password_expired(db: AsyncSession, user_id) -> bool:
    """Whether the user's password is past the expiry policy."""
    sec = await get_user_security(db, user_id)
    if sec is None:
        return False  # no record -> treat as not expiring (backward compatible)
    changed = ensure_utc(sec.password_changed_at)
    if changed is None:
        return False
    age = _utcnow() - changed
    return age > timedelta(days=settings.PASSWORD_EXPIRY_DAYS)


async def record_password_change(
    db: AsyncSession, user: User, new_password: str
) -> None:
    """Store a new password: update history and the user's security record."""
    sec = await get_or_create_user_security(db, user.id)
    sec.password_changed_at = _utcnow()

    # Keep only the most recent PASSWORD_HISTORY_LIMIT entries.
    stmt = (
        select(PasswordHistory)
        .where(PasswordHistory.user_id == user.id)
        .order_by(PasswordHistory.changed_at.desc())
    )
    existing = list((await db.execute(stmt)).scalars().all())
    for row in existing[settings.PASSWORD_HISTORY_LIMIT - 1 :]:
        await db.delete(row)

    db.add(
        PasswordHistory(user_id=user.id, password_hash=hash_password(new_password))
    )
    await db.commit()


async def recent_failed_login_window(
    db: AsyncSession, *, ip_address: str | None, identifier: str | None
) -> int:
    """Count failures in the last observation window (brute-force signal)."""
    window = _utcnow() - timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES)
    stmt = select(func.count(LoginAttempt.id)).where(
        LoginAttempt.success.is_(False), LoginAttempt.occurred_at >= window
    )
    if ip_address:
        stmt = stmt.where(LoginAttempt.ip_address == ip_address)
    if identifier:
        stmt = stmt.where(LoginAttempt.identifier == identifier)
    return int((await db.execute(stmt)).scalar_one() or 0)
