from app.agents.decision import build_procurement_alternatives, rank_strategies
from app.domain import SimulationEngine, build_energy_network
from app.domain.scenarios import ResponseLevers, ScenarioShock, ScenarioSpec, ScenarioCategory, get_scenario


def test_daily_horizon_and_finite_spr() -> None:
    engine = SimulationEngine(build_energy_network())
    spec = get_scenario("hormuz_closure")
    result = engine.run(spec, ResponseLevers(spr_release_pct=100,
                                             enable_reroute=True, enable_spot=True))
    assert len(result.daily_balance) == spec.shock.duration_days
    assert result.spr_consumed_mmt <= engine.net.spr_total_mmt
    assert all(day.spr_remaining_mmt >= 0 for day in result.daily_balance)
    assert result.residual_shortfall_kbpd == max(
        day.residual_shortfall_kbpd for day in result.daily_balance
    )
    assert result.spr_drawdown_plan
    assert round(sum(site.release_kbpd for site in result.spr_drawdown_plan), 1) == result.spr_release_kbpd
    assert all(site.replenishment_from_day for site in result.spr_drawdown_plan)
    assert len(result.refinery_projections) == len(engine.net.refineries)
    assert 0 <= result.power_sector_stress_pct <= 100


def test_digital_twin_reaches_downstream_demand_hubs() -> None:
    network = build_energy_network()
    assert network.demand_centers
    assert round(sum(center.demand_share for center in network.demand_centers), 6) == 1
    refinery_ids = {refinery.id for refinery in network.refineries}
    assert all(set(center.supplying_refinery_ids) <= refinery_ids
               for center in network.demand_centers)


def test_overlapping_shocks_do_not_double_count_cargo() -> None:
    engine = SimulationEngine(build_energy_network())
    spec = ScenarioSpec(
        id="overlap", name="Overlap", category=ScenarioCategory.SANCTIONS,
        description="Supplier and route fail together",
        shock=ScenarioShock(corridor_id="red_sea", block_fraction=1,
                            sanctioned_supplier_ids=["russia"], duration_days=5),
    )
    result = engine.run(spec)
    assert result.supply_gap_kbpd <= engine.net.daily_crude_imports_kbpd
    expected_red_sea = sum(
        supplier.import_share * engine.net.daily_crude_imports_kbpd
        for supplier in engine.net.suppliers if supplier.corridor_id == "red_sea"
    )
    assert result.supply_gap_kbpd == round(expected_red_sea, 1)


def test_procurement_rejects_blocked_hormuz_suppliers() -> None:
    engine = SimulationEngine(build_energy_network())
    spec = get_scenario("hormuz_closure")
    alternatives = build_procurement_alternatives(engine, spec, 800)
    assert alternatives
    assert all(not item.feasible for item in alternatives if item.route == "Strait of Hormuz")
    assert any(item.feasible and item.supplier == "United States" for item in alternatives)


def test_strategy_ranking_includes_feasibility_and_evidence() -> None:
    engine = SimulationEngine(build_energy_network())
    strategies = rank_strategies(engine, get_scenario("hormuz_closure"),
                                 engine.net.daily_crude_imports_kbpd)
    assert [strategy.rank for strategy in strategies] == [1, 2, 3]
    assert all("feasibility" in strategy.scores and "evidence" in strategy.scores
               for strategy in strategies)
    assert all(strategy.procurement_alternatives for strategy in strategies)
