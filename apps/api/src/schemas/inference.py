"""Phase 3 inference REST schemas."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AiModelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    version: str
    backend: str
    status: str
    generation: int
    accelerator: str | None = None
    device: str | None = None
    providers: list[str] | None = None
    weights_path: str | None = None
    classes: list[str] | None = None
    error: str | None = None
    loaded_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class InferenceRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    camera_id: UUID
    model_name: str
    model_version: str
    model_generation: int
    frame_seq: int
    ts: datetime
    width: int
    height: int
    pre_ms: float
    infer_ms: float
    post_ms: float
    total_ms: float
    batch_size: int
    detections: int
    fps: float
    accelerator: str | None = None
    backend: str | None = None


class DetectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    run_id: UUID
    camera_id: UUID
    model_name: str
    class_name: str
    confidence: float
    track_id: int | None = None
    x: float
    y: float
    w: float
    h: float
    cx: float
    cy: float
    frame_seq: int
    ts: datetime


class InferenceAlertRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    camera_id: UUID
    model_name: str
    rule: str
    class_name: str
    level: str
    message: str
    confidence: float | None = None
    count: int
    first_seen_at: datetime
    last_seen_at: datetime
    resolved: bool
    resolved_at: datetime | None = None
    created_at: datetime


class InferenceConfig(BaseModel):
    enabled: bool
    model: str
    weights_dir: str
    accel_mode: str
    plugins: list[dict[str, Any]]
    device: dict[str, Any]
    batch: dict[str, Any]
    confidence: float
    max_fps_per_camera: float
    store_enabled: bool
    alert_enabled: bool
    processes_active: int


class BenchmarkRequest(BaseModel):
    iterations: int = Field(default=50, ge=5, le=2000)
    image_width: int = Field(default=1280, ge=64, le=4096)
    image_height: int = Field(default=720, ge=64, le=4096)
    batch_size: int = Field(default=1, ge=1, le=16)


class BenchmarkResult(BaseModel):
    model: str
    backend: str
    accelerator: str
    device_name: str
    providers: list[str]
    image_width: int
    image_height: int
    batch_size: int
    iterations: int
    frames_processed: int
    pre_ms_avg: float
    infer_ms_avg: float
    post_ms_avg: float
    total_ms_avg: float
    fps: float
    objects_per_second: float
    objects_per_frame_avg: float
    run_ms: float
    ts: datetime
    report_file: str | None = None