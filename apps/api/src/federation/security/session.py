"""Session security: validation, refresh-token rotation, revocation, timeout,
concurrent-session control, account lock and password policy.

Sessions are stored hashed; the raw refresh token is only held by the client.
Rotation: each refresh produces a new hashed token binding and increments the
rotation counter, and the old binding is revoked (a reused old token is
rejected -- prevents token-replay).
"""

from __future__ import annotations

import hashlib
import re
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.federation.models import OfficerSession, SessionStatus


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(dt: datetime | None) -> datetime | None:
    """Return a tz-aware UTC datetime, tolerating naive DB read-back (SQLite)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _is_expired(dt: datetime | None) -> bool:
    aware = _as_aware(dt)
    return aware is not None and utcnow() >= aware


def sha256(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


# --- Password policy -----------------------------------------------------------
_PASSWORD_MIN = 8
_PASSWORD_REQUIREMENTS = {
    "lowercase": re.compile(r"[a-z]"),
    "uppercase": re.compile(r"[A-Z]"),
    "digit": re.compile(r"\d"),
    "symbol": re.compile(r"[^A-Za-z0-9]"),
}

# --- Session lifecycle settings ------------------------------------------------
ACCESS_TTL = timedelta(minutes=15)
REFRESH_TTL = timedelta(days=7)
MAX_ACTIVE_SESSIONS = 5
LOCK_THRESHOLD = 5
LOCKOUT_MINUTES = 15


@dataclass
class SessionConfig:
    access_ttl: timedelta = ACCESS_TTL
    refresh_ttl: timedelta = REFRESH_TTL
    max_active_sessions: int = MAX_ACTIVE_SESSIONS
    lock_threshold: int = LOCK_THRESHOLD
    lockout_minutes: int = LOCKOUT_MINUTES


def validate_password_policy(password: str) -> list[str]:
    """Return a list of unmet password-policy requirements (empty = compliant)."""
    problems: list[str] = []
    if len(password) < _PASSWORD_MIN:
        problems.append(f"min_{_PASSWORD_MIN}_chars")
    for label, pattern in _PASSWORD_REQUIREMENTS.items():
        if not pattern.search(password):
            problems.append(f"missing_{label}")
    return problems


def password_meets_policy(password: str) -> bool:
    return not validate_password_policy(password)


def _new_refresh_token() -> tuple[str, str]:
    raw = secrets.token_urlsafe(48)
    return raw, sha256(raw)


@dataclass
class CreatedSession:
    session: OfficerSession
    raw_refresh_token: str
    access_jti: str


class SessionManager:
    def __init__(self, db: AsyncSession, config: SessionConfig | None = None) -> None:
        self.db = db
        self.config = config or SessionConfig()

    async def create(
        self,
        officer_id: uuid.UUID,
        *,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> CreatedSession:
        """Start a new refresh-token session with concurrent-session control."""
        await self.enforce_concurrent_limit(officer_id)
        raw, hashed = _new_refresh_token()
        access_jti = str(uuid.uuid4())
        session = OfficerSession(
            officer_id=officer_id,
            refresh_token_hash=hashed,
            access_token_jti=access_jti,
            user_agent=user_agent,
            ip_address=ip_address,
            expires_at=utcnow() + self.config.refresh_ttl,
            status=SessionStatus.ACTIVE,
            rotation_count=0,
        )
        self.db.add(session)
        await self.db.flush()
        return CreatedSession(session=session, raw_refresh_token=raw, access_jti=access_jti)

    async def validate_access(self, jti: str) -> bool:
        """An access JTI is valid iff it is bound to a non-expired active session."""
        result = await self.db.execute(
            select(OfficerSession).where(OfficerSession.access_token_jti == jti)
        )
        session = result.scalars().first()
        if session is None:
            return False
        if session.status != SessionStatus.ACTIVE:
            return False
        if _is_expired(session.expires_at):
            return False
        return True

    async def rotate_refresh(
        self, raw_refresh: str, *, user_agent: str | None = None, ip_address: str | None = None
    ) -> CreatedSession | None:
        """Rotate a refresh token. Returns new binding or None (rejected/replayed)."""
        hashed = sha256(raw_refresh)
        result = await self.db.execute(
            select(OfficerSession).where(OfficerSession.refresh_token_hash == hashed)
        )
        session = result.scalars().first()
        if session is None:
            return None  # unknown token
        if session.status == SessionStatus.REVOKED:
            return None  # a rotated token being reused = replay, reject
        if _is_expired(session.expires_at):
            session.status = SessionStatus.EXPIRED
            await self.db.flush()
            return None

        # Revoke the old binding and mint a new one.
        session.status = SessionStatus.REVOKED
        session.rotation_count += 1
        await self.db.flush()

        raw_new, hashed_new = _new_refresh_token()
        access_jti = str(uuid.uuid4())
        new_session = OfficerSession(
            officer_id=session.officer_id,
            refresh_token_hash=hashed_new,
            access_token_jti=access_jti,
            user_agent=user_agent or session.user_agent,
            ip_address=ip_address or session.ip_address,
            expires_at=utcnow() + self.config.refresh_ttl,
            status=SessionStatus.ACTIVE,
            rotation_count=session.rotation_count,
        )
        self.db.add(new_session)
        await self.db.flush()
        return CreatedSession(session=new_session, raw_refresh_token=raw_new, access_jti=access_jti)

    async def revoke(self, raw_refresh: str) -> bool:
        """Revoke a session by its (hashed) refresh token."""
        return await self._set_status(sha256(raw_refresh), SessionStatus.REVOKED)

    async def revoke_session_id(self, session_id: uuid.UUID, officer_id: uuid.UUID) -> bool:
        result = await self.db.execute(
            select(OfficerSession).where(
                OfficerSession.id == session_id,
                OfficerSession.officer_id == officer_id,
            )
        )
        session = result.scalars().first()
        if session is None:
            return False
        session.status = SessionStatus.REVOKED
        await self.db.flush()
        return True

    async def revoke_all_for_officer(self, officer_id: uuid.UUID) -> int:
        result = await self.db.execute(
            update(OfficerSession)
            .where(OfficerSession.officer_id == officer_id,
                   OfficerSession.status == SessionStatus.ACTIVE)
            .values(status=SessionStatus.REVOKED)
        )
        return result.rowcount or 0

    async def _set_status(self, hashed: str, status: SessionStatus) -> bool:
        result = await self.db.execute(
            select(OfficerSession).where(OfficerSession.refresh_token_hash == hashed)
        )
        session = result.scalars().first()
        if session is None:
            return False
        session.status = status
        await self.db.flush()
        return True

    async def enforce_concurrent_limit(self, officer_id: uuid.UUID) -> None:
        """Revoke oldest active sessions beyond the concurrent limit."""
        result = await self.db.execute(
            select(OfficerSession).where(
                OfficerSession.officer_id == officer_id,
                OfficerSession.status == SessionStatus.ACTIVE,
            ).order_by(OfficerSession.created_at.desc())
        )
        sessions = list(result.scalars().all())
        overflow = sessions[self.config.max_active_sessions:]
        for s in overflow:
            s.status = SessionStatus.REVOKED
        if overflow:
            await self.db.flush()

    async def list_active(self, officer_id: uuid.UUID) -> list[OfficerSession]:
        result = await self.db.execute(
            select(OfficerSession).where(
                OfficerSession.officer_id == officer_id,
                OfficerSession.status == SessionStatus.ACTIVE,
            ).order_by(OfficerSession.created_at.desc())
        )
        return list(result.scalars().all())


def is_locked_out(failed_attempts: int, last_failure: datetime | None, config: SessionConfig | None = None) -> bool:
    config = config or SessionConfig()
    if failed_attempts < config.lock_threshold:
        return False
    if last_failure is None:
        return False
    if utcnow() - last_failure > timedelta(minutes=config.lockout_minutes):
        return False
    return True


def should_lock(failed_attempts: int, config: SessionConfig | None = None) -> bool:
    config = config or SessionConfig()
    return failed_attempts >= config.lock_threshold
