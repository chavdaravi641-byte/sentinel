"""Camera coverage analysis for the statewide CCTV GIS foundation.

Computes per-camera coverage circles, effective (union) covered area, pairwise
overlap, blind spots (uncovered cells), camera density and how well critical /
road points are covered. Purely geometric — no DB or network required.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from src.registry.geography import (
    bbox_of,
    grid_cells,
    haversine_m,
    point_in_circle,
    union_area_of_coverage,
)


@dataclass
class CameraPoint:
    id: str
    lat: float
    lon: float
    radius_m: float = 250.0
    category: str = "city"
    status: str = "online"
    district_code: str = ""

    def as_dict(self, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id, "lat": self.lat, "lng": self.lon,
            "radius_m": self.radius_m, "category": self.category, "status": self.status,
        }
        if extra:
            data.update(extra)
        return data


def total_nominal_area(points: Iterable[CameraPoint]) -> float:
    pts = list(points)
    if not pts:
        return 0.0
    return sum(_circle_area(p.radius_m) for p in pts)


def _circle_area(r: float) -> float:
    import math  # noqa: PLC0415
    return math.pi * r * r


def effective_covered_area(points: Iterable[CameraPoint], grid: int = 120) -> float:
    """Union (non-duplicated) area covered by all coverage circles in m^2."""
    pts = list(points)
    if not pts:
        return 0.0
    return union_area_of_coverage([(p.lat, p.lon) for p in pts], max(p.radius_m for p in pts), grid=grid)


def overlap_ratio_pair(a: CameraPoint, b: CameraPoint) -> float:
    """Fraction of the smaller circle overlapped by the larger (0..1)."""
    from src.registry.geography import circle_intersection_area  # noqa: PLC0415
    r = min(a.radius_m, b.radius_m)
    inter = circle_intersection_area(a.lat, a.lon, b.lat, b.lon, r)
    return min(1.0, inter / max(_circle_area(r), 1e-12))


def overlaps(points: Iterable[CameraPoint], threshold: float = 0.3) -> list[dict[str, Any]]:
    """List of overlapping camera pairs above the given overlap ratio."""
    pts = list(points)
    out: list[dict[str, Any]] = []
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            ratio = overlap_ratio_pair(pts[i], pts[j])
            if ratio >= threshold:
                out.append({
                    "a": pts[i].id, "b": pts[j].id,
                    "distance_m": round(haversine_m(pts[i].lat, pts[i].lon, pts[j].lat, pts[j].lon), 1),
                    "overlap_ratio": round(ratio, 3),
                })
    return out


def blind_spots(points: Iterable[CameraPoint], cell_m: float = 500.0) -> dict[str, Any]:
    """Identify uncovered grid cells (blind spots) within the cluster bbox.

    Returns the uncovered cells and the estimated uncovered area.
    """
    pts = list(points)
    if not pts:
        return {"uncovered_cells": [], "cell_m": cell_m, "uncovered_area_m2": 0.0, "covered_area_m2": 0.0, "total_area_m2": 0.0}
    bbox = bbox_of([(p.lat, p.lon) for p in pts])
    min_lat, min_lon, max_lat, max_lon = bbox
    cells = grid_cells(min_lat, min_lon, max_lat, max_lon, cell_m)
    uncovered: list[dict[str, Any]] = []
    covered_cells = 0
    for (clat, clon) in cells:
        hit = any(point_in_circle(clat, clon, p.lat, p.lon, p.radius_m) for p in pts)
        if hit:
            covered_cells += 1
        else:
            uncovered.append({"lat": clat, "lng": clon})
    cell_m2 = cell_m * cell_m
    return {
        "uncovered_cells": uncovered,
        "cell_m": cell_m,
        "uncovered_area_m2": len(uncovered) * cell_m2,
        "covered_area_m2": covered_cells * cell_m2,
        "total_area_m2": len(cells) * cell_m2,
    }


def density_grid(points: Iterable[CameraPoint], cell_m: float = 2000.0, radius_m: float = 1500.0) -> list[dict[str, Any]]:
    """Density (cameras per area) grid layer for heat-mapping in Leaflet."""
    pts = list(points)
    if not pts:
        return []
    bbox = bbox_of([(p.lat, p.lon) for p in pts])
    cells = grid_cells(bbox[0], bbox[1], bbox[2], bbox[3], cell_m)
    out: list[dict[str, Any]] = []
    for (clat, clon) in cells:
        count = sum(1 for p in pts if point_in_circle(clat, clon, p.lat, p.lon, radius_m))
        if count:
            out.append({"lat": clat, "lng": clon, "count": count})
    return out


def road_coverage(points: Iterable[CameraPoint], road_points: Iterable[CameraPoint | tuple[float, float]],
                  radius_m: float | None = None) -> dict[str, Any]:
    """Fraction of given road / critical points within camera coverage radii."""
    pts = list(points)
    road = list(road_points)
    if not pts or not road:
        return {"total_points": len(road), "covered": 0, "coverage_pct": 0.0}
    covered = 0
    for rp in road:
        if isinstance(rp, CameraPoint):
            lat, lon = rp.lat, rp.lon
        else:
            lat, lon = rp
        if any(point_in_circle(lat, lon, p.lat, p.lon, p.radius_m if radius_m is None else radius_m) for p in pts):
            covered += 1
    return {
        "total_points": len(road),
        "covered": covered,
        "coverage_pct": round(100.0 * covered / len(road), 2),
    }


def analyze(points: Iterable[CameraPoint], *, cell_m: float = 500.0) -> dict[str, Any]:
    """Run the full coverage analysis and return a structured report."""
    pts = list(points)
    if not pts:
        return {
            "cameras": 0, "nominal_area_m2": 0.0, "effective_area_m2": 0.0,
            "efficiency_pct": 0.0, "overlapping_pairs": [], "blind_spots": [],
            "density": [], "coverage": {},
        }
    nominal = total_nominal_area(pts)
    effective = effective_covered_area(pts, grid=min(60, max(30, round(len(pts) ** 0.5) * 10)))
    efficiency = (effective / nominal * 100.0) if nominal else 0.0
    return {
        "cameras": len(pts),
        "nominal_area_m2": round(nominal, 1),
        "effective_area_m2": round(effective, 1),
        "efficiency_pct": round(efficiency, 2),
        "overlapping_pairs": overlaps(pts),
        "blind_spots": blind_spots(pts, cell_m=cell_m),
        "density": density_grid(pts, cell_m=cell_m * 4),
        "coverage_radius_m": pts[0].radius_m,
    }


__all__: list[str] = [
    "CameraPoint", "analyze", "blind_spots", "density_grid", "effective_covered_area",
    "overlap_ratio_pair", "overlaps", "road_coverage", "total_nominal_area",
]
