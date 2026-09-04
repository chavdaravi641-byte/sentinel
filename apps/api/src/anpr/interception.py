"""Predictive Corridor Interception Vector (grand-finale killer feature #2).

When a watchlist vehicle triggers an ANPR alert at a camera, this module
computes the *interception corridor*: the top-K next junction nodes within a
circular radius that a PCR (Police Control Room) unit should race to, each with
a real arrival window so dispatch can be scheduled.

Method
------
1. Starting from the trigger camera node, the camera graph is searched within
   ``radius_km`` (road distance along the derived graph).
2. Every candidate is scored: junction/interceptor nodes are preferred (they
   are the most probable re-acquisition points), then by shortest travel time.
3. For each ranked candidate the module returns the road distance, travel time
   at the assumed target speed and an **arrival window** (ETA ± speed-variance)
   so a PCR dispatcher sees when the vehicle is expected to pass.
4. The full corridor path (camera id chain from trigger -> candidate) is
   included for the tactical map overlay.

The core scoring is pure (no DB/network) so it is unit-testable; the DB-facing
``interception_vector`` assembles the graph and junction metadata.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from src.anpr.vehicle_intel.graph import CameraGraph
from src.anpr.vehicle_intel.prediction import predict_next_cameras

# Junction-like camera categories that make a node a prime interception point.
JUNCTION_CATEGORIES = {"junction", "interceptor", "toll", "signal", "critical_infrastructure"}

# Speed variance bounds for the arrival window (fraction of nominal travel).
WINDOW_LOWER = 0.85
WINDOW_UPPER = 1.25


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class InterceptionNode:
    camera_id: str
    camera_name: str
    location: str
    latitude: float
    longitude: float
    rank: int
    road_distance_km: float
    travel_time_minutes: float
    eta_utc: str
    window_start_utc: str
    window_end_utc: str
    is_junction: bool
    corridor_path: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "camera_id": self.camera_id,
            "camera_name": self.camera_name,
            "location": self.location,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "rank": self.rank,
            "road_distance_km": round(self.road_distance_km, 3),
            "travel_time_minutes": round(self.travel_time_minutes, 1),
            "eta_utc": self.eta_utc,
            "window_start_utc": self.window_start_utc,
            "window_end_utc": self.window_end_utc,
            "is_junction": self.is_junction,
            "corridor_path": self.corridor_path,
        }


@dataclass
class InterceptionVector:
    plate: str
    trigger_camera: str
    assumed_speed_kph: float
    radius_km: float
    observed_ts: str
    basis: str
    nodes: list[InterceptionNode] = field(default_factory=list)

    @property
    def confidence(self) -> float:
        if not self.nodes:
            return 0.0
        # Confidence decays with the most distant hop; closer nodes are surer.
        travel = self.nodes[0].travel_time_minutes
        return round(max(0.35, 1.0 - travel / 120.0), 3)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plate": self.plate,
            "trigger_camera": self.trigger_camera,
            "assumed_speed_kph": self.assumed_speed_kph,
            "radius_km": self.radius_km,
            "observed_ts": self.observed_ts,
            "basis": self.basis,
            "confidence": self.confidence,
            "recommendation": _recommendation(self.nodes),
            "nodes": [n.to_dict() for n in self.nodes],
        }


def _recommendation(nodes: list[InterceptionNode]) -> str:
    if not nodes:
        return "No interception corridor within radius."
    top = nodes[0]
    return (
        f"Dispatch PCR to {top.camera_name} ({top.location or 'unknown location'}) "
        f"~{top.road_distance_km:.1f} km ahead; ETA {top.eta_utc}."
    )


def _pts_to_iso(observed_ts: float | None, delta_minutes: float) -> str:
    base = datetime.fromtimestamp(observed_ts, tz=timezone.utc) if observed_ts else datetime.now(timezone.utc)
    return (base + timedelta(minutes=delta_minutes)).isoformat(timespec="seconds")


def _reachable_within(
    graph: CameraGraph,
    start: str,
    radius_km: float,
    *,
    speed_kph: float,
) -> list[tuple[str, float, float]]:
    """BFS over the graph returning
    ``(camera_id, travel_time_minutes, road_distance_km)`` for every node
    reachable from `start` within `radius_km` of road distance."""
    if not graph.has(start):
        return []
    best: dict[str, tuple[float, float]] = {}  # camera -> (minutes, road_km)
    stack = [(start, 0.0)]
    seen = {start}
    while stack:
        cur, acc = stack.pop()
        for nxt in graph.neighbors(cur):
            edge = graph.edge(cur, nxt)
            if edge is None:
                continue
            road = acc + edge.road_distance_km
            if road > radius_km:
                continue
            minutes = road / speed_kph * 60.0
            old = best.get(nxt)
            if old is None or minutes < old[0]:
                best[nxt] = (minutes, road)
            if nxt not in seen:
                seen.add(nxt)
                stack.append((nxt, road))
    out = [(c, m, r) for c, (m, r) in best.items() if c != start]
    out.sort(key=lambda x: x[1])
    return out


def _shortest_path(graph: CameraGraph, start: str, end: str) -> list[str]:
    sp = graph.shortest_path(start, end)
    return list(sp[0]) if sp else [start, end]


def compute_interception(
    graph: CameraGraph,
    trigger_camera: str,
    *,
    plate: str,
    observed_ts: float | None = None,
    speed_kph: float = 35.0,
    radius_km: float = 15.0,
    top_k: int = 3,
    junction_camera_ids: set[str] | None = None,
    history: list[str] | None = None,
) -> InterceptionVector:
    """Rank the top-K interception corridor nodes for a triggered vehicle.

    ``history`` is the vehicle's camera-id sequence (newest last); when present
    the next-camera prediction is blended in so the polyline follows the likely
    direction of travel rather than nearest-anywhere.
    """
    junction_camera_ids = junction_camera_ids or set()
    observed_ts = observed_ts

    candidates = _reachable_within(graph, trigger_camera, radius_km, speed_kph=speed_kph)
    if not candidates:
        return InterceptionVector(
            plate=plate, trigger_camera=trigger_camera,
            assumed_speed_kph=speed_kph, radius_km=radius_km,
            observed_ts=_pts_to_iso(observed_ts, 0.0),
            basis="none",
            nodes=[],
        )

    # Optional directional bias from the route-prediction model.
    bias: dict[str, float] = {}
    if history:
        pred = predict_next_cameras(trigger_camera, history, graph, top_k=top_k)
        for p in pred.predictions:
            # Small boost to predicted next cameras.
            bias[p["camera_id"]] = p["confidence"]

    scored: list[tuple[float, str]] = []
    for cam, minutes, _road in candidates:
        is_junction = 1.0 if cam in junction_camera_ids else 0.0
        # Junction nodes first, then closeness; weak bias to predicted path.
        bias_boost = bias.get(cam, 0.0) * 10.0
        score = is_junction * 100.0 - minutes + bias_boost
        scored.append((score, cam))
    scored.sort(key=lambda x: x[0], reverse=True)

    candidates_by_id = {cam: (minutes, road) for cam, minutes, road in candidates}
    nodes: list[InterceptionNode] = []
    for rank, (_, cam) in enumerate(scored[:top_k], start=1):
        minutes, road = candidates_by_id[cam]
        node = graph._nodes[cam]
        path = _shortest_path(graph, trigger_camera, cam)
        nodes.append(
            InterceptionNode(
                camera_id=cam,
                camera_name=node.camera_name,
                location=node.location,
                latitude=node.latitude,
                longitude=node.longitude,
                rank=rank,
                road_distance_km=road,
                travel_time_minutes=minutes,
                eta_utc=_pts_to_iso(observed_ts, minutes),
                window_start_utc=_pts_to_iso(observed_ts, minutes * WINDOW_LOWER),
                window_end_utc=_pts_to_iso(observed_ts, minutes * WINDOW_UPPER),
                is_junction=cam in junction_camera_ids,
                corridor_path=path,
            )
        )

    basis = "learned+graph" if history else "graph"
    return InterceptionVector(
        plate=plate,
        trigger_camera=trigger_camera,
        assumed_speed_kph=speed_kph,
        radius_km=radius_km,
        observed_ts=_pts_to_iso(observed_ts, 0.0),
        basis=basis,
        nodes=nodes,
    )


async def interception_vector(
    db,
    *,
    plate: str,
    trigger_camera: str,
    observed_ts: float | None = None,
    speed_kph: float = 35.0,
    radius_km: float = 15.0,
) -> InterceptionVector:
    """DB-facing assembly: build the graph + junction metadata, then compute
    the interception corridor for the given trigger camera."""
    from src.anpr.vehicle_intel.service import get_graph

    graph = await get_graph(db)

    junction_ids: set[str] = set()
    from sqlalchemy import select
    from src.models.registry import CameraRegistry

    reg_rows = (await db.execute(select(CameraRegistry))).scalars().all()
    for r in reg_rows:
        if r.category.value in JUNCTION_CATEGORIES:
            junction_ids.add(str(r.camera_id))

    # Pull a short recent history for this plate (newest last) if available.
    from src.models.anpr import PlateDetection
    history_rows = (
        (
            await db.execute(
                select(PlateDetection.camera_id)
                .where(
                    PlateDetection.normalized_plate == plate.upper().replace(" ", "")
                )
                .order_by(PlateDetection.ts.desc())
                .limit(8)
            )
        )
        .scalars()
        .all()
    )
    history = [str(c) for c in reversed(history_rows)]

    vector = compute_interception(
        graph,
        trigger_camera,
        plate=plate,
        observed_ts=observed_ts,
        speed_kph=speed_kph,
        radius_km=radius_km,
        junction_camera_ids=junction_ids,
        history=history or None,
    )
    return vector


__all__ = [
    "JUNCTION_CATEGORIES",
    "InterceptionNode",
    "InterceptionVector",
    "compute_interception",
    "interception_vector",
]
