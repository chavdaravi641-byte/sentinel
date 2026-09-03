"""Phase 3 inference REST endpoints: config, models, lifecycle, telemetry."""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select

from src.api.deps import CurrentUser, DBDep, StaffUser
from src.core.logging import log
from src.inference.engine import get_inference_manager
from src.models.camera import Camera
from src.models.inference import (
    AiModel,
    Detection,
    InferenceAlert,
    InferenceRun,
)
from src.schemas.common import MessageResponse, Paginated
from src.schemas.inference import (
    AiModelRead,
    BenchmarkRequest,
    BenchmarkResult,
    DetectionRead,
    InferenceAlertRead,
    InferenceConfig,
    InferenceRunRead,
)

router = APIRouter()


def _camera_404(camera_id: UUID) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found.")


def _model_404(name: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Model '{name}' not registered.")


async def _get_camera(db: DBDep, camera_id: UUID) -> Camera:
    camera_obj = await db.get(Camera, camera_id)
    if camera_obj is None:
        raise _camera_404(camera_id)
    return camera_obj


async def _model_read(db: DBDep, name: str) -> AiModelRead:
    row = (await db.execute(select(AiModel).where(AiModel.name == name))).scalar_one_or_none()
    if row is not None:
        return AiModelRead.model_validate(row)
    snapshot = next((m for m in get_inference_manager().models() if m["name"] == name), None)
    if snapshot is None:
        raise _model_404(name)
    return AiModelRead(**snapshot)


# ------------------------------------------------------------------------ #
# Config / models
# ------------------------------------------------------------------------ #
@router.get("/config", response_model=InferenceConfig)
async def inference_config(_: CurrentUser) -> InferenceConfig:
    return InferenceConfig(**await get_inference_manager().config_payload())


@router.get("/models", response_model=list[AiModelRead])
async def list_models(*, db: DBDep, _: CurrentUser) -> list[AiModelRead]:
    engine = get_inference_manager()
    for snapshot in engine.models():
        engine.store.submit_model(snapshot)
    rows = (await db.execute(select(AiModel).order_by(AiModel.name))).scalars().all()
    if rows:
        return [AiModelRead.model_validate(row) for row in rows]
    return [AiModelRead(**m) for m in engine.models()]


@router.get("/models/{name}", response_model=AiModelRead)
async def get_model(name: str, *, db: DBDep, _: CurrentUser) -> AiModelRead:
    return await _model_read(db, name)


def _require_plugin(name: str):
    engine = get_inference_manager()
    try:
        return engine.plugin(name)
    except KeyError:
        raise _model_404(name)


@router.post("/models/{name}/load", response_model=AiModelRead)
async def load_model(name: str, *, db: DBDep, _: StaffUser) -> AiModelRead:
    _require_plugin(name)
    await get_inference_manager().model_load(name)
    return await _model_read(db, name)


@router.post("/models/{name}/reload", response_model=AiModelRead)
async def reload_model(name: str, *, db: DBDep, _: StaffUser) -> AiModelRead:
    _require_plugin(name)
    await get_inference_manager().model_reload(name)
    return await _model_read(db, name)


@router.post("/models/{name}/unload", response_model=AiModelRead)
async def unload_model(name: str, *, db: DBDep, _: StaffUser) -> AiModelRead:
    _require_plugin(name)
    await get_inference_manager().model_unload(name)
    return await _model_read(db, name)


@router.get("/models/{name}/health", response_model=dict)
async def model_health(name: str, *, _: CurrentUser) -> dict:
    plugin = _require_plugin(name)
    return {**plugin.health(), "active_pumps": len([rt for rt in get_inference_manager().cameras() if rt.active])}


# ------------------------------------------------------------------------ #
# Raw image inference
# ------------------------------------------------------------------------ #
@router.post("/infer")
async def infer_image(file: UploadFile = File(...), *, _: CurrentUser) -> dict:
    jpeg = await file.read()
    if not jpeg:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty image upload.")
    engine = get_inference_manager()
    try:
        return await engine.analyze_image(jpeg)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Model not loaded: {exc}")


# ------------------------------------------------------------------------ #
# Per-camera runtime
# ------------------------------------------------------------------------ #
@router.get("/cameras/{camera_id}/status", response_model=dict)
async def camera_inference_status(camera_id: UUID, *, db: DBDep, _: CurrentUser) -> dict:
    camera_obj = await _get_camera(db, camera_id)
    return await get_inference_manager().camera_status(camera_obj)


@router.get("/cameras/{camera_id}/stats", response_model=dict)
async def camera_inference_stats(camera_id: UUID, *, db: DBDep, _: CurrentUser) -> dict:
    camera_obj = await _get_camera(db, camera_id)
    return await get_inference_manager().camera_stats(camera_obj)


@router.post("/cameras/{camera_id}/start", response_model=dict)
async def start_camera_inference(camera_id: UUID, *, db: DBDep, _: StaffUser) -> dict:
    camera_obj = await _get_camera(db, camera_id)
    engine = get_inference_manager()
    await engine.camera_start(camera_obj)
    log.info("inference.camera_start", camera_id=str(camera_id))
    return await engine.camera_stats(camera_obj)


@router.post("/cameras/{camera_id}/stop", response_model=MessageResponse)
async def stop_camera_inference(camera_id: UUID, *, db: DBDep, _: StaffUser) -> MessageResponse:
    await _get_camera(db, camera_id)
    await get_inference_manager().camera_stop(str(camera_id))
    log.info("inference.camera_stop", camera_id=str(camera_id))
    return MessageResponse(message="Inference stopped.")


@router.get("/cameras/{camera_id}/overlay/last", response_model=dict)
async def last_overlay(camera_id: UUID, *, db: DBDep, _: CurrentUser) -> dict:
    await _get_camera(db, camera_id)
    payload = get_inference_manager().last_overlay(str(camera_id))
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No overlay published yet. Start inference on a running stream.",
        )
    return payload


