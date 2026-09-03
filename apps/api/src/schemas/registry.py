"""Registry & GIS schemas — global CCTV registry, onboarding, GIS API.

These are Pydantic response/request models for the ``/api/v1/registry``
endpoints. They stay DB-light (the engine operates on plain dicts) so the API
contract is clean and matches the pure-Python model.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.models.registry import AccessRole, CameraCategory, OwnershipType
from src.models.registry import RegistryEventType
from src.schemas.common import MessageResponse, Paginated


# --- registry CRUD ----------------------------------------------------------


class RegistryCameraBase(BaseModel):
    cctv_code: str = Field(min_length=6, max_length=40, examples=["IN-GJ-AHM-JCT-000123"])
    name: str = Field(min_length=1, max_length=160)
    location: str = Field(min_length=1, max_length=255)
    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)
    district_code: str = Field(min_length=1, max_length=12)
    state_code: str = Field(default="GJ", max_length=8)
    department_code: str | None = Field(default=None, max_length=20)
    board_code: str | None = Field(default=None, max_length=20)
    category: CameraCategory = CameraCategory.CITY
    ownership_type: OwnershipType = OwnershipType.STATE
    serial_number: str | None = Field(default=None, max_length=80)
    make: str | None = Field(default=None, max_length=60)
    model: str | None = Field(default=None, max_length=80)
    ip_address: str | None = Field(default=None, max_length=45)
    mac_address: str | None = Field(default=None, max_length=20)
    firmware: str | None = Field(default=None, max_length=60)
    coverage_radius_m: float = Field(default=250.0, ge=0.0, le=5000.0)
    gis_layer: str | None = Field(default=None, max_length=32)
    orientation_deg: float | None = Field(default=None, ge=0.0, le=360.0)
    notes: str | None = Field(default=None, max_length=2000)


class RegistryCameraCreate(RegistryCameraBase):
    status: str = "unknown"


class RegistryCameraUpdate(BaseModel):
    cctv_code: str | None = Field(default=None, min_length=6, max_length=40)
    name: str | None = Field(default=None, min_length=1, max_length=160)
    location: str | None = Field(default=None, min_length=1, max_length=255)
    latitude: float | None = Field(default=None, ge=-90.0, le=90.0)
    longitude: float | None = Field(default=None, ge=-180.0, le=180.0)
    district_code: str | None = Field(default=None, min_length=1, max_length=12)
    state_code: str | None = Field(default=None, max_length=8)
    department_code: str | None = Field(default=None, max_length=20)
    board_code: str | None = Field(default=None, max_length=20)
    category: CameraCategory | None = None
    ownership_type: OwnershipType | None = None
    serial_number: str | None = Field(default=None, max_length=80)
    make: str | None = Field(default=None, max_length=60)
    model: str | None = Field(default=None, max_length=80)
    ip_address: str | None = Field(default=None, max_length=45)
    mac_address: str | None = Field(default=None, max_length=20)
    firmware: str | None = Field(default=None, max_length=60)
    coverage_radius_m: float | None = Field(default=None, ge=0.0, le=5000.0)
    gis_layer: str | None = Field(default=None, max_length=32)
    orientation_deg: float | None = Field(default=None, ge=0.0, le=360.0)
    notes: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None


class RegistryCameraRead(RegistryCameraBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    camera_id: UUID
    status: str | None = None
    last_health_score: int | None = None
    uptime_pct: float | None = None
    last_seen_at: datetime | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


# --- bulk onboarding --------------------------------------------------------


class ImportPreview(BaseModel):
    format: str
    total_rows: int
    valid: int
    errored: int
    duplicates: int
    can_commit: bool
    unused_headers: list[str] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)


class ImportCommit(BaseModel):
    committed: int
    expected: int


# --- search ------------------------------------------------------------------


class SearchRequest(BaseModel):
    query: str | None = Field(default=None, max_length=120)
    district_code: str | None = None
    department_code: str | None = None
    board_code: str | None = None
    category: CameraCategory | None = None
    status: str | None = None
    ownership_type: OwnershipType | None = None
    health_level: str | None = None
    gis_layer: str | None = None
    cluster_key: str | None = None
    geo: dict[str, Any] | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=500)
    sort_by: str = Field(default="name", max_length=40)
    sort_dir: str = Field(default="asc", pattern="^(asc|desc)$")


class SearchResult(BaseModel):
    items: list[dict[str, Any]]
    total: int
    page: int
    page_size: int
    pages: int


# --- GIS / coverage ----------------------------------------------------------


class CoverageReport(BaseModel):
    cameras: int
    nominal_area_m2: float
    effective_area_m2: float
    efficiency_pct: float
    overlapping_pairs: list[dict[str, Any]]
    blind_spots: dict[str, Any]
    density: list[dict[str, Any]]
    coverage_radius_m: float


class GapReport(BaseModel):
    camera_count: int
    blind_spot_cells: int
    uncovered_area_m2: float
    low_density_zones: list[dict[str, Any]]
    recommended_placements: list[dict[str, Any]] = Field(default_factory=list)


class CameraHealthScore(BaseModel):
    score: float
    level: str
    status: str
    uptime_pct: float | None = None
    last_seen_at: datetime | None = None


class RegistryOverview(BaseModel):
    total_cameras: int
    active: int
    inactive: int
    districts: int
    last_registered: datetime | None = None


# --- audit -------------------------------------------------------------------


class AuditRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    camera_id: UUID | None = None
    registry_id: UUID | None = None
    cctv_code: str | None = None
    event_type: RegistryEventType
    actor_id: UUID | None = None
    actor_role: str | None = None
    scope: str | None = None
    summary: str
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    created_at: datetime


class RoleMatrix(BaseModel):
    roles: dict[str, list[str]]


class ClusterLayerItem(BaseModel):
    id: str
    count: int
    lat: float
    lng: float
    member_ids: list[str] = Field(default_factory=list)
    radius_m: float = 0.0


class DensityLayerItem(BaseModel):
    lat: float
    lng: float
    count: int


class RoadCoverageResult(BaseModel):
    total_points: int
    covered: int
    coverage_pct: float


__all__: list[str] = [
    "AuditRead",
    "CameraHealthScore",
    "ClusterLayerItem",
    "CoverageReport",
    "DensityLayerItem",
    "GapReport",
    "ImportCommit",
    "ImportPreview",
    "MessageResponse",
    "Paginated",
    "RegistryCameraCreate",
    "RegistryCameraRead",
    "RegistryCameraUpdate",
    "RegistryOverview",
    "RoadCoverageResult",
    "RoleMatrix",
    "SearchRequest",
    "SearchResult",
    "AccessRole",
    "RegistryEventType",
]