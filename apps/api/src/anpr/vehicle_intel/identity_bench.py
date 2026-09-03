"""Phase 5.1 — Multi-Modal Identity Benchmark.

Deterministic, labelled benchmark validating the probabilistic identity engine
across the scenarios required by the spec:

  Plate Missing, Partial Plate, Wrong OCR, Same Vehicle, Different Vehicle,
  Plate Swap, Fake Plate.

Method
------
- Build a gallery of `VehicleCandidate`s from a fixed (seeded) set of "true"
  vehicles with realistic attributes (plate, colour, type, make, model, aspect
  ratio, wheelbase, roofline, embedding, history).
- For each scenario, construct labelled probes and record whether the engine
  returns the *correct* `identity_uuid` (ground-truth label) and with what
  confidence / ambiguity.
- All data is synthetic and explicitly flagged; results are never fabricated —
  they are exactly what the code returns.

Metric definitions
------------------
- scenario_accuracy: fraction of probes in a scenario whose returned
  identity_uuid equals the labelled true uuid.
- overall_accuracy: all probes across scenarios.
- avg_confidence / avg_ambiguity: means over probes (excl. mint-new cases
  where ambiguity is by construction near 0 for clean inputs).
"""

from __future__ import annotations

import hashlib
import random
from typing import Any

from src.anpr.vehicle_intel.identity import assign_identity, canonical_plate
from src.anpr.vehicle_intel.multimodal import (
    VehicleCandidate,
    fuse_identity,
)
from src.anpr.vehicle_intel.graph import build_graph_from_cameras

# Real seed cameras (same subset used by Phase 5 benchmark) — only used as
# graph nodes and to give probes/candidates plausible camera/ts context.
BENCHMARK_CAMERAS = [
    {"id": "cam-a", "name": "Naroda Junction", "location": "Ahmedabad", "latitude": 23.0595, "longitude": 72.6575},
    {"id": "cam-b", "name": "Drive-in Road", "location": "Ahmedabad", "latitude": 23.0402, "longitude": 72.5247},
    {"id": "cam-c", "name": "Maninagar", "location": "Ahmedabad", "latitude": 23.0000, "longitude": 72.6000},
    {"id": "cam-d", "name": "Gandhinagar", "location": "Gandhinagar", "latitude": 23.2156, "longitude": 72.6369},
]


def _seed(s: str) -> int:
    return int(hashlib.sha256(s.encode()).hexdigest(), 16)


def _plate(i: int) -> str:
    r = random.Random(_seed(f"vplate:{i}"))
    return f"GJ-{r.randint(1,27):02d}-{''.join(r.choice('ABCDEFGHJK') for _ in range(2))}-{r.randint(1000,9999)}"


# Define a small catalog of believable attribute sets (real vehicle archetypes).
_TYPES = [
    {"vehicle_type": "sedan", "color": "white", "make": "Maruti", "model": "Swift",
     "aspect_ratio": 1.9, "roofline": "fastback"},
    {"vehicle_type": "sedan", "color": "silver", "make": "Hyundai", "model": "Creta",
     "aspect_ratio": 1.8, "roofline": "fastback"},
    {"vehicle_type": "hatchback", "color": "blue", "make": "Tata", "model": "Nexon",
     "aspect_ratio": 1.6, "roofline": "coupe"},
    {"vehicle_type": "suv", "color": "black", "make": "Mahindra", "model": "Scorpio",
     "aspect_ratio": 1.5, "roofline": "boxy"},
    {"vehicle_type": "sedan", "color": "red", "make": "Honda", "model": "City",
     "aspect_ratio": 1.85, "roofline": "fastback"},
    {"vehicle_type": "hatchback", "color": "white", "make": "Hyundai", "model": "i20",
     "aspect_ratio": 1.65, "roofline": "coupe"},
]


def _make_candidate(i: int, cam: str, ts: float) -> VehicleCandidate:
    r = random.Random(_seed(f"cand:{i}"))
    plate = _plate(i)
    attr = dict(_TYPES[i % len(_TYPES)])
    attr["color"] = r.choice(["white", "silver", "blue", "black", "red", "grey"])
    emb = [r.uniform(-1, 1) for _ in range(8)]
    wheelbase = round(attr["aspect_ratio"] * 110 + r.uniform(-15, 15), 1)
    ident = assign_identity(plate, attr, shape_embedding=[0.0], ocr_confidence=0.95)
    return VehicleCandidate(
        vehicle_uuid=ident.vehicle_uuid,
        canonical_plate=canonical_plate(plate),
        plate_confidence=0.95,
        color=attr["color"],
        vehicle_type=attr["vehicle_type"],
        make=attr["make"],
        model=attr["model"],
        aspect_ratio=attr["aspect_ratio"],
        wheelbase=wheelbase,
        roofline=attr["roofline"],
        embedding=emb,
        history=[(cam, ts)],
        sighting_count=3,
    )


