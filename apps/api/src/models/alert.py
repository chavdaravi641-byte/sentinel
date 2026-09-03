"""AI / analytics alert model produced against a camera feed."""

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin


class AlertType(str, enum.Enum):
    MOTION = "motion"
    INTRUSION = "intrusion"
    LOITERING = "loitering"
    CROWD = "crowd"
    ABANDONED_OBJECT = "abandoned_object"
    LICENSE_PLATE = "license_plate"
    SUSPICIOUS_BEHAVIOR = "suspicious_behavior"
    UNKNOWN = "unknown"


class AlertSeverity(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class AlertStatus(str, enum.Enum):
    NEW = "new"
    ACKNOWLEDGED = "acknowledged"
    ESCALATED = "escalated"
    RESOLVED = "resolved"


class Alert(Base, TimestampMixin):
    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    camera_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cameras.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    type: Mapped[AlertType] = mapped_column(
        Enum(AlertType, name="alert_type", values_callable=lambda e: [m.value for m in e]),
        index=True,
        nullable=False,
    )
    severity: Mapped[AlertSeverity] = mapped_column(
        Enum(
            AlertSeverity,
            name="alert_severity",
            values_callable=lambda e: [m.value for m in e],
        ),
        index=True,
        nullable=False,
    )
    status: Mapped[AlertStatus] = mapped_column(
        Enum(
            AlertStatus,
            name="alert_status",
            values_callable=lambda e: [m.value for m in e],
        ),
        default=AlertStatus.NEW,
        index=True,
        nullable=False,
    )
    message: Mapped[str] = mapped_column(String(512), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    snapshot_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )

    camera = relationship("Camera", back_populates="alerts")

    def __repr__(self) -> str:  # pragma: no cover - used for debugging
        return f"<Alert id={self.id} type={self.type.value} severity={self.severity.value}>"


__all__: list[str] = [
    "Alert",
    "AlertType",
    "AlertSeverity",
    "AlertStatus",
    "Any",
    "Integer",
]