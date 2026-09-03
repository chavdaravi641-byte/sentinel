"""Phase 3 AI inference schema models.

All tables are additive — Phase 1/2 tables are untouched. Bounding boxes are
stored normalized to the source frame (0..1) so downstream tools never need to
know the ingest resolution; pixel dimensions live on the owning run row.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin

# Model runtime statuses (plain strings — no PG enum, matching Phase 1/2 style).
AI_MODEL_STATUS_LOADING = "loading"
AI_MODEL_STATUS_LOADED = "loaded"
AI_MODEL_STATUS_UNLOADED = "unloaded"
AI_MODEL_STATUS_ERROR = "error"


class AiModel(Base, TimestampMixin):
    """Registry snapshot for a registered inference plugin/model."""

    __tablename__ = "ai_models"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    version: Mapped[str] = mapped_column(String(32), default="0.0.0", nullable=False)
    backend: Mapped[str] = mapped_column(String(32), default="sim", nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), default=AI_MODEL_STATUS_UNLOADED, index=True, nullable=False
    )
    generation: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    accelerator: Mapped[str | None] = mapped_column(String(16), nullable=True)
    device: Mapped[str | None] = mapped_column(String(128), nullable=True)
    providers: Mapped[list | None] = mapped_column(JSON, nullable=True)
    weights_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    classes: Mapped[list | None] = mapped_column(JSON, nullable=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    error: Mapped[str | None] = mapped_column(String(512), nullable=True)
    loaded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<AiModel name={self.name} status={self.status!r} generation={self.generation}>"


class InferenceRun(Base, TimestampMixin):
    """One analyzed frame — per-frame timing, throughput and detection counts."""

    __tablename__ = "inference_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    camera_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cameras.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    model_name: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    model_version: Mapped[str] = mapped_column(String(32), default="0.0.0", nullable=False)
    model_generation: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    frame_seq: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.now, index=True, nullable=False
    )
    width: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    height: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pre_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    infer_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    post_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    batch_size: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    detections: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    fps: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    accelerator: Mapped[str | None] = mapped_column(String(16), nullable=True)
    backend: Mapped[str | None] = mapped_column(String(32), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<InferenceRun camera={self.camera_id} seq={self.frame_seq}>"


class Detection(Base, TimestampMixin):
    """A single object detection (per bounding box)."""

    __tablename__ = "detections"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inference_runs.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    camera_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cameras.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    model_name: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    class_name: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    track_id: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)
    # Normalized bounding box (0..1 relative to the source frame).
    x: Mapped[float] = mapped_column(Float, nullable=False)  # top-left x
    y: Mapped[float] = mapped_column(Float, nullable=False)  # top-left y
    w: Mapped[float] = mapped_column(Float, nullable=False)
    h: Mapped[float] = mapped_column(Float, nullable=False)
    cx: Mapped[float] = mapped_column(Float, nullable=False)
    cy: Mapped[float] = mapped_column(Float, nullable=False)
    frame_seq: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.now, index=True, nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Detection {self.class_name} conf={self.confidence:.2f} track={self.track_id}>"


class InferenceAlert(Base, TimestampMixin):
    """A rule-based alert raised from detections (Phase 3 alert engine)."""

    __tablename__ = "inference_alerts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    camera_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cameras.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    model_name: Mapped[str] = mapped_column(String(64), default="yolov12", nullable=False)
    rule: Mapped[str] = mapped_column(String(32), nullable=False)
    class_name: Mapped[str] = mapped_column(String(32), nullable=False)
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
        return f"<InferenceAlert camera={self.camera_id} rule={self.rule!r}>"


__all__: list[str] = [
    "AiModel",
    "InferenceRun",
    "Detection",
    "InferenceAlert",
    "AI_MODEL_STATUS_LOADING",
    "AI_MODEL_STATUS_LOADED",
    "AI_MODEL_STATUS_UNLOADED",
    "AI_MODEL_STATUS_ERROR",
]