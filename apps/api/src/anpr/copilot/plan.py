"""Phase 6 Copilot — shared data models.

Pure dataclasses describing intents, time windows and the structured search plan
produced by the natural-language engine and consumed by the executor. Kept free
of SQLAlchemy / FastAPI so it is trivially unit-testable and reusable between
the NL layer and the analysis layer.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TimeWindow:
    """Resolved absolute time window (or None bounds = open)."""

    start: dt.datetime | None = None
    end: dt.datetime | None = None
    label: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "start": self.start.isoformat() if self.start else None,
            "end": self.end.isoformat() if self.end else None,
            "label": self.label,
        }


# Intents the NL engine can resolve.
INTENT_FIND_VEHICLES = "find_vehicles"
INTENT_VEHICLES_NEAR = "vehicles_near"
INTENT_MULTI_DISTRICT = "multi_district"
INTENT_REPEATED_NIGHT = "repeated_night_visitors"
INTENT_RELATED_VEHICLES = "related_vehicles"
INTENT_TIMELINE = "timeline"
INTENT_EVIDENCE = "evidence_builder"
INTENT_UNKNOWN = "unknown"


@dataclass
class SearchFilters:
    """Structured filters extracted from natural language."""

    plate: str | None = None            # exact / partial plate
    vehicle_type: str | None = None     # suv, car, truck, bus, motorcycle...
    color: str | None = None
    make: str | None = None
    model: str | None = None
    state: str | None = None
    district: str | None = None
    camera: str | None = None           # camera name (partial, e.g. "GJ-114")
    min_confidence: float = 0.0
    window: TimeWindow = field(default_factory=TimeWindow)
    limit: int = 100
    near_lat: float | None = None
    near_lng: float | None = None
    radius_km: float = 10.0

    def is_empty(self) -> bool:
        return not any(
            [self.plate, self.vehicle_type, self.color, self.make, self.model,
             self.state, self.district, self.camera, self.min_confidence,
             self.near_lat, self.near_lng]
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "plate": self.plate,
            "vehicle_type": self.vehicle_type,
            "color": self.color,
            "make": self.make,
            "model": self.model,
            "state": self.state,
            "district": self.district,
            "camera": self.camera,
            "min_confidence": self.min_confidence,
            "window": self.window.to_dict(),
            "limit": self.limit,
            "near_lat": self.near_lat,
            "near_lng": self.near_lng,
            "radius_km": self.radius_km,
        }


@dataclass
class PlanStep:
    """One interpretable step in the search plan, with rationale."""

    action: str
    parameters: dict[str, Any] = field(default_factory=dict)
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"action": self.action, "parameters": self.parameters, "rationale": self.rationale}


@dataclass
class SearchPlan:
    """A structured, explainable plan derived from a natural-language query."""

    raw_query: str
    intent: str
    filters: SearchFilters = field(default_factory=SearchFilters)
    analytic: dict[str, Any] = field(default_factory=dict)  # e.g. min_districts, window_hours
    steps: list[PlanStep] = field(default_factory=list)
    confidence: float = 0.0
    notes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_step(self, action: str, rationale: str, **params: Any) -> None:
        self.steps.append(PlanStep(action=action, parameters=params, rationale=rationale))

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw_query": self.raw_query,
            "intent": self.intent,
            "filters": self.filters.to_dict(),
            "analytic": dict(self.analytic),
            "steps": [s.to_dict() for s in self.steps],
            "confidence": round(self.confidence, 3),
            "notes": self.notes,
            "warnings": self.warnings,
        }


__all__ = [
    "TimeWindow",
    "SearchFilters",
    "SearchPlan",
    "PlanStep",
    "INTENT_FIND_VEHICLES",
    "INTENT_VEHICLES_NEAR",
    "INTENT_MULTI_DISTRICT",
    "INTENT_REPEATED_NIGHT",
    "INTENT_RELATED_VEHICLES",
    "INTENT_TIMELINE",
    "INTENT_EVIDENCE",
    "INTENT_UNKNOWN",
]
