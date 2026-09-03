"""Statewide CCTV Registry & GIS endpoints (Model 1).

REST surface for the global camera registry: CRUD, bulk onboarding with
preview/commit/rollback, GIS layers (cluster/density/coverage), gap analysis,
health scoring, RBAC-guarded access, search (11 filters), audit log and
dashboard widgets. All heavy math is delegated to the pure-Python
:mod:`src.registry` engine so it runs identically at test time and at 80k+.

Resolves the effective registry RBAC from the existing auth (see
:func:`_registry_user`) and scopes every dataset render to the caller.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select

from src.api.deps import CurrentUser, DBDep
from src.models.camera import Camera, CameraStatus
from src.models.registry import (
    AccessRole,
    CameraAuditLog,
    CameraRegistry,
    RegistryEventType,
)
from src.registry import (
    SearchSpec,
    aggregate_by_district,
    all_widgets,
    analyze,
    apply_filters,
    build_plan,
    diff_before_after,
    fleet_health as fleet_health_agg,
    greedy_clusters,
    kmean_clusters,
    onboarding_summary,
    paginate,
    road_coverage,
    run_gap_report,
    score_camera,
    summarize_changes,
)
from src.registry.coverage import CameraPoint
from src.registry.roles import (
    RegistryUser,
    build_permission_matrix,
)
from src.schemas.common import MessageResponse
from src.schemas.registry import (
    AuditRead,
    CameraHealthScore,
    ClusterLayerItem,
    CoverageReport,
    GapReport,
    ImportCommit,
    ImportPreview,
    RegistryCameraCreate,
    RegistryCameraRead,
    RegistryCameraUpdate,
    RegistryOverview,
    RoadCoverageResult,
    RoleMatrix,
    SearchResult,
)

router = APIRouter()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _registry_user(user: CurrentUser, district: str | None = None,
                   department: str | None = None) -> RegistryUser:
    return RegistryUser.from_platform(str(user.id), user.role.value, full_name=user.full_name,
                                      district_code=district, department_code=department)


def _require(user: CurrentUser, action: str, *, district: str | None = None,
             department: str | None = None) -> RegistryUser:
    ruser = _registry_user(user, district, department)
    if not ruser.can(action):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail=f"role {ruser.role.value} lacks '{action}' permission")
    return ruser


def _404(detail: str = "Registry camera not found.") -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


async def _all_registry(db) -> list[CameraRegistry]:
    result = await db.execute(select(CameraRegistry))
    return list(result.scalars().all())


async def _all_cameras(db) -> dict[UUID, Camera]:
    result = await db.execute(select(Camera))
    return {c.id: c for c in result.scalars().all()}


def _registry_record(reg: CameraRegistry, cam: Camera | None) -> dict[str, Any]:
    return {
        "id": str(reg.id), "camera_id": str(reg.camera_id),
        "cctv_code": reg.cctv_code, "name": cam.name if cam else reg.cctv_code,
        "location": cam.location if cam else "",
        "latitude": reg.latitude, "longitude": reg.longitude,
        "district_code": reg.district_code, "state_code": reg.state_code,
        "department_code": reg.department_code, "board_code": reg.board_code,
        "category": reg.category.value, "ownership_type": reg.ownership_type.value,
        "status": cam.status.value if cam else "unknown",
        "serial_number": reg.serial_number, "ip_address": reg.ip_address,
        "make": reg.make, "model": reg.model, "firmware": reg.firmware,
        "mac_address": reg.mac_address, "orientation_deg": reg.orientation_deg,
        "notes": reg.notes,
        "coverage_radius_m": reg.coverage_radius_m, "gis_layer": reg.gis_layer,
        "cluster_key": reg.cluster_key, "health_level": "",
        "last_health_score": reg.last_health_score, "uptime_pct": reg.uptime_pct,
        "last_seen_at": reg.last_seen_at, "is_active": reg.is_active,
        "created_at": reg.created_at, "updated_at": reg.updated_at,
    }


def _as_points(records: list[dict[str, Any]]) -> list[CameraPoint]:
    return [CameraPoint(id=r["cctv_code"], lat=r["latitude"], lon=r["longitude"],
                        radius_m=r["coverage_radius_m"] or 250.0, category=r["category"],
                        status=r["status"], district_code=r["district_code"])
            for r in records if r["latitude"] is not None and r["longitude"] is not None]


def _scope_filter(user: RegistryUser, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if user.role in (AccessRole.STATE_ADMIN, AccessRole.VIEWER) and user.scope.kind == "state":
        return records
    return [r for r in records if user.in_scope(
        state_code=r.get("state_code", "GJ"),
        district_code=r.get("district_code"),
        department_code=r.get("department_code"))]


# --- role matrix / RBAC ------------------------------------------------------


@router.get("/roles/matrix", response_model=RoleMatrix)
async def role_matrix(_: CurrentUser) -> RoleMatrix:
    """Return the registry RBAC permission matrix (role -> allowed actions)."""
    return RoleMatrix(roles=build_permission_matrix())


# --- global registry CRUD ----------------------------------------------------


@router.get("", response_model=SearchResult)
async def search_registry(
    db: DBDep,
    current_user: CurrentUser,
    query: str | None = Query(default=None, max_length=120),
    district_code: str | None = None,
    department_code: str | None = None,
    board_code: str | None = None,
    category: str | None = None,
    status: str | None = None,
    ownership_type: str | None = None,
    health_level: str | None = None,
    gis_layer: str | None = None,
    cluster_key: str | None = None,
    lat: float | None = None,
    lng: float | None = None,
    radius_m: float | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=500),
    sort_by: str = "name",
    sort_dir: str = "asc",
) -> SearchResult:
    """Search the global registry with 11 composable filters."""
    ruser = _require(current_user, "search")
    regs = await _all_registry(db)
    cams = await _all_cameras(db)
    records = [_registry_record(r, cams.get(r.camera_id)) for r in regs]
    records = _scope_filter(ruser, records)
    spec = SearchSpec(
        query=query, district_code=district_code, department_code=department_code,
        board_code=board_code, category=category, status=status,
        ownership_type=ownership_type, health_level=health_level, gis_layer=gis_layer,
        cluster_key=cluster_key, geo_lat=lat, geo_lng=lng, geo_radius_m=radius_m,
        page=page, page_size=page_size, sort_by=sort_by, sort_dir=sort_dir,
    )
    return SearchResult(**paginate(apply_filters(records, spec), page, page_size))


@router.post("", response_model=RegistryCameraRead, status_code=status.HTTP_201_CREATED)
async def create_registry_camera(
    body: RegistryCameraCreate,
    *,
    db: DBDep,
    current_user: CurrentUser,
) -> RegistryCameraRead:
    """Register one camera into the global registry (create action)."""
    ruser = _require(current_user, "create")
    existing = (await db.execute(select(CameraRegistry).where(CameraRegistry.cctv_code == body.cctv_code))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="cctv_code already registered")
    if not ruser.in_scope(state_code=body.state_code, district_code=body.district_code,
                          department_code=body.department_code):
        raise HTTPException(status_code=403, detail="outside caller's jurisdiction")

    cam = Camera(
        name=body.name, rtsp_url=f"rtsp://{body.ip_address or '127.0.0.1'}:554/stream",
        location=body.location, latitude=body.latitude, longitude=body.longitude,
        status=CameraStatus(body.status),
    )
    db.add(cam)
    await db.flush()
    reg = CameraRegistry(
        camera_id=cam.id, cctv_code=body.cctv_code, serial_number=body.serial_number,
        make=body.make, model=body.model, firmware=body.firmware, category=body.category,
        ip_address=body.ip_address, mac_address=body.mac_address, ownership_type=body.ownership_type,
        state_code=body.state_code, district_code=body.district_code,
        department_code=body.department_code, board_code=body.board_code,
        latitude=body.latitude, longitude=body.longitude, gis_layer=body.gis_layer,
        coverage_radius_m=body.coverage_radius_m, orientation_deg=body.orientation_deg,
        notes=body.notes, registered_by=UUID(str(ruser.user_id)), is_active=True,
    )
    db.add(reg)
    db.add(CameraAuditLog(
        camera_id=cam.id, registry_id=reg.id, cctv_code=reg.cctv_code,
        event_type=RegistryEventType.CREATE, actor_id=UUID(str(ruser.user_id)),
        actor_role=ruser.role.value, scope=ruser.scope.kind, summary=f"registered {reg.cctv_code}",
        after=_registry_record(reg, cam),
    ))
    await db.commit()
    await db.refresh(reg)
    await db.refresh(cam)
    return RegistryCameraRead(**{**_registry_record(reg, cam), "camera_id": reg.camera_id, "status": cam.status.value})


@router.get("/{camera_id}", response_model=RegistryCameraRead)
async def get_registry_camera(
    camera_id: UUID,
    *,
    db: DBDep,
    current_user: CurrentUser,
) -> RegistryCameraRead:
    """Fetch one registered camera by its registry id."""
    _require(current_user, "view")
    reg = await db.get(CameraRegistry, camera_id)
    if reg is None:
        raise _404()
    cam = await db.get(Camera, reg.camera_id)
    return RegistryCameraRead(**{**_registry_record(reg, cam), "camera_id": reg.camera_id, "status": (cam.status.value if cam else "unknown")})


@router.patch("/{camera_id}", response_model=RegistryCameraRead)
async def update_registry_camera(
    camera_id: UUID,
    body: RegistryCameraUpdate,
    *,
    db: DBDep,
    current_user: CurrentUser,
) -> RegistryCameraRead:
    """Edit registry attributes (update action; audits changes)."""
    ruser = _require(current_user, "update")
    reg = await db.get(CameraRegistry, camera_id)
    if reg is None:
        raise _404()
    if not ruser.in_scope(state_code=reg.state_code, district_code=reg.district_code,
                          department_code=reg.department_code):
        raise HTTPException(status_code=403, detail="outside caller's jurisdiction")
    cam = await db.get(Camera, reg.camera_id)
    before = _registry_record(reg, cam)
    for key, value in body.model_dump(exclude_unset=True).items():
        if key in {"name", "location"} and cam is not None:
            setattr(cam, key, value)
        elif hasattr(reg, key):
            setattr(reg, key, value)
    after = _registry_record(reg, cam)
    changes = diff_before_after(before, after)
    if changes:
        db.add(CameraAuditLog(
            camera_id=reg.camera_id, registry_id=reg.id, cctv_code=reg.cctv_code,
            event_type=RegistryEventType.UPDATE, actor_id=UUID(str(ruser.user_id)),
            actor_role=ruser.role.value, scope=ruser.scope.kind,
            summary=summarize_changes(changes)[:255], before=before, after=after,
        ))
    await db.commit()
    await db.refresh(reg)
    return RegistryCameraRead(**{**_registry_record(reg, cam), "camera_id": reg.camera_id, "status": (cam.status.value if cam else "unknown")})


@router.delete("/{camera_id}", response_model=MessageResponse)
async def delete_registry_camera(
    camera_id: UUID,
    *,
    db: DBDep,
    current_user: CurrentUser,
) -> MessageResponse:
    """Remove a camera from the registry (delete action; audit recorded)."""
    ruser = _require(current_user, "delete")
    reg = await db.get(CameraRegistry, camera_id)
    if reg is None:
        raise _404()
    db.add(CameraAuditLog(
        camera_id=reg.camera_id, registry_id=reg.id, cctv_code=reg.cctv_code,
        event_type=RegistryEventType.DELETE, actor_id=UUID(str(ruser.user_id)),
        actor_role=ruser.role.value, scope=ruser.scope.kind, summary=f"deleted {reg.cctv_code}",
        before=_registry_record(reg, await db.get(Camera, reg.camera_id)),
    ))
    await db.delete(reg)
    await db.commit()
    return MessageResponse(message="Registry camera deleted.")


# --- bulk onboarding ---------------------------------------------------------


@router.post("/import/preview", response_model=ImportPreview)
async def import_preview(
    db: DBDep,
    current_user: CurrentUser,
    file: UploadFile = File(...),
    format: str = Form(default="csv"),
) -> ImportPreview:
    """Dry-run: parse + validate + dedupe an upload without writing anything."""
    _require(current_user, "create")
    content = await file.read()
    existing = await _all_registry(db)
    plan = build_plan(format, content, _preview_existing_codes([r.cctv_code for r in existing]))
    return ImportPreview(**plan.summary())


def _preview_existing_codes(existing_codes: list[str]):
    pool = {c.strip().upper() for c in existing_codes}
    return lambda _c: pool


@router.post("/import/commit", response_model=ImportCommit)
async def import_commit(
    db: DBDep,
    current_user: CurrentUser,
    file: UploadFile = File(...),
    format: str = Form(default="csv"),
) -> ImportCommit:
    """Validate + persist valid rows; the whole operation is transactional so a
    mid-chunk failure rolls everything back (rollback guarantee)."""
    ruser = _require(current_user, "create")
    content = await file.read()
    existing = await _all_registry(db)
    plan = build_plan(format, content, _preview_existing_codes([r.cctv_code for r in existing]))
    if not plan.can_commit:
        raise HTTPException(status_code=422, detail="cannot commit: fix validation errors first")

    valid_records = plan.valid_records
    committed = 0

    async def _persist_chunk(chunk: list[dict[str, Any]]) -> None:
        for rec in chunk:
            cam = Camera(
                name=rec.get("name", rec.get("cctv_code")), rtsp_url=f"rtsp://{rec.get('ip_address') or '127.0.0.1'}:554/stream",
                location=rec.get("location", ""), latitude=rec.get("latitude") or 0.0,
                longitude=rec.get("longitude") or 0.0, status=CameraStatus("unknown"),
            )
            db.add(cam)
            await db.flush()
            reg = CameraRegistry(
                camera_id=cam.id, cctv_code=rec["cctv_code"], serial_number=rec.get("serial_number"),
                make=rec.get("make"), model=rec.get("model"), firmware=rec.get("firmware"),
                category=rec.get("category") or "city", ip_address=rec.get("ip_address"),
                mac_address=rec.get("mac_address"), ownership_type=rec.get("ownership_type") or "state",
                state_code=rec.get("state_code") or "GJ", district_code=rec.get("district_code") or "UNK",
                department_code=rec.get("department_code"), board_code=rec.get("board_code"),
                latitude=rec.get("latitude") or 0.0, longitude=rec.get("longitude") or 0.0,
                gis_layer=rec.get("gis_layer"), coverage_radius_m=rec.get("coverage_radius_m") or 250.0,
                registered_by=UUID(str(ruser.user_id)), is_active=True,
            )
            db.add(reg)
            db.add(CameraAuditLog(
                camera_id=cam.id, registry_id=reg.id, cctv_code=reg.cctv_code,
                event_type=RegistryEventType.BULK_IMPORT, actor_id=UUID(str(ruser.user_id)),
                actor_role=ruser.role.value, scope=ruser.scope.kind,
                summary=f"bulk imported {reg.cctv_code}", after=_registry_record(reg, cam),
            ))

    try:
        for i in range(0, len(valid_records), 500):
            await _persist_chunk(valid_records[i:i + 500])
            committed += len(valid_records[i:i + 500])
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return ImportCommit(committed=committed, expected=plan.valid)


def _preview_existing_codes(existing_codes: list[str]):
    pool = {c.strip().upper() for c in existing_codes}
    return lambda _c: pool


# --- GIS engine --------------------------------------------------------------


@router.get("/gis/clusters", response_model=list[ClusterLayerItem])
async def gis_clusters(
    db: DBDep, current_user: CurrentUser,
    algo: str = Query(default="greedy", pattern="^(greedy|kmeans)$"),
    k: int = Query(default=20, ge=1, le=500),
    radius_m: float = Query(default=5000, ge=100, le=50000),
) -> list[ClusterLayerItem]:
    """Leaflet marker-cluster layer (greedy or k-means)."""
    ruser = _require(current_user, "gis")
    regs = await _all_registry(db)
    cams = await _all_cameras(db)
    records = _scope_filter(ruser, [_registry_record(r, cams.get(r.camera_id)) for r in regs])
    pts = _as_points(records)
    if algo == "kmeans":
        items = kmean_clusters(pts, k)
    else:
        items = greedy_clusters(pts, radius_m)
    return [ClusterLayerItem(**i) for i in items]


@router.get("/gis/density", response_model=list[dict[str, Any]])
async def gis_density(
    db: DBDep, current_user: CurrentUser,
    cell_m: float = Query(default=2000, ge=200, le=50000),
    radius_m: float = Query(default=1500, ge=100, le=50000),
) -> list[dict[str, Any]]:
    """Leaflet heat-map density layer (cameras per cell)."""
    ruser = _require(current_user, "gis")
    regs = await _all_registry(db)
    cams = await _all_cameras(db)
    records = _scope_filter(ruser, [_registry_record(r, cams.get(r.camera_id)) for r in regs])
    pts = _as_points(records)
    from src.registry.coverage import density_grid  # noqa: PLC0415
    return density_grid(pts, cell_m=cell_m, radius_m=radius_m)


@router.get("/gis/coverage", response_model=CoverageReport)
async def gis_coverage(
    db: DBDep, current_user: CurrentUser,
    cell_m: float = Query(default=500, ge=100, le=5000),
) -> CoverageReport:
    """Coverage analysis over the caller's fleet (union area, overlap, blind
    spots, density)."""
    ruser = _require(current_user, "gis")
    regs = await _all_registry(db)
    cams = await _all_cameras(db)
    records = _scope_filter(ruser, [_registry_record(r, cams.get(r.camera_id)) for r in regs])
    pts = _as_points(records)
    return CoverageReport(**analyze(pts, cell_m=cell_m))


@router.get("/gis/gaps", response_model=GapReport)
async def gis_gaps(
    db: DBDep, current_user: CurrentUser,
    cell_m: float = Query(default=4000, ge=500, le=50000),
) -> GapReport:
    """Gap analysis: blind spots + low-density zones + placement suggestions."""
    ruser = _require(current_user, "gis")
    regs = await _all_registry(db)
    cams = await _all_cameras(db)
    records = _scope_filter(ruser, [_registry_record(r, cams.get(r.camera_id)) for r in regs])
    pts = _as_points(records)
    return GapReport(**run_gap_report(pts, cell_m=cell_m))


@router.get("/gis/districts", response_model=list[dict[str, Any]])
async def gis_districts(db: DBDep, current_user: CurrentUser) -> list[dict[str, Any]]:
    """Per-district rollup for choropleth / chart widgets."""
    ruser = _require(current_user, "gis")
    regs = await _all_registry(db)
    cams = await _all_cameras(db)
    records = _scope_filter(ruser, [_registry_record(r, cams.get(r.camera_id)) for r in regs])
    pts = _as_points(records)
    return aggregate_by_district(pts)


@router.post("/gis/road-coverage", response_model=RoadCoverageResult)
async def gis_road_coverage(
    body: dict[str, Any],
    *,
    db: DBDep,
    current_user: CurrentUser,
) -> RoadCoverageResult:
    """How well supplied road / critical points are covered by the fleet."""
    ruser = _require(current_user, "gis")
    regs = await _all_registry(db)
    cams = await _all_cameras(db)
    records = _scope_filter(ruser, [_registry_record(r, cams.get(r.camera_id)) for r in regs])
    pts = _as_points(records)
    road_points = [(float(p["lat"]), float(p["lng"])) for p in body.get("points", []) if p.get("lat") is not None and p.get("lng") is not None]
    radius = body.get("radius_m")
    return RoadCoverageResult(**road_coverage(pts, road_points, radius_m=radius))


# --- health ------------------------------------------------------------------


@router.get("/health/scores/{camera_id}", response_model=CameraHealthScore)
async def camera_health_score(
    camera_id: UUID,
    *,
    db: DBDep,
    current_user: CurrentUser,
) -> CameraHealthScore:
    """Health score for one registered camera."""
    _require(current_user, "health")
    reg = await db.get(CameraRegistry, camera_id)
    if reg is None:
        raise _404()
    cam = await db.get(Camera, reg.camera_id)
    result = score_camera(cam.status.value if cam else "unknown", reg.last_seen_at, reg.uptime_pct)
    return CameraHealthScore(**result)


@router.get("/health/fleet")
async def fleet_health(db: DBDep, current_user: CurrentUser) -> dict[str, Any]:
    """Fleet-wide health aggregate for the caller's scope."""
    ruser = _require(current_user, "health")
    regs = await _all_registry(db)
    cams = await _all_cameras(db)
    records = _scope_filter(ruser, [_registry_record(r, cams.get(r.camera_id)) for r in regs])
    rows = [score_camera(r["status"], r["last_seen_at"], r["uptime_pct"]) for r in records]
    return fleet_health_agg(rows)


