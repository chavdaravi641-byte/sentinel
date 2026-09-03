"""Part 9 — Observability: correlation / request / trace IDs and health.

A middleware that:

- trusts/accepts an inbound trace ID (``X-Trace-ID``) or generates a new one;
- generates a fresh request ID (backward compatible with the previous
  ``X-Request-ID`` behaviour);
- binds the request ID to the structlog context;
- returns ``X-Request-ID`` and ``X-Trace-ID`` response headers.
"""

from __future__ import annotations

import uuid
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.core.logging import bind_request, unbind_request


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def new_trace_id() -> str:
    return uuid.uuid4().hex


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """Correlation & trace ID management (supersedes the old request_context).

    Backward compatible: still sets ``X-Request-ID`` and binds the structlog
    context, and additionally maintains a trace (correlation) ID.
    """

    async def dispatch(self, request: Request, call_next):
        trace_id = request.headers.get("x-trace-id", "") or new_trace_id()
        request_id = request.headers.get("x-request-id", "") or new_id()
        request.state.request_id = request_id
        request.state.trace_id = trace_id
        bind_request(request_id, request.method, request.url.path)
        try:
            response: Response = await call_next(request)
        finally:
            unbind_request()
        response.headers.setdefault("X-Request-ID", request_id)
        response.headers.setdefault("X-Trace-ID", trace_id)
        return response


def health_diagnostics(**extra: Any) -> dict[str, Any]:
    """Return a diagnostics summary for health/readiness endpoints."""
    return {
        "service": "sentinel-api",
        "request_id": extra.get("request_id"),
        "trace_id": extra.get("trace_id"),
        **extra,
    }
