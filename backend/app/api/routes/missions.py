from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

from app.api.routes.sources import require_operator_pin
from app.db import get_repositories

router = APIRouter(prefix="/missions", tags=["missions"])


@router.get("/latest")
async def get_latest_mission(scenario_id: str | None = None) -> dict:
    row = await get_repositories().get_latest_mission(scenario_id)
    if not row:
        raise HTTPException(404, "Mission not found")
    return row


@router.get("/{mission_id}")
async def get_mission(mission_id: str) -> dict:
    row = await get_repositories().get_mission(mission_id)
    if not row:
        raise HTTPException(404, "Mission not found")
    return row


@router.post("/{mission_id}/activate")
async def activate_mission(mission_id: str,
                           x_operator_pin: str | None = Header(default=None)) -> dict:
    require_operator_pin(x_operator_pin)
    row = await get_repositories().activate_mission(mission_id)
    if not row:
        raise HTTPException(404, "Mission not found")
    return row
