"""Dashboard aggregate schemas."""

from uuid import UUID

from pydantic import BaseModel

from src.models.camera import CameraStatus
from src.schemas.alert import AlertRead
from src.schemas.incident import IncidentRead


class CameraGeoPoint(BaseModel):
    id: UUID
    name: str
    latitude: float
    longitude: float
    status: CameraStatus


class SystemHealth(BaseModel):
    api: str
    database: str
    redis: str
    version: str


class DashboardSummary(BaseModel):
    cameras: dict[str, int]
    alerts: dict[str, int]
    recent_alerts: list[AlertRead]
    camera_geo: list[CameraGeoPoint]
    system: SystemHealth
    latest_incident: IncidentRead | None = None
    detections_today: int = 0