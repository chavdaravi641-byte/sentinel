"""Unit tests for the Phase 7.1 distributed-edge orchestration core.

Covers the deterministic scheduler/score logic, the in-memory ``ClusterStore``
(register / heartbeat / reconcile / lease / ownership CAS), and lease-based
failover. Split-brain prevention is the explicit focus: only an expired lease
combined with an OFFLINE/RECOVERING owner triggers a transfer, and a concurrent
second sweep must never double-transfer the same camera.

Time is controlled through an injectable clock (``now``) so lease expiry and
heartbeat staleness are deterministic.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from src.cluster.config import settings
from src.cluster.scheduler import ScheduleWeights, best_node, schedule_score
from src.cluster.store import ClusterStore, NodeStatus


class _Clock:
    """Mutable clock; advance by calling :meth:`advance`."""

    def __init__(self):
        self.offset = 0.0

    def __call__(self) -> datetime:
        return datetime.now(UTC) + timedelta(seconds=self.offset)

    def advance(self, seconds: float):
        self.offset += seconds


class _FakeNode:
    """Minimal object exposing only the fields the scheduler reads."""

    def __init__(self, node_id, *, status=NodeStatus.ALIVE, cpu_util=0.0,
                 mem_util=0.0, gpu_util=None, gpu_count=0, active_cameras=0,
                 cpu_cores=8, ram_gb=16):
        self.node_id = node_id
        self.status = status
        self.cpu_util = cpu_util
        self.mem_util = mem_util
        self.gpu_util = gpu_util
        self.gpu_count = gpu_count
        self.active_cameras = active_cameras
        self.cpu_cores = cpu_cores
        self.ram_gb = ram_gb


# --------------------------------------------------------------------------
# Scheduler (pure, deterministic)
# --------------------------------------------------------------------------
def test_schedule_score_prefers_lower_cpu_util():
    a = _FakeNode("a", cpu_util=0.1)
    b = _FakeNode("b", cpu_util=0.9)
    assert schedule_score(a) > schedule_score(b)
    assert best_node([a, b]).node_id == "a"


def test_best_node_excludes_offline():
    a = _FakeNode("a", cpu_util=0.1, status=NodeStatus.OFFLINE)
    b = _FakeNode("b", cpu_util=0.9, status=NodeStatus.ALIVE)
    assert best_node([a, b]).node_id == "b"


def test_best_node_exclude_set_skips_victim():
    a = _FakeNode("a")
    b = _FakeNode("b")
    assert best_node([a, b], exclude={"a"}).node_id == "b"


def test_schedule_score_returns_none_for_unschedulable():
    a = _FakeNode("a", status=NodeStatus.OFFLINE)
    b = _FakeNode("b", status=NodeStatus.RECOVERING)
    assert schedule_score(a) is None
    assert schedule_score(b) is None
    assert best_node([a, b]) is None


def test_schedule_weights_can_be_overridden():
    a = _FakeNode("a", cpu_util=0.9)
    b = _FakeNode("b", cpu_util=0.2)
    w = ScheduleWeights(cpu=1.0)
    assert best_node([a, b], weights=w).node_id == "b"


# --------------------------------------------------------------------------
# ClusterStore (async)
# --------------------------------------------------------------------------
@pytest.fixture
def store():
    return ClusterStore(now=_Clock())


async def _seed(store: ClusterStore, n: int = 2):
    for i in range(n):
        await store.register(f"node-{i:05d}", hostname=f"h{i}", cpu_cores=8, ram_gb=16)


async def test_register_and_heartbeat_status(store: ClusterStore):
    await store.register("node-00000", hostname="h0")
    n = await store.heartbeat("node-00000", seq=1)
    assert n.status == NodeStatus.ALIVE
    assert store.node("node-00000").heartbeat_seq == 1


async def test_reconcile_marks_stale_nodes_offline(store: ClusterStore):
    await store.register("node-00000", hostname="h0")
    await store.heartbeat("node-00000", seq=1)
    store._now.advance(settings.HEARTBEAT_GRACE_SECONDS + 1)
    offline = await store.reconcile()
    assert "node-00000" in offline
    assert store.node("node-00000").status == NodeStatus.OFFLINE


async def test_no_failover_while_owner_alive(store: ClusterStore):
    await _seed(store)
    cid = uuid.uuid4()
    await store.assign_camera(cid, owner_node_id="node-00000")
    # put the lease far past TTL -- but owner is ALIVE, so no failover
    store._now.advance(settings.LEASE_TTL_SECONDS + 60)
    transfers = await store.failover_sweep()
    assert transfers == []
    assert store.lease(cid).owner_node_id == "node-00000"


async def test_failover_only_when_owner_offline_and_lease_expired(store: ClusterStore):
    await _seed(store)  # 2 alive nodes
    cid = uuid.uuid4()
    await store.assign_camera(cid, owner_node_id="node-00000")
    await store.deregister("node-00000", graceful=False)
    store._now.advance(settings.LEASE_TTL_SECONDS + 5)
    await store.reconcile()
    transfers = await store.failover_sweep()
    assert len(transfers) == 1
    assert transfers[0]["to_node"] == "node-00001"
    assert store.lease(cid).owner_node_id == "node-00001"


async def test_lease_renewal_cas_bumps_ownership_version(store: ClusterStore):
    await _seed(store)
    cid = uuid.uuid4()
    await store.assign_camera(cid, owner_node_id="node-00000")
    v0 = store.lease(cid).ownership_version
    renewed = await store.renew_lease(cid, "node-00000", version=v0)
    assert renewed is not None
    assert store.lease(cid).ownership_version == v0 + 1


async def test_lease_renewal_rejected_for_wrong_owner(store: ClusterStore):
    await _seed(store)
    cid = uuid.uuid4()
    await store.assign_camera(cid, owner_node_id="node-00000")
    assert await store.renew_lease(cid, "node-00001", version=0) is None


async def test_lease_renewal_rejected_on_version_skew(store: ClusterStore):
    await _seed(store)
    cid = uuid.uuid4()
    await store.assign_camera(cid, owner_node_id="node-00000")
    # stale CAS token -> reject
    assert await store.renew_lease(cid, "node-00000", version=0) is None


async def test_concurrent_failover_no_double_transfer(store: ClusterStore):
    """Two concurrent sweeps must not transfer the same camera twice."""
    await _seed(store)
    cameras = [uuid.uuid4() for _ in range(4)]
    for c in cameras:
        await store.assign_camera(c, owner_node_id="node-00000")
    await store.deregister("node-00000", graceful=False)
    store._now.advance(settings.LEASE_TTL_SECONDS + 5)
    await store.reconcile()
    first, second = await asyncio.gather(
        store.failover_sweep(), store.failover_sweep()
    )
    # exactly all 4 transfer once; second sweep transfers nothing
    assert len(first) == 4
    assert second == []
    for c in cameras:
        assert store.lease(c).owner_node_id == "node-00001"


async def test_owned_cameras_reports_owner(store: ClusterStore):
    await _seed(store)
    cid = uuid.uuid4()
    await store.assign_camera(cid, owner_node_id="node-00000")
    owned = store.owned_cameras("node-00000")
    assert [lease.camera_id for lease in owned] == [cid]
