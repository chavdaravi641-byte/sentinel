"""Cluster orchestration service (Phase 7.1 --> Phase 7.2).

Wraps the :class:`ClusterStore` with a process-wide singleton, a background
maintenance loop (heartbeat reconciliation + lease-based failover) and optional
self-registration for the local node.

The service is intentionally broker-free: heartbeats arrive via the REST API
(``POST /cluster/heartbeat``) and the maintenance loop owns reconciliation and
failover. Single-node deployments are unaffected -- if no remote node ever
registers, the store simply contains this one node.

Phase 7.2: durable shared state. :func:`install_durable_cluster` binds the store
to the shared cluster DB and recovers persistent ownership on startup, so a
restarted process sees the same registry, leases and ownership log.
"""

from __future__ import annotations

import asyncio
import socket
from threading import Lock
from typing import Any

from src.cluster.config import settings
from src.cluster.store import ClusterStore
from src.core.logging import log

_STORE: ClusterStore | None = None
_SERVICE: "ClusterService | None" = None
_STORE_LOCK = Lock()


def get_store() -> ClusterStore:
    global _STORE
    if _STORE is None:
        with _STORE_LOCK:
            if _STORE is None:
                _STORE = ClusterStore()
    return _STORE


def get_service() -> "ClusterService":
    global _STORE, _SERVICE
    if _SERVICE is None:
        with _STORE_LOCK:
            if _SERVICE is None:
                if _STORE is None:
                    _STORE = ClusterStore()
                _SERVICE = ClusterService(_STORE)
    return _SERVICE


async def install_durable_cluster() -> bool:
    """Phase 7.2 -- install a durable-backed cluster store as the singleton.

    Binds the store to the shared cluster DB, recovers persistent state into it
    (node restart / ownership persistence) and installs a fresh :class:`Service`.
    Returns True on success, False if durability could not be initialised (in
    which case the caller keeps the default in-memory store --- single-node and
    small deployments still work exactly as in Phase 7.1).
    """
    global _STORE, _SERVICE
    try:
        from src.cluster.db import AsyncSessionLocal
        from src.cluster.durable import DurableClusterBackend

        backend = DurableClusterBackend(AsyncSessionLocal)
        store = ClusterStore(backend=backend)
        await store.recover()
        with _STORE_LOCK:
            _STORE = store
            _SERVICE = ClusterService(store)
        return True
    except Exception as exc:
        log.warning("cluster.install_durable_failed", error=str(exc), exc_info=True)
        return False


class ClusterService:
    """Operational facade over a :class:`ClusterStore` plus lifecycle."""

    def __init__(self, store: ClusterStore):
        self.store = store
        self._maintenance_task: asyncio.Task | None = None
        self._started = False
        self._failover_count = 0

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    async def start(self) -> None:
        if self._started:
            return
        self._started = True
        # Optional self-registration.
        if settings.NODE_ID:
            hostname = settings.HOSTNAME or socket.gethostname()
            await self.store.register(
                settings.NODE_ID,
                hostname=hostname,
                region=settings.REGION,
                district=settings.DISTRICT or None,
                version=settings.VERSION,
            )
        self._maintenance_task = asyncio.create_task(self._maintenance_loop(), name="cluster-maintenance")
        return None

    async def stop(self) -> None:
        if not self._started:
            return
        self._started = False
        if self._maintenance_task is not None:
            self._maintenance_task.cancel()
            try:
                await self._maintenance_task
            except asyncio.CancelledError:
                pass
            self._maintenance_task = None
        return None

    async def _maintenance_loop(self) -> None:
        interval = settings.FAILOVER_CHECK_INTERVAL_SECONDS
        while True:
            try:
                await self.store.reconcile()
                transfers = await self.store.failover_sweep()
                if transfers:
                    self._failover_count += len(transfers)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.error("cluster.maintenance_failed", error=str(exc), exc_info=True)
            await asyncio.sleep(interval)

    # ------------------------------------------------------------------ #
    # Failover helpers (used by the API + simulator)
    # ------------------------------------------------------------------ #
    async def failover_camera(
        self, camera_id, *, force_node_id: str | None = None, reason: str = "failover"
    ) -> dict[str, Any] | None:
        """Immediately fail over a single camera (optionally to a fixed node)."""
        transfers = await self.store.failover_sweep(force_node_id=force_node_id, reason=reason)
        for t in transfers:
            if str(t["camera_id"]) == str(camera_id):
                return t
        # camera not eligible (lease still valid / no healthy target)
        return None

    def status(self) -> dict[str, Any]:
        return self.store.health_summary()

    @property
    def failover_count(self) -> int:
        return self._failover_count


__all__ = ["ClusterService", "get_service", "get_store", "install_durable_cluster"]
