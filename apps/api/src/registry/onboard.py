"""Bulk camera onboarding engine — parse, validate, dedup, preview, commit.

Pipeline (pure-Python, unit-testable):

1. ``parse`` — turn raw file content (csv/xlsx/json) into normalised records
   plus the original per-row identity (1-based row number).
2. ``validate`` — run field rules producing per-row ValidationErrors.
3. ``dedupe`` — mark rows that duplicate an existing registry code/serial.
4. ``preview`` — return a dry-run plan with counts + per-row status.
5. ``commit`` — persist the *valid, non-duplicate* rows via an injected
   ``persist`` callback in chunks (80k+ friendly); the endpoint owns the DB
   transaction so a failure rolls back atomically.

Kept free of hard DB imports so the whole engine is testable in the container.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

from src.registry.parsers import PARSERS
from src.registry.validate import ValidationError, validate_record

IMPORT_CHUNK_SIZE = 500
MAX_RECORDS = 200_000


@dataclass
class ParsedRow:
    row: int                  # 1-based row in source file (header not counted)
    record: dict[str, Any]
    errors: list[ValidationError] = field(default_factory=list)
    duplicate: bool = False

    def status(self) -> str:
        if self.duplicate:
            return "duplicate"
        if self.errors:
            return "error"
        return "ok"

    def to_dict(self) -> dict[str, Any]:
        return {
            "row": self.row,
            "status": self.status(),
            "record": self.record if self.status() == "ok" else None,
            "errors": [e.as_dict() for e in self.errors],
        }


@dataclass
class ImportPlan:
    format: str
    total_rows: int
    valid: int
    errored: int
    duplicates: int
    rows: list[ParsedRow] = field(default_factory=list)
    unused_headers: list[str] = field(default_factory=list)
    can_commit: bool = False

    @property
    def valid_records(self) -> list[dict[str, Any]]:
        return [r.record for r in self.rows if r.status() == "ok"]

    def summary(self) -> dict[str, Any]:
        return {
            "format": self.format,
            "total_rows": self.total_rows,
            "valid": self.valid,
            "errored": self.errored,
            "duplicates": self.duplicates,
            "can_commit": self.can_commit,
            "unused_headers": self.unused_headers,
            "rows": [r.to_dict() for r in self.rows],
        }


def parse_raw(format_name: str, content: str | bytes) -> tuple[list[dict[str, Any]], list[str]]:
    """Route to the right parser; raise ValueError on bad format/content."""
    parser = PARSERS.get(format_name.lower())
    if parser is None:
        raise ValueError(f"unsupported import format '{format_name}' (use csv/xlsx/json)")
    if format_name.lower() == "xlsx" and not isinstance(content, bytes):
        content = content.encode("utf-8")
    records, unused = parser(content)
    return records, unused


def build_plan(
    format_name: str,
    content: str | bytes,
    existing_codes: Callable[[Iterable[str]], set[str]],
    *,
    start_row: int = 2,
    max_records: int = MAX_RECORDS,
) -> ImportPlan:
    """Parse + validate + dedupe into an improcessable plan (no DB writes)."""
    records, unused = parse_raw(format_name, content)
    if len(records) > max_records:
        raise ValueError(f"file exceeds {max_records} records")

    # Existing registry codes (de-dup reference).
    candidates = [str(r.get("cctv_code", "")).strip().upper() for r in records if r.get("cctv_code")]
    existing = existing_codes(candidates)

    rows: list[ParsedRow] = []
    seen: set[str] = set()
    valid = errored = duplicates = 0
    for i, record in enumerate(records):
        parsed = ParsedRow(row=start_row + i, record=dict(record))
        # Duplicate check first (vs existing DB + within-file).
        code = str(record.get("cctv_code", "")).strip().upper()
        if code:
            if code in existing or code in seen:
                parsed.duplicate = True
                duplicates += 1
            else:
                seen.add(code)
        if not parsed.duplicate:
            parsed.errors = validate_record(parsed.record, parsed.row)
            if parsed.errors:
                errored += 1
            else:
                valid += 1
        rows.append(parsed)

    can_commit = errored == 0 and valid > 0
    return ImportPlan(
        format=format_name.lower(),
        total_rows=len(records),
        valid=valid,
        errored=errored,
        duplicates=duplicates,
        rows=rows,
        unused_headers=unused,
        can_commit=can_commit,
    )


def commit_plan(
    plan: ImportPlan,
    persist: Callable[[list[dict[str, Any]]], None],
    *,
    chunk_size: int = IMPORT_CHUNK_SIZE,
) -> dict[str, Any]:
    """Persist valid records through ``persist`` in chunks.

    ``persist`` receives a list of valid raw records and must write them. On
    failure the caller (endpoint) owns the DB transaction rollback, so a
    partial chunk never leaves the DB half-written.
    """
    valid_records = plan.valid_records
    committed = 0
    for i in range(0, len(valid_records), chunk_size):
        chunk = valid_records[i:i + chunk_size]
        persist(chunk)
        committed += len(chunk)
    return {"committed": committed, "expected": plan.valid}


def preview_existing_codes(existing: Iterable[str]) -> Callable[[Iterable[str]], set[str]]:
    pool = {str(c).strip().upper() for c in existing if c}
    return lambda _cands: pool


__all__: list[str] = [
    "IMPORT_CHUNK_SIZE", "MAX_RECORDS", "ImportPlan", "ParsedRow", "build_plan",
    "commit_plan", "parse_raw", "preview_existing_codes",
]
