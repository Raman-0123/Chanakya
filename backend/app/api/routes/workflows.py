from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.db import get_repositories

router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.get("/{run_id}")
async def get_workflow(run_id: str) -> dict:
    row = await get_repositories().get_workflow(run_id)
    if not row:
        raise HTTPException(404, "Workflow not found")
    return row
