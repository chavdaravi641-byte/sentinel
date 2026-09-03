"""phase 2 streaming schema: streams + recordings

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-30 00:00:00.000000

Both tables are additive — Phase 1 tables are untouched. Lifecycle states and
triggers are stored as plain text columns (no new PostgreSQL enum types), so
this migration can never collide with the Phase 1 enum bootstrap.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- streams --------------------------------------------------------
    op.create_table(
        "streams",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("camera_id", sa.UUID(), nullable=False),
        sa.Column(
            "state",
            sa.String(length=16),
            nullable=False,
            server_default="stopped",
        ),
        sa.Column("mode", sa.String(length=32), nullable=False, server_default="balanced"),
        sa.Column("source", sa.String(length=512), nullable=False),
        sa.Column("error", sa.String(length=512), nullable=True),
        sa.Column(
            "reconnect_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_health_at", sa.DateTime(timezone=True), nullable=True),
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
            name=op.f("fk_streams_camera_id_cameras"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_streams")),
    )
    op.create_index(op.f("ix_streams_camera_id"), "streams", ["camera_id"], unique=True)
    op.create_index(op.f("ix_streams_state"), "streams", ["state"], unique=False)

    # --- recordings -----------------------------------------------------
    op.create_table(
        "recordings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("camera_id", sa.UUID(), nullable=False),
        sa.Column("stream_id", sa.UUID(), nullable=True),
        sa.Column("started_by", sa.UUID(), nullable=True),
        sa.Column(
            "trigger",
            sa.String(length=16),
            nullable=False,
            server_default="manual",
        ),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default="recording",
        ),
        sa.Column("file_path", sa.String(length=512), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("segment_seconds", sa.Integer(), nullable=False, server_default=sa.text("15")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
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
            name=op.f("fk_recordings_camera_id_cameras"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["started_by"],
            ["users.id"],
            name=op.f("fk_recordings_started_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["stream_id"],
            ["streams.id"],
            name=op.f("fk_recordings_stream_id_streams"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recordings")),
    )
    op.create_index(op.f("ix_recordings_camera_id"), "recordings", ["camera_id"], unique=False)
    op.create_index(op.f("ix_recordings_status"), "recordings", ["status"], unique=False)
    op.create_index(op.f("ix_recordings_started_at"), "recordings", ["started_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_recordings_started_at"), table_name="recordings")
    op.drop_index(op.f("ix_recordings_status"), table_name="recordings")
    op.drop_index(op.f("ix_recordings_camera_id"), table_name="recordings")
    op.drop_table("recordings")
    op.drop_index(op.f("ix_streams_state"), table_name="streams")
    op.drop_index(op.f("ix_streams_camera_id"), table_name="streams")
    op.drop_table("streams")