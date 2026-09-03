"""Cluster API request/response schemas (Part 8)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- POST /cluster/register -------------------------------------------------
class NodeRegisterIn(BaseModel):
    node_id: str = Field(..., min_length=1, max_length=128)
    hostname: str = ""
    region: str = "Gujarat"
    district: str | None = None
    capabilities: dict[str, Any] = Field(default_factory=dict)
    gpu_count: int = 0
    cpu_cores: int = 0
    ram_gb: int = 0
    version: str = ""
    synthetic: bool = False


class NodeOut(BaseModel):
    node_id: str
    hostname: str
    region: str
    district: str | None
    capabilities: dict[str, Any]
    gpu_count: int
    cpu_cores: int
    ram_gb: int
    version: str
    status: str
    last_heartbeat_at: str | None
    heartbeat_seq: int
    cpu_util: float
    gpu_util: float | None
    mem_util: float
    active_cameras: int
    registered_at: str | None
    synthetic: bool


# --- POST /cluster/heartbeat ------------------------------------------------
class HeartbeatIn(BaseModel):
    node_id: str = Field(..., min_length=1, max_length=128)
    seq: int = 0
    cpu_util: float = 0.0
    gpu_util: float | None = None
    mem_util: float = 0.0
    active_cameras: int = 0
    synthetic: bool = False


class HeartbeatOut(BaseModel):
    node_id: str
    seq: int
    status: str
    ack: bool = True
    failover_pending: int = 0


# --- Camera ownership --------------------------------------------------------
class CameraLeaseOut(BaseModel):
    camera_id: str
    owner_node_id: str | None
    lease_expiry: str | None
    priority: int
    failover_state: str
    ownership_version: int
    last_change_at: str | None
    synthetic: bool


class CameraAssignIn(BaseModel):
    camera_id: UUID
    owner_node_id: str | None = None  # None = let the scheduler choose
    priority: int = 0


class CameraRenewIn(BaseModel):
    camera_id: UUID
    node_id: str
    version: int | None = None


class OwnershipChangeOut(BaseModel):
    camera_id: str | None
    from_node: str | None
    to_node: str | None
    reason: str
    ownership_version: int
    at: str | None
    synthetic: bool


# --- Health / dashboard (Part 7) --------------------------------------------
class HealthSummaryOut(BaseModel):
    node_total: int
    by_status: dict[str, int]
    owned_cameras_total: int
    capacity: dict[str, int]
    ownership_changes_total: int


class DashboardOut(BaseModel):
    nodes: list[NodeOut]
    heartbeats: list[dict[str, Any]]
    owned_cameras: list[CameraLeaseOut]
    capacity: dict[str, Any]
    health: HealthSummaryOut


class FailoverOut(BaseModel):
    transferred: list[OwnershipChangeOut]
