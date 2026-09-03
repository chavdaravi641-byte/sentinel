"""Phase 6 — AI Investigation Copilot API schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class InvestigateRequest(BaseModel):
    """A single natural-language investigation request."""

    query: str = Field(..., min_length=1, max_length=1000)
    case_number: str | None = None
    limit: int = Field(default=100, ge=1, le=500)


class EvidenceRequest(BaseModel):
    """Build an evidence package for a vehicle."""

    vehicle_uuid: str = Field(..., min_length=1)
    query: str | None = None
    case_number: str | None = None


class ReportRequest(BaseModel):
    """Generate a PDF investigation report from an investigation payload."""

    investigation: dict[str, Any]


class CaseCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None


class NoteCreate(BaseModel):
    body: str = Field(..., min_length=1)


class EvidenceAttach(BaseModel):
    kind: str = Field(..., max_length=32)  # vehicle/plate/timeline/package
    ref: str | None = None
    label: str | None = None
    content: dict[str, Any] | None = None


class BookmarkCreate(BaseModel):
    vehicle_uuid: str = Field(..., min_length=1)
    plate: str | None = None
    reason: str | None = None
