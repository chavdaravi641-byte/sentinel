"""Gap analysis for the statewide CCTV registry.

Identifies areas with insufficient coverage (blind spots), low-density zones,
and recommends candidate camera placements to close the most impactful gaps.
Pure geometric analysis on top of :mod:`src.registry.coverage`.
"""

from __future__ import annotations

from typing import Any, Iterable

from src.registry.coverage import CameraPoint, blind_spots, road_coverage
from src.registry.geography import bbox_of, grid_cells, haversine_m


def low_density_zones(points: Iterable[CameraPoint], cell_m: float = 4000.0,
                      threshold: int = 2, radius_m: float = 3000.0) -> list[dict[str, Any]]:
    """Find grid cells whose camera count falls below ``threshold``.

    Each returned zone carries a suggested placement at the cell centre, the
    nearest existing camera distance, and a priority based on deficit.
    """
    pts = list(points)
    if not pts:
        return []
    bbox = bbox_of([(p.lat, p.lon) for p in pts])
    cells = grid_cells(bbox[0], bbox[1], bbox[2], bbox[3], cell_m)
    zones: list[dict[str, Any]] = []
    for (clat, clon) in cells:
        nearby = [p for p in pts if haversine_m(clat, clon, p.lat, p.lon) <= radius_m]
        count = len(nearby)
        if count <= threshold and count == 0:
            nearest = min(
                (haversine_m(clat, clon, p.lat, p.lon) for p in pts), default=0.0
            )
            zones.append({
                "lat": round(clat, 6), "lng": round(clon, 6),
                "nearby_cameras": count,
                "nearest_camera_m": round(nearest, 1),
                "priority": _priority(nearest),
                "suggested_placement": {"lat": round(clat, 6), "lng": round(clon, 6)},
            })
    zones.sort(key=lambda z: (-z["nearest_camera_m"], z["lng"], z["lat"]))
    return zones


def _priority(nearest_m: float) -> str:
    if nearest_m >= 10000:
        return "high"
    if nearest_m >= 4000:
        return "medium"
    return "low"


def critical_point_coverage(points: Iterable[CameraPoint],
                            critical_points: Iterable[tuple[float, float]],
                            radius_m: float | None = None) -> dict[str, Any]:
    """How well the given critical/road points are covered by cameras."""
    pts = list(points)
    return road_coverage(pts, list(critical_points), radius_m=radius_m)


def run_gap_report(points: Iterable[CameraPoint], *, cell_m: float = 4000.0) -> dict[str, Any]:
    """Produce the full gap-analysis report."""
    pts = list(points)
    bl = blind_spots(pts, cell_m=cell_m)
    zones = low_density_zones(pts, cell_m=cell_m * 8)
    return {
        "camera_count": len(pts),
        "blind_spot_cells": len(bl["uncovered_cells"]),
        "uncovered_area_m2": round(bl["uncovered_area_m2"], 1),
        "low_density_zones": zones,
        "recommended_placements": [z["suggested_placement"] for z in zones[:20]],
    }


__all__: list[str] = ["critical_point_coverage", "low_density_zones", "run_gap_report"]