# ------------------------------------------------------------------------ #
# Persisted history
# ------------------------------------------------------------------------ #
@router.get("/runs", response_model=Paginated[InferenceRunRead])
async def list_runs(
    *,
    db: DBDep,
    _: CurrentUser,
    camera_id: UUID | None = Query(default=None),
    model: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
) -> Paginated[InferenceRunRead]:
    stmt = select(InferenceRun)
    count_stmt = select(func.count(InferenceRun.id))
    if camera_id:
        stmt = stmt.where(InferenceRun.camera_id == camera_id)
        count_stmt = count_stmt.where(InferenceRun.camera_id == camera_id)
    if model:
        stmt = stmt.where(InferenceRun.model_name == model)
        count_stmt = count_stmt.where(InferenceRun.model_name == model)
    total = int((await db.execute(count_stmt)).scalar_one())
    stmt = stmt.order_by(InferenceRun.ts.desc()).offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(stmt)).scalars().all()
    return Paginated.build(
        [InferenceRunRead.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/runs/{run_id}/detections", response_model=list[DetectionRead])
async def run_detections(run_id: UUID, *, db: DBDep, _: CurrentUser) -> list[DetectionRead]:
    run = await db.get(InferenceRun, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found.")
    rows = (
        await db.execute(
            select(Detection).where(Detection.run_id == run_id).order_by(Detection.confidence.desc())
        )
    ).scalars().all()
    return [DetectionRead.model_validate(r) for r in rows]


@router.get("/detections", response_model=Paginated[DetectionRead])
async def list_detections(
    *,
    db: DBDep,
    _: CurrentUser,
    camera_id: UUID | None = Query(default=None),
    class_name: str | None = Query(default=None),
    model: str | None = Query(default=None),
    min_confidence: float | None = Query(default=None, ge=0.0, le=1.0),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
) -> Paginated[DetectionRead]:
    stmt = select(Detection)
    count_stmt = select(func.count(Detection.id))
    if camera_id:
        stmt = stmt.where(Detection.camera_id == camera_id)
        count_stmt = count_stmt.where(Detection.camera_id == camera_id)
    if class_name:
        stmt = stmt.where(Detection.class_name == class_name)
        count_stmt = count_stmt.where(Detection.class_name == class_name)
    if model:
        stmt = stmt.where(Detection.model_name == model)
        count_stmt = count_stmt.where(Detection.model_name == model)
    if min_confidence is not None:
        stmt = stmt.where(Detection.confidence >= min_confidence)
        count_stmt = count_stmt.where(Detection.confidence >= min_confidence)
    total = int((await db.execute(count_stmt)).scalar_one())
    stmt = stmt.order_by(Detection.ts.desc()).offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(stmt)).scalars().all()
    return Paginated.build(
        [DetectionRead.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/alerts", response_model=Paginated[InferenceAlertRead])
async def list_inference_alerts(
    *,
    db: DBDep,
    _: CurrentUser,
    camera_id: UUID | None = Query(default=None),
    resolved: bool | None = Query(default=None),
    rule: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> Paginated[InferenceAlertRead]:
    stmt = select(InferenceAlert)
    count_stmt = select(func.count(InferenceAlert.id))
    if camera_id:
        stmt = stmt.where(InferenceAlert.camera_id == camera_id)
        count_stmt = count_stmt.where(InferenceAlert.camera_id == camera_id)
    if resolved is not None:
        stmt = stmt.where(InferenceAlert.resolved.is_(resolved))
        count_stmt = count_stmt.where(InferenceAlert.resolved.is_(resolved))
    if rule:
        stmt = stmt.where(InferenceAlert.rule == rule)
        count_stmt = count_stmt.where(InferenceAlert.rule == rule)
    total = int((await db.execute(count_stmt)).scalar_one())
    stmt = stmt.order_by(InferenceAlert.last_seen_at.desc()).offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(stmt)).scalars().all()
    return Paginated.build(
        [InferenceAlertRead.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/alerts/{alert_id}/resolve", response_model=InferenceAlertRead)
async def resolve_inference_alert(alert_id: UUID, *, db: DBDep, _: StaffUser) -> InferenceAlertRead:
    row = await db.get(InferenceAlert, alert_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inference alert not found.")
    if not row.resolved:
        row.resolved = True
        row.resolved_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(row)
    return InferenceAlertRead.model_validate(row)


@router.get("/summary", response_model=dict)
async def inference_summary(*, db: DBDep, _: CurrentUser) -> dict:
    return await get_inference_manager().summary(db)


@router.post("/benchmark", response_model=BenchmarkResult)
async def run_benchmark(body: BenchmarkRequest, *, _: StaffUser) -> BenchmarkResult:
    from src.inference.benchmark import run_benchmark as _run_benchmark

    engine = get_inference_manager()
    report = await _run_benchmark(
        engine=engine,
        iterations=body.iterations,
        width=body.image_width,
        height=body.image_height,
        batch_size=body.batch_size,
    )
    return BenchmarkResult(**report)