"""phase 3 inference schema: ai_models, inference_runs, detections, inference_alerts

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-31 00:00:00.000000

All tables are additive — Phase 1/2 tables are untouched. Statuses/triggers use
plain text columns (no new PostgreSQL enum types), matching the Phase 1/2
migration strategy. Bounding boxes are normalized (0..1) with source pixel
dimensions carried on the owning run row.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- ai_models (runtime registry snapshot) -----------------------------
    op.create_table(
        "ai_models",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False, server_default="0.0.0"),
        sa.Column("backend", sa.String(length=32), nullable=False, server_default="sim"),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default="unloaded",
        ),
        sa.Column("generation", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("accelerator", sa.String(length=16), nullable=True),
        sa.Column("device", sa.String(length=128), nullable=True),
        sa.Column("providers", sa.JSON(), nullable=True),
        sa.Column("weights_path", sa.String(length=512), nullable=True),
        sa.Column("classes", sa.JSON(), nullable=True),
        sa.Column("meta", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("error", sa.String(length=512), nullable=True),
        sa.Column("loaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_models")),
    )
    op.create_index(op.f("ix_ai_models_name"), "ai_models", ["name"], unique=True)
    op.create_index(op.f("ix_ai_models_status"), "ai_models", ["status"], unique=False)

    # --- inference_runs (one row per analyzed frame) -----------------------
    op.create_table(
        "inference_runs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("camera_id", sa.UUID(), nullable=False),
        sa.Column("model_name", sa.String(length=64), nullable=False),
        sa.Column("model_version", sa.String(length=32), nullable=False, server_default="0.0.0"),
        sa.Column("model_generation", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("frame_seq", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "ts",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("width", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("height", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("pre_ms", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("infer_ms", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("post_ms", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("total_ms", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("batch_size", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("detections", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("fps", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("accelerator", sa.String(length=16), nullable=True),
        sa.Column("backend", sa.String(length=32), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["camera_id"],
            ["cameras.id"],
            name=op.f("fk_inference_runs_camera_id_cameras"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_inference_runs")),
    )
    op.create_index(op.f("ix_inference_runs_camera_id"), "inference_runs", ["camera_id"], unique=False)
    op.create_index(op.f("ix_inference_runs_model_name"), "inference_runs", ["model_name"], unique=False)
    op.create_index(op.f("ix_inference_runs_ts"), "inference_runs", ["ts"], unique=False)

    # --- detections (one row per bounding box) -----------------------------
    op.create_table(
        "detections",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("camera_id", sa.UUID(), nullable=False),
        sa.Column("model_name", sa.String(length=64), nullable=False),
        sa.Column("class_name", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("track_id", sa.Integer(), nullable=True),
        sa.Column("x", sa.Float(), nullable=False),
        sa.Column("y", sa.Float(), nullable=False),
        sa.Column("w", sa.Float(), nullable=False),
        sa.Column("h", sa.Float(), nullable=False),
        sa.Column("cx", sa.Float(), nullable=False),
        sa.Column("cy", sa.Float(), nullable=False),
        sa.Column("frame_seq", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "ts",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["camera_id"],
            ["cameras.id"],
            name=op.f("fk_detections_camera_id_cameras"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["inference_runs.id"],
            name=op.f("fk_detections_run_id_inference_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_detections")),
    )
    op.create_index(op.f("ix_detections_camera_id"), "detections", ["camera_id"], unique=False)
    op.create_index(op.f("ix_detections_class_name"), "detections", ["class_name"], unique=False)
    op.create_index(op.f("ix_detections_model_name"), "detections", ["model_name"], unique=False)
    op.create_index(op.f("ix_detections_run_id"), "detections", ["run_id"], unique=False)
    op.create_index(op.f("ix_detections_track_id"), "detections", ["track_id"], unique=False)
    op.create_index(op.f("ix_detections_ts"), "detections", ["ts"], unique=False)

    # --- inference_alerts (rule engine output) -----------------------------
    op.create_table(
        "inference_alerts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("camera_id", sa.UUID(), nullable=False),
        sa.Column("model_name", sa.String(length=64), nullable=False, server_default="yolov12"),
        sa.Column("rule", sa.String(length=32), nullable=False),
        sa.Column("class_name", sa.String(length=32), nullable=False),
        sa.Column("level", sa.String(length=16), nullable=False, server_default="info"),
        sa.Column("message", sa.String(length=512), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("count", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("resolved", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["camera_id"],
            ["cameras.id"],
            name=op.f("fk_inference_alerts_camera_id_cameras"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_inference_alerts")),
    )
    op.create_index(op.f("ix_inference_alerts_camera_id"), "inference_alerts", ["camera_id"], unique=False)
    op.create_index(op.f("ix_inference_alerts_last_seen_at"), "inference_alerts", ["last_seen_at"], unique=False)
    op.create_index(op.f("ix_inference_alerts_resolved"), "inference_alerts", ["resolved"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_inference_alerts_resolved"), table_name="inference_alerts")
    op.drop_index(op.f("ix_inference_alerts_last_seen_at"), table_name="inference_alerts")
    op.drop_index(op.f("ix_inference_alerts_camera_id"), table_name="inference_alerts")
    op.drop_table("inference_alerts")
    op.drop_index(op.f("ix_detections_ts"), table_name="detections")
    op.drop_index(op.f("ix_detections_track_id"), table_name="detections")
    op.drop_index(op.f("ix_detections_run_id"), table_name="detections")
    op.drop_index(op.f("ix_detections_model_name"), table_name="detections")
    op.drop_index(op.f("ix_detections_class_name"), table_name="detections")
    op.drop_index(op.f("ix_detections_camera_id"), table_name="detections")
    op.drop_table("detections")
    op.drop_index(op.f("ix_inference_runs_ts"), table_name="inference_runs")
    op.drop_index(op.f("ix_inference_runs_model_name"), table_name="inference_runs")
    op.drop_index(op.f("ix_inference_runs_camera_id"), table_name="inference_runs")
    op.drop_table("inference_runs")
    op.drop_index(op.f("ix_ai_models_status"), table_name="ai_models")
    op.drop_index(op.f("ix_ai_models_name"), table_name="ai_models")
    op.drop_table("ai_models")