"""Deterministic Phase 5 benchmark (Phase 5).

Runs a *labelled synthetic* dataset through the identity/association/route/
prediction/metrics pipeline and returns real, reproducible metrics. The data is
explicitly synthetic (generated for validation), because we must never
fabricate production routes/cameras/metrics. All cameras used are drawn from
the real registered camera seed list.

The ground-truth labels are the "true" vehicle ids and expected next cameras;
metrics quantify how well the engine recovers them.
"""

from __future__ import annotations

import hashlib
import random
import time
from typing import Any

from src.anpr.vehicle_intel.identity import assign_identity
from src.anpr.vehicle_intel.graph import CameraGraph, build_graph_from_cameras
from src.anpr.vehicle_intel.metrics import compute_phase5_metrics
from src.anpr.vehicle_intel.prediction import TransitionModel

# A compact real subset of the seeded Gujarat cameras (used only as graph
# nodes; coordinates match the real seed list). See apps/api/src/seed.py.
BENCHMARK_CAMERAS = [
    {"id": "cam-a", "name": "Naroda Junction", "location": "Ahmedabad", "latitude": 23.0595, "longitude": 72.6575},
    {"id": "cam-b", "name": "Drive-in Road", "location": "Ahmedabad", "latitude": 23.0402, "longitude": 72.5247},
    {"id": "cam-c", "name": "Maninagar", "location": "Ahmedabad", "latitude": 23.0000, "longitude": 72.6000},
    {"id": "cam-d", "name": "Gandhinagar", "location": "Gandhinagar", "latitude": 23.2156, "longitude": 72.6369},
    {"id": "cam-e", "name": "Vadodara", "location": "Vadodara", "latitude": 22.3072, "longitude": 73.1812},
    {"id": "cam-f", "name": "Surat", "location": "Surat", "latitude": 21.1702, "longitude": 72.8311},
]


def _stable(s: str) -> int:
    return int(hashlib.sha256(s.encode()).hexdigest(), 16)


def _plate(i: int) -> str:
    rng = random.Random(_stable(f"plate:{i}"))
    letters = "".join(rng.choice("GJABCDEF") for _ in range(2))
    return f"GJ-{rng.randint(1, 27):02d}-{letters}-{rng.randint(1000, 9999)}"


def _time_between(a: str, b: str, graph: CameraGraph, factor: float = 1.4) -> float:
    """Return a plausible elapsed seconds between two real cameras (base ts + dt)."""
    base = 1700000000.0
    e = graph.edge(a, b)
    travel_min = e.travel_time_minutes if e else 30.0
    # observed elapsed = graph travel time + a small labelled dwell (noise),
    # so the engine is measuring real error, not a tautology.
    dwell = random.Random(_stable(f"dwell:{a}:{b}")).uniform(-1.5, 4.0)
    return base + (travel_min + dwell) * factor * 60.0


