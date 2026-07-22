"""NASA FIRMS adapter — satellite thermal anomalies near energy assets.

VIIRS thermal detections (fires, refinery flares, burning vessels) are a real
geospatial-intelligence layer. FIRMS requires a free MAP_KEY; without one this
adapter returns nothing and reports the source as UNAVAILABLE — it never
fabricates satellite observations, keeping provenance honest.

With a key set (NASA_FIRMS_MAP_KEY), it pulls recent detections over a bounding
box spanning the Gulf, Red Sea and India's coasts, tags each to its nearest
monitored asset, and labels them LIVE.
"""

from __future__ import annotations

import csv
import io

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.domain import build_energy_network
from app.ingestion.cache import cache_get, cache_set
from app.ingestion.models import SatelliteDetection, SourceKind
from app.ingestion.status import source_status

log = get_logger("ingestion.firms")

# west, south, east, north — Gulf + Red Sea + Arabian Sea + India coasts
_AREA = "32,-10,92,32"
_SOURCE = "VIIRS_SNPP_NRT"
_BASE = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
_TTL = 1800
_CONF = {"l": "low", "n": "nominal", "h": "high"}

_net = build_energy_network()


def _assets() -> list[tuple[str, float, float]]:
    points: list[tuple[str, float, float]] = []
    for corr in _net.corridors:
        if corr.chokepoint_coords:
            points.append((corr.chokepoint, corr.chokepoint_coords.lat,
                           corr.chokepoint_coords.lon))
    for port in _net.ports:
        points.append((port.name, port.coords.lat, port.coords.lon))
    return points


def _nearest_asset(lat: float, lon: float) -> str | None:
    best, best_d = None, 6.0  # ~6° cutoff so distant fires stay unlabelled
    for label, alat, alon in _assets():
        d = ((lat - alat) ** 2 + (lon - alon) ** 2) ** 0.5
        if d < best_d:
            best, best_d = label, d
    return best


def _parse(rows: str) -> list[SatelliteDetection]:
    detections: list[SatelliteDetection] = []
    reader = csv.DictReader(io.StringIO(rows))
    for i, row in enumerate(reader):
        try:
            lat, lon = float(row["latitude"]), float(row["longitude"])
        except (KeyError, ValueError):
            continue
        bright = float(row.get("bright_ti4") or row.get("brightness") or 0)
        conf = _CONF.get(str(row.get("confidence", "n")).lower()[:1], "nominal")
        detections.append(SatelliteDetection(
            id=f"firms-{i}-{row.get('acq_date','')}-{row.get('acq_time','')}",
            lat=lat, lon=lon, brightness_k=round(bright, 1), confidence=conf,
            acquired_at=f"{row.get('acq_date','')}T{str(row.get('acq_time','')).zfill(4)}Z",
            satellite=row.get("satellite", "VIIRS"),
            near_asset=_nearest_asset(lat, lon),
            source_kind=SourceKind.LIVE,
        ))
    return detections


async def fetch_firms() -> list[SatelliteDetection]:
    key = settings.nasa_firms_map_key
    if not key:
        source_status.update("nasa_firms", ok=False, provenance=SourceKind.UNAVAILABLE,
                             configured=False, error="NASA_FIRMS_MAP_KEY not set")
        return []
    cached = await cache_get("firms:detections")
    if cached:
        return [SatelliteDetection(**{**d, "source_kind": SourceKind.CACHED}) for d in cached]
    url = f"{_BASE}/{key}/{_SOURCE}/{_AREA}/1"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(url)
            r.raise_for_status()
            detections = _parse(r.text)
    except Exception as exc:  # noqa: BLE001
        log.warning("firms.fetch_failed", error=str(exc))
        source_status.update("nasa_firms", ok=False, provenance=SourceKind.UNAVAILABLE,
                             configured=True, error=str(exc))
        return []
    await cache_set("firms:detections", [d.model_dump(mode="json") for d in detections], _TTL)
    source_status.update("nasa_firms", ok=True, provenance=SourceKind.LIVE,
                         configured=True, event_count=len(detections))
    return detections
