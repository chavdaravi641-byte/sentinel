"""Redis async client and caching helpers."""

from redis import asyncio as aioredis

from src.core.config import settings

# Shared asynchronous redis client bound to the configured URL.
redis_client = aioredis.from_url(
    settings.REDIS_URL,
    encoding="utf-8",
    decode_responses=True,
    socket_connect_timeout=2,
    socket_timeout=2,
    health_check_interval=30,
)


async def close_redis() -> None:
    await redis_client.aclose()