@router.get("/health/refresh", response_model=dict[str, Any])
async def health_refresh(db: DBDep, current_user: CurrentUser) -> dict[str, Any]:
    """Recompute health scores for all cameras in scope (maintain/health action)."""
    ruser = _require(current_user, "health")
    regs = await _all_registry(db)
    scored = 0
    for reg in regs:
        cam = await db.get(Camera, reg.camera_id)
        res = score_camera(cam.status.value if cam else "unknown", reg.last_seen_at, reg.uptime_pct)
        reg.last_health_score = int(res["score"])
        db.add(CameraAuditLog(
            camera_id=reg.camera_id, registry_id=reg.id, cctv_code=reg.cctv_code,
            event_type=RegistryEventType.HEALTH, actor_id=UUID(str(ruser.user_id)),
            actor_role=ruser.role.value, scope=ruser.scope.kind,
            summary=f"health {reg.cctv_code}: {res['level']} ({res['score']:.1f})",
            after={"last_health_score": reg.last_health_score},
        ))
        scored += 1
    await db.commit()
    return {"scored": scored, "method": "on_demand"}


# --- dashboard ----------------------------------------------------------------


@router.get("/dashboard/overview", response_model=RegistryOverview)
async def dashboard_overview(db: DBDep, current_user: CurrentUser) -> RegistryOverview:
    """Overview widget for the caller's scope."""
    ruser = _require(current_user, "view")
    regs = await _all_registry(db)
    cams = await _all_cameras(db)
    records = _scope_filter(ruser, [_registry_record(r, cams.get(r.camera_id)) for r in regs])
    ov = {k: v for k, v in all_widgets(records)["overview"].items()}
    return RegistryOverview(**ov)


