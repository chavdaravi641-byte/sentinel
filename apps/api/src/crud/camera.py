"""Camera data access."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.crud.base import clamp_page, count_rows
from src.models.camera import Camera, CameraStatus
from src.schemas.camera import CameraCreate, CameraUpdate


async def get_by_id(db: AsyncSession, camera_id: UUID) -> Camera | None:
    return await db.get(Camera, camera_id)


async def create(db: AsyncSession, data: CameraCreate) -> Camera:
    camera = Camera(**data.model_dump())
    db.add(camera)
    await db.commit()
    await db.refresh(camera)
    return camera


async def update(db: AsyncSession, camera: Camera, data: CameraUpdate) -> Camera:
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(camera, key, value)
    await db.commit()
    await db.refresh(camera)
    return camera


async def delete(db: AsyncSession, camera: Camera) -> None:
    await db.delete(camera)
    await db.commit()


async def list_cameras(
    db: AsyncSession,
    *,
    status: CameraStatus | None,
    search: str | None,
    page: int,
    page_size: int,
) -> tuple[list[Camera], int]:
    page, page_size = clamp_page(page, page_size)
    stmt = select(Camera)
    count_stmt = select(func.count(Camera.id))

    if status is not None:
        stmt = stmt.where(Camera.status == status)
        count_stmt = count_stmt.where(Camera.status == status)
    if search:
        escaped = search.strip().lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        like = f"%{escaped}%"
        cond = Camera.name.ilike(like, escape="\\") | Camera.location.ilike(like, escape="\\")
        stmt = stmt.where(cond)
        count_stmt = count_stmt.where(cond)

    stmt = stmt.order_by(Camera.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    total = int((await db.execute(count_stmt)).scalar_one())
    return list(result.scalars().all()), total


async def status_counts(db: AsyncSession) -> dict[str, int]:
    rows = (await db.execute(select(Camera.status, func.count()).group_by(Camera.status))).all()
    counts = {status.value: 0 for status in CameraStatus}
    for status, count in rows:
        counts[status.value] = count
    counts["total"] = sum(v for k, v in counts.items() if k != "total")
    return counts


async def all_geo(db: AsyncSession) -> list[Camera]:
    result = await db.execute(
        select(Camera).where(Camera.is_active.is_(True)).order_by(Camera.name)
    )
    return list(result.scalars().all())


async def set_status(db: AsyncSession, camera: Camera, status: CameraStatus, last_seen: object = None) -> None:
    camera.status = status
    camera.last_seen_at = last_seen
    await db.commit()