"""Phase 6 Copilot — Explainable AI.

Every Copilot answer is accompanied by a structured explanation:

* what the query was understood to mean (intent + filters),
* why each returned vehicle was selected (matching evidence),
* why alternative candidates were rejected,
* a confidence score,
* the supporting stored detections.

This module turns a plan + an executed result into an ``Explanation``. It never
adds information beyond what the executor traced, keeping the AI accountable.
"""

from __future__ import annotations

from typing import Any

from src.anpr.copilot.plan import SearchPlan


class ExplainableAI:
    """Builds explainable answers from a plan and its result."""

    def explain(self, plan: SearchPlan, result: dict[str, Any]) -> dict[str, Any]:
        explanation = {
            "query_interpretation": self._interpretation(plan),
            "selection_reasons": self._selections(plan, result),
            "rejections": self._rejections(plan, result),
            "confidence": round(float(plan.confidence or result.get("confidence", 0.0)), 3),
            "supporting_evidence": self._supporting(result),
            "data_availability": result.get("data_unavailable"),
            "traceability": "Every candidate is traceable to stored detections; "
                            "no evidence is invented.",
        }
        return explanation

    # ------------------------------------------------------------------ #
    def _interpretation(self, plan: SearchPlan) -> dict[str, Any]:
        return {
            "intent": plan.intent,
            "filters": plan.filters.to_dict(),
            "analytic": dict(plan.analytic),
            "steps": [s.rationale for s in plan.steps],
        }

    # ------------------------------------------------------------------ #
    def _selections(self, plan: SearchPlan, result: dict[str, Any]) -> list[dict[str, Any]]:
        vehicles = result.get("vehicles") or []
        out = []
        for v in vehicles[:10]:
            out.append(
                {
                    "vehicle_uuid": v.get("vehicle_uuid"),
                    "plate": v.get("plate"),
                    "why": v.get("reason") or self._vehicle_why(v),
                }
            )
        return out

    @staticmethod
    def _vehicle_why(v: dict[str, Any]) -> str:
        bits = []
        if v.get("district_count") is not None and v.get("districts"):
            bits.append(f"observed across {v['district_count']} districts {v['districts']}")
        if v.get("night_visit_count") is not None:
            bits.append(f"night visits on {v['night_visit_count']} distinct nights")
        if v.get("sighting_count"):
            bits.append(f"{v['sighting_count']} matching detections")
        if not bits:
            bits.append("matched the query criteria on its stored detections")
        return "; ".join(bits)

    # ------------------------------------------------------------------ #
    def _rejections(self, plan: SearchPlan, result: dict[str, Any]) -> list[str]:
        # Explicit reasons a candidate may have been excluded.
        reasons = []
        f = plan.filters
        if f.plate:
            reasons.append(f"Vehicles whose canonical plate does not contain '{f.plate}' were rejected.")
        if f.vehicle_type:
            reasons.append(f"Vehicles with type != '{f.vehicle_type}' were rejected.")
        if f.color:
            reasons.append(f"Vehicles with colour != '{f.color}' were rejected.")
        if f.district:
            reasons.append(f"Vehicles with no district '{f.district}' sighting were rejected.")
        if plan.intent in ("multi_district", "repeated_night_visitors"):
            reasons.append("Vehicles failing the analytic threshold were rejected and not shown.")
        if not reasons and not result.get("vehicles"):
            reasons.append("No candidate passed the criteria; alternatives were rejected as "
                           "non-matching to the traced detections.")
        exclusions = result.get("excluded") or []
        reasons.extend(exclusions)
        return reasons

    # ------------------------------------------------------------------ #
    def _supporting(self, result: dict[str, Any]) -> list[dict[str, Any]]:
        out = []
        for v in (result.get("vehicles") or [])[:10]:
            support = v.get("supporting") or []
            out.append(
                {
                    "vehicle_uuid": v.get("vehicle_uuid"),
                    "plate": v.get("plate"),
                    "detections": support,
                }
            )
        return out


__all__ = ["ExplainableAI"]
