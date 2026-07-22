"""IntelligenceService — fuses all adapters into one situational picture.

Geopolitical (GDELT), weather, and sanctions signals are normalised into a
single risk-ranked event feed; prices and vessels ride alongside. This is the
Global Intelligence Room's data source and the agents' shared evidence base.
"""

from __future__ import annotations

import asyncio
from collections import Counter

from app.ingestion.gdelt import fetch_gdelt_events
from app.ingestion.models import (
    Evidence,
    IntelEvent,
    PriceQuote,
    SanctionSignal,
    SignalCategory,
    SourceKind,
    Vessel,
    WeatherObs,
)
from app.ingestion.prices import fetch_prices
from app.ingestion.sanctions import fetch_sanctions
from app.ingestion.tagging import make_id
from app.ingestion.vessels import fetch_vessels
from app.ingestion.weather import fetch_weather

_RISK_LOCATION_CORRIDOR = {"hormuz": "hormuz", "bab_el_mandeb": "red_sea"}


def _weather_to_events(obs: list[WeatherObs]) -> list[IntelEvent]:
    events: list[IntelEvent] = []
    for o in obs:
        if o.shipping_risk in ("high", "critical"):
            corr = _RISK_LOCATION_CORRIDOR.get(o.location_id)
            risk = 78 if o.shipping_risk == "critical" else 58
            events.append(IntelEvent(
                id=make_id("weather", o.location_id, o.condition),
                title=f"Severe conditions at {o.location_name}",
                summary=(f"Wind {o.wind_kph:.0f} kph"
                         + (f", waves {o.wave_m:.1f} m" if o.wave_m else "")
                         + f" — {o.shipping_risk} shipping risk."),
                category=SignalCategory.WEATHER,
                severity=o.shipping_risk, confidence=88, risk_score=risk,
                affected_corridors=[corr] if corr else [],
                lat=o.lat, lon=o.lon, source="Open-Meteo",
                source_kind=o.source_kind,
                evidence=[Evidence(label="Observation",
                                   detail=f"{o.condition}, wind {o.wind_kph:.0f} kph")],
            ))
    return events


def _sanctions_to_events(sigs: list[SanctionSignal]) -> list[IntelEvent]:
    return [
        IntelEvent(
            id=make_id("sanction-ev", s.id),
            title=f"Sanctions activity: {s.program}",
            summary=s.description,
            category=SignalCategory.SANCTIONS,
            severity="high", confidence=76, risk_score=62,
            affected_countries=s.affected_countries,
            affected_corridors=["hormuz"] if "Iran" in s.affected_countries else [],
            source=s.source, source_kind=s.source_kind,
            evidence=[Evidence(label="Designation", detail=f"{s.target} ({s.target_type})")],
        )
        for s in sigs
    ]


class IntelligenceFeed:
    def __init__(self, events, prices, weather, vessels, sanctions):
        self.events: list[IntelEvent] = events
        self.prices: list[PriceQuote] = prices
        self.weather: list[WeatherObs] = weather
        self.vessels: list[Vessel] = vessels
        self.sanctions: list[SanctionSignal] = sanctions

    def summary(self) -> dict:
        sev = Counter(e.severity for e in self.events)
        corridors = Counter()
        for e in self.events:
            for c in e.affected_corridors:
                corridors[c] += 1
        provenance = Counter(e.source_kind.value for e in self.events)
        top_risk = max((e.risk_score for e in self.events), default=0)
        threat = ("critical" if sev.get("critical") else
                  "high" if sev.get("high") else
                  "elevated" if sev.get("elevated") else "nominal")
        return {
            "event_count": len(self.events),
            "by_severity": dict(sev),
            "corridors_flagged": dict(corridors),
            "provenance": dict(provenance),
            "peak_risk_score": top_risk,
            "threat_level": threat,
            "is_live": any(e.source_kind == SourceKind.LIVE for e in self.events),
        }


class IntelligenceService:
    async def feed(self) -> IntelligenceFeed:
        geo, prices, weather, vessels, sanctions = await asyncio.gather(
            fetch_gdelt_events(), fetch_prices(), fetch_weather(),
            fetch_vessels(), fetch_sanctions(),
        )
        events = geo + _weather_to_events(weather) + _sanctions_to_events(sanctions)
        events.sort(key=lambda e: e.risk_score, reverse=True)
        return IntelligenceFeed(events, prices, weather, vessels, sanctions)


_service = IntelligenceService()


def get_intelligence_service() -> IntelligenceService:
    return _service
