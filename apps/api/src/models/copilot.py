"""Phase 6 Copilot — case workspace + audit log persistence models.

Additive tables (do not touch Phase 1-5). Persists investigation cases, their
evidence, notes, bookmarked vehicles, and a full audit trail of every
investigation action so the Copilot is accountable and exportable.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class InvestigationCase(Base, TimestampMixin):
    """A police investigation case / workspace."""

    __tablename__ = "copilot_cases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_number: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="open", index=True, nullable=False)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now, nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CaseEvidence(Base, TimestampMixin):
    """A piece of evidence added to a case (vehicle / plate / timeline / note)."""

    __tablename__ = "copilot_case_evidence"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("copilot_cases.id", ondelete="CASCADE"), index=True, nullable=False
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)  # vehicle/plate/timeline/package
    ref: Mapped[str | None] = mapped_column(String(128), nullable=True)  # plate / vehicle_uuid
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    added_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now, nullable=False)


class CaseNote(Base, TimestampMixin):
    """A free-text analyst note on a case."""

    __tablename__ = "copilot_case_notes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("copilot_cases.id", ondelete="CASCADE"), index=True, nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    author_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)


class CaseBookmark(Base, TimestampMixin):
    """A vehicle bookmarked for follow-up in a case."""

    __tablename__ = "copilot_case_bookmarks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("copilot_cases.id", ondelete="CASCADE"), index=True, nullable=False
    )
    vehicle_uuid: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    plate: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)


class InvestigationLog(Base, TimestampMixin):
    """Audit trail — every investigation action is logged."""

    __tablename__ = "copilot_audit_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    officer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True, nullable=True)
    officer_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    action: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    query: Mapped[str | None] = mapped_column(Text, nullable=True)
    case_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("copilot_cases.id", ondelete="SET NULL"), index=True, nullable=True
    )
    evidence_accessed: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


__all__ = [
    "InvestigationCase",
    "CaseEvidence",
    "CaseNote",
    "CaseBookmark",
    "InvestigationLog",
]
