"""Incident schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.models.alert import AlertSeverity
from src.models.incident import IncidentStatus, IncidentType


class IncidentBase(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    type: IncidentType
    severity: AlertSeverity = AlertSeverity.MEDIUM
    location: str | None = Field(default=None, max_length=255)
    latitude: float | None = Field(default=None, ge=-90.0, le=90.0)
    longitude: float | None = Field(default=None, ge=-180.0, le=180.0)


class IncidentCreate(IncidentBase):
    status: IncidentStatus = IncidentStatus.OPEN
    camera_id: UUID | None = None
    occurred_at: datetime | None = None


class IncidentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    type: IncidentType | None = None
    severity: AlertSeverity | None = None
    status: IncidentStatus | None = None


class IncidentRead(IncidentBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    camera_id: UUID | None
    camera_name: str | None = None
    status: IncidentStatus
    reported_by: UUID | None
    reported_by_name: str | None = None
    occurred_at: datetime
    created_at: datetime
    updated_at: datetime