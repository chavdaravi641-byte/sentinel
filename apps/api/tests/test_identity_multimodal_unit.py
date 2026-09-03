"""Phase 5.1 — Multi-Modal Vehicle Identity unit tests (no DB, no network).

Validates the probabilistic identity engine: confidence-weighted fusion across
12 signals, automatic plate-weight reduction, identity that still functions
with missing plate, and the 7 required benchmark scenarios.
"""

from __future__ import annotations

from src.anpr.vehicle_intel.identity import assign_identity, canonical_plate
from src.anpr.vehicle_intel.multimodal import (
    VehicleCandidate,
    effective_plate_weight,
    fuse_identity,
)
from src.anpr.vehicle_intel.identity_bench import run_identity_benchmark


APP = {"vehicle_type": "sedan", "color": "white", "make": "Maruti", "model": "Swift"}
EMB = [0.1, 0.2, -0.1, 0.4, 0.3, -0.2, 0.5, -0.3]


def _cand(plate: str, *, color="white", vtype="sedan", make="Maruti", model="Swift",
          ar=1.9, wb=209.0, roofline="fastback", emb=EMB, cam="cam-a", ts=1700000000.0):
    ident = assign_identity(plate, {"color": color, "vehicle_type": vtype,
                                    "make": make, "model": model}, ocr_confidence=0.9)
    return VehicleCandidate(
        vehicle_uuid=ident.vehicle_uuid,
        canonical_plate=canonical_plate(plate),
        color=color, vehicle_type=vtype, make=make, model=model,
        aspect_ratio=ar, wheelbase=wb, roofline=roofline, embedding=emb,
        history=[(cam, ts)], sighting_count=3,
    )


def _probe(plate, *, conf=0.9, app=APP, emb=EMB, cam="cam-a", ts=1700000001.0):
    return {
        "plate": plate, "ocr_confidence": conf, "appearance": app,
        "shape_embedding": emb, "aspect_ratio": 1.9, "wheelbase": 209.0,
        "roofline": "fastback", "camera_id": cam, "ts": ts,
    }


# --------------------------------------------------------------------------- #
# Auto plate-weight reduction
# --------------------------------------------------------------------------- #
def test_effective_plate_weight_reduces_with_low_confidence():
    full = effective_plate_weight(0.9, True)
    reduced = effective_plate_weight(0.2, True)
    assert full > reduced > 0.0
    assert effective_plate_weight(0.9, False) == 0.0  # missing plate -> 0


def test_plate_weight_reduced_in_contributions():
    c = _cand("GJ-01-AB-1234")
    fused_low = fuse_identity(
        _probe("GJ-01-AB-1234", conf=0.2), [c], None
    )
    fused_high = fuse_identity(
        _probe("GJ-01-AB-1234", conf=0.95), [c], None
    )
    assert fused_low.plate_weight_used < fused_high.plate_weight_used


# --------------------------------------------------------------------------- #
# Identity functions without plate
# --------------------------------------------------------------------------- #
def test_identity_functions_when_plate_missing():
    c = _cand("GJ-01-AB-1234")
    probe = _probe("", conf=0.0)  # no plate at all
    fused = fuse_identity(probe, [c], None)
    assert fused.identity_uuid == c.vehicle_uuid
    assert fused.plate_weight_used == 0.0
    assert any("plate_missing" in r for r in fused.identity_reasoning)
    assert fused.identity_confidence >= 0.5


# --------------------------------------------------------------------------- #
# Required return fields
# --------------------------------------------------------------------------- #
def test_fusion_returns_required_fields():
    c = _cand("GJ-01-AB-1234")
    fused = fuse_identity(_probe("GJ-01-AB-1234"), [c], None)
    d = fused.to_dict()
    for field in (
        "identity_uuid",
        "identity_confidence",
        "identity_reasoning",
        "feature_contributions",
        "ambiguity_score",
    ):
        assert field in d, field
    assert set(fused.feature_contributions) == {
        "plate_similarity", "vehicle_embedding", "vehicle_color", "vehicle_type",
        "vehicle_make", "vehicle_model", "aspect_ratio", "wheelbase", "roofline",
        "travel_time", "camera_graph", "historical_sightings",
    }
    assert 0.0 <= fused.ambiguity_score <= 1.0


# --------------------------------------------------------------------------- #
# Behaviour with a gallery
# --------------------------------------------------------------------------- #
def test_same_vehicle_matches_correct_candidate():
    a = _cand("GJ-01-AB-1234", color="white")
    b = _cand("GJ-05-XY-8888", color="blue", vtype="hatchback", ar=1.6,
              wb=176.0, roofline="coupe", emb=[0.9, -0.8, 0.5])
    fused = fuse_identity(_probe("GJ-01-AB-1234"), [a, b], None)
    assert fused.identity_uuid == a.vehicle_uuid


def test_plate_swap_does_not_trust_plate_alone():
    # plate from vehicle B placed on vehicle A; appearance/embedding tie it to A.
    a = _cand("GJ-01-AB-1234", color="white")
    b = _cand("GJ-05-XY-8888", color="blue", vtype="hatchback", ar=1.6,
              wb=176.0, roofline="coupe", emb=[0.9, -0.8, 0.5, -0.2, 0.7, 0.1, -0.4, 0.6])
    probe = _probe(b.canonical_plate, conf=0.95, app=APP, cam="cam-a")
    fused = fuse_identity(probe, [a, b], None)
    # The multi-modal engine should return A (appearance/embedding), NOT blindly
    # adopt B's plate-based identity.
    assert fused.identity_uuid == a.vehicle_uuid
    assert fused.identity_uuid != b.vehicle_uuid


def test_new_plate_mints_new_identity_when_no_match():
    c = _cand("GJ-01-AB-1234")
    # A genuinely different car (different appearance/embedding + new plate)
    probe = {
        "plate": "GJ-99-ZZ-0001", "ocr_confidence": 0.9,
        "appearance": {"color": "green", "vehicle_type": "truck", "make": "Tata", "model": "Ace"},
        "shape_embedding": [0.9, -0.8, 0.5, -0.2, 0.7, 0.1, -0.4, 0.6],
        "aspect_ratio": 1.35, "wheelbase": 180.0, "roofline": "boxy",
        "camera_id": "cam-b", "ts": 1700000720.0,
    }
    fused = fuse_identity(probe, [c], None)
    assert fused.identity_uuid != c.vehicle_uuid
    # New identity is keyed by the plate through the existing assign_identity.
    assert fused.identity_uuid == assign_identity(probe["plate"], probe["appearance"],
                                                  ocr_confidence=0.9).vehicle_uuid


# --------------------------------------------------------------------------- #
# Benchmark (all 7 required scenarios)
# --------------------------------------------------------------------------- #
def test_benchmark_covers_all_required_scenarios():
    report = run_identity_benchmark()
    assert report["synthetic"] is True
    required = {
        "plate_missing", "partial_plate", "wrong_ocr", "same_vehicle",
        "different_vehicle", "plate_swap", "fake_plate",
    }
    assert set(report["scenarios_included"]) >= required
    for sc, res in report["scenarios"].items():
        assert 0.0 <= res["accuracy"] <= 1.0
    assert report["overall_accuracy"] >= 0.7
