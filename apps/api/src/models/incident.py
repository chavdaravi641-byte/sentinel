"""Reported law-enforcement incident model."""

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.alert import AlertSeverity
from src.models.base import Base, TimestampMixin


class IncidentType(str, enum.Enum):
    THEFT = "theft"
    ASSAULT = "assault"
    TRAFFIC = "traffic"
    FIRE = "fire"
    MISSING_PERSON = "missing_person"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    VANDALISM = "vandalism"
    OTHER = "other"


class IncidentStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    CLOSED = "closed"


class Incident(Base, TimestampMixin):
    __tablename__ = "incidents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    camera_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cameras.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    type: Mapped[IncidentType] = mapped_column(
        Enum(
            IncidentType,
            name="incident_type",
            values_callable=lambda e: [m.value for m in e],
        ),
        index=True,
        nullable=False,
    )
    severity: Mapped[AlertSeverity] = mapped_column(
        Enum(
            AlertSeverity,
            name="alert_severity",
            values_callable=lambda e: [m.value for m in e],
        ),
        default=AlertSeverity.MEDIUM,
        index=True,
        nullable=False,
    )
    status: Mapped[IncidentStatus] = mapped_column(
        Enum(
            IncidentStatus,
            name="incident_status",
            values_callable=lambda e: [m.value for m in e],
        ),
        default=IncidentStatus.OPEN,
        index=True,
        nullable=False,
    )
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    reported_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )

    camera = relationship("Camera", back_populates="incidents")

    def __repr__(self) -> str:  # pragma: no cover - used for debugging
        return f"<Incident id={self.id} title={self.title!r} status={self.status.value}>"


__all__: list[str] = ["Incident", "IncidentType", "IncidentStatus", "Any"]