from __future__ import annotations

import json
import time
from typing import Any

from redis.asyncio import Redis

from app.core.config import settings


_redis_client: Redis | None = None
_memory_store: dict[str, tuple[str, float | None]] = {}


def get_redis_client() -> Redis:
    """Create a shared Redis client."""
    global _redis_client
    if _redis_client is None:
        _redis_client = Redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            max_connections=settings.redis_max_connections,
        )
    return _redis_client


async def cache_set(key: str, value: Any, ttl_seconds: int | None = None) -> None:
    """Store JSON-serializable data in Redis, with in-memory fallback."""
    payload = json.dumps(value)
    try:
        client = get_redis_client()
        await client.set(key, payload, ex=ttl_seconds)
        return
    except Exception:
        expires_at = time.time() + ttl_seconds if ttl_seconds else None
        _memory_store[key] = (payload, expires_at)


async def cache_get(key: str) -> Any | None:
    """Read JSON-serializable data from Redis, with in-memory fallback."""
    try:
        client = get_redis_client()
        value = await client.get(key)
        return json.loads(value) if value is not None else None
    except Exception:
        payload = _memory_store.get(key)
        if payload is None:
            return None
        value, expires_at = payload
        if expires_at is not None and time.time() > expires_at:
            _memory_store.pop(key, None)
            return None
        return json.loads(value)


async def cache_delete(key: str) -> None:
    """Delete data from Redis, with in-memory fallback."""
    try:
        client = get_redis_client()
        await client.delete(key)
    except Exception:
        _memory_store.pop(key, None)
