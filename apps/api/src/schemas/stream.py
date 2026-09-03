"""Phase 2 streaming schemas."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StreamTestRequest(BaseModel):
    """Optional body for a stream test — reserved for future overrides."""


class StreamTestResult(BaseModel):
    id: UUID
    name: str
    kind: str | None = None
    ok: bool
    message: str
    codec: str | None = None
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    bit_rate: int | None = None
    duration: float | None = None
    format: str | None = None
    decode_ms: float | None = None
    tested_at: datetime


class StreamStartRequest(BaseModel):
    record: bool = False
    record_trigger: str = "manual"
    record_seconds: int = Field(default=0, ge=0)
    motion: bool | None = None


class StreamHealth(BaseModel):
    camera_id: UUID
    name: str | None = None
    state: str
    running: bool
    live: bool = False
    error: str | None = None
    reconnect_count: int = 0
    kind: str | None = None
    started_at: datetime | None = None
    stopped_at: datetime | None = None
    uptime_s: float | None = None
    startup_ms: float | None = None
    latency_ms: float | None = None
    hls_latency_ms: float | None = None
    fps: float | None = None
    bitrate_kbps: float | None = None
    jitter_ms: float | None = None
    last_frame_age_ms: float | None = None
    recording: bool = False
    recording_trigger: str | None = None
    motion_detections: int = 0
    last_motion_score: float | None = None
    publisher: dict[str, Any] = Field(default_factory=dict)


class StreamInfo(StreamHealth):
    """One row of the live wall — stream health + camera identity."""


class StreamMediaUrls(BaseModel):
    camera_id: UUID
    hls_url: str | None = None
    mjpeg_url: str | None = None
    snapshot_url: str | None = None
    whep_url: str | None = None
    expires_in: int
    published_at: datetime


class RecordStartRequest(BaseModel):
    trigger: str = Field(default="manual", pattern="^(manual|schedule|motion)$")
    seconds: int = Field(default=0, ge=0)
    segment_seconds: int | None = Field(default=None, ge=1, le=120)


class RecordStartResponse(BaseModel):
    status: str
    recording_id: UUID | None = None
    camera_id: UUID | None = None
    trigger: str | None = None
    file_path: str | None = None


class RecordingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    camera_id: UUID
    stream_id: UUID | None = None
    started_by: UUID | None = None
    trigger: str
    status: str
    file_path: str
    size_bytes: int | None = None
    duration_seconds: float | None = None
    segment_seconds: int
    started_at: datetime | None = None
    ended_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    camera_name: str | None = None


class StreamCapabilities(BaseModel):
    ffmpeg: dict[str, Any]
    opencv: dict[str, Any]
    publisher: dict[str, Any]
    source_types: list[str]
    profile: dict[str, Any]
    max_cameras: int
    active_streams: int = 0
    recording_dir: str
    recording_max_seconds: int
    motion: dict[str, Any]


class OnvifDiscoverResult(BaseModel):
    mode: str
    devices: list[dict[str, Any]]
    count: int
    reachable: int
    duration_ms: float