"""phase 6 copilot: case workspace + audit log

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-01 00:00:00.000000

Additive tables for the Phase 6 AI Investigation Copilot (case workspace,
case evidence, notes, bookmarks, and a full investigation audit log). All
tables are additive — earlier phases are untouched. No new PostgreSQL enums;
statuses are plain text columns, matching the established strategy. JSONB
carries flexible evidence / audit payloads.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- copilot_cases ------------------------------------------------------
    op.create_table(
        "copilot_cases",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("case_number", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("owner_id", sa.UUID(), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_copilot_cases")),
    )
    op.create_index(op.f("ix_copilot_cases_case_number"), "copilot_cases", ["case_number"], unique=True)
    op.create_index(op.f("ix_copilot_cases_status"), "copilot_cases", ["status"], unique=False)

    # --- copilot_case_evidence ----------------------------------------------
    op.create_table(
        "copilot_case_evidence",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("case_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("ref", sa.String(length=128), nullable=True),
        sa.Column("label", sa.String(length=255), nullable=True),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("added_by", sa.UUID(), nullable=True),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["case_id"], ["copilot_cases.id"], name=op.f("fk_copilot_case_evidence_case_id_copilot_cases"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_copilot_case_evidence")),
    )
    op.create_index(op.f("ix_copilot_case_evidence_case_id"), "copilot_case_evidence", ["case_id"], unique=False)

    # --- copilot_case_notes ---------------------------------------------------
    op.create_table(
        "copilot_case_notes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("case_id", sa.UUID(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("author_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["case_id"], ["copilot_cases.id"], name=op.f("fk_copilot_case_notes_case_id_copilot_cases"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_copilot_case_notes")),
    )
    op.create_index(op.f("ix_copilot_case_notes_case_id"), "copilot_case_notes", ["case_id"], unique=False)

    # --- copilot_case_bookmarks ------------------------------------------------
    op.create_table(
        "copilot_case_bookmarks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("case_id", sa.UUID(), nullable=False),
        sa.Column("vehicle_uuid", sa.String(length=36), nullable=False),
        sa.Column("plate", sa.String(length=32), nullable=True),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["case_id"], ["copilot_cases.id"], name=op.f("fk_copilot_case_bookmarks_case_id_copilot_cases"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_copilot_case_bookmarks")),
    )
    op.create_index(op.f("ix_copilot_case_bookmarks_case_id"), "copilot_case_bookmarks", ["case_id"], unique=False)
    op.create_index(op.f("ix_copilot_case_bookmarks_vehicle_uuid"), "copilot_case_bookmarks", ["vehicle_uuid"], unique=False)

    # --- copilot_audit_log ------------------------------------------------------
    op.create_table(
        "copilot_audit_log",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("officer_id", sa.UUID(), nullable=True),
        sa.Column("officer_name", sa.String(length=160), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("query", sa.Text(), nullable=True),
        sa.Column("case_id", sa.UUID(), nullable=True),
        sa.Column("evidence_accessed", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["case_id"], ["copilot_cases.id"], name=op.f("fk_copilot_audit_log_case_id_copilot_cases"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_copilot_audit_log")),
    )
    op.create_index(op.f("ix_copilot_audit_log_officer_id"), "copilot_audit_log", ["officer_id"], unique=False)
    op.create_index(op.f("ix_copilot_audit_log_action"), "copilot_audit_log", ["action"], unique=False)
    op.create_index(op.f("ix_copilot_audit_log_case_id"), "copilot_audit_log", ["case_id"], unique=False)
    op.create_index(op.f("ix_copilot_audit_log_created_at"), "copilot_audit_log", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_table("copilot_audit_log")
    op.drop_table("copilot_case_bookmarks")
    op.drop_table("copilot_case_notes")
    op.drop_table("copilot_case_evidence")
    op.drop_table("copilot_cases")
