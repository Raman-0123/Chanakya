from app.domain import build_energy_network
from app.domain.logistics import assess_logistics, tanker_tightness
from app.domain.scenarios import ScenarioShock, ScenarioSpec, ScenarioCategory, get_scenario


def _compatible(net, supplier):
    return [r for r in net.refineries
            if r.preferred_grade == supplier.grade
            or supplier.grade.value == "medium_sour"]


def _receiving_capacity(net, compatible):
    port_ids = {pid for r in compatible for pid in r.port_ids}
    return sum(p.crude_capacity_kbpd for p in net.ports if p.id in port_ids)


def test_transit_delay_is_real_and_eta_consistent() -> None:
    net = build_energy_network()
    spec = get_scenario("hormuz_closure")
    supplier = next(s for s in net.suppliers if s.id == "usa")
    corridor = net.corridor(supplier.corridor_id)
    compatible = _compatible(net, supplier)
    logi = assess_logistics(net, supplier, corridor, compatible,
                            _receiving_capacity(net, compatible), spec, {"hormuz"})
    # the old hardcoded 0.0 is gone: a real disruption adds shipping friction
    assert logi.transit_delay_days > 0
    assert logi.eta_days == round(corridor.base_transit_days + logi.transit_delay_days)
    assert logi.tanker_status in {"available", "tight", "scarce"}


def test_tanker_market_tightens_with_shock_severity() -> None:
    hormuz = get_scenario("hormuz_closure")            # block_fraction 0.9
    calm = ScenarioSpec(id="calm", name="Calm", category=ScenarioCategory.DEMAND,
                        description="mild", shock=ScenarioShock(demand_surge_pct=2))
    assert tanker_tightness(hormuz) > tanker_tightness(calm)


def test_war_risk_higher_on_contested_chokepoint() -> None:
    net = build_energy_network()
    spec = get_scenario("hormuz_closure")
    affected = {"hormuz"}
    russia = next(s for s in net.suppliers if s.id == "russia")   # red_sea
    usa = next(s for s in net.suppliers if s.id == "usa")         # cape (open ocean)
    r_logi = assess_logistics(net, russia, net.corridor("red_sea"),
                              _compatible(net, russia),
                              _receiving_capacity(net, _compatible(net, russia)),
                              spec, affected)
    u_logi = assess_logistics(net, usa, net.corridor("cape"),
                              _compatible(net, usa),
                              _receiving_capacity(net, _compatible(net, usa)),
                              spec, affected)
    assert r_logi.war_risk_premium_usd_bbl > u_logi.war_risk_premium_usd_bbl
    assert u_logi.war_risk_premium_usd_bbl == 0.0  # open-ocean Cape route
