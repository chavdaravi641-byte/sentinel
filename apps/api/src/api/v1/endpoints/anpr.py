"""Phase 4 ANPR & vehicle intelligence REST endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select

from src.api.deps import CurrentUser, DBDep, StaffUser
from src.anpr.benchmark import run_benchmark
from src.anpr.dataset import SyntheticDataset
from src.anpr.diagnostics import FrameDiagnostics
from src.anpr.evaluate import Evaluator
from src.anpr.pipeline import get_anpr_manager
from src.anpr.reports import ReportBuilder
from src.anpr.search import SearchEngine
from src.anpr.validator import PlateValidator
from src.core.logging import log
from src.models.anpr import AnprAlert, BlacklistEntry, EvidenceRecord, PlateDetection
from src.models.camera import Camera
from src.schemas.anpr import (
    AnprAlertRead,
    BenchmarkResult,
    BlacklistCreate,
    BlacklistRead,
    DashboardStats,
    DiagnosticSummary,
    EvalReport,
    EvalRunRequest,
    EvidenceRecordRead,
    FrequentPlate,
    PlateEventRead,
    TimelinePoint,
)
from src.schemas.common import MessageResponse, Paginated

router = APIRouter()


def _anpr_404(entity: str, entity_id: uuid.UUID) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail=f"{entity} not found: {entity_id}"
    )


async def _get_camera(db: DBDep, camera_id: uuid.UUID) -> Camera:
    camera = await db.get(Camera, camera_id)
    if camera is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found.")
    return camera


@router.get("/config", response_model=dict)
async def anpr_config(_: CurrentUser) -> dict:
    return get_anpr_manager().config_payload()


# ------------------------------------------------------------------------ #
# Dashboard
# ------------------------------------------------------------------------ #
@router.get("/dashboard", response_model=DashboardStats)
async def anpr_dashboard(*, db: DBDep, _: CurrentUser) -> DashboardStats:
    total_plates = int((await db.execute(select(func.count(PlateDetection.id)))).scalar_one())
    unique_plates = int(
        (
            await db.execute(
                select(func.count(func.distinct(PlateDetection.normalized_plate)))
            )
        ).scalar_one()
    )
    blacklisted_count = int(
        (
            await db.execute(
                select(func.count(BlacklistEntry.id)).where(BlacklistEntry.active.is_(True))
            )
        ).scalar_one()
    )
    active_alerts = int(
        (await db.execute(select(func.count(AnprAlert.id)).where(AnprAlert.resolved.is_(False)))).scalar_one()
    )
    cameras_active = len(
        [rt for rt in get_anpr_manager().cameras() if rt.active]
    )

    recent_rows = (
        (await db.execute(select(PlateDetection).order_by(PlateDetection.ts.desc()).limit(15)))
        .scalars()
        .all()
    )
    recent = [PlateEventRead.model_validate(r) for r in recent_rows]

    freq_rows = (
        await db.execute(
            select(
                PlateDetection.plate,
                PlateDetection.normalized_plate,
                func.count(PlateDetection.id).label("cnt"),
                func.max(PlateDetection.ts).label("last_seen"),
            )
            .group_by(PlateDetection.plate, PlateDetection.normalized_plate)
            .order_by(func.count(PlateDetection.id).desc())
            .limit(10)
        )
    ).all()
    frequent = [
        FrequentPlate(
            plate=r.plate, normalized_plate=r.normalized_plate,
            count=int(r.cnt), last_seen_at=r.last_seen,
        )
        for r in freq_rows
    ]

    by_color = dict(
        (await db.execute(select(PlateDetection.color, func.count()).group_by(PlateDetection.color))).all()
    )
    by_type = dict(
        (await db.execute(select(PlateDetection.vehicle_type, func.count()).group_by(PlateDetection.vehicle_type))).all()
    )
    by_state = dict(
        (await db.execute(select(PlateDetection.state_code, func.count()).group_by(PlateDetection.state_code))).all()
    )

    return DashboardStats(
        total_plates=total_plates,
        unique_plates=unique_plates,
        blacklisted_count=blacklisted_count,
        active_alerts=active_alerts,
        cameras_active=cameras_active,
        recent=recent,
        frequent=frequent,
        by_color={k: int(v) for k, v in by_color.items() if k},
        by_type={k: int(v) for k, v in by_type.items() if k},
        by_state={k: int(v) for k, v in by_state.items() if k},
    )


# ------------------------------------------------------------------------ #
# Intelligent search
# ------------------------------------------------------------------------ #
@router.get("/search", response_model=Paginated[PlateEventRead])
async def anpr_search(
    *,
    db: DBDep,
    _: CurrentUser,
    plate: str | None = Query(default=None),
    partial: str | None = Query(default=None),
    state: str | None = Query(default=None),
    color: str | None = Query(default=None),
    vehicle_type: str | None = Query(default=None),
    make: str | None = Query(default=None),
    model: str | None = Query(default=None),
    camera_id: uuid.UUID | None = Query(default=None),
    camera_name: str | None = Query(default=None),
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> Paginated[PlateEventRead]:
    result = await SearchEngine().search(
        db,
        plate=plate, partial=partial, state=state, color=color,
        vehicle_type=vehicle_type, make=make, model=model,
        camera_id=camera_id, camera_name=camera_name, start=start, end=end,
        page=page, page_size=page_size,
    )
    return Paginated.build(
        [PlateEventRead.model_validate(item) for item in result["items"]],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
    )


# ------------------------------------------------------------------------ #
# Blacklist CRUD
# ------------------------------------------------------------------------ #
@router.get("/blacklist", response_model=Paginated[BlacklistRead])
async def list_blacklist(
    *,
    db: DBDep,
    _: CurrentUser,
    active: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> Paginated[BlacklistRead]:
    stmt = select(BlacklistEntry)
    count_stmt = select(func.count(BlacklistEntry.id))
    if active is not None:
        stmt = stmt.where(BlacklistEntry.active.is_(active))
        count_stmt = count_stmt.where(BlacklistEntry.active.is_(active))
    total = int((await db.execute(count_stmt)).scalar_one())
    rows = (
        (await db.execute(stmt.order_by(BlacklistEntry.added_at.desc())
                          .offset((page - 1) * page_size).limit(page_size)))
        .scalars().all()
    )
    return Paginated.build(
        [BlacklistRead.model_validate(r) for r in rows],
        total=total, page=page, page_size=page_size,
    )


@router.post("/blacklist", response_model=BlacklistRead, status_code=status.HTTP_201_CREATED)
async def add_blacklist(body: BlacklistCreate, *, db: DBDep, _: StaffUser) -> BlacklistRead:
    from src.anpr.primitives import normalize_plate

    norm = normalize_plate(body.plate)
    existing = (
        await db.execute(
            select(BlacklistEntry).where(BlacklistEntry.normalized_plate == norm)
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Plate already blacklisted.")
    row = BlacklistEntry(
        plate=body.plate, normalized_plate=norm, reason=body.reason, note=body.note
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    # Hot-sync into the in-memory engine so the next match sees it immediately.
    get_anpr_manager()._blacklist.upsert(norm, reason=body.reason, note=body.note)
    log.info("anpr.blacklist.add", plate=norm, added_by=str(_get_uid(_)))
    return BlacklistRead.model_validate(row)


def _get_uid(user) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(user["id"])) if isinstance(user, dict) else uuid.UUID(str(user.id))
    except Exception:  # noqa: BLE001
        return None


@router.delete("/blacklist/{entry_id}", response_model=MessageResponse)
async def remove_blacklist(entry_id: uuid.UUID, *, db: DBDep, _: StaffUser) -> MessageResponse:
    row = await db.get(BlacklistEntry, entry_id)
    if row is None:
        raise _anpr_404("Blacklist entry", entry_id)
    await db.delete(row)
    await db.commit()
    get_anpr_manager()._blacklist.remove(row.normalized_plate)
    log.info("anpr.blacklist.remove", plate=row.normalized_plate)
    return MessageResponse(message="Blacklist entry removed.")


# ------------------------------------------------------------------------ #
# Alerts
# ------------------------------------------------------------------------ #
@router.get("/alerts", response_model=Paginated[AnprAlertRead])
async def list_anpr_alerts(
    *,
    db: DBDep,
    _: CurrentUser,
    camera_id: uuid.UUID | None = Query(default=None),
    rule: str | None = Query(default=None),
    resolved: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> Paginated[AnprAlertRead]:
    stmt = select(AnprAlert)
    count_stmt = select(func.count(AnprAlert.id))
    if camera_id:
        stmt = stmt.where(AnprAlert.camera_id == camera_id)
        count_stmt = count_stmt.where(AnprAlert.camera_id == camera_id)
    if rule:
        stmt = stmt.where(AnprAlert.rule == rule)
        count_stmt = count_stmt.where(AnprAlert.rule == rule)
    if resolved is not None:
        stmt = stmt.where(AnprAlert.resolved.is_(resolved))
        count_stmt = count_stmt.where(AnprAlert.resolved.is_(resolved))
    total = int((await db.execute(count_stmt)).scalar_one())
    rows = (
        (await db.execute(stmt.order_by(AnprAlert.last_seen_at.desc())
                          .offset((page - 1) * page_size).limit(page_size)))
        .scalars().all()
    )
    return Paginated.build(
        [AnprAlertRead.model_validate(r) for r in rows],
        total=total, page=page, page_size=page_size,
    )


@router.post("/alerts/{alert_id}/resolve", response_model=AnprAlertRead)
async def resolve_anpr_alert(alert_id: uuid.UUID, *, db: DBDep, _: StaffUser) -> AnprAlertRead:
    row = await db.get(AnprAlert, alert_id)
    if row is None:
        raise _anpr_404("Alert", alert_id)
    if not row.resolved:
        row.resolved = True
        row.resolved_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(row)
    return AnprAlertRead.model_validate(row)


# ------------------------------------------------------------------------ #
# Evidence
# ------------------------------------------------------------------------ #
@router.get("/evidence", response_model=Paginated[EvidenceRecordRead])
async def list_evidence(
    *,
    db: DBDep,
    _: CurrentUser,
    plate: str | None = Query(default=None),
    camera_id: uuid.UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> Paginated[EvidenceRecordRead]:
    stmt = select(EvidenceRecord)
    count_stmt = select(func.count(EvidenceRecord.id))
    if plate:
        stmt = stmt.where(EvidenceRecord.plate == plate)
        count_stmt = count_stmt.where(EvidenceRecord.plate == plate)
    if camera_id:
        stmt = stmt.where(EvidenceRecord.camera_id == camera_id)
        count_stmt = count_stmt.where(EvidenceRecord.camera_id == camera_id)
    total = int((await db.execute(count_stmt)).scalar_one())
    rows = (
        (await db.execute(stmt.order_by(EvidenceRecord.ts.desc())
                          .offset((page - 1) * page_size).limit(page_size)))
        .scalars().all()
    )
    return Paginated.build(
        [EvidenceRecordRead.model_validate(r) for r in rows],
        total=total, page=page, page_size=page_size,
    )


@router.get("/evidence/{record_id}/asset")
async def evidence_asset(
    record_id: uuid.UUID,
    kind: str = Query(...),
    *,
    db: DBDep,
    _: CurrentUser,
):
    """Serve an evidence JPEG artifact over authenticated REST."""
    record = await db.get(EvidenceRecord, record_id)
    if record is None:
        raise _anpr_404("Evidence record", record_id)
    if kind not in ("frame", "plate", "vehicle"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid kind.")
    from src.anpr.evidence import EvidenceStore

    store = EvidenceStore(
        enabled=True, root_dir=get_anpr_manager()._evidence.root_dir
    )
    resolved = store.asset_path(record, kind)
    if resolved is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found on disk.")
    return FileResponse(
        resolved,
        media_type="image/jpeg",
        filename=f"{kind}-{record.id}.jpg",
    )


# ------------------------------------------------------------------------ #
# Timeline / frequent / summary
# ------------------------------------------------------------------------ #
@router.get("/timeline", response_model=list[TimelinePoint])
async def anpr_timeline(
    *,
    db: DBDep,
    _: CurrentUser,
    plate: str | None = Query(default=None),
    camera_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[TimelinePoint]:
    stmt = (
        select(PlateDetection)
        .join(Camera, Camera.id == PlateDetection.camera_id)
        .order_by(PlateDetection.ts.desc())
        .limit(limit)
    )
    if plate:
        from src.anpr.primitives import normalize_plate

        stmt = stmt.where(PlateDetection.normalized_plate == normalize_plate(plate).upper())
    if camera_id:
        stmt = stmt.where(PlateDetection.camera_id == camera_id)
    rows = (await db.execute(stmt)).scalars().all()
    return [
        TimelinePoint(
            ts=r.ts,
            camera_id=r.camera_id,
            camera_name=r.camera_name,
            plate=r.plate,
            normalized_plate=r.normalized_plate,
            ocr_confidence=r.ocr_confidence,
            evidence_id=r.evidence_id,
        )
        for r in rows
    ]


@router.get("/frequent", response_model=list[FrequentPlate])
async def anpr_frequent(
    *,
    db: DBDep,
    _: CurrentUser,
    limit: int = Query(default=10, ge=1, le=50),
) -> list[FrequentPlate]:
    rows = (
        await db.execute(
            select(
                PlateDetection.plate,
                PlateDetection.normalized_plate,
                func.count(PlateDetection.id).label("cnt"),
                func.max(PlateDetection.ts).label("last_seen"),
            )
            .group_by(PlateDetection.plate, PlateDetection.normalized_plate)
            .order_by(func.count(PlateDetection.id).desc())
            .limit(limit)
        )
    ).all()
    return [
        FrequentPlate(
            plate=r.plate, normalized_plate=r.normalized_plate,
            count=int(r.cnt), last_seen_at=r.last_seen,
        )
        for r in rows
    ]


@router.post("/benchmark", response_model=BenchmarkResult)
async def anpr_benchmark(
    *,
    _: StaffUser,
    iterations: int = Query(default=50, ge=1, le=500),
    width: int = Query(default=640, ge=128, le=1920),
    height: int = Query(default=360, ge=128, le=1080),
) -> BenchmarkResult:
    manager = get_anpr_manager()
    report = run_benchmark(
        detector=manager._detector,
        ocr=manager._ocr,
        vehicles=manager._vehicles,
        iterations=iterations,
        width=width,
        height=height,
        batch_size=1,
    )
    return BenchmarkResult(**report)


# ------------------------------------------------------------------------ #
# Comprehensive evaluation (Phase 4 framework)
# ------------------------------------------------------------------------ #
@router.post("/eval/run", response_model=EvalReport)
async def anpr_eval_run(body: EvalRunRequest | None = None, *, _: StaffUser) -> EvalReport:
    """Run the full condition-aware evaluation over the synthetic corpus."""
    body = body or EvalRunRequest()
    manager = get_anpr_manager()
    evaluator = Evaluator(
        detector=manager._detector,
        ocr=manager._ocr,
        validator=PlateValidator(),
    )
    report = evaluator.evaluate_all(
        size_per_condition=body.size_per_condition,
        width=body.width,
        height=body.height,
        iou_threshold=body.iou_threshold,
    )
    return EvalReport(
        overall=report["overall"],
        per_condition=report["per_condition"],
        sample_count=report["sample_count"],
        hardware=_hardware_summary(),
    )


@router.get("/eval/report", response_model=EvalReport)
async def anpr_eval_report(
    size_per_condition: int = Query(default=60, ge=1, le=500),
    width: int = Query(default=640, ge=128, le=1920),
    height: int = Query(default=360, ge=128, le=1080),
    *,
    _: StaffUser,
) -> EvalReport:
    """Run evaluation and additionally emit chart/CSV artifacts to disk."""
    manager = get_anpr_manager()
    evaluator = Evaluator(
        detector=manager._detector,
        ocr=manager._ocr,
        validator=PlateValidator(),
    )
    report = evaluator.evaluate_all(
        size_per_condition=size_per_condition, width=width, height=height
    )
    from src.anpr.evaluate import _aggregate, SampleResult

    all_results: list[SampleResult] = []
    for cond in report["per_condition"]:
        cond_results, _ = evaluator.evaluate_condition(
            condition=cond, size=size_per_condition, width=width, height=height
        )
        all_results.extend(cond_results)
    report["overall"] = _aggregate(
        all_results,
        [r.detect_ms for r in all_results],
        [r.total_ms for r in all_results],
    )

    base = _eval_artifacts_dir()
    report_obj = ReportBuilder(evaluator, base)
    artifacts = report_obj.generate(report, all_results)
    return EvalReport(
        overall=report["overall"],
        per_condition=report["per_condition"],
        sample_count=report["sample_count"],
        hardware=_hardware_summary(),
        artifacts={k: str(v) for k, v in artifacts.items()},
    )


@router.get("/diagnostics", response_model=DiagnosticSummary)
async def anpr_diagnostics(
    condition: str = Query(default="day"),
    width: int = Query(default=640, ge=128, le=1920),
    height: int = Query(default=360, ge=128, le=1080),
    *,
    _: CurrentUser,
) -> DiagnosticSummary:
    """Self-diagnostics on a synthetic capture: blur/light/motion/dirty-lens."""
    ds = SyntheticDataset(seed=2026)
    sample = ds.generate(1, width, height, condition)[0]
    diag = FrameDiagnostics()
    return DiagnosticSummary(**diag.summarize(sample.frame))


def _hardware_summary() -> dict:
    info: dict = {"accelerator": "Not Measured"}
    try:
        manager = get_anpr_manager()
        info["device"] = manager._detector._device
        info["sim"] = manager._detector.is_sim
        info["ocr_engine"] = manager._ocr.engine
    except Exception:  # noqa: BLE001
        info["device"] = "unknown"
    return info


def _eval_artifacts_dir() -> str:
    import os

    path = os.environ.get("ANPR_EVAL_DIR", "/media/ai/anpr-eval")
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:  # noqa: BLE001 - read-only probes fall back to temp
        import tempfile

        path = os.path.join(tempfile.gettempdir(), "sentinel-anpr-eval")
        os.makedirs(path, exist_ok=True)
    return path


@router.get("/cameras", response_model=list[dict])
async def anpr_cameras(_: CurrentUser) -> list[dict]:
    manager = get_anpr_manager()
    return [
        {
            "camera_id": rt.camera_id,
            "camera_name": rt.camera_name,
            "inference_active": rt.active,
            "frames_analyzed": rt.frames_analyzed,
            "plates_read": rt.plates_read,
            "fps": round(rt.fps, 2),
        }
        for rt in manager.cameras()
    ]
