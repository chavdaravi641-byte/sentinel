"""Alert endpoints: history, filtering, lifecycle, stats."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from src.api.deps import CurrentUser, DBDep, StaffUser
from src.crud import alert as alert_crud
from src.models.alert import AlertSeverity, AlertStatus, AlertType
from src.schemas.alert import AlertRead, AlertStats, AlertUpdate
from src.schemas.common import Paginated

router = APIRouter()


def _to_read(row: alert_crud.AlertRow) -> AlertRead:
    alert, camera_name = row
    read = AlertRead.model_validate(alert)
    read.camera_name = camera_name
    return read


def _alert_404() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found.")


@router.get("", response_model=Paginated[AlertRead])
async def list_alerts(
    db: DBDep,
    current_user: CurrentUser,
    severity: AlertSeverity | None = Query(default=None),
    alert_status: AlertStatus | None = Query(default=None, alias="status"),
    alert_type: AlertType | None = Query(default=None, alias="type"),
    camera_id: UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> Paginated[AlertRead]:
    """List alerts (detections raised by the intelligence layer)."""
    rows, total = await alert_crud.list_alerts(
        db,
        severity=severity,
        status=alert_status,
        alert_type=alert_type,
        camera_id=camera_id,
        page=page,
        page_size=page_size,
    )
    return Paginated.build(
        [_to_read(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/stats", response_model=AlertStats)
async def alerts_stats(
    db: DBDep,
    current_user: CurrentUser,
) -> AlertStats:
    """Aggregate alert statistics used by dashboards and analytics."""
    return await alert_crud.stats(db)


@router.get("/{alert_id}", response_model=AlertRead)
async def get_alert(
    alert_id: UUID,
    *,
    db: DBDep,
    _: CurrentUser,
) -> AlertRead:
    row = await alert_crud.get_with_camera(db, alert_id)
    if row is None:
        raise _alert_404()
    return _to_read(row)


@router.patch("/{alert_id}", response_model=AlertRead)
async def update_alert(
    alert_id: UUID,
    body: AlertUpdate,
    *,
    db: DBDep,
    _: StaffUser,
) -> AlertRead:
    """Acknowledge / escalate / resolve an alert."""
    alert_obj = await alert_crud.get_by_id(db, alert_id)
    if alert_obj is None:
        raise _alert_404()
    updated = await alert_crud.update(db, alert_obj, body)
    row = await alert_crud.get_with_camera(db, updated.id)
    return _to_read(row or (updated, None))