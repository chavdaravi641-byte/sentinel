"""Emergency (break-glass) access service.

Time-limited, audited, supervisor-approved elevated access. Any escalation is
recorded in the audit log; activation emits an alert. Access automatically
expires at ``expires_at`` (checked on read/activate), so a grant can never
outlive its window even if revocation is skipped.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.federation.models import (
    AccessMode,
    EmergencyAccess,
    EmergencyStatus,
    Severity,
)
from src.federation.security.audit import AuditEvent, write_audit


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(dt: datetime | None) -> datetime | None:
    """Return tz-aware UTC, tolerating naive DB read-back (SQLite)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _expired(record: EmergencyAccess) -> bool:
    aware = _as_aware(record.expires_at)
    return aware is not None and utcnow() >= aware


def is_active(record: EmergencyAccess) -> bool:
    return (
        record.status == EmergencyStatus.ACTIVE
        and record.activated_at is not None
        and not _expired(record)
    )


async def request_access(
    db: AsyncSession,
    *,
    officer_id: uuid.UUID,
    department_id: uuid.UUID,
    reason: str,
    case_reference: str | None = None,
    duration_seconds: int = 1800,
    grant: str = "cross_department_read",
) -> EmergencyAccess:
    """Create a break-glass request (status REQUESTED). Audited."""
    expires_at = utcnow() + timedelta(seconds=duration_seconds)
    record = EmergencyAccess(
        officer_id=officer_id,
        department_id=department_id,
        reason=reason,
        case_reference=case_reference,
        expires_at=expires_at,
        status=EmergencyStatus.REQUESTED,
        duration_seconds=duration_seconds,
        grant=grant,
    )
    db.add(record)
    await db.flush()
    await write_audit(
        db,
        AuditEvent(
            actor=str(officer_id),
            actor_department=str(department_id),
            action="emergency.request",
            resource_type="system",
            resource_id=str(record.id),
            outcome="allow",
            access_mode=AccessMode.BREAK_GLASS,
            reason=reason,
            officer_id=officer_id,
            department_id=department_id,
            new_value={"status": record.status.value, "duration_seconds": duration_seconds,
                       "grant": grant},
            severity=Severity.WARNING,
        ),
    )
    await db.commit()
    return record


async def approve(
    db: AsyncSession,
    emergency_id: uuid.UUID,
    *,
    approver_id: uuid.UUID,
    approver_department: uuid.UUID,
    approve_flag: bool,
    reason: str | None = None,
) -> EmergencyAccess | None:
    """Approve (or deny) a break-glass request. Audited."""
    record = await db.get(EmergencyAccess, emergency_id)
    if record is None:
        return None
    if record.status != EmergencyStatus.REQUESTED:
        raise ValueError(f"cannot approve emergency in status {record.status.value}")

    if not approve_flag:
        record.status = EmergencyStatus.DENIED
        await write_audit(
            db,
            AuditEvent(
                actor=str(approver_id),
                actor_department=str(approver_department),
                action="emergency.deny",
                resource_type="system",
                resource_id=str(record.id),
                access_mode=AccessMode.BREAK_GLASS,
                reason=reason,
                officer_id=approver_id,
                department_id=approver_department,
                severity=Severity.WARNING,
            ),
        )
        await db.commit()
        return record

    record.approved_by = approver_id
    record.approval_time = utcnow()
    record.status = EmergencyStatus.APPROVED
    await write_audit(
        db,
        AuditEvent(
            actor=str(approver_id),
            actor_department=str(approver_department),
            action="emergency.approve",
            resource_type="system",
            resource_id=str(record.id),
            access_mode=AccessMode.BREAK_GLASS,
            reason=reason,
            officer_id=approver_id,
            department_id=approver_department,
            severity=Severity.WARNING,
        ),
    )
    await db.commit()
    return record


