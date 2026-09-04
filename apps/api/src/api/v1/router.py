"""Aggregates all versioned endpoint routers."""

from fastapi import APIRouter

from src.api.v1.endpoints import (
    alerts,
    anpr,
    auth,
    cameras,
    copilot,
    dashboard,
    health,
    incidents,
    inference,
    registry,
    security,
    streams,
    vehicle_intel,
    vehicles,
    watchlist,
)
from src.api.v1.ws import router as ws_router

from src.federation.iam_api import iam_router
from src.cluster.router import router as cluster_router

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(cameras.router, prefix="/cameras", tags=["cameras"])
api_router.include_router(alerts.router, prefix="/alerts", tags=["alerts"])
api_router.include_router(incidents.router, prefix="/incidents", tags=["incidents"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(streams.router, prefix="/streams", tags=["streams"])
api_router.include_router(inference.router, prefix="/inference", tags=["inference"])
api_router.include_router(anpr.router, prefix="/anpr", tags=["anpr"])
api_router.include_router(vehicle_intel.router, prefix="/vehicle-intel", tags=["vehicle-intel"])
api_router.include_router(copilot.router, prefix="/copilot", tags=["copilot"])
api_router.include_router(registry.router, prefix="/registry", tags=["registry", "gis"])
api_router.include_router(security.router, prefix="/security", tags=["security"])
api_router.include_router(watchlist.router, prefix="/watchlists", tags=["watchlists"])
api_router.include_router(vehicles.router, prefix="/vehicles", tags=["vehicles", "forensics"])
api_router.include_router(ws_router, tags=["inference"])
api_router.include_router(iam_router, tags=["iam"])
api_router.include_router(cluster_router, tags=["cluster"])