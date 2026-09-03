"""Phase 5 — Global Vehicle Identity Engine Pydantic schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class IdentityRead(BaseModel):
    vehicle_uuid: str
    key: str
    plate: str
    confidence: float
    basis: str
    appearance_signature: str = ""
    embedding_signature: str = ""


class GraphEdgeRead(BaseModel):
    source: str
    target: str
    road_distance_km: float
    travel_time_minutes: float
    bidirectional: bool = True


class GraphNodeRead(BaseModel):
    camera_id: str
    camera_name: str
    location: str
    latitude: float
    longitude: float


class GraphRead(BaseModel):
    assumptions: list[str]
    config: dict[str, Any]
    nodes: list[GraphNodeRead]
    edges: list[GraphEdgeRead]


class AssociationRead(BaseModel):
    is_match: bool
    score: float
    confidence: float
    plate_similarity: float
    appearance_similarity: float
    embedding_similarity: float
    travel_similarity: float
    travel_minutes: float
    matched_on: str


class AssociationRequest(BaseModel):
    obs_a: dict[str, Any]
    obs_b: dict[str, Any]
    match_threshold: float = Field(default=0.55, ge=0.0, le=1.0)


class SegmentRead(BaseModel):
    from_camera: str
    to_camera: str
    observed_elapsed_minutes: float
    graph_travel_minutes: float
    road_distance_km: float
    inferred_speed_kph: float | None = None
    is_stop: bool
    path: list[str]


class RouteRead(BaseModel):
    vehicle_uuid: str
    start_camera: str
    end_camera: str
    start_ts: float = 0.0
    end_ts: float = 0.0
    total_travel_minutes: float = 0.0
    total_road_km: float = 0.0
    stop_count: int = 0
    average_speed_kph: float | None = None
    segments: list[SegmentRead] = []


class RouteRequest(BaseModel):
    vehicle_uuid: str
    observations: list[dict[str, Any]]


class PredictionItem(BaseModel):
    camera_id: str
    confidence: float
    basis: str


class PredictionRead(BaseModel):
    current_camera: str
    predictions: list[PredictionItem]
    total_confidence: float
    basis: str
    history_length: int


class PredictionRequest(BaseModel):
    current_camera: str
    history: list[str]


class TimelineRead(BaseModel):
    vehicle_uuid: str
    observation_count: int
    journey_count: int
    clusters: list[dict[str, Any]]
    entries: list[dict[str, Any]]


class TimelineRequest(BaseModel):
    sightings: list[dict[str, Any]]
    gap_minutes: float = Field(default=20.0, ge=0.0)


class SearchRequest(BaseModel):
    plate: str = ""
    vehicle_type: str = ""
    color: str = ""
    location: str = ""
    near_lat: float | None = None
    near_lng: float | None = None
    radius_km: float = Field(default=10.0, ge=0.0)
    min_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    start_ts: float | None = None
    end_ts: float | None = None
    limit: int = Field(default=100, ge=1, le=500)


class Phase5MetricsRead(BaseModel):
    association_precision: float
    association_recall: float
    association_f1: float
    route_accuracy: float
    travel_time_mae_minutes: float
    travel_time_mape_pct: float
    prediction_hit_rate: float
    prediction_total_confidence: float
    identity_stability: float
    avg_latency_ms: float
    num_trials: int


# --------------------------------------------------------------------------- #
# Phase 5.1 — Multi-Modal Identity
# --------------------------------------------------------------------------- #
class CandidateAttribute(BaseModel):
    vehicle_uuid: str
    canonical_plate: str = ""
    plate_confidence: float = 0.0
    color: str = ""
    vehicle_type: str = ""
    make: str = ""
    model: str = ""
    aspect_ratio: float | None = None
    wheelbase: float | None = None
    roofline: str = ""
    embedding: Any = None
    history: list[list[Any]] = []  # [[camera_id, ts], ...]
    sighting_count: int = 0


class FusedIdentityRequest(BaseModel):
    probe: dict[str, Any]
    candidates: list[CandidateAttribute]
    match_threshold: float = Field(default=0.40, ge=0.0, le=1.0)


class FusedIdentityRead(BaseModel):
    identity_uuid: str
    identity_confidence: float
    identity_reasoning: list[str]
    feature_contributions: dict[str, float]
    ambiguity_score: float
    basis: str
    matched_candidate_uuid: str | None = None
    raw_score: float = 0.0
    runner_up_score: float = 0.0
    plate_weight_used: float = 0.0
