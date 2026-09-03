"""Sentinel AI FastAPI application entrypoint.

Bootstrap order:
  1. Middleware (security headers, size limits, CORS, request/trace IDs, logging)
  2. Routers (health, auth, security, cameras, alerts, incidents, dashboard)
  3. Optional idempotent seed on startup

Phase 6.2 adds additive hardening middleware (security headers, request body
size limits, observability with request+correlation IDs) without changing any
existing endpoint behaviour.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.v1.router import api_router
from src.core.config import settings
from src.core.logging import log
from src.core.redis import close_redis
from src.security.headers import RequestSizeLimitMiddleware, SecurityHeadersMiddleware
from src.security.observability import ObservabilityMiddleware, new_id
from src.services.media.manager import get_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle hooks."""
    if settings.SEED_ON_STARTUP:
        from src.seed import run_seed

        log.info("startup.seed", enabled=True)
        try:
            await run_seed()
        except Exception:
            log.warning("startup.seed_failed", exc_info=True)

    # Federation IAM: create tables and idempotently seed default data (isolated DB).
    try:
        from src.federation.db import AsyncSessionLocal, init_federation_db
        from src.federation.iam_seed import seed

        await init_federation_db()
        async with AsyncSessionLocal() as fed_session:
            await seed(fed_session)
        log.info("startup.federation_iam", enabled=True)
    except Exception:
        log.warning("startup.federation_iam_failed", exc_info=True)

    # Phase 7.1/7.2: cluster orchestration -- isolated DB + durable state + maintenance.
    try:
        from src.cluster.db import init_cluster_db
        from src.cluster.service import get_service, install_durable_cluster

        await init_cluster_db()
        # Phase 7.2: move ownership state into durable shared storage and
        # recover it on boot (persistent ownership across restarts). Falls back
        # to the in-memory store if durability cannot be initialised.
        await install_durable_cluster()
        await get_service().start()
        log.info("startup.cluster_orchestration", enabled=True)
    except Exception:
        log.warning("startup.cluster_orchestration_failed", exc_info=True)

    log.info(
        "startup.complete",
        project=settings.PROJECT_NAME,
        environment=settings.ENVIRONMENT,
        version=settings.VERSION,
    )
    from src.inference.engine import get_inference_manager

    await get_inference_manager().start()
    from src.anpr.pipeline import get_anpr_manager

    await get_anpr_manager().start()
    yield
    await get_anpr_manager().shutdown()
    await get_inference_manager().shutdown()
    await get_manager().shutdown()
    from src.cluster.service import get_service

    try:
        await get_service().stop()
    except Exception:
        pass
    await close_redis()
    log.info("shutdown.complete")


app = FastAPI(
    title=settings.PROJECT_NAME,
    description=(
        "Gujarat Police CCTV Intelligence Platform - Phase 1 backend. "
        "Authentication, camera inventory, alert/incident management and "
        "operational dashboards."
    ),
    version=settings.VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Phase 6.2 additive hardening middleware.
if settings.SECURITY_HEADERS_ENABLED:
    app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestSizeLimitMiddleware)
app.add_middleware(ObservabilityMiddleware)


@app.middleware("http")
async def unhandled_error_handler(request: Request, call_next):
    """Final safety net: JSON 500 responses with a request id."""
    request_id = getattr(request.state, "request_id", None) or new_id()
    try:
        return await call_next(request)
    except Exception as exc:  # noqa: BLE001 - final safety net
        log.error("request.unhandled_error", error=str(exc))
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": "Internal server error.",
                "request_id": request_id,
            },
        )


@app.get("/", include_in_schema=False)
async def root() -> dict:
    return {
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs": "/docs",
        "health": f"{settings.API_V1_PREFIX}/health",
    }


app.include_router(api_router, prefix=settings.API_V1_PREFIX)

# import side-effect ensures logging config is applied before serving
from src.core import logging as _logging  # noqa: F401

__all__ = ["app"]