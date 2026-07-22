"""Global Intelligence Room endpoints — the live, fused situational feed."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from app.ingestion import get_intelligence_service

router = APIRouter(prefix="/intelligence", tags=["intelligence"])


def _event_payload(event) -> dict:
    row = event.model_dump(mode="json")
    freshness = max(0, int((datetime.now(timezone.utc) - event.published_at).total_seconds()))
    return {**row, "schema_version": "1.0", "provenance": event.source_kind.value,
            "freshness_seconds": freshness, "stale": freshness > 3600}


@router.get("/feed")
async def get_feed() -> dict:
    """Everything, fused: risk-ranked events + prices + weather + vessels + sanctions."""
    feed = await get_intelligence_service().feed()
    return {
        "summary": feed.summary(),
        "schema_version": "1.0",
        "events": [_event_payload(e) for e in feed.events],
        "prices": [p.model_dump(mode="json") for p in feed.prices],
        "weather": [w.model_dump(mode="json") for w in feed.weather],
        "vessels": [v.model_dump(mode="json") for v in feed.vessels],
        "sanctions": [s.model_dump(mode="json") for s in feed.sanctions],
    }


@router.get("/events")
async def get_events() -> dict:
    feed = await get_intelligence_service().feed()
    return {
        "summary": feed.summary(),
        "schema_version": "1.0",
        "events": [_event_payload(e) for e in feed.events],
    }


@router.get("/summary")
async def get_summary() -> dict:
    feed = await get_intelligence_service().feed()
    return feed.summary()
