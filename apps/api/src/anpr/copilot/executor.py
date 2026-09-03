"""Phase 6 Copilot — plan executor over stored detections.

Converts a validated `SearchPlan` into concrete results *traceable to stored
`PlateDetection` rows* by:

1. Loading observations from the DB (reusing the Phase 5 identity mapping so
   every detection maps to a stable `vehicle_uuid`).
2. Applying the plan's filters (plate / attributes / district / camera / time).
3. Running the analytic intents (multi-district / night visitors / related).

Privacy & honesty rules (enforced here, not just documented):
* If no stored detection matches a criterion, the executor returns an explicit
  ``data_unavailable`` note with the criterion named — it never invents evidence.
* Every returned vehicle cites the exact stored detections (camera + ts + plate +
  confidence) that support it.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.anpr.copilot.analysis import (
    district_of,
    multi_district_vehicles,
    related_vehicles,
    repeated_night_visitors,
)
from src.anpr.copilot.plan import (
    INTENT_EVIDENCE,
    INTENT_FIND_VEHICLES,
    INTENT_MULTI_DISTRICT,
    INTENT_RELATED_VEHICLES,
    INTENT_REPEATED_NIGHT,
    INTENT_TIMELINE,
    INTENT_UNKNOWN,
    INTENT_VEHICLES_NEAR,
    SearchPlan,
)
from src.anpr.vehicle_intel.identity import assign_identity, canonical_plate
from src.anpr.vehicle_intel.graph import haversine_km
from src.models.anpr import PlateDetection


class CopilotExecutor:
    """Executes search plans against the detection store."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ------------------------------------------------------------------ #
    async def load_detections(
        self,
        *,
        limit: int = 4000,
        window: dict[str, Any] | None = None,
        camera: str | None = None,
        district: str | None = None,
    ) -> list[dict[str, Any]]:
        """Load recent detections as observation dicts, filtered by the plan
        where possible (SQL-level) to keep the working set small."""
        stmt = select(PlateDetection).order_by(PlateDetection.ts.desc()).limit(limit)
        if window:
            start = window.get("start")
            end = window.get("end")
            if start:
                stmt = stmt.where(PlateDetection.ts >= dt.datetime.fromisoformat(start))
            if end:
                stmt = stmt.where(PlateDetection.ts <= dt.datetime.fromisoformat(end))
        if district:
            stmt = stmt.where(
                PlateDetection.location.ilike(f"%{district}%")
                | PlateDetection.camera_name.ilike(f"%{district}%")
            )
        if camera and camera.upper() not in ("", "NONE"):
            stmt = stmt.where(PlateDetection.camera_name.ilike(f"%{camera}%"))
        rows = (await self._db.execute(stmt)).scalars().all()

        sightings: list[dict[str, Any]] = []
        for r in rows:
            identity = assign_identity(
                r.plate,
                {"vehicle_type": r.vehicle_type, "color": r.color,
                 "make": r.make, "model": r.model},
                ocr_confidence=r.ocr_confidence,
            )
            sightings.append(
                {
                    "detection_id": str(r.id),
                    "vehicle_uuid": identity.vehicle_uuid,
                    "camera_id": str(r.camera_id),
                    "camera_name": r.camera_name or str(r.camera_id),
                    "location": r.location or "",
                    "latitude": r.latitude,
                    "longitude": r.longitude,
                    "plate": r.plate or "",
                    "normalized_plate": r.normalized_plate or "",
                    "appearance": {
                        "vehicle_type": r.vehicle_type,
                        "color": r.color, "make": r.make, "model": r.model,
                    },
                    "ocr_confidence": r.ocr_confidence,
                    "detection_confidence": r.detection_confidence,
                    "ts": r.ts.timestamp() if r.ts else 0,
                    "evidence_id": str(r.evidence_id) if r.evidence_id else None,
                }
            )
        return sightings

    # ------------------------------------------------------------------ #
    def _apply_composite_filters(
        self, sightings: list[dict[str, Any]], plan: SearchPlan
    ) -> list[dict[str, Any]]:
        """Apply filters not (fully) done at SQL level: plate, attributes,
        district, near-geo, time, min-confidence."""
        f = plan.filters
        out = []
        qplate = canonical_plate(f.plate or "")
        qtype = (f.vehicle_type or "").strip().lower()
        qcolor = (f.color or "").strip().lower()
        qmake = (f.make or "").strip().lower()
        qmodel = (f.model or "").strip().lower()
        qstate = (f.state or "").upper()
        qdistrict = (f.district or "").strip().lower()
        window_start = f.window.start
        window_end = f.window.end

        for o in sightings:
            plate = canonical_plate(o.get("normalized_plate") or o.get("plate", ""))
            app = o.get("appearance") or {}
            otype = (app.get("vehicle_type") or "").strip().lower()
            ocolor = (app.get("color") or "").strip().lower()
            omake = (app.get("make") or "").strip().lower()
            omodel = (app.get("model") or "").strip().lower()
            ts = float(o.get("ts", 0))

            if window_start is not None and ts < window_start.timestamp():
                continue
            if window_end is not None and ts > window_end.timestamp():
                continue
            if qplate and qplate not in plate:
                continue
            if qtype and otype != qtype:
                continue
            if qcolor and ocolor != qcolor:
                continue
            if qmake and qmake not in omake:
                continue
            if qmodel and qmodel not in omodel:
                continue
            if qstate and not plate.startswith(qstate):
                continue
            if qdistrict and district_of(o.get("location"), o.get("camera_name")).lower() != qdistrict:
                continue
            if f.min_confidence and float(o.get("ocr_confidence", 0.0)) < f.min_confidence:
                continue
            if f.near_lat is not None and f.near_lng is not None:
                if o.get("latitude") is None or o.get("longitude") is None:
                    continue
                d = haversine_km(f.near_lat, f.near_lng,
                                 float(o["latitude"]), float(o["longitude"]))
                if d > f.radius_km:
                    continue
            out.append(o)
        return out

    # ------------------------------------------------------------------ #
    async def execute(self, plan: SearchPlan) -> dict[str, Any]:
        """Execute a plan; returns a traceable, explainable result."""
        window_dict = plan.filters.window.to_dict() if plan.filters.window else {}
        sightings = await self.load_detections(
            limit=max(plan.filters.limit * 20, 4000),
            window=window_dict,
            camera=plan.filters.camera,
            district=plan.filters.district,
        )
        filtered = self._apply_composite_filters(sightings, plan)

        # ---- vehicles near / find -------------------------------------- #
        if plan.intent in (INTENT_FIND_VEHICLES, INTENT_VEHICLES_NEAR, INTENT_TIMELINE, INTENT_EVIDENCE):
            return self._group_vehicles(filtered, plan, sightings)

        if plan.intent == INTENT_MULTI_DISTRICT:
            return self._multi_district(filtered, plan)

        if plan.intent == INTENT_REPEATED_NIGHT:
            return self._night_visitors(filtered, plan)

        if plan.intent == INTENT_RELATED_VEHICLES:
            return self._related(filtered, plan, sightings)

        return {
            "intent": plan.intent,
            "data_unavailable": "Query intent is unsupported; no assumption made.",
            "results": [],
        }

    # ------------------------------------------------------------------ #
    def _group_vehicles(
        self, filtered: list[dict[str, Any]], plan: SearchPlan, all_sightings: list[dict[str, Any]]
    ) -> dict[str, Any]:
        by_vehicle: dict[str, list[dict[str, Any]]] = {}
        for o in filtered:
            by_vehicle.setdefault(str(o["vehicle_uuid"]), []).append(o)
        vehicle_rows = []
        for uid, obs in by_vehicle.items():
            obs_sorted = sorted(obs, key=lambda x: float(x.get("ts", 0)))
            first = obs_sorted[0]
            last = obs_sorted[-1]
            plate = canonical_plate(first.get("plate", ""))
            app = first.get("appearance") or {}
            vehicle_rows.append(
                {
                    "vehicle_uuid": uid,
                    "plate": plate,
                    "normalized_plate": first.get("normalized_plate") or plate,
                    "vehicle_type": app.get("vehicle_type"),
                    "color": app.get("color"),
                    "make": app.get("make"),
                    "model": app.get("model"),
                    "sighting_count": len(obs_sorted),
                    "districts": sorted({district_of(o.get("location"), o.get("camera_name"))
                                         for o in obs_sorted if district_of(o.get("location"), o.get("camera_name"))}),
                    "first_seen_ts": first.get("ts"),
                    "last_seen_ts": last.get("ts"),
                    "supporting": [
                        {"camera_id": o.get("camera_id"), "camera_name": o.get("camera_name"),
                         "location": o.get("location"), "plate": o.get("plate"),
                         "ts": o.get("ts"), "ocr_confidence": o.get("ocr_confidence"),
                         "evidence_id": o.get("evidence_id")}
                        for o in obs_sorted[:15]
                    ],
                }
            )
        # Rank by sighting count desc, then by last-seen.
        vehicle_rows.sort(key=lambda r: (-r["sighting_count"], -float(r["last_seen_ts"] or 0)))
        return {
            "intent": plan.intent,
            "interpretation": plan.to_dict(),
            "vehicle_count": len(vehicle_rows),
            "vehicles": vehicle_rows[: plan.filters.limit],
            "data_unavailable": self._unavailable_note(plan, filtered),
            "excluded": self._excluded_note(plan),
        }

    # ------------------------------------------------------------------ #
    def _multi_district(self, filtered: list[dict[str, Any]], plan: SearchPlan) -> dict[str, Any]:
        results = multi_district_vehicles(
            filtered,
            min_districts=int(plan.analytic.get("min_districts", 3)),
            max_elapsed_hours=plan.analytic.get("max_elapsed_hours"),
        )
        return {
            "intent": INTENT_MULTI_DISTRICT,
            "minimum_districts": plan.analytic.get("min_districts"),
            "max_elapsed_hours": plan.analytic.get("max_elapsed_hours"),
            "vehicle_count": len(results),
            "vehicles": results[: plan.filters.limit],
            "data_unavailable": self._unavailable_note(plan, filtered, prefix="No detection data matched"),
        }

    def _night_visitors(self, filtered: list[dict[str, Any]], plan: SearchPlan) -> dict[str, Any]:
        results = repeated_night_visitors(
            filtered,
            period_nights=int(plan.analytic.get("period_nights", 7)),
            hour_start=int(plan.analytic.get("hour_start", 20)),
            hour_end=int(plan.analytic.get("hour_end", 6)),
            min_night_visits=int(plan.analytic.get("min_night_visits", 2)),
        )
        return {
            "intent": INTENT_REPEATED_NIGHT,
            "vehicle_count": len(results),
            "vehicles": results[: plan.filters.limit],
            "data_unavailable": self._unavailable_note(plan, filtered, prefix="No night detections matched"),
        }

    def _related(self, filtered, plan, all_sightings) -> dict[str, Any]:
        results = related_vehicles(
            filtered,
            window_seconds=float(plan.analytic.get("cooccurrence_window_seconds", 120)),
            min_vehicles=int(plan.analytic.get("min_vehicles", 2)),
            min_cameras=int(plan.analytic.get("min_cameras", 2)),
        )
        return {
            "intent": INTENT_RELATED_VEHICLES,
            "data_unavailable": self._unavailable_note(plan, filtered, prefix="No co-occurrence detections matched"),
            **results,
        }

    @staticmethod
    def _unavailable_note(plan: SearchPlan, filtered: list[dict], *, prefix: str = "No matching detections") -> str | None:
        if filtered:
            return None
        criteria = []
        f = plan.filters
        if f.plate:
            criteria.append(f"plate contains '{f.plate}'")
        if f.vehicle_type:
            criteria.append(f"type '{f.vehicle_type}'")
        if f.color:
            criteria.append(f"color '{f.color}'")
        if f.district:
            criteria.append(f"district '{f.district}'")
        if f.camera:
            criteria.append(f"camera '{f.camera}'")
        if f.window and (f.window.start or f.window.end):
            criteria.append(f"time window '{f.window.label}'")
        if plan.analytic:
            criteria.append("analytic criteria")
        return f"{prefix} for {' + '.join(criteria) if criteria else 'the stated criteria'}; " \
               f"the requested data is unavailable in the stored detections and was not fabricated."

    @staticmethod
    def _excluded_note(plan: SearchPlan) -> list[str]:
        # Explainable: what the system would have considered but did not use.
        notes = []
        if plan.intent == INTENT_UNKNOWN:
            notes.append("No recognised intent; results excluded any guess-based filtering.")
        if plan.warnings:
            notes.extend(plan.warnings)
        return notes


__all__ = ["CopilotExecutor"]
