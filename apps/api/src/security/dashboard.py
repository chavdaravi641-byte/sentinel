"""Part 8 — Security audit dashboard.

Aggregates auth events, open vulnerabilities and threat findings into a single
risk-scored view. Purely observational — it never alters enforcement.

Risk score is a weighted sum (0..100) of:

- secrets risk      (unresolved secret-management issues)
- auth risk         (recent login failures / lockouts / replay)
- threat risk       (open, non-resolved threat findings)
- permission risk   (recent permission-abuse events)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.security import LoginAttempt, SecurityEvent, SecurityThreat
from src.security.secrets import run_secret_diagnostics

_utcnow = lambda: datetime.now(timezone.utc)  # noqa: E731


async def _count(db: AsyncSession, model, *conditions) -> int:
    try:
        stmt = select(func.count()).select_from(model)
        for cond in conditions:
            stmt = stmt.where(cond)
        return int((await db.execute(stmt)).scalar_one() or 0)
    except Exception:
        return 0


async def auth_events(db: AsyncSession, *, limit: int = 50) -> list[dict]:
    try:
        stmt = (
            select(SecurityEvent)
            .where(
                SecurityEvent.event_type.in_(
                    [
                        "login_success",
                        "login_failure",
                        "login_lockout",
                        "password_changed",
                        "mfa_failure",
                        "token_replay",
                        "session_killed",
                    ]
                )
            )
            .order_by(SecurityEvent.occurred_at.desc())
            .limit(limit)
        )
        rows = list((await db.execute(stmt)).scalars().all())
        return [
            {
                "id": str(r.id),
                "event_type": r.event_type,
                "severity": r.severity,
                "actor_id": r.actor_id,
                "ip_address": r.ip_address,
                "occurred_at": r.occurred_at.isoformat() if r.occurred_at else None,
                "detail": r.detail or {},
            }
            for r in rows
        ]
    except Exception:
        return []


async def threat_timeline(db: AsyncSession, *, limit: int = 50) -> list[dict]:
    try:
        stmt = (
            select(SecurityThreat)
            .order_by(SecurityThreat.last_seen.desc())
            .limit(limit)
        )
        rows = list((await db.execute(stmt)).scalars().all())
        return [
            {
                "id": str(r.id),
                "threat_type": r.threat_type,
                "severity": r.severity,
                "observed_count": r.observed_count,
                "status": r.status,
                "first_seen": r.first_seen.isoformat() if r.first_seen else None,
                "last_seen": r.last_seen.isoformat() if r.last_seen else None,
                "detail": r.detail or {},
            }
            for r in rows
        ]
    except Exception:
        return []


async def open_vulnerabilities() -> list[dict]:
    """Open misconfigurations surfaced by secret-management diagnostics."""
    out: list[dict] = []
    for diag in run_secret_diagnostics():
        for issue in diag.issues:
            if issue.severity in ("critical", "high"):
                out.append(
                    {
                        "secret": diag.name,
                        "kind": issue.kind,
                        "severity": issue.severity,
                        "detail": issue.detail,
                    }
                )
    return out


async def risk_score(db: AsyncSession) -> dict[str, Any]:
    """Compute a 0..100 risk score and its component breakdown."""
    now = _utcnow()
    hour_ago = now - timedelta(hours=1)
    day_ago = now - timedelta(hours=24)

    recent_failures = await _count(
        db, LoginAttempt, LoginAttempt.success.is_(False), LoginAttempt.occurred_at >= hour_ago
    )
    day_failures = await _count(
        db, LoginAttempt, LoginAttempt.success.is_(False), LoginAttempt.occurred_at >= day_ago
    )
    open_threats = await _count(db, SecurityThreat, SecurityThreat.status == "open")
    high_threats = await _count(
        db, SecurityThreat, SecurityThreat.status == "open", SecurityThreat.severity.in_(["critical", "high"])
    )
    replays = await _count(db, SecurityEvent, SecurityEvent.event_type == "token_replay", SecurityEvent.occurred_at >= day_ago)
    perm_abuse = await _count(db, SecurityEvent, SecurityEvent.event_type == "permission_denied", SecurityEvent.occurred_at >= day_ago)

    # Weights.
    secrets_risk = 40.0 if any(v["severity"] == "critical" for v in await open_vulnerabilities()) else 15.0 if any(v["severity"] == "high" for v in await open_vulnerabilities()) else 0.0
    auth_risk = min(30.0, 10.0 * recent_failures) + (15.0 if replays else 0.0)
    threat_risk = min(20.0, 5.0 * high_threats) + min(10.0, 2.0 * (open_threats - high_threats))
    perm_risk = min(15.0, 5.0 * perm_abuse)

    total = round(min(100.0, secrets_risk + auth_risk + threat_risk + perm_risk), 1)
    level = "low" if total < 25 else "medium" if total < 55 else "high" if total < 80 else "critical"

    return {
        "score": total,
        "level": level,
        "components": {
            "secrets": round(secrets_risk, 1),
            "auth": round(min(100.0, auth_risk), 1),
            "threats": round(threat_risk, 1),
            "permissions": round(perm_risk, 1),
        },
        "counters": {
            "recent_login_failures_hour": recent_failures,
            "recent_login_failures_day": day_failures,
            "open_threats": open_threats,
            "high_threats": high_threats,
            "token_replays_day": replays,
            "permission_denials_day": perm_abuse,
        },
    }


async def dashboard(db: AsyncSession) -> dict[str, Any]:
    """Full security dashboard payload."""
    return {
        "risk": await risk_score(db),
        "open_vulnerabilities": await open_vulnerabilities(),
        "auth_events": await auth_events(db),
        "threat_timeline": await threat_timeline(db),
        "generated_at": _utcnow().isoformat(),
    }
