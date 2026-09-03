"""Incident data access."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.crud.base import clamp_page
from src.models.camera import Camera
from src.models.incident import Incident, IncidentStatus, IncidentType
from src.models.user import User
from src.schemas.incident import IncidentCreate, IncidentUpdate

IncidentRow = tuple[Incident, str | None, str | None]


async def list_incidents(
    db: AsyncSession,
    *,
    status: IncidentStatus | None,
    incident_type: IncidentType | None,
    page: int,
    page_size: int,
) -> tuple[list[IncidentRow], int]:
    page, page_size = clamp_page(page, page_size)
    stmt = (
        select(Incident, Camera.name.label("camera_name"), User.full_name.label("reporter"))
        .outerjoin(Camera, Camera.id == Incident.camera_id)
        .outerjoin(User, User.id == Incident.reported_by)
    )
    count_stmt = select(func.count(Incident.id))

    if status is not None:
        stmt = stmt.where(Incident.status == status)
        count_stmt = count_stmt.where(Incident.status == status)
    if incident_type is not None:
        stmt = stmt.where(Incident.type == incident_type)
        count_stmt = count_stmt.where(Incident.type == incident_type)

    stmt = (
        stmt.order_by(Incident.occurred_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(stmt)).all()
    total = int((await db.execute(count_stmt)).scalar_one())
    return [(incident, camera_name, reporter) for incident, camera_name, reporter in rows], total


async def get_with_relations(db: AsyncSession, incident_id: UUID) -> IncidentRow | None:
    row = (
        await db.execute(
            select(Incident, Camera.name, User.full_name)
            .outerjoin(Camera, Camera.id == Incident.camera_id)
            .outerjoin(User, User.id == Incident.reported_by)
            .where(Incident.id == incident_id)
        )
    ).first()
    if row is None:
        return None
    return row[0], row[1], row[2]


async def get_by_id(db: AsyncSession, incident_id: UUID) -> Incident | None:
    return await db.get(Incident, incident_id)


async def create(
    db: AsyncSession, data: IncidentCreate, reporter_id: UUID | None = None
) -> Incident:
    payload = data.model_dump(exclude_unset=True)
    payload["occurred_at"] = (
        data.occurred_at or datetime.now(timezone.utc)
    )
    incident = Incident(
        **{**payload, "reported_by": reporter_id},
    )
    db.add(incident)
    await db.commit()
    await db.refresh(incident)
    return incident


async def update(db: AsyncSession, incident: Incident, data: IncidentUpdate) -> Incident:
    for key, value in data.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(incident, key, value)
    await db.commit()
    await db.refresh(incident)
    return incident


async def status_counts(db: AsyncSession) -> dict[str, int]:
    rows = (
        await db.execute(select(Incident.status, func.count()).group_by(Incident.status))
    ).all()
    return {status.value: int(count) for status, count in rows}