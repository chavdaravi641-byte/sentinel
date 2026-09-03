"""Durable shared cluster state (Phase 7.2).

Phase 7.1 kept the authoritative orchestration state in process memory and only
*snapshotted* it to the cluster database. Phase 7.2 moves ownership into shared
durable state: the registry, camera leases and ownership log live in the cluster
DB and become the source of truth, so a restarted process can recover persistent
ownership and two processes writing to the same DB cannot create a split brain.

The backend exposes optimistic-concurrency (CAS) primitives that are *atomic in
the database*:

* ``update_node_cas`` / ``insert_node`` -- node registry writes guarded by the
  per-node ``generation``.
* ``update_camera_cas`` / ``insert_camera`` -- ownership writes guarded by
  ``ownership_version`` **and** ``generation``. A conditional UPDATE affects zero
  rows if the stored version no longer equals the caller's observed version, so
  concurrent failovers of the same camera never both win.

``load_state`` rehydrates the full durable view (nodes, cameras, changes,
heartbeats) so :meth:`ClusterStore.recover` can rebuild a process's in-memory
cache after a restart -- this is node restart, lease recovery and ownership
persistence.

The in-memory ``ClusterStore`` remains the hot read cache; the DB is the
authoritative CAS arbiter. When no backend is configured the store behaves
exactly as in Phase 7.1 (pure in-memory), preserving backward compatibility.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.cluster.models import (
    ClusterCamera,
    ClusterHeartbeat,
    ClusterNode,
    OwnershipChange,
)
from src.cluster.store import NodeStatus


@dataclass
class RecoveredState:
    """A full snapshot of durable state used to rehydrate a process."""

    nodes: dict[str, dict[str, Any]] = field(default_factory=dict)
    cameras: dict[uuid.UUID, dict[str, Any]] = field(default_factory=dict)
    changes: list[dict[str, Any]] = field(default_factory=list)
    heartbeats: list[dict[str, Any]] = field(default_factory=list)


class DurableClusterBackend:
    """Async, DB-backed CAS store for cluster orchestration state.

    ``session_factory`` is an async sessionmaker bound to the durable cluster DB.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._sf = session_factory

    # ------------------------------------------------------------------ #
    # Node registry -- CAS by generation
    # ------------------------------------------------------------------ #
    async def update_node_cas(
        self, node_id: str, *, expected_generation: int, values: dict[str, Any]
    ) -> bool:
        """Conditional node update; affects 0 rows if generation changed.

        Returns True if the update applied (no concurrent writer), False if a
        concurrent writer bumped the generation first (split-brain guard).
        """
        async with self._sf() as session:
            stmt = (
                update(ClusterNode)
                .where(ClusterNode.node_id == node_id)
                .where(ClusterNode.generation == expected_generation)
                .values(**values)
            )
            res = await session.execute(stmt)
            await session.commit()
            return res.rowcount == 1

    async def insert_node(self, node_id: str, values: dict[str, Any]) -> None:
        async with self._sf() as session:
            session.add(ClusterNode(node_id=node_id, generation=values.get("generation", 0)))
            await _apply_node_values(session, node_id, values)
            await session.commit()

    async def touch_node_generation(self, node_id: str) -> int | None:
        """Bump a node's generation unconditionally; returns the new generation."""
        async with self._sf() as session:
            row = (
                await session.execute(
                    select(ClusterNode).where(ClusterNode.node_id == node_id)
                )
            ).scalars().first()
            if row is None:
                await session.rollback()
                return None
            row.generation += 1
            await session.commit()
            return row.generation

    # ------------------------------------------------------------------ #
    # Camera ownership -- CAS by ownership_version + generation
    # ------------------------------------------------------------------ #
    async def update_camera_cas(
        self,
        camera_id: uuid.UUID,
        *,
        expected_version: int,
        expected_generation: int,
        values: dict[str, Any],
    ) -> bool:
        """Conditional camera update (ownership CAS). Affects 0 rows on conflict."""
        async with self._sf() as session:
            stmt = (
                update(ClusterCamera)
                .where(ClusterCamera.camera_id == camera_id)
                .where(ClusterCamera.ownership_version == expected_version)
                .where(ClusterCamera.generation == expected_generation)
                .values(**values)
            )
            res = await session.execute(stmt)
            await session.commit()
            return res.rowcount == 1

    async def insert_camera(self, camera_id: uuid.UUID, values: dict[str, Any]) -> None:
        async with self._sf() as session:
            session.add(
                ClusterCamera(
                    camera_id=camera_id,
                    ownership_version=values.get("ownership_version", 0),
                    generation=values.get("generation", 0),
                )
            )
            await _apply_camera_values(session, camera_id, values)
            await session.commit()

    async def read_camera(self, camera_id: uuid.UUID) -> dict[str, Any] | None:
        """Read a camera row (for recovery/conflict refresh)."""
        async with self._sf() as session:
            row = (
                await session.execute(
                    select(ClusterCamera).where(ClusterCamera.camera_id == camera_id)
                )
            ).scalars().first()
            if row is None:
                return None
            return _camera_to_dict(row)

    # ------------------------------------------------------------------ #
    # Heartbeat + change log (append-only, idempotent per caller)
    # ------------------------------------------------------------------ #
    async def append_heartbeat(self, hb: dict[str, Any]) -> None:
        async with self._sf() as session:
            session.add(
                ClusterHeartbeat(
                    node_id=hb["node_id"], seq=hb.get("seq", 0),
                    status=hb.get("status", "alive"),
                    cpu_util=hb.get("cpu_util", 0.0),
                    gpu_util=hb.get("gpu_util"),
                    mem_util=hb.get("mem_util", 0.0),
                    active_cameras=hb.get("active_cameras", 0),
                    synthetic=hb.get("synthetic", False),
                )
            )
            await session.commit()

    async def append_change(self, change: dict[str, Any]) -> None:
        async with self._sf() as session:
            cid = change.get("camera_id")
            session.add(
                OwnershipChange(
                    camera_id=uuid.UUID(str(cid)) if cid else uuid.uuid4(),
                    from_node=change.get("from_node"),
                    to_node=change.get("to_node") or "",
                    reason=change.get("reason", "failover"),
                    ownership_version=change.get("ownership_version", 0),
                    synthetic=change.get("synthetic", False),
                )
            )
            await session.commit()

    async def clear(self) -> None:
        """Drop all durable cluster rows (used by validation/tests)."""
        async with self._sf() as session:
            await session.execute(delete(ClusterHeartbeat))
            await session.execute(delete(OwnershipChange))
            await session.execute(delete(ClusterCamera))
            await session.execute(delete(ClusterNode))
            await session.commit()

    # ------------------------------------------------------------------ #
    # Load for recovery
    # ------------------------------------------------------------------ #
    async def load_state(self) -> RecoveredState:
        """Load the full durable view for recovery/restart."""
        state = RecoveredState()
        async with self._sf() as session:
            for row in (
                await session.execute(select(ClusterNode).order_by(ClusterNode.node_id))
            ).scalars():
                state.nodes[row.node_id] = _node_to_dict(row)
            for row in (
                await session.execute(select(ClusterCamera).order_by(ClusterCamera.camera_id))
            ).scalars():
                state.cameras[row.camera_id] = _camera_to_dict(row)
            for row in (
                await session.execute(
                    select(OwnershipChange).order_by(OwnershipChange.at)
                )
            ).scalars():
                state.changes.append(_change_to_dict(row))
        return state

    async def load_heartbeats(self, limit: int = 200) -> list[dict[str, Any]]:
        async with self._sf() as session:
            rows = (
                await session.execute(
                    select(ClusterHeartbeat).order_by(ClusterHeartbeat.received_at.desc()).limit(limit)
                )
            ).scalars()
            return [
                {
                    "node_id": h.node_id, "seq": h.seq, "status": h.status,
                    "cpu_util": h.cpu_util, "gpu_util": h.gpu_util,
                    "mem_util": h.mem_util, "active_cameras": h.active_cameras,
                    "at": h.received_at.isoformat() if h.received_at else None,
                    "synthetic": h.synthetic,
                }
                for h in rows
            ]


