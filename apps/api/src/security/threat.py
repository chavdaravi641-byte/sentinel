"""Part 7 — Threat detection.

Correlates security events/login attempts into aggregated threat findings.
Detection rules (additive, never change existing allow/deny behaviour):

- Credential stuffing  : many failures across many distinct identifiers from one IP.
- Brute force          : many consecutive failures for one account/IP.
- Token replay         : reuse of an already-rotated token (refresh replay).
- Permission abuse     : repeated denied (403) authorization attempts.
- Rapid search         : many search/query calls in a short window.
- Mass export          : very large list/export responses in a window.
- Suspicious API usage : unusual burst of requests from a single client.

Each finding is persisted to ``security_threats`` (deduplicated by type+key)
and logged. Threat evaluation is best-effort: DB/services unavailable => the
finding is skipped, never raises.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logging import log
from src.models.security import LoginAttempt, SecurityEvent, SecurityThreat
from src.security.core import sha256_hex

_utcnow = lambda: datetime.now(timezone.utc)  # noqa: E731

# Tunable thresholds.
_FAIL_LOOKBACK = timedelta(minutes=15)
_STUFFING_UNIQUE_IDENTIFIERS = 3
_BRUTEFORCE_FAILURES = 5
_REPLAY_WINDOW = timedelta(minutes=10)
_PERM_ABUSE_COUNT = 5
_PERM_ABUSE_WINDOW = timedelta(minutes=15)
_RAPID_SEARCH_COUNT = 30
_RAPID_SEARCH_WINDOW = timedelta(minutes=1)
_MASS_EXPORT_MIN_ROWS = 5000


async def record_event(
    db: AsyncSession,
    *,
    event_type: str,
    severity: str = "info",
    actor_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    detail: dict[str, Any] | None = None,
    trace_id: str | None = None,
    request_id: str | None = None,
) -> SecurityEvent | None:
    """Append an immutable security event (best-effort)."""
    if db is None:
        return None
    try:
        event = SecurityEvent(
            event_type=event_type,
            severity=severity,
            actor_id=actor_id,
            ip_address=ip_address,
            user_agent=user_agent,
            detail=detail,
            trace_id=trace_id,
            request_id=request_id,
        )
        db.add(event)
        await db.commit()
        return event
    except Exception:
        await db.rollback()
        log.warning("security.event_skipped", event_type=event_type)
        return None


async def _upsert_threat(db: AsyncSession, *, threat_type: str, severity: str, key: str, detail: dict) -> None:
    try:
        stmt = select(SecurityThreat).where(
            SecurityThreat.threat_type == threat_type,
            SecurityThreat.key == key,
            SecurityThreat.status == "open",
        )
        existing = (await db.execute(stmt)).scalar_one_or_none()
        now = _utcnow()
        if existing is None:
            db.add(
                SecurityThreat(
                    threat_type=threat_type,
                    severity=severity,
                    key=key,
                    detail=detail,
                    observed_count=1,
                    first_seen=now,
                    last_seen=now,
                    status="open",
                )
            )
        else:
            await db.execute(
                update(SecurityThreat)
                .where(SecurityThreat.id == existing.id)
                .values(
                    last_seen=now,
                    observed_count=SecurityThreat.observed_count + 1,
                    detail=detail,
                )
            )
        await db.commit()
    except Exception:
        await db.rollback()
        log.warning("security.threat_upsert_skipped", threat_type=threat_type)


async def evaluate_login_patterns(db: AsyncSession, *, ip_address: str | None, identifier: str | None) -> None:
    """Detect credential stuffing / brute force from recent login attempts."""
    if db is None:
        return
    try:
        window = _utcnow() - _FAIL_LOOKBACK
        failure_stmt = select(LoginAttempt).where(
            LoginAttempt.success.is_(False), LoginAttempt.occurred_at >= window
        )
        rows = list((await db.execute(failure_stmt)).scalars().all())

        if ip_address:
            ip_rows = [r for r in rows if r.ip_address == ip_address]
            unique_ids = {r.identifier for r in ip_rows if r.identifier}
            if len(ip_rows) >= _BRUTEFORCE_FAILURES:
                await _upsert_threat(
                    db,
                    threat_type="brute_force",
                    severity="high",
                    key=f"ip:{ip_address}",
                    detail={"ip": ip_address, "failures": len(ip_rows)},
                )
            if len(unique_ids) >= _STUFFING_UNIQUE_IDENTIFIERS:
                await _upsert_threat(
                    db,
                    threat_type="credential_stuffing",
                    severity="critical",
                    key=f"stuffing:{ip_address}",
                    detail={
                        "ip": ip_address,
                        "unique_identifiers": sorted(unique_ids)[:20],
                        "failures": len(ip_rows),
                    },
                )
    except Exception:
        await db.rollback()
        log.warning("security.login_eval_skipped")


async def report_permission_abuse(
    db: AsyncSession, *, actor_id: str, ip_address: str | None, resource: str
) -> None:
    await record_event(
        db,
        event_type="permission_denied",
        severity="warning",
        actor_id=actor_id,
        ip_address=ip_address,
        detail={"resource": resource},
    )
    # Fast-path: repeated denials => threat.
    try:
        window = _utcnow() - _PERM_ABUSE_WINDOW
        stmt = select(SecurityEvent).where(
            SecurityEvent.event_type == "permission_denied",
            SecurityEvent.actor_id == actor_id,
            SecurityEvent.occurred_at >= window,
        )
        count = len(list((await db.execute(stmt)).scalars().all()))
        if count >= _PERM_ABUSE_COUNT:
            await _upsert_threat(
                db,
                threat_type="permission_abuse",
                severity="high",
                key=actor_id,
                detail={"actor_id": actor_id, "denials": count, "resource": resource},
            )
    except Exception:
        await db.rollback()


async def report_token_replay(
    db: AsyncSession, *, actor_id: str | None, ip_address: str | None
) -> None:
    await record_event(
        db,
        event_type="token_replay",
        severity="high",
        actor_id=actor_id,
        ip_address=ip_address,
        detail={"forwarded": True},
    )
    await _upsert_threat(
        db,
        threat_type="token_replay",
        severity="high",
        key=f"replay:{actor_id or ip_address or 'anon'}",
        detail={"actor_id": actor_id, "ip_address": ip_address},
    )


async def report_rapid_search(
    db: AsyncSession, *, actor_id: str, ip_address: str | None, hits: int
) -> None:
    if hits >= _RAPID_SEARCH_COUNT:
        await _upsert_threat(
            db,
            threat_type="rapid_search",
            severity="medium",
            key=f"search:{actor_id}",
            detail={"actor_id": actor_id, "calls_in_window": hits, "ip": ip_address},
        )


async def report_mass_export(
    db: AsyncSession, *, actor_id: str, rows: int, ip_address: str | None = None
) -> None:
    if rows >= _MASS_EXPORT_MIN_ROWS:
        await _upsert_threat(
            db,
            threat_type="mass_export",
            severity="high",
            key=f"export:{actor_id}",
            detail={"actor_id": actor_id, "rows": rows, "ip": ip_address},
        )


def threat_key_for_type(threat_type: str, key: str) -> str:
    return sha256_hex(f"{threat_type}:{key}")[:16]
