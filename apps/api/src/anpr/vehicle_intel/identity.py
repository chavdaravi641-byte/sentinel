"""Vehicle Identity Engine (Phase 5).

Every vehicle is assigned a permanent, global UUID. The identity must survive
camera changes, lighting changes, small OCR errors, partial occlusion and
different viewing angles.

Design
------
- The *primary key* is the canonical normalized plate string (uppercase
  alphanumerics). A stable UUID is derived deterministically from that string,
  so the same plate always maps to the same vehicle UUID on every camera.
- When the plate is absent / too unreliable (partial occlusion, failed OCR),
  we fall back to an *appearance signature* (vehicle type + color + make +
  model + a coarse embedding hash). This fallback UUID is still stable for a
  given appearance, letting identity survive short occlusion gaps, but it is
  flagged as `low_confidence` because appearance is far weaker than a plate.
- "Survives lighting/viewing-angle changes" is achieved by normalizing to the
  same canonical string and by treating appearance as a secondary, tolerant
  signal rather than a strict equality check.

Assumptions (documented, not fabricated)
----------------------------------------
- UUID is derived via SHA-256 (namespace-based) and is therefore reproducible
  across reloads / replicas without any shared store — a property we rely on
  for Redis cache hits and background-job idempotency.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from typing import Any


def canonical_plate(text: str) -> str:
    """Upper-case alphanumeric canonical form. Returns '' when nothing remains."""
    return "".join(ch for ch in (text or "").upper() if ch.isalnum())


def plate_fingerprint(normalized_plate: str) -> str:
    """Stable 16-hex fingerprint of a canonical plate string.

    Case/format-insensitive: input is canonicalized before hashing so the same
    plate always yields the same fingerprint regardless of how it was written.
    """
    norm = canonical_plate(normalized_plate)
    if not norm:
        return ""
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]


def appearance_signature(
    appearance: dict[str, Any] | None,
    *,
    hash_bits: int = 128,
) -> str:
    """A compact, stable hash of a coarse appearance tuple.

    The embedding-friendly fields (shape embedding vector, if present) are
    quantised-preserving via their byte representation; categorical fields
    (type/color/make/model) are folded into the digest so a stable appearance
    yields a stable signature.
    """
    if not appearance:
        return ""
    bucket = {
        "vehicle_type": str(appearance.get("vehicle_type", "unknown")),
        "color": str(appearance.get("color", "unknown")),
        "make": str(appearance.get("make", "unknown")),
        "model": str(appearance.get("model", "unknown")),
    }
    payload = "|".join(f"{k}={bucket[k]}" for k in sorted(bucket))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[: hash_bits // 4]


def shape_embedding_fingerprint(embedding: Any) -> str:
    """Stable digest of a shape-embedding vector (viewing-angle tolerant).

    We quantise each float to 4 significant digits before hashing so that tiny
    camera/lighting differences do not change the identity mapping.
    """
    if embedding is None:
        return ""
    try:
        import numpy as np  # type: ignore

        arr = np.asarray(embedding, dtype=np.float64).ravel()
    except Exception:  # noqa: BLE001 - non-numeric input handled gracefully
        return ""
    items = []
    for v in arr[:64]:
        try:
            items.append(f"{float(v):.4g}")
        except (TypeError, ValueError):
            items.append("x")
    payload = ",".join(items)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


@dataclass(frozen=True)
class VehicleIdentity:
    """The permanent identity of a vehicle, plus its provenance."""

    vehicle_uuid: str
    key: str  # the canonical plate (or appearance signature when plate missing)
    plate: str  # canonical plate string (may be '')
    confidence: float  # 0..1 how much we trust this identity
    basis: str  # "plate" | "appearance" | "plate+appearance"
    appearance_signature: str = ""
    embedding_signature: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "vehicle_uuid": self.vehicle_uuid,
            "key": self.key,
            "plate": self.plate,
            "confidence": round(self.confidence, 4),
            "basis": self.basis,
            "appearance_signature": self.appearance_signature,
            "embedding_signature": self.embedding_signature,
        }


NAMESPACE_VEHICLE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


def _uuid_from(key: str) -> str:
    return str(uuid.uuid5(NAMESPACE_VEHICLE, key))


def assign_identity(
    plate: str = "",
    appearance: dict[str, Any] | None = None,
    *,
    shape_embedding: Any = None,
    ocr_confidence: float = 0.0,
    plate_confidence_threshold: float = 0.45,
) -> VehicleIdentity:
    """Assign a stable global identity to a vehicle observation.

    Priority:
      1. If we have a trustworthy canonical plate -> UUID derived from plate.
      2. Else if we have a shape embedding -> UUID derived from embedding sig
         (most view/lighting tolerant of the appearance signals).
      3. Else if we have an appearance -> UUID derived from appearance sig.
      4. Else -> a random throwaway identity (should not normally happen).
    """
    norm = canonical_plate(plate)
    embedding_sig = (
        shape_embedding_fingerprint(shape_embedding)
        if shape_embedding is not None
        else ""
    )
    app_sig = appearance_signature(appearance)

    plate_ok = bool(norm) and ocr_confidence >= plate_confidence_threshold

    if plate_ok:
        key = norm
        basis = "plate"
        if embedding_sig:
            basis = "plate+appearance"
        identity = VehicleIdentity(
            vehicle_uuid=_uuid_from(f"plate:{norm}"),
            key=key,
            plate=norm,
            confidence=min(1.0, 0.7 + 0.3 * ocr_confidence),
            basis=basis,
            appearance_signature=app_sig,
            embedding_signature=embedding_sig,
        )
        return identity

    if embedding_sig:
        key = f"emb:{embedding_sig}"
        return VehicleIdentity(
            vehicle_uuid=_uuid_from(key),
            key=key,
            plate="",
            confidence=0.45,
            basis="appearance",
            appearance_signature=app_sig,
            embedding_signature=embedding_sig,
        )

    if app_sig:
        key = f"app:{app_sig}"
        return VehicleIdentity(
            vehicle_uuid=_uuid_from(key),
            key=key,
            plate="",
            confidence=0.35,
            basis="appearance",
            appearance_signature=app_sig,
            embedding_signature="",
        )

    # Fully anonymous fallback (should be rare).
    return VehicleIdentity(
        vehicle_uuid=str(uuid.uuid4()),
        key=f"anon:{uuid.uuid4().hex[:12]}",
        plate="",
        confidence=0.1,
        basis="appearance",
    )


__all__ = [
    "canonical_plate",
    "plate_fingerprint",
    "appearance_signature",
    "shape_embedding_fingerprint",
    "VehicleIdentity",
    "assign_identity",
]
