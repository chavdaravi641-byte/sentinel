"""Traffic intelligence (Phase 5).

Aggregates many vehicle observations into network-level insight:

- most-used routes (frequent camera sequences),
- suspicious routes (unnaturally fast travel — likely speeding, or repeated
  unusual path patterns),
- repeated visits (same vehicle at same camera multiple times),
- night activity (observations in night hours),
- heatmap (per-camera observation density and per-segment load).

All figures are computed from real observations on registered cameras only.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from src.anpr.vehicle_intel.reconstruction import reconstruct_route
from src.anpr.vehicle_intel.graph import CameraGraph


@dataclass
class TrafficInsights:
    total_observations: int
    unique_vehicles: int
    active_cameras: int
    total_routes_reconstructed: int
    most_used_routes: list[dict[str, Any]]
    suspicious_routes: list[dict[str, Any]]
    repeated_visits: list[dict[str, Any]]
    night_activity: dict[str, Any]
    camera_heatmap: list[dict[str, Any]]
    segment_load: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_observations": self.total_observations,
            "unique_vehicles": self.unique_vehicles,
            "active_cameras": self.active_cameras,
            "total_routes_reconstructed": self.total_routes_reconstructed,
            "most_used_routes": self.most_used_routes,
            "suspicious_routes": self.suspicious_routes,
            "repeated_visits": self.repeated_visits,
            "night_activity": self.night_activity,
            "camera_heatmap": self.camera_heatmap,
            "segment_load": self.segment_load,
        }


def _is_night(ts: float) -> bool:
    import datetime as _dt

    try:
        local = _dt.datetime.fromtimestamp(ts, tz=_dt.timezone.utc)
        return local.hour >= 21 or local.hour < 6
    except Exception:  # noqa: BLE001
        return False


def compute_traffic_insights(
    observations: list[dict[str, Any]],
    graph: CameraGraph,
    *,
    top_routes: int = 10,
    speed_threshold_kph: float = 80.0,
) -> TrafficInsights:
    """Compute aggregate traffic intelligence from observations.

    `observations` must contain dicts with keys: vehicle_uuid, camera_id, ts,
    (optionally) appearance, plate, lat, lng.
    """
    total_obs = len(observations)
    unique_vehicles = len({o.get("vehicle_uuid") for o in observations})
    active_cameras = len({o.get("camera_id") for o in observations})

    # Group observations by vehicle, sort by ts.
    by_vehicle: dict[str, list[dict[str, Any]]] = {}
    for o in observations:
        by_vehicle.setdefault(o.get("vehicle_uuid"), []).append(o)
    for vid in by_vehicle:
        by_vehicle[vid].sort(key=lambda x: float(x.get("ts", 0)))

    # ---- routes ---------------------------------------------------------
    routes: Counter[str] = Counter()
    route_to_seq: dict[str, list[str]] = {}
    suspicious: list[dict[str, Any]] = []
    total_routes = 0

    for vid, seq in by_vehicle.items():
        if len(seq) < 2:
            continue
        cam_seq = [str(o.get("camera_id")) for o in seq]
        route_key = "->".join(cam_seq)
        routes[route_key] += 1
        route_to_seq[route_key] = cam_seq
        total_routes += 1
        # Detect suspicious: max inferred segment speed above threshold.
        rec = reconstruct_route(vid, seq, graph)
        max_speed = max((s.inferred_speed_kph or 0.0) for s in rec.segments) if rec.segments else 0.0
        if max_speed > speed_threshold_kph:
            suspicious.append(
                {
                    "vehicle_uuid": vid,
                    "route": route_key,
                    "max_inferred_speed_kph": round(max_speed, 1),
                    "stop_count": rec.stop_count,
                }
            )

    most_used = [
        {"route": key, "count": cnt, "camera_sequence": route_to_seq[key]}
        for key, cnt in routes.most_common(top_routes)
    ]

    # ---- repeated visits ------------------------------------------------
    visit_counts: Counter = Counter()
    for vid, seq in by_vehicle.items():
        for cam in set(str(o.get("camera_id")) for o in seq):
            visit_counts[(vid, cam)] += 1
    repeated = [
        {"vehicle_uuid": vid, "camera_id": cam, "visits": n}
        for (vid, cam), n in visit_counts.items()
        if n >= 2
    ]
    repeated.sort(key=lambda x: -x["visits"])

    # ---- night activity --------------------------------------------------
    night_obs = [o for o in observations if _is_night(float(o.get("ts", 0)))]
    night_vehicles = len({o.get("vehicle_uuid") for o in night_obs})
    night_activity = {
        "night_observations": len(night_obs),
        "night_vehicles": night_vehicles,
        "night_pct": round(100.0 * len(night_obs) / total_obs, 2) if total_obs else 0.0,
    }

    # ---- heatmap / segment load ------------------------------------------
    cam_counts: Counter = Counter(o.get("camera_id") for o in observations)
    camera_heatmap = [
        {
            "camera_id": cam,
            "observations": n,
            "share_pct": round(100.0 * n / total_obs, 2) if total_obs else 0.0,
        }
        for cam, n in cam_counts.most_common()
    ]

    seg_counts: Counter = Counter()
    for _, seq in route_to_seq.items():
        for a, b in zip(seq, seq[1:]):
            seg_counts[(a, b)] += 1
    segment_load = [
        {
            "from_camera": a,
            "to_camera": b,
            "route_count": n,
            "travel_time_minutes": (
                round(graph.edge(a, b).travel_time_minutes, 2)
                if graph.has(a) and graph.has(b) and graph.edge(a, b)
                else None
            ),
        }
        for (a, b), n in seg_counts.most_common()
    ]

    return TrafficInsights(
        total_observations=total_obs,
        unique_vehicles=unique_vehicles,
        active_cameras=active_cameras,
        total_routes_reconstructed=total_routes,
        most_used_routes=most_used,
        suspicious_routes=suspicious,
        repeated_visits=repeated[:50],
        night_activity=night_activity,
        camera_heatmap=camera_heatmap,
        segment_load=segment_load,
    )


__all__ = ["TrafficInsights", "compute_traffic_insights"]
