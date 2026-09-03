"""Phase 4 ANPR & vehicle intelligence persistence models.

All tables are additive — Phase 1/2/3 tables are untouched. Plate regions are
stored normalized (0..1) relative to the source frame; attribute fields
(vehicle_type / color / make / model / state_code / rto_code) are plain columns
so they participate in indexed searches.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class PlateDetection(Base, TimestampMixin):
    """One recognized plate event (per plate crop)."""

    __tablename__ = "anpr_plate_detections"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    camera_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cameras.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    camera_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)

    plate: Mapped[str] = mapped_column(String(32), nullable=False)
    normalized_plate: Mapped[str] = mapped_column(
        String(32), index=True, nullable=False
    )
    state_code: Mapped[str | None] = mapped_column(String(8), index=True, nullable=True)
    rto_code: Mapped[str | None] = mapped_column(String(8), nullable=True)

    ocr_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    detection_confidence: Mapped[float] = mapped_column(Float, nullable=False)

    # Vehicle attributes.
    vehicle_type: Mapped[str | None] = mapped_column(
        String(24), index=True, nullable=True
    )
    color: Mapped[str | None] = mapped_column(String(24), index=True, nullable=True)
    make: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    attribute_confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Normalized plate region.
    x: Mapped[float] = mapped_column(Float, nullable=False)
    y: Mapped[float] = mapped_column(Float, nullable=False)
    w: Mapped[float] = mapped_column(Float, nullable=False)
    h: Mapped[float] = mapped_column(Float, nullable=False)

    # Pipeline provenance.
    backend: Mapped[str] = mapped_column(String(16), default="sim", nullable=False)
    frame_seq: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.now, index=True, nullable=False
    )
    evidence_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<PlateDetection {self.normalized_plate} conf={self.ocr_confidence:.2f}>"


class EvidenceRecord(Base, TimestampMixin):
    """Metadata for a set of evidence artifacts produced by one plate event."""

    __tablename__ = "anpr_evidence"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    camera_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cameras.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    plate: Mapped[str] = mapped_column(String(32), nullable=False)
    normalized_plate: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    frame_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    plate_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    vehicle_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    frame_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    plate_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    vehicle_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detection_confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    ocr_confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.now, index=True, nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<EvidenceRecord {self.plate}>"


class BlacklistEntry(Base, TimestampMixin):
    """A plate placed on the blacklist."""

    __tablename__ = "anpr_blacklist"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    plate: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    normalized_plate: Mapped[str] = mapped_column(
        String(32), unique=True, index=True, nullable=False
    )
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True, nullable=False)
    added_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.now, nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<BlacklistEntry {self.plate} active={self.active}>"


class AnprAlert(Base, TimestampMixin):
    """A phase-4 ANPR alert (blacklist / low-confidence / multi-camera / reappear)."""

    __tablename__ = "anpr_alerts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    camera_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cameras.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    plate: Mapped[str] = mapped_column(String(32), nullable=False)
    normalized_plate: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    rule: Mapped[str] = mapped_column(String(32), nullable=False)
    class_name: Mapped[str] = mapped_column(String(24), default="vehicle", nullable=False)
    level: Mapped[str] = mapped_column(String(16), default="info", nullable=False)
    message: Mapped[str] = mapped_column(String(512), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.now, nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.now, index=True, nullable=False
    )
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, index=True, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<AnprAlert rule={self.rule!r} plate={self.plate}>"


__all__ = [
    "PlateDetection",
    "EvidenceRecord",
    "BlacklistEntry",
    "AnprAlert",
]
