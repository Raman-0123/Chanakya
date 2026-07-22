from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.api.routes.sources import require_operator_pin
from app.db import get_repositories

router = APIRouter(prefix="/missions", tags=["missions"])


class TaskUpdateRequest(BaseModel):
    status: str
    note: str | None = None


class ActivateMissionRequest(BaseModel):
    strategy_id: str | None = None


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
                           req: ActivateMissionRequest | None = None,
                           x_operator_pin: str | None = Header(default=None)) -> dict:
    require_operator_pin(x_operator_pin)
    row = await get_repositories().activate_mission(
        mission_id, req.strategy_id if req else None,
    )
    if not row:
        raise HTTPException(404, "Mission or selected workflow strategy not found")
    return row


@router.post("/{mission_id}/tasks/{task_id}")
async def update_mission_task(
    mission_id: str, task_id: str, req: TaskUpdateRequest,
    x_operator_pin: str | None = Header(default=None),
) -> dict:
    require_operator_pin(x_operator_pin)
    allowed = {"queued", "acknowledged", "in_progress", "blocked", "completed"}
    if req.status not in allowed:
        raise HTTPException(422, f"status must be one of {sorted(allowed)}")
    row = await get_repositories().update_mission_task(
        mission_id, task_id, req.status, req.note,
    )
    if not row:
        raise HTTPException(404, "Mission or task not found")
    return row
