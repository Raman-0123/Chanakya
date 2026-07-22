"""Normalized event-store endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.db import get_repositories

router = APIRouter(prefix="/events", tags=["events"])


@router.get("")
async def list_events(limit: int = Query(100, ge=1, le=500), category: str | None = None) -> dict:
    rows = await get_repositories().list_events(limit=limit, category=category)
    return {"schema_version": "1.0", "events": rows, "count": len(rows)}


@router.get("/{event_id}")
async def get_event(event_id: str) -> dict:
    row = await get_repositories().get_event(event_id)
    if not row:
        raise HTTPException(404, "Event not found")
    return row
