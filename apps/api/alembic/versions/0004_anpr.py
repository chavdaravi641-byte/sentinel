"""phase 4 anpr schema: anpr_plate_detections, anpr_evidence, anpr_blacklist, anpr_alerts

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-31 00:00:00.000000

All tables are additive — Phase 1/2/3 tables are untouched. Statuses/triggers use
plain text columns (no new PostgreSQL enum types), matching the established
migration strategy. Plate regions are stored normalized (0..1); attribute and
state/RTO fields are plain indexed columns so search is cheap.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- anpr_plate_detections ---------------------------------------------
    op.create_table(
        "anpr_plate_detections",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("camera_id", sa.UUID(), nullable=False),
        sa.Column("camera_name", sa.String(length=160), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("plate", sa.String(length=32), nullable=False),
        sa.Column("normalized_plate", sa.String(length=32), nullable=False),
        sa.Column("state_code", sa.String(length=8), nullable=True),
        sa.Column("rto_code", sa.String(length=8), nullable=True),
        sa.Column("ocr_confidence", sa.Float(), nullable=False),
        sa.Column("detection_confidence", sa.Float(), nullable=False),
        sa.Column("vehicle_type", sa.String(length=24), nullable=True),
        sa.Column("color", sa.String(length=24), nullable=True),
        sa.Column("make", sa.String(length=64), nullable=True),
        sa.Column("model", sa.String(length=64), nullable=True),
        sa.Column("attribute_confidence", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("x", sa.Float(), nullable=False),
        sa.Column("y", sa.Float(), nullable=False),
        sa.Column("w", sa.Float(), nullable=False),
        sa.Column("h", sa.Float(), nullable=False),
        sa.Column("backend", sa.String(length=16), nullable=False, server_default="sim"),
        sa.Column("frame_seq", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("evidence_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["camera_id"], ["cameras.id"], name=op.f("fk_anpr_plate_detections_camera_id_cameras"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_anpr_plate_detections")),
    )
    op.create_index(op.f("ix_anpr_plate_detections_camera_id"), "anpr_plate_detections", ["camera_id"], unique=False)
    op.create_index(op.f("ix_anpr_plate_detections_normalized_plate"), "anpr_plate_detections", ["normalized_plate"], unique=False)
    op.create_index(op.f("ix_anpr_plate_detections_state_code"), "anpr_plate_detections", ["state_code"], unique=False)
    op.create_index(op.f("ix_anpr_plate_detections_vehicle_type"), "anpr_plate_detections", ["vehicle_type"], unique=False)
    op.create_index(op.f("ix_anpr_plate_detections_color"), "anpr_plate_detections", ["color"], unique=False)
    op.create_index(op.f("ix_anpr_plate_detections_make"), "anpr_plate_detections", ["make"], unique=False)
    op.create_index(op.f("ix_anpr_plate_detections_ts"), "anpr_plate_detections", ["ts"], unique=False)
    op.create_index(op.f("ix_anpr_plate_detections_evidence_id"), "anpr_plate_detections", ["evidence_id"], unique=False)

    # --- anpr_evidence ------------------------------------------------------
    op.create_table(
        "anpr_evidence",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("camera_id", sa.UUID(), nullable=False),
        sa.Column("plate", sa.String(length=32), nullable=False),
        sa.Column("normalized_plate", sa.String(length=32), nullable=False),
        sa.Column("frame_path", sa.String(length=512), nullable=True),
        sa.Column("plate_path", sa.String(length=512), nullable=True),
        sa.Column("vehicle_path", sa.String(length=512), nullable=True),
        sa.Column("ocr_text", sa.Text(), nullable=True),
        sa.Column("frame_hash", sa.String(length=64), nullable=True),
        sa.Column("plate_hash", sa.String(length=64), nullable=True),
        sa.Column("vehicle_hash", sa.String(length=64), nullable=True),
        sa.Column("detection_confidence", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("ocr_confidence", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["camera_id"], ["cameras.id"], name=op.f("fk_anpr_evidence_camera_id_cameras"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_anpr_evidence")),
    )
    op.create_index(op.f("ix_anpr_evidence_camera_id"), "anpr_evidence", ["camera_id"], unique=False)
    op.create_index(op.f("ix_anpr_evidence_normalized_plate"), "anpr_evidence", ["normalized_plate"], unique=False)
    op.create_index(op.f("ix_anpr_evidence_ts"), "anpr_evidence", ["ts"], unique=False)

    # --- anpr_blacklist -----------------------------------------------------
    op.create_table(
        "anpr_blacklist",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("plate", sa.String(length=32), nullable=False),
        sa.Column("normalized_plate", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("added_by", sa.UUID(), nullable=True),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_anpr_blacklist")),
    )
    op.create_index(op.f("ix_anpr_blacklist_plate"), "anpr_blacklist", ["plate"], unique=False)
    op.create_index(op.f("ix_anpr_blacklist_normalized_plate"), "anpr_blacklist", ["normalized_plate"], unique=True)
    op.create_index(op.f("ix_anpr_blacklist_active"), "anpr_blacklist", ["active"], unique=False)

    # --- anpr_alerts --------------------------------------------------------
    op.create_table(
        "anpr_alerts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("camera_id", sa.UUID(), nullable=False),
        sa.Column("plate", sa.String(length=32), nullable=False),
        sa.Column("normalized_plate", sa.String(length=32), nullable=False),
        sa.Column("rule", sa.String(length=32), nullable=False),
        sa.Column("class_name", sa.String(length=24), nullable=False, server_default="vehicle"),
        sa.Column("level", sa.String(length=16), nullable=False, server_default="info"),
        sa.Column("message", sa.String(length=512), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("count", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("resolved", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["camera_id"], ["cameras.id"], name=op.f("fk_anpr_alerts_camera_id_cameras"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_anpr_alerts")),
    )
    op.create_index(op.f("ix_anpr_alerts_camera_id"), "anpr_alerts", ["camera_id"], unique=False)
    op.create_index(op.f("ix_anpr_alerts_normalized_plate"), "anpr_alerts", ["normalized_plate"], unique=False)
    op.create_index(op.f("ix_anpr_alerts_last_seen_at"), "anpr_alerts", ["last_seen_at"], unique=False)
    op.create_index(op.f("ix_anpr_alerts_resolved"), "anpr_alerts", ["resolved"], unique=False)


def downgrade() -> None:
    op.drop_table("anpr_alerts")
    op.drop_table("anpr_blacklist")
    op.drop_table("anpr_evidence")
    op.drop_table("anpr_plate_detections")