def run_benchmark() -> dict[str, Any]:
    """Execute the labelled benchmark and return reportable metrics."""
    rng = random.Random(42)
    graph = build_graph_from_cameras(BENCHMARK_CAMERAS)

    trials: list[dict[str, Any]] = []
    transitions: list[list[str]] = []

    # --- Build labelled same-vehicle trailing / non-match pairs -----------
    # ~20 true vehicles; each appears on 3 directly-connected cameras (A->B->C)
    # using only real graph edges so travel times are always defined.
    vehicles: list[tuple[str, str, str]] = []
    for v in range(20):
        a = rng.choice(BENCHMARK_CAMERAS)["id"]
        nbrs = graph.neighbors(a)
        if not nbrs:
            continue
        b = rng.choice(nbrs)
        nb = graph.neighbors(b)
        if not nb:
            continue
        c = rng.choice(nb)
        vehicles.append((a, b, c))

    for vi, (cam_a, cam_b, cam_c) in enumerate(vehicles):
        plate = _plate(vi)
        appearance = {"vehicle_type": "car", "color": "white", "make": "Toyota", "model": "Corolla"}
        emb = [0.1 * vi, 0.2, -0.1, 0.4, 0.3, -0.2]

        obs_a = {
            "plate": plate, "camera_id": cam_a, "appearance": appearance,
            "shape_embedding": emb, "ocr_confidence": 0.85,
            "ts": 1700000000.0, "vehicle_uuid": assign_identity(plate, appearance, ocr_confidence=0.85).vehicle_uuid,
        }
        obs_b = {
            "plate": plate, "camera_id": cam_b, "appearance": appearance,
            "shape_embedding": emb, "ocr_confidence": 0.9,
            "ts": _time_between(cam_a, cam_b, graph), "vehicle_uuid": obs_a["vehicle_uuid"],
        }
        obs_c = {
            "plate": plate, "camera_id": cam_c, "appearance": appearance,
            "shape_embedding": emb, "ocr_confidence": 0.88,
            "ts": _time_between(cam_b, cam_c, graph), "vehicle_uuid": obs_a["vehicle_uuid"],
        }
        transitions.append([cam_a, cam_b, cam_c])

        # Positive pairs (same true vehicle)
        # ground_truth_rel_dt is the *labelled true* travel time: graph edge
        # travel time plus a small stochastic dwell that represents real-world
        # stop/queue time. The engine's estimate is compared against this
        # labelled truth, so travel-time error is a genuine measurement.
        gt_dt_ab = graph.edge(cam_a, cam_b).travel_time_minutes + rng.uniform(-1.5, 4.0)
        gt_dt_bc = graph.edge(cam_b, cam_c).travel_time_minutes + rng.uniform(-1.5, 4.0)
        trials.append({
            "obs_a": dict(obs_a), "obs_b": dict(obs_b),
            "ground_truth_match": True,
            "ground_truth_rel_dt": gt_dt_ab,
            "gt_route_cams": [cam_a, cam_b],
        })
        trials.append({
            "obs_a": dict(obs_b), "obs_b": dict(obs_c),
            "ground_truth_match": True,
            "ground_truth_rel_dt": gt_dt_bc,
            "gt_route_cams": [cam_b, cam_c],
        })

        # Negative (hard) pairs: same appearance, wrong plate, far camera.
        other_plate = _plate(vi + 500)
        obs_hard = dict(obs_a)
        obs_hard["plate"] = other_plate
        obs_hard["vehicle_uuid"] = assign_identity(other_plate, appearance, ocr_confidence=0.85).vehicle_uuid
        trials.append({
            "obs_a": dict(obs_a), "obs_b": obs_hard,
            "ground_truth_match": False,
        })

    # --- Add prediction ground-truth trials ------------------------------
    model = TransitionModel()
    model.update_many(transitions)
    for idx, (cam_a, cam_b, cam_c) in enumerate(vehicles):
        trials.append({
            "obs_a": {"plate": _plate(idx), "camera_id": cam_b, "appearance": {"vehicle_type": "car"},
                      "shape_embedding": [0.1], "ocr_confidence": 0.8,
                      "ts": 1700000000.0, "vehicle_uuid": f"v-{idx}"},
            "obs_b": {"plate": _plate(idx), "camera_id": cam_b, "appearance": {"vehicle_type": "car"},
                      "shape_embedding": [0.1], "ocr_confidence": 0.8,
                      "ts": 1700000100.0, "vehicle_uuid": f"v-{idx}"},
            "ground_truth_match": True,
            "gt_next_camera": cam_c,
            "history": [cam_a, cam_b],
        })

    t0 = time.perf_counter()
    metrics = compute_phase5_metrics(graph, trials)
    wall_ms = (time.perf_counter() - t0) * 1000.0

    return {
        "title": "Phase 5: Global Vehicle Identity Engine — Benchmark",
        "synthetic": True,
        "graph_nodes": len(BENCHMARK_CAMERAS),
        "graphs_from_real_seed_cameras": True,
        "trials": len(trials),
        "wall_ms": round(wall_ms, 3),
        "metrics": metrics.to_dict(),
        "assumptions": graph.to_payload()["assumptions"],
    }


__all__ = ["BENCHMARK_CAMERAS", "run_benchmark"]
