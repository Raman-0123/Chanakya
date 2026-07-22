"""Async TTL cache used by every adapter to survive free-tier rate limits.

Uses Redis when the datastore is up (shared across workers) and always keeps an
in-process fallback so caching works even with no Redis.
"""

from __future__ import annotations

import json
import time
from typing import Any

from app.core.logging import get_logger
from app.db import get_datastores

log = get_logger("ingestion.cache")

_local: dict[str, tuple[float, Any]] = {}


async def cache_get(key: str) -> Any | None:
    # in-process first (fast path)
    hit = _local.get(key)
    if hit and hit[0] > time.time():
        return hit[1]

    stores = get_datastores()
    if stores.redis is not None:
        try:
            raw = await stores.redis.get(f"intel:{key}")
            if raw:
                return json.loads(raw)
        except Exception as exc:  # noqa: BLE001
            log.debug("cache.redis_get_failed", error=str(exc))
    return None


async def cache_set(key: str, value: Any, ttl: int) -> None:
    _local[key] = (time.time() + ttl, value)
    stores = get_datastores()
    if stores.redis is not None:
        try:
            await stores.redis.set(f"intel:{key}", json.dumps(value), ex=ttl)
        except Exception as exc:  # noqa: BLE001
            log.debug("cache.redis_set_failed", error=str(exc))
