"""Investigation workspace / search (Phase 5).

Search utilities for the analyst: find a vehicle by partial plate, find matches
near a location, filter by appearance, and build a compact work file for an
investigation (identity + timeline + route summary).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.anpr.vehicle_intel.identity import canonical_plate, plate_fingerprint
from src.anpr.vehicle_intel.graph import CameraGraph, haversine_km


@dataclass
class SearchQuery:
    plate: str = ""
    vehicle_type: str = ""
    color: str = ""
    location: str = ""
    near_lat: float | None = None
    near_lng: float | None = None
    radius_km: float = 10.0
    min_confidence: float = 0.0
    start_ts: float | None = None
    end_ts: float | None = None
    limit: int = 100


def _plate_partial_match(observed_plate: str, query_plate: str) -> bool:
    """True if the canonical observed plate contains the query plate as a
    contiguous substring (partial plate search)."""
    if not query_plate:
        return True
    q = canonical_plate(query_plate)
    return q in canonical_plate(observed_plate)


def search_observations(
    sightings: list[dict[str, Any]],
    graph: CameraGraph,
    query: SearchQuery,
) -> list[dict[str, Any]]:
    """Filter a set of observations against a `SearchQuery`.

    Returns matching observation dicts (enriched with camera name/location),
    scored and ranked by relevance, up to `query.limit`.
    """
    node_idx = {n.camera_id: n for n in graph.nodes()}
    results = []
    qc = canonical_plate(query.plate)
    qtype = query.vehicle_type.strip().lower()
    qcolor = query.color.strip().lower()

    for o in sightings:
        cam = str(o.get("camera_id"))
        plate = canonical_plate(o.get("plate", ""))
        app = o.get("appearance") or {}
        otype = str(app.get("vehicle_type", "")).strip().lower()
        ocolor = str(app.get("color", "")).strip().lower()

        # time window
        ts = float(o.get("ts", 0))
        if query.start_ts is not None and ts < query.start_ts:
            continue
        if query.end_ts is not None and ts > query.end_ts:
            continue
        # plate
        if qc and not _plate_partial_match(plate, query.plate):
            continue
        # appearance
        if qtype and otype != qtype:
            continue
        if qcolor and ocolor != qcolor:
            continue
        # confidence
        if float(o.get("ocr_confidence", 0.0)) < query.min_confidence:
            continue
        # geo radius
        node = node_idx.get(cam)
        if query.near_lat is not None and query.near_lng is not None:
            if node is None:
                continue
            d = haversine_km(query.near_lat, query.near_lng, node.latitude, node.longitude)
            if d > query.radius_km:
                continue

        score = 1.0
        if qc:
            score += 1.0 if canonical_plate(plate) == qc else 0.5
        if qtype and otype == qtype:
            score += 0.3
        if qcolor and ocolor == qcolor:
            score += 0.2
        if query.near_lat is not None and query.near_lng is not None and node is not None:
            d = haversine_km(query.near_lat, query.near_lng, node.latitude, node.longitude)
            score += 1.0 / (0.1 + d)

        results.append(
            {
                **dict(o),
                "camera_name": node.camera_name if node else cam,
                "location": node.location if node else o.get("location", ""),
                "search_score": round(score, 4),
            }
        )

    results.sort(key=lambda x: -x["search_score"])
    return results[: query.limit]


def build_investigation_workspace(
    vehicle_uuid: str,
    identity: dict[str, Any],
    sightings: list[dict[str, Any]],
    graph: CameraGraph,
    timeline: dict[str, Any],
    route_summary: dict[str, Any],
) -> dict[str, Any]:
    """Assemble a compact work file for an investigation."""
    return {
        "vehicle_uuid": vehicle_uuid,
        "identity": identity,
        "sighting_count": len(sightings),
        "journeys": timeline.get("journey_count", 0),
        "timeline": timeline,
        "route_summary": route_summary,
    }


__all__ = [
    "SearchQuery",
    "plate_fingerprint",
    "search_observations",
    "build_investigation_workspace",
]
