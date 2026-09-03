"""Phase 4 ANPR & vehicle intelligence Pydantic schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PlateEventRead(BaseModel):
    """One recognized plate read."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    camera_id: uuid.UUID
    camera_name: str | None = None
    location: str | None = None
    plate: str
    normalized_plate: str
    state_code: str | None = None
    rto_code: str | None = None
    ocr_confidence: float
    detection_confidence: float
    vehicle_type: str | None = None
    color: str | None = None
    make: str | None = None
    model: str | None = None
    attribute_confidence: float = 0.0
    backend: str = "sim"
    frame_seq: int = 0
    ts: datetime
    evidence_id: uuid.UUID | None = None


class EvidenceRecordRead(BaseModel):
    """Metadata for a set of evidence artifacts."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    camera_id: uuid.UUID
    plate: str
    normalized_plate: str
    frame_path: str | None = None
    plate_path: str | None = None
    vehicle_path: str | None = None
    ocr_text: str | None = None
    frame_hash: str | None = None
    plate_hash: str | None = None
    vehicle_hash: str | None = None
    detection_confidence: float = 0.0
    ocr_confidence: float = 0.0
    ts: datetime


class BlacklistRead(BaseModel):
    """A blacklist entry."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    plate: str
    normalized_plate: str
    reason: str | None = None
    note: str | None = None
    active: bool = True
    added_at: datetime


class BlacklistCreate(BaseModel):
    plate: str = Field(min_length=3, max_length=32)
    reason: str | None = Field(default=None, max_length=255)
    note: str | None = None


class AnprAlertRead(BaseModel):
    """A Phase 4 ANPR alert."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    camera_id: uuid.UUID
    plate: str
    normalized_plate: str
    rule: str
    class_name: str = "vehicle"
    level: str = "info"
    message: str
    confidence: float | None = None
    count: int = 1
    first_seen_at: datetime
    last_seen_at: datetime
    resolved: bool = False
    resolved_at: datetime | None = None


class FrequentPlate(BaseModel):
    plate: str
    normalized_plate: str
    count: int
    last_seen_at: datetime


class TimelinePoint(BaseModel):
    ts: datetime
    camera_id: uuid.UUID
    camera_name: str | None = None
    plate: str
    normalized_plate: str
    ocr_confidence: float
    evidence_id: uuid.UUID | None = None


class DashboardStats(BaseModel):
    total_plates: int
    unique_plates: int
    blacklisted_count: int
    active_alerts: int
    cameras_active: int
    recent: list[PlateEventRead] = Field(default_factory=list)
    frequent: list[FrequentPlate] = Field(default_factory=list)
    by_color: dict[str, int] = Field(default_factory=dict)
    by_type: dict[str, int] = Field(default_factory=dict)
    by_state: dict[str, int] = Field(default_factory=dict)


class BenchmarkResult(BaseModel):
    total_ms: float
    avg_ms: float
    min_ms: float
    max_ms: float
    per_frame_ms: float
    fps: float
    frames: int
    ok: int
    fail: int
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    precision: float = 0.0
    recall: float = 0.0
    character_accuracy: float = 0.0
    accuracy: dict


class LatencyMetric(BaseModel):
    avg: float
    median: float
    p95: float
    min: float
    max: float


class ConditionSummary(BaseModel):
    samples: int
    true_positive: int
    false_positive: int
    false_negative: int
    precision: float
    recall: float
    f1: float
    false_positive_rate: float
    char_accuracy: float
    word_accuracy: float
    state_accuracy: float
    latency_ms: dict
    latency_detect_ms: dict
    fps: float


class EvalRunRequest(BaseModel):
    size_per_condition: int = Field(default=60, ge=1, le=500)
    width: int = Field(default=640, ge=128, le=1920)
    height: int = Field(default=360, ge=128, le=1080)
    iou_threshold: float = Field(default=0.5, ge=0.0, le=1.0)


class EvalReport(BaseModel):
    overall: ConditionSummary
    per_condition: dict[str, ConditionSummary]
    sample_count: int
    hardware: dict = Field(default_factory=dict)
    diagnostics: dict = Field(default_factory=dict)
    artifacts: dict = Field(default_factory=dict)


class DiagnosisItemSchema(BaseModel):
    name: str
    severity: float
    ok: bool
    detail: str


class DiagnosticSummary(BaseModel):
    ok: bool
    severity: float
    issues: list[DiagnosisItemSchema]
    all: list[DiagnosisItemSchema]
