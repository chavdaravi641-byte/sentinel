"""Pydantic schemas for the federation API.

These define the wire contract for the resolver endpoints. The 24 canonical
camera registry fields map 1:1 to :class:`src.federation.models.Camera`.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.federation.models import CameraState, DepartmentKind, StreamProtocol, Vendor


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Camera registry ----------------------------------------------------------
class DepartmentBase(OrmModel):
    code: str
    name: str
    kind: DepartmentKind = DepartmentKind.POLICE
    parent_id: UUID | None = None
    description: str | None = None


class CameraBase(OrmModel):
    camera_id: str
    name: str
    vendor: Vendor = Vendor.ONVIF
    model: str | None = None
    firmware: str | None = None
    region: str = "Gujarat"
    district: str | None = None
    taluka: str | None = None
    locality: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    host: str | None = None
    port: int | None = None
    rtsp_url: str | None = None
    stream_uri: str | None = None
    protocols: list[StreamProtocol] = Field(default_factory=list)
    channel: int | None = None
    department_id: UUID
    camera_type: str = "fixed"
    public_accessible: bool = False
    classification: int = 2
    state: CameraState = CameraState.REGISTERED
    metadata_: dict[str, Any] = Field(default_factory=dict)


class CameraCreate(BaseModel):
    camera_id: str
    name: str
    vendor: Vendor = Vendor.ONVIF
    model: str | None = None
    firmware: str | None = None
    region: str = "Gujarat"
    district: str | None = None
    taluka: str | None = None
    locality: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    host: str | None = None
    port: int | None = None
    rtsp_url: str | None = None
    stream_uri: str | None = None
    protocols: list[StreamProtocol] = Field(default_factory=list)
    channel: int | None = None
    department_id: UUID
    camera_type: str = "fixed"
    public_accessible: bool = False
    classification: int = 2
    state: CameraState = CameraState.REGISTERED
    metadata_: dict[str, Any] = Field(default_factory=dict)


class CameraOut(CameraBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    department: DepartmentBase | None = None


# --- Streams ------------------------------------------------------------------
class StreamStartRequest(BaseModel):
    protocol: StreamProtocol = StreamProtocol.HLS
    quality: str = "auto"


class StreamInfo(BaseModel):
    camera_id: UUID
    protocol: StreamProtocol
    url: str | None = None
    session_id: str | None = None
    active: bool
    view_count: int


# --- Health --------------------------------------------------------------------
class HealthOut(BaseModel):
    camera_id: UUID
    status: str
    latency_ms: int | None = None
    bitrate_kbps: int | None = None
    signal: int | None = None
    detail: dict[str, Any] = Field(default_factory=dict)
    checked_at: datetime | None = None


# --- Retention ------------------------------------------------------------------
class RetentionPolicyIn(BaseModel):
    department_id: UUID | None = None
    camera_id: UUID | None = None
    retention_days: int = 30
    storage_bucket: str = "default"
    archive_with_evidence: bool = False


# --- Event bus --------------------------------------------------------------------
class EventMessage(BaseModel):
    type: str
    source: str
    subject_type: str
    subject_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    at: datetime  # ISO-8601 timestamp from producer


# --- DB connectors ------------------------------------------------------------------
class GovtQuery(BaseModel):
    lookup_type: str  # e.g. registration, dl, complaint, fingerprints, vote
    identifier: str


class GovtResponse(BaseModel):
    source: str
    matched: bool
    status: str = "ok"
    data: dict[str, Any] = Field(default_factory=dict)
    message: str | None = None


# --- Security ------------------------------------------------------------------------
class WebhookCreate(BaseModel):
    name: str
    url: str
    events: list[str] = Field(default_factory=list)
    active: bool = True


class AuditOut(OrmModel):
    id: UUID
    at: datetime
    actor: str
    actor_department: str | None = None
    action: str
    resource_type: str
    resource_id: str | None = None
    source_ip: str | None = None
    outcome: str
    detail: dict[str, Any] = Field(default_factory=dict)


# --- Dashboard ---------------------------------------------------------------------------
class DashboardOut(BaseModel):
    total_cameras: int
    connected: int
    offline: int
    degraded: int
    departments: int
    active_streams: int
    total_views: int
    storage_used_gb: float
    storage_capacity_gb: float
    retention_days_min: int
    retention_days_max: int
