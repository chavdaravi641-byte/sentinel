"""phase 6.1 IAM: extend fed_departments/fed_audit (additive) + IAM tables

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-01 00:00:00.000000

Additive only. Existing Phase 1..6 columns/tables are untouched. New NOT NULL
columns carry server defaults so existing rows migrate with zero data loss.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _enum(name: str, *values: str) -> postgresql.ENUM:
    return postgresql.ENUM(*values, name=name)


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Enum types
    # ------------------------------------------------------------------
    dept_type = _enum("fed_dept_type", "state_hq", "range", "commissionerate", "district",
                      "sub_division", "police_station", "traffic", "cid", "ats", "srp",
                      "cyber_crime", "control_room", "home_department", "special_branch", "other")
    jurisdiction = _enum("fed_jurisdiction_scope", "state", "range", "city", "district",
                         "sub_division", "police_station", "camera", "custom")
    access_mode = _enum("fed_access_mode", "normal", "break_glass", "read_only",
                        "investigation", "system", "api", "service_account")
    severity = _enum("fed_severity", "info", "warning", "error", "critical")
    officer_rank = _enum("fed_officer_rank", "dgp", "adgp", "igp", "dig", "cp", "jcp", "sp",
                         "dcp", "adsp", "acp", "dsp", "pi", "psi", "asi", "head_constable",
                         "constable", "operator", "analyst", "auditor", "viewer")
    officer_status = _enum("fed_officer_status", "active", "locked", "disabled", "pending")
    role_jurisdiction = _enum("fed_role_jurisdiction_scope", "state", "range", "city",
                              "district", "sub_division", "police_station", "camera", "custom")
    resource_type = _enum("fed_resource_type", "camera", "stream", "vehicle", "anpr",
                          "identity", "alert", "evidence", "timeline", "report", "dashboard",
                          "analytics", "map", "case", "officer", "department", "role",
                          "permission", "audit", "settings", "system")
    permission_action = _enum("fed_permission_action", "read", "create", "update", "delete",
                              "approve", "assign", "search", "export", "import", "configure",
                              "manage", "view_live", "stream", "download", "share", "archive")
    permission_effect = _enum("fed_permission_effect", "allow", "deny")
    abac_effect = _enum("fed_abac_effect", "allow", "deny")
    emergency_status = _enum("fed_emergency_status", "requested", "approved", "active",
                             "expired", "revoked", "denied")
    session_status = _enum("fed_session_status", "active", "expired", "revoked", "invalid")

    for e in (dept_type, jurisdiction, access_mode, severity, officer_rank, officer_status,
              role_jurisdiction, resource_type, permission_action, permission_effect,
              abac_effect, emergency_status, session_status):
        e.create(op.get_bind(), checkfirst=True)

    # ------------------------------------------------------------------
    # Extend fed_departments (additive)
    # ------------------------------------------------------------------
    op.add_column("fed_departments", sa.Column("dept_type", dept_type, nullable=False,
                                               server_default="other"))
    op.add_column("fed_departments", sa.Column("hierarchy_level", sa.Integer(), nullable=False,
                                               server_default=sa.text("0")))
    op.add_column("fed_departments", sa.Column("jurisdiction_scope", jurisdiction, nullable=False,
                                               server_default="state"))
    op.add_column("fed_departments", sa.Column("district", sa.String(length=64), nullable=True))
    op.add_column("fed_departments", sa.Column("state", sa.String(length=64), nullable=True))
    op.add_column("fed_departments", sa.Column("latitude", sa.Float(), nullable=True))
    op.add_column("fed_departments", sa.Column("longitude", sa.Float(), nullable=True))
    op.add_column("fed_departments", sa.Column("address", sa.String(length=512), nullable=True))
    op.add_column("fed_departments", sa.Column("contact_email", sa.String(length=255), nullable=True))
    op.add_column("fed_departments", sa.Column("contact_phone", sa.String(length=64), nullable=True))
    op.add_column("fed_departments", sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()),
                                               nullable=False, server_default=sa.text("'{}'::jsonb")))
    op.add_column("fed_departments", sa.Column("created_by", sa.UUID(), nullable=True))
    op.add_column("fed_departments", sa.Column("updated_by", sa.UUID(), nullable=True))
    op.add_column("fed_departments", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("fed_departments", sa.Column("is_deleted", sa.Boolean(), nullable=False,
                                               server_default=sa.text("false")))
    op.create_index("ix_fed_departments_dept_type", "fed_departments", ["dept_type"])
    op.create_index("ix_fed_departments_is_deleted", "fed_departments", ["is_deleted"])

    # ------------------------------------------------------------------
    # Extend fed_audit (additive)
    # ------------------------------------------------------------------
    op.add_column("fed_audit", sa.Column("officer_id", sa.UUID(), nullable=True))
    op.add_column("fed_audit", sa.Column("department_id", sa.UUID(), nullable=True))
    op.add_column("fed_audit", sa.Column("device", sa.String(length=128), nullable=True))
    op.add_column("fed_audit", sa.Column("browser", sa.String(length=64), nullable=True))
    op.add_column("fed_audit", sa.Column("operating_system", sa.String(length=64), nullable=True))
    op.add_column("fed_audit", sa.Column("user_agent", sa.String(length=512), nullable=True))
    op.add_column("fed_audit", sa.Column("location", sa.String(length=255), nullable=True))
    op.add_column("fed_audit", sa.Column("latitude", sa.Float(), nullable=True))
    op.add_column("fed_audit", sa.Column("longitude", sa.Float(), nullable=True))
    op.add_column("fed_audit", sa.Column("access_mode", access_mode, nullable=False,
                                         server_default="normal"))
    op.add_column("fed_audit", sa.Column("reason", sa.String(length=512), nullable=True))
    op.add_column("fed_audit", sa.Column("old_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("fed_audit", sa.Column("new_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("fed_audit", sa.Column("status", sa.String(length=32), nullable=True))
    op.add_column("fed_audit", sa.Column("session_id", sa.UUID(), nullable=True))
    op.add_column("fed_audit", sa.Column("request_id", sa.UUID(), nullable=True))
    op.add_column("fed_audit", sa.Column("trace_id", sa.UUID(), nullable=True))
    op.add_column("fed_audit", sa.Column("case_id", sa.UUID(), nullable=True))
    op.add_column("fed_audit", sa.Column("severity", severity, nullable=False, server_default="info"))
    op.add_column("fed_audit", sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()),
                                         nullable=False, server_default=sa.text("'{}'::jsonb")))
    op.create_index("ix_fed_audit_department_id", "fed_audit", ["department_id"])
    op.create_index("ix_fed_audit_officer_id", "fed_audit", ["officer_id"])
    op.create_index("ix_fed_audit_request_id", "fed_audit", ["request_id"])
    op.create_index("ix_fed_audit_trace_id", "fed_audit", ["trace_id"])
    op.create_index("ix_fed_audit_case_id", "fed_audit", ["case_id"])
    op.create_index("ix_fed_audit_severity", "fed_audit", ["severity"])

    # ------------------------------------------------------------------
    # IAM tables
    # ------------------------------------------------------------------
    op.create_table(
        "fed_officers",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("badge_number", sa.String(length=64), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=64), nullable=True),
        sa.Column("department_id", sa.UUID(), nullable=False),
        sa.Column("rank", officer_rank, nullable=False, server_default="constable"),
        sa.Column("designation", sa.String(length=255), nullable=True),
        sa.Column("assigned_district", sa.String(length=64), nullable=True),
        sa.Column("assigned_station", sa.String(length=128), nullable=True),
        sa.Column("status", officer_status, nullable=False, server_default="pending"),
        sa.Column("role_id", sa.UUID(), nullable=True),
        sa.Column("supervisor_id", sa.UUID(), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("account_status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("mfa_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["department_id"], ["fed_departments.id"]),
        sa.ForeignKeyConstraint(["role_id"], ["fed_roles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_fed_officers_badge_number"), "fed_officers", ["badge_number"], unique=True)
    op.create_index(op.f("ix_fed_officers_email"), "fed_officers", ["email"], unique=True)
    op.create_index(op.f("ix_fed_officers_department_id"), "fed_officers", ["department_id"])

    op.create_table(
        "fed_roles",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("parent_role_id", sa.UUID(), nullable=True),
        sa.Column("resource_scope", sa.String(length=32), nullable=False, server_default="department"),
        sa.Column("jurisdiction_scope", role_jurisdiction, nullable=False, server_default="district"),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_fed_roles_code"), "fed_roles", ["code"], unique=True)

    op.create_table(
        "fed_permissions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(length=128), nullable=False),
        sa.Column("resource", resource_type, nullable=False),
        sa.Column("action", permission_action, nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("scope", sa.String(length=32), nullable=False, server_default="department"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_fed_permissions_code"), "fed_permissions", ["code"], unique=True)

    op.create_table(
        "fed_role_permissions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("role_id", sa.UUID(), nullable=False),
        sa.Column("permission_id", sa.UUID(), nullable=False),
        sa.Column("effect", permission_effect, nullable=False, server_default="allow"),
        sa.Column("inherited_from", sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(["permission_id"], ["fed_permissions.id"]),
        sa.ForeignKeyConstraint(["role_id"], ["fed_roles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_fed_role_permissions_role_id"), "fed_role_permissions", ["role_id"])
    op.create_index(op.f("ix_fed_role_permissions_permission_id"), "fed_role_permissions", ["permission_id"])

    op.create_table(
        "fed_abac_policies",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("effect", abac_effect, nullable=False),
        sa.Column("resource", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("conditions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default=sa.text("100")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "fed_emergency_access",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("officer_id", sa.UUID(), nullable=False),
        sa.Column("department_id", sa.UUID(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("case_reference", sa.String(length=128), nullable=True),
        sa.Column("approved_by", sa.UUID(), nullable=True),
        sa.Column("approval_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", sa.UUID(), nullable=True),
        sa.Column("status", emergency_status, nullable=False, server_default="requested"),
        sa.Column("duration_seconds", sa.Integer(), nullable=False, server_default=sa.text("1800")),
        sa.Column("grant", sa.String(length=64), nullable=False, server_default="cross_department_read"),
        sa.ForeignKeyConstraint(["department_id"], ["fed_departments.id"]),
        sa.ForeignKeyConstraint(["officer_id"], ["fed_officers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_fed_emergency_access_officer_id"), "fed_emergency_access", ["officer_id"])
    op.create_index(op.f("ix_fed_emergency_access_department_id"), "fed_emergency_access", ["department_id"])

    op.create_table(
        "fed_officer_sessions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("officer_id", sa.UUID(), nullable=False),
        sa.Column("refresh_token_hash", sa.String(length=255), nullable=False),
        sa.Column("access_token_jti", sa.String(length=128), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", session_status, nullable=False, server_default="active"),
        sa.Column("rotation_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.ForeignKeyConstraint(["officer_id"], ["fed_officers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_fed_officer_sessions_officer_id"), "fed_officer_sessions", ["officer_id"])
    op.create_index(op.f("ix_fed_officer_sessions_refresh_token_hash"), "fed_officer_sessions",
                    ["refresh_token_hash"])

    op.create_table(
        "fed_camera_groups",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("department_id", sa.UUID(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["department_id"], ["fed_departments.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_fed_camera_groups_department_id"), "fed_camera_groups", ["department_id"])

    op.create_table(
        "fed_department_cameras",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("department_id", sa.UUID(), nullable=False),
        sa.Column("camera_id", sa.UUID(), nullable=False),
        sa.Column("access_mode", sa.String(length=32), nullable=False, server_default="owner"),
        sa.ForeignKeyConstraint(["camera_id"], ["fed_cameras.id"]),
        sa.ForeignKeyConstraint(["department_id"], ["fed_departments.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_fed_department_cameras_department_id"), "fed_department_cameras", ["department_id"])
    op.create_index(op.f("ix_fed_department_cameras_camera_id"), "fed_department_cameras", ["camera_id"])


def downgrade() -> None:
    op.drop_table("fed_department_cameras")
    op.drop_table("fed_camera_groups")
    op.drop_table("fed_officer_sessions")
    op.drop_table("fed_emergency_access")
    op.drop_table("fed_abac_policies")
    op.drop_table("fed_role_permissions")
    op.drop_table("fed_permissions")
    op.drop_table("fed_roles")
    op.drop_table("fed_officers")

    op.drop_index("ix_fed_audit_severity", table_name="fed_audit")
    op.drop_index("ix_fed_audit_case_id", table_name="fed_audit")
    op.drop_index("ix_fed_audit_trace_id", table_name="fed_audit")
    op.drop_index("ix_fed_audit_request_id", table_name="fed_audit")
    op.drop_index("ix_fed_audit_officer_id", table_name="fed_audit")
    op.drop_index("ix_fed_audit_department_id", table_name="fed_audit")
    _drop_columns("fed_audit", ["metadata", "severity", "case_id", "trace_id", "request_id",
                                "session_id", "status", "new_value", "old_value", "reason",
                                "access_mode", "longitude", "latitude", "location", "user_agent",
                                "operating_system", "browser", "device", "department_id", "officer_id"])

    op.drop_index("ix_fed_departments_is_deleted", table_name="fed_departments")
    op.drop_index("ix_fed_departments_dept_type", table_name="fed_departments")
    _drop_columns("fed_departments", ["is_deleted", "deleted_at", "updated_by", "created_by",
                                      "metadata", "contact_phone", "contact_email", "address",
                                      "longitude", "latitude", "state", "district",
                                      "jurisdiction_scope", "hierarchy_level", "dept_type"])

    for name in ("fed_session_status", "fed_emergency_status", "fed_abac_effect",
                 "fed_permission_effect", "fed_permission_action", "fed_resource_type",
                 "fed_role_jurisdiction_scope", "fed_officer_status", "fed_officer_rank",
                 "fed_severity", "fed_access_mode", "fed_jurisdiction_scope", "fed_dept_type"):
        _enum_type = postgresql.ENUM(name=name)
        _enum_type.drop(op.get_bind(), checkfirst=True)


def _drop_columns(table: str, cols: list[str]) -> None:
    for col in cols:
        op.drop_column(table, col)
