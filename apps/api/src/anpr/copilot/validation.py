"""Phase 6 Copilot — Validation harness.

Runs the Copilot engine over a strict, deterministic synthetic corpus and reports
accuracy + latency metrics. Nothing here touches a live DB; the same
planner/analysis/executor logic used in production is exercised over synthetic
observation dicts so results are reproducible and honest (cases where the data
cannot answer are reported as data-unavailable, never fabricated).
"""

from __future__ import annotations

import time
from typing import Any

from src.anpr.copilot.analysis import (
    multi_district_vehicles,
    related_vehicles,
    repeated_night_visitors,
)
from src.anpr.copilot.explain import ExplainableAI
from src.anpr.copilot.nl import NaturalLanguagePlanner


def _obs(vehicle_uuid: str, plate: str, ts: float, camera_id: str,
         camera_name: str, location: str, *, vehicle_type: str = "sedan",
         color: str = "white", ocr_conf: float = 0.95) -> dict[str, Any]:
    return {
        "vehicle_uuid": vehicle_uuid, "plate": plate, "ts": ts,
        "camera_id": camera_id, "camera_name": camera_name, "location": location,
        "ocr_confidence": ocr_conf,
        "appearance": {"vehicle_type": vehicle_type, "color": color},
    }


def _corpus() -> list[dict[str, Any]]:
    base = 1_700_000_000.0
    cam = {
        "A": ("CAM-A", "Ring Road, Ahmedabad"),
        "B": ("CAM-B", "Uvarsad, Gandhinagar"),
        "C": ("CAM-C", "Raiya Road, Rajkot"),
        "D": ("CAM-D", "Kalawad Road, Rajkot"),
    }
    obs = []
    # Vehicle V1 seen in 3 DISTINCT districts within 3 hours -> multi-district.
    obs += [
        _obs("V1", "GJ01AB1234", base + 0 * 3600, "A", cam["A"][0], cam["A"][1]),
        _obs("V1", "GJ01AB1234", base + 1 * 3600, "B", cam["B"][0], cam["B"][1]),
        _obs("V1", "GJ01AB1234", base + 2 * 3600, "C", cam["C"][0], cam["C"][1]),
    ]
    # Vehicle V2 only in 1 district -> should NOT be multi-district(>=3).
    obs += [
        _obs("V2", "MH12DE5678", base + 0 * 3600, "A", cam["A"][0], cam["A"][1]),
        _obs("V2", "MH12DE5678", base + 1 * 3600, "A", cam["A"][0], cam["A"][1]),
    ]
    # Vehicle V3 repeated night visitor across 3 nights (hour 22 -> night).
    for day in range(3):
        obs.append(_obs("V3", "GJ05XY9012", base + (day * 24 + 22) * 3600, "B",
                        cam["B"][0], cam["B"][1], vehicle_type="suv", color="black"))
    # Vehicle V4 co-travels with V3 on 2 cameras (convoy) but only 2 nights.
    obs += [
        _obs("V4", "GJ01QQ3456", base + (0 * 24 + 22) * 3600, "B", cam["B"][0], cam["B"][1],
             vehicle_type="suv", color="black"),
        _obs("V4", "GJ01QQ3456", base + (1 * 24 + 22.05) * 3600, "D", cam["D"][0], cam["D"][1],
             vehicle_type="suv", color="black"),
    ]
    # Add a shared V3 sighting on cam D day 1 so the convoy covers 2 cameras
    # (B and D) with V3.
    obs.append(_obs("V3", "GJ05XY9012", base + (1 * 24 + 22.05) * 3600, "D", cam["D"][0],
                    cam["D"][1], vehicle_type="suv", color="black"))
    return obs


