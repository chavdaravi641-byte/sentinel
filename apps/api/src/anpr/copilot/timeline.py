"""Phase 6 Copilot — Investigation Timeline.

Chronological, interactive reconstruction of a vehicle's movements. Reuses the
Phase 5 evidence-timeline + route-reconstruction primitives and enriches every
event with:

* district (derived from location/camera),
* GPS coordinates,
* OCR / detection confidence,
* association reason (why each sighting is linked to the vehicle),
* inferred speed from the reconstructed route where calculable.

All data comes from stored detections; nothing is fabricated.
"""

from __future__ import annotations

from typing import Any

from src.anpr.copilot.analysis import district_of
from src.anpr.copilot.evidence import EvidenceBuilder
from src.anpr.vehicle_intel.graph import CameraGraph
from src.anpr.vehicle_intel.reconstruction import reconstruct_route
from src.anpr.vehicle_intel.timeline import build_evidence_timeline


class InvestigationTimeline:
    """Build an enriched investigation timeline for a vehicle."""

    def __init__(self, graph: CameraGraph, db=None, *, evidence_root: str | None = None) -> None:
        self._graph = graph
        self._evidence = EvidenceBuilder(db, evidence_root=evidence_root) if db else None

    async def build(
        self,
        observations: list[dict[str, Any]],
        *,
        vehicle_uuid: str | None = None,
        association_reasons: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        obs = sorted(observations, key=lambda o: float(o.get("ts", 0)))
        if not obs:
            return {"vehicle_uuid": vehicle_uuid or "", "entries": [], "journeys": [],
                    "data_unavailable": "No observations to build a timeline from."}

        base = build_evidence_timeline(obs, self._graph)
        route = reconstruct_route(vehicle_uuid or "", obs, self._graph)

        # Speed lookup per (from_camera -> to_camera) segment for label enrichment.
        speed_map: dict[tuple[str, str], Any] = {}
        for seg in route.segments:
            speed_map[(seg.from_camera, seg.to_camera)] = seg.inferred_speed_kph

        entries = []
        for i, e in enumerate(base["entries"]):
            prev = entries[-1] if entries else None
            prev_cam = prev["camera_id"] if prev else None
            speed = speed_map.get((prev_cam, e["camera_id"])) if prev_cam else None
            reason = self._reason_for(obs, e["index"], association_reasons)
            entries.append(
                {
                    **e,
                    "district": district_of(e.get("location"), e.get("camera_name")),
                    "latitude": obs[e["index"]].get("latitude"),
                    "longitude": obs[e["index"]].get("longitude"),
                    "inferred_speed_kph": speed,
                    "association_reason": reason,
                }
            )

        return {
            "vehicle_uuid": base["vehicle_uuid"],
            "observation_count": base["observation_count"],
            "journey_count": base["journey_count"],
            "journeys": base["clusters"],
            "entries": entries,
            "route_summary": route.to_dict(),
            "explanations": self._explanations(entries),
        }

    @staticmethod
    def _reason_for(obs, index: int, association_reasons) -> str:
        if association_reasons:
            for r in association_reasons:
                if r.get("index") == index or r.get("detection_id") == obs[index].get("detection_id"):
                    return r.get("reason", "")
        return "Consecutive sighting of the same global identity on the route."

    @staticmethod
    def _explanations(entries) -> list[dict[str, Any]]:
        out = []
        for e in entries:
            bits = []
            if e.get("has_plate"):
                bits.append(f"linked by canonical plate '{e.get('plate')}'")
            else:
                bits.append("linked by appearance signature (no trusted plate)")
            if e.get("district"):
                bits.append(f"in {e['district']}")
            out.append(
                {"index": e["index"], "ts": e["iso_ts"], "camera": e["camera_name"],
                 "explanation": "; ".join(bits)}
            )
        return out


__all__ = ["InvestigationTimeline"]
