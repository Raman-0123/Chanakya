"""Deterministic disruption simulation engine.

Given the baseline network, a shock, and response levers, it computes the
cascade — supply gap → mitigation → reserve drawdown → residual shortfall →
price / refinery / macro impact → NESI — recording every assumption so the
result is fully auditable (the docs' "no black-box AI" requirement).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.entities import EnergyNetwork
from app.domain.nesi import NesiResult, NesiSignals, compute_nesi
from app.domain.scenarios import ResponseLevers, ScenarioSpec

# ---- calibration constants (stated assumptions) ----
BBL_PER_LITRE_RETAIL_FACTOR = 0.62   # crude->pump pass-through incl. tax buffering
SPR_MAX_RELEASE_KBPD = 900.0         # max sustainable SPR draw rate
GDP_SENSITIVITY = 0.15               # % GDP per 10% sustained Brent rise
INFLATION_SENSITIVITY = 5.0          # CPI bps per 1% Brent rise


class ImpactLine(BaseModel):
    label: str
    value: float
    unit: str
    detail: str


class DailyBalance(BaseModel):
    day: int
    disrupted_kbpd: float
    reroute_arrivals_kbpd: float
    replacement_arrivals_kbpd: float
    inventory_draw_kbpd: float
    spr_draw_kbpd: float
    residual_shortfall_kbpd: float
    spr_remaining_mmt: float


class SimulationResult(BaseModel):
    scenario_id: str
    scenario_name: str
    duration_days: int

    # supply cascade (kbpd)
    supply_gap_kbpd: float
    rerouted_kbpd: float
    replaced_spare_kbpd: float
    replaced_spot_kbpd: float
    spr_release_kbpd: float
    residual_shortfall_kbpd: float

    # coverage
    spr_days_remaining: float
    national_utilization_pct: float
    stressed_refineries: list[str]

    # market + macro
    brent_projected_usd: float
    brent_change_pct: float
    diesel_projected_inr: float
    petrol_projected_inr: float
    inflation_bps: float
    gdp_impact_pct: float
    transit_delay_days: float
    freight_premium_pct: float
    est_daily_cost_musd: float

    # index
    nesi_before: float
    nesi_after: NesiResult

    # explainability
    headline: str
    assumptions: list[str]
    impact_lines: list[ImpactLine]
    daily_balance: list[DailyBalance] = Field(default_factory=list)
    spr_consumed_mmt: float = 0.0
    spr_remaining_mmt: float = 0.0
    feasibility_warnings: list[str] = Field(default_factory=list)


class SimulationEngine:
    """Pure, side-effect-free simulator over an EnergyNetwork baseline."""

    def __init__(self, network: EnergyNetwork):
        self.net = network

    # -- helpers -------------------------------------------------------------
    def _daily_imports_kbpd(self, demand_surge_pct: float) -> float:
        base = self.net.daily_crude_imports_kbpd
        return base * (1 + demand_surge_pct / 100)

    def _affected_corridor_ids(self, spec: ScenarioSpec) -> set[str]:
        ids: set[str] = set()
        if spec.shock.corridor_id and spec.shock.block_fraction > 0:
            ids.add(spec.shock.corridor_id)
        return ids

    def _daily_horizon(
        self, spec: ScenarioSpec, gap: float, rerouted: float,
        replaced_spare: float, replaced_spot: float, desired_spr_rate: float,
        transit_delay: float,
    ) -> tuple[list[DailyBalance], float, float, list[str]]:
        """Resolve the disruption day-by-day with finite buffers and ETAs."""
        net = self.net
        usable_inventory_kbbl = sum(
            max(0.0, refinery.inventory_days - 5.0) * refinery.throughput_kbpd
            for refinery in net.refineries
        )
        spr_remaining_kbbl = net.spr_total_mmt * 1_000_000 * net.demand.bbl_per_tonne / 1000
        procurement_eta = min(12, max(5, round(min(
            (corridor.base_transit_days for corridor in net.corridors), default=7
        ) / 2)))
        rows: list[DailyBalance] = []
        warnings: list[str] = []
        for day in range(1, spec.shock.duration_days + 1):
            reroute_arrival = rerouted if rerouted and day > max(1, round(transit_delay)) else 0.0
            replacement = ((replaced_spare + replaced_spot)
                           if day > procurement_eta else 0.0)
            uncovered = max(0.0, gap - reroute_arrival - replacement)
            inventory_draw = min(uncovered, usable_inventory_kbbl)
            usable_inventory_kbbl -= inventory_draw
            uncovered -= inventory_draw
            spr_draw = min(uncovered, desired_spr_rate, spr_remaining_kbbl)
            spr_remaining_kbbl -= spr_draw
            residual = max(0.0, uncovered - spr_draw)
            rows.append(DailyBalance(
                day=day, disrupted_kbpd=round(gap, 1),
                reroute_arrivals_kbpd=round(reroute_arrival, 1),
                replacement_arrivals_kbpd=round(replacement, 1),
                inventory_draw_kbpd=round(inventory_draw, 1),
                spr_draw_kbpd=round(spr_draw, 1),
                residual_shortfall_kbpd=round(residual, 1),
                spr_remaining_mmt=round(
                    spr_remaining_kbbl * 1000 / (1_000_000 * net.demand.bbl_per_tonne), 3
                ),
            ))
        if rows and any(row.spr_draw_kbpd < desired_spr_rate and
                        row.residual_shortfall_kbpd > 0 for row in rows):
            warnings.append("SPR inventory or draw capacity is insufficient for the full horizon.")
        consumed_kbbl = (net.spr_total_mmt * 1_000_000 * net.demand.bbl_per_tonne / 1000
                         - spr_remaining_kbbl)
        consumed_mmt = consumed_kbbl * 1000 / (1_000_000 * net.demand.bbl_per_tonne)
        remaining_mmt = spr_remaining_kbbl * 1000 / (1_000_000 * net.demand.bbl_per_tonne)
        return rows, round(consumed_mmt, 3), round(remaining_mmt, 3), warnings

    # -- main ----------------------------------------------------------------
    def run(self, spec: ScenarioSpec, levers: ResponseLevers | None = None) -> SimulationResult:
        s = spec.shock
        lev = levers or spec.default_levers
        net = self.net
        assumptions: list[str] = []

        daily_imports = self._daily_imports_kbpd(s.demand_surge_pct)
        if s.demand_surge_pct:
            assumptions.append(
                f"Demand surge of {s.demand_surge_pct:.0f}% lifts daily crude need "
                f"to ~{daily_imports:,.0f} kbpd."
            )

        affected = self._affected_corridor_ids(spec)

        # ---- 1. gross supply disrupted ----------------------------------
        gap = 0.0
        for sup in net.suppliers:
            share_kbpd = sup.import_share * daily_imports
            corridor_fraction = s.block_fraction if sup.corridor_id in affected else 0.0
            sanction_fraction = 1.0 if (sup.id in s.sanctioned_supplier_ids or sup.sanctioned) else 0.0
            # A cargo affected by both sanctions and a corridor closure is still
            # one cargo. Use the strongest shock instead of double-counting it.
            gap += share_kbpd * max(corridor_fraction, sanction_fraction)
        if s.ports_offline:
            # ports offline choke intake regardless of corridor
            port_cap = sum(
                p.crude_capacity_kbpd for p in net.ports if p.id in s.ports_offline
            )
            gap += min(port_cap, daily_imports * 0.25)
            assumptions.append(
                f"Ports offline ({', '.join(s.ports_offline)}) remove up to "
                f"{port_cap:,.0f} kbpd of intake capacity."
            )
        if s.opec_cut_kbpd:
            # tightens market; India loses a proportional slice of spot access
            gap += s.opec_cut_kbpd * 0.12
            assumptions.append(
                f"OPEC+ cut of {s.opec_cut_kbpd:,.0f} kbpd removes global spare "
                "and tightens India's spot access."
            )
        gap = round(min(gap, daily_imports), 1)

        # ---- 2. rerouting (delayed, not lost) ---------------------------
        rerouted = 0.0
        transit_delay = 0.0
        freight_premium = 0.0
        for cid in affected:
            corr = net.corridor(cid)
            if corr and corr.reroute_corridor_id and lev.enable_reroute:
                corr_kbpd = sum(
                    sup.import_share * daily_imports
                    for sup in net.suppliers
                    if sup.corridor_id == cid
                ) * s.block_fraction
                rerouted += corr_kbpd
                transit_delay = max(transit_delay, corr.reroute_added_days)
                freight_premium = max(freight_premium, corr.reroute_cost_premium_pct)
                assumptions.append(
                    f"{corr.name} cargoes reroute via {corr.reroute_corridor_id} "
                    f"(+{corr.reroute_added_days:.0f} days, +{corr.reroute_cost_premium_pct:.0f}% freight)."
                )
        rerouted = round(min(rerouted, gap), 1)
        lost = gap - rerouted  # volume that must be replaced, not just delayed

        # ---- 3. replacement: spare capacity from UNAFFECTED suppliers ----
        available_spare = sum(
            sup.spare_capacity_kbpd
            for sup in net.suppliers
            if sup.corridor_id not in affected
            and sup.id not in s.sanctioned_supplier_ids
        )
        if s.opec_cut_kbpd:
            available_spare *= 0.4  # OPEC cut guts spare
            assumptions.append("Available spare capacity cut to 40% under OPEC+ action.")
        replaced_spare = round(min(lost, available_spare), 1)
        remaining = lost - replaced_spare

        # ---- 4. spot procurement (bounded) ------------------------------
        replaced_spot = 0.0
        if lev.enable_spot and remaining > 0:
            spot_ceiling = daily_imports * 0.05  # can source ~5% of imports on spot
            replaced_spot = round(min(remaining, spot_ceiling), 1)
            remaining -= replaced_spot
            assumptions.append(
                f"Spot procurement covers up to ~{spot_ceiling:,.0f} kbpd at premium."
            )

        # ---- 5. SPR drawdown --------------------------------------------
        desired_spr_release = round(SPR_MAX_RELEASE_KBPD * lev.spr_release_pct / 100, 1)
        daily_balance, spr_consumed_mmt, spr_remaining_mmt, feasibility_warnings = self._daily_horizon(
            spec, gap, rerouted, replaced_spare, replaced_spot,
            desired_spr_release, transit_delay,
        )
        spr_release = max((row.spr_draw_kbpd for row in daily_balance), default=0.0)
        residual = max((row.residual_shortfall_kbpd for row in daily_balance), default=0.0)
        # days SPR lasts at this release rate
        spr_bbl = net.spr_total_mmt * 1_000_000 * net.demand.bbl_per_tonne
        spr_days = round(spr_bbl / (spr_release * 1000), 1) if spr_release > 0 else net.spr_coverage_days()
        assumptions.append(
            f"SPR release {lev.spr_release_pct:.0f}% → {spr_release:,.0f} kbpd, "
            f"sustainable ~{spr_days:.1f} days."
        )
        assumptions.append(
            "Daily horizon holds five refinery inventory days as an operational minimum; "
            "replacement cargo begins after a calibrated procurement lead time."
        )

        # ---- 6. refinery utilisation under residual shortfall ------------
        base_thru = net.total_throughput_kbpd
        shortfall_ratio = residual / base_thru if base_thru else 0
        national_util = round(
            100 * net.total_throughput_kbpd / net.total_refining_capacity_kbpd
            * (1 - shortfall_ratio),
            1,
        )
        stressed = [
            r.name for r in net.refineries
            if r.inventory_days < spec.shock.duration_days and residual > 0
        ][:5]

        # ---- 7. market + macro ------------------------------------------
        duration_factor = min(1.6, s.duration_days / 14)
        gap_pressure = 0.45 * (residual / daily_imports) if daily_imports else 0
        brent_shock = s.market_shock_base * duration_factor + gap_pressure
        brent_proj = round(net.market.brent_usd * (1 + brent_shock), 1)
        brent_change_pct = round(brent_shock * 100, 1)

        d_brent = brent_proj - net.market.brent_usd
        retail_delta = d_brent * net.market.inr_usd / 159 * BBL_PER_LITRE_RETAIL_FACTOR
        diesel_proj = round(net.market.retail_diesel_inr_per_l + retail_delta, 1)
        petrol_proj = round(net.market.retail_petrol_inr_per_l + retail_delta, 1)

        inflation_bps = round(brent_change_pct * INFLATION_SENSITIVITY, 0)
        gdp_impact = round(-(brent_change_pct / 10) * GDP_SENSITIVITY, 2)

        # cost of disruption ≈ premium on rerouted/spot/spot-priced volume
        spot_premium_avg = 3.0
        est_daily_cost = round(
            (replaced_spot * 1000 * spot_premium_avg
             + rerouted * 1000 * d_brent * 0.05) / 1_000_000,
            1,
        )

        # ---- 8. NESI recompute ------------------------------------------
        nesi_before = compute_nesi(net).value
        supply_avail = round(100 * (1 - residual / daily_imports), 1) if daily_imports else 100
        shipping_stab = 70.0 - (60.0 if affected else 0) * s.block_fraction
        geo_tension = 52.0 + (35.0 if (affected or s.sanctioned_supplier_ids) else 10.0) * min(1, duration_factor)
        volatility = 42.0 + brent_change_pct * 1.4
        nesi_after = compute_nesi(
            net,
            NesiSignals(
                supply_availability=max(0, supply_avail),
                shipping_stability=max(0, shipping_stab),
                geopolitical_tension=min(100, geo_tension),
                market_volatility=min(100, volatility),
            ),
        )

        headline = self._headline(spec, residual, brent_change_pct, nesi_after.value)

        impact_lines = [
            ImpactLine(label="Supply Gap", value=gap, unit="kbpd",
                       detail="Gross crude flow disrupted at peak."),
            ImpactLine(label="Residual Shortfall", value=residual, unit="kbpd",
                       detail="Unmet demand after mitigation + SPR."),
            ImpactLine(label="Brent Projection", value=brent_proj, unit="USD/bbl",
                       detail=f"{brent_change_pct:+.1f}% vs. ${net.market.brent_usd:.0f}."),
            ImpactLine(label="Diesel (retail)", value=diesel_proj, unit="INR/L",
                       detail=f"{retail_delta:+.1f} INR/L pass-through."),
            ImpactLine(label="Inflation", value=inflation_bps, unit="bps",
                       detail="Estimated CPI pressure."),
            ImpactLine(label="GDP Impact", value=gdp_impact, unit="%",
                       detail="Annualised, if sustained."),
            ImpactLine(label="SPR Coverage", value=spr_days, unit="days",
                       detail="At chosen release rate."),
        ]

        return SimulationResult(
            scenario_id=spec.id, scenario_name=spec.name,
            duration_days=s.duration_days,
            supply_gap_kbpd=gap, rerouted_kbpd=rerouted,
            replaced_spare_kbpd=replaced_spare, replaced_spot_kbpd=replaced_spot,
            spr_release_kbpd=spr_release, residual_shortfall_kbpd=residual,
            spr_days_remaining=spr_days, national_utilization_pct=max(0, national_util),
            stressed_refineries=stressed,
            brent_projected_usd=brent_proj, brent_change_pct=brent_change_pct,
            diesel_projected_inr=diesel_proj, petrol_projected_inr=petrol_proj,
            inflation_bps=inflation_bps, gdp_impact_pct=gdp_impact,
            transit_delay_days=transit_delay, freight_premium_pct=freight_premium,
            est_daily_cost_musd=est_daily_cost,
            nesi_before=nesi_before, nesi_after=nesi_after,
            headline=headline, assumptions=assumptions, impact_lines=impact_lines,
            daily_balance=daily_balance, spr_consumed_mmt=spr_consumed_mmt,
            spr_remaining_mmt=spr_remaining_mmt,
            feasibility_warnings=feasibility_warnings,
        )

    @staticmethod
    def _headline(spec: ScenarioSpec, residual: float, brent_pct: float, nesi: float) -> str:
        if residual <= 0:
            return (
                f"{spec.name}: mitigation and reserves fully absorb the shock; "
                f"Brent +{brent_pct:.0f}%, security index holds at {nesi:.0f}."
            )
        return (
            f"{spec.name}: ~{residual:,.0f} kbpd unmet after mitigation; "
            f"Brent +{brent_pct:.0f}%, security index falls to {nesi:.0f}."
        )
