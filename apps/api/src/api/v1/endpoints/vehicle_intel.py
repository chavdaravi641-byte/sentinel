"""Phase 5 / 5.1 — Global Vehicle Identity Engine REST endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query
from sqlalchemy import select

from src.api.deps import CurrentUser, DBDep, StaffUser
from src.anpr.vehicle_intel import (
    associate,
    assign_identity,
    build_evidence_timeline,
    compute_traffic_insights,
    predict_next_cameras,
    reconstruct_route,
)
from src.anpr.vehicle_intel.benchmark import run_benchmark
from src.anpr.vehicle_intel.cache import cache_set_json
from src.anpr.vehicle_intel.identity_bench import run_identity_benchmark
from src.anpr.vehicle_intel.multimodal import fuse_identity, VehicleCandidate
from src.anpr.vehicle_intel.service import get_graph
from src.core.logging import log
from src.models.anpr import PlateDetection
from src.schemas.vehicle_intel import (
    AssociationRead,
    AssociationRequest,
    FusedIdentityRead,
    FusedIdentityRequest,
    GraphRead,
    IdentityRead,
    Phase5MetricsRead,
    PredictionRead,
    PredictionRequest,
    RouteRead,
    RouteRequest,
    SearchRequest,
    TimelineRead,
    TimelineRequest,
)

router = APIRouter()


def _identity_payload(identity) -> dict:
    return identity.to_dict()


def _candidate_from_schema(schema) -> VehicleCandidate:
    history = [(str(h[0]), float(h[1])) for h in (schema.history or []) if h]
    return VehicleCandidate(
        vehicle_uuid=schema.vehicle_uuid,
        canonical_plate=schema.canonical_plate,
        plate_confidence=schema.plate_confidence,
        color=schema.color,
        vehicle_type=schema.vehicle_type,
        make=schema.make,
        model=schema.model,
        aspect_ratio=schema.aspect_ratio,
        wheelbase=schema.wheelbase,
        roofline=schema.roofline,
        embedding=schema.embedding,
        history=history,
        sighting_count=schema.sighting_count,
    )


# ------------------------------------------------------------------------ #
# Identity
# ------------------------------------------------------------------------ #
@router.post("/identity/assign", response_model=IdentityRead)
async def assign_vehicle_identity(body: dict, _: CurrentUser) -> IdentityRead:
    """Assign the permanent global identity for an observation payload."""
    identity = assign_identity(
        plate=body.get("plate", ""),
        appearance=body.get("appearance"),
        shape_embedding=body.get("shape_embedding"),
        ocr_confidence=float(body.get("ocr_confidence", 0.0)),
        plate_confidence_threshold=float(body.get("plate_confidence_threshold", 0.45)),
    )
    return IdentityRead(**identity.to_dict())


# ------------------------------------------------------------------------ #
# Phase 5.1 — Multi-modal probabilistic identity
# ------------------------------------------------------------------------ #
@router.post("/identity/fuse", response_model=FusedIdentityRead)
async def fuse_vehicle_identity(
    body: FusedIdentityRequest, *, db: DBDep, _: CurrentUser
) -> FusedIdentityRead:
    """Fuse a probe against a candidate gallery using 12 signals with
    confidence-weighted fusion. Returns identity_uuid, identity_confidence,
    identity_reasoning, feature_contributions and ambiguity_score."""
    graph = await get_graph(db)
    candidates = [_candidate_from_schema(c) for c in body.candidates]
    fused = fuse_identity(
        body.probe, candidates, graph, match_threshold=body.match_threshold
    )
    return FusedIdentityRead(**fused.to_dict())


@router.post("/identity/benchmark-51", response_model=dict)
async def identity_51_benchmark(*, _: StaffUser) -> dict:
    """Run the Phase 5.1 multi-modal identity benchmark (labelled synthetic)."""
    report = run_identity_benchmark()
    await cache_set_json("identity51", report, ttl=3600)
    log.info("anpr.vehicle_intel.identity51", overall=report["overall_accuracy"])
    return report


# ------------------------------------------------------------------------ #
# Camera graph
# ------------------------------------------------------------------------ #
@router.get("/graph", response_model=GraphRead)
async def camera_graph(
    *, db: DBDep, _: CurrentUser, max_link_km: float = Query(default=12.0, ge=0.5, le=50)
) -> GraphRead:
    """Return the derived camera graph (real registered cameras only)."""
    graph = await get_graph(db, max_link_km=max_link_km)
    payload = graph.to_payload()
    return GraphRead(**payload)


# ------------------------------------------------------------------------ #
# Association
# ------------------------------------------------------------------------ #
@router.post("/associate", response_model=AssociationRead)
async def associate_observations(
    body: AssociationRequest, *, db: DBDep, _: CurrentUser
) -> AssociationRead:
    graph = await get_graph(db)
    result = associate(body.obs_a, body.obs_b, graph, match_threshold=body.match_threshold)
    return AssociationRead(**result.to_dict())


# ------------------------------------------------------------------------ #
# Route reconstruction
# ------------------------------------------------------------------------ #
@router.post("/route/reconstruct", response_model=RouteRead)
async def reconstruct_observations(
    body: RouteRequest, *, db: DBDep, _: CurrentUser
) -> RouteRead:
    obs = sorted(body.observations, key=lambda o: float(o.get("ts", 0)))
    graph = await get_graph(db)
    route = reconstruct_route(body.vehicle_uuid, obs, graph)
    return RouteRead(**route.to_dict())


# ------------------------------------------------------------------------ #
# Route prediction
# ------------------------------------------------------------------------ #
@router.post("/route/predict", response_model=PredictionRead)
async def predict_next(
    body: PredictionRequest, *, db: DBDep, _: CurrentUser
) -> PredictionRead:
    graph = await get_graph(db)
    pred = predict_next_cameras(body.current_camera, body.history, graph, top_k=5)
    return PredictionRead(
        current_camera=pred.current_camera,
        predictions=pred.predictions,
        total_confidence=pred.total_confidence,
        basis=pred.basis,
        history_length=pred.history_length,
    )


# ------------------------------------------------------------------------ #
# Timeline
# ------------------------------------------------------------------------ #
@router.post("/timeline", response_model=TimelineRead)
async def evidence_timeline(
    body: TimelineRequest, *, db: DBDep, _: CurrentUser
) -> TimelineRead:
    graph = await get_graph(db)
    result = build_evidence_timeline(body.sightings, graph, gap_minutes=body.gap_minutes)
    return TimelineRead(**result)


# ------------------------------------------------------------------------ #
# Investigation / search
# ------------------------------------------------------------------------ #
@router.post("/investigate", response_model=dict)
async def investigate(
    body: SearchRequest, *, db: DBDep, _: CurrentUser
) -> dict:
    """Investigate: find sightings matching a query, then build a timeline +
    route summary for the first matched vehicle."""
    from src.anpr.vehicle_intel.search_workspace import SearchQuery, search_observations

    graph = await get_graph(db)

    # Pull recent plate detections from the DB (real data) as the observation set.
    det_rows = (
        (await db.execute(select(PlateDetection).order_by(PlateDetection.ts.desc()).limit(2000)))
        .scalars()
        .all()
    )
    sightings = []
    for r in det_rows:
        identity = assign_identity(
            r.plate,
            {
                "vehicle_type": r.vehicle_type,
                "color": r.color,
                "make": r.make,
                "model": r.model,
            },
            ocr_confidence=r.ocr_confidence,
        )
        sightings.append(
            {
                "vehicle_uuid": identity.vehicle_uuid,
                "camera_id": str(r.camera_id),
                "camera_name": r.camera_name or str(r.camera_id),
                "location": r.location or "",
                "plate": r.plate,
                "appearance": {
                    "vehicle_type": r.vehicle_type,
                    "color": r.color,
                    "make": r.make,
                    "model": r.model,
                },
                "ocr_confidence": r.ocr_confidence,
                "ts": r.ts.timestamp() if r.ts else 0,
                "attributes": {},
            }
        )

    query = SearchQuery(
        plate=body.plate,
        vehicle_type=body.vehicle_type,
        color=body.color,
        location=body.location,
        near_lat=body.near_lat,
        near_lng=body.near_lng,
        radius_km=body.radius_km,
        min_confidence=body.min_confidence,
        start_ts=body.start_ts,
        end_ts=body.end_ts,
        limit=body.limit,
    )
    matches = search_observations(sightings, graph, query)
    if not matches:
        return {"vehicle_uuid": None, "matches": [], "message": "No matching sightings."}

    top = matches[0]["vehicle_uuid"]
    vehicle_sightings = [o for o in sightings if o["vehicle_uuid"] == top]
    timeline = build_evidence_timeline(vehicle_sightings, graph)
    route = reconstruct_route(top, vehicle_sightings, graph)
    return {
        "vehicle_uuid": top,
        "matches": matches,
        "timeline": timeline,
        "route_summary": route.to_dict(),
    }


# ------------------------------------------------------------------------ #
# Traffic intelligence (over real DB detections)
# ------------------------------------------------------------------------ #
@router.get("/traffic", response_model=dict)
async def traffic_intelligence(
    *, db: DBDep, _: CurrentUser, limit: int = Query(default=2000, ge=1, le=5000)
) -> dict:
    graph = await get_graph(db)
    det_rows = (
        (await db.execute(select(PlateDetection).order_by(PlateDetection.ts.desc()).limit(limit)))
        .scalars()
        .all()
    )
    sightings = []
    for r in det_rows:
        identity = assign_identity(
            r.plate,
            {"vehicle_type": r.vehicle_type, "color": r.color, "make": r.make, "model": r.model},
            ocr_confidence=r.ocr_confidence,
        )
        sightings.append(
            {
                "vehicle_uuid": identity.vehicle_uuid,
                "camera_id": str(r.camera_id),
                "ts": r.ts.timestamp() if r.ts else 0,
                "plate": r.plate,
                "appearance": {
                    "vehicle_type": r.vehicle_type,
                    "color": r.color,
                    "make": r.make,
                    "model": r.model,
                },
                "ocr_confidence": r.ocr_confidence,
            }
        )
    insights = compute_traffic_insights(sightings, graph)
    return insights.to_dict()


# ------------------------------------------------------------------------ #
# Benchmark / validation
# ------------------------------------------------------------------------ #
@router.post("/benchmark", response_model=Phase5MetricsRead)
async def phase5_benchmark(*, _: StaffUser) -> Phase5MetricsRead:
    """Run the labelled synthetic benchmark and report real Phase 5 metrics."""
    report = run_benchmark()
    await cache_set_json("benchmark", report, ttl=3600)
    log.info("anpr.vehicle_intel.benchmark", trials=report["trials"], wall_ms=report["wall_ms"])
    return Phase5MetricsRead(**report["metrics"])
