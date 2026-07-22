from datetime import datetime, timezone

from app.agents.base import AgentAssessment
from app.agents.decision import rank_strategies
from app.domain import SimulationEngine, build_energy_network
from app.domain.scenarios import ResponseLevers, ScenarioCategory, ScenarioShock, ScenarioSpec
from app.ingestion.models import IntelEvent, PriceQuote, SignalCategory, SourceKind, Vessel, WeatherObs
from app.ingestion.service import IntelligenceFeed
from app.operations.service import OperationalStateService


def test_operational_snapshot_only_uses_qualified_events_for_actions() -> None:
    now = datetime.now(timezone.utc)
    live_red_sea = IntelEvent(
        id="live-red-sea", title="Shipping suspension", summary="Verified transit interruption",
        category=SignalCategory.SHIPPING, severity="critical", confidence=95,
        risk_score=96, affected_corridors=["red_sea"], estimated_duration_days=12,
        lat=12.6, lon=43.3, source="test-live", source_kind=SourceKind.LIVE,
        published_at=now,
    )
    simulated_hormuz = IntelEvent(
        id="sim-hormuz", title="Exercise input", summary="Training-only closure",
        category=SignalCategory.GEOPOLITICAL, severity="critical", confidence=99,
        risk_score=99, affected_corridors=["hormuz"], estimated_duration_days=30,
        lat=26.5, lon=56.2, source="fixture", source_kind=SourceKind.SIMULATED,
        published_at=now,
    )
    feed = IntelligenceFeed(
        [live_red_sea, simulated_hormuz],
        [PriceQuote(symbol="BRENT", price_usd=91.2, change_pct=4.5,
                    source="market-test", source_kind=SourceKind.LIVE, as_of=now)],
        [WeatherObs(location_id="vadinar", location_name="Vadinar / Sikka",
                    lat=22.28, lon=69.72, wind_kph=52, wave_m=2.8,
                    condition="rough", shipping_risk="high",
                    source_kind=SourceKind.LIVE)],
        [Vessel(id="tanker-1", name="Verified tanker", kind="tanker", lat=15, lon=51,
                speed_kn=12, corridor_id="red_sea", source_kind=SourceKind.LIVE)],
        [],
    )

    snapshot = OperationalStateService().update(feed)

    assert snapshot.market.brent_usd == 91.2
    assert snapshot.active_scenario.shock.corridor_blocks.get("red_sea", 0) > 0
    assert "hormuz" not in snapshot.active_scenario.shock.corridor_blocks
    assert "live-red-sea" in snapshot.active_scenario.source_event_ids
    assert snapshot.port_capacity_factor["vadinar"] == 0.5
    assert any(station.id == "station:weather:vadinar" and station.provenance == "live"
               for station in snapshot.stations)
    assert snapshot.vessel_count_map()["red_sea"] == 1


def test_route_specific_eta_controls_daily_arrivals() -> None:
    engine = SimulationEngine(build_energy_network())
    spec = ScenarioSpec(
        id="short-shock", name="Short Hormuz shock", category=ScenarioCategory.CHOKEPOINT,
        description="A five-day closure cannot be solved by a month-away cargo.",
        shock=ScenarioShock(corridor_id="hormuz", block_fraction=0.9, duration_days=5),
    )
    result = engine.run(
        spec,
        ResponseLevers(spr_release_pct=0, enable_reroute=True, enable_spot=False),
    )

    assert any(option.feasible and not option.arrives_within_horizon
               for option in result.procurement_plan)
    assert result.replacement_arrived_by_horizon_kbpd == 0
    assert all(day.replacement_arrivals_kbpd == 0 for day in result.daily_balance)
    assert any("arrives after" in warning for warning in result.feasibility_warnings)


def test_agent_control_proposals_reach_optimizer() -> None:
    engine = SimulationEngine(build_energy_network())
    assessments = [
        AgentAssessment(
            agent_id=f"agent-{index}", agent_name=f"Agent {index}", role="test",
            stance="Use reserve bridge", confidence=90,
            proposed_levers=ResponseLevers(
                spr_release_pct=80, enable_reroute=False, enable_spot=False,
            ),
        )
        for index in range(6)
    ]
    strategies = rank_strategies(
        engine,
        ScenarioSpec(
            id="agent-test", name="Agent test", category=ScenarioCategory.CHOKEPOINT,
            description="Verify council controls reach decision search.",
            shock=ScenarioShock(corridor_id="hormuz", block_fraction=0.8, duration_days=14),
        ),
        engine.net.daily_crude_imports_kbpd,
        assessments=assessments,
    )

    assert strategies[0].optimization["council_target"] == {
        "spr_release_pct": 80.0, "enable_reroute": False, "enable_spot": False,
    }
    assert all("council_alignment" in strategy.scores for strategy in strategies)
