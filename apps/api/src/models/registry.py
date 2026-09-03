"""Statewide CCTV Registry — global camera registry foundation (Model 1).

All tables here are ADDITIVE. Phase 1..5 models (Camera, User, alert, incident,
stream, inference, anpr, vehicle_intel, copilot) are intentionally left
untouched. The registry extends the platform with two additive tables that
reference the existing ``cameras`` and ``users`` tables by UUID:

* ``camera_registry`` — one row per managed camera carrying the global
  identity (unique CCTV code), regulatory/enum fields, ownership scoping
  (state / department / district / board), and GIS metadata (lat/lng plus a
  PostGIS point rendered as plain floats for portability).
* ``camera_audit_log`` — append-only audit trail for create / update /
  delete / maintenance / health / ownership events.

Latitude/longitude are stored as plain floats (portable, no spatial extension
required). A GeoAlchemy2 ``Geometry`` column is *available* in production via
the companion SQL migration, but the working engine relies exclusively on
pure-Python GIS math so it runs anywhere (including the test container).
"""

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class AccessRole(str, enum.Enum):
    """The six registry roles (additive RBAC layer).

    Maps onto the existing :class:`UserRole` for the three that overlap and
    introduces the three governance roles. Role rank (state > department >
    district > operator/maintenance > viewer) is enforced in
    :mod:`src.registry.roles`.
    """

    STATE_ADMIN = "state_admin"
    DEPARTMENT_ADMIN = "department_admin"
    DISTRICT_ADMIN = "district_admin"
    OPERATOR = "operator"
    MAINTENANCE = "maintenance"
    VIEWER = "viewer"


class OwnershipType(str, enum.Enum):
    STATE = "state"
    DEPARTMENT = "department"
    DISTRICT = "district"
    MUNICIPALITY = "municipality"
    PRIVATE = "private"


class CameraCategory(str, enum.Enum):
    HIGHWAY = "highway"
    CITY = "city"
    JUNCTION = "junction"
    TOLL = "toll"
    SIGNAL = "signal"
    PUBLIC_PLACE = "public_place"
    CRITICAL = "critical_infrastructure"
    INTERCEPTOR = "interceptor"
    PAN_TILT_ZOOM = "ptz"


class RegistryEventType(str, enum.Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    MAINTENANCE = "maintenance"
    HEALTH = "health"
    OWNERSHIP = "ownership"
    BULK_IMPORT = "bulk_import"


class CameraRegistry(Base, TimestampMixin):
    """Additive global registry record keyed 1:1 to a :class:`Camera`."""

    __tablename__ = "camera_registry"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    camera_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cameras.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    # Global unique identity code, e.g. "IN-GJ-AHM-JCT-000123".
    cctv_code: Mapped[str] = mapped_column(String(40), unique=True, index=True, nullable=False)
    serial_number: Mapped[str | None] = mapped_column(String(80), index=True, nullable=True)
    make: Mapped[str | None] = mapped_column(String(60), nullable=True)
    model: Mapped[str | None] = mapped_column(String(80), nullable=True)
    firmware: Mapped[str | None] = mapped_column(String(60), nullable=True)

    # Regulatory / placement attributes.
    category: Mapped[CameraCategory] = mapped_column(
        Enum(
            CameraCategory,
            name="camera_category",
            values_callable=lambda e: [m.value for m in e],
        ),
        default=CameraCategory.CITY,
        nullable=False,
    )
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    mac_address: Mapped[str | None] = mapped_column(String(20), nullable=True)
    vendor_id: Mapped[str | None] = mapped_column(String(60), nullable=True)

    # Ownership + governance scoping (RBAC territory).
    ownership_type: Mapped[OwnershipType] = mapped_column(
        Enum(
            OwnershipType,
            name="camera_ownership_type",
            values_callable=lambda e: [m.value for m in e],
        ),
        default=OwnershipType.STATE,
        nullable=False,
    )
    state_code: Mapped[str] = mapped_column(String(8), default="GJ", index=True, nullable=False)
    district_code: Mapped[str] = mapped_column(String(12), index=True, nullable=False)
    department_code: Mapped[str | None] = mapped_column(String(20), index=True, nullable=True)
    board_code: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Geo reference (portable floats; PostGIS point available in production).
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    gis_layer: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    cluster_key: Mapped[str | None] = mapped_column(String(80), index=True, nullable=True)

    # Coverage / visibility defaults.
    coverage_radius_m: Mapped[float] = mapped_column(Float, default=250.0, nullable=False)
    elevation_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    height_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    orientation_deg: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Statistics (fed by health job / live probes — plain ints for cheap reads).
    last_health_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    uptime_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Bookkeeping.
    registered_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<CameraRegistry id={self.id} code={self.cctv_code!r} district={self.district_code!r}>"


class CameraAuditLog(Base):
    """Append-only audit trail for registry events and ownership changes."""

    __tablename__ = "camera_audit_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    camera_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cameras.id", ondelete="SET NULL"), index=True, nullable=True
    )
    registry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("camera_registry.id", ondelete="SET NULL"), index=True, nullable=True
    )
    cctv_code: Mapped[str | None] = mapped_column(String(40), index=True, nullable=True)
    event_type: Mapped[RegistryEventType] = mapped_column(
        Enum(
            RegistryEventType,
            name="registry_event_type",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    actor_role: Mapped[str | None] = mapped_column(String(24), nullable=True)
    scope: Mapped[str | None] = mapped_column(String(40), nullable=True)
    summary: Mapped[str] = mapped_column(String(255), nullable=False)
    before: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    after: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<CameraAuditLog id={self.id} event={self.event_type.value} code={self.cctv_code!r}>"


__all__: list[str] = [
    "AccessRole",
    "CameraAuditLog",
    "CameraCategory",
    "CameraRegistry",
    "OwnershipType",
    "RegistryEventType",
    "Any",
]
