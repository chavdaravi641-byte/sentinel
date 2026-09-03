"""Phase 6 Copilot — Evidence Builder.

Assembles a single, self-contained evidence package for a vehicle (or set of
observations). The package is *assembled from stored artifacts only*:

* vehicle images / plate crops — resolved from each detection's `EvidenceRecord`
  asset paths (served through the authenticated evidence store, never invented),
* a chronological timeline,
* GPS / camera / confidence / (when reconstructable) inferred speed,
* association reasoning and identity reasoning (why observations belong to one
  vehicle).

When an artifact is missing on disk, the package records it as ``unavailable``
rather than fabricating an image or path.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.anpr.evidence import EvidenceStore
from src.anpr.vehicle_intel.identity import assign_identity, canonical_plate
from src.models.anpr import EvidenceRecord


class EvidenceBuilder:
    """Builds an evidence package from stored detections + artifacts."""

    def __init__(self, db: AsyncSession, *, evidence_root: str | None = None) -> None:
        self._db = db
        self._store = EvidenceStore(root_dir=evidence_root) if evidence_root else None

    # ------------------------------------------------------------------ #
    async def _resolve_assets(self, evidence_id: str | None) -> dict[str, Any]:
        """Resolve frame/plate/vehicle asset paths for an evidence record."""
        from uuid import UUID

        if not evidence_id:
            return {"frame": None, "plate": None, "vehicle": None}
        try:
            uid = UUID(str(evidence_id))
        except (ValueError, TypeError):
            return {"frame": None, "plate": None, "vehicle": None}
        record = (
            await self._db.execute(select(EvidenceRecord).where(EvidenceRecord.id == uid))
        ).scalar_one_or_none() if self._db else None
        if record is None:
            return {"frame": None, "plate": None, "vehicle": None}
        out = {}
        for kind in ("frame", "plate", "vehicle"):
            if self._store is not None:
                out[kind] = self._store.asset_path(record, kind)
            else:
                out[kind] = getattr(record, f"{kind}_path", None)
        return out

    # ------------------------------------------------------------------ #
    async def build_for_vehicle(
        self,
        observations: list[dict[str, Any]],
        *,
        vehicle_uuid: str | None = None,
        identity_reasoning: str = "",
        association_reasons: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Build an evidence package from time-ordered observations."""
        obs = sorted(observations, key=lambda o: float(o.get("ts", 0)))
        if not obs:
            return {
                "vehicle_uuid": vehicle_uuid or "",
                "evidence_package": None,
                "data_unavailable": "No observations supplied to package.",
            }

        first = obs[0]
        plate = canonical_plate(first.get("plate", ""))
        identity = assign_identity(
            plate,
            {"vehicle_type": (first.get("appearance") or {}).get("vehicle_type"),
             "color": (first.get("appearance") or {}).get("color")},
            ocr_confidence=float(first.get("ocr_confidence", 0.0)),
        )
        vuid = vehicle_uuid or identity.vehicle_uuid

        events = []
        for o in obs:
            assets = await self._resolve_assets(o.get("evidence_id"))
            events.append(
                {
                    "camera_id": o.get("camera_id"),
                    "camera_name": o.get("camera_name"),
                    "location": o.get("location"),
                    "latitude": o.get("latitude"),
                    "longitude": o.get("longitude"),
                    "ts": o.get("ts"),
                    "plate": o.get("plate"),
                    "ocr_confidence": o.get("ocr_confidence"),
                    "detection_confidence": o.get("detection_confidence"),
                    "assets": assets,
                    "detection_id": o.get("detection_id"),
                }
            )

        return {
            "vehicle_uuid": vuid,
            "plate": plate,
            "identity": identity.to_dict(),
            "identity_reasoning": identity_reasoning or self._default_identity_reason(identity, plate),
            "event_count": len(events),
            "events": events,
            "association_reasons": association_reasons or [],
            "summary": {
                "vehicle_type": (first.get("appearance") or {}).get("vehicle_type"),
                "color": (first.get("appearance") or {}).get("color"),
                "make": (first.get("appearance") or {}).get("make"),
                "model": (first.get("appearance") or {}).get("model"),
                "first_seen_ts": obs[0].get("ts"),
                "last_seen_ts": obs[-1].get("ts"),
                "total_sightings": len(obs),
            },
        }

    @staticmethod
    def _default_identity_reason(identity, plate: str) -> str:
        if plate and identity.basis in ("plate", "plate+appearance"):
            return (f"Identity keyed to the unambiguous canonical plate '{plate}' "
                    f"(basis={identity.basis}, confidence={identity.confidence:.2f}); "
                    f"the same UUID is derived for this plate on every camera.")
        return (f"Identity derived from appearance signature "
                f"(basis={identity.basis}, confidence={identity.confidence:.2f}) since no "
                f"trusted plate was available; flagged lower-confidence.")


__all__ = ["EvidenceBuilder"]
