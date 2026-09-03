"""Field-level validation rules for registry camera records.

Validation is intentionally decoupled from the DB so bulk onboarding can
preview / report errors before anything is committed. Each rule is a pure
function returning a list of :class:`ValidationError` objects tagged with
``field`` and ``code`` for machine + human consumption.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from src.models.registry import CameraCategory, OwnershipType


@dataclass
class ValidationError:
    row: int  # 1-based row number in the source file
    field: str
    code: str
    message: str
    value: Any = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "row": self.row,
            "field": self.field,
            "code": self.code,
            "message": self.message,
            "value": self.value,
        }


# --- individual predicates ---------------------------------------------------


def _check_required(record: dict[str, Any], row: int, field_name: str,
                    errors: list[ValidationError]) -> None:
    value = record.get(field_name)
    if value is None or (isinstance(value, str) and not value.strip()):
        errors.append(ValidationError(row, field_name, "required", f"{field_name} is required", value))


def _coerce_latlon(record: dict[str, Any], row: int, errors: list[ValidationError]) -> None:
    for key, (lo, hi), label in [
        ("latitude", (-90.0, 90.0), "latitude"),
        ("longitude", (-180.0, 180.0), "longitude"),
    ]:
        _latlon_coerce(record, row, key, lo, hi, label, errors)


def _latlon_coerce(record: dict[str, Any], row: int, key: str, lo: float, hi: float,
                   label: str, errors: list[ValidationError]) -> None:
    value = record.get(key)
    if value is None:
        return
    try:
        fv = float(value)
    except (TypeError, ValueError):
        errors.append(ValidationError(row, key, "type", f"{label} must be numeric", value))
        return
    if not (lo <= fv <= hi):
        errors.append(ValidationError(row, key, "range", f"{label} must be within [{lo}, {hi}]", value))
        return
    record[key] = fv


def _check_enum(record: dict[str, Any], row: int, key: str, allowed: set[str],
                errors: list[ValidationError], label: str) -> None:
    value = record.get(key)
    if value is None or (isinstance(value, str) and not value.strip()):
        return
    sv = str(value).strip().lower()
    if sv not in allowed:
        errors.append(
            ValidationError(row, key, "enum",
                            f"{label} must be one of {sorted(allowed)}", value)
        )


def _check_cctv_code(record: dict[str, Any], row: int, errors: list[ValidationError]) -> None:
    code = record.get("cctv_code")
    if code is None or (isinstance(code, str) and not code.strip()):
        errors.append(ValidationError(row, "cctv_code", "required", "cctv_code is required", code))
        return
    sv = str(code).strip().upper()
    if len(sv) < 6 or len(sv) > 40:
        errors.append(ValidationError(row, "cctv_code", "format", "cctv_code must be 6..40 chars", code))
    if any(not (c.isalnum() or c in "-_") for c in sv):
        errors.append(ValidationError(row, "cctv_code", "format", "cctv_code has invalid characters", code))
    record["cctv_code"] = sv


def _check_required_default(record: dict[str, Any], row: int, key: str, default: Any,
                            errors: list[ValidationError]) -> None:
    if record.get(key) is None or record.get(key) == "":
        record[key] = default


# --- rule registry -----------------------------------------------------------

@dataclass
class FieldRule:
    name: str
    fn: Callable[[dict[str, Any], int, list[ValidationError]], None]
    description: str = ""


FIELD_RULES: list[FieldRule] = [
    FieldRule("cctv_code", _check_cctv_code, "Global unique CCTV code, uppercase alnum + '-'/'_'"),
    FieldRule("name", lambda r, row, err: _check_required(r, row, "name", err), "Display name"),
    FieldRule("location", lambda r, row, err: _check_required(r, row, "location", err), "Street / landmark"),
    FieldRule("district_code", lambda r, row, err: _check_required(r, row, "district_code", err), "District code"),
    FieldRule("coords", _coerce_latlon, "Validate + coerce latitude/longitude"),
    FieldRule("category", lambda r, row, err: _check_enum(
        r, row, "category", {c.value for c in CameraCategory}, err, "category"), "Camera category"),
    FieldRule("ownership_type", lambda r, row, err: _check_enum(
        r, row, "ownership_type", {o.value for o in OwnershipType}, err, "ownership_type"),
        "Ownership type"),
    FieldRule("defaults", lambda r, row, err: (
        _check_required_default(r, row, "state_code", "GJ", err),
        _check_required_default(r, row, "category", "city", err),
        _check_required_default(r, row, "ownership_type", "state", err),
    ), "Apply sensible defaults"),
]


def validate_record(record: dict[str, Any], row: int) -> list[ValidationError]:
    """Run every field rule against one normalized record (mutates in place)."""
    errors: list[ValidationError] = []
    for rule in FIELD_RULES:
        rule.fn(record, row, errors)
    return errors


def validate_records(records: list[dict[str, Any]], start_row: int = 2) -> list[ValidationError]:
    errors: list[ValidationError] = []
    for offset, record in enumerate(records):
        errors.extend(validate_record(record, start_row + offset))
    return errors


__all__: list[str] = ["FIELD_RULES", "ValidationError", "FieldRule", "validate_record", "validate_records"]
