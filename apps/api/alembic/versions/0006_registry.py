"""phase 6 registry schema: camera_registry, camera_audit_log

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-01 00:00:00.000000

All tables are additive — Phase 1..5 tables are untouched. Statuses/categories
use plain enum-backed columns (values_stored: value text), matching the
established migration strategy. Lat/lng are stored as portable floats; the
companion ``postgis_view.sql`` offers an optional production spatial index.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- camera_registry ----------------------------------------------------
    op.create_table(
        "camera_registry",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("camera_id", sa.UUID(), nullable=False),
        sa.Column("cctv_code", sa.String(length=40), nullable=False),
        sa.Column("serial_number", sa.String(length=80), nullable=True),
        sa.Column("make", sa.String(length=60), nullable=True),
        sa.Column("model", sa.String(length=80), nullable=True),
        sa.Column("firmware", sa.String(length=60), nullable=True),
        sa.Column("category", sa.String(length=24), nullable=False, server_default="city"),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("mac_address", sa.String(length=20), nullable=True),
        sa.Column("vendor_id", sa.String(length=60), nullable=True),
        sa.Column("ownership_type", sa.String(length=16), nullable=False, server_default="state"),
        sa.Column("state_code", sa.String(length=8), nullable=False, server_default="GJ"),
        sa.Column("district_code", sa.String(length=12), nullable=False),
        sa.Column("department_code", sa.String(length=20), nullable=True),
        sa.Column("board_code", sa.String(length=20), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("gis_layer", sa.String(length=32), nullable=True),
        sa.Column("cluster_key", sa.String(length=80), nullable=True),
        sa.Column("coverage_radius_m", sa.Float(), nullable=False, server_default=sa.text("250")),
        sa.Column("elevation_m", sa.Float(), nullable=True),
        sa.Column("height_m", sa.Float(), nullable=True),
        sa.Column("orientation_deg", sa.Float(), nullable=True),
        sa.Column("last_health_score", sa.Integer(), nullable=True),
        sa.Column("uptime_pct", sa.Float(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("registered_by", sa.UUID(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["camera_id"], ["cameras.id"], name=op.f("fk_camera_registry_camera_id_cameras"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["registered_by"], ["users.id"], name=op.f("fk_camera_registry_registered_by_users"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_camera_registry")),
    )
    op.create_index(op.f("ix_camera_registry_camera_id"), "camera_registry", ["camera_id"], unique=True)
    op.create_index(op.f("ix_camera_registry_cctv_code"), "camera_registry", ["cctv_code"], unique=True)
    op.create_index(op.f("ix_camera_registry_serial_number"), "camera_registry", ["serial_number"], unique=False)
    op.create_index(op.f("ix_camera_registry_state_code"), "camera_registry", ["state_code"], unique=False)
    op.create_index(op.f("ix_camera_registry_district_code"), "camera_registry", ["district_code"], unique=False)
    op.create_index(op.f("ix_camera_registry_department_code"), "camera_registry", ["department_code"], unique=False)
    op.create_index(op.f("ix_camera_registry_gis_layer"), "camera_registry", ["gis_layer"], unique=False)
    op.create_index(op.f("ix_camera_registry_cluster_key"), "camera_registry", ["cluster_key"], unique=False)

    # --- camera_audit_log ---------------------------------------------------
    op.create_table(
        "camera_audit_log",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("camera_id", sa.UUID(), nullable=True),
        sa.Column("registry_id", sa.UUID(), nullable=True),
        sa.Column("cctv_code", sa.String(length=40), nullable=True),
        sa.Column("event_type", sa.String(length=24), nullable=False),
        sa.Column("actor_id", sa.UUID(), nullable=True),
        sa.Column("actor_role", sa.String(length=24), nullable=True),
        sa.Column("scope", sa.String(length=40), nullable=True),
        sa.Column("summary", sa.String(length=255), nullable=False),
        sa.Column("before", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["camera_id"], ["cameras.id"], name=op.f("fk_camera_audit_log_camera_id_cameras"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["registry_id"], ["camera_registry.id"], name=op.f("fk_camera_audit_log_registry_id_camera_registry"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], name=op.f("fk_camera_audit_log_actor_id_users"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_camera_audit_log")),
    )
    op.create_index(op.f("ix_camera_audit_log_camera_id"), "camera_audit_log", ["camera_id"], unique=False)
    op.create_index(op.f("ix_camera_audit_log_registry_id"), "camera_audit_log", ["registry_id"], unique=False)
    op.create_index(op.f("ix_camera_audit_log_cctv_code"), "camera_audit_log", ["cctv_code"], unique=False)
    op.create_index(op.f("ix_camera_audit_log_event_type"), "camera_audit_log", ["event_type"], unique=False)


def downgrade() -> None:
    op.drop_table("camera_audit_log")
    op.drop_table("camera_registry")