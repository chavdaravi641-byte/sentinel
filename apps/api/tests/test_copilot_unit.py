"""Phase 6 — Copilot unit tests (no DB, no network).

Covers the pure-python core: NL planning (intents/attributes/time), the analytic
intents (multi-district, night visitors, related), the PDF report generator and
the validation harness. Evidence/executor DB paths are exercised in Docker.
"""

from __future__ import annotations

import datetime as dt

from src.anpr.copilot.nl import NaturalLanguagePlanner
from src.anpr.copilot.analysis import (
    district_of,
    multi_district_vehicles,
    related_vehicles,
    repeated_night_visitors,
)
from src.anpr.copilot.pdf import PDFReportGenerator
from src.anpr.copilot.plan import (
    INTENT_EVIDENCE,
    INTENT_FIND_VEHICLES,
    INTENT_MULTI_DISTRICT,
    INTENT_RELATED_VEHICLES,
    INTENT_REPEATED_NIGHT,
    INTENT_TIMELINE,
    INTENT_VEHICLES_NEAR,
)
from src.anpr.copilot.validation import run_validation


NOW = dt.datetime(2026, 9, 1, 12, 0, tzinfo=dt.timezone.utc)


def _plan(query: str):
    return NaturalLanguagePlanner().plan(query, now=NOW)


# --------------------------------------------------------------------------- #
# NL planner — intents
# --------------------------------------------------------------------------- #
def test_planner_find_vehicles_intent():
    p = _plan("white SUV Ahmedabad after 8 PM")
    assert p.intent == INTENT_FIND_VEHICLES
    assert p.filters.color == "white"
    assert p.filters.vehicle_type == "suv"
    assert p.filters.district == "Ahmedabad"
    assert p.filters.window.start is not None


def test_planner_vehicles_near_intent():
    p = _plan("find vehicles near Camera GJ-114 last 3 hours")
    assert p.intent == INTENT_VEHICLES_NEAR
    assert p.filters.camera == "GJ-114"
    assert p.filters.window.label.startswith("last 3 hour")


def test_planner_multi_district_word_count():
    p = _plan("crossed three districts in under 2 hours")
    assert p.intent == INTENT_MULTI_DISTRICT
    assert p.analytic.get("min_districts") == 3
    assert p.analytic.get("max_elapsed_hours") == 2.0


def test_planner_multi_district_digit_count():
    p = _plan("crossed 4 districts in under 5 hours")
    assert p.intent == INTENT_MULTI_DISTRICT
    assert p.analytic.get("min_districts") == 4
    assert p.analytic.get("max_elapsed_hours") == 5.0


def test_planner_repeated_night_visitors_intent():
    p = _plan("repeated night visitors last 7 days minimum 2 nights")
    assert p.intent == INTENT_REPEATED_NIGHT
    assert p.analytic.get("min_night_visits") == 2


def test_planner_timeline_intent_and_plate():
    p = _plan("timeline for vehicle GJ01AB1234")
    assert p.intent == INTENT_TIMELINE
    assert p.filters.plate


def test_planner_evidence_intent():
    p = _plan("show me the evidence for GJ05XY9012")
    assert p.intent == INTENT_EVIDENCE


def test_planner_related_intent():
    p = _plan("related vehicles around GJ01QQ3456")
    assert p.intent == INTENT_RELATED_VEHICLES


def test_planner_no_fabrication_on_empty():
    # A query with a filterable criterion absent from a filter yields warnings,
    # never a guessed plate.
    p = _plan("which cars were seen last night")
    assert p.intent == INTENT_FIND_VEHICLES
    assert p.filters.plate is None


# --------------------------------------------------------------------------- #
# District resolution (Gujarat alias table)
# --------------------------------------------------------------------------- #
def test_district_resolution_gujarat():
    assert district_of("Ring Road, Ahmedabad") == "Ahmedabad"
    assert district_of("Uvarsad, Gandhinagar") == "Gandhinagar"
    assert district_of("Raiya Road, Rajkot") == "Rajkot"


def test_district_non_gujarat_not_resolved():
    assert district_of("Marine Drive, Mumbai") == ""
    assert district_of("Pune MG Road") == ""


