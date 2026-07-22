"""Bounded Redis Stream event bus plus in-process WebSocket fan-out."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import WebSocket

from app.core.config import settings
from app.core.logging import get_logger
from app.db import get_datastores
from app.db import get_repositories
from app.ingestion.models import DomainEvent

log = get_logger("events.bus")


class WebSocketHub:
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    @property
    def count(self) -> int:
        return len(self._clients)

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._clients.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(websocket)

    async def broadcast(self, message: dict[str, Any]) -> None:
        stale: list[WebSocket] = []
        for client in tuple(self._clients):
            try:
                await client.send_json(message)
            except Exception:  # noqa: BLE001
                stale.append(client)
        if stale:
            async with self._lock:
                for client in stale:
                    self._clients.discard(client)


class EventBus:
    async def publish(self, events: list[DomainEvent]) -> None:
        redis = get_datastores().redis
        for event in events:
            payload = event.model_dump_json()
            stream_id = event.id
            if redis is not None:
                try:
                    stream_id = await redis.xadd(
                        settings.event_stream_name,
                        {"event": payload, "attempt": "0"},
                        maxlen=settings.event_stream_maxlen,
                        approximate=True,
                    )
                except Exception as exc:  # noqa: BLE001
                    log.warning("events.redis_publish_failed", error=str(exc))
            await websocket_hub.broadcast({
                "type": "intelligence.event",
                "cursor": stream_id,
                "schema_version": event.schema_version,
                "data": json.loads(payload),
            })

    async def publish_status(self, source: str, status: dict) -> None:
        await websocket_hub.broadcast({
            "type": "source.status", "source": source, "data": status,
        })

    async def publish_operational(self, snapshot) -> None:
        await websocket_hub.broadcast({
            "type": "operations.snapshot",
            "cursor": snapshot.id,
            "schema_version": "1.0",
            "data": {
                "id": snapshot.id,
                "generated_at": snapshot.generated_at.isoformat(),
                "scenario": snapshot.active_scenario.model_dump(mode="json"),
                "is_live": snapshot.is_live,
                "data_quality_score": snapshot.data_quality_score,
            },
        })

    async def publish_recommendation(self, result, snapshot_id: str) -> None:
        await websocket_hub.broadcast({
            "type": "operations.recommendation",
            "cursor": result.workflow_run_id,
            "schema_version": result.schema_version,
            "data": {
                "snapshot_id": snapshot_id,
                "workflow_run_id": result.workflow_run_id,
                "mission_id": result.mission_id,
                "recommended_strategy_id": result.recommended_strategy_id,
                "consensus_confidence": result.consensus_confidence,
            },
        })


websocket_hub = WebSocketHub()
event_bus = EventBus()


class StreamConsumer:
    """At-least-once ontology consumer with bounded retries and DLQ."""

    group = "chanakya-workers"
    consumer = "ontology-writer"

    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    async def _ensure_group(self, redis) -> None:
        try:
            await redis.xgroup_create(settings.event_stream_name, self.group,
                                      id="0", mkstream=True)
        except Exception as exc:  # BUSYGROUP is expected after first boot
            if "BUSYGROUP" not in str(exc):
                raise

    async def _loop(self) -> None:
        while not self._stop.is_set():
            redis = get_datastores().redis
            if redis is None:
                await asyncio.sleep(2)
                continue
            try:
                await self._ensure_group(redis)
                messages = await redis.xreadgroup(
                    self.group, self.consumer, {settings.event_stream_name: ">"},
                    count=20, block=5000,
                )
                for _stream, entries in messages or []:
                    for message_id, fields in entries:
                        try:
                            event = DomainEvent.model_validate_json(fields["event"])
                            await get_repositories().upsert_event_nodes([event])
                            await redis.xack(settings.event_stream_name, self.group, message_id)
                        except Exception as exc:  # noqa: BLE001
                            attempt = int(fields.get("attempt", 0)) + 1
                            target = (settings.event_dead_letter_stream if attempt >= 3
                                      else settings.event_stream_name)
                            await redis.xadd(target, {**fields, "attempt": str(attempt),
                                                      "error": str(exc)[:300]},
                                             maxlen=settings.event_stream_maxlen,
                                             approximate=True)
                            await redis.xack(settings.event_stream_name, self.group, message_id)
            except Exception as exc:  # noqa: BLE001
                log.warning("events.consumer_failed", error=str(exc))
                await asyncio.sleep(2)

    def start(self) -> None:
        if not self._task:
            self._task = asyncio.create_task(self._loop(), name="chanakya-stream-consumer")

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            await self._task
            self._task = None


stream_consumer = StreamConsumer()
