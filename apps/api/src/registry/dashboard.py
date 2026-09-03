"""Dashboard widget aggregations for the statewide CCTV registry.

Pure functions over registry records so they can be unit-tested without a DB
and reused by the dashboard endpoint. Each group mirrors a sentinel widget:
totals, status, category, ownership, district, health and onboarding health.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Iterable


def registry_overview(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = list(records)
    total = len(rows)
    active = sum(1 for r in rows if r.get("is_active"))
    return {
        "total_cameras": total,
        "active": active,
        "inactive": total - active,
        "districts": len({(r.get("state_code"), r.get("district_code")) for r in rows}),
        "last_registered": max((r.get("created_at") for r in rows), default=None),
    }


def status_breakdown(records: Iterable[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(str(r.get("status", "unknown")) for r in records)
    return dict(counts)


def category_breakdown(records: Iterable[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(str(r.get("category", "unknown")) for r in records)
    return dict(counts)


def ownership_breakdown(records: Iterable[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(str(r.get("ownership_type", "unknown")) for r in records)
    return dict(counts)


def district_breakdown(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in records:
        buckets[r.get("district_code", "unknown")].append(r)
    out = []
    for code, rows in buckets.items():
        online = sum(1 for r in rows if r.get("status") == "online")
        out.append({"district_code": code, "count": len(rows), "online": online,
                    "online_pct": round(100.0 * online / len(rows), 1)})
    out.sort(key=lambda d: d["count"], reverse=True)
    return out


def health_breakdown(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    levels = Counter(str(r.get("health_level", "unknown")) for r in records)
    return {
        "healthy": levels.get("healthy", 0),
        "degraded": levels.get("degraded", 0),
        "poor": levels.get("poor", 0),
        "critical": levels.get("critical", 0),
        "unknown": levels.get("unknown", 0),
    }


def onboarding_summary(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = list(records)
    if not rows:
        return {"total": 0, "with_serial": 0, "with_ip": 0, "complete_coords": 0, "data_completeness_pct": 0.0}
    complete = sum(
        1 for r in rows
        if r.get("serial_number") and r.get("ip_address")
        and r.get("latitude") is not None and r.get("longitude") is not None
    )
    return {
        "total": len(rows),
        "with_serial": sum(1 for r in rows if r.get("serial_number")),
        "with_ip": sum(1 for r in rows if r.get("ip_address")),
        "complete_coords": sum(1 for r in rows if r.get("latitude") is not None and r.get("longitude") is not None),
        "data_completeness_pct": round(100.0 * complete / len(rows), 1),
    }


def all_widgets(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = list(records)
    return {
        "overview": registry_overview(rows),
        "status": status_breakdown(rows),
        "category": category_breakdown(rows),
        "ownership": ownership_breakdown(rows),
        "districts": district_breakdown(rows),
        "health": health_breakdown(rows),
    }


__all__: list[str] = [
    "all_widgets", "category_breakdown", "district_breakdown", "health_breakdown",
    "onboarding_summary", "ownership_breakdown", "registry_overview", "status_breakdown",
]
