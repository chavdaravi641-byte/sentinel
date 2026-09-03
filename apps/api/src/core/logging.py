"""Structured logging configuration built on structlog.

Logs are emitted as JSON in production environments and as pretty key/value
lines during local development.
"""

import logging
import sys

import structlog

from src.core.config import settings

is_json = settings.ENVIRONMENT.upper() in {"PRODUCTION", "STAGING"}


def _configure_stdlib() -> None:
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.INFO if not is_json else logging.WARNING,
    )
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


_configure_stdlib()

_PROCESSORS: list = [
    structlog.contextvars.merge_contextvars,
    structlog.processors.add_log_level,
    structlog.processors.TimeStamper(fmt="iso", utc=True),
    structlog.processors.StackInfoRenderer(),
    structlog.processors.format_exc_info,
]

if is_json:
    _PROCESSORS.append(structlog.processors.JSONRenderer())
else:
    _PROCESSORS.append(structlog.dev.ConsoleRenderer(sort_keys=False))

structlog.configure(
    processors=_PROCESSORS,
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

log = structlog.get_logger("sentinel")


def bind_request(request_id: str, method: str, path: str) -> None:
    """Bind context that will appear on every log line within a request."""
    structlog.contextvars.bind_contextvars(
        request_id=request_id,
        method=method,
        path=path,
    )


def unbind_request() -> None:
    structlog.contextvars.clear_contextvars()