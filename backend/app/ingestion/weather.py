"""Open-Meteo adapter — keyless weather at chokepoints & Indian ports.

Wind + wave observations become a shipping-risk band, feeding weather-driven
disruption signals (e.g. cyclone risk over western terminals).
"""

from __future__ import annotations

import asyncio

import httpx

from app.core.logging import get_logger
from app.ingestion.cache import cache_get, cache_set
from app.ingestion.models import SourceKind, WeatherObs

log = get_logger("ingestion.weather")

_FORECAST = "https://api.open-meteo.com/v1/forecast"
_MARINE = "https://marine-api.open-meteo.com/v1/marine"
_TTL = 1800

# id, name, lat, lon
_LOCATIONS = [
    ("hormuz", "Strait of Hormuz", 26.57, 56.25),
    ("bab_el_mandeb", "Bab-el-Mandeb", 12.6, 43.3),
    ("vadinar", "Vadinar / Sikka", 22.28, 69.72),
    ("mumbai", "Mumbai Coast", 18.95, 72.85),
    ("mangalore", "Mangalore", 12.92, 74.80),
    ("paradip", "Paradip", 20.27, 86.67),
    ("vizag", "Visakhapatnam", 17.69, 83.22),
]


def _risk(wind_kph: float, wave_m: float | None) -> str:
    w = wave_m or 0
    if wind_kph >= 62 or w >= 3.5:
        return "critical"
    if wind_kph >= 45 or w >= 2.5:
        return "high"
    if wind_kph >= 30 or w >= 1.6:
        return "elevated"
    return "nominal"


async def _one(client: httpx.AsyncClient, loc: tuple) -> WeatherObs:
    lid, name, lat, lon = loc
    wind, wave, code = 14.0, None, 0
    r = await client.get(_FORECAST, params={
        "latitude": lat, "longitude": lon,
        "current": "wind_speed_10m,weather_code",
        "wind_speed_unit": "kmh",
    })
    r.raise_for_status()
    cur = r.json().get("current", {})
    if "wind_speed_10m" not in cur:
        raise ValueError(f"missing wind observation for {lid}")
    wind = float(cur["wind_speed_10m"])
    code = int(cur.get("weather_code", 0))
    try:
        r = await client.get(_MARINE, params={
            "latitude": lat, "longitude": lon, "current": "wave_height",
        })
        r.raise_for_status()
        wave = float(r.json().get("current", {}).get("wave_height", 0)) or None
    except Exception:  # noqa: BLE001
        wave = None

    return WeatherObs(
        location_id=lid, location_name=name, lat=lat, lon=lon,
        wind_kph=round(wind, 1), wave_m=wave,
        condition="storm" if code >= 80 else "rough" if wind >= 45 else "clear",
        shipping_risk=_risk(wind, wave),
        source_kind=SourceKind.LIVE,
    )


async def fetch_weather() -> list[WeatherObs]:
    cached = await cache_get("weather:obs")
    if cached:
        return [WeatherObs(**{**w, "source_kind": SourceKind.CACHED}) for w in cached]
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            obs = await asyncio.gather(*[_one(client, loc) for loc in _LOCATIONS])
    except Exception as exc:  # noqa: BLE001
        log.warning("weather.fetch_failed", error=str(exc))
        return _fallback()
    await cache_set("weather:obs", [o.model_dump(mode="json") for o in obs], _TTL)
    return list(obs)


def _fallback() -> list[WeatherObs]:
    return [
        WeatherObs(location_id=lid, location_name=name, lat=lat, lon=lon,
                   wind_kph=16.0, wave_m=1.1, condition="clear",
                   shipping_risk="nominal", source_kind=SourceKind.FALLBACK)
        for (lid, name, lat, lon) in _LOCATIONS
    ]
