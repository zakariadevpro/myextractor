import json
import logging
from functools import wraps

from app.db.redis import redis_client

logger = logging.getLogger(__name__)


async def cache_get(key: str) -> dict | None:
    """Get cached JSON value from Redis."""
    try:
        raw = await redis_client.get(key)
        if raw:
            return json.loads(raw)
    except Exception as e:
        logger.debug("Cache get failed for %s: %s", key, e)
    return None


async def cache_set(key: str, value: dict, ttl: int = 300) -> None:
    """Set cached JSON value in Redis with TTL in seconds."""
    try:
        await redis_client.set(key, json.dumps(value, default=str), ex=ttl)
    except Exception as e:
        logger.debug("Cache set failed for %s: %s", key, e)


async def cache_invalidate_prefix(prefix: str) -> None:
    """Delete all keys matching a prefix pattern."""
    try:
        keys = []
        async for key in redis_client.scan_iter(match=f"{prefix}*", count=100):
            keys.append(key)
        if keys:
            await redis_client.delete(*keys)
    except Exception as e:
        logger.debug("Cache invalidate failed for %s*: %s", prefix, e)
