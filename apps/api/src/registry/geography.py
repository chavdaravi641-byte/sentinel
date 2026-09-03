"""Pure-Python geographic primitives for the statewide CCTV GIS foundation.

This module deliberately avoids GeoAlchemy2 / Proj / shapely so the GIS engine
runs anywhere (including the test container). The math here backs coverage,
clustering, density and gap analysis; production deployments can swap in the
companion PostGIS SQL (:mod:`src.registry.gis_sql`) for native spatial scaling
to 80,000+ cameras.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Iterable

# Mean Earth radius in metres (WGS84 spherical approximation).
EARTH_RADIUS_M = 6_371_000.0


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points in metres."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    return haversine_m(lat1, lon1, lat2, lon2) / 1000.0


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial bearing from point 1 to point 2 in degrees (0..360)."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dlmb = math.radians(lon2 - lon1)
    y = math.sin(dlmb) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlmb)
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def point_at(lat: float, lon: float, dist_m: float, bearing: float) -> tuple[float, float]:
    """Destination point given start, distance (m) and bearing (deg)."""
    phi1 = math.radians(lat)
    lmb1 = math.radians(lon)
    angular = dist_m / EARTH_RADIUS_M
    theta = math.radians(bearing)
    phi2 = math.asin(
        math.sin(phi1) * math.cos(angular) + math.cos(phi1) * math.sin(angular) * math.cos(theta)
    )
    lmb2 = lmb1 + math.atan2(
        math.sin(theta) * math.sin(angular) * math.cos(phi1),
        math.cos(angular) - math.sin(phi1) * math.sin(phi2),
    )
    return math.degrees(phi2), math.degrees(lmb2)


def point_in_circle(lat: float, lon: float, center_lat: float, center_lon: float, radius_m: float) -> bool:
    """True when ``(lat,lon)`` falls within ``radius_m`` of the center."""
    return haversine_m(lat, lon, center_lat, center_lon) <= radius_m


def circle_intersection_area(
    lat1: float, lon1: float, lat2: float, lon2: float, radius_m: float,
) -> float:
    """Overlap area (m^2) of two equal circles of radius ``radius_m``."""
    d = haversine_m(lat1, lon1, lat2, lon2)
    if d == 0:
        return math.pi * radius_m * radius_m
    if d >= 2 * radius_m:
        return 0.0
    r2 = radius_m * radius_m
    part = (2 * r2) * math.acos(d / (2 * radius_m))
    part -= (d / 2) * math.sqrt(4 * r2 - d * d)
    return part


def union_area_of_coverage(
    points: Iterable[tuple[float, float]],
    radius_m: float,
    samples: int = 24,
    grid: int = 200,
) -> float:
    """Monte-Carlo / raster estimate of the union area covered by circles.

    Deterministic grid-sampling of the bounding box with ``grid`` cells per
    axis. Used by coverage analysis to report *effective* (non-duplicated)
    coverage area — a figure a naive per-camera ``pi r^2`` sum grossly
    overstates when cameras overlap.
    """
    pts = list(points)
    if not pts:
        return 0.0
    min_lat = min(p[0] for p in pts)
    max_lat = max(p[0] for p in pts)
    min_lon = min(p[1] for p in pts)
    max_lon = max(p[1] for p in pts)
    if max_lat == min_lat and max_lon == min_lon:
        return math.pi * radius_m * radius_m
    # Expand bbox by one radius so edge circles are fully sampled.
    min_lat, min_lon = point_at(min_lat, min_lon, radius_m, 225.0)
    max_lat, max_lon = point_at(max_lat, max_lon, radius_m, 45.0)

    lat_step = (max_lat - min_lat) / grid
    lon_step = (max_lon - min_lon) / grid
    covered = 0
    for i in range(grid):
        lat = min_lat + (i + 0.5) * lat_step
        for j in range(grid):
            lon = min_lon + (j + 0.5) * lon_step
            for (clat, clon) in pts:
                if haversine_m(lat, lon, clat, clon) <= radius_m:
                    covered += 1
                    break
    cell_lat_m = haversine_m(min_lat, 0, min_lat + lat_step, 0)
    cell_lon_m = haversine_m((min_lat + max_lat) / 2.0, min_lon, (min_lat + max_lat) / 2.0, min_lon + lon_step)
    cell_area = max(cell_lat_m, 0.0) * max(cell_lon_m, 0.0)
    return covered * cell_area


def grid_cells(
    min_lat: float, min_lon: float, max_lat: float, max_lon: float, cell_m: float,
) -> list[tuple[float, float]]:
    """Centres of a fixed-metre grid over a lat/lon bbox."""
    cells: list[tuple[float, float]] = []
    # Grid step in lat (metres are ~constant for meridian) and lon (scaled).
    step_lat = cell_m / EARTH_RADIUS_M * (180.0 / math.pi)
    mid_lat = (min_lat + max_lat) / 2.0
    step_lon = cell_m / EARTH_RADIUS_M * (180.0 / math.pi) / max(math.cos(math.radians(mid_lat)), 1e-6)
    if step_lat <= 0 or step_lon <= 0:
        return []
    lat = min_lat
    while lat <= max_lat:
        lon = min_lon
        while lon <= max_lon:
            cells.append((lat, lon))
            lon += step_lon
        lat += step_lat
    return cells


def area_m2(min_lat: float, min_lon: float, max_lat: float, max_lon: float) -> float:
    """Approx area (m^2) of a lat/lon bounding box.

    Width is taken at the mid-latitude (lon degrees shrink towards the poles);
    height is a constant meridian distance.
    """
    mid_lat = (min_lat + max_lat) / 2.0
    height_m = haversine_m(min_lat, 0, max_lat, 0)
    width_m = haversine_m(mid_lat, 0, mid_lat, abs(max_lon - min_lon))
    return height_m * width_m


def bbox_of(points: Iterable[tuple[float, float]]) -> tuple[float, float, float, float] | None:
    pts = list(points)
    if not pts:
        return None
    lats = [p[0] for p in pts]
    lons = [p[1] for p in pts]
    return min(lats), min(lons), max(lats), max(lons)


def kmeans2(points: list[tuple[float, float]], k: int, max_iter: int = 12) -> list[tuple[float, float]]:
    """A tiny deterministic k-means (seeded by a grid) for spatial clustering."""
    pts = list(points)
    n = len(pts)
    if n == 0:
        return []
    if k <= 1:
        return [sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n]
    if k >= n:
        return list(pts)
    clats = [p[0] for p in pts]
    clons = [p[1] for p in pts]
    # Deterministic initial centroids spread across min/max.
    min_lat = min(clats)
    max_lat = max(clats)
    min_lon = min(clons)
    max_lon = max(clons)
    centroids = [
        (
            min_lat + ((i + 1) / (k + 1)) * (max_lat - min_lat),
            min_lon + ((i + 1) / (k + 1)) * (max_lon - min_lon),
        )
        for i in range(k)
    ]
    for _ in range(max_iter):
        clusters: list[list[tuple[float, float]]] = [[] for _ in range(k)]
        for p in pts:
            dists = [haversine_m(p[0], p[1], c[0], c[1]) for c in centroids]
            clusters[int(dists.index(min(dists)))].append(p)
        moved = False
        for i in range(k):
            if not clusters[i]:
                continue
            new_c = (sum(p[0] for p in clusters[i]) / len(clusters[i]),
                     sum(p[1] for p in clusters[i]) / len(clusters[i]))
            if haversine_m(new_c[0], new_c[1], centroids[i][0], centroids[i][1]) > 1.0:
                moved = True
            centroids[i] = new_c
        if not moved:
            break
    return centroids


def point_on_grid_density(
    cells: list[tuple[float, float]],
    points: list[tuple[float, float]],
    radius_m: float,
) -> list[dict[str, Any]]:
    """Counts how many points fall within each grid cell (density layer)."""
    out: list[dict[str, Any]] = []
    for (clat, clon) in cells:
        count = sum(1 for (lat, lon) in points if haversine_m(lat, lon, clat, clon) <= radius_m)
        if count:
            out.append({"lat": clat, "lng": clon, "count": count})
    return out


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


__all__: list[str] = [
    "EARTH_RADIUS_M",
    "area_m2",
    "bbox_of",
    "bearing_deg",
    "circle_intersection_area",
    "grid_cells",
    "haversine_km",
    "haversine_m",
    "kmeans2",
    "point_at",
    "point_in_circle",
    "point_on_grid_density",
    "union_area_of_coverage",
    "utc_now",
]