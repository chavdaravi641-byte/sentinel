"""Watchlist schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.models.watchlist import WatchlistCategory, WatchlistSourceDB, WatchlistTargetType


class WatchlistBase(BaseModel):
    target_type: WatchlistTargetType
    identifier_number: str = Field(min_length=1, max_length=64)
    category: WatchlistCategory
    source_db: WatchlistSourceDB
    notes: str | None = Field(default=None, max_length=2000)


class WatchlistCreate(WatchlistBase):
    active: bool = True


class WatchlistUpdate(BaseModel):
    target_type: WatchlistTargetType | None = None
    identifier_number: str | None = Field(default=None, min_length=1, max_length=64)
    category: WatchlistCategory | None = None
    source_db: WatchlistSourceDB | None = None
    notes: str | None = Field(default=None, max_length=2000)
    active: bool | None = None


class WatchlistRead(WatchlistBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    active: bool
    added_by: UUID | None
    added_at: datetime
    created_at: datetime
    updated_at: datetime


class WatchlistStats(BaseModel):
    total: int
    active: int
    inactive: int
    by_type: dict[str, int]
    by_category: dict[str, int]
    by_source: dict[str, int]
