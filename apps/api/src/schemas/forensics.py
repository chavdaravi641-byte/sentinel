"""Forensic dossier response schemas (grand-finale killer feature #1)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, model_serializer, model_validator


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
    schema_ref: str
    generated_at: str
    integrity_sha256: str
    source: str
    watchlist: Any = None
    summary: DossierSummaryRead
    sightings: list[DossierSightingRead] = []

    @model_validator(mode="before")
    @classmethod
    def _accept_public_schema_name(cls, value: Any) -> Any:
        if isinstance(value, dict) and "schema" in value and "schema_ref" not in value:
            value = dict(value)
            value["schema_ref"] = value.pop("schema")
        return value

    @model_serializer(mode="plain")
    def _serialize_public_schema_name(self) -> dict[str, Any]:
        payload = self.__dict__.copy()
        payload["schema"] = payload.pop("schema_ref")
        return payload


class DossierVerifyRead(BaseModel):
    plate: str
    integrity_sha256: str
    valid: bool
