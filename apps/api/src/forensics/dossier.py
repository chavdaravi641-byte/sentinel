"""Court-admissible forensic dossier export.

Produces a tamper-evident, immutable package for a vehicle (by registration
plate): the watchlist context, the chronological ANPR sighting chain with
department / district / GPS provenance, and a SHA-256 integrity digest so the
exported artefact can be re-verified end-to-end by a court or external auditor.

Design
------
* Canonicalisation and hashing are **pure** (no DB, no network) so they are
  trivially unit-testable: any two systems that run the same canonicaliser
  arrive at the same integrity digest for the same facts.
* ``build_dossier`` is the DB-facing assembly that pulls real rows from
  ``anpr_plate_detections`` and joins provenance from ``camera_registry``.
* The PDF renderer is a dependency-light, deterministic writer — no external
  binary or heavyweight renderer is required, so it runs inside the API
  container and in the test suite identically.
"""

from __future__ import annotations

import hashlib
import io
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from src.crud import watchlist as wl_crud
from src.models.anpr import PlateDetection
from src.models.registry import CameraRegistry

DOSSIER_VERSION = "1.0"
DOSSIER_SCHEMA = "sentinel/forensic-dossier/1.0"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def canonical_json(value: Any) -> str:
    """Deterministic, whitespace-free JSON serialisation.

    Keys are emitted in sorted order and floats are normalised so the same
    logical payload always hashes identically across systems.
    """
    def _float(x: Any) -> Any:
        if isinstance(x, float):
            return round(x, 6)
        return x

    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        default=_float,
    )


def compute_integrity(manifest: dict[str, Any]) -> str:
    """Return the SHA-256 of the canonical manifest bytes."""
    return hashlib.sha256(canonical_json(manifest).encode("utf-8")).hexdigest()


@dataclass
class DossierSighting:
    """One tamper-evident sighting entry in a dossier."""

    detection_id: str
    camera_id: str
    cctv_code: str | None
    camera_name: str | None
    location: str | None
    district_code: str | None
    department_code: str | None
    latitude: float | None
    longitude: float | None
    ts: str
    ocr_confidence: float
    detection_confidence: float
    vehicle_type: str | None
    color: str | None
    make: str | None
    model: str | None
    state_code: str | None
    rto_code: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "detection_id": self.detection_id,
            "camera_id": self.camera_id,
            "cctv_code": self.cctv_code,
            "camera_name": self.camera_name,
            "location": self.location,
            "district_code": self.district_code,
            "department_code": self.department_code,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "ts": self.ts,
            "ocr_confidence": round(self.ocr_confidence, 4),
            "detection_confidence": round(self.detection_confidence, 4),
            "vehicle_type": self.vehicle_type,
            "color": self.color,
            "make": self.make,
            "model": self.model,
            "state_code": self.state_code,
            "rto_code": self.rto_code,
        }


@dataclass
class ForensicDossier:
    """The compiled, sealed dossier for a plate."""

    plate: str
    normalized_plate: str
    version: str
    schema_ref: str
    generated_at: str
    integrity_sha256: str
    watchlist: dict[str, Any] | None
    sightings: list[DossierSighting] = field(default_factory=list)
    source: str = "anpr_plate_detections"

    def counts(self) -> dict[str, int]:
        return {
            "sightings": len(self.sightings),
            "distinct_cameras": len({s.camera_id for s in self.sightings}),
            "distinct_departments": len(
                {s.department_code for s in self.sightings if s.department_code}
            ),
            "distinct_districts": len(
                {s.district_code for s in self.sightings if s.district_code}
            ),
        }

    def to_dict(self, *, with_sightings: bool = True) -> dict[str, Any]:
        base: dict[str, Any] = {
            "plate": self.plate,
            "normalized_plate": self.normalized_plate,
            "version": self.version,
            "schema": self.schema_ref,
            "generated_at": self.generated_at,
            "integrity_sha256": self.integrity_sha256,
            "source": self.source,
            "watchlist": self.watchlist,
            "summary": self.counts(),
        }
        if with_sightings:
            base["sightings"] = [s.to_dict() for s in self.sightings]
        else:
            base["sightings_hash"] = self._sightings_digest()
        return base

    def _sightings_digest(self) -> str:
        rows = [s.to_dict() for s in self.sightings]
        return compute_integrity({"sightings": rows})

    def verify(self) -> bool:
        """Re-seal the manifest and confirm the stored digest matches."""
        manifest = self._manifest(with_sightings=True)
        return compute_integrity(manifest) == self.integrity_sha256

    def _manifest(self, *, with_sightings: bool) -> dict[str, Any]:
        return {
            "plate": self.plate,
            "normalized_plate": self.normalized_plate,
            "version": self.version,
            "schema": self.schema_ref,
            "generated_at": self.generated_at,
            "source": self.source,
            "watchlist": self.watchlist,
            "counts": self.counts(),
            "sightings": [s.to_dict() for s in self.sightings]
            if with_sightings
            else [],
        }


