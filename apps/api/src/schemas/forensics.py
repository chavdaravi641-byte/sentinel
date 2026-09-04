"""Forensic dossier response schemas (grand-finale killer feature #1)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class DossierWatchlistRead(BaseModel):
    matched: bool
    target_type: str | None = None
    category: str | None = None
    source_db: str | None = None
    notes: str | None = None
    active: bool | None = None
    added_at: str | None = None


class DossierSightingRead(BaseModel):
    detection_id: str
    camera_id: str
    cctv_code: str | None = None
    camera_name: str | None = None
    location: str | None = None
    district_code: str | None = None
    department_code: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    ts: str
    ocr_confidence: float
    detection_confidence: float
    vehicle_type: str | None = None
    color: str | None = None
    make: str | None = None
    model: str | None = None
    state_code: str | None = None
    rto_code: str | None = None


class DossierSummaryRead(BaseModel):
    sightings: int
    distinct_cameras: int
    distinct_departments: int
    distinct_districts: int


class DossierRead(BaseModel):
    plate: str
    normalized_plate: str
    version: str
    schema: str
    generated_at: str
    integrity_sha256: str
    source: str
    watchlist: Any = None
    summary: DossierSummaryRead
    sightings: list[DossierSightingRead] = []


class DossierVerifyRead(BaseModel):
    plate: str
    integrity_sha256: str
    valid: bool
