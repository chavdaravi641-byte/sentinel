"""Watchlist CRUD + search endpoints."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from src.api.deps import AdminUser, CurrentUser, DBDep, StaffUser
from src.crud import watchlist as wl_crud
from src.models.watchlist import WatchlistCategory, WatchlistSourceDB, WatchlistTargetType
from src.schemas.common import MessageResponse, Paginated
from src.schemas.watchlist import (
    WatchlistCreate,
    WatchlistRead,
    WatchlistStats,
    WatchlistUpdate,
)

router = APIRouter()


def _to_read(entry) -> WatchlistRead:
    return WatchlistRead.model_validate(entry)


def _404() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Watchlist entry not found."
    )


@router.get("", response_model=Paginated[WatchlistRead])
async def list_watchlists(
    db: DBDep,
    _: CurrentUser,
    target_type: WatchlistTargetType | None = Query(default=None),
    category: WatchlistCategory | None = Query(default=None),
    source_db: WatchlistSourceDB | None = Query(default=None),
    active_only: bool = Query(default=False),
    search: str | None = Query(default=None, max_length=120),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> Paginated[WatchlistRead]:
    items, total = await wl_crud.list_watchlists(
        db,
        target_type=target_type,
        category=category,
        source_db=source_db,
        active_only=active_only,
        search=search,
        page=page,
        page_size=page_size,
    )
    return Paginated.build(
        [_to_read(e) for e in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=WatchlistRead, status_code=status.HTTP_201_CREATED)
async def create_watchlist_entry(
    body: WatchlistCreate,
    *,
    db: DBDep,
    current_user: StaffUser,
) -> WatchlistRead:
    entry = await wl_crud.create(db, body, added_by=current_user.id)
    return _to_read(entry)


@router.get("/stats", response_model=WatchlistStats)
async def watchlist_stats(
    db: DBDep,
    _: CurrentUser,
) -> WatchlistStats:
    data = await wl_crud.stats(db)
    return WatchlistStats(**data)


@router.get("/{entry_id}", response_model=WatchlistRead)
async def get_watchlist_entry(
    entry_id: UUID,
    *,
    db: DBDep,
    _: CurrentUser,
) -> WatchlistRead:
    entry = await wl_crud.get_by_id(db, entry_id)
    if entry is None:
        raise _404()
    return _to_read(entry)


@router.patch("/{entry_id}", response_model=WatchlistRead)
async def update_watchlist_entry(
    entry_id: UUID,
    body: WatchlistUpdate,
    *,
    db: DBDep,
    _: StaffUser,
) -> WatchlistRead:
    entry = await wl_crud.get_by_id(db, entry_id)
    if entry is None:
        raise _404()
    updated = await wl_crud.update(db, entry, body)
    return _to_read(updated)


@router.delete("/{entry_id}", response_model=MessageResponse)
async def delete_watchlist_entry(
    entry_id: UUID,
    *,
    db: DBDep,
    _: AdminUser,
) -> MessageResponse:
    entry = await wl_crud.get_by_id(db, entry_id)
    if entry is None:
        raise _404()
    await wl_crud.delete(db, entry)
    return MessageResponse(message="Watchlist entry deleted.")


@router.get("/lookup/{plate}", response_model=WatchlistRead | None)
async def lookup_plate(
    plate: str,
    *,
    db: DBDep,
    _: CurrentUser,
) -> WatchlistRead | None:
    """Fast plate lookup against the active watchlist. Returns null if not found."""
    entry = await wl_crud.get_by_identifier(db, plate)
    if entry is None:
        return None
    return _to_read(entry)
