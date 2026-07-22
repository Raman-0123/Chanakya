from uuid import uuid4

import pytest
import redis.asyncio as aioredis

from app.core.config import settings


@pytest.mark.asyncio
async def test_redis_stream_consumer_contract_when_available() -> None:
    client = aioredis.from_url(settings.redis_url, decode_responses=True)
    key = f"chanakya:test:{uuid4().hex}"
    connected = False
    try:
        try:
            await client.ping()
            connected = True
        except Exception as exc:  # noqa: BLE001
            pytest.skip(f"Redis integration unavailable: {exc}")
        entry_id = await client.xadd(key, {"event": "fixture", "attempt": "0"}, maxlen=10)
        await client.xgroup_create(key, "test-group", id="0")
        rows = await client.xreadgroup("test-group", "test-consumer", {key: ">"}, count=1)
        assert rows[0][1][0][0] == entry_id
        assert await client.xack(key, "test-group", entry_id) == 1
    finally:
        # GitHub Actions does not provision Redis for the unit-test job. In
        # that environment the test intentionally skips; do not turn the skip
        # into a failure by attempting cleanup through the same unavailable
        # connection.
        if connected:
            await client.delete(key)
        await client.aclose()
