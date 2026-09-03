"""Camera Graph (Phase 5).

Represents the Gujarat CCTV camera network as a directed graph. Every node is a
real registered camera (from the `cameras` table). Edges encode road
connectivity / reachability, travel time and road distance between cameras.

Documented assumptions (no fabricated road data)
------------------------------------------------
A real road network / GIS layer is NOT available in this phase. Therefore the
graph abstraction is built with the following explicit, configurable
assumptions:

1. *Connectivity*: two cameras A->B are connected if the great-circle
   (haversine) distance between them is `<= MAX_LINK_KM`. This is a purely
   geometric proxy for "B is physically reachable from A".
2. *Road distance*: `road_distance = haversine_km * ROAD_FACTOR` where
   `ROAD_FACTOR` (default 1.25) accounts for the fact roads are rarely
   straight. Fully configurable; when a real road layer is provided later, the
   factor is replaced by measured distances.
3. *Average travel time*: `travel_time_minutes = road_distance_km /
   ASSUMED_SPEED_KPH * 60`, using a default network-average speed
   `ASSUMED_SPEED_KPH = 35` (urban/mixed Gujarat). Configurable per deployment.
4. Directed edges default to bidirectional (a surveyed 2-way road). Lane
   direction restriction is a future enhancement (assumption: all edges are
   traversable both ways).

These assumptions are exposed as `GraphConfig` so an operator can calibrate
them against measured data. No fabricated camera is created: the graph is
*derived* from cameras present in the system.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from src.anpr.vehicle_intel.identity import canonical_plate  # noqa: F401  (re-export convenience)


# --------------------------------------------------------------------------- #
# Geometry
# --------------------------------------------------------------------------- #
EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two lat/lon points in kilometres."""
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
@dataclass
class GraphConfig:
    max_link_km: float = 12.0  # assume connected if within this distance
    road_factor: float = 1.25  # road distance = haversine * factor
    assumed_speed_kph: float = 35.0  # network-average speed for travel-time


# --------------------------------------------------------------------------- #
# Types
# --------------------------------------------------------------------------- #
@dataclass
class CameraNode:
    camera_id: str
    camera_name: str
    location: str
    latitude: float
    longitude: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "camera_id": self.camera_id,
            "camera_name": self.camera_name,
            "location": self.location,
            "latitude": self.latitude,
            "longitude": self.longitude,
        }


@dataclass
class CameraEdge:
    source: str
    target: str
    road_distance_km: float
    travel_time_minutes: float
    bidirectional: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "road_distance_km": round(self.road_distance_km, 3),
            "travel_time_minutes": round(self.travel_time_minutes, 2),
            "bidirectional": self.bidirectional,
        }