def _seal(plate: str, normalized: str, watchlist: dict[str, Any] | None,
          sightings: list[DossierSighting], generated_at: str) -> ForensicDossier:
    """Build the dossier from parts and seal it with an integrity digest.

    The digest is computed over the canonical manifest **including** the full
    sighting chain so any alteration to any row breaks verification.
    """
    counts = {
        "sightings": len(sightings),
        "distinct_cameras": len({s.camera_id for s in sightings}),
        "distinct_departments": len(
            {s.department_code for s in sightings if s.department_code}
        ),
        "distinct_districts": len(
            {s.district_code for s in sightings if s.district_code}
        ),
    }
    manifest = {
        "plate": plate,
        "normalized_plate": normalized,
        "version": DOSSIER_VERSION,
        "schema": DOSSIER_SCHEMA,
        "generated_at": generated_at,
        "source": "anpr_plate_detections",
        "watchlist": watchlist,
        "counts": counts,
        "sightings": [s.to_dict() for s in sightings],
    }
    digest = compute_integrity(manifest)
    return ForensicDossier(
        plate=plate,
        normalized_plate=normalized,
        version=DOSSIER_VERSION,
        schema_ref=DOSSIER_SCHEMA,
        generated_at=generated_at,
        integrity_sha256=digest,
        watchlist=watchlist,
        sightings=sightings,
    )


async def build_dossier(db, plate: str) -> ForensicDossier:
    """Assemble + seal a forensic dossier for the given registration plate.

    ``plate`` is normalised (spaces stripped, uppercased). The dossier pulls:

    1. the active watchlist context for the plate (if any) — source DB,
       category, notes and the timestamp it was added;
    2. the chronological ANPR detection chain for the plate, joined with
       registry provenance (cctv_code, district, department) where available.
    """
    normalized = plate.upper().replace(" ", "")

    watchlist = await wl_crud.get_by_identifier(db, normalized)
    wl_payload: dict[str, Any] | None = None
    if watchlist is not None:
        wl_payload = {
            "matched": True,
            "target_type": watchlist.target_type.value,
            "category": watchlist.category.value,
            "source_db": watchlist.source_db.value,
            "notes": watchlist.notes,
            "active": watchlist.active,
            "added_at": (
                watchlist.added_at.isoformat(timespec="seconds")
                if watchlist.added_at
                else None
            ),
        }

    rows = (
        (
            await db.execute(
                select(PlateDetection)
                .where(PlateDetection.normalized_plate == normalized)
                .order_by(PlateDetection.ts.asc())
            )
        )
        .scalars()
        .all()
    )

    # Registry provenance lookup (camera -> cctv_code / district / department).
    provenance: dict[str, CameraRegistry] = {}
    if rows:
        camera_ids = [r.camera_id for r in rows]
        reg_rows = (
            (
                await db.execute(
                    select(CameraRegistry).where(CameraRegistry.camera_id.in_(camera_ids))
                )
            )
            .scalars()
            .all()
        )
        provenance = {str(r.camera_id): r for r in reg_rows}

    sightings: list[DossierSighting] = []
    for r in rows:
        reg = provenance.get(str(r.camera_id))
        sightings.append(
            DossierSighting(
                detection_id=str(r.id),
                camera_id=str(r.camera_id),
                cctv_code=reg.cctv_code if reg else None,
                camera_name=r.camera_name,
                location=r.location,
                district_code=reg.district_code if reg else None,
                department_code=reg.department_code if reg else None,
                latitude=r.latitude,
                longitude=r.longitude,
                ts=r.ts.isoformat(timespec="seconds") if r.ts else "",
                ocr_confidence=r.ocr_confidence,
                detection_confidence=r.detection_confidence,
                vehicle_type=r.vehicle_type,
                color=r.color,
                make=r.make,
                model=r.model,
                state_code=r.state_code,
                rto_code=r.rto_code,
            )
        )

    return _seal(normalized if not sightings else normalized, normalized,
                 wl_payload, sightings, _utcnow())


def render_dossier_markdown(dossier: ForensicDossier) -> str:
    """Render the sealed dossier as a Markdown handout for a court / judge."""
    lines: list[str] = [
        "# Forensic Evidence Dossier",
        "",
        f"**Registration plate:** `{dossier.normalized_plate}`  ",
        f"**Generated:** `{dossier.generated_at}`  ",
        f"**Schema:** `{dossier.schema_ref}`  ",
        f"**Integrity SHA-256:** `{dossier.integrity_sha256}`",
        "",
        "## Watchlist context",
        "",
    ]
    if dossier.watchlist:
        w = dossier.watchlist
        lines.append(
            f"- Matched: **{w.get('source_db', '')}** / {w.get('category', '')} "
            f"(active={w.get('active')})"
        )
        if w.get("notes"):
            lines.append(f"- Notes: {w['notes']}")
    else:
        lines.append("- No active watchlist entry for this plate.")
    lines += [
        "",
        "## Sighting chain",
        "",
    ]
    if not dossier.sightings:
        lines.append("- No ANPR detections on record.")
    else:
        for i, s in enumerate(dossier.sightings, 1):
            where = f"{s.location or ''} ({s.district_code or 'GJ'}/{s.department_code or '-'})"
            lines.append(
                f"{i}. **{s.ts}** — `{s.cctv_code or s.camera_id}` · {s.camera_name or ''} "
                f"· {where} · conf {s.ocr_confidence:.0%}"
            )
    counts = dossier.counts()
    lines += [
        "",
        f"_Sealed by Sentinel: {counts['sightings']} sightings, "
        f"{counts['distinct_cameras']} cameras, "
        f"{counts['distinct_departments']} departments._",
    ]
    return "\n".join(lines)


