"""Cluster orchestration FastAPI router (Part 8).

Endpoints (all under ``/cluster``):

* ``GET  /cluster/nodes``        -- registered nodes (registry)
* ``GET  /cluster/health``       -- cluster health summary (Part 7)
* ``GET  /cluster/cameras``      -- camera ownership (Part 2)
* ``POST /cluster/register``     -- node join/discovery (Parts 1 & 4)
* ``POST /cluster/heartbeat``    -- node heartbeat (Part 3)

Additive helpers: ``/cluster/dashboard``, ``/cluster/cameras/{id}/lease``
(renewal, Part 2), ``/cluster/failover`` (Part 5) and ``/cluster/ownership``
(transfer log). The router is self-contained and does not touch Phase 1-6
routers.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import UUID4

from src.cluster.schemas import (
    CameraAssignIn,
    CameraLeaseOut,
    CameraRenewIn,
    DashboardOut,
    FailoverOut,
    HealthSummaryOut,
    HeartbeatIn,
    HeartbeatOut,
    NodeOut,
    NodeRegisterIn,
    OwnershipChangeOut,
)
from src.cluster.service import get_service

router = APIRouter(prefix="/cluster", tags=["cluster"])


@router.get("/nodes", response_model=list[NodeOut])
async def list_nodes():
    """Part 1 & 4 -- active node registry."""
    svc = get_service()
    return [n.to_dict() for n in svc.store.nodes()]


@router.get("/nodes/{node_id}", response_model=NodeOut)
async def get_node(node_id: str):
    svc = get_service()
    node = svc.store.node(node_id)
    if node is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Node not found.")
    return node.to_dict()


@router.get("/health", response_model=HealthSummaryOut)
async def cluster_health():
    """Part 7 -- cluster health summary."""
    return get_service().store.health_summary()


@router.get("/cameras", response_model=list[CameraLeaseOut])
async def list_cameras(
    node_id: str | None = Query(default=None, description="Filter by owning node"),
):
    """Part 2 -- camera ownership registry."""
    svc = get_service()
    leases = svc.store.leases()
    if node_id:
        leases = [l for l in leases if l.owner_node_id == node_id]
    return [l.to_dict() for l in leases]


@router.get("/cameras/{camera_id}", response_model=CameraLeaseOut)
async def get_camera(camera_id: UUID4):
    svc = get_service()
    lease = svc.store.lease(uuid.UUID(str(camera_id)))
    if lease is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Camera not owned.")
    return lease.to_dict()


@router.post("/register", response_model=NodeOut, status_code=201)
async def register_node(payload: NodeRegisterIn):
    """Parts 1 & 4 -- a node joins (or re-joins) the cluster."""
    svc = get_service()
    node = await svc.store.register(
        payload.node_id,
        hostname=payload.hostname,
        region=payload.region,
        district=payload.district,
        capabilities=payload.capabilities,
        gpu_count=payload.gpu_count,
        cpu_cores=payload.cpu_cores,
        ram_gb=payload.ram_gb,
        version=payload.version,
        synthetic=payload.synthetic,
    )
    return node.to_dict()


@router.post("/heartbeat", response_model=HeartbeatOut)
async def heartbeat(payload: HeartbeatIn):
    """Part 3 -- receive a node heartbeat; trigger pending failover."""
    svc = get_service()
    node = await svc.store.heartbeat(
        payload.node_id,
        seq=payload.seq,
        cpu_util=payload.cpu_util,
        gpu_util=payload.gpu_util,
        mem_util=payload.mem_util,
        active_cameras=payload.active_cameras,
        synthetic=payload.synthetic,
    )
    transfers = await svc.store.failover_sweep()
    return HeartbeatOut(
        node_id=payload.node_id,
        seq=node.heartbeat_seq,
        status=node.status,
        ack=True,
        failover_pending=len(transfers),
    )


# ---------------------------------------------------------------------------
# Additive helpers
# ---------------------------------------------------------------------------
@router.post("/cameras/assign", response_model=CameraLeaseOut)
async def assign_camera(payload: CameraAssignIn):
    """Part 6 -- schedule a camera to a node (or let the scheduler pick)."""
    svc = get_service()
    if payload.owner_node_id is None:
        lease = await svc.store.schedule_one(uuid.UUID(str(payload.camera_id)))
    else:
        lease = await svc.store.assign_camera(
            uuid.UUID(str(payload.camera_id)),
            owner_node_id=payload.owner_node_id,
            priority=payload.priority,
        )
    if lease is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="No schedulable node available.")
    return lease.to_dict()


@router.post("/cameras/{camera_id}/lease", response_model=CameraLeaseOut)
async def renew_lease(camera_id: UUID4, payload: CameraRenewIn):
    """Part 2 -- lease renewal (split-brain-safe CAS)."""
    svc = get_service()
    lease = await svc.store.renew_lease(
        uuid.UUID(str(camera_id)),
        payload.node_id,
        version=payload.version,
    )
    if lease is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Lease renewal rejected: node is not the owner (version skew).",
        )
    return lease.to_dict()


@router.post("/failover", response_model=FailoverOut)
async def failover(
    camera_id: UUID4 | None = Query(default=None),
    force_node_id: str | None = Query(default=None),
):
    """Part 5 -- force lease-based failover (optionally a specific camera/node)."""
    svc = get_service()
    if camera_id is not None:
        record = await svc.failover_camera(
            uuid.UUID(str(camera_id)), force_node_id=force_node_id
        )
        transferred = [record] if record else []
    else:
        transferred = await svc.store.failover_sweep(force_node_id=force_node_id)
    return FailoverOut(transferred=transferred)


@router.get("/ownership", response_model=list[OwnershipChangeOut])
async def ownership_log(limit: int = Query(default=100, le=1000)):
    return get_service().store.changes(limit=limit)


@router.get("/dashboard", response_model=DashboardOut)
async def dashboard():
    """Part 7 -- health dashboard payload (nodes, heartbeats, capacity)."""
    svc = get_service()
    store = svc.store
    return DashboardOut(
        nodes=[n.to_dict() for n in store.nodes()],
        heartbeats=store.heartbeat_log(limit=100),
        owned_cameras=[l.to_dict() for l in store.leases()],
        capacity=store.health_summary()["capacity"],
        health=store.health_summary(),
    )
