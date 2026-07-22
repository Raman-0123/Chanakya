"""EIA, PPAC baseline and NASA FIRMS adapters.

PPAC currently publishes changing spreadsheets rather than a stable public API.
The adapter therefore exposes a versioned, cited snapshot and can be replaced
without altering simulation contracts. It is deliberately marked cached.
"""

from __future__ import annotations

from datetime import datetime, timezone
import csv
import io

import httpx
from pydantic import BaseModel

from app.core.config import settings
from app.core.logging import get_logger
from app.ingestion.models import Evidence, IntelEvent, PriceQuote, SignalCategory, SourceKind
from app.ingestion.tagging import make_id

log = get_logger("ingestion.supplemental")


class PPACSnapshot(BaseModel):
    refinery_demand_kbpd: float = 4900
    import_dependence_pct: float = 88.0
    period: str = "FY2024-25 baseline"
    source_url: str = "https://ppac.gov.in/import-export"
    provenance: SourceKind = SourceKind.CACHED
    retrieved_at: datetime = datetime(2025, 4, 1, tzinfo=timezone.utc)


def get_ppac_snapshot() -> PPACSnapshot:
    return PPACSnapshot()


async def fetch_eia_prices() -> list[PriceQuote]:
    if not settings.eia_api_key:
        return []
    url = "https://api.eia.gov/v2/petroleum/pri/spt/data/"
    params = [
        ("api_key", settings.eia_api_key), ("frequency", "weekly"),
        ("data[0]", "value"), ("facets[series][]", "RBRTE"),
        ("sort[0][column]", "period"), ("sort[0][direction]", "desc"),
        ("length", "2"),
    ]
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            rows = response.json().get("response", {}).get("data", [])
        if not rows:
            return []
        latest = float(rows[0]["value"])
        prior = float(rows[1]["value"]) if len(rows) > 1 else latest
        change = (latest - prior) / prior * 100 if prior else 0
        return [PriceQuote(symbol="BRENT", price_usd=round(latest, 2),
                           change_pct=round(change, 2), source="US EIA",
                           source_kind=SourceKind.LIVE)]
    except Exception as exc:  # noqa: BLE001
        log.warning("eia.fetch_failed", error=str(exc))
        return []


_FIRMS_AREAS = [
    ("west_india", 68.0, 8.0, 77.5, 24.5),
    ("east_india", 79.0, 10.0, 89.5, 23.5),
]


async def fetch_firms_events() -> list[IntelEvent]:
    if not settings.nasa_firms_map_key:
        return []
    events: list[IntelEvent] = []
    async with httpx.AsyncClient(timeout=15) as client:
        for area_id, west, south, east, north in _FIRMS_AREAS:
            url = ("https://firms.modaps.eosdis.nasa.gov/api/area/csv/"
                   f"{settings.nasa_firms_map_key}/VIIRS_SNPP_NRT/"
                   f"{west},{south},{east},{north}/1")
            try:
                response = await client.get(url)
                response.raise_for_status()
                for row in list(csv.DictReader(io.StringIO(response.text)))[:20]:
                    confidence = float(row.get("confidence") or 50)
                    lat, lon = float(row["latitude"]), float(row["longitude"])
                    title = f"Thermal anomaly detected in {area_id.replace('_', ' ')}"
                    events.append(IntelEvent(
                        id=make_id("firms", row.get("acq_date", ""), str(lat), str(lon)),
                        title=title,
                        summary="NASA FIRMS VIIRS near-real-time thermal detection.",
                        category=SignalCategory.SATELLITE,
                        severity="high" if confidence >= 80 else "elevated",
                        confidence=min(95, confidence), risk_score=min(80, 35 + confidence / 2),
                        lat=lat, lon=lon, source="NASA FIRMS", source_kind=SourceKind.LIVE,
                        evidence=[Evidence(label="VIIRS detection", detail=row.get("acq_date", ""),
                                           url="https://firms.modaps.eosdis.nasa.gov/")],
                    ))
            except Exception as exc:  # noqa: BLE001
                log.warning("firms.area_failed", area=area_id, error=str(exc))
    return events
