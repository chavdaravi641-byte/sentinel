"""Liveness / readiness probes for orchestration and the UI status pill."""

import time

from fastapi import APIRouter
from sqlalchemy import text

from src.api.deps import DBDep
from src.core.config import settings
from src.core.redis import redis_client
from src.schemas.common import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse, include_in_schema=True)
async def health(db: DBDep) -> HealthResponse:
    """Probe database and redis connectivity along with base latency."""

    def _component(status: str, latency_ms: float | None) -> dict:
        return {"status": status, "latency_ms": latency_ms}

    db_status, db_latency = "degraded", None
    try:
        start = time.perf_counter()
        await db.execute(text("SELECT 1"))
        db_latency = round((time.perf_counter() - start) * 1000, 2)
        db_status = "ok"
    except Exception:
        pass

    redis_status, redis_latency = "degraded", None
    try:
        start = time.perf_counter()
        await redis_client.ping()
        redis_latency = round((time.perf_counter() - start) * 1000, 2)
        redis_status = "ok"
    except Exception:
        pass

    status = "ok" if db_status == "ok" and redis_status == "ok" else "degraded"
    return HealthResponse(
        status=status,
        version=settings.VERSION,
        components={
            "database": _component(db_status, db_latency),
            "redis": _component(redis_status, redis_latency),
        },
    )