class CameraGraph:
    """Directed weighted graph over registered cameras."""

    def __init__(self, config: GraphConfig | None = None) -> None:
        self.config = config or GraphConfig()
        self._nodes: dict[str, CameraNode] = {}
        self._edges: dict[str, dict[str, CameraEdge]] = {}  # source -> {target: edge}
        self._assumptions = [
            "No real road network/GIS layer; connectivity = geometric proximity within MAX_LINK_KM.",
            "road_distance = haversine_km * ROAD_FACTOR (default 1.25).",
            "travel_time = road_distance / ASSUMED_SPEED_KPH (default 35 kph mix).",
            "All edges bidirectional (2-way roads) by default.",
        ]

    # ------------------------------------------------------------------ #
    def add_camera(
        self,
        camera_id: str,
        camera_name: str,
        location: str,
        latitude: float,
        longitude: float,
    ) -> None:
        self._nodes[camera_id] = CameraNode(
            camera_id=camera_id,
            camera_name=camera_name,
            location=location,
            latitude=float(latitude),
            longitude=float(longitude),
        )

    def add_cameras(self, cameras: list[dict[str, Any]]) -> None:
        for c in cameras:
            self.add_camera(
                camera_id=str(c["id"]),
                camera_name=str(c.get("name", "")),
                location=str(c.get("location", "")),
                latitude=float(c["latitude"]),
                longitude=float(c["longitude"]),
            )

    def _connect(self) -> None:
        """Build edges from geometry (idempotent; recompute)."""
        self._edges = {cid: {} for cid in self._nodes}
        ids = list(self._nodes)
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a = self._nodes[ids[i]]
                b = self._nodes[ids[j]]
                km = haversine_km(a.latitude, a.longitude, b.latitude, b.longitude)
                if km <= self.config.max_link_km:
                    road = km * self.config.road_factor
                    minutes = road / self.config.assumed_speed_kph * 60.0
                    self._edges[a.camera_id][b.camera_id] = CameraEdge(
                        source=a.camera_id,
                        target=b.camera_id,
                        road_distance_km=road,
                        travel_time_minutes=minutes,
                    )
                    self._edges[b.camera_id][a.camera_id] = CameraEdge(
                        source=b.camera_id,
                        target=a.camera_id,
                        road_distance_km=road,
                        travel_time_minutes=minutes,
                    )

    def build(self) -> None:
        self._connect()

    # ------------------------------------------------------------------ #
    def nodes(self) -> list[CameraNode]:
        return list(self._nodes.values())

    def has(self, camera_id: str) -> bool:
        return camera_id in self._nodes

    def neighbors(self, camera_id: str) -> list[str]:
        return list(self._edges.get(camera_id, {}).keys())

    def edge(self, source: str, target: str) -> CameraEdge | None:
        return self._edges.get(source, {}).get(target)

    def nearby_cameras(self, camera_id: str, k: int = 10) -> list[dict[str, Any]]:
        """Nearest neighbours by road distance (default returns all neighbours)."""
        nbrs = sorted(
            self.neighbors(camera_id),
            key=lambda t: self._edges[camera_id][t].road_distance_km,
        )
        out = []
        for t in nbrs[:k]:
            e = self._edges[camera_id][t]
            n = self._nodes[t]
            out.append(
                {
                    "camera_id": t,
                    "camera_name": n.camera_name,
                    "road_distance_km": round(e.road_distance_km, 3),
                    "travel_time_minutes": round(e.travel_time_minutes, 2),
                    "location": n.location,
                }
            )
        return out

    # ------------------------------------------------------------------ #
    # Shortest path (Dijkstra on travel time)
    # ------------------------------------------------------------------ #
    def shortest_path(
        self, start: str, end: str
    ) -> tuple[list[str], float] | None:
        """Return (camera_id path, total_travel_minutes) or None if unreachable."""
        if start not in self._nodes or end not in self._nodes:
            return None
        import heapq

        dist = {start: 0.0}
        prev: dict[str, str | None] = {start: None}
        pq = [(0.0, start)]
        seen = set()
        while pq:
            d, u = heapq.heappop(pq)
            if u in seen:
                continue
            seen.add(u)
            if u == end:
                break
            for v, e in self._edges.get(u, {}).items():
                nd = d + e.travel_time_minutes
                if nd < dist.get(v, math.inf):
                    dist[v] = nd
                    prev[v] = u
                    heapq.heappush(pq, (nd, v))
        if end not in dist:
            return None
        # Reconstruct
        path: list[str] = []
        cur: str | None = end
        while cur is not None:
            path.append(cur)
            cur = prev[cur]
        path.reverse()
        return path, dist[end]

    def road_distance(self, start: str, end: str) -> float | None:
        sp = self.shortest_path(start, end)
        if sp is None:
            return None
        path, _ = sp
        total = 0.0
        for a, b in zip(path, path[1:]):
            total += self._edges[a][b].road_distance_km
        return total

    # ------------------------------------------------------------------ #
    def to_payload(self) -> dict[str, Any]:
        return {
            "assumptions": list(self._assumptions),
            "config": {
                "max_link_km": self.config.max_link_km,
                "road_factor": self.config.road_factor,
                "assumed_speed_kph": self.config.assumed_speed_kph,
            },
            "nodes": [n.to_dict() for n in self.nodes()],
            "edges": [
                e.to_dict()
                for targets in self._edges.values()
                for e in targets.values()
            ],
        }


def build_graph_from_cameras(cameras: list[dict[str, Any]], config: GraphConfig | None = None) -> CameraGraph:
    """Construct a CameraGraph from DB camera rows (assumes `id`, `name`,
    `location`, `latitude`, `longitude` keys present)."""
    g = CameraGraph(config)
    g.add_cameras(cameras)
    g.build()
    return g


__all__ = [
    "EARTH_RADIUS_KM",
    "haversine_km",
    "GraphConfig",
    "CameraNode",
    "CameraEdge",
    "CameraGraph",
    "build_graph_from_cameras",
]
