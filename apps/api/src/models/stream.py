"""Live streaming + recording models (Phase 2)."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin

# Stream lifecycle states (kept as plain strings — no PG enum needed).
STREAM_STATE_STOPPED = "stopped"
STREAM_STATE_STARTING = "starting"
STREAM_STATE_RUNNING = "running"
STREAM_STATE_CONNECTING = "connecting"
STREAM_STATE_ERROR = "error"


class Stream(Base, TimestampMixin):
    """One row per camera describing the current/last streaming session."""

    __tablename__ = "streams"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    camera_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cameras.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    state: Mapped[str] = mapped_column(
        String(16), default=STREAM_STATE_STOPPED, index=True, nullable=False
    )
    mode: Mapped[str] = mapped_column(String(32), default="balanced", nullable=False)
    source: Mapped[str] = mapped_column(String(512), nullable=False)
    error: Mapped[str | None] = mapped_column(String(512), nullable=True)
    reconnect_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_health_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Stream camera_id={self.camera_id} state={self.state!r}>"


class Recording(Base, TimestampMixin):
    """Persisted metadata for a recording run."""

    __tablename__ = "recordings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    camera_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cameras.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    stream_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("streams.id", ondelete="CASCADE"), nullable=True
    )
    started_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    trigger: Mapped[str] = mapped_column(
        String(16), default="manual", nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(16), default="recording", index=True, nullable=False
    )
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    segment_seconds: Mapped[int] = mapped_column(
        Integer, default=15, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Recording id={self.id} camera_id={self.camera_id} status={self.status!r}>"


__all__: list[str] = [
    "Stream",
    "Recording",
    "STREAM_STATE_STOPPED",
    "STREAM_STATE_STARTING",
    "STREAM_STATE_RUNNING",
    "STREAM_STATE_CONNECTING",
    "STREAM_STATE_ERROR",
]