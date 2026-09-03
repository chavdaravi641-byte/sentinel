"""Camera health scoring for the statewide registry.

Produces a 0..100 health score per camera from signal + recency + uptime
signals, plus fleet-level aggregates. Designed to be fed by a background
health job polling each camera's ``status`` / ``last_seen_at``.

Pure-Python (no DB/network) so the scoring is unit-testable and callable from
the health worker or on-demand endpoint.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.models.camera import CameraStatus


class HealthRule:
    """Declarative health scoring configuration with sensible defaults."""

    def __init__(
        self,
        *,
        online_base: int = 100,
        offline_penalty: int = 60,
        maintenance_ceiling: int = 70,
        unknown_base: int = 40,
        stale_after_minutes: float = 15.0,
        stale_penalty_per_hour: float = 8.0,
        uptime_weight: float = 0.3,
    ) -> None:
        self.online_base = online_base
        self.offline_penalty = offline_penalty
        self.maintenance_ceiling = maintenance_ceiling
        self.unknown_base = unknown_base
        self.stale_after_minutes = stale_after_minutes
        self.stale_penalty_per_hour = stale_penalty_per_hour
        self.uptime_weight = uptime_weight

    @classmethod
    def default(cls) -> "HealthRule":
        return cls()


def score_camera(
    status: CameraStatus | str,
    last_seen_at: datetime | None,
    uptime_pct: float | None = None,
    *,
    rule: HealthRule | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Compute a 0..100 health score for one camera."""
    rule = rule or HealthRule.default()
    now = now or datetime.now(timezone.utc)
    if isinstance(status, str):
        status = CameraStatus(status)

    if status == CameraStatus.ONLINE:
        score = float(rule.online_base)
    elif status == CameraStatus.OFFLINE:
        score = float(max(0.0, rule.offline_penalty - 10.0))
    elif status == CameraStatus.MAINTENANCE:
        score = float(rule.maintenance_ceiling * 0.6)
    else:
        score = float(rule.unknown_base)

    # Recency penalty: a camera that has not reported in a while decays.
    if last_seen_at is not None:
        if last_seen_at.tzinfo is None:
            last_seen_at = last_seen_at.replace(tzinfo=timezone.utc)
        age_minutes = (now - last_seen_at).total_seconds() / 60.0
        if age_minutes > rule.stale_after_minutes:
            stale_hours = max(0.0, (age_minutes - rule.stale_after_minutes) / 60.0)
            score -= rule.stale_penalty_per_hour * stale_hours

    # Blend in historical uptime for online/offline devices (uptime_pct is 0..1).
    if uptime_pct is not None and status in (CameraStatus.ONLINE, CameraStatus.OFFLINE):
        score = score * (1.0 - rule.uptime_weight) + (uptime_pct * 100.0) * rule.uptime_weight

    score = max(0.0, min(100.0, score))

    if score >= 85:
        level = "healthy"
    elif score >= 55:
        level = "degraded"
    elif score >= 25:
        level = "poor"
    else:
        level = "critical"

    return {
        "score": round(score, 1),
        "level": level,
        "status": status.value,
        "uptime_pct": uptime_pct,
        "last_seen_at": last_seen_at,
    }


def fleet_health(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate per-camera health dicts into fleet-level stats."""
    if not rows:
        return {
            "total": 0, "healthy": 0, "degraded": 0, "poor": 0, "critical": 0,
            "avg_score": 0.0, "online": 0, "offline": 0, "maintenance": 0, "unknown": 0,
        }
    counts: dict[str, int] = {"healthy": 0, "degraded": 0, "poor": 0, "critical": 0}
    status_counts: dict[str, int] = {}
    total = 0.0
    for r in rows:
        counts[r.get("level", "unknown")] = counts.get(r.get("level", "unknown"), 0) + 1
        status_counts[r.get("status", "unknown")] = status_counts.get(r.get("status", "unknown"), 0) + 1
        total += float(r.get("score", 0.0))
    return {
        "total": len(rows),
        "healthy": counts.get("healthy", 0),
        "degraded": counts.get("degraded", 0),
        "poor": counts.get("poor", 0),
        "critical": counts.get("critical", 0),
        "avg_score": round(total / len(rows), 1),
        "online": status_counts.get("online", 0),
        "offline": status_counts.get("offline", 0),
        "maintenance": status_counts.get("maintenance", 0),
        "unknown": status_counts.get("unknown", 0),
    }


__all__: list[str] = ["HealthRule", "fleet_health", "score_camera"]
