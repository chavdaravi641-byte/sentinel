"""Predictive interception corridor response schemas (killer feature #2)."""

from __future__ import annotations

from pydantic import BaseModel


class InterceptionNodeRead(BaseModel):
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
    corridor_path: list[str]


class InterceptionVectorRead(BaseModel):
    plate: str
    trigger_camera: str
    assumed_speed_kph: float
    radius_km: float
    observed_ts: str
    basis: str
    confidence: float
    recommendation: str
    nodes: list[InterceptionNodeRead]


class InterceptionRequest(BaseModel):
    plate: str
    trigger_camera: str
    observed_ts: float | None = None
    speed_kph: float = 35.0
    radius_km: float = 15.0
