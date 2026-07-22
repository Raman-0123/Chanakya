"""Live operational snapshot and auto-detected incident endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from app.operations import get_operational_service

router = APIRouter(prefix="/operations", tags=["operations"])


@router.get("/snapshot")
async def operational_snapshot() -> dict:
    snapshot = await get_operational_service().current()
    return snapshot.model_dump(mode="json")


@router.get("/scenario")
async def detected_scenario() -> dict:
    snapshot = await get_operational_service().current()
    return {
        "snapshot_id": snapshot.id,
        "scenario": snapshot.active_scenario.model_dump(mode="json"),
        "is_live": snapshot.is_live,
        "data_quality_score": snapshot.data_quality_score,
        "provenance": snapshot.provenance,
    }