# ---------------------------------------------------------------------------
# serialisation helpers (store record <-> ORM row values)
# ---------------------------------------------------------------------------
def node_row_values(node) -> dict[str, Any]:
    return {
        "hostname": node.hostname,
        "region": node.region,
        "district": node.district,
        "capabilities": node.capabilities,
        "gpu_count": node.gpu_count,
        "cpu_cores": node.cpu_cores,
        "ram_gb": node.ram_gb,
        "version": node.version,
        "status": node.status,
        "last_heartbeat_at": node.last_heartbeat_at,
        "heartbeat_seq": node.heartbeat_seq,
        "cpu_util": node.cpu_util,
        "gpu_util": node.gpu_util,
        "mem_util": node.mem_util,
        "active_cameras": node.active_cameras,
        "generation": node.generation,
        "synthetic": node.synthetic,
    }


def camera_row_values(lease, *, owner_node_id, failover_state, ownership_version,
                      generation, lease_expiry, priority, synthetic) -> dict[str, Any]:
    return {
        "owner_node_id": owner_node_id,
        "lease_expiry": lease_expiry,
        "priority": priority,
        "failover_state": failover_state,
        "ownership_version": ownership_version,
        "generation": generation,
        "synthetic": synthetic,
    }


async def _apply_node_values(session: AsyncSession, node_id: str, values: dict[str, Any]) -> None:
    vals = {k: v for k, v in values.items() if k in _NODE_FIELDS}
    for k, v in vals.items():
        setattr(
            (await session.execute(select(ClusterNode).where(ClusterNode.node_id == node_id)))
            .scalars().first(),
            k, v,
        )


