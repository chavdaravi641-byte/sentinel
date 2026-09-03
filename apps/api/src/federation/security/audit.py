"""Audit engine.

Audit records are **immutable**: they are only ever INSERTED. The service
enriches each entry with device/browser/OS/user-agent, optional location and
co-ordinates, access mode, request/trace IDs, and old/new values for change
events. Searches are jurisdiction-aware to honour data isolation.

Because the federation DB may be memory-backed during validation, the service
accepts an async session and returns both the created record and its request ID.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.federation.models import AccessMode, AuditLog, Severity


@dataclass
class AuditEvent:
    actor: str
    actor_department: str | None
    action: str
    resource_type: str
    resource_id: str | None = None
    outcome: str = "allow"
    detail: dict[str, Any] = field(default_factory=dict)
    # --- additive enrichment --------------------------------------------
    officer_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None
    device: str | None = None
    browser: str | None = None
    operating_system: str | None = None
    user_agent: str | None = None
    location: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    access_mode: AccessMode = AccessMode.NORMAL
    reason: str | None = None
    old_value: dict | None = None
    new_value: dict | None = None
    status: str | None = None
    session_id: uuid.UUID | None = None
    request_id: uuid.UUID | None = None
    trace_id: uuid.UUID | None = None
    case_id: uuid.UUID | None = None
    severity: Severity = Severity.INFO
    metadata_: dict[str, Any] = field(default_factory=dict)


def parse_user_agent(ua: str | None) -> tuple[str | None, str | None, str | None]:
    """Best-effort browser / OS extraction from a user-agent header."""
    if not ua:
        return None, None, None
    browser: str | None = None
    for marker, name in (("Firefox", "Firefox"), ("Chrome", "Chrome"),
                         ("Safari", "Safari"), ("Edg/", "Edge"), ("MSIE", "IE"),
                         ("Postman", "Postman")):
        if marker in ua:
            browser = name
            break
    os_: str | None = None
    for marker, name in (("Windows", "Windows"), ("Mac OS X", "macOS"),
                         ("Android", "Android"), ("iPhone", "iOS"),
                         ("Linux", "Linux")):
        if marker in ua:
            os_ = name
            break
    return browser, os_, ua


async def write_audit(db: AsyncSession, event: AuditEvent) -> AuditLog:
    """Persist an immutable audit record and flush (never update/delete)."""
    browser, os_, ua = parse_user_agent(event.user_agent)
    record = AuditLog(
        actor=event.actor,
        actor_department=event.actor_department,
        action=event.action,
        resource_type=event.resource_type,
        resource_id=event.resource_id,
        source_ip=event.detail.pop("source_ip", None),
        outcome=event.outcome,
        detail=event.detail,
        officer_id=event.officer_id,
        department_id=event.department_id,
        device=event.device,
        browser=browser or event.browser,
        operating_system=os_ or event.operating_system,
        user_agent=event.user_agent,
        location=event.location,
        latitude=event.latitude,
        longitude=event.longitude,
        access_mode=event.access_mode,
        reason=event.reason,
        old_value=event.old_value,
        new_value=event.new_value,
        status=event.status,
        session_id=event.session_id,
        request_id=event.request_id,
        trace_id=event.trace_id,
        case_id=event.case_id,
        severity=event.severity,
        metadata_=event.metadata_,
    )
    db.add(record)
    await db.flush()
    return record


async def search_audit(
    db: AsyncSession,
    *,
    department_ids: set[uuid.UUID] | None = None,
    officer_id: uuid.UUID | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    severity: Severity | None = None,
    access_mode: AccessMode | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[AuditLog]:
    """Search audit records, filtered to the caller's jurisdiction cone."""
    stmt = select(AuditLog).order_by(AuditLog.at.desc())
    if department_ids is not None:
        stmt = stmt.where(AuditLog.department_id.in_(department_ids))
    if officer_id is not None:
        stmt = stmt.where(AuditLog.officer_id == officer_id)
    if action is not None:
        stmt = stmt.where(AuditLog.action == action)
    if resource_type is not None:
        stmt = stmt.where(AuditLog.resource_type == resource_type)
    if severity is not None:
        stmt = stmt.where(AuditLog.severity == severity)
    if access_mode is not None:
        stmt = stmt.where(AuditLog.access_mode == access_mode)
    stmt = stmt.limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())


def new_request_id() -> uuid.UUID:
    return uuid.uuid4()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
