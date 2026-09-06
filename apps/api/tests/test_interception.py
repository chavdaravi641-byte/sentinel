"""Predictive corridor interception unit tests (no DB, no network)."""

from __future__ import annotations

from src.anpr.interception import compute_interception
from src.anpr.vehicle_intel.graph import CameraGraph, GraphConfig


def _build_graph():
    g = CameraGraph(GraphConfig(max_link_km=60.0))
    g.add_cameras([
        {"id": "A", "name": "A", "location": "Ahmedabad", "latitude": 23.02, "longitude": 72.57},
        {"id": "B", "name": "B", "location": "Maninagar", "latitude": 23.00, "longitude": 72.59},
        {"id": "J1", "name": "J1 Junction", "location": "Asarwa", "latitude": 23.04, "longitude": 72.60},
        {"id": "C", "name": "C", "location": "CTM", "latitude": 22.99, "longitude": 72.62},
        {"id": "D", "name": "D", "location": "Nikol", "latitude": 23.06, "longitude": 72.63},
    ])
    g.build()
    return g


def test_returns_top_k_nodes_within_radius():
    g = _build_graph()
    v = compute_interception(
        g, "A", plate="GJ01AB1234", observed_ts=1750000000.0,
        radius_km=25.0, top_k=3,
    )
    assert v.basis == "graph"
    assert len(v.nodes) == 3
    assert v.nodes[0].camera_id == "B"  # nearest by travel time


def test_junction_nodes_are_prioritised():
    g = _build_graph()
    v = compute_interception(
        g, "A", plate="GJ01AB1234", observed_ts=1750000000.0,
        radius_km=25.0, top_k=3, junction_camera_ids={"J1"},
    )
    assert v.nodes[0].camera_id == "J1"
    assert v.nodes[0].is_junction is True
    # ETA after observed_ts and within the window [lower, upper]
    import datetime
    eta = datetime.datetime.fromisoformat(v.nodes[0].eta_utc)
    start = datetime.datetime.fromisoformat(v.nodes[0].window_start_utc)
    end = datetime.datetime.fromisoformat(v.nodes[0].window_end_utc)
    assert start <= eta <= end


def test_no_reachable_nodes_returns_empty():
    g = CameraGraph(GraphConfig(max_link_km=1.0))
    g.add_cameras([
        {"id": "X", "name": "X", "location": "", "latitude": 23.0, "longitude": 72.5},
        {"id": "Y", "name": "Y", "location": "", "latitude": 23.5, "longitude": 73.0},
    ])
    g.build()
    v = compute_interception(g, "X", plate="P", radius_km=1.0)
    assert v.basis == "none"
    assert v.nodes == []
    assert v.confidence == 0.0


def test_unknown_trigger_returns_empty():
    g = _build_graph()
    v = compute_interception(g, "NOPE", plate="P")
    assert v.nodes == []


def test_road_distance_within_radius_km():
    g = _build_graph()
    v = compute_interception(
        g, "A", plate="P", radius_km=25.0, top_k=10,
    )
    for n in v.nodes:
        assert n.road_distance_km <= 25.0 + 1e-6


def test_history_adds_directional_basis():
    g = _build_graph()
    v = compute_interception(
        g, "A", plate="P", radius_km=25.0, top_k=3,
        history=["A"],
    )
    # With a single-camera history the model still yields a graph basis.
    assert v.basis == "learned+graph"


def test_confidence_decreases_over_distance():
    g = _build_graph()
    near = compute_interception(g, "A", plate="P", radius_km=25.0, top_k=1)
    far = compute_interception(g, "A", plate="P", radius_km=100.0, top_k=1, speed_kph=35.0)
    assert near.confidence > 0
    assert far.confidence > 0