async def _apply_camera_values(session: AsyncSession, camera_id: uuid.UUID, values: dict[str, Any]) -> None:
    row = (
        await session.execute(select(ClusterCamera).where(ClusterCamera.camera_id == camera_id))
    ).scalars().first()
    for k, v in values.items():
        if k in _CAMERA_FIELDS:
            setattr(row, k, v)


_NODE_FIELDS = {
    "hostname", "region", "district", "capabilities", "gpu_count", "cpu_cores",
    "ram_gb", "version", "status", "last_heartbeat_at", "heartbeat_seq",
    "cpu_util", "gpu_util", "mem_util", "active_cameras", "generation", "synthetic",
}

_CAMERA_FIELDS = {
    "owner_node_id", "lease_expiry", "priority", "failover_state",
    "ownership_version", "generation", "synthetic",
}


def _node_to_dict(row) -> dict[str, Any]:
    return {
        "node_id": row.node_id,
        "hostname": row.hostname,
        "region": row.region,
        "district": row.district,
        "capabilities": row.capabilities,
        "gpu_count": row.gpu_count,
        "cpu_cores": row.cpu_cores,
        "ram_gb": row.ram_gb,
        "version": row.version,
        "status": row.status if isinstance(row.status, str) else row.status.value,
        "last_heartbeat_at": row.last_heartbeat_at,
        "heartbeat_seq": row.heartbeat_seq,
        "cpu_util": row.cpu_util,
        "gpu_util": row.gpu_util,
        "mem_util": row.mem_util,
        "active_cameras": row.active_cameras,
        "generation": row.generation,
        "synthetic": row.synthetic,
    }


def _camera_to_dict(row) -> dict[str, Any]:
    return {
        "camera_id": row.camera_id,
        "owner_node_id": row.owner_node_id,
        "lease_expiry": row.lease_expiry,
        "priority": row.priority,
        "failover_state": row.failover_state if isinstance(row.failover_state, str) else row.failover_state.value,
        "ownership_version": row.ownership_version,
        "generation": row.generation,
        "synthetic": row.synthetic,
    }


def _change_to_dict(row) -> dict[str, Any]:
    return {
        "camera_id": str(row.camera_id),
        "from_node": row.from_node,
        "to_node": row.to_node,
        "reason": row.reason,
        "ownership_version": row.ownership_version,
        "at": row.at,
        "synthetic": row.synthetic,
    }


__all__ = [
    "DurableClusterBackend",
    "RecoveredState",
    "node_row_values",
    "camera_row_values",
]
