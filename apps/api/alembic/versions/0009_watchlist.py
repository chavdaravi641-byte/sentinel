"""add watchlists table

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-03 00:00:00.000000

Watchlist for flagged vehicles and persons. Cross-referenced by the ANPR
pipeline for real-time alert generation when a plate matches an active entry.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM as PgEnum

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- enums ---------------------------------------------------------------
    # Follow the proven pattern from 0001_initial: create the native enum types
    # idempotently via a DO-block (swallowing duplicate_object), then declare the
    # column enums with create_type=False so create_table never re-emits
    # CREATE TYPE (which would collide on databases boosted via create_all).
    enum_values: dict[str, list[str]] = {
        "watchlist_target_type": ["vehicle", "person"],
        "watchlist_category": [
            "stolen_vehicle", "wanted", "missing", "uninsured",
            "blacklisted", "suspect", "other",
        ],
        "watchlist_source_db": ["vahan", "egujcop", "sarthi", "internal", "manual"],
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

    watchlist_target_type = PgEnum("vehicle", "person", name="watchlist_target_type",
                                   create_type=False)
    watchlist_category = PgEnum(
        "stolen_vehicle", "wanted", "missing", "uninsured",
        "blacklisted", "suspect", "other",
        name="watchlist_category", create_type=False,
    )
    watchlist_source_db = PgEnum(
        "vahan", "egujcop", "sarthi", "internal", "manual",
        name="watchlist_source_db", create_type=False,
    )

    # --- watchlists table ----------------------------------------------------
    op.create_table(
        "watchlists",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("target_type", watchlist_target_type, nullable=False),
        sa.Column("identifier_number", sa.String(length=64), nullable=False),
        sa.Column("category", watchlist_category, nullable=False),
        sa.Column("source_db", watchlist_source_db, nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("added_by", sa.UUID(), nullable=True),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_watchlists")),
    )
    op.create_index(op.f("ix_watchlists_target_type"), "watchlists", ["target_type"], unique=False)
    op.create_index(op.f("ix_watchlists_identifier_number"), "watchlists", ["identifier_number"], unique=False)
    op.create_index(op.f("ix_watchlists_category"), "watchlists", ["category"], unique=False)
    op.create_index(op.f("ix_watchlists_source_db"), "watchlists", ["source_db"], unique=False)
    op.create_index(op.f("ix_watchlists_active"), "watchlists", ["active"], unique=False)


def downgrade() -> None:
    op.drop_table("watchlists")
    sa.Enum(name="watchlist_source_db").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="watchlist_category").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="watchlist_target_type").drop(op.get_bind(), checkfirst=True)
