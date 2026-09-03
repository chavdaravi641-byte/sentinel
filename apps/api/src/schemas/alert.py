"""Alert schemas."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.models.alert import AlertSeverity, AlertStatus, AlertType


class AlertRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    camera_id: UUID | None
    camera_name: str | None = None
    type: AlertType
    severity: AlertSeverity
    status: AlertStatus
    message: str
    confidence: float | None
    snapshot_url: str | None
    occurred_at: datetime
    created_at: datetime
    updated_at: datetime


class AlertUpdate(BaseModel):
    status: AlertStatus | None = None
    severity: AlertSeverity | None = None


class AlertStats(BaseModel):
    total: int
    new: int
    critical: int
    acknowledged: int
    escalated: int
    resolved: int
    by_type: dict[str, int]
    by_severity: dict[str, int]