def run_validation() -> dict[str, Any]:
    started = time.perf_counter()
    obs = _corpus()
    corpus_build_ms = (time.perf_counter() - started) * 1000

    planner = NaturalLanguagePlanner()
    explainer = ExplainableAI()
    results: dict[str, Any] = {}

    # ---- 1. NL planner accuracy -------------------------------- #
    nl_cases = [
        ("white SUV Ahmedabad after 8 PM", {"intent": "find_vehicles"}),
        ("find vehicles near Camera GJ-114 last 3 hours", {"intent": "vehicles_near"}),
        ("crossed three districts in under 2 hours", {"intent": "multi_district"}),
        ("repeated night visitors last 7 days minimum 2 nights",
         {"intent": "repeated_night_visitors"}),
        ("timeline for vehicle GJ01AB1234", {"intent": "timeline"}),
        ("related vehicles around GJ01QQ3456", {"intent": "related_vehicles"}),
        ("show me the evidence for GJ05XY9012", {"intent": "evidence_builder"}),
        ("which cars were seen last night", {"intent": "find_vehicles"}),
    ]
    nl_ok = 0
    nl_detail = []
    for query, expected in nl_cases:
        t0 = time.perf_counter()
        plan = planner.plan(query, now=_now_dt())
        lat_ms = (time.perf_counter() - t0) * 1000
        got = plan.intent
        ok = got == expected["intent"]
        nl_ok += 1 if ok else 0
        nl_detail.append({
            "query": query, "expected": expected["intent"], "got": got,
            "ok": ok, "latency_ms": round(lat_ms, 1),
        })

    # ---- 2. Analytics accuracy ---------------------------------- #
    md = multi_district_vehicles(obs, min_districts=3, max_elapsed_hours=3)
    md_uids = sorted(r["vehicle_uuid"] for r in md)
    md_ok = md_uids == ["V1"]  # only V1 crosses 3 districts in <3h

    nv = repeated_night_visitors(obs, period_nights=7, min_night_visits=3)
    nv_uids = sorted(r["vehicle_uuid"] for r in nv)
    nv_ok = nv_uids == ["V3"]  # V3 visits 3 nights; V4 shares nights but 2 distinct? -> expect V3 only

    rel = related_vehicles(obs, window_seconds=120, min_cameras=2, min_vehicles=2)
    rel_plates = sorted(set(p for c in rel["convoys"] for p in c["plates"] if p))
    rel_ok = ("GJ05XY9012" in rel_plates and "GJ01QQ3456" in rel_plates)

    # ---- 3. Explainability -------------------------------------- #
    plan = planner.plan("find vehicles of type suv color black", now=_now_dt())
    expl = explainer.explain(plan, {"vehicles": [{"vehicle_uuid": "V3", "plate": "GJ05XY9012"}]})
    expl_ok = bool(expl)

    # ---- 4. PDF generation (pure, no DB) ------------------------ #
    from src.anpr.copilot.pdf import PDFReportGenerator
    t0 = time.perf_counter()
    pdf_bytes = PDFReportGenerator().generate({
        "executive_summary": "Vehicle GJ05XY9012 repeatedly visited at night.",
        "vehicle": {"plate": "GJ05XY9012", "vehicle_uuid": "V3"},
        "timeline": [{"ts": base_now, "camera_name": "CAM-B",
                      "district": "Ahmedabad", "ocr_confidence": 0.95,
                      "inferred_speed_kph": None}],
        "evidence": [{"kind": "plate", "ref": "GJ05XY9012", "present": True}],
        "reasoning": ["Repeated night visits across 3 nights."],
        "chain_of_evidence": ["2026-01-01 officer@sentinel.gp opened case SENT-1"],
        "data_availability": "available",
    })
    pdf_lat_ms = (time.perf_counter() - t0) * 1000
    pdf_ok = pdf_bytes.startswith(b"%PDF-1.4") and b"%%EOF" in pdf_bytes

    # ---- 5. Honesty / no-fabrication probe ---------------------- #
    empty = multi_district_vehicles([], min_districts=3)
    honesty_ok = empty == []  # no invented results on empty input

    total_ms = (time.perf_counter() - started) * 1000

    metrics = {
        "nl_intent_accuracy": round(nl_ok / len(nl_cases), 3),
        "nl_cases_total": len(nl_cases),
        "nl_cases_passed": nl_ok,
        "multi_district_accuracy": 1.0 if md_ok else 0.0,
        "night_visitor_accuracy": 1.0 if nv_ok else 0.0,
        "related_vehicle_accuracy": 1.0 if rel_ok else 0.0,
        "explainability_ok": expl_ok,
        "pdf_generation_ok": pdf_ok,
        "honesty_no_fabrication": honesty_ok,
        "latency_ms": {
            "corpus_build": round(corpus_build_ms, 1),
            "nl_avg": round(sum(d["latency_ms"] for d in nl_detail) / len(nl_detail), 1),
            "pdf_generation": round(pdf_lat_ms, 1),
            "total_validation": round(total_ms, 1),
        },
    }
    results["metrics"] = metrics
    results["nl_detail"] = nl_detail
    results["analytics"] = {
        "multi_district_vehicles": md_uids, "multi_district_ok": md_ok,
        "night_visitors": nv_uids, "night_visitors_ok": nv_ok,
        "related_plates": rel_plates, "related_ok": rel_ok,
    }
    results["honesty"] = {"query_empty_multi_district": honesty_ok}
    return results


base_now = 1_700_000_000.0


def _now_dt():
    import datetime as _dt
    return _dt.datetime.fromtimestamp(base_now, tz=_dt.timezone.utc)


if __name__ == "__main__":
    import json

    out = run_validation()
    print(json.dumps(out, indent=2, default=str))
