"""Quantified ontology cascade — magnitude propagation across the digital twin.

The ontology `/impact` endpoint answers *which* nodes are downstream of a shock.
This module answers *how much*: block a port / corridor / supplier / refinery by
a fraction and it propagates the physical consequence through the
supplier→corridor→port→refinery ontology — how many kbpd of crude each refinery
loses, its utilisation drop, which nodes are fully isolated, how long strategic
reserves could bridge the gap, and the national macro rollup (validated by
re-running the deterministic simulation engine where the shock maps to one).

Pure and deterministic over the seeded network — same input ⇒ same cascade.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.engine import SimulationEngine
from app.domain.entities import EnergyNetwork
from app.domain.scenarios import ResponseLevers, ScenarioCategory, ScenarioShock, ScenarioSpec


class CascadeImpact(BaseModel):
    id: str
    type: str
    label: str
    relation: str                       # how the shock reaches this node
    crude_short_kbpd: float = 0.0
    utilization_before: float | None = None
    utilization_after: float | None = None
    status: str = "nominal"             # nominal|elevated|strained|critical|offline
    isolated: bool = False
    note: str = ""


class CascadeHop(BaseModel):
    source: str
    target: str
    relation: str
    magnitude_kbpd: float


class MacroProjection(BaseModel):
    nesi_before: float
    nesi_after: float
    nesi_band: str
    brent_change_pct: float
    residual_shortfall_kbpd: float
    diesel_projected_inr: float


class CascadeResult(BaseModel):
    origin: dict
    block_fraction: float
    affected: list[CascadeImpact] = Field(default_factory=list)
    hops: list[CascadeHop] = Field(default_factory=list)
    isolated: list[str] = Field(default_factory=list)
    rollup: dict = Field(default_factory=dict)
    macro_projection: MacroProjection | None = None
    narrative: str = ""


def _status_from_util(util_after: float, lost_fraction: float) -> str:
    if util_after <= 5 or lost_fraction >= 0.95:
        return "offline"
    if util_after < 40:
        return "critical"
    if util_after < 70:
        return "strained"
    if lost_fraction > 0:
        return "elevated"
    return "nominal"


def _resolve(net: EnergyNetwork, node_id: str) -> tuple[str, object] | None:
    """Resolve 'port:vadinar' or bare 'vadinar' to (type, entity)."""
    raw = node_id.split(":", 1)[-1]
    for port in net.ports:
        if port.id == raw:
            return "port", port
    for corr in net.corridors:
        if corr.id == raw:
            return "corridor", corr
    for sup in net.suppliers:
        if sup.id == raw:
            return "supplier", sup
    for ref in net.refineries:
        if ref.id == raw:
            return "refinery", ref
    return None


def _spr_bridge_days(net: EnergyNetwork, short_kbpd: float) -> float:
    if short_kbpd <= 0:
        return 0.0
    spr_bbl = net.spr_total_mmt * 1_000_000 * net.demand.bbl_per_tonne
    return round(spr_bbl / (short_kbpd * 1000), 1)


def _refinery_impacts_from_port(
    net: EnergyNetwork, port_id: str, block_fraction: float
) -> tuple[list[CascadeImpact], list[CascadeHop]]:
    impacts, hops = [], []
    for ref in net.refineries:
        if port_id not in ref.port_ids:
            continue
        # A refinery splits intake across its feeding ports; blocking one removes
        # that port's share of the refinery's crude (scaled by the block level).
        share_via_port = 1.0 / len(ref.port_ids)
        lost_fraction = block_fraction * share_via_port
        short = round(ref.throughput_kbpd * lost_fraction, 1)
        util_before = ref.utilization
        util_after = round(ref.throughput_kbpd * (1 - lost_fraction) / ref.nameplate_kbpd * 100, 1)
        status = _status_from_util(util_after, lost_fraction)
        impacts.append(CascadeImpact(
            id=f"refinery:{ref.id}", type="refinery", label=ref.name,
            relation=f"fed by blocked port ({share_via_port:.0%} of its intake)",
            crude_short_kbpd=short, utilization_before=util_before,
            utilization_after=util_after, status=status,
            isolated=util_after <= 5,
            note=(f"Loses {short:,.0f} kbpd; utilisation {util_before:.0f}%→{util_after:.0f}%."),
        ))
        hops.append(CascadeHop(source=f"port:{port_id}", target=f"refinery:{ref.id}",
                               relation="FEEDS", magnitude_kbpd=short))
    return impacts, hops


def _allocate_refinery_loss(
    refineries: list, total_short_kbpd: float, relation: str,
) -> list[CascadeImpact]:
    throughput = sum(refinery.throughput_kbpd for refinery in refineries) or 1.0
    impacts: list[CascadeImpact] = []
    for refinery in refineries:
        short = min(refinery.throughput_kbpd,
                    total_short_kbpd * refinery.throughput_kbpd / throughput)
        after = 100 * max(0.0, refinery.throughput_kbpd - short) / refinery.nameplate_kbpd
        lost_fraction = short / refinery.throughput_kbpd if refinery.throughput_kbpd else 0
        impacts.append(CascadeImpact(
            id=f"refinery:{refinery.id}", type="refinery", label=refinery.name,
            relation=relation, crude_short_kbpd=round(short, 1),
            utilization_before=refinery.utilization,
            utilization_after=round(after, 1),
            status=_status_from_util(after, lost_fraction), isolated=after <= 5,
            note=f"Allocated flow loss {short:,.0f} kbpd; utilisation falls to {after:.0f}%.",
        ))
    return impacts


def _distribution_impacts(
    net: EnergyNetwork, refinery_impacts: list[CascadeImpact],
) -> tuple[list[CascadeImpact], list[CascadeHop]]:
    by_refinery = {item.id.split(":", 1)[-1]: item for item in refinery_impacts}
    impacts: list[CascadeImpact] = []
    hops: list[CascadeHop] = []
    for center in net.demand_centers:
        linked = [by_refinery[refinery_id] for refinery_id in center.supplying_refinery_ids
                  if refinery_id in by_refinery]
        if not linked:
            continue
        linked_capacity = sum(
            next(refinery.throughput_kbpd for refinery in net.refineries
                 if refinery.id == item.id.split(":", 1)[-1])
            for item in linked
        ) or 1.0
        product_loss = sum(item.crude_short_kbpd for item in linked)
        loss_fraction = min(1.0, product_loss / linked_capacity)
        status = ("critical" if loss_fraction >= 0.35 else
                  "strained" if loss_fraction >= 0.15 else "elevated")
        impacts.append(CascadeImpact(
            id=f"demand:{center.id}", type="distribution", label=center.name,
            relation="receives products from affected refineries",
            crude_short_kbpd=round(product_loss, 1), status=status,
            isolated=loss_fraction >= 0.95,
            note=(f"Estimated product-flow exposure {loss_fraction:.0%}; "
                  f"power-linked demand share {center.sector_mix.get('power', 0):.0%}."),
        ))
        for item in linked:
            hops.append(CascadeHop(
                source=item.id, target=f"demand:{center.id}",
                relation="DISTRIBUTES_TO", magnitude_kbpd=item.crude_short_kbpd,
            ))
    return impacts, hops


def propagate_cascade(
    net: EnergyNetwork, node_id: str, block_fraction: float = 1.0
) -> CascadeResult:
    """Propagate a node block through the ontology into quantified impacts."""
    block_fraction = max(0.0, min(1.0, block_fraction))
    resolved = _resolve(net, node_id)
    if resolved is None:
        return CascadeResult(origin={"id": node_id, "type": "unknown", "label": node_id},
                             block_fraction=block_fraction,
                             narrative=f"No ontology node matches '{node_id}'.")
    ntype, entity = resolved
    impacts: list[CascadeImpact] = []
    hops: list[CascadeHop] = []
    macro_shock: ScenarioShock | None = None
    label = getattr(entity, "name", None) or getattr(entity, "country", entity.id)

    if ntype == "port":
        impacts, hops = _refinery_impacts_from_port(net, entity.id, block_fraction)
        macro_shock = ScenarioShock(ports_offline=[entity.id], duration_days=10,
                                    market_shock_base=0.03)

    elif ntype == "corridor":
        # suppliers on the corridor lose their transiting volume
        daily = net.daily_crude_imports_kbpd
        for sup in net.suppliers:
            if sup.corridor_id != entity.id:
                continue
            short = round(sup.import_share * daily * block_fraction, 1)
            impacts.append(CascadeImpact(
                id=f"supplier:{sup.id}", type="supplier", label=sup.country,
                relation="transits blocked corridor", crude_short_kbpd=short,
                status="critical" if block_fraction >= 0.6 else "strained",
                note=f"{short:,.0f} kbpd of {sup.country} crude delayed/blocked.",
            ))
            hops.append(CascadeHop(source=f"supplier:{sup.id}", target=f"corridor:{entity.id}",
                                   relation="TRANSITS", magnitude_kbpd=short))
        # corridor delivers to its ports → refineries feel the intake loss
        served_ports = [p for p in net.ports
                        if (entity.id == "malacca" and p.coast.value == "east")
                        or (entity.id != "malacca" and p.coast.value == "west")]
        corridor_short = sum(i.crude_short_kbpd for i in impacts)
        for port in served_ports:
            hops.append(CascadeHop(source=f"corridor:{entity.id}", target=f"port:{port.id}",
                                   relation="ARRIVES_AT", magnitude_kbpd=round(corridor_short / max(1, len(served_ports)), 1)))
        served_ids = {port.id for port in served_ports}
        downstream = [refinery for refinery in net.refineries
                      if served_ids.intersection(refinery.port_ids)]
        allocated = _allocate_refinery_loss(
            downstream, corridor_short, "downstream of disrupted corridor",
        )
        impacts.extend(allocated)
        for item in allocated:
            hops.append(CascadeHop(
                source=f"corridor:{entity.id}", target=item.id,
                relation="CONSTRAINS", magnitude_kbpd=item.crude_short_kbpd,
            ))
        macro_shock = ScenarioShock(corridor_id=entity.id, block_fraction=block_fraction,
                                    duration_days=14, market_shock_base=0.12)

    elif ntype == "supplier":
        daily = net.daily_crude_imports_kbpd
        short_total = round(entity.import_share * daily * block_fraction, 1)
        impacts.append(CascadeImpact(
            id=f"supplier:{entity.id}", type="supplier", label=entity.country,
            relation="blocked at source", crude_short_kbpd=short_total,
            status="critical" if block_fraction >= 0.6 else "strained",
            note=f"{short_total:,.0f} kbpd ({entity.import_share:.0%} of imports) removed.",
        ))
        compatible_refineries = [
            ref for ref in net.refineries
            if (ref.preferred_grade == entity.grade
                or entity.grade.value == "medium_sour"
                or ref.preferred_grade.value == "medium_sour")
        ]
        allocated = _allocate_refinery_loss(
            compatible_refineries, short_total, "grade-compatible supplier loss",
        )
        impacts.extend(allocated)
        for item in allocated:
            hops.append(CascadeHop(
                source=f"supplier:{entity.id}", target=item.id,
                relation="SUPPLIES", magnitude_kbpd=item.crude_short_kbpd,
            ))
        macro_shock = ScenarioShock(sanctioned_supplier_ids=[entity.id], duration_days=30,
                                    market_shock_base=0.07)

    elif ntype == "refinery":
        lost = round(entity.throughput_kbpd * block_fraction, 1)
        util_after = round(entity.throughput_kbpd * (1 - block_fraction) / entity.nameplate_kbpd * 100, 1)
        impacts.append(CascadeImpact(
            id=f"refinery:{entity.id}", type="refinery", label=entity.name,
            relation="production halted", crude_short_kbpd=lost,
            utilization_before=entity.utilization, utilization_after=util_after,
            status=_status_from_util(util_after, block_fraction), isolated=util_after <= 5,
            note=f"Processing down {lost:,.0f} kbpd; fuel output falls proportionally.",
        ))

    refinery_impacts = [item for item in impacts if item.type == "refinery"]
    demand_impacts, demand_hops = _distribution_impacts(net, refinery_impacts)
    impacts.extend(demand_impacts)
    hops.extend(demand_hops)

    isolated = [i.id for i in impacts if i.isolated]
    total_short = round(sum(i.crude_short_kbpd for i in impacts if i.type in ("refinery",)) or
                        sum(i.crude_short_kbpd for i in impacts), 1)
    refinery_impacts = [i for i in impacts if i.type == "refinery"]
    rollup = {
        "total_crude_short_kbpd": total_short,
        "pct_national_throughput": round(100 * total_short / net.total_throughput_kbpd, 1)
        if net.total_throughput_kbpd else 0.0,
        "refineries_affected": len(refinery_impacts),
        "refineries_offline": sum(1 for i in refinery_impacts if i.status == "offline"),
        "refineries_critical": sum(1 for i in refinery_impacts if i.status == "critical"),
        "isolated_count": len(isolated),
        "spr_bridge_days": _spr_bridge_days(net, total_short),
        # ~diesel is roughly 38% of refinery output in India's slate
        "est_diesel_output_loss_kbpd": round(total_short * 0.38, 1),
        "distribution_hubs_affected": len(demand_impacts),
        "power_linked_demand_at_risk_pct": round(sum(
            center.demand_share * center.sector_mix.get("power", 0) * 100
            for center in net.demand_centers
            if f"demand:{center.id}" in {item.id for item in demand_impacts}
        ), 1),
    }

    macro = None
    if macro_shock is not None:
        spec = ScenarioSpec(id=f"cascade-{ntype}", name=f"Cascade: {label}",
                            category=ScenarioCategory.CHOKEPOINT,
                            description=f"Ontology cascade from blocking {label}.",
                            shock=macro_shock)
        r = SimulationEngine(net).run(spec, ResponseLevers(spr_release_pct=30))
        macro = MacroProjection(
            nesi_before=r.nesi_before, nesi_after=r.nesi_after.value,
            nesi_band=r.nesi_after.band, brent_change_pct=r.brent_change_pct,
            residual_shortfall_kbpd=r.residual_shortfall_kbpd,
            diesel_projected_inr=r.diesel_projected_inr,
        )

    narrative = _narrative(ntype, label, block_fraction, rollup, isolated, macro)
    return CascadeResult(
        origin={"id": f"{ntype}:{entity.id}", "type": ntype, "label": label},
        block_fraction=block_fraction, affected=impacts, hops=hops,
        isolated=isolated, rollup=rollup, macro_projection=macro, narrative=narrative,
    )


def _narrative(ntype, label, frac, rollup, isolated, macro) -> str:
    parts = [f"Blocking {label} by {frac:.0%} removes "
             f"{rollup['total_crude_short_kbpd']:,.0f} kbpd of crude flow "
             f"({rollup['pct_national_throughput']:.1f}% of national throughput)."]
    if rollup["refineries_affected"]:
        parts.append(f"{rollup['refineries_affected']} refineries feel it "
                     f"({rollup['refineries_critical']} critical, "
                     f"{rollup['refineries_offline']} offline).")
    if isolated:
        parts.append(f"{len(isolated)} node(s) are fully isolated: {', '.join(isolated)}.")
    parts.append(f"Strategic reserves could bridge the gap ~{rollup['spr_bridge_days']:.0f} days.")
    if macro:
        parts.append(f"Security Index {macro.nesi_before:.0f}→{macro.nesi_after:.0f} "
                     f"({macro.nesi_band}); Brent {macro.brent_change_pct:+.1f}%.")
    return " ".join(parts)
