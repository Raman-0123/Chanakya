"""Live adapter state and protected manual refresh."""

from __future__ import annotations

import hmac

from fastapi import APIRouter, Header, HTTPException

from app.core.config import settings
from app.ingestion.pipeline import pipeline
from app.ingestion.status import source_status

router = APIRouter(prefix="/sources", tags=["sources"])


def require_operator_pin(x_operator_pin: str | None = Header(default=None)) -> None:
    if not settings.operator_pin:
        raise HTTPException(503, "Operator actions are disabled until OPERATOR_PIN is configured")
    if not x_operator_pin or not hmac.compare_digest(x_operator_pin, settings.operator_pin):
        raise HTTPException(403, "Invalid operator PIN")


@router.get("/status")
async def source_health() -> dict:
    return {"schema_version": "1.0", "sources": source_status.all()}


@router.post("/refresh")
async def refresh_sources(x_operator_pin: str | None = Header(default=None)) -> dict:
    require_operator_pin(x_operator_pin)
    events = await pipeline.run_once()
    return {"accepted": len(events), "sources": source_status.all()}
