"""Lifespan-managed datastore connections.

Every connection is optional and lazy: if a store is unavailable the platform
keeps running with that capability marked unhealthy, rather than failing to
boot. This mirrors CHANAKYA's graceful-degradation principle end to end.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("db.manager")


@dataclass
class DataStores:
    redis: object | None = None
    pg_engine: object | None = None
    neo4j_driver: object | None = None
    qdrant: object | None = None
    _status: dict[str, bool] = field(default_factory=dict)

    # ---- connect ----
    async def connect(self) -> None:
        await self._connect_redis()
        await self._connect_postgres()
        await self._connect_neo4j()
        self._connect_qdrant()
        log.info("db.connected", status=self.health())

    async def _connect_redis(self) -> None:
        try:
            import redis.asyncio as aioredis

            self.redis = aioredis.from_url(settings.redis_url, decode_responses=True)
            await self.redis.ping()
            self._status["redis"] = True
        except Exception as exc:  # noqa: BLE001
            log.warning("db.redis_unavailable", error=str(exc))
            self.redis = None
            self._status["redis"] = False

    async def _connect_postgres(self) -> None:
        try:
            from sqlalchemy.ext.asyncio import create_async_engine
            from sqlalchemy import text

            self.pg_engine = create_async_engine(
                settings.database_url, pool_pre_ping=True, pool_size=5
            )
            async with self.pg_engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            self._status["postgres"] = True
        except Exception as exc:  # noqa: BLE001
            log.warning("db.postgres_unavailable", error=str(exc))
            self.pg_engine = None
            self._status["postgres"] = False

    async def _connect_neo4j(self) -> None:
        try:
            from neo4j import AsyncGraphDatabase

            self.neo4j_driver = AsyncGraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_user, settings.neo4j_password),
            )
            await self.neo4j_driver.verify_connectivity()
            self._status["neo4j"] = True
        except Exception as exc:  # noqa: BLE001
            log.warning("db.neo4j_unavailable", error=str(exc))
            self.neo4j_driver = None
            self._status["neo4j"] = False

    def _connect_qdrant(self) -> None:
        try:
            from qdrant_client import QdrantClient

            self.qdrant = QdrantClient(
                url=settings.qdrant_url,
                api_key=settings.qdrant_api_key or None,
                timeout=5,
            )
            self.qdrant.get_collections()
            self._status["qdrant"] = True
        except Exception as exc:  # noqa: BLE001
            log.warning("db.qdrant_unavailable", error=str(exc))
            self.qdrant = None
            self._status["qdrant"] = False

    # ---- teardown ----
    async def disconnect(self) -> None:
        if self.redis is not None:
            await self.redis.aclose()
        if self.pg_engine is not None:
            await self.pg_engine.dispose()
        if self.neo4j_driver is not None:
            await self.neo4j_driver.close()
        if self.qdrant is not None:
            self.qdrant.close()
        log.info("db.disconnected")

    def health(self) -> dict[str, bool]:
        return dict(self._status)


_datastores = DataStores()


def get_datastores() -> DataStores:
    return _datastores
