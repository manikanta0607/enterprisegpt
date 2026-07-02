"""Async Redis client for caching, rate limiting, and short-term session state.

A single connection pool is shared across the application lifetime. Phase 5
(Caching & Rate Limiting) will build higher-level services on top of this
client; Phase 1 only establishes the connection and a health check.
"""

from redis import asyncio as aioredis

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_redis_client: aioredis.Redis | None = None


def get_redis_client() -> aioredis.Redis:
    """Return the singleton async Redis client, creating it if needed.

    Returns:
        A configured `redis.asyncio.Redis` instance backed by a connection pool.
    """
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            max_connections=20,
        )
        logger.info("Redis client created for host=%s", settings.redis_host)
    return _redis_client


async def check_redis_connection() -> bool:
    """Verify Redis connectivity for health checks.

    Returns:
        True if a PING succeeds, False otherwise.
    """
    try:
        client = get_redis_client()
        return bool(await client.ping())
    except Exception:
        logger.exception("Redis health check failed")
        return False
