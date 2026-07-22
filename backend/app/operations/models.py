"""Typed, provenance-carrying state consumed by simulation and optimization."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.domain.scenarios import ScenarioSpec


class GeoStation(BaseModel):
    id: str
    kind: str                  # chokepoint | weather | port | refinery | reserve
    name: str
    lat: float
    lon: float
    status: str                # nominal | elevated | high | critical | unavailable
    risk_score: float = 0.0
    provenance: str = "unavailable"
    observed_at: datetime | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)
    affected_entity_ids: list[str] = Field(default_factory=list)


class CorridorOperationalState(BaseModel):
    corridor_id: str
    disruption_probability: float
    band: str
    signal_pressure: float
    mean_confidence: float
    contributing_events: int
    lead_time_hours: float
    is_live: bool
    source_kinds: list[str] = Field(default_factory=list)
    actionable: bool = False


class VesselFlowState(BaseModel):
    corridor_id: str
    vessel_count: int = 0
    tanker_count: int = 0
    moving_tankers: int = 0
    average_speed_kn: float = 0.0
    live_count: int = 0
    coverage: str = "unavailable"


class MarketOperationalState(BaseModel):
    brent_usd: float
    change_pct: float = 0.0
    observed_at: datetime
    source: str
    provenance: str


class OperationalSnapshot(BaseModel):
    id: str
    generated_at: datetime
    active_scenario: ScenarioSpec
    corridors: list[CorridorOperationalState]
    stations: list[GeoStation]
    vessel_flows: list[VesselFlowState]
    market: MarketOperationalState
    supplier_risk: dict[str, float] = Field(default_factory=dict)
    port_capacity_factor: dict[str, float] = Field(default_factory=dict)
    evidence_events: list[dict[str, Any]] = Field(default_factory=list)
    provenance: dict[str, int] = Field(default_factory=dict)
    is_live: bool = False
    data_quality_score: float = 0.0
    freshness_seconds: int | None = None
    assumptions: list[str] = Field(default_factory=list)

    def corridor_risk_map(self) -> dict[str, float]:
        return {row.corridor_id: row.disruption_probability for row in self.corridors}

    def vessel_count_map(self) -> dict[str, int]:
        return {row.corridor_id: row.moving_tankers for row in self.vessel_flows}
