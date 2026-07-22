"""Fuse current intelligence into one auditable operational snapshot.

The old application fetched live feeds and then simulated a disconnected static
scenario.  This service is the missing bridge: the same snapshot is consumed by
the risk map, live scenario, simulator, procurement optimizer and agent council.
"""

from __future__ import annotations

import asyncio
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import time

from app.domain import build_energy_network
from app.domain.risk_scoring import assess_disruption_risk
from app.domain.scenarios import (
    ResponseLevers,
    ScenarioCategory,
    ScenarioShock,
    ScenarioSpec,
)
from app.ingestion.models import SignalCategory, SourceKind
from app.ingestion.service import IntelligenceFeed, get_intelligence_service
from app.operations.models import (
    CorridorOperationalState,
    GeoStation,
    MarketOperationalState,
    OperationalSnapshot,
    VesselFlowState,
)

_ACTIONABLE_KINDS = {SourceKind.LIVE, SourceKind.CACHED}
_WEATHER_TO_PORT = {
    "vadinar": "vadinar", "mumbai": "mumbai", "mangalore": "mangalore",
    "paradip": "paradip", "vizag": "vizag",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _severity_score(value: str) -> float:
    return {"nominal": 12.0, "elevated": 38.0, "high": 68.0,
            "critical": 92.0}.get(value, 0.0)


def _snapshot_id(material: dict) -> str:
    raw = json.dumps(material, sort_keys=True, default=str, separators=(",", ":"))
    return "ops-" + hashlib.sha256(raw.encode()).hexdigest()[:16]


class OperationalStateService:
    def __init__(self) -> None:
        self._network = build_energy_network()
        self._snapshot: OperationalSnapshot | None = None
        self._updated_monotonic = 0.0
        self._lock = asyncio.Lock()

    async def current(self, *, force: bool = False) -> OperationalSnapshot:
        if self._snapshot is not None and not force and time.monotonic() - self._updated_monotonic < 15:
            return self._snapshot
        async with self._lock:
            if self._snapshot is not None and not force and time.monotonic() - self._updated_monotonic < 15:
                return self._snapshot
            feed = await get_intelligence_service().feed()
            return self.update(feed)

    def update(self, feed: IntelligenceFeed) -> OperationalSnapshot:
        generated = _now()
        risk = assess_disruption_risk(self._network, feed.events, now=generated)
        provenance = Counter()
        for row in [*feed.events, *feed.prices, *feed.weather, *feed.vessels,
                    *feed.sanctions, *feed.detections]:
            provenance[getattr(row, "source_kind", SourceKind.UNAVAILABLE).value] += 1

        corridor_rows: list[CorridorOperationalState] = []
        for row in risk.corridors:
            contributing = [event for event in feed.events
                            if row.corridor_id in event.affected_corridors]
            kinds = sorted({event.source_kind.value for event in contributing})
            actionable = any(event.source_kind in _ACTIONABLE_KINDS for event in contributing)
            corridor_rows.append(CorridorOperationalState(
                corridor_id=row.corridor_id,
                disruption_probability=row.disruption_probability,
                band=row.band,
                signal_pressure=row.signal_pressure,
                mean_confidence=row.mean_confidence,
                contributing_events=row.contributing_events,
                lead_time_hours=row.lead_time_hours,
                is_live=row.is_live,
                source_kinds=kinds,
                actionable=actionable,
            ))

        latest_price = next((p for p in feed.prices if p.symbol.upper() == "BRENT"), None)
        if latest_price is None:
            market = self._network.market
            market_state = MarketOperationalState(
                brent_usd=market.brent_usd, change_pct=0,
                observed_at=generated, source="domain baseline", provenance="simulated",
            )
        else:
            market_state = MarketOperationalState(
                brent_usd=latest_price.price_usd, change_pct=latest_price.change_pct,
                observed_at=latest_price.as_of, source=latest_price.source,
                provenance=latest_price.source_kind.value,
            )

        stations, port_factors = self._stations(feed, corridor_rows, generated)
        flows = self._vessel_flows(feed)
        scenario = self._derive_scenario(feed, corridor_rows, port_factors,
                                         market_state, generated, dict(provenance))
        supplier_risk = {row.supplier_id: row.disruption_probability for row in risk.suppliers}
        observed = [event.published_at for event in feed.events
                    if event.source_kind in _ACTIONABLE_KINDS]
        freshest = max(observed) if observed else None
        freshness = max(0, int((generated - freshest).total_seconds())) if freshest else None
        evidence = [
            {
                "id": event.id, "title": event.title, "summary": event.summary,
                "category": event.category.value, "severity": event.severity,
                "source": event.source, "source_kind": event.source_kind.value,
                "published_at": event.published_at.isoformat(),
                "risk_score": event.risk_score, "confidence": event.confidence,
                "affected_corridors": event.affected_corridors,
                "affected_countries": event.affected_countries,
                "url": next((item.url for item in event.evidence if item.url), None),
            }
            for event in feed.events[:12]
        ]
        total = sum(provenance.values())
        trustworthy = provenance.get("live", 0) + provenance.get("cached", 0) * 0.75
        quality = round(100 * trustworthy / total, 1) if total else 0.0
        material = {
            "scenario": scenario.model_dump(mode="json", exclude={"generated_at"}),
            "market": [market_state.brent_usd, market_state.change_pct, market_state.provenance],
            "stations": [(s.id, s.status, round(s.risk_score, 1), s.provenance) for s in stations],
            "flows": [(f.corridor_id, f.tanker_count, f.moving_tankers) for f in flows],
        }
        snapshot = OperationalSnapshot(
            id=_snapshot_id(material), generated_at=generated, active_scenario=scenario,
            corridors=corridor_rows, stations=stations, vessel_flows=flows,
            market=market_state, supplier_risk=supplier_risk,
            port_capacity_factor=port_factors, evidence_events=evidence,
            provenance=dict(provenance), is_live=provenance.get("live", 0) > 0,
            data_quality_score=quality, freshness_seconds=freshness,
            assumptions=[
                "Only live or cached evidence may automatically disrupt a corridor or supplier.",
                "Simulated fallback signals remain visible for training but cannot trigger an operational action.",
                "Weather-derived port capacity is a decision-support estimate, not a port-authority closure notice.",
            ],
        )
        self._snapshot = snapshot
        self._updated_monotonic = time.monotonic()
        return snapshot

    def _stations(self, feed: IntelligenceFeed,
                  corridors: list[CorridorOperationalState],
                  generated: datetime) -> tuple[list[GeoStation], dict[str, float]]:
        stations: list[GeoStation] = []
        port_factors = {port.id: 1.0 for port in self._network.ports}
        corridor_by_id = {row.corridor_id: row for row in corridors}
        for corridor in self._network.corridors:
            if corridor.chokepoint_coords is None:
                continue
            state = corridor_by_id[corridor.id]
            provenance = ("live" if state.is_live else
                          "cached" if "cached" in state.source_kinds else
                          "simulated" if state.source_kinds else "unavailable")
            stations.append(GeoStation(
                id=f"station:chokepoint:{corridor.id}", kind="chokepoint",
                name=corridor.chokepoint, lat=corridor.chokepoint_coords.lat,
                lon=corridor.chokepoint_coords.lon, status=state.band,
                risk_score=state.disruption_probability, provenance=provenance,
                observed_at=generated,
                metrics={"signal_pressure": state.signal_pressure,
                         "confidence": state.mean_confidence,
                         "lead_time_hours": state.lead_time_hours,
                         "event_count": state.contributing_events},
                affected_entity_ids=[f"corridor:{corridor.id}"],
            ))

        weather_by_id = {row.location_id: row for row in feed.weather}
        for obs in feed.weather:
            risk_score = _severity_score(obs.shipping_risk)
            stations.append(GeoStation(
                id=f"station:weather:{obs.location_id}", kind="weather",
                name=f"{obs.location_name} met-ocean station", lat=obs.lat, lon=obs.lon,
                status=obs.shipping_risk, risk_score=risk_score,
                provenance=obs.source_kind.value, observed_at=generated,
                metrics={"wind_kph": obs.wind_kph, "wave_m": obs.wave_m,
                         "condition": obs.condition},
            ))
            port_id = _WEATHER_TO_PORT.get(obs.location_id)
            if port_id:
                factor = {"critical": 0.0, "high": 0.5, "elevated": 0.8,
                          "nominal": 1.0}.get(obs.shipping_risk, 1.0)
                port_factors[port_id] = factor

        for port in self._network.ports:
            obs = weather_by_id.get(port.id)
            status = obs.shipping_risk if obs else "unavailable"
            stations.append(GeoStation(
                id=f"station:port:{port.id}", kind="port", name=port.name,
                lat=port.coords.lat, lon=port.coords.lon, status=status,
                risk_score=_severity_score(status),
                provenance=obs.source_kind.value if obs else "unavailable",
                observed_at=generated if obs else None,
                metrics={"nominal_capacity_kbpd": port.crude_capacity_kbpd,
                         "available_capacity_kbpd": round(
                             port.crude_capacity_kbpd * port_factors[port.id], 1)},
                affected_entity_ids=[f"port:{port.id}"],
            ))
        return stations, port_factors

    def _vessel_flows(self, feed: IntelligenceFeed) -> list[VesselFlowState]:
        rows: list[VesselFlowState] = []
        for corridor in self._network.corridors:
            vessels = [v for v in feed.vessels if v.corridor_id == corridor.id]
            tankers = [v for v in vessels if "tanker" in v.kind]
            moving = [v for v in tankers if 1 <= v.speed_kn <= 30]
            speeds = [v.speed_kn for v in moving]
            rows.append(VesselFlowState(
                corridor_id=corridor.id, vessel_count=len(vessels),
                tanker_count=len(tankers), moving_tankers=len(moving),
                average_speed_kn=round(sum(speeds) / len(speeds), 1) if speeds else 0,
                live_count=sum(v.source_kind == SourceKind.LIVE for v in vessels),
                coverage=("live" if any(v.source_kind == SourceKind.LIVE for v in vessels)
                          else "replay" if vessels else "unavailable"),
            ))
        return rows

    def _derive_scenario(
        self, feed: IntelligenceFeed, corridors: list[CorridorOperationalState],
        port_factors: dict[str, float], market: MarketOperationalState,
        generated: datetime, provenance: dict[str, int],
    ) -> ScenarioSpec:
        actionable_events = [event for event in feed.events
                             if event.source_kind in _ACTIONABLE_KINDS]
        corridor_blocks: dict[str, float] = {}
        source_ids: set[str] = set()
        confidence_values: list[float] = []
        durations: list[int] = []
        for state in corridors:
            related = [event for event in actionable_events
                       if state.corridor_id in event.affected_corridors]
            if not related or state.disruption_probability < 35:
                continue
            block = min(0.9, max(0.1, (state.disruption_probability - 20) / 90))
            corridor_blocks[state.corridor_id] = round(block, 3)
            source_ids.update(event.id for event in related)
            confidence_values.extend(event.confidence for event in related)
            durations.extend(event.estimated_duration_days for event in related
                             if event.estimated_duration_days)

        supplier_loss: dict[str, float] = {}
        for event in actionable_events:
            if event.category != SignalCategory.SANCTIONS:
                continue
            for supplier in self._network.suppliers:
                if supplier.country in event.affected_countries:
                    supplier_loss[supplier.id] = max(
                        supplier_loss.get(supplier.id, 0.0), event.confidence / 100,
                    )
                    source_ids.add(event.id)
                    confidence_values.append(event.confidence)

        port_loss = {port_id: round(1 - factor, 2)
                     for port_id, factor in port_factors.items() if factor < 1}
        if port_loss:
            weather_events = [event for event in actionable_events
                              if event.category == SignalCategory.WEATHER]
            source_ids.update(event.id for event in weather_events)
            confidence_values.extend(event.confidence for event in weather_events)
            durations.extend(event.estimated_duration_days for event in weather_events
                             if event.estimated_duration_days)
        primary = max(corridor_blocks, key=corridor_blocks.get) if corridor_blocks else None
        block_fraction = corridor_blocks.get(primary, 0.0) if primary else 0.0
        duration = max(durations, default=7 if (corridor_blocks or supplier_loss or port_loss) else 1)
        confidence = (round(sum(confidence_values) / len(confidence_values), 1)
                      if confidence_values else 60.0)
        if corridor_blocks:
            category = ScenarioCategory.CHOKEPOINT
            label = ", ".join(self._network.corridor(cid).name for cid in corridor_blocks
                              if self._network.corridor(cid))
            name = f"Live detected corridor disruption: {label}"
        elif supplier_loss:
            category = ScenarioCategory.SANCTIONS
            name = "Live detected supplier restriction"
        elif port_loss:
            category = ScenarioCategory.WEATHER
            name = "Live detected port-capacity disruption"
        else:
            category = ScenarioCategory.MARKET
            name = "Live operating baseline"
        return ScenarioSpec(
            id="auto_live", name=name, category=category,
            description=(
                "Automatically generated from the latest provenance-qualified "
                "geopolitical, sanctions, weather, market and AIS snapshot."
            ),
            shock=ScenarioShock(
                corridor_id=primary, block_fraction=block_fraction,
                corridor_blocks=corridor_blocks,
                duration_days=max(1, min(90, duration)),
                sanctioned_supplier_ids=list(supplier_loss),
                supplier_disruption_fraction=supplier_loss,
                ports_offline=[pid for pid, loss in port_loss.items() if loss >= 1],
                port_capacity_loss=port_loss,
                market_shock_base=max(0.0, market.change_pct / 100),
            ),
            default_levers=ResponseLevers(spr_release_pct=25, enable_reroute=True,
                                          enable_spot=True),
            source=("live" if provenance.get("live", 0) else
                    "cached" if provenance.get("cached", 0) else "simulated"),
            generated_at=generated, source_event_ids=sorted(source_ids),
            confidence=confidence, provenance=provenance,
        )


_service = OperationalStateService()


def get_operational_service() -> OperationalStateService:
    return _service