async def activate(
    db: AsyncSession,
    emergency_id: uuid.UUID,
    *,
    actor_id: uuid.UUID,
    actor_department: uuid.UUID,
) -> EmergencyAccess | None:
    """Activate an approved emergency (marks ACTIVE, audits + raises alert)."""
    record = await db.get(EmergencyAccess, emergency_id)
    if record is None:
        return None
    if record.status != EmergencyStatus.APPROVED:
        raise ValueError(f"cannot activate emergency in status {record.status.value}")
    if _expired(record):
        record.status = EmergencyStatus.EXPIRED
        await _expire(db, record)
        return record

    record.status = EmergencyStatus.ACTIVE
    record.activated_at = utcnow()
    await write_audit(
        db,
        AuditEvent(
            actor=str(actor_id),
            actor_department=str(actor_department),
            action="emergency.activate",
            resource_type="system",
            resource_id=str(record.id),
            access_mode=AccessMode.BREAK_GLASS,
            reason=record.reason,
            officer_id=actor_id,
            department_id=actor_department,
            case_id=uuid.UUID(record.case_reference) if _is_uuid(record.case_reference) else None,
            new_value={"status": record.status.value, "grant": record.grant,
                       "expires_at": record.expires_at.isoformat()},
            severity=Severity.CRITICAL,
        ),
    )
    await db.commit()
    return record


async def check_expiry(db: AsyncSession, emergency_id: uuid.UUID) -> EmergencyAccess | None:
    """Auto-expire a grant if its window has elapsed. Returns the record."""
    record = await db.get(EmergencyAccess, emergency_id)
    if record is None:
        return None
    if record.status == EmergencyStatus.ACTIVE and _expired(record):
        await _expire(db, record)
    return record


async def revoke(
    db: AsyncSession,
    emergency_id: uuid.UUID,
    *,
    revoker_id: uuid.UUID,
    revoker_department: uuid.UUID,
    reason: str | None = None,
) -> EmergencyAccess | None:
    """Revoke an emergency grant (active or approved). Audited."""
    record = await db.get(EmergencyAccess, emergency_id)
    if record is None:
        return None
    if record.status in (EmergencyStatus.REVOKED, EmergencyStatus.EXPIRED):
        return record
    record.status = EmergencyStatus.REVOKED
    record.revoked_at = utcnow()
    record.revoked_by = revoker_id
    await write_audit(
        db,
        AuditEvent(
            actor=str(revoker_id),
            actor_department=str(revoker_department),
            action="emergency.revoke",
            resource_type="system",
            resource_id=str(record.id),
            access_mode=AccessMode.BREAK_GLASS,
            reason=reason,
            officer_id=revoker_id,
            department_id=revoker_department,
            severity=Severity.WARNING,
        ),
    )
    await db.commit()
    return record


async def active_for_officer(db: AsyncSession, officer_id: uuid.UUID) -> EmergencyAccess | None:
    """Return the officer's currently-active emergency grant (or None)."""
    result = await db.execute(
        select(EmergencyAccess).where(
            EmergencyAccess.officer_id == officer_id,
            EmergencyAccess.status == EmergencyStatus.ACTIVE,
        )
    )
    for record in result.scalars().all():
        if is_active(record):
            return record
    return None


async def _expire(db: AsyncSession, record: EmergencyAccess) -> None:
    """Mark expired and audit (called only when window elapsed)."""
    record.expires_at = record.expires_at
    await db.execute(
        update(EmergencyAccess)
        .where(EmergencyAccess.id == record.id)
        .values(status=EmergencyStatus.EXPIRED, revoked_at=utcnow())
    )
    await write_audit(
        db,
        AuditEvent(
            actor=str(record.officer_id),
            actor_department=str(record.department_id),
            action="emergency.expire",
            resource_type="system",
            resource_id=str(record.id),
            access_mode=AccessMode.BREAK_GLASS,
            reason="auto_expired",
            officer_id=record.officer_id,
            department_id=record.department_id,
            new_value={"status": "expired"},
            severity=Severity.WARNING,
        ),
    )


def _is_uuid(value: str | None) -> bool:
    if not value:
        return False
    try:
        uuid.UUID(value)
        return True
    except (ValueError, AttributeError):
        return False
