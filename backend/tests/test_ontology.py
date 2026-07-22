from datetime import datetime, timezone

import httpx
import pytest

from app.db import get_repositories
from app.ingestion.models import DomainEvent, SignalCategory, SourceKind
from app.main import app


@pytest.mark.asyncio
async def test_ontology_schema_and_canonical_alias_expansion() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        schema = await client.get("/api/ontology/schema")
        assert schema.status_code == 200
        relation_types = {row["type"] for row in schema.json()["relationship_types"]}
        assert {"TRANSITS", "ARRIVES_AT", "FEEDS", "DISTRIBUTES_TO", "AFFECTS"} <= relation_types

        explored = await client.get("/api/ontology/explore/ref:koyali_ref?depth=1")
        assert explored.status_code == 200
        body = explored.json()
        assert body["center"] == "refinery:koyali_ref"
        assert any(node["id"] == "refinery:koyali_ref" for node in body["nodes"])
        assert all(edge["label"] != "SUPPLIES" for edge in body["edges"])


@pytest.mark.asyncio
async def test_impact_returns_real_branches_not_one_flattened_chain() -> None:
    event = DomainEvent(
        id="ontology-test-event",
        event_type="geopolitical",
        category=SignalCategory.GEOPOLITICAL,
        title="Observed disruption near Hormuz",
        summary="Test observation with an explicit corridor mapping.",
        source="test-fixture",
        provenance=SourceKind.LIVE,
        observed_at=datetime.now(timezone.utc),
        affected_corridors=["hormuz"],
        risk_score=82,
    )
    await get_repositories().save_events([event])

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/ontology/impact/ontology-test-event")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert len(body["paths"]) > 1
        assert all(path[0]["id"] == "event:ontology-test-event" for path in body["paths"])
        assert all(path[1]["id"] == "corridor:hormuz" for path in body["paths"])
        assert all(not any(step["type"] == "supplier" for step in path) for path in body["paths"])
        assert body["exposures"]


@pytest.mark.asyncio
async def test_shortest_path_crosses_physical_supply_layers() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/ontology/path?source=sup:iraq&target=demand:north&max_depth=6"
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        node_types = [step["type"] for step in body["path"]]
        assert node_types[0] == "supplier"
        assert "corridor" in node_types
        assert "port" in node_types
        assert "refinery" in node_types
        assert node_types[-1] == "demand"
