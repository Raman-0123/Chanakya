"""Agent Council + Decision Center endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agents import get_council
from app.domain.scenarios import ResponseLevers

router = APIRouter(prefix="/council", tags=["council"])


class ConveneRequest(BaseModel):
    scenario_id: str
    levers: ResponseLevers | None = None


@router.post("/convene")
async def convene(req: ConveneRequest) -> dict:
    """Run the six-agent council + Decision Engine for a scenario."""
    try:
        result = await get_council().convene(req.scenario_id, req.levers)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    return result.model_dump(mode="json")
