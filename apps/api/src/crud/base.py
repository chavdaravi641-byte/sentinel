"""Generic CRUD helpers used across resource modules."""

import math
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


async def count_rows(db: AsyncSession, model: type) -> int:
    result = await db.execute(select(func.count(model.id)))
    return int(result.scalar_one())


def paginate(page: int, page_size: int, total: int) -> dict[str, int]:
    pages = math.ceil(total / page_size) if page_size else 0
    return {"page": page, "page_size": page_size, "pages": pages}


def clamp_page(page: int, page_size: int) -> tuple[int, int]:
    return max(1, page), min(max(1, page_size), 100)


def apply_filters(
    stmt: Any,
    filters: list[Any],
) -> Any:
    """Apply a list of SQLAlchemy binary expressions to a select stmt."""
    for f in filters:
        if f is not None:
            stmt = stmt.where(f)
    return stmt


__all__ = ["clamp_page", "count_rows", "paginate", "apply_filters"]