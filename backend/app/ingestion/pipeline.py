"""Scheduled normalization -> persistence -> Redis Streams pipeline."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from app.core.config import settings
from app.core.logging import get_logger
from app.db import get_datastores, get_repositories
from app.events import event_bus
from app.ingestion.models import DomainEvent, Evidence, SignalCategory, SourceKind
from app.ingestion.service import get_intelligence_service
from app.ingestion.status import source_status
from app.ingestion.supplemental import fetch_firms_events, get_ppac_snapshot

log = get_logger("ingestion.pipeline")


class IngestionPipeline:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    async def run_once(self) -> list[DomainEvent]:
        feed = await get_intelligence_service().feed()
        supplemental = await fetch_firms_events()
        intel = feed.events + supplemental
        events = [DomainEvent.from_intel(event) for event in intel]
        now = datetime.now(timezone.utc)
        for quote in feed.prices:
            events.append(DomainEvent(
                id=f"price-{quote.symbol.lower()}-{quote.as_of:%Y%m%d%H}",
                event_type="commodity_price", category=SignalCategory.MARKET,
                title=f"{quote.symbol} ${quote.price_usd:.2f}/bbl",
                summary=f"{quote.change_pct:+.2f}% from prior observation.",
                source=quote.source, provenance=quote.source_kind,
                observed_at=quote.as_of, ingested_at=now,
                freshness_seconds=max(0, int((now - quote.as_of).total_seconds())),
                stale=(now - quote.as_of).total_seconds() > 86400,
                severity="elevated" if abs(quote.change_pct) >= 3 else "nominal",
                confidence=90 if quote.source_kind == SourceKind.LIVE else 55,
                risk_score=min(100, 20 + abs(quote.change_pct) * 8),
                evidence=[Evidence(label="Price observation", detail=quote.source)],
                attributes={"symbol": quote.symbol, "price_usd": quote.price_usd,
                            "change_pct": quote.change_pct},
            ))

        accepted = await get_repositories().save_events(events)
        await get_repositories().upsert_vessels(feed.vessels)
        await event_bus.publish(accepted)
        await self._update_statuses(feed, supplemental)
        log.info("ingestion.completed", observed=len(events), accepted=len(accepted))
        return accepted

    async def _update_statuses(self, feed, supplemental) -> None:
        groups = {
            "gdelt": ([event for event in feed.events
                       if event.category == SignalCategory.GEOPOLITICAL], settings.gdelt_enabled),
            "open_meteo": (feed.weather, settings.open_meteo_enabled),
            "prices": (feed.prices, bool(settings.eia_api_key or settings.alpha_vantage_api_key)),
            "ais": (feed.vessels, bool(settings.aisstream_api_key)),
            "opensanctions": (feed.sanctions, bool(settings.opensanctions_api_key)),
            "nasa_firms": (supplemental, bool(settings.nasa_firms_map_key)),
            "ppac": ([get_ppac_snapshot()], settings.ppac_enabled),
        }
        for name, (rows, configured) in groups.items():
            kinds = [getattr(row, "source_kind",
                             getattr(row, "provenance", SourceKind.UNAVAILABLE)) for row in rows]
            provenance = (SourceKind.LIVE if SourceKind.LIVE in kinds else
                          SourceKind.CACHED if SourceKind.CACHED in kinds else
                          SourceKind.REPLAY if SourceKind.REPLAY in kinds else
                          SourceKind.SIMULATED if rows else SourceKind.UNAVAILABLE)
            status = source_status.update(name, ok=bool(rows), provenance=provenance,
                                          event_count=len(rows),
                                          error=None if rows else "No observations",
                                          configured=configured)
            await event_bus.publish_status(name, status)

    async def _loop(self) -> None:
        while not self._stop.is_set():
            redis = get_datastores().redis
            owns_lease = True
            if redis is not None:
                try:
                    owns_lease = bool(await redis.set(
                        "chanakya:ingestion:lease", "1", nx=True,
                        ex=max(60, settings.event_poll_seconds - 5),
                    ))
                except Exception:  # noqa: BLE001
                    owns_lease = True
            if owns_lease:
                try:
                    await self.run_once()
                except Exception as exc:  # noqa: BLE001
                    log.warning("ingestion.cycle_failed", error=str(exc))
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=settings.event_poll_seconds)
            except asyncio.TimeoutError:
                pass

    def start(self) -> None:
        if not self._task:
            self._task = asyncio.create_task(self._loop(), name="chanakya-ingestion")

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            await self._task
            self._task = None


pipeline = IngestionPipeline()
