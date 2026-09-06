"""Dashboard aggregation endpoint."""

from datetime import datetime, timezone

from fastapi import APIRouter
from sqlalchemy import func, select

from src.api.deps import CurrentUser, DBDep
from src.core.config import settings
from src.crud import alert as alert_crud
from src.crud import camera as camera_crud
from src.crud import incident as incident_crud
from src.models.camera import CameraStatus
from src.models.inference import Detection
from src.schemas.alert import AlertRead
from src.schemas.incident import IncidentRead
from src.schemas.dashboard import (
    CameraGeoPoint,
    DashboardSummary,
    SystemHealth,
)
from src.services.redis_service import ping as redis_ping

router = APIRouter()


@router.get("/summary", response_model=DashboardSummary)
async def dashboard_summary(
    db: DBDep,
    current_user: CurrentUser,
) -> DashboardSummary:
    """Aggregated numbers + live grid geodata for the command center."""

    # Camera status breakdown
    camera_counts = await camera_crud.status_counts(db)
    total = camera_counts.pop("total", 0)
    active = camera_counts.get(CameraStatus.ONLINE.value, 0)
    offline = camera_counts.get(CameraStatus.OFFLINE.value, 0)
    maintenance = camera_counts.get(CameraStatus.MAINTENANCE.value, 0)
    unknown = camera_counts.get(CameraStatus.UNKNOWN.value, 0)

    # Recent alerts
    recent_alerts = []
    for alert, camera_name in await alert_crud.recent(db, limit=6):
        read = AlertRead.model_validate(alert)
        read.camera_name = camera_name
        recent_alerts.append(read)

    # Live grid points
    geo_rows = await camera_crud.all_geo(db)
    camera_geo = [
        CameraGeoPoint(
            id=cam.id,
            name=cam.name,
            latitude=cam.latitude,
            longitude=cam.longitude,
            status=cam.status,
        )
        for cam in geo_rows
    ]

    # Alert aggregates (single query pass)
    alert_stats = await alert_crud.stats(db)

    # Operational context for the first viewport.
    latest_rows, _ = await incident_crud.list_incidents(db, status=None, incident_type=None, page=1, page_size=1)
    latest_incident = None
    if latest_rows:
        incident, camera_name, reporter_name = latest_rows[0]
        latest_incident = IncidentRead.model_validate(incident)
        latest_incident.camera_name = camera_name
        latest_incident.reported_by_name = reporter_name

    start_of_day = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    detections_today = int(
        (
            await db.execute(
                select(func.count(Detection.id)).where(Detection.ts >= start_of_day)
            )
        ).scalar_one()
    )

    redis_latency = await redis_ping()
    is_db_ok = True  # this endpoint only resolves when the DB session works
    system = SystemHealth(
        api="ok",
        database="ok" if is_db_ok else "degraded",
        redis="ok" if redis_latency is not None else "degraded",
        version=settings.VERSION,
    )

    return DashboardSummary(
        cameras={
            "total": total,
            "active": active,
            "offline": offline,
            "maintenance": maintenance,
            "unknown": unknown,
        },
        alerts={
            "total": alert_stats.total,
            "new": alert_stats.new,
            "critical": alert_stats.critical,
        },
        recent_alerts=recent_alerts,
        camera_geo=camera_geo,
        system=system,
        latest_incident=latest_incident,
        detections_today=detections_today,
    )