# --------------------------------------------------------------------------- #
# Analytics
# --------------------------------------------------------------------------- #
def _obs(uid, plate, ts, cam, camera_name, location, *, vtype="sedan", color="white"):
    return {
        "vehicle_uuid": uid, "plate": plate, "ts": ts, "camera_id": cam,
        "camera_name": camera_name, "location": location, "ocr_confidence": 0.95,
        "appearance": {"vehicle_type": vtype, "color": color},
    }


def test_multi_district_detects_only_true_crosser():
    base = 1_700_000_000.0
    obs = [
        _obs("V1", "GJ01AB1234", base + 0, "A", "CAM-A", "Ring Road, Ahmedabad"),
        _obs("V1", "GJ01AB1234", base + 3600, "C", "CAM-C", "Raiya Road, Rajkot"),
        _obs("V1", "GJ01AB1234", base + 7200, "B", "CAM-B", "Uvarsad, Gandhinagar"),
        _obs("V2", "MH12DE5678", base + 0, "A", "CAM-A", "Ring Road, Ahmedabad"),
        _obs("V2", "MH12DE5678", base + 3600, "A", "CAM-A", "Ring Road, Ahmedabad"),
    ]
    res = multi_district_vehicles(obs, min_districts=3, max_elapsed_hours=3)
    assert [r["vehicle_uuid"] for r in res] == ["V1"]


def test_night_visitors_min_nights():
    base = 1_700_000_000.0
    obs = []
    for day in range(3):
        obs.append(_obs("V3", "GJ05XY9012", base + (day * 24 + 22) * 3600, "B",
                        "CAM-B", "Uvarsad, Gandhinagar"))
    obs.append(_obs("V4", "GJ01QQ3456", base + 0 * 3600, "A", "CAM-A", "Ring Road, Ahmedabad"))
    obs.append(_obs("V4", "GJ01QQ3456", base + 2 * 3600, "A", "CAM-A", "Ring Road, Ahmedabad"))
    res = repeated_night_visitors(obs, period_nights=7, min_night_visits=3)
    assert [r["vehicle_uuid"] for r in res] == ["V3"]


def test_related_convoy_two_cameras():
    base = 1_700_000_000.0
    obs = [
        _obs("V3", "GJ05XY9012", base + 22 * 3600, "B", "CAM-B", "Uvarsad, Gandhinagar",
             vtype="suv", color="black"),
        _obs("V4", "GJ01QQ3456", base + 22 * 3600, "B", "CAM-B", "Uvarsad, Gandhinagar",
             vtype="suv", color="black"),
        _obs("V3", "GJ05XY9012", base + (24 + 22.05) * 3600, "D", "CAM-D", "Kalawad Road, Rajkot",
             vtype="suv", color="black"),
        _obs("V4", "GJ01QQ3456", base + (24 + 22.05) * 3600, "D", "CAM-D", "Kalawad Road, Rajkot",
             vtype="suv", color="black"),
    ]
    res = related_vehicles(obs, window_seconds=120, min_cameras=2, min_vehicles=2)
    plates = sorted(set(p for c in res["convoys"] for p in c["plates"] if p))
    assert "GJ05XY9012" in plates and "GJ01QQ3456" in plates


def test_empty_analytics_no_fabrication():
    assert multi_district_vehicles([], min_districts=3) == []
    assert repeated_night_visitors([], min_night_visits=2) == []


# --------------------------------------------------------------------------- #
# PDF generator
# --------------------------------------------------------------------------- #
def test_pdf_generation_valid():
    pdf = PDFReportGenerator().generate({
        "executive_summary": "Vehicle GJ05XY9012 repeatedly visited at night.",
        "vehicle": {"plate": "GJ05XY9012", "vehicle_uuid": "V3"},
        "timeline": [],
        "evidence": [],
        "reasoning": ["Repeated night visits across 3 nights."],
        "chain_of_evidence": [],
        "data_availability": "available",
    })
    assert pdf.startswith(b"%PDF-1.4")
    assert b"%%EOF" in pdf


# --------------------------------------------------------------------------- #
# Validation harness
# --------------------------------------------------------------------------- #
def test_validation_metrics_full_accuracy():
    out = run_validation()
    m = out["metrics"]
    assert m["nl_intent_accuracy"] == 1.0
    assert m["multi_district_accuracy"] == 1.0
    assert m["night_visitor_accuracy"] == 1.0
    assert m["related_vehicle_accuracy"] == 1.0
    assert m["explainability_ok"] is True
    assert m["pdf_generation_ok"] is True
    assert m["honesty_no_fabrication"] is True
