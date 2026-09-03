"""Part 5 — Security headers middleware.

Sets the standard hardening response headers. HSTS is only emitted for
production HTTPS deployments; in development it is suppressed so local testing
is unaffected.

Headers set:
  Content-Security-Policy (CSP)
  Strict-Transport-Security (HSTS, production only)
  X-Frame-Options
  X-Content-Type-Options
  Referrer-Policy
  Permissions-Policy
  X-XSS-Protection (legacy, informational)
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.core.config import settings


def security_headers(env: str | None = None) -> dict[str, str]:
    env = env or settings.ENVIRONMENT
    headers = {
        # Restrict content sources; self + inline styles/images for the SPA.
        "Content-Security-Policy": (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; "
            "connect-src 'self' ws: wss:; "
            "frame-ancestors 'self'; "
            "base-uri 'self'; "
            "form-action 'self'"
        ),
        "X-Frame-Options": "SAMEORIGIN",
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": (
            "geolocation=(), microphone=(), camera=(), payment=(), usb=()"
        ),
        "X-XSS-Protection": "1; mode=block",
        "X-Download-Options": "noopen",
        "X-Permitted-Cross-Domain-Policies": "none",
    }
    if settings.SECURITY_HEADERS_HSTS and env == "production":
        headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return headers


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach the security headers to every response."""

    async def dispatch(self, request: Request, call_next):
        if not settings.SECURITY_HEADERS_ENABLED:
            return await call_next(request)
        response: Response = await call_next(request)
        for name, value in security_headers().items():
            response.headers.setdefault(name, value)
        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject oversized request bodies (Part 4)."""

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length is not None and content_length.isdigit():
            from src.security.api import request_too_large

            if request_too_large(int(content_length)):
                from starlette.responses import JSONResponse

                return JSONResponse(
                    status_code=413,
                    content={"detail": "Request body too large."},
                )
        return await call_next(request)
