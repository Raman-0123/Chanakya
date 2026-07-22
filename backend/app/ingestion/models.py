"""Normalized ingestion schema — one shape for every source."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from typing import Any

from pydantic import BaseModel, Field


class SourceKind(str, Enum):
    LIVE = "live"
    CACHED = "cached"
    REPLAY = "replay"
    SIMULATED = "simulated"
    UNAVAILABLE = "unavailable"
    # Compatibility alias for older adapters. It intentionally serializes as
    # simulated so synthetic records are never represented as live evidence.
    FALLBACK = "simulated"


class SignalCategory(str, Enum):
    GEOPOLITICAL = "geopolitical"
    SHIPPING = "shipping"
    MARKET = "market"
    WEATHER = "weather"
    SANCTIONS = "sanctions"
    SATELLITE = "satellite"


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Evidence(BaseModel):
    label: str
    detail: str
    url: str | None = None


class DomainEvent(BaseModel):
    """Versioned event contract shared by adapters, storage, agents and WS."""

    id: str
    event_type: str
    category: SignalCategory
    title: str
    summary: str
    source: str
    provenance: SourceKind
    observed_at: datetime = Field(default_factory=_now)
    ingested_at: datetime = Field(default_factory=_now)
    freshness_seconds: int = Field(default=0, ge=0)
    stale: bool = False
    severity: str = "elevated"
    confidence: float = Field(default=60.0, ge=0, le=100)
    risk_score: float = Field(default=50.0, ge=0, le=100)
    lat: float | None = None
    lon: float | None = None
    affected_entity_ids: list[str] = Field(default_factory=list)
    affected_countries: list[str] = Field(default_factory=list)
    affected_corridors: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    source_url: str | None = None
    raw_hash: str = ""
    deduplication_key: str = ""
    schema_version: str = "1.0"
    attributes: dict[str, Any] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        canonical = json.dumps(
            {
                "source": self.source,
                "event_type": self.event_type,
                "title": self.title,
            },
            sort_keys=True,
        )
        digest = hashlib.sha256(canonical.encode()).hexdigest()
        if not self.raw_hash:
            self.raw_hash = digest
        if not self.deduplication_key:
            self.deduplication_key = digest[:32]

    @classmethod
    def from_intel(cls, event: "IntelEvent") -> "DomainEvent":
        now = _now()
        freshness = max(0, int((now - event.published_at).total_seconds()))
        return cls(
            id=event.id,
            event_type=event.category.value,
            category=event.category,
            title=event.title,
            summary=event.summary,
            source=event.source,
            provenance=event.source_kind,
            observed_at=event.published_at,
            ingested_at=now,
            freshness_seconds=freshness,
            stale=freshness > 3600,
            severity=event.severity,
            confidence=event.confidence,
            risk_score=event.risk_score,
            lat=event.lat,
            lon=event.lon,
            affected_entity_ids=[f"corridor:{c}" for c in event.affected_corridors],
            affected_countries=event.affected_countries,
            affected_corridors=event.affected_corridors,
            evidence=event.evidence,
            source_url=next((item.url for item in event.evidence if item.url), None),
            attributes={"estimated_duration_days": event.estimated_duration_days},
        )


class IntelEvent(BaseModel):
    """A clustered, risk-scored situational event (not a raw article)."""

    id: str
    title: str
    summary: str
    category: SignalCategory
    severity: str = "elevated"          # nominal | elevated | high | critical
    confidence: float = 60.0            # 0–100
    risk_score: float = 50.0            # 0–100
    affected_countries: list[str] = Field(default_factory=list)
    affected_corridors: list[str] = Field(default_factory=list)
    estimated_duration_days: int | None = None
    lat: float | None = None
    lon: float | None = None
    source: str = "unknown"
    source_kind: SourceKind = SourceKind.FALLBACK
    published_at: datetime = Field(default_factory=_now)
    evidence: list[Evidence] = Field(default_factory=list)


class PriceQuote(BaseModel):
    symbol: str                          # BRENT | WTI
    price_usd: float
    change_pct: float = 0.0
    as_of: datetime = Field(default_factory=_now)
    source: str = "unknown"
    source_kind: SourceKind = SourceKind.FALLBACK


class WeatherObs(BaseModel):
    location_id: str
    location_name: str
    lat: float
    lon: float
    wind_kph: float
    wave_m: float | None = None
    condition: str = "clear"
    shipping_risk: str = "nominal"       # severity band
    source_kind: SourceKind = SourceKind.FALLBACK


class Vessel(BaseModel):
    id: str
    name: str
    kind: str = "crude_tanker"
    lat: float
    lon: float
    heading: float = 0.0
    speed_kn: float = 0.0
    corridor_id: str | None = None
    origin: str | None = None
    destination: str | None = None
    cargo_kbbl: float | None = None
    source_kind: SourceKind = SourceKind.FALLBACK


class SanctionSignal(BaseModel):
    id: str
    program: str
    target: str
    target_type: str = "entity"          # entity | vessel | country
    description: str
    affected_countries: list[str] = Field(default_factory=list)
    listed_on: str | None = None
    source: str = "OFAC/OpenSanctions"
    source_kind: SourceKind = SourceKind.FALLBACK
