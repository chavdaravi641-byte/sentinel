"""Camera CRUD + test + health endpoints."""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from src.api.deps import AdminUser, CurrentUser, DBDep, StaffUser
from src.core.config import settings
from src.crud import camera as camera_crud
from src.models.camera import Camera, CameraStatus
from src.schemas.camera import (
    CameraCreate,
    CameraRead,
    CameraTestResult,
    CameraUpdate,
)
from src.schemas.common import MessageResponse, Paginated
from src.services import camera_test
from src.services.redis_service import get_camera_test, set_camera_test

router = APIRouter()


def _to_read(camera: Camera) -> CameraRead:
    return CameraRead.model_validate(camera)


def _camera_404() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found.")


@router.get("", response_model=Paginated[CameraRead])
async def list_cameras(
    db: DBDep,
    current_user: CurrentUser,
    camera_status: CameraStatus | None = Query(
        default=None, alias="status", description="Filter by camera status"
    ),
    search: str | None = Query(default=None, max_length=120),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> Paginated[CameraRead]:
    """List cameras with optional status/search filters and pagination."""
    items, total = await camera_crud.list_cameras(
        db,
        status=camera_status,
        search=search,
        page=page,
        page_size=page_size,
    )
    return Paginated.build(
        [_to_read(c) for c in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=CameraRead, status_code=status.HTTP_201_CREATED)
async def create_camera(
    body: CameraCreate,
    *,
    db: DBDep,
    _: StaffUser,
) -> CameraRead:
    """Register a new CCTV camera."""
    camera_obj = await camera_crud.create(db, body)
    return _to_read(camera_obj)


@router.get("/{camera_id}", response_model=CameraRead)
async def get_camera(
    camera_id: UUID,
    *,
    db: DBDep,
    _: CurrentUser,
) -> CameraRead:
    camera_obj = await camera_crud.get_by_id(db, camera_id)
    if camera_obj is None:
        raise _camera_404()
    return _to_read(camera_obj)


@router.patch("/{camera_id}", response_model=CameraRead)
async def update_camera(
    camera_id: UUID,
    body: CameraUpdate,
    *,
    db: DBDep,
    _: StaffUser,
) -> CameraRead:
    """Update camera attributes."""
    camera_obj = await camera_crud.get_by_id(db, camera_id)
    if camera_obj is None:
        raise _camera_404()
    updated = await camera_crud.update(db, camera_obj, body)
    return _to_read(updated)


@router.delete("/{camera_id}", response_model=MessageResponse)
async def delete_camera(
    camera_id: UUID,
    *,
    db: DBDep,
    _: AdminUser,
) -> MessageResponse:
    """Permanently delete a camera. Admin only."""
    camera_obj = await camera_crud.get_by_id(db, camera_id)
    if camera_obj is None:
        raise _camera_404()
    await camera_crud.delete(db, camera_obj)
    return MessageResponse(message="Camera deleted.")


@router.post("/{camera_id}/test", response_model=CameraTestResult)
async def test_camera_endpoint(
    camera_id: UUID,
    *,
    db: DBDep,
    _: CurrentUser,
) -> CameraTestResult:
    """Run a connectivity probe against the camera's RTSP endpoint.

    Phase 1 performs a TCP liveness + latency probe (a full RTSP handshake
    lands in a later phase). Results are cached in Redis for 10 minutes and
    the persisted camera status is derived from the probe result.
    """
    camera_obj = await camera_crud.get_by_id(db, camera_id)
    if camera_obj is None:
        raise _camera_404()

    probe = await camera_test.test_camera(
        camera_obj, timeout=settings.CAMERA_TEST_TIMEOUT_SECONDS
    )
    probe["tested_at"] = datetime.now(timezone.utc)

    derived = camera_test.apply_probe_status(camera_obj, probe)
    if derived != camera_obj.status:
        await camera_crud.set_status(
            db,
            camera_obj,
            derived,
            last_seen=datetime.now(timezone.utc) if derived == CameraStatus.ONLINE else None,
        )

    await set_camera_test(str(camera_id), probe)
    return CameraTestResult.model_validate(probe)


@router.get("/{camera_id}/health", response_model=CameraTestResult | None)
async def camera_health(
    camera_id: UUID,
    *,
    db: DBDep,
    _: CurrentUser,
) -> CameraTestResult | None:
    """Return the last cached connectivity result for a camera, if any."""
    cached = await get_camera_test(str(camera_id))
    if cached is None:
        return None
    cached["id"] = str(camera_id)
    return CameraTestResult.model_validate(cached)