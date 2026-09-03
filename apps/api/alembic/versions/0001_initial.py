"""initial schema for sentinel ai phase 1

Revision ID: 0001
Revises:
Create Date: 2026-01-01 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM as PgEnum

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Enum types -------------------------------------------------------
    #
    # PostgreSQL types are created explicitly below with an exception-guarded
    # DO block so the migration is idempotent (safe to re-run if the API
    # container restarts mid-boot). Every column reference then uses
    # create_type=False so CREATE TABLE never auto-creates a duplicate type.
    enum_values: dict[str, list[str]] = {
        "user_role": ["admin", "operator", "viewer"],
        "camera_status": ["online", "offline", "maintenance", "unknown"],
        "incident_type": [
            "theft",
            "assault",
            "traffic",
            "fire",
            "missing_person",
            "suspicious_activity",
            "vandalism",
            "other",
        ],
        "incident_status": ["open", "in_progress", "closed"],
        "alert_type": [
            "motion",
            "intrusion",
            "loitering",
            "crowd",
            "abandoned_object",
            "license_plate",
            "suspicious_behavior",
            "unknown",
        ],
        "alert_severity": ["critical", "high", "medium", "low", "info"],
        "alert_status": ["new", "acknowledged", "escalated", "resolved"],
    }

    bind = op.get_bind()
    for type_name, values in enum_values.items():
        list_sql = ", ".join(f"'{v}'" for v in values)
        bind.execute(
            sa.text(
                f"DO $$ BEGIN "
                f"CREATE TYPE {type_name} AS ENUM ({list_sql}); "
                f"EXCEPTION WHEN duplicate_object THEN NULL; "
                f"END $$;"
            )
        )

    user_role_enum = PgEnum(
        "admin", "operator", "viewer", name="user_role", create_type=False
    )
    camera_status_enum = PgEnum(
        "online", "offline", "maintenance", "unknown", name="camera_status", create_type=False
    )
    incident_type_enum = PgEnum(
        "theft",
        "assault",
        "traffic",
        "fire",
        "missing_person",
        "suspicious_activity",
        "vandalism",
        "other",
        name="incident_type",
        create_type=False,
    )
    incident_status_enum = PgEnum(
        "open", "in_progress", "closed", name="incident_status", create_type=False
    )
    alert_type_enum = PgEnum(
        "motion",
        "intrusion",
        "loitering",
        "crowd",
        "abandoned_object",
        "license_plate",
        "suspicious_behavior",
        "unknown",
        name="alert_type",
        create_type=False,
    )
    alert_severity_enum = PgEnum(
        "critical", "high", "medium", "low", "info", name="alert_severity", create_type=False
    )
    alert_status_enum = PgEnum(
        "new", "acknowledged", "escalated", "resolved",
        name="alert_status",
        create_type=False,
    )

    # --- users ----------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=120), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "role",
            user_role_enum,
            nullable=False,
            server_default="viewer",
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "last_login_at",
            sa.DateTime(timezone=True),
            nullable=True,
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    # --- cameras --------------------------------------------------------
    op.create_table(
        "cameras",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("rtsp_url", sa.String(length=512), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            camera_status_enum,
            nullable=False,
            server_default="unknown",
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=True,
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cameras")),
    )
    op.create_index(op.f("ix_cameras_name"), "cameras", ["name"], unique=False)
    op.create_index(op.f("ix_cameras_status"), "cameras", ["status"], unique=False)
    op.create_index(op.f("ix_cameras_location"), "cameras", ["location"], unique=False)

    # --- refresh_tokens -------------------------------------------------
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
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
            ["user_id"],
            ["users.id"],
            name=op.f("fk_refresh_tokens_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refresh_tokens")),
    )
    op.create_index(
        op.f("ix_refresh_tokens_token_hash"),
        "refresh_tokens",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        op.f("ix_refresh_tokens_user_id"),
        "refresh_tokens",
        ["user_id"],
        unique=False,
    )

    # --- alerts ---------------------------------------------------------
    op.create_table(
        "alerts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("camera_id", sa.UUID(), nullable=True),
        sa.Column("type", alert_type_enum, nullable=False),
        sa.Column("severity", alert_severity_enum, nullable=False),
        sa.Column(
            "status",
            alert_status_enum,
            nullable=False,
            server_default="new",
        ),
        sa.Column("message", sa.String(length=512), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("snapshot_url", sa.String(length=512), nullable=True),
        sa.Column(
            "occurred_at",
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
            name=op.f("fk_alerts_camera_id_cameras"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_alerts")),
    )
    op.create_index(op.f("ix_alerts_severity"), "alerts", ["severity"], unique=False)
    op.create_index(op.f("ix_alerts_status"), "alerts", ["status"], unique=False)
    op.create_index(op.f("ix_alerts_type"), "alerts", ["type"], unique=False)
    op.create_index(op.f("ix_alerts_camera_id"), "alerts", ["camera_id"], unique=False)
    op.create_index(op.f("ix_alerts_occurred_at"), "alerts", ["occurred_at"], unique=False)

    # --- incidents ------------------------------------------------------
    op.create_table(
        "incidents",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("camera_id", sa.UUID(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("type", incident_type_enum, nullable=False),
        sa.Column(
            "severity",
            alert_severity_enum,
            nullable=False,
            server_default="medium",
        ),
        sa.Column(
            "status",
            incident_status_enum,
            nullable=False,
            server_default="open",
        ),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("reported_by", sa.UUID(), nullable=True),
        sa.Column(
            "occurred_at",
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
            name=op.f("fk_incidents_camera_id_cameras"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["reported_by"],
            ["users.id"],
            name=op.f("fk_incidents_reported_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_incidents")),
    )
    op.create_index(op.f("ix_incidents_status"), "incidents", ["status"], unique=False)
    op.create_index(op.f("ix_incidents_type"), "incidents", ["type"], unique=False)
    op.create_index(op.f("ix_incidents_camera_id"), "incidents", ["camera_id"], unique=False)
    op.create_index(op.f("ix_incidents_reported_by"), "incidents", ["reported_by"], unique=False)
    op.create_index(op.f("ix_incidents_occurred_at"), "incidents", ["occurred_at"], unique=False)


def downgrade() -> None:
    op.drop_table("incidents")
    op.drop_table("alerts")
    op.drop_table("refresh_tokens")
    op.drop_table("cameras")
    op.drop_table("users")

    for name in (
        "alert_status",
        "alert_type",
        "alert_severity",
        "incident_status",
        "incident_type",
        "camera_status",
        "user_role",
    ):
        sa.Enum(name=name).drop(op.get_bind(), checkfirst=True)