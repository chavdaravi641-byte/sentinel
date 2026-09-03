"""Spatial clustering + district/city aggregation for the GIS foundation.

Groups cameras into geospatial clusters (for Leaflet marker clustering and
district rollups) using a deterministic k-means and greedy radius grouping.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

from src.registry.coverage import CameraPoint
from src.registry.geography import haversine_m, kmeans2


def greedy_clusters(points: Iterable[CameraPoint], radius_m: float = 5000.0) -> list[dict[str, Any]]:
    """Greedy single-link clustering by proximity.

    Returns cluster objects with a representative centroid, member ids and
    count — suitable for Leaflet ``L.markerClusterGroup`` / centre popups.
    """
    pts = list(points)
    clusters: list[list[CameraPoint]] = []
    for p in pts:
        placed = False
        for cluster in clusters:
            centre = _cluster_centre(cluster)
            if haversine_m(p.lat, p.lon, centre[0], centre[1]) <= radius_m:
                cluster.append(p)
                placed = True
                break
        if not placed:
            clusters.append([p])
    out: list[dict[str, Any]] = []
    for cluster in clusters:
        centre = _cluster_centre(cluster)
        out.append({
            "id": cluster[0].id.rsplit("-", 1)[-1] if "-" in cluster[0].id else cluster[0].id,
            "count": len(cluster),
            "lat": round(centre[0], 6),
            "lng": round(centre[1], 6),
            "member_ids": [c.id for c in cluster],
            "radius_m": radius_m,
        })
    return out


def _cluster_centre(cluster: list[CameraPoint]) -> tuple[float, float]:
    return sum(c.lat for c in cluster) / len(cluster), sum(c.lon for c in cluster) / len(cluster)


def kmean_clusters(points: Iterable[CameraPoint], k: int) -> list[dict[str, Any]]:
    """K-means spatial clusters (deterministic)."""
    pts = list(points)
    if not pts:
        return []
    k = max(1, min(k, len(pts)))
    centroids = kmeans2([(p.lat, p.lon) for p in pts], k)
    if k == 1 and centroids:
        return [{"count": len(pts), "lat": round(centroids[0], 6), "lng": round(centroids[1], 6),
                 "member_ids": [c.id for c in pts], "radius_m": 0}]
    groups: list[list[CameraPoint]] = [[] for _ in range(k)]
    for p in pts:
        dists = [haversine_m(p.lat, p.lon, c[0], c[1]) for c in centroids]
        groups[int(dists.index(min(dists)))].append(p)
    out: list[dict[str, Any]] = []
    for i, group in enumerate(groups):
        if not group:
            continue
        c = centroids[i]
        out.append({"count": len(group), "lat": round(c[0], 6), "lng": round(c[1], 6),
                    "member_ids": [p.id for p in group], "radius_m": 0})
    return out


def aggregate_by_district(points: Iterable[CameraPoint]) -> list[dict[str, Any]]:
    """Roll up cameras by district (derived from ``id`` prefix if encoded).

    Callers may pass ``district_code`` per camera; when absent the cluster is
    bucketed as ``unknown``.
    """
    buckets: dict[str, list[CameraPoint]] = defaultdict(list)
    for p in points:
        code = getattr(p, "district_code", None) or "unknown"
        buckets[code].append(p)
    out: list[dict[str, Any]] = []
    for code, group in buckets.items():
        centre = _cluster_centre(group)
        out.append({"district_code": code, "count": len(group),
                    "lat": round(centre[0], 6), "lng": round(centre[1], 6)})
    out.sort(key=lambda d: d["count"], reverse=True)
    return out


__all__: list[str] = ["aggregate_by_district", "greedy_clusters", "kmean_clusters"]
