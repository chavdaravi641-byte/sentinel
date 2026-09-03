"""Phase 4 ANPR shared primitives.

Plain dataclasses shared across the ANPR stages (plate detection, rectification,
OCR, vehicle attributes) and the evidence store. Everything is JSON-serialisable
via `to_dict()` so pipeline results can be handed straight to the REST layer,
the WebSocket feed and the Postgres store without ad-hoc glue.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Timings:
    """Split timings for one ANPR processing step (milliseconds)."""

    pre_ms: float = 0.0
    infer_ms: float = 0.0
    post_ms: float = 0.0

    @property
    def total_ms(self) -> float:
        return self.pre_ms + self.infer_ms + self.post_ms

    def to_dict(self) -> dict[str, float]:
        return {
            "pre_ms": round(self.pre_ms, 3),
            "infer_ms": round(self.infer_ms, 3),
            "post_ms": round(self.post_ms, 3),
            "total_ms": round(self.total_ms, 3),
        }


@dataclass
class PlateBox:
    """A detected plate region with a confidence score."""

    confidence: float
    x: float
    y: float
    w: float
    h: float

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2

    def to_dict(self) -> dict[str, Any]:
        return {
            "confidence": round(self.confidence, 4),
            "x": round(self.x, 4),
            "y": round(self.y, 4),
            "w": round(self.w, 4),
            "h": round(self.h, 4),
            "cx": round(self.cx, 4),
            "cy": round(self.cy, 4),
        }


@dataclass
class OcrRead:
    """A single OCR read of a rectified plate region."""

    text: str
    confidence: float
    normalized: str  # uppercased alphanumerics for strict matching

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "confidence": round(self.confidence, 4),
            "normalized": self.normalized,
        }


@dataclass
class VehicleAttribute:
    """Extracted vehicle intelligence attributes."""

    vehicle_type: str = "unknown"  # car / bike / bus / truck / bicycle / other
    color: str = "unknown"
    make: str = "unknown"
    model: str = "unknown"
    confidence: float = 0.0
    color_confidence: float = 0.0
    type_confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "vehicle_type": self.vehicle_type,
            "color": self.color,
            "make": self.make,
            "model": self.model,
            "confidence": round(self.confidence, 4),
            "color_confidence": round(self.color_confidence, 4),
            "type_confidence": round(self.type_confidence, 4),
        }


@dataclass
class PlateEvent:
    """A fully-recognized plate read after the pipeline runs on a frame."""

    camera_id: str
    plate: str
    normalized_plate: str
    ocr_confidence: float
    state_code: str | None  # e.g. "GJ"
    rto_code: str | None  # e.g. "01"
    vehicle: VehicleAttribute
    frame_seq: int
    ts: str  # ISO-8601 UTC
    plate_box: PlateBox
    detection_confidence: float  # plate detector confidence
    backend: str  # sim / onnx
    evidence_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "camera_id": self.camera_id,
            "plate": self.plate,
            "normalized_plate": self.normalized_plate,
            "ocr_confidence": round(self.ocr_confidence, 4),
            "state_code": self.state_code,
            "rto_code": self.rto_code,
            "vehicle": self.vehicle.to_dict(),
            "frame_seq": self.frame_seq,
            "ts": self.ts,
            "plate_box": self.plate_box.to_dict(),
            "detection_confidence": round(self.detection_confidence, 4),
            "backend": self.backend,
            "evidence_id": self.evidence_id,
        }


@dataclass
class EvidenceDoc:
    """Evidence-store artifact (frame / plate crop / vehicle crop)."""

    kind: str  # frame / plate / vehicle
    path: str
    sha256: str
    size_bytes: int
    mime: str = "image/jpeg"

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "path": self.path,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "mime": self.mime,
        }


@dataclass
class AnprResult:
    """Complete output of the ANPR pipeline for one camera frame."""

    camera_id: str
    frame_seq: int
    ts: str
    plates: list[PlateEvent] = field(default_factory=list)
    vehicles: list[VehicleAttribute] = field(default_factory=list)
    timings: Timings = field(default_factory=Timings)
    evidence: list[EvidenceDoc] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "camera_id": self.camera_id,
            "frame_seq": self.frame_seq,
            "ts": self.ts,
            "plates": [p.to_dict() for p in self.plates],
            "vehicles": [v.to_dict() for v in self.vehicles],
            "timings": self.timings.to_dict(),
            "evidence": [e.to_dict() for e in self.evidence],
        }


def parse_state_rto(plate: str) -> tuple[str | None, str | None]:
    """Extract the Indian state-code and RTO-code from a normalized plate.

    Indian plates follow `<state><rto>-<series>-<number>`, e.g. `GJ01AB1234`.
    Returns (state_code, rto_code) or (None, None) when the pattern is absent.
    """
    digits = [c for c in plate if c.isdigit()]
    alpha = [c for c in plate if c.isalpha()]
    if len(digits) >= 2 and len(alpha) >= 1:
        # First two digits after the leading letters are the RTO code.
        state_chars: list[str] = []
        i = 0
        chars = list(plate)
        while i < len(chars) and not chars[i].isdigit():
            state_chars.append(chars[i])
            i += 1
        rto_digits: list[str] = []
        while i < len(chars) and chars[i].isdigit():
            rto_digits.append(chars[i])
            i += 1
        if state_chars and len(rto_digits) >= 2:
            return "".join(state_chars).upper(), rto_digits[0]
        state = "".join(state_chars).upper() or None
        return state, None
    return None, None


# Normalized plate normalization (uppercase, alphanumeric only).
def normalize_plate(text: str) -> str:
    return "".join(ch for ch in text.upper() if ch.isalnum())


__all__ = [
    "Timings",
    "PlateBox",
    "OcrRead",
    "VehicleAttribute",
    "PlateEvent",
    "EvidenceDoc",
    "AnprResult",
    "parse_state_rto",
    "normalize_plate",
]
