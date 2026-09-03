"""Redis-backed operational state (camera health, cache, counters)."""

import json
import time
from datetime import datetime
from typing import Any

from src.core.config import settings
from src.core.redis import redis_client

CAMERA_TEST_KEY = "camera:test:{camera_id}"
ALERT_COUNTER_KEY = "counters:alerts"


async def set_camera_test(camera_id: str, result: dict[str, Any]) -> None:
    """Cache the most recent camera connectivity test result (10 min TTL)."""
    await redis_client.set(
        CAMERA_TEST_KEY.format(camera_id=camera_id),
        json.dumps(result, default=datetime.isoformat),
        ex=600,
    )


async def get_camera_test(camera_id: str) -> dict[str, Any] | None:
    raw = await redis_client.get(CAMERA_TEST_KEY.format(camera_id=camera_id))
    if not raw:
        return None
    return json.loads(raw)


async def increment_alert_counter() -> int:
    """Increment the global alert counter (for uptime-style metrics)."""
    value = await redis_client.incr(ALERT_COUNTER_KEY)
    return int(value)


async def ping() -> float | None:
    """Return Redis round-trip latency in ms or None when unreachable."""
    try:
        start = time.perf_counter()
        await redis_client.ping()
        elapsed_ms = (time.perf_counter() - start) * 1000
        return round(elapsed_ms, 2)
    except Exception:
        return None


async def get_test_timeout() -> float:
    return settings.CAMERA_TEST_TIMEOUT_SECONDS