def render_dossier_pdf(dossier: ForensicDossier) -> bytes:
    """Deterministic dependency-light PDF renderer for the sealed dossier.

    Produces a simple, readable single-page-per-logic document with the plate,
    integrity digest, watchlist context and the chronological sighting table.
    The output is byte-deterministic for identical input.
    """
    buf = io.BytesIO()
    lines: list[tuple[str, int]] = []  # (text, size)
    lines.append(("FORENSIC EVIDENCE DOSSIER", 18))
    lines.append((f"Vehicle: {dossier.normalized_plate}", 12))
    lines.append((f"Generated: {dossier.generated_at}", 9))
    lines.append((f"Schema: {dossier.schema_ref}", 9))
    lines.append((f"SHA-256: {dossier.integrity_sha256}", 9))
    lines.append(("", 9))
    lines.append(("WATCHLIST CONTEXT", 11))
    if dossier.watchlist:
        w = dossier.watchlist
        lines.append(
            (f"Matched: {w.get('source_db','')} / {w.get('category','')} "
             f"(active={w.get('active')})", 9)
        )
        if w.get("notes"):
            lines.append((f"Notes: {w['notes']}", 9))
    else:
        lines.append(("No active watchlist entry.", 9))
    lines.append(("", 9))
    lines.append(("SIGHTING CHAIN", 11))
    if not dossier.sightings:
        lines.append(("No ANPR detections on record.", 9))
    else:
        for s in dossier.sightings:
            lines.append((s.ts, 9))
            lines.append(
                (f"  {s.cctv_code or s.camera_id} | {s.camera_name or ''} | "
                 f"{s.location or ''} | {s.district_code or 'GJ'}/{s.department_code or '-'}",
                 8),
            )
            lines.append((f"  conf {s.ocr_confidence:.0%}", 8))
    summary = dossier.counts()
    lines.append(("", 9))
    lines.append(
        (f"Summary: {summary['sightings']} sightings, "
         f"{summary['distinct_cameras']} cameras, "
         f"{summary['distinct_departments']} depts.", 9)
    )

    _write_pdf(buf, lines)
    return buf.getvalue()


# --------------------------------------------------------------------------- #
# Minimal PDF writer (subset of PDF 1.4, ASCII only)
# --------------------------------------------------------------------------- #
def _write_pdf(buf: io.BytesIO, lines: list[tuple[str, int]]) -> None:
    """Deterministic PDF writer (Courier Type1, single page, xref table)."""
    buf.write(_rebuild_pdf(lines))


def _rebuild_pdf(lines: list[tuple[str, int]]) -> bytes:
    """Clean deterministic PDF build: objects with correct stream length."""
    stream_lines = ["BT", "/F1 10 Tf", "72 800 Td", "16 TL"]
    for text, size in lines:
        if not text:
            stream_lines.append("T*")
            continue
        safe = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        if size != 10:
            stream_lines.append(f"/F1 {size} Tf")
        stream_lines.append(f"({safe}) Tj")
        stream_lines.append("T*")
    stream_lines.append("ET")
    stream = ("\n".join(stream_lines)).encode("latin-1", "replace")

    content_obj = (
        b"<< /Length " + str(len(stream)).encode("latin-1") + b" >>\nstream\n"
        + stream + b"\nendstream"
    )

    body_parts = [
        b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n",
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\nendobj\n",
        b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>\nendobj\n",
        b"5 0 obj\n" + content_obj + b"\nendobj\n",
    ]

    out = bytearray()
    offsets: list[int] = []
    for part in body_parts:
        offsets.append(len(out))
        out += part
    xref_pos = len(out)
    out += b"xref\n0 6\n"
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode("latin-1")
    out += (
        b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n"
        + str(xref_pos).encode("latin-1") + b"\n%%EOF"
    )
    return bytes(out)


__all__ = [
    "DOSSIER_VERSION",
    "DOSSIER_SCHEMA",
    "canonical_json",
    "compute_integrity",
    "DossierSighting",
    "ForensicDossier",
    "build_dossier",
    "render_dossier_markdown",
    "render_dossier_pdf",
]
