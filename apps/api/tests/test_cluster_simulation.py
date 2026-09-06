"""Simulation tests for Phase 7.1 deterministic node-scale sweeps.

Runs the real scheduler/store code paths over 1 and 5 nodes and asserts the
core correctness invariants: every camera scheduled, no split-brain on
failover, and honest synthetic labelling (no fabricated metrics).
"""

from __future__ import annotations



from src.cluster.simulator import run_simulations, run_node_scale


async def test_single_node_scale_run_is_synthetic_and_correct():
    r = await run_node_scale(1)
    assert r["synthetic"] is True
    assert r["n_nodes"] == 1
    iv = r["invariants"]
    assert iv["cameras_scheduled"] == iv["expected_scheduled"]
    assert iv["no_split_brain"] is True
    # single node has no failover partner -> not supported, no cameras transfer
    assert iv["failover_supported"] is False
    assert iv["victim_cameras_transferred"] == 0
    assert r["metrics"]["recovery_time_s"] > 0


async def test_multi_node_scale_run_fails_over_without_split_brain():
    r = await run_node_scale(5)
    assert r["synthetic"] is True
    iv = r["invariants"]
    assert iv["cameras_scheduled"] == iv["expected_scheduled"]
    assert iv["no_split_brain"] is True
    assert iv["failover_supported"] is True
    # the victim's cameras were all transferred to a surviving node
    assert iv["victim_cameras_transferred"] == iv["victim_cameras_expected"]
    assert iv["victim_cameras_transferred"] > 0
    # realistic, bounded latencies for the real code paths
    m = r["metrics"]
    assert m["register_ms"] >= 0
    assert m["heartbeat_latency_ms_per_heartbeat"] > 0
    assert m["schedule_per_camera_ms"] > 0
    assert m["ownership_transfer_ms"] > 0


async def test_full_sweep_invariants_for_all_scales():
    results = await run_simulations([1, 5, 20])
    assert len(results) == 3
    results.sort(key=lambda x: x["n_nodes"])
    for r in results:
        assert r["synthetic"] is True
        iv = r["invariants"]
        assert iv["cameras_scheduled"] == iv["expected_scheduled"]
        assert iv["no_split_brain"] is True
