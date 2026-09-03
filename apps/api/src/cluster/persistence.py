"""Optional durability layer for cluster orchestration.

Snapshots the live :class:`ClusterStore` into the isolated cluster database so
the node registry, camera ownership, heartbeat history and the ownership-change
log survive a restart. Additive: nothing reads this back into the live store
(which is the authoritative source of truth while running); it exists purely for
observability and audit.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.cluster.models import (
    ClusterCamera,
    ClusterHeartbeat,
    ClusterNode,
    OwnershipChange,
)
from src.cluster.store import ClusterStore


async def persist_node_registry(db: AsyncSession, store: ClusterStore) -> int:
    """Upsert the node registry from the store. Returns number of nodes written."""
    count = 0
    for node in store.nodes():
        existing = (
            await db.execute(
                select(ClusterNode).where(ClusterNode.node_id == node.node_id)
            )
        ).scalars().first()
        if existing is None:
            existing = ClusterNode(node_id=node.node_id)
            db.add(existing)
        data = node.to_dict()
        existing.hostname = data["hostname"]
        existing.region = data["region"]
        existing.district = data["district"]
        existing.capabilities = data["capabilities"]
        existing.gpu_count = data["gpu_count"]
        existing.cpu_cores = data["cpu_cores"]
        existing.ram_gb = data["ram_gb"]
        existing.version = data["version"]
        existing.cpu_util = data["cpu_util"]
        existing.gpu_util = data["gpu_util"]
        existing.mem_util = data["mem_util"]
        existing.active_cameras = data["active_cameras"]
        existing.heartbeat_seq = data["heartbeat_seq"]
        existing.synthetic = data["synthetic"]
        count += 1
    await db.flush()
    return count


async def persist_camera_registry(db: AsyncSession, store: ClusterStore) -> int:
    """Upsert camera ownership from the store. Returns number of cameras written."""
    count = 0
    for lease in store.leases():
        existing = (
            await db.execute(
                select(ClusterCamera).where(
                    ClusterCamera.camera_id == lease.camera_id
                )
            )
        ).scalars().first()
        if existing is None:
            existing = ClusterCamera(camera_id=lease.camera_id)
            db.add(existing)
        existing.owner_node_id = lease.owner_node_id
        existing.lease_expiry = lease.lease_expiry
        existing.priority = lease.priority
        existing.failover_state = lease.failover_state
        existing.ownership_version = lease.ownership_version
        existing.synthetic = lease.synthetic
        count += 1
    await db.flush()
    return count


async def append_heartbeats(db: AsyncSession, store: ClusterStore, limit: int = 500) -> int:
    """Append the most recent heartbeat records that are not yet persisted.

    Because the in-memory log is not tracked per-row, this action is idempotent
    only at the level of "write the last N". Used for audit/observability.
    """
    rows = store.heartbeat_log(limit=250)
    written = 0
    for hb in rows:
        db.add(
            ClusterHeartbeat(
                node_id=hb["node_id"], seq=hb["seq"], status=hb["status"],
                cpu_util=hb["cpu_util"], gpu_util=hb.get("gpu_util"),
                mem_util=hb["mem_util"], active_cameras=hb["active_cameras"],
                synthetic=hb.get("synthetic", False),
            )
        )
        written += 1
    await db.flush()
    return written


async def persist_ownership_changes(db: AsyncSession, store: ClusterStore) -> int:
    """Persist the ownership-change log (audit of transfers)."""
    rows = store.changes(limit=1000)
    written = 0
    for c in rows:
        db.add(
            OwnershipChange(
                camera_id=uuid.UUID(c["camera_id"]) if c["camera_id"] else uuid.uuid4(),
                from_node=c["from_node"], to_node=c["to_node"], reason=c["reason"],
                ownership_version=c["ownership_version"], synthetic=c["synthetic"],
            )
        )
        written += 1
    await db.flush()
    return written


async def snapshot_to_db(db: AsyncSession, store: ClusterStore) -> dict[str, int]:
    """Write a full snapshot of the store to the cluster DB."""
    return {
        "nodes": await persist_node_registry(db, store),
        "cameras": await persist_camera_registry(db, store),
        "heartbeats": await append_heartbeats(db, store),
        "ownership_changes": await persist_ownership_changes(db, store),
    }


__all__ = [
    "snapshot_to_db",
    "persist_node_registry",
    "persist_camera_registry",
    "append_heartbeats",
    "persist_ownership_changes",
]

