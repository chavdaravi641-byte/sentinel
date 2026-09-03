"""Incident endpoints: reporting and case management."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from src.api.deps import CurrentUser, DBDep, StaffUser
from src.crud import incident as incident_crud
from src.models.incident import IncidentStatus, IncidentType
from src.schemas.common import Paginated
from src.schemas.incident import IncidentCreate, IncidentRead, IncidentUpdate

router = APIRouter()


def _to_read(row: incident_crud.IncidentRow) -> IncidentRead:
    incident, camera_name, reporter = row
    read = IncidentRead.model_validate(incident)
    read.camera_name = camera_name
    read.reported_by_name = reporter
    return read


def _incident_404() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found."
    )


@router.get("", response_model=Paginated[IncidentRead])
async def list_incidents(
    db: DBDep,
    current_user: CurrentUser,
    incident_status: IncidentStatus | None = Query(default=None, alias="status"),
    incident_type: IncidentType | None = Query(default=None, alias="type"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> Paginated[IncidentRead]:
    """List logged incidents with optional filters."""
    rows, total = await incident_crud.list_incidents(
        db,
        status=incident_status,
        incident_type=incident_type,
        page=page,
        page_size=page_size,
    )
    return Paginated.build(
        [_to_read(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=IncidentRead, status_code=status.HTTP_201_CREATED)
async def create_incident(
    body: IncidentCreate,
    *,
    db: DBDep,
    current_user: CurrentUser,
) -> IncidentRead:
    """Log a new incident. Reporters are tracked for accountability."""
    incident_obj = await incident_crud.create(db, body, reporter_id=current_user.id)
    row = await incident_crud.get_with_relations(db, incident_obj.id)
    return _to_read(row or (incident_obj, None, None))


@router.get("/{incident_id}", response_model=IncidentRead)
async def get_incident(
    incident_id: UUID,
    *,
    db: DBDep,
    _: CurrentUser,
) -> IncidentRead:
    row = await incident_crud.get_with_relations(db, incident_id)
    if row is None:
        raise _incident_404()
    return _to_read(row)


@router.patch("/{incident_id}", response_model=IncidentRead)
async def update_incident(
    incident_id: UUID,
    body: IncidentUpdate,
    *,
    db: DBDep,
    _: StaffUser,
) -> IncidentRead:
    """Update an incident (type, severity, status)."""
    incident_obj = await incident_crud.get_by_id(db, incident_id)
    if incident_obj is None:
        raise _incident_404()
    updated = await incident_crud.update(db, incident_obj, body)
    row = await incident_crud.get_with_relations(db, updated.id)
    return _to_read(row or (updated, None, None))