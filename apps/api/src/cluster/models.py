"""Cluster orchestration persistence models.

These tables hold a **durable snapshot** of the in-memory orchestration state so
the registry, camera ownership and the ownership-transfer log survive a restart.
They are distinct from the live store (see ``store.py``), which is the
authoritative source of truth while the process is running.

No foreign keys point into the Phase 1-6 schema: the cluster package is fully
additive and isolated on its own ``ClusterBase.metadata``.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.cluster.db import ClusterBase


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class NodeStatus(str, enum.Enum):
    ALIVE = "alive"
    UNHEALTHY = "unhealthy"
    OFFLINE = "offline"
    RECOVERING = "recovering"


class FailoverState(str, enum.Enum):
    NONE = "none"
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    TRANSFERRED = "transferred"
    FAILED = "failed"


class ClusterNode(ClusterBase, TimestampMixin):
    """A registered edge processing node (Part 1)."""

    __tablename__ = "cluster_nodes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    node_id: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    hostname: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    region: Mapped[str] = mapped_column(String(64), default="Gujarat", nullable=False)
    district: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    # capabilities (Part 1)
    capabilities: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    gpu_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cpu_cores: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ram_gb: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    version: Mapped[str] = mapped_column(String(32), default="", nullable=False)

    # heartbeat / status (Part 3)
    status: Mapped[NodeStatus] = mapped_column(
        Enum(NodeStatus, name="cluster_node_status", values_callable=lambda e: [m.value for m in e]),
        default=NodeStatus.ALIVE,
        nullable=False,
    )
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    heartbeat_seq: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cpu_util: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    gpu_util: Mapped[float | None] = mapped_column(Float, nullable=True)
    mem_util: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    active_cameras: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Phase 7.2 -- monotonic per-node generation counter, bumped on every mutation
    # (register / heartbeat / reconcile / deregister). It is the optimistic-
    # concurrency (CAS) token for durable cross-process node updates.
    generation: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    synthetic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class ClusterCamera(ClusterBase, TimestampMixin):
    """Camera ownership record (Part 2)."""

    __tablename__ = "cluster_cameras"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    camera_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True, index=True, nullable=False)

    # ownership
    owner_node_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    lease_expiry: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failover_state: Mapped[FailoverState] = mapped_column(
        Enum(
            FailoverState,
            name="cluster_failover_state",
            values_callable=lambda e: [m.value for m in e],
        ),
        default=FailoverState.NONE,
        nullable=False,
    )
    # optimistic concurrency guard for lease/CAS split-brain prevention
    ownership_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Phase 7.2 -- monotonic per-camera generation counter, bumped alongside
    # ownership_version. Combined they form the durable CAS token: a transfer or
    # renewal writes only if the stored generation/version still equals the value
    # the caller observed (conditional UPDATE -> cross-process split-brain guard).
    generation: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    synthetic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class ClusterHeartbeat(ClusterBase):
    """Heartbeat history (Part 3)."""

    __tablename__ = "cluster_heartbeats"
    __table_args__ = (Index("ix_cluster_heartbeat_node_at", "node_id", "received_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    node_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    seq: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="alive", nullable=False)
    cpu_util: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    gpu_util: Mapped[float | None] = mapped_column(Float, nullable=True)
    mem_util: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    active_cameras: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    synthetic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class OwnershipChange(ClusterBase):
    """Audit log of ownership transfers (Part 5 / Part 10 validation)."""

    __tablename__ = "cluster_ownership_changes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    camera_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), index=True, nullable=False
    )
    from_node: Mapped[str | None] = mapped_column(String(128), nullable=True)
    to_node: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    reason: Mapped[str] = mapped_column(String(64), default="failover", nullable=False)
    ownership_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False, index=True
    )
    synthetic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


__all__ = [
    "NodeStatus",
    "FailoverState",
    "ClusterNode",
    "ClusterCamera",
    "ClusterHeartbeat",
    "OwnershipChange",
    "TimestampMixin",
]
