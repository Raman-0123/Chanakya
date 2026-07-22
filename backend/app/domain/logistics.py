"""Logistics realism for procurement alternatives.

The rubric grades procurement on *executability* — factoring spot pricing,
**tanker availability, port congestion** and refinery-grade compatibility. The
decision engine already handles grade/route/sanction feasibility; this module
adds the physical shipping frictions so a ranked alternative carries a real ETA
and landed cost, not a placeholder zero delay.

Deterministic and pure: derived from the baseline network + the active shock.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.domain.entities import EnergyNetwork, Refinery, ShippingCorridor, Supplier
from app.domain.scenarios import ScenarioSpec

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


def tanker_tightness(spec: ScenarioSpec) -> float:
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
    tightness = tanker_tightness(spec)
    status, charter_delay = _tanker_status(tightness)
    if charter_delay > 0:
        notes.append(f"Tanker market {status} (tightness {tightness:.2f}) → "
                     f"+{charter_delay:.0f} days to fix tonnage.")

    # --- war-risk: if the supplier's own corridor is a contested chokepoint ---
    war_risk = _CORRIDOR_WAR_RISK_USD.get(supplier.corridor_id, 1.0)
    # An active shock on any chokepoint lifts the regional risk premium.
    if affected:
        war_risk *= 1.0 + 0.5 * spec.shock.block_fraction
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
