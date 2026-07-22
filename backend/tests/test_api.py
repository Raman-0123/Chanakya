import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import app
from app.api.routes.realtime import router as realtime_router
from app.core.config import settings
from app.db import get_repositories


@pytest.mark.asyncio
async def test_public_contracts_without_lifespan() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.get("/api/livez")).status_code == 200
        events = await client.get("/api/events")
        assert events.status_code == 200
        assert events.json()["schema_version"] == "1.0"
        sources = await client.get("/api/sources/status")
        assert sources.status_code == 200


@pytest.mark.asyncio
async def test_operator_action_is_protected() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/missions/missing/activate")
        assert response.status_code in {403, 503}


@pytest.mark.asyncio
async def test_operator_can_activate_persistent_mission(monkeypatch) -> None:
    monkeypatch.setattr(settings, "operator_pin", "correct-pin")
    mission = await get_repositories().create_mission("hormuz_closure", "reserve_led",
                                                      None, {})
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        latest = await client.get("/api/missions/latest?scenario_id=hormuz_closure")
        assert latest.status_code == 200
        assert latest.json()["id"] == mission["id"]
        denied = await client.post(f"/api/missions/{mission['id']}/activate",
                                   headers={"X-Operator-Pin": "wrong"})
        assert denied.status_code == 403
        accepted = await client.post(f"/api/missions/{mission['id']}/activate",
                                     headers={"X-Operator-Pin": "correct-pin"})
        assert accepted.status_code == 200
        assert accepted.json()["status"] == "active"


def test_websocket_heartbeat_contract() -> None:
    ws_app = FastAPI()
    ws_app.include_router(realtime_router, prefix="/api")
    with TestClient(ws_app).websocket_connect("/api/ws/intelligence") as websocket:
        assert websocket.receive_json()["type"] == "connection.ready"
        websocket.send_json({"type": "ping", "cursor": "1-0"})
        response = websocket.receive_json()
        assert response == {"type": "pong", "cursor": "1-0"}
