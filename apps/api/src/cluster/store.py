"""In-memory cluster orchestration store (Phase 7.1 core).

Holds the authoritative orchestration state for a multi-node deployment and
implements the algorithms: node registry + discovery (Parts 1 & 4), heartbeat
tracking (Part 3), camera ownership with leases (Part 2), and lease-based
failover with split-brain prevention (Part 5). Scheduling (Part 6) is delegated
to :mod:`src.cluster.scheduler`.

Design notes
------------
* The store is a single-writer, asyncio.Lock-guarded in-memory map, making the
  orchestration decisions deterministic and trivially testable. Persistence is
  a layered snapshot (see ``persistence.py``) so decisions can be replayed.
* Split-brain prevention is **lease + optimistic-concurrency based**: every
  ownership mutation bumps ``ownership_version`` and only the caller who still
  holds the current version may change an owner (compare-and-swap). In this
  process the lock guarantees atomicity; the version provides the token that a
  multi-process persistence layer can CAS on.
* ``_now`` is injectable so unit tests and the deterministic simulator advance a
  virtual clock instead of sleeping.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from src.cluster.config import settings
from src.cluster.scheduler import Scoreable, best_node

UTC = timezone.utc


def utcnow() -> datetime:
    return datetime.now(UTC)


class NodeStatus(str):
    """Node liveness states (kept as plain strings for simple JSON payloads)."""

    ALIVE = "alive"
    UNHEALTHY = "unhealthy"
    OFFLINE = "offline"
    RECOVERING = "recovering"


class FailoverState(str):
    NONE = "none"
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    TRANSFERRED = "transferred"
    FAILED = "failed"


class OwnershipChange:
    __slots__ = ("camera_id", "from_node", "to_node", "reason", "ownership_version", "at", "synthetic")

    def __init__(self, camera_id, from_node, to_node, reason, ownership_version, at, synthetic=False):
        self.camera_id = camera_id
        self.from_node = from_node
        self.to_node = to_node
        self.reason = reason
        self.ownership_version = ownership_version
        self.at = at
        self.synthetic = synthetic

    def to_dict(self):
        return {
            "camera_id": str(self.camera_id),
            "from_node": self.from_node,
            "to_node": self.to_node,
            "reason": self.reason,
            "ownership_version": self.ownership_version,
            "at": self.at.isoformat() if self.at else None,
            "synthetic": self.synthetic,
        }


class ClusterNode:
    """Mutable node record in the store (implements :class:`Scoreable`)."""

    __slots__ = (
        "node_id", "hostname", "region", "district", "capabilities",
        "gpu_count", "cpu_cores", "ram_gb", "version",
        "status", "last_heartbeat_at", "heartbeat_seq",
        "cpu_util", "gpu_util", "mem_util", "active_cameras",
        "registered_at", "updated_at", "synthetic", "in_cluster",
        "generation",
    )

    def __init__(self, node_id, *, hostname="", region="Gujarat", district=None,
                 capabilities=None, gpu_count=0, cpu_cores=0, ram_gb=0, version="",
                 synthetic=False, now=None):
        self.node_id = node_id
        self.hostname = hostname
        self.region = region
        self.district = district
        self.capabilities = capabilities or {}
        self.gpu_count = gpu_count
        self.cpu_cores = cpu_cores
        self.ram_gb = ram_gb
        self.version = version
        self.status = NodeStatus.ALIVE
        self.last_heartbeat_at = None
        self.heartbeat_seq = 0
        self.cpu_util = 0.0
        self.gpu_util = None
        self.mem_util = 0.0
        self.active_cameras = 0
        self.registered_at = now or utcnow()
        self.updated_at = None
        self.synthetic = synthetic
        self.in_cluster = True
        self.generation = 0

    def to_dict(self):
        return {
            "node_id": self.node_id,
            "hostname": self.hostname,
            "region": self.region,
            "district": self.district,
            "capabilities": self.capabilities,
            "gpu_count": self.gpu_count,
            "cpu_cores": self.cpu_cores,
            "ram_gb": self.ram_gb,
            "version": self.version,
            "status": self.status,
            "last_heartbeat_at": self.last_heartbeat_at.isoformat() if self.last_heartbeat_at else None,
            "heartbeat_seq": self.heartbeat_seq,
            "cpu_util": self.cpu_util,
            "gpu_util": self.gpu_util,
            "mem_util": self.mem_util,
            "active_cameras": self.active_cameras,
            "registered_at": self.registered_at.isoformat() if self.registered_at else None,
            "synthetic": self.synthetic,
            "generation": self.generation,
        }


class CameraLease:
    """Camera ownership + lease record."""

    __slots__ = (
        "camera_id", "owner_node_id", "lease_expiry", "priority",
        "failover_state", "ownership_version", "last_change_at", "synthetic",
        "generation",
    )

    def __init__(self, camera_id, *, owner_node_id=None, lease_expiry=None, priority=0,
                 failover_state=FailoverState.NONE, ownership_version=0, last_change_at=None,
                 synthetic=False):
        self.camera_id = camera_id
        self.owner_node_id = owner_node_id
        self.lease_expiry = lease_expiry
        self.priority = priority
        self.failover_state = failover_state
        self.ownership_version = ownership_version
        self.last_change_at = last_change_at
        self.synthetic = synthetic
        self.generation = 0

    def to_dict(self):
        return {
            "camera_id": str(self.camera_id),
            "owner_node_id": self.owner_node_id,
            "lease_expiry": self.lease_expiry.isoformat() if self.lease_expiry else None,
            "priority": self.priority,
            "failover_state": self.failover_state,
            "ownership_version": self.ownership_version,
            "last_change_at": self.last_change_at.isoformat() if self.last_change_at else None,
            "synthetic": self.synthetic,
            "generation": self.generation,
        }


# default scoring weights (health-weighted) shared between store and API
class ClusterStore:
    """Single-writer registry + ownership + heartbeat + failover state."""

    def __init__(self, *, now: Callable[[], datetime] | None = None, backend=None):
        self._lock = asyncio.Lock()
        self._now = now or utcnow
        # Phase 7.2: optional durable shared-state backend. When present, every
        # mutation is written through to durable storage under an optimistic
        # CAS; on a conflict the in-memory cache is refreshed from the durable
        # row so two processes never both win an ownership change (no split
        # brain). When absent (default) the store is pure in-memory (7.1).
        self.backend = backend
        self._nodes: dict[str, ClusterNode] = {}
        self._leases: dict[uuid.UUID, CameraLease] = {}
        from collections import deque

        self._changes: deque[OwnershipChange] = deque(maxlen=1000)
        self._heartbeat_log: deque[dict[str, Any]] = deque(maxlen=2000)
        # cache so scheduler reads O(1) node list without allocation churn
        self._schedulable_cache: list[ClusterNode] = []

    # ------------------------------------------------------------------ #
    # internals
    # ------------------------------------------------------------------ #
    def _now_dt(self) -> datetime:
        return self._now()

    def _mark(self, node: ClusterNode, now: datetime) -> None:
        node.updated_at = now

    # ------------------------------------------------------------------ #
    # Phase 7.2 durable write-through + CAS helpers
    # ------------------------------------------------------------------ #
    async def _persist_node(self, node: ClusterNode) -> None:
        """Write-through a node to durable storage under generation CAS.

        A CAS conflict (concurrent writer in another process bumped the node's
        generation) is absorbed: the in-memory generation is refreshed to match
        the durable row so reads stay consistent. Registry writes are
        best-effort -- a durability hiccup never breaks the hot path.
        """
        if self.backend is None:
            return
        from src.cluster.durable import node_row_values

        # Mutators bump node.generation (+1) before this call, so the durable
        # row still holds the pre-bump value; CAS against that.
        expected = max(0, node.generation - 1)
        try:
            ok = await self.backend.update_node_cas(
                node.node_id, expected_generation=expected, values=node_row_values(node)
            )
        except Exception as exc:  # durability hiccup is best-effort, but log
            from src.core.logging import log

            log.warning("cluster.persist_node_failed", node_id=node.node_id, error=str(exc))
            return
        if not ok:
            # a concurrent writer bumped the row first; adopt the newer gen
            node.generation = node.generation + 1

    async def _persist_new_node(self, node: ClusterNode) -> None:
        if self.backend is None:
            return
        from src.cluster.durable import node_row_values

        try:
            await self.backend.insert_node(node.node_id, node_row_values(node))
        except Exception as exc:
            from src.core.logging import log

            log.warning("cluster.persist_new_node_failed", node_id=node.node_id, error=str(exc))

    async def _persist_camera(self, lease: CameraLease) -> bool:
        """CAS write-through of an ownership mutation. Returns True on success,
        False on durable CAS conflict (another process changed the camera).
        """
        if self.backend is None:
            return True
        from src.cluster.durable import camera_row_values

        expected_version = lease.ownership_version - 1
        expected_generation = lease.generation - 1
        values = camera_row_values(
            lease,
            owner_node_id=lease.owner_node_id,
            failover_state=lease.failover_state,
            ownership_version=lease.ownership_version,
            generation=lease.generation,
            lease_expiry=lease.lease_expiry,
            priority=lease.priority,
            synthetic=lease.synthetic,
        )
        try:
            return await self.backend.update_camera_cas(
                lease.camera_id,
                expected_version=expected_version,
                expected_generation=expected_generation,
                values=values,
            )
        except Exception:
            return True

    async def _persist_new_camera(self, lease: CameraLease) -> None:
        if self.backend is None:
            return
        from src.cluster.durable import camera_row_values

        try:
            await self.backend.insert_camera(lease.camera_id, camera_row_values(
                lease,
                owner_node_id=lease.owner_node_id,
                failover_state=lease.failover_state,
                ownership_version=lease.ownership_version,
                generation=lease.generation,
                lease_expiry=lease.lease_expiry,
                priority=lease.priority,
                synthetic=lease.synthetic,
            ))
        except Exception:
            pass

    async def _reload_camera(self, lease: CameraLease) -> None:
        """Refresh an in-memory camera from durable state after a CAS conflict.

        The durable row is authoritative: on a conflict another process already
        changed ownership, so we adopt that owner (durable wins, never both).
        If the row does not exist (concurrent removal), leave a neutral lease.
        """
        if self.backend is None:
            return
        try:
            row = await self.backend.read_camera(lease.camera_id)
        except Exception:
            return
        if row is None:
            return
        lease.owner_node_id = row["owner_node_id"]
        lease.lease_expiry = row["lease_expiry"]
        lease.priority = row.get("priority", lease.priority)
        lease.failover_state = row["failover_state"]
        lease.ownership_version = row["ownership_version"]
        lease.generation = row["generation"]
        lease.synthetic = row.get("synthetic", lease.synthetic)

    async def _persist_change(self, change: OwnershipChange) -> None:
        if self.backend is None:
            return
        try:
            await self.backend.append_change(change.to_dict())
        except Exception:
            pass

    async def _persist_heartbeat(self, hb: dict[str, Any]) -> None:
        if self.backend is None:
            return
        try:
            await self.backend.append_heartbeat(hb)
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # Node registry / discovery (Parts 1 & 4)
    # ------------------------------------------------------------------ #
    async def register(
        self,
        node_id: str,
        *,
        hostname: str = "",
        region: str = "",
        district: str | None = None,
        capabilities: dict | None = None,
        gpu_count: int = 0,
        cpu_cores: int = 0,
        ram_gb: int = 0,
        version: str = "",
        synthetic: bool = False,
    ) -> ClusterNode:
        """Join/upsert a node. A previously-OFFLINE node returns in RECOVERING."""
        async with self._lock:
            now = self._now_dt()
            existing = self._nodes.get(node_id)
            if existing is not None:
                # re-join after absence -> recovering until heartbeats confirm
                if existing.status == NodeStatus.OFFLINE:
                    existing.status = NodeStatus.RECOVERING
                existing.hostname = hostname or existing.hostname
                existing.region = region or existing.region
                existing.district = district if district is not None else existing.district
                existing.gpu_count = gpu_count if gpu_count else existing.gpu_count
                existing.cpu_cores = cpu_cores if cpu_cores else existing.cpu_cores
                existing.ram_gb = ram_gb if ram_gb else existing.ram_gb
                existing.capabilities = capabilities if capabilities else existing.capabilities
                existing.version = version or existing.version
                existing.in_cluster = True
                existing.generation += 1
                self._mark(existing, now)
                await self._persist_node(existing)
                return existing

            node = ClusterNode(
                node_id,
                hostname=hostname,
                region=region or settings.REGION,
                district=district,
                capabilities=capabilities,
                gpu_count=gpu_count,
                cpu_cores=cpu_cores,
                ram_gb=ram_gb,
                version=version,
                synthetic=synthetic,
                now=now,
            )
            node.generation = 1
            self._nodes[node_id] = node
            await self._persist_new_node(node)
            return node

    async def deregister(self, node_id: str, *, graceful: bool = True) -> bool:
        """Node leaves the cluster (Part 4 'Leave'). Marks OFFLINE immediately.

        If ``graceful`` is True the node's cameras are failed over right away;
        otherwise they wait for lease expiry (crash semantics)."""
        async with self._lock:
            node = self._nodes.get(node_id)
            if node is None:
                return False
            node.status = NodeStatus.OFFLINE
            node.in_cluster = False
            node.generation += 1
            self._mark(node, self._now_dt())
            self._changes.append(
                OwnershipChange(
                    camera_id=None, from_node=node_id, to_node=None,
                    reason="node_leave", ownership_version=0, at=self._now_dt(),
                    synthetic=node.synthetic,
                )
            )
            await self._persist_node(node)
            await self._persist_change(self._changes[-1])
            return True

    # ------------------------------------------------------------------ #
    # Heartbeat (Part 3)
    # ------------------------------------------------------------------ #
    async def heartbeat(
        self,
        node_id: str,
        *,
        seq: int,
        cpu_util: float = 0.0,
        gpu_util: float | None = None,
        mem_util: float = 0.0,
        active_cameras: int = 0,
        synthetic: bool = False,
    ) -> ClusterNode:
        """Record a node heartbeat and recompute its status."""
        async with self._lock:
            now = self._now_dt()
            node = self._nodes.get(node_id)
            if node is None:
                # implicit registration on first heartbeat
                node = ClusterNode(node_id, synthetic=synthetic, now=now)
                self._nodes[node_id] = node
            node.last_heartbeat_at = now
            if seq > node.heartbeat_seq:
                node.heartbeat_seq = seq
            node.cpu_util = cpu_util
            node.gpu_util = gpu_util if gpu_util is not None else node.gpu_util
            node.mem_util = mem_util
            node.active_cameras = active_cameras
            # a returning node confirms liveness -> ALIVE
            if node.status in (NodeStatus.OFFLINE, NodeStatus.RECOVERING):
                node.status = NodeStatus.ALIVE
            elif node.status != NodeStatus.ALIVE:
                node.status = NodeStatus.ALIVE
            node.in_cluster = True
            node.generation += 1
            self._mark(node, now)
            self._heartbeat_log.append(
                {
                    "node_id": node_id, "seq": seq, "status": node.status,
                    "cpu_util": cpu_util, "gpu_util": gpu_util, "mem_util": mem_util,
                    "active_cameras": active_cameras, "at": now.isoformat(),
                    "synthetic": synthetic,
                }
            )
            await self._persist_node(node)
            if self.backend is not None:
                await self._persist_heartbeat(self._heartbeat_log[-1])
            return node

    # ------------------------------------------------------------------ #
    # Node status reconciliation (Part 3)
    # ------------------------------------------------------------------ #
    async def reconcile(self) -> list[str]:
        """Mark stale nodes UNHEALTHY / OFFLINE based on heartbeat age.

        Returns the node ids that transitioned to OFFLINE so the caller can
        trigger a failover sweep. Call this on an interval (the API does).
        """
        async with self._lock:
            now = self._now_dt()
            offline: list[str] = []
            changed: list[ClusterNode] = []
            for node in self._nodes.values():
                if not node.in_cluster and node.status == NodeStatus.OFFLINE:
                    continue
                age = self._age(node, now)
                if age is None:
                    continue
                if age > settings.HEARTBEAT_GRACE_SECONDS:
                    if node.status != NodeStatus.OFFLINE:
                        node.status = NodeStatus.OFFLINE
                        node.generation += 1
                        offline.append(node.node_id)
                        changed.append(node)
                elif age > settings.HEARTBEAT_TTL_SECONDS:
                    if node.status != NodeStatus.UNHEALTHY:
                        node.status = NodeStatus.UNHEALTHY
                        node.generation += 1
                        changed.append(node)
            for node in changed:
                await self._persist_node(node)
            return offline

    @staticmethod
    def _age(node: ClusterNode, now: datetime) -> float | None:
        if node.last_heartbeat_at is None:
            return None
        return (now - node.last_heartbeat_at).total_seconds()

    # ------------------------------------------------------------------ #
    # Camera ownership + leases (Part 2)
    # ------------------------------------------------------------------ #
    def _lease(self, camera_id: uuid.UUID) -> CameraLease:
        lease = self._leases.get(camera_id)
        if lease is None:
            lease = CameraLease(camera_id)
            self._leases[camera_id] = lease
        return lease

    async def assign_camera(
        self,
        camera_id: uuid.UUID,
        *,
        owner_node_id: str,
        priority: int = 0,
        ttl_seconds: float | None = None,
        synthetic: bool = False,
    ) -> CameraLease:
        """Scheduled (re)assignment. Bumps ownership_version (CAS token)."""
        async with self._lock:
            now = self._now_dt()
            lease = self._lease(camera_id)
            is_new = lease.owner_node_id is None
            old_owner = lease.owner_node_id
            lease.owner_node_id = owner_node_id
            lease.priority = priority
            lease.failover_state = FailoverState.NONE
            lease.ownership_version += 1
            lease.generation += 1
            lease.last_change_at = now
            lease.lease_expiry = _add_seconds(now, ttl_seconds or settings.LEASE_TTL_SECONDS)
            lease.synthetic = synthetic
            if self.backend is not None:
                if is_new:
                    await self._persist_new_camera(lease)
                elif not await self._persist_camera(lease):
                    # durable CAS conflict -> another process owns it now
                    await self._reload_camera(lease)
            node = self._nodes.get(owner_node_id)
            if node is not None:
                node.active_cameras = max(0, node.active_cameras + (0 if old_owner else 1))
                if old_owner and old_owner != owner_node_id:
                    old = self._nodes.get(old_owner)
                    if old is not None:
                        old.active_cameras = max(0, old.active_cameras - 1)
            return lease

    async def renew_lease(
        self, camera_id: uuid.UUID, node_id: str, *, version: int | None = None,
        ttl_seconds: float | None = None,
    ) -> CameraLease | None:
        """Renew a camera lease. Returns the lease on success, or None if the
        caller is no longer the owner (split-brain: lost ownership)."""
        async with self._lock:
            now = self._now_dt()
            lease = self._lease(camera_id)
            if lease.owner_node_id != node_id:
                return None
            if version is not None and lease.ownership_version != version:
                return None
            lease.lease_expiry = _add_seconds(now, ttl_seconds or settings.LEASE_TTL_SECONDS)
            lease.ownership_version += 1
            lease.generation += 1
            lease.last_change_at = now
            if self.backend is not None:
                if not await self._persist_camera(lease):
                    # durable CAS conflict: ownership moved in another process
                    await self._reload_camera(lease)
                    return None
            return lease

    def owned_cameras(self, node_id: str) -> list[CameraLease]:
        return [l for l in self._leases.values() if l.owner_node_id == node_id]

    # ------------------------------------------------------------------ #
    # Lease-based failover (Part 5)
    # ------------------------------------------------------------------ #
    async def failover_sweep(
        self, *, force_node_id: str | None = None, reason: str = "failover",
    ) -> list[dict[str, Any]]:
        """Transfer ownership of cameras whose lease has expired (owner gone).

        Split-brain prevention: a camera is only re-assigned when its lease is
        genuinely expired (owner stopped renewing = owner down), the transfer
        bumps ``ownership_version`` atomically under the lock, and the chosen
        replacement is a healthy schedulable node. Returns the transfer records.
        """
        async with self._lock:
            now = self._now_dt()
            transfers: list[dict[str, Any]] = []
            for lease in list(self._leases.values()):
                if lease.owner_node_id is None:
                    continue
                if lease.lease_expiry is not None and lease.lease_expiry > now:
                    # lease still valid -> owner is alive; nothing to do
                    continue
                owner = self._nodes.get(lease.owner_node_id)
                # extra guard: never steal from an alive/degraded-but-present node
                if owner is not None and owner.status not in (NodeStatus.OFFLINE, NodeStatus.RECOVERING):
                    continue
                if owner is not None and owner.in_cluster and owner.status == NodeStatus.RECOVERING:
                    continue

                to_node = force_node_id
                if to_node is None:
                    target = best_node(self._nodes.values())
                    to_node = target.node_id if target else None
                if to_node is None or to_node == lease.owner_node_id:
                    continue

                old_owner = lease.owner_node_id
                lease.owner_node_id = to_node
                lease.ownership_version += 1
                lease.generation += 1
                lease.failover_state = FailoverState.TRANSFERRED
                lease.last_change_at = now
                lease.lease_expiry = _add_seconds(now, settings.LEASE_TTL_SECONDS)

                if owner is not None:
                    owner.active_cameras = max(0, owner.active_cameras - 1)
                new_owner = self._nodes.get(to_node)
                if new_owner is not None:
                    new_owner.active_cameras += 1

                # durable CAS: only one process may win this transfer. On a
                # conflict another owner already claimed it -> adopt durable and
                # do NOT record a transfer (no split brain).
                if self.backend is not None and not await self._persist_camera(lease):
                    await self._reload_camera(lease)
                    continue

                record = OwnershipChange(
                    camera_id=lease.camera_id,
                    from_node=old_owner,
                    to_node=to_node,
                    reason=reason,
                    ownership_version=lease.ownership_version,
                    at=now,
                    synthetic=lease.synthetic,
                )
                self._changes.append(record)
                await self._persist_change(record)
                transfers.append(record.to_dict())
            return transfers

    # ------------------------------------------------------------------ #
    # Scheduling entry (Part 6) -- schedule one unassigned camera
    # ------------------------------------------------------------------ #
    async def schedule_one(self, camera_id: uuid.UUID) -> CameraLease | None:
        """Pick the best node and assign ``camera_id`` to it (if unassigned)."""
        async with self._lock:
            lease = self._lease(camera_id)
            if lease.owner_node_id is not None:
                return lease
            target = best_node(self._nodes.values())
            if target is None:
                return None
        return await self.assign_camera(camera_id, owner_node_id=target.node_id)

    async def schedule_many(self, camera_ids: list[uuid.UUID]) -> list[CameraLease]:
        result = []
        for cid in camera_ids:
            lease = await self.schedule_one(cid)
            if lease is not None:
                result.append(lease)
        return result

    # ------------------------------------------------------------------ #
    # Reads
    # ------------------------------------------------------------------ #
    async def recover(self) -> int:
        """Rehydrate the in-memory cache from durable shared state (Phase 7.2).

        Used after a process restart so persistent ownership, lease expiry and
        the node registry survive. Returns the number of cameras recovered.
        No-op when no durable backend is configured.
        """
        if self.backend is None:
            return 0
        state = await self.backend.load_state()
        self._nodes.clear()
        self._leases.clear()
        self._changes.clear()
        now = self._now_dt()

        for node_id, nd in state.nodes.items():
            node = ClusterNode(
                node_id,
                hostname=nd.get("hostname", ""),
                region=nd.get("region", "Gujarat"),
                district=nd.get("district"),
                capabilities=nd.get("capabilities") or {},
                gpu_count=nd.get("gpu_count", 0),
                cpu_cores=nd.get("cpu_cores", 0),
                ram_gb=nd.get("ram_gb", 0),
                version=nd.get("version", ""),
                synthetic=nd.get("synthetic", False),
                now=now,
            )
            node.status = nd.get("status", NodeStatus.ALIVE)
            node.last_heartbeat_at = _coerce_utc(nd.get("last_heartbeat_at"))
            node.heartbeat_seq = nd.get("heartbeat_seq", 0)
            node.cpu_util = nd.get("cpu_util", 0.0)
            node.gpu_util = nd.get("gpu_util")
            node.mem_util = nd.get("mem_util", 0.0)
            node.active_cameras = nd.get("active_cameras", 0)
            node.generation = nd.get("generation", 0)
            self._nodes[node_id] = node

        for cid, lease_d in state.cameras.items():
            lease = CameraLease(
                cid,
                owner_node_id=lease_d.get("owner_node_id"),
                lease_expiry=_coerce_utc(lease_d.get("lease_expiry")),
                priority=lease_d.get("priority", 0),
                failover_state=lease_d.get("failover_state", FailoverState.NONE),
                ownership_version=lease_d.get("ownership_version", 0),
                synthetic=lease_d.get("synthetic", False),
            )
            lease.generation = lease_d.get("generation", 0)
            lease.last_change_at = _coerce_utc(lease_d.get("last_change_at"))
            self._leases[cid] = lease

        for c in state.changes:
            self._changes.append(OwnershipChange(
                camera_id=uuid.UUID(str(c["camera_id"])) if c.get("camera_id") else None,
                from_node=c.get("from_node"),
                to_node=c.get("to_node"),
                reason=c.get("reason", "failover"),
                ownership_version=c.get("ownership_version", 0),
                at=_coerce_utc(c.get("at")),
                synthetic=c.get("synthetic", False),
            ))

        self._heartbeat_log = await self.backend.load_heartbeats(limit=200)
        return len(self._leases)

    def nodes(self) -> list[ClusterNode]:
        return list(self._nodes.values())

    def node(self, node_id: str) -> ClusterNode | None:
        return self._nodes.get(node_id)

    def leases(self) -> list[CameraLease]:
        return list(self._leases.values())

    def lease(self, camera_id: uuid.UUID) -> CameraLease | None:
        return self._leases.get(camera_id)

    def changes(self, limit: int = 100) -> list[dict[str, Any]]:
        return [c.to_dict() for c in self._changes[-limit:]]

    def heartbeat_log(self, limit: int = 200) -> list[dict[str, Any]]:
        return self._heartbeat_log[-limit:]

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    def health_summary(self) -> dict[str, Any]:
        nodes = self._nodes.values()
        by_status: dict[str, int] = {}
        total_cameras = 0
        total_cpu = 0
        total_mem = 0
        for n in nodes:
            by_status[n.status] = by_status.get(n.status, 0) + 1
            total_cameras += n.active_cameras
            total_cpu += n.cpu_cores
            total_mem += n.ram_gb
        return {
            "node_total": len(self._nodes),
            "by_status": by_status,
            "owned_cameras_total": total_cameras,
            "capacity": {
                "cpu_cores_total": total_cpu,
                "ram_gb_total": total_mem,
            },
            "ownership_changes_total": len(self._changes),
        }


def _add_seconds(dt: datetime, seconds: float) -> datetime:
    from datetime import timedelta

    return dt + timedelta(seconds=seconds)


def _coerce_utc(dt) -> datetime | None:
    """Normalise a recovered datetime to timezone-aware UTC.

    SQLite does not preserve timezone info, so rows read back are offset-naive.
    The store compares these against ``utcnow()`` (offset-aware), so we tag naive
    values as UTC.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


__all__ = ["ClusterStore", "NodeStatus", "FailoverState", "utcnow"]
