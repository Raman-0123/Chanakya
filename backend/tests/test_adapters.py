import pytest

from app.core.config import settings
from app.ingestion.gdelt import fetch_gdelt_events
from app.ingestion.models import SourceKind
from app.ingestion.prices import fetch_prices
from app.ingestion.supplemental import fetch_firms_events, get_ppac_snapshot
from app.ingestion.weather import fetch_weather
from app.ingestion.vessels import _ship_kind, assign_corridor
from app.ingestion.sanctions import _COUNTRY_NAMES


class FailingClient:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, *args, **kwargs):
        raise TimeoutError("fixture timeout")


@pytest.mark.asyncio
async def test_gdelt_timeout_is_simulated_not_live(monkeypatch) -> None:
    monkeypatch.setattr("app.ingestion.gdelt.httpx.AsyncClient", FailingClient)
    events = await fetch_gdelt_events()
    assert events
    assert all(event.source_kind == SourceKind.SIMULATED for event in events)


@pytest.mark.asyncio
async def test_weather_timeout_is_simulated_not_live(monkeypatch) -> None:
    monkeypatch.setattr("app.ingestion.weather.httpx.AsyncClient", FailingClient)
    observations = await fetch_weather()
    assert observations
    assert all(item.source_kind == SourceKind.SIMULATED for item in observations)


@pytest.mark.asyncio
async def test_unconfigured_sources_are_honest(monkeypatch) -> None:
    monkeypatch.setattr(settings, "eia_api_key", "")
    monkeypatch.setattr(settings, "alpha_vantage_api_key", "")
    monkeypatch.setattr(settings, "nasa_firms_map_key", "")
    prices = await fetch_prices()
    assert all(item.source_kind == SourceKind.SIMULATED for item in prices)
    assert await fetch_firms_events() == []
    assert get_ppac_snapshot().provenance == SourceKind.CACHED


def test_ais_type_and_route_geofencing_are_not_assumed() -> None:
    assert _ship_kind(None) == "unknown"
    assert _ship_kind(84) == "tanker"
    assert _ship_kind(72) == "cargo"
    assert assign_corridor(26.57, 56.25) == "hormuz"
    assert assign_corridor(45.0, -30.0) is None
    assert _COUNTRY_NAMES["RU"] == "Russia"
