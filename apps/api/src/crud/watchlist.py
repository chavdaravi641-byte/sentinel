"""Watchlist data access."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.crud.base import clamp_page
from src.models.watchlist import (
    Watchlist,
    WatchlistCategory,
    WatchlistSourceDB,
    WatchlistTargetType,
)
from src.schemas.watchlist import WatchlistCreate, WatchlistUpdate


async def get_by_id(db: AsyncSession, watchlist_id: UUID) -> Watchlist | None:
    return await db.get(Watchlist, watchlist_id)


async def get_by_identifier(db: AsyncSession, identifier: str) -> Watchlist | None:
    """Look up a watchlist entry by normalized identifier (e.g., plate number)."""
    normalized = identifier.upper().replace(" ", "")
    stmt = select(Watchlist).where(
        Watchlist.identifier_number == normalized,
        Watchlist.active.is_(True),
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def create(db: AsyncSession, data: WatchlistCreate, added_by: UUID | None = None) -> Watchlist:
    entry = Watchlist(**data.model_dump(), added_by=added_by)
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


async def update(db: AsyncSession, entry: Watchlist, data: WatchlistUpdate) -> Watchlist:
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(entry, key, value)
    await db.commit()
    await db.refresh(entry)
    return entry


async def delete(db: AsyncSession, entry: Watchlist) -> None:
    await db.delete(entry)
    await db.commit()


async def list_watchlists(
    db: AsyncSession,
    *,
    target_type: WatchlistTargetType | None = None,
    category: WatchlistCategory | None = None,
    source_db: WatchlistSourceDB | None = None,
    active_only: bool = False,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Watchlist], int]:
    page, page_size = clamp_page(page, page_size)
    stmt = select(Watchlist)
    count_stmt = select(func.count(Watchlist.id))

    if target_type is not None:
        stmt = stmt.where(Watchlist.target_type == target_type)
        count_stmt = count_stmt.where(Watchlist.target_type == target_type)
    if category is not None:
        stmt = stmt.where(Watchlist.category == category)
        count_stmt = count_stmt.where(Watchlist.category == category)
    if source_db is not None:
        stmt = stmt.where(Watchlist.source_db == source_db)
        count_stmt = count_stmt.where(Watchlist.source_db == source_db)
    if active_only:
        stmt = stmt.where(Watchlist.active.is_(True))
        count_stmt = count_stmt.where(Watchlist.active.is_(True))
    if search:
        escaped = search.strip().lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        like = f"%{escaped}%"
        cond = Watchlist.identifier_number.ilike(like, escape="\\") | Watchlist.notes.ilike(like, escape="\\")
        stmt = stmt.where(cond)
        count_stmt = count_stmt.where(cond)

    stmt = stmt.order_by(Watchlist.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    total = int((await db.execute(count_stmt)).scalar_one())
    return list(result.scalars().all()), total


async def stats(db: AsyncSession) -> dict:
    total = int((await db.execute(select(func.count(Watchlist.id)))).scalar_one())
    active = int(
        (await db.execute(
            select(func.count(Watchlist.id)).where(Watchlist.active.is_(True))
        )).scalar_one()
    )

    by_type_rows = (
        await db.execute(select(Watchlist.target_type, func.count()).group_by(Watchlist.target_type))
    ).all()
    by_type = {r[0].value: r[1] for r in by_type_rows}

    by_cat_rows = (
        await db.execute(select(Watchlist.category, func.count()).group_by(Watchlist.category))
    ).all()
    by_category = {r[0].value: r[1] for r in by_cat_rows}

    by_src_rows = (
        await db.execute(select(Watchlist.source_db, func.count()).group_by(Watchlist.source_db))
    ).all()
    by_source = {r[0].value: r[1] for r in by_src_rows}

    return {
        "total": total,
        "active": active,
        "inactive": total - active,
        "by_type": by_type,
        "by_category": by_category,
        "by_source": by_source,
    }
