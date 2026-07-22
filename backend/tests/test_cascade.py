from app.domain import build_energy_network
from app.domain.cascade import propagate_cascade


def test_port_block_isolates_single_port_refineries() -> None:
    net = build_energy_network()
    r = propagate_cascade(net, "port:vadinar", 1.0)
    # every refinery whose ONLY feeding port is vadinar must be fully isolated
    expected = {rf.id for rf in net.refineries if rf.port_ids == ["vadinar"]}
    isolated_ids = {i.id.split(":", 1)[1] for i in r.affected if i.isolated}
    assert expected, "seed should have single-port vadinar refineries"
    assert expected.issubset(isolated_ids)
    assert r.rollup["total_crude_short_kbpd"] > 0
    assert 0 <= r.rollup["pct_national_throughput"] <= 100
    assert r.rollup["spr_bridge_days"] > 0


def test_block_fraction_scales_impact_monotonically() -> None:
    net = build_energy_network()
    half = propagate_cascade(net, "port:vadinar", 0.5).rollup["total_crude_short_kbpd"]
    full = propagate_cascade(net, "port:vadinar", 1.0).rollup["total_crude_short_kbpd"]
    assert full > half > 0


def test_corridor_block_hits_transiting_suppliers_and_has_macro() -> None:
    net = build_energy_network()
    r = propagate_cascade(net, "corridor:hormuz", 0.9)
    hormuz_suppliers = {s.country for s in net.suppliers if s.corridor_id == "hormuz"}
    hit = {i.label for i in r.affected if i.type == "supplier"}
    assert hit == hormuz_suppliers
    assert r.macro_projection is not None
    assert r.macro_projection.brent_change_pct > 0


def test_unknown_node_is_handled_gracefully() -> None:
    net = build_energy_network()
    r = propagate_cascade(net, "port:does_not_exist", 1.0)
    assert r.affected == []
    assert "No ontology node matches" in r.narrative
