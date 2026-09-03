"""Phase 5 — Global Vehicle Identity Engine unit tests (no DB, no network).

Covers: identity stability, camera graph, association, route reconstruction,
route prediction, timeline and the benchmark-driven MOT/Phase-5 metrics.
"""

from __future__ import annotations

from src.anpr.vehicle_intel.identity import (
    assign_identity,
    canonical_plate,
    plate_fingerprint,
)
from src.anpr.vehicle_intel.graph import (
    GraphConfig,
    build_graph_from_cameras,
    haversine_km,
)
from src.anpr.vehicle_intel.association import associate
from src.anpr.vehicle_intel.reconstruction import reconstruct_route
from src.anpr.vehicle_intel.prediction import TransitionModel, predict_next_cameras
from src.anpr.vehicle_intel.timeline import build_evidence_timeline
from src.anpr.vehicle_intel.traffic import compute_traffic_insights
from src.anpr.vehicle_intel.metrics import compute_mot_metrics
from src.anpr.vehicle_intel.benchmark import run_benchmark, BENCHMARK_CAMERAS


APP = {"vehicle_type": "car", "color": "white", "make": "Toyota", "model": "Corolla"}
EMB = [0.1, 0.2, -0.1, 0.4, 0.3, -0.2]


# --------------------------------------------------------------------------- #
# Identity
# --------------------------------------------------------------------------- #
def test_identity_stable_across_cameras_and_lighting():
    # Same plate, different ocr confidences and embeddings -> same UUID.
    i1 = assign_identity("GJ-01-AB-1234", APP, ocr_confidence=0.81)
    i2 = assign_identity("gj-01-ab-1234", APP, shape_embedding=[0.9, -0.2], ocr_confidence=0.93)
    assert i1.vehicle_uuid == i2.vehicle_uuid
    assert i1.basis == "plate"
    assert i1.confidence > 0.7


def test_identity_appearance_fallback_when_no_plate():
    i = assign_identity("", APP, ocr_confidence=0.0)
    assert i.basis == "appearance"
    assert i.plate == ""
    # Same appearance -> same fallback identity.
    j = assign_identity("", APP, ocr_confidence=0.0)
    assert i.vehicle_uuid == j.vehicle_uuid


def test_canonical_plate():
    assert canonical_plate("  GJ-01 aB 1234 ") == "GJ01AB1234"
    assert plate_fingerprint("GJ01AB1234") == plate_fingerprint("gj01ab1234")


# --------------------------------------------------------------------------- #
# Camera graph
# --------------------------------------------------------------------------- #
def test_graph_built_from_cameras_and_haversine():
    config = GraphConfig(max_link_km=50, road_factor=1.25, assumed_speed_kph=35)
    g = build_graph_from_cameras(BENCHMARK_CAMERAS, config)
    assert len(g.nodes()) == len(BENCHMARK_CAMERAS)
    # Naroda (Ahmedabad) to Gandhinagar are within 50km -> linked.
    assert g.has("cam-a") and g.has("cam-d")
    e = g.edge("cam-a", "cam-d")
    assert e is not None and e.road_distance_km > 0
    sp = g.shortest_path("cam-a", "cam-d")
    assert sp is not None and len(sp[0]) >= 2


def test_haversine_sanity():
    # Naroda Junction -> Drive-in Road is ~14km crow-flies.
    d = haversine_km(23.0595, 72.6575, 23.0402, 72.5247)
    assert 10 < d < 20


# --------------------------------------------------------------------------- #
# Association
# --------------------------------------------------------------------------- #
def _mk(plate, cam, ts, conf=0.85, app=APP, emb=EMB):
    return {
        "plate": plate, "camera_id": cam, "appearance": app,
        "shape_embedding": emb, "ocr_confidence": conf, "ts": ts,
        "vehicle_uuid": assign_identity(plate, app, ocr_confidence=conf).vehicle_uuid,
    }


def test_association_same_vehicle_matches():
    g = build_graph_from_cameras(BENCHMARK_CAMERAS)
    a = _mk("GJ-01-AB-1234", "cam-a", 1700000000.0)
    b = _mk("GJ-01-AB-1234", "cam-b", 1700000300.0)  # ~5min later
    res = associate(a, b, g)
    assert res.is_match is True
    assert res.plate_sim == 1.0
    assert res.confidence > 0.8


