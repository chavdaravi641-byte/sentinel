"""Phase 5 — Global Vehicle Identity Engine persistence models.

Additive: does not touch existing Phase 1-4 tables. Stores:
- `VehicleIdentity` — the permanent global UUID for a plate/appearance,
- `CameraGraphEdge` — a weighted directed edge between registered cameras
  (materialised from the geometric abstraction; travel times are computed from
  documented assumptions, never fabricated roads).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class VehicleIdentity(Base, TimestampMixin):
    """A permanent, globally stable vehicle identity."""

    __tablename__ = "anpr_vehicle_identities"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    vehicle_uuid: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, nullable=False
    )
    key: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    plate: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    basis: Mapped[str] = mapped_column(String(24), nullable=False)  # plate | appearance
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    appearance_signature: Mapped[str | None] = mapped_column(String(64), nullable=True)
    embedding_signature: Mapped[str | None] = mapped_column(String(64), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.now, nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.now, index=True, nullable=False
    )
    sighting_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<VehicleIdentity {self.vehicle_uuid} basis={self.basis}>"


class CameraGraphEdge(Base, TimestampMixin):
    """A weighted directed edge in the derived camera graph."""

    __tablename__ = "anpr_camera_graph_edges"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_camera: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cameras.id", ondelete="CASCADE"), index=True
    )
    target_camera: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cameras.id", ondelete="CASCADE"), index=True
    )
    road_distance_km: Mapped[float] = mapped_column(Float, nullable=False)
    travel_time_minutes: Mapped[float] = mapped_column(Float, nullable=False)
    bidirectional: Mapped[bool] = mapped_column(default=True, nullable=False)
    assumptions: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("source_camera", "target_camera", name="uq_graph_edge"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<CameraGraphEdge {self.source_camera}->{self.target_camera}>"


class VehicleSighting(Base, TimestampMixin):
    """A Phase 5 identity-tagged sighting derived from a plate detection."""

    __tablename__ = "anpr_vehicle_sightings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    vehicle_uuid: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    detection_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    camera_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cameras.id", ondelete="CASCADE"), index=True
    )
    plate: Mapped[str] = mapped_column(String(32), nullable=False)
    normalized_plate: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    identity_confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    basis: Mapped[str] = mapped_column(String(24), nullable=False)
    appearance: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.now, index=True, nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<VehicleSighting {self.vehicle_uuid}@{self.camera_id}>"


__all__ = ["VehicleIdentity", "CameraGraphEdge", "VehicleSighting"]
