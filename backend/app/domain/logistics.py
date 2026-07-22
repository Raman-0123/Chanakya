"""Logistics realism for procurement alternatives.

The rubric grades procurement on *executability* — factoring spot pricing,
**tanker availability, port congestion** and refinery-grade compatibility. The
decision engine already handles grade/route/sanction feasibility; this module
adds the physical shipping frictions so a ranked alternative carries a real ETA
and landed cost, not a placeholder zero delay.

Deterministic and pure: derived from the baseline network + the active shock.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.entities import EnergyNetwork, Refinery, ShippingCorridor, Supplier
from app.domain.scenarios import ScenarioSpec
from app.operations.models import OperationalSnapshot

# War-risk insurance premium ($/bbl) a route carries at baseline, by chokepoint
# exposure. Open-ocean routes carry none; contested chokepoints carry the most.
_CORRIDOR_WAR_RISK_USD = {"hormuz": 2.5, "red_sea": 2.0, "malacca": 0.8, "cape": 0.0}
# Berth utilisation above this fraction starts adding congestion queue days.
_CONGESTION_THRESHOLD = 0.70


class LogisticsProfile(BaseModel):
    eta_days: int
    transit_delay_days: float
    port_congestion_days: float
    charter_delay_days: float
    tanker_status: str            # available | tight | scarce
    war_risk_premium_usd_bbl: float
    landed_premium_usd_bbl: float  # spot premium + war-risk, per bbl
    notes: list[str]


class ProcurementOption(BaseModel):
    """A physically checked replacement-cargo option used by simulation and UI."""

    supplier_id: str
    supplier: str
    crude_grade: str
    compatible_refineries: list[str] = Field(default_factory=list)
    volume_kbpd: float
    route: str
    corridor_id: str
    eta_days: int
    transit_delay_days: float
    estimated_premium_usd_bbl: float
    capacity_constraint: str
    confidence: float
    feasible: bool
    arrives_within_horizon: bool = False
    port_congestion_days: float = 0.0
    charter_delay_days: float = 0.0
    tanker_status: str = "available"
    war_risk_premium_usd_bbl: float = 0.0
    landed_premium_usd_bbl: float = 0.0
    logistics_notes: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    provenance: dict[str, str] = Field(default_factory=dict)


def tanker_tightness(
    spec: ScenarioSpec,
    operational: OperationalSnapshot | None = None,
    corridor_id: str | None = None,
) -> float:
    """0–1 index of how strained the tanker market is under this shock.

    Rerouting a blocked corridor around a longer path ties up tonnage for more
    days per cargo, so charter availability tightens as the shock deepens.
    """
    s = spec.shock
    tightness = 0.12  # a normally functioning market still runs fairly full
    if s.corridor_id and s.block_fraction > 0:
        tightness += 0.55 * s.block_fraction
    if s.opec_cut_kbpd:
        tightness += 0.15
    if s.demand_surge_pct:
        tightness += min(0.2, s.demand_surge_pct / 100)
    if operational is not None and corridor_id:
        corridor_risk = operational.corridor_risk_map().get(corridor_id, 0.0)
        tightness += min(0.22, corridor_risk / 450)
        flow = next((row for row in operational.vessel_flows
                     if row.corridor_id == corridor_id), None)
        if flow and flow.coverage == "live":
            if flow.moving_tankers == 0:
                tightness += 0.18
            elif flow.moving_tankers >= 8:
                tightness -= 0.05
    return round(min(1.0, tightness), 2)


def _tanker_status(tightness: float) -> tuple[str, float]:
    if tightness >= 0.75:
        return "scarce", 5.0
    if tightness >= 0.45:
        return "tight", 2.0
    return "available", 0.0


def assess_logistics(
    net: EnergyNetwork,
    supplier: Supplier,
    corridor: ShippingCorridor | None,
    compatible: list[Refinery],
    receiving_capacity_kbpd: float,
    spec: ScenarioSpec,
    affected: set[str],
    operational: OperationalSnapshot | None = None,
) -> LogisticsProfile:
    """Compute the real shipping frictions for one procurement alternative."""
    notes: list[str] = []
    base_transit = corridor.base_transit_days if corridor else 14.0

    # --- port congestion: queueing when receiving berths are near saturated ---
    compat_throughput = sum(r.throughput_kbpd for r in compatible)
    utilisation = (compat_throughput / receiving_capacity_kbpd
                   if receiving_capacity_kbpd > 0 else 1.0)
    congestion_days = round(max(0.0, (utilisation - _CONGESTION_THRESHOLD) * 12), 1)
    congestion_days = min(congestion_days, 8.0)
    if congestion_days > 0:
        notes.append(
            f"Receiving berths ~{utilisation*100:.0f}% utilised → "
            f"+{congestion_days:.1f} days queueing."
        )

    # --- tanker availability: charter lead time under market tightness ---
    tightness = tanker_tightness(spec, operational, supplier.corridor_id)
    status, charter_delay = _tanker_status(tightness)
    if charter_delay > 0:
        notes.append(f"Tanker market {status} (tightness {tightness:.2f}) → "
                     f"+{charter_delay:.0f} days to fix tonnage.")

    # --- war-risk: if the supplier's own corridor is a contested chokepoint ---
    war_risk = _CORRIDOR_WAR_RISK_USD.get(supplier.corridor_id, 1.0)
    # An active shock on any chokepoint lifts the regional risk premium.
    if affected:
        war_risk *= 1.0 + 0.5 * spec.shock.block_fraction
    if operational is not None:
        live_risk = operational.corridor_risk_map().get(supplier.corridor_id, 0.0)
        war_risk *= 1.0 + live_risk / 200
    war_risk = round(war_risk, 1)
    if war_risk > 0:
        notes.append(f"War-risk insurance ~+${war_risk:.1f}/bbl on this route.")

    transit_delay = round(congestion_days + charter_delay, 1)
    eta_days = round(base_transit + transit_delay)
    landed_premium = round(supplier.spot_premium_usd + war_risk, 1)

    return LogisticsProfile(
        eta_days=eta_days,
        transit_delay_days=transit_delay,
        port_congestion_days=congestion_days,
        charter_delay_days=charter_delay,
        tanker_status=status,
        war_risk_premium_usd_bbl=war_risk,
        landed_premium_usd_bbl=landed_premium,
        notes=notes,
    )


def build_procurement_options(
    net: EnergyNetwork,
    spec: ScenarioSpec,
    required_kbpd: float,
    operational: OperationalSnapshot | None = None,
) -> list[ProcurementOption]:
    """Rank supplier/route/refinery combinations against current constraints.

    Unlike the old UI-only table, this exact plan is also consumed by the daily
    simulator, so a 34-day cargo cannot magically close a gap on day six.
    """
    blocks = dict(spec.shock.corridor_blocks)
    if spec.shock.corridor_id and spec.shock.block_fraction > 0:
        blocks[spec.shock.corridor_id] = max(
            blocks.get(spec.shock.corridor_id, 0.0), spec.shock.block_fraction,
        )
    affected = {cid for cid, fraction in blocks.items() if fraction > 0}
    sanctioned = set(spec.shock.sanctioned_supplier_ids)
    port_factors = operational.port_capacity_factor if operational else {}
    supplier_risk = operational.supplier_risk if operational else {}
    remaining = max(0.0, required_kbpd)
    options: list[ProcurementOption] = []

    def adjusted_spare(supplier: Supplier) -> float:
        explicit_loss = spec.shock.supplier_disruption_fraction.get(supplier.id, 0.0)
        # Current supplier risk trims confidence/capacity conservatively; it never
        # zeroes supply unless the scenario carries an explicit disruption.
        risk_trim = min(0.45, supplier_risk.get(supplier.id, 0.0) / 220)
        return supplier.spare_capacity_kbpd * (1 - explicit_loss) * (1 - risk_trim)

    ordered = sorted(net.suppliers, key=lambda supplier: (
        supplier.corridor_id in affected,
        -adjusted_spare(supplier),
        supplier.spot_premium_usd,
    ))
    for supplier in ordered:
        corridor = net.corridor(supplier.corridor_id)
        route_block = blocks.get(supplier.corridor_id, 0.0)
        is_sanctioned = supplier.id in sanctioned or supplier.sanctioned
        compatible = [
            refinery for refinery in net.refineries
            if (refinery.preferred_grade == supplier.grade or
                refinery.preferred_grade.value == "medium_sour" or
                supplier.grade.value == "medium_sour")
        ]
        compatible_capacity = sum(refinery.nameplate_kbpd for refinery in compatible)
        receiving_port_ids = {pid for refinery in compatible for pid in refinery.port_ids}
        receiving_capacity = sum(
            port.crude_capacity_kbpd * port_factors.get(port.id, 1.0)
            for port in net.ports
            if port.id in receiving_port_ids and port.id not in spec.shock.ports_offline
        )
        spare = adjusted_spare(supplier)
        volume = min(spare, remaining, compatible_capacity, receiving_capacity)
        route_available = route_block < 0.5
        feasible = bool(volume > 0 and compatible and route_available and not is_sanctioned)
        reasons: list[str] = []
        if not route_available:
            reasons.append(f"route {route_block:.0%} disrupted")
        if is_sanctioned:
            reasons.append("sanctions constraint")
        if not compatible:
            reasons.append("no grade-compatible refinery")
        if receiving_capacity <= 0:
            reasons.append("no available receiving-port capacity")
        if remaining <= 0:
            reasons.append("replacement requirement already allocated")
        logistics = assess_logistics(
            net, supplier, corridor, compatible, receiving_capacity,
            spec, affected, operational,
        )
        within_horizon = feasible and logistics.eta_days <= spec.shock.duration_days
        if feasible:
            remaining = max(0.0, remaining - volume)
        capacity_text = ("; ".join(reasons) if reasons else
                         f"available supplier {spare:,.0f}; compatible refining "
                         f"{compatible_capacity:,.0f}; receiving ports "
                         f"{receiving_capacity:,.0f} kbpd")
        confidence = supplier.reliability
        if operational:
            confidence *= max(0.45, 1 - supplier_risk.get(supplier.id, 0) / 160)
        if not feasible:
            confidence *= 0.45
        options.append(ProcurementOption(
            supplier_id=supplier.id, supplier=supplier.country,
            crude_grade=supplier.grade.value,
            compatible_refineries=[refinery.name for refinery in compatible[:6]],
            volume_kbpd=round(max(0.0, volume), 1),
            route=corridor.name if corridor else supplier.corridor_id,
            corridor_id=supplier.corridor_id, eta_days=logistics.eta_days,
            transit_delay_days=logistics.transit_delay_days,
            estimated_premium_usd_bbl=supplier.spot_premium_usd,
            capacity_constraint=capacity_text, confidence=round(min(95, confidence), 1),
            feasible=feasible, arrives_within_horizon=within_horizon,
            port_congestion_days=logistics.port_congestion_days,
            charter_delay_days=logistics.charter_delay_days,
            tanker_status=logistics.tanker_status,
            war_risk_premium_usd_bbl=logistics.war_risk_premium_usd_bbl,
            landed_premium_usd_bbl=logistics.landed_premium_usd_bbl,
            logistics_notes=logistics.notes,
            evidence=[
                "Supplier capacity/grade from the versioned baseline.",
                "Route checked against every active corridor disruption.",
                f"ETA {logistics.eta_days}d includes {logistics.transit_delay_days:.1f}d "
                f"operational friction; landed premium +${logistics.landed_premium_usd_bbl:.1f}/bbl.",
            ],
            provenance={
                "supplier_capacity": "baseline",
                "market": operational.market.provenance if operational else "baseline",
                "vessels": next((flow.coverage for flow in operational.vessel_flows
                                 if flow.corridor_id == supplier.corridor_id), "unavailable")
                if operational else "unavailable",
            },
        ))
    options.sort(key=lambda item: (
        not item.feasible, not item.arrives_within_horizon,
        item.landed_premium_usd_bbl, -item.confidence,
    ))
    return options