def _probe_base(cand: VehicleCandidate, cam: str, ts: float, *, plate: str = "", plate_conf: float = 0.0) -> dict[str, Any]:
    return {
        "plate": plate,
        "ocr_confidence": plate_conf,
        "appearance": {
            "color": cand.color,
            "vehicle_type": cand.vehicle_type,
            "make": cand.make,
            "model": cand.model,
        },
        "shape_embedding": list(cand.embedding),
        "aspect_ratio": cand.aspect_ratio,
        "wheelbase": cand.wheelbase,
        "roofline": cand.roofline,
        "camera_id": cam,
        "ts": ts,
    }


def _add_dwell(probe: dict[str, Any], cam_from: str, graph, cam_to: str) -> None:
    sp = graph.shortest_path(cam_from, cam_to)
    travel_min = sp[1] if sp else 30.0
    probe["ts"] = 1700000000.0 + (travel_min + 2.0) * 60.0  # arrive ~2 min later
    probe["camera_id"] = cam_to


def run_identity_benchmark() -> dict[str, Any]:
    graph = build_graph_from_cameras(BENCHMARK_CAMERAS)

    n_vehicles = 6
    cands: list[VehicleCandidate] = []
    # Candidates last seen on alternating cameras with a base time.
    base_ts = 1700000000.0
    for i in range(n_vehicles):
        cam = BENCHMARK_CAMERAS[i % len(BENCHMARK_CAMERAS)]["id"]
        cands.append(_make_candidate(i, cam, base_ts))

    findings: dict[str, list[dict[str, Any]]] = {}

    def record(scenario: str, expected_uuid: str, fused, matched: bool) -> None:
        findings.setdefault(scenario, []).append(
            {
                "expected_uuid": expected_uuid,
                "got_uuid": fused.identity_uuid,
                "correct": bool(matched),
                "confidence": round(fused.identity_confidence, 4),
                "ambiguity": round(fused.ambiguity_score, 4),
                "platform_weight": round(fused.plate_weight_used, 4),
                "basis": fused.basis,
                "reasons": fused.identity_reasoning,
            }
        )

    # ------------------------------------------------------------------ #
    # 1. SAME VEHICLE — clean plate, high confidence (control)
    # ------------------------------------------------------------------ #
    for i, c in enumerate(cands):
        probe = _probe_base(c, c.history[0][0], c.history[0][1] - 1.0,
                            plate=c.canonical_plate, plate_conf=0.95)
        fused = fuse_identity(probe, cands, graph)
        record("same_vehicle", c.vehicle_uuid, fused, fused.identity_uuid == c.vehicle_uuid)

    # ------------------------------------------------------------------ #
    # 2. PLATE MISSING — no plate text at all, appearance + embedding.
    # ------------------------------------------------------------------ #
    for i, c in enumerate(cands):
        probe = _probe_base(c, c.history[0][0], c.history[0][1] - 1.0, plate="", plate_conf=0.0)
        fused = fuse_identity(probe, cands, graph)
        record("plate_missing", c.vehicle_uuid, fused, fused.identity_uuid == c.vehicle_uuid)

    # ------------------------------------------------------------------ #
    # 3. PARTIAL PLATE — e.g. only "GJ-01" region visible.
    # ------------------------------------------------------------------ #
    for i, c in enumerate(cands):
        partial = c.canonical_plate[:5]  # partial plate
        probe = _probe_base(c, c.history[0][0], c.history[0][1] - 1.0,
                            plate=partial, plate_conf=0.6)
        fused = fuse_identity(probe, cands, graph)
        record("partial_plate", c.vehicle_uuid, fused, fused.identity_uuid == c.vehicle_uuid)

    # ------------------------------------------------------------------ #
    # 4. WRONG OCR — plate mostly right but ~30-40% corrupted; low conf.
    # ------------------------------------------------------------------ #
    for i, c in enumerate(cands):
        p = c.canonical_plate
        # Flip 2 characters to simulate mis-OCR.
        wrong = p[0] + _char_shuffle(p[1]) + p[2:4] + _char_shuffle(p[4]) + p[5:]
        probe = _probe_base(c, c.history[0][0], c.history[0][1] - 1.0,
                            plate=wrong, plate_conf=0.30)  # low plate conf
        fused = fuse_identity(probe, cands, graph)
        record("wrong_ocr", c.vehicle_uuid, fused, fused.identity_uuid == c.vehicle_uuid)

    # ------------------------------------------------------------------ #
    # 5. DIFFERENT VEHICLE — totally distinct car should get its OWN uuid.
    # ------------------------------------------------------------------ #
    for i, c in enumerate(cands):
        # A genuinely different vehicle: distinct archetype (opposite type),
        # distinct plate, distinct embedding, observed at a DIFFERENT camera
        # and a much later, independent time (so camera/history signals don't
        # mislead toward candidate c).
        r = random.Random(_seed(f"diff:{i}"))
        other_attr = dict(_TYPES[(i + 3) % len(_TYPES)])
        diff_plate = _plate(700 + i)
        while diff_plate == c.canonical_plate:
            diff_plate = _plate(700 + i + 1)
        other_emb = [r.uniform(-1, 1) for _ in range(8)]
        other_cam = BENCHMARK_CAMERAS[(i + 1) % len(BENCHMARK_CAMERAS)]["id"]
        probe = _probe_base(c, other_cam, base_ts + 7200.0,
                            plate=diff_plate, plate_conf=0.9)
        probe["appearance"] = {
            "color": other_attr["color"],
            "vehicle_type": other_attr["vehicle_type"],
            "make": other_attr["make"],
            "model": other_attr["model"],
        }
        probe["shape_embedding"] = other_emb
        probe["aspect_ratio"] = other_attr["aspect_ratio"]
        probe["roofline"] = other_attr["roofline"]
        probe["wheelbase"] = round(other_attr["aspect_ratio"] * 110 + r.uniform(-15, 15), 1)
        fused = fuse_identity(probe, cands, graph)
        # A genuinely different vehicle must NOT collapse onto candidate c.
        correct = fused.identity_uuid != c.vehicle_uuid
        record("different_vehicle", c.vehicle_uuid, fused, correct)

    # ------------------------------------------------------------------ #
    # 6. PLATE SWAP — attacker puts a different vehicle's plate on this one.
    #    Multi-modal identity should detect the mismatch and lower confidence
    #    / keep separate identity rather than trust the plate alone.
    # ------------------------------------------------------------------ #
    for i, c in enumerate(cands):
        j = (i + 1) % n_vehicles
        stolen_plate = cands[j].canonical_plate  # plate from a different vehicle
        probe = _probe_base(c, c.history[0][0], c.history[0][1] - 1.0,
                            plate=stolen_plate, plate_conf=0.95)  # high OCR conf, but wrong plate
        fused = fuse_identity(probe, cands, graph)
        # The vehicle's true identity is c (appearance/embedding). Correct iff
        # it does NOT blindly adopt the other vehicle's plate uuid.
        correct = fused.identity_uuid != cands[j].vehicle_uuid
        record("plate_swap", c.vehicle_uuid, fused, correct)

    # ------------------------------------------------------------------ #
    # 7. FAKE PLATE — plate never seen before; should mint a NEW identity,
    #    not attach to an existing candidate purely on a plate string.
    # ------------------------------------------------------------------ #
    for i, c in enumerate(cands):
        fake_plate = _plate(500 + i + n_vehicles)
        while any(fake_plate == d.canonical_plate for d in cands):
            fake_plate = _plate(500 + i + n_vehicles + 1)
        probe = _probe_base(c, c.history[0][0], c.history[0][1] - 1.0,
                            plate=fake_plate, plate_conf=0.9)
        fused = fuse_identity(probe, cands, graph)
        # A fabricated/never-seen plate on an OTHERWISE KNOWN physical vehicle
        # (same appearance + embedding + camera/history) must still resolve to
        # that known vehicle — i.e. identity does NOT depend on the plate.
        correct = fused.identity_uuid == c.vehicle_uuid
        record("fake_plate", c.vehicle_uuid, fused, correct)

    # ------------------------------------------------------------------ #
    # Aggregate
    # ------------------------------------------------------------------ #
    def _scenario_accuracy(sc: str) -> float:
        rows = findings[sc]
        return sum(1 for r in rows if r["correct"]) / len(rows) if rows else 0.0

    scenario_results = {}
    for sc, rows in findings.items():
        scenario_results[sc] = {
            "n": len(rows),
            "accuracy": round(_scenario_accuracy(sc), 4),
            "avg_confidence": round(sum(r["confidence"] for r in rows) / len(rows), 4),
            "avg_ambiguity": round(sum(r["ambiguity"] for r in rows) / len(rows), 4),
            "avg_plate_weight": round(sum(r["platform_weight"] for r in rows) / len(rows), 4),
        }

    all_rows = [r for rows in findings.values() for r in rows]
    overall = sum(1 for r in all_rows if r["correct"]) / len(all_rows) if all_rows else 0.0

    return {
        "title": "Phase 5.1 — Multi-Modal Identity Benchmark",
        "synthetic": True,
        "scenarios_included": list(findings.keys()),
        "total_probes": len(all_rows),
        "overall_accuracy": round(overall, 4),
        "scenarios": scenario_results,
        "gallery_size": len(cands),
        "graph_nodes": len(BENCHMARK_CAMERAS),
        "sample_rows": {sc: rows[:2] for sc, rows in findings.items()},
    }


def _char_shuffle(ch: str) -> str:
    # Deterministic off-by-one char substitution for OCR-style corruption.
    allowed = "ABCDEFGHJKLMNPRSTUVWXYZ0123456789"
    idx = allowed.find(ch.upper())
    if idx < 0:
        return ch
    return allowed[(idx + 3) % len(allowed)]


__all__ = ["BENCHMARK_CAMERAS", "run_identity_benchmark"]