def test_association_wrong_vehicle_rejected():
    g = build_graph_from_cameras(BENCHMARK_CAMERAS)
    a = _mk("GJ-01-AB-1234", "cam-a", 1700000000.0)
    # A genuinely different car: different plate AND different appearance &
    # embedding (so this isn't just an OCR-misread of the same vehicle).
    b = _mk(
        "GJ-02-CD-9999", "cam-b", 1700000300.0,
        app={"vehicle_type": "truck", "color": "blue", "make": "Tata", "model": "Ace"},
        emb=[0.9, -0.8, 0.5, -0.2, 0.7, 0.1],
    )
    res = associate(a, b, g)
    assert res.is_match is False


def test_association_same_plate_but_misread_digit_recovers():
    # Same car, one OCR digit flipped -> appearance + embedding bridge the gap.
    g = build_graph_from_cameras(BENCHMARK_CAMERAS)
    a = _mk("GJ-01-AB-1234", "cam-a", 1700000000.0)
    b = _mk("GJ-01-AB-1235", "cam-b", 1700000300.0)  # last digit misread
    res = associate(a, b, g)
    assert res.is_match is True


# --------------------------------------------------------------------------- #
# Route reconstruction
# --------------------------------------------------------------------------- #
def test_route_reconstruction_path_and_speed():
    g = build_graph_from_cameras(BENCHMARK_CAMERAS)
    obs = [_mk("GJ-01-AB-1234", "cam-a", 1700000000.0),
           _mk("GJ-01-AB-1234", "cam-b", 1700000300.0)]
    route = reconstruct_route("u-1", obs, g)
    assert route.start_camera == "cam-a"
    assert route.end_camera == "cam-b"
    assert route.total_road_km > 0
    path = route.segments[0].path
    assert path[0] == "cam-a" and path[-1] == "cam-b"
    # Path must be fully connected through real graph edges.
    for x, y in zip(path, path[1:]):
        assert g.edge(x, y) is not None


# --------------------------------------------------------------------------- #
# Prediction
# --------------------------------------------------------------------------- #
def test_prediction_top5_from_model():
    g = build_graph_from_cameras(BENCHMARK_CAMERAS)
    model = TransitionModel()
    model.update_many([["cam-a", "cam-b", "cam-c"], ["cam-a", "cam-b", "cam-c"]])
    pred = predict_next_cameras("cam-b", ["cam-a", "cam-b"], g, model, top_k=5)
    assert pred.predictions
    assert pred.predictions[0]["camera_id"] == "cam-c"
    assert len(pred.predictions) <= 5
    assert pred.total_confidence <= 1.0 + 1e-6


# --------------------------------------------------------------------------- #
# Timeline
# --------------------------------------------------------------------------- #
def test_timeline_clusters_journeys():
    g = build_graph_from_cameras(BENCHMARK_CAMERAS)
    base = 1700000000.0
    s1 = _mk("GJ-01-AB-1234", "cam-a", base)
    s2 = _mk("GJ-01-AB-1234", "cam-b", base + 3600)
    s3 = _mk("GJ-01-AB-1234", "cam-c", base + 24 * 3600)  # next day
    tl = build_evidence_timeline([s1, s2, s3], g, gap_minutes=120)
    assert tl["observation_count"] == 3
    assert tl["journey_count"] >= 2


# --------------------------------------------------------------------------- #
# Traffic intelligence
# --------------------------------------------------------------------------- #
def test_traffic_insights_aggregates():
    g = build_graph_from_cameras(BENCHMARK_CAMERAS)
    obs = [
        _mk("GJ-01-AB-1234", "cam-a", 1700000000.0),
        _mk("GJ-01-AB-1234", "cam-b", 1700000300.0),
        _mk("GJ-05-XY-8888", "cam-b", 1700000400.0),
        _mk("GJ-05-XY-8888", "cam-c", 1700000600.0),
    ]
    ti = compute_traffic_insights(obs, g)
    assert ti.total_observations == 4
    assert ti.unique_vehicles == 2
    assert len(ti.most_used_routes) >= 1


# --------------------------------------------------------------------------- #
# Metrics / benchmark
# --------------------------------------------------------------------------- #
def test_compute_mot_metrics():
    m = compute_mot_metrics(
        ["v1", "v1", "v2", "v2"],
        ["v1", "v1", "v3", "v3"],
    )
    assert m["idf1"] >= 0.5
    assert 0.0 <= m["mota"] <= 1.0


def test_benchmark_runs_and_reports_real_metrics():
    report = run_benchmark()
    assert report["synthetic"] is True
    metrics = report["metrics"]
    for key in (
        "association_precision", "association_recall", "association_f1",
        "route_accuracy", "prediction_hit_rate", "identity_stability",
    ):
        assert 0.0 <= metrics[key] <= 1.0, key
    assert metrics["num_trials"] > 0
    assert report["graph_nodes"] == len(BENCHMARK_CAMERAS)
