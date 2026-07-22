"""System status endpoints — the platform's self-awareness surface."""

from __future__ import annotations

from fastapi import APIRouter

from app import __version__
from app.core.config import settings
from app.db import get_datastores
from app.llm.router import get_llm_router
from app.events import websocket_hub

router = APIRouter(tags=["system"])


@router.get("/livez")
async def livez() -> dict:
    return {"status": "alive"}


@router.get("/readyz")
async def readyz() -> dict:
    stores = get_datastores().health()
    router_ = get_llm_router()
    weak_pin = settings.operator_pin_is_weak
    security = {
        "operator_pin_configured": bool(settings.operator_pin.strip()),
        "operator_pin_weak": weak_pin,
    }
    llm = {"available": router_.available, "providers": router_.provider_names}
    stores_ok = all(stores.get(k, False) for k in ("postgres", "redis", "neo4j", "qdrant"))
    # In production, readiness requires connected stores AND a strong operator PIN
    # (mission activation is gated on that PIN). LLM stays optional — the council
    # degrades to deterministic grounded reasoning without a provider.
    ready = True if not settings.is_production else (stores_ok and not weak_pin)
    warnings: list[str] = []
    if settings.is_production and weak_pin:
        warnings.append("OPERATOR_PIN is unset or weak; set a strong secret before hosting.")
    if settings.is_production and not stores_ok:
        warnings.append("One or more datastores are not connected.")
    return {"status": "ready" if ready else "degraded", "ready": ready,
            "datastores": stores, "security": security, "llm": llm,
            "warnings": warnings}


@router.get("/health")
async def health() -> dict:
    """Liveness + capability snapshot: what is wired and what is degraded."""
    stores = get_datastores()
    router_ = get_llm_router()
    return {
        "status": "ok",
        "version": __version__,
        "environment": settings.environment,
        "datastores": stores.health(),
        "llm": {
            "available": router_.available,
            "providers": router_.provider_names,
        },
        "process_role": settings.process_role,
        "websocket_clients": websocket_hub.count,
        "data_sources": {
            "gdelt": settings.gdelt_enabled,
            "open_meteo": settings.open_meteo_enabled,
            "openweather": bool(settings.openweather_api_key),
            "eia": bool(settings.eia_api_key),
            "alpha_vantage": bool(settings.alpha_vantage_api_key),
            "aisstream": bool(settings.aisstream_api_key),
            "newsapi": bool(settings.newsapi_key),
            "sanctions": settings.sanctions_enabled,
        },
    }
