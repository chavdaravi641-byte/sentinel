"""Route / journey reconstruction (Phase 5).

Chains a single vehicle's observations across cameras into a coherent journey
and, where the camera graph has path info, infers the most likely road route,
speed and stops between consecutive sightings.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.anpr.vehicle_intel.graph import CameraGraph


@dataclass
class Segment:
    from_camera: str
    to_camera: str
    observed_elapsed_minutes: float
    graph_travel_minutes: float
    road_distance_km: float
    inferred_speed_kph: float | None
    is_stop: bool
    path: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "from_camera": self.from_camera,
            "to_camera": self.to_camera,
            "observed_elapsed_minutes": round(self.observed_elapsed_minutes, 2),
            "graph_travel_minutes": round(self.graph_travel_minutes, 2),
            "road_distance_km": round(self.road_distance_km, 3),
            "inferred_speed_kph": (
                round(self.inferred_speed_kph, 1)
                if self.inferred_speed_kph is not None
                else None
            ),
            "is_stop": self.is_stop,
            "path": self.path,
        }


@dataclass
class ReconstructedRoute:
    vehicle_uuid: str
    observations: list[dict[str, Any]]
    segments: list[Segment]
    start_camera: str
    end_camera: str
    start_ts: float
    end_ts: float
    total_travel_minutes: float
    total_road_km: float
    stop_count: int
    average_speed_kph: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "vehicle_uuid": self.vehicle_uuid,
            "start_camera": self.start_camera,
            "end_camera": self.end_camera,
            "start_ts": self.start_ts,
            "end_ts": self.end_ts,
            "total_travel_minutes": round(self.total_travel_minutes, 2),
            "total_road_km": round(self.total_road_km, 3),
            "stop_count": self.stop_count,
            "average_speed_kph": (
                round(self.average_speed_kph, 1)
                if self.average_speed_kph is not None
                else None
            ),
            "segments": [s.to_dict() for s in self.segments],
        }


def reconstruct_route(
    vehicle_uuid: str,
    observations: list[dict[str, Any]],
    graph: CameraGraph,
    *,
    stop_threshold_minutes: float = 8.0,
) -> ReconstructedRoute:
    """Reconstruct a journey from time-ordered observations (by `ts`).

    `observations` must all belong to `vehicle_uuid` and be sorted ascending by
    `ts`.
    """
    if not observations:
        return ReconstructedRoute(
            vehicle_uuid=vehicle_uuid,
            observations=[],
            segments=[],
            start_camera="",
            end_camera="",
            start_ts=0.0,
            end_ts=0.0,
            total_travel_minutes=0.0,
            total_road_km=0.0,
            stop_count=0,
            average_speed_kph=None,
        )

    start_cam = str(observations[0]["camera_id"])
    end_cam = str(observations[-1]["camera_id"])
    start_ts = float(observations[0]["ts"])
    end_ts = float(observations[-1]["ts"])

    segments: list[Segment] = []
    total_road = 0.0
    total_travel = 0.0
    stops = 0

    for a, b in zip(observations, observations[1:]):
        cam_a = str(a["camera_id"])
        cam_b = str(b["camera_id"])
        elapsed = (float(b["ts"]) - float(a["ts"])) / 60.0
        sp = graph.shortest_path(cam_a, cam_b) if graph.has(cam_a) and graph.has(cam_b) else None
        path: list[str] = []
        graph_min = 0.0
        road_km = 0.0
        if sp:
            path, graph_min = sp
            for x, y in zip(path, path[1:]):
                e = graph.edge(x, y)
                if e:
                    road_km += e.road_distance_km
        is_stop = elapsed > graph_min + stop_threshold_minutes if sp else False
        inferred_speed = None
        if road_km > 0 and elapsed > 0:
            inferred_speed = road_km / (elapsed / 60.0)
        if is_stop:
            stops += 1
        total_road += road_km
        total_travel += elapsed
        segments.append(
            Segment(
                from_camera=cam_a,
                to_camera=cam_b,
                observed_elapsed_minutes=elapsed,
                graph_travel_minutes=graph_min,
                road_distance_km=road_km,
                inferred_speed_kph=inferred_speed,
                is_stop=is_stop,
                path=path,
            )
        )

    avg_speed = None
    if total_road > 0 and total_travel > 0:
        avg_speed = total_road / (total_travel / 60.0)

    return ReconstructedRoute(
        vehicle_uuid=vehicle_uuid,
        observations=[dict(o) for o in observations],
        segments=segments,
        start_camera=start_cam,
        end_camera=end_cam,
        start_ts=start_ts,
        end_ts=end_ts,
        total_travel_minutes=total_travel,
        total_road_km=total_road,
        stop_count=stops,
        average_speed_kph=avg_speed,
    )


__all__ = ["Segment", "ReconstructedRoute", "reconstruct_route"]
