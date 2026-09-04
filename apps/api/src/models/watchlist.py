"""Watchlist model for flagged vehicles and persons.

Stores targets from external databases (VAHAN, eGujCop, SARTHI) that should
trigger instant alerts when detected by the ANPR pipeline.
"""

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Enum, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class WatchlistTargetType(str, enum.Enum):
    VEHICLE = "vehicle"
    PERSON = "person"


class WatchlistCategory(str, enum.Enum):
    STOLEN_VEHICLE = "stolen_vehicle"
    WANTED = "wanted"
    MISSING = "missing"
    UNINSURED = "uninsured"
    BLACKLISTED = "blacklisted"
    SUSPECT = "suspect"
    OTHER = "other"


class WatchlistSourceDB(str, enum.Enum):
    VAHAN = "vahan"
    EGUJCOP = "egujcop"
    SARTHI = "sarthi"
    INTERNAL = "internal"
    MANUAL = "manual"


class Watchlist(Base, TimestampMixin):
    __tablename__ = "watchlists"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    target_type: Mapped[WatchlistTargetType] = mapped_column(
        Enum(
            WatchlistTargetType,
            name="watchlist_target_type",
            values_callable=lambda e: [m.value for m in e],
        ),
        index=True,
        nullable=False,
    )
    identifier_number: Mapped[str] = mapped_column(
        String(64), index=True, nullable=False
    )
    category: Mapped[WatchlistCategory] = mapped_column(
        Enum(
            WatchlistCategory,
            name="watchlist_category",
            values_callable=lambda e: [m.value for m in e],
        ),
        index=True,
        nullable=False,
    )
    source_db: Mapped[WatchlistSourceDB] = mapped_column(
        Enum(
            WatchlistSourceDB,
            name="watchlist_source_db",
            values_callable=lambda e: [m.value for m in e],
        ),
        index=True,
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True, nullable=False)
    added_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.now, nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Watchlist {self.identifier_number} type={self.target_type.value}>"


__all__ = [
    "Watchlist",
    "WatchlistTargetType",
    "WatchlistCategory",
    "WatchlistSourceDB",
    "Any",
]
