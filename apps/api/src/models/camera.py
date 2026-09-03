"""CCTV camera model."""

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Enum, Float, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin


class CameraStatus(str, enum.Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"
    UNKNOWN = "unknown"


class Camera(Base, TimestampMixin):
    __tablename__ = "cameras"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(160), index=True, nullable=False)
    rtsp_url: Mapped[str] = mapped_column(String(512), nullable=False)
    location: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[CameraStatus] = mapped_column(
        Enum(
            CameraStatus,
            name="camera_status",
            values_callable=lambda e: [m.value for m in e],
        ),
        default=CameraStatus.UNKNOWN,
        index=True,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    alerts = relationship("Alert", back_populates="camera", cascade="all, delete-orphan")
    incidents = relationship(
        "Incident", back_populates="camera", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover - used for debugging
        return f"<Camera id={self.id} name={self.name!r} status={self.status.value}>"


__all__: list[str] = ["Camera", "CameraStatus", "Any"]