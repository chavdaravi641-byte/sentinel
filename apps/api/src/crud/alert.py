"""Alert data access."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.crud.base import clamp_page
from src.models.alert import Alert, AlertSeverity, AlertStatus, AlertType
from src.models.camera import Camera
from src.schemas.alert import AlertStats, AlertUpdate

AlertRow = tuple[Alert, str | None]


async def list_alerts(
    db: AsyncSession,
    *,
    severity: AlertSeverity | None,
    status: AlertStatus | None,
    alert_type: AlertType | None,
    camera_id: UUID | None,
    page: int,
    page_size: int,
) -> tuple[list[AlertRow], int]:
    page, page_size = clamp_page(page, page_size)
    stmt = select(Alert, Camera.name.label("camera_name")).outerjoin(
        Camera, Camera.id == Alert.camera_id
    )
    count_stmt = select(func.count(Alert.id))

    conditions: list = []
    if severity is not None:
        conditions.append(Alert.severity == severity)
    if status is not None:
        conditions.append(Alert.status == status)
    if alert_type is not None:
        conditions.append(Alert.type == alert_type)
    if camera_id is not None:
        conditions.append(Alert.camera_id == camera_id)

    for cond in conditions:
        stmt = stmt.where(cond)
        count_stmt = count_stmt.where(cond)

    stmt = (
        stmt.order_by(Alert.occurred_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(stmt)).all()
    total = int((await db.execute(count_stmt)).scalar_one())
    return [(alert, name) for alert, name in rows], total


async def get_with_camera(db: AsyncSession, alert_id: UUID) -> AlertRow | None:
    row = (
        await db.execute(
            select(Alert, Camera.name)
            .outerjoin(Camera, Camera.id == Alert.camera_id)
            .where(Alert.id == alert_id)
        )
    ).first()
    if row is None:
        return None
    return row[0], row[1]


async def get_by_id(db: AsyncSession, alert_id: UUID) -> Alert | None:
    return await db.get(Alert, alert_id)


async def update(db: AsyncSession, alert: Alert, data: AlertUpdate) -> Alert:
    for key, value in data.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(alert, key, value)
    await db.commit()
    await db.refresh(alert)
    return alert


async def stats(db: AsyncSession) -> AlertStats:
    total = int((await db.execute(select(func.count(Alert.id)))).scalar_one())
    by_status = dict(
        (await db.execute(select(Alert.status, func.count()).group_by(Alert.status))).all()
    )
    by_severity = dict(
        (await db.execute(select(Alert.severity, func.count()).group_by(Alert.severity))).all()
    )
    by_type = dict(
        (await db.execute(select(Alert.type, func.count()).group_by(Alert.type))).all()
    )

    def _dict(enum_cls, raw) -> dict[str, int]:
        return {m.value: int(raw.get(m, 0)) for m in enum_cls}

    return AlertStats(
        total=total,
        new=int(by_status.get(AlertStatus.NEW, 0)),
        acknowledged=int(by_status.get(AlertStatus.ACKNOWLEDGED, 0)),
        escalated=int(by_status.get(AlertStatus.ESCALATED, 0)),
        resolved=int(by_status.get(AlertStatus.RESOLVED, 0)),
        critical=int(by_severity.get(AlertSeverity.CRITICAL, 0)),
        by_type=_dict(AlertType, by_type),
        by_severity=_dict(AlertSeverity, by_severity),
    )


async def recent(db: AsyncSession, limit: int = 6) -> list[AlertRow]:
    rows = (
        await db.execute(
            select(Alert, Camera.name)
            .outerjoin(Camera, Camera.id == Alert.camera_id)
            .order_by(Alert.occurred_at.desc())
            .limit(limit)
        )
    ).all()
    return [(alert, name) for alert, name in rows]


async def severity_counts(db: AsyncSession) -> dict[str, int]:
    rows = (
        await db.execute(select(Alert.severity, func.count()).group_by(Alert.severity))
    ).all()
    return {severity.value: int(count) for severity, count in rows}


async def new_count(db: AsyncSession) -> int:
    return int(
        (
            await db.execute(
                select(func.count(Alert.id)).where(Alert.status == AlertStatus.NEW)
            )
        ).scalar_one()
    )