@router.get("/dashboard/widgets")
async def dashboard_widgets(db: DBDep, current_user: CurrentUser) -> dict[str, Any]:
    """All dashboard widgets for the caller's scope."""
    ruser = _require(current_user, "view")
    regs = await _all_registry(db)
    cams = await _all_cameras(db)
    records = _scope_filter(ruser, [_registry_record(r, cams.get(r.camera_id)) for r in regs])
    return all_widgets(records)


@router.get("/dashboard/onboarding-summary")
async def dashboard_onboarding(db: DBDep, current_user: CurrentUser) -> dict[str, Any]:
    """Onboarding data-quality widget."""
    _require(current_user, "view")
    regs = await _all_registry(db)
    cams = await _all_cameras(db)
    records = [_registry_record(r, cams.get(r.camera_id)) for r in regs]
    return onboarding_summary(records)


# --- audit --------------------------------------------------------------------


@router.get("/audit", response_model=dict[str, Any])
async def audit_log(
    db: DBDep, current_user: CurrentUser,
    event_type: RegistryEventType | None = Query(default=None),
    cctv_code: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    """Read the registry audit log (audit action; admins)."""
    ruser = _require(current_user, "audit")
    stmt = select(CameraAuditLog).order_by(CameraAuditLog.created_at.desc())
    if event_type:
        stmt = stmt.where(CameraAuditLog.event_type == event_type)
    if cctv_code:
        stmt = stmt.where(CameraAuditLog.cctv_code == cctv_code)
    total = int((await db.execute(select(func.count()).select_from(CameraAuditLog))).scalar_one())
    result = await db.execute(stmt.offset((page - 1) * page_size).limit(page_size))
    items = [AuditRead.model_validate(a) for a in result.scalars().all()]
    pages = (total + page_size - 1) // page_size or 0
    return {"items": [i.model_dump() for i in items], "total": total, "page": page, "page_size": page_size, "pages": pages,
            "scope": ruser.scope.kind, "role": ruser.role.value}