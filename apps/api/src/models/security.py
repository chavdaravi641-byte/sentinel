"""Phase 6.2 security model extensions.

Additive tables/columns for password history, MFA, login attempts, security
events, threat detection and trusted devices. All new columns are nullable or
carry server defaults so existing rows and the schema remain fully
backward-compatible.

The JSON columns use SQLAlchemy's portable ``JSON`` type so the same models work
on PostgreSQL (asyncpg) and the SQLite test backend.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class SecurityEventType(str, enum.Enum):
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGIN_LOCKOUT = "login_lockout"
    PASSWORD_CHANGED = "password_changed"
    PASSWORD_EXPIRED = "password_expired"
    MFA_ENABLED = "mfa_enabled"
    MFA_DISABLED = "mfa_disabled"
    MFA_FAILURE = "mfa_failure"
    MFA_RECOVERY_USED = "mfa_recovery_used"
    TOKEN_REVOKED = "token_revoked"
    TOKEN_REPLAY = "token_replay"
    SESSION_KILLED = "session_killed"
    RATE_LIMITED = "rate_limited"
    PERMISSION_DENIED = "permission_denied"
    THREAT_DETECTED = "threat_detected"
    MASS_EXPORT = "mass_export"
    RAPID_SEARCH = "rapid_search"


class SecurityThreatType(str, enum.Enum):
    CREDENTIAL_STUFFING = "credential_stuffing"
    BRUTE_FORCE = "brute_force"
    TOKEN_REPLAY = "token_replay"
    PERMISSION_ABUSE = "permission_abuse"
    RAPID_SEARCH = "rapid_search"
    MASS_EXPORT = "mass_export"
    SUSPICIOUS_API = "suspicious_api"


class UserSecurity(Base, TimestampMixin):
    """Security-related attributes for a core-auth user (additive / nullable).

    Kept as a companion table so ``users`` is not burdened and the original
    ``User`` model remains untouched (full backward compatibility).
    """

    __tablename__ = "user_security"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    password_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    mfa_secret: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<UserSecurity user_id={self.user_id}>"


class PasswordHistory(Base, TimestampMixin):
    """Recent password hashes per user, to prevent reuse."""

    __tablename__ = "password_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )


class LoginAttempt(Base, TimestampMixin):
    """Login attempt record used for lockout and brute-force detection."""

    __tablename__ = "login_attempts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    identifier: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), default="password", nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )


class MfaRecoveryCode(Base, TimestampMixin):
    """One-time recovery codes, stored as hashes only."""

    __tablename__ = "mfa_recovery_codes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TrustedDevice(Base, TimestampMixin):
    """Trusted/bound device for a user, tied to their session fingerprint."""

    __tablename__ = "trusted_devices"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SecurityEvent(Base, TimestampMixin):
    """Immutable security event stream (auth events, threat timeline)."""

    __tablename__ = "security_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    event_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    severity: Mapped[str] = mapped_column(String(16), default="info", nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )


class SecurityThreat(Base, TimestampMixin):
    """Aggregated threat finding (deduplicated by type+key)."""

    __tablename__ = "security_threats"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    threat_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    severity: Mapped[str] = mapped_column(String(16), default="medium", nullable=False)
    key: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    observed_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), default="open", nullable=False)


__all__ = [
    "UserSecurity",
    "PasswordHistory",
    "LoginAttempt",
    "MfaRecoveryCode",
    "TrustedDevice",
    "SecurityEvent",
    "SecurityThreat",
    "SecurityEventType",
    "SecurityThreatType",
]
