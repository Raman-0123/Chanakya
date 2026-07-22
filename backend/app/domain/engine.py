"""Deterministic disruption simulation engine.

Given the baseline network, a shock, and response levers, it computes the
cascade — supply gap → mitigation → reserve drawdown → residual shortfall →
price / refinery / macro impact → NESI — recording every assumption so the
result is fully auditable (the docs' "no black-box AI" requirement).
"""

from __future__ import annotations

import math

from pydantic import BaseModel, Field

from app.domain.entities import EnergyNetwork
from app.domain.logistics import ProcurementOption, build_procurement_options
from app.domain.nesi import NesiResult, NesiSignals, compute_nesi
from app.domain.scenarios import ResponseLevers, ScenarioSpec
from app.operations.models import OperationalSnapshot

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


class RefineryProjection(BaseModel):
    refinery_id: str
    refinery: str
    utilization_before_pct: float
    utilization_after_pct: float
    throughput_loss_kbpd: float
    inventory_days: float
    status: str


class SprSiteSchedule(BaseModel):
    site_id: str
    site: str
    release_kbpd: float
    sustainable_days: float
    projected_draw_mmt: float
    start_day: int
    taper_day: int | None = None
    replenishment_from_day: int | None = None
    served_refineries: list[str] = Field(default_factory=list)
    rationale: str


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
    power_sector_stress_pct: float
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
    procurement_plan: list[ProcurementOption] = Field(default_factory=list)
    replacement_arrived_by_horizon_kbpd: float = 0.0
    refinery_projections: list[RefineryProjection] = Field(default_factory=list)
    spr_drawdown_plan: list[SprSiteSchedule] = Field(default_factory=list)
    operational_snapshot_id: str | None = None
    input_provenance: dict[str, int | str] = Field(default_factory=dict)


class SimulationEngine:
    """Pure, side-effect-free simulator over an EnergyNetwork baseline."""

    def __init__(self, network: EnergyNetwork):
        self.net = network

    # -- helpers -------------------------------------------------------------
    def _daily_imports_kbpd(self, demand_surge_pct: float) -> float:
        base = self.net.daily_crude_imports_kbpd
        return base * (1 + demand_surge_pct / 100)

    def _affected_corridors(self, spec: ScenarioSpec) -> dict[str, float]:
        blocks = dict(spec.shock.corridor_blocks)
        if spec.shock.corridor_id and spec.shock.block_fraction > 0:
            blocks[spec.shock.corridor_id] = max(
                blocks.get(spec.shock.corridor_id, 0.0), spec.shock.block_fraction,
            )
        return {cid: max(0.0, min(1.0, fraction))
                for cid, fraction in blocks.items() if fraction > 0}

    def _daily_horizon(
        self, spec: ScenarioSpec, gap: float, rerouted: float,
        procurement_plan: list[ProcurementOption], replaced_spot: float,
        desired_spr_rate: float, transit_delay: float, spot_eta_days: int,
    ) -> tuple[list[DailyBalance], float, float, list[str]]:
        """Resolve the disruption day-by-day with finite buffers and ETAs."""
        net = self.net
        usable_inventory_kbbl = sum(
            max(0.0, refinery.inventory_days - 5.0) * refinery.throughput_kbpd
            for refinery in net.refineries
        )
        spr_remaining_kbbl = net.spr_total_mmt * 1_000_000 * net.demand.bbl_per_tonne / 1000
        rows: list[DailyBalance] = []
        warnings: list[str] = []
        for day in range(1, spec.shock.duration_days + 1):
            reroute_arrival = rerouted if rerouted and day > max(1, round(transit_delay)) else 0.0
            replacement = sum(
                option.volume_kbpd for option in procurement_plan
                if option.feasible and option.eta_days <= day
            )
            if replaced_spot and day >= spot_eta_days:
                replacement += replaced_spot
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

    def _refinery_projections(self, residual_kbpd: float) -> list[RefineryProjection]:
        """Allocate an unmet national gap toward inventory-vulnerable refineries."""
        weights = {
            refinery.id: refinery.throughput_kbpd / max(1.0, refinery.inventory_days)
            for refinery in self.net.refineries
        }
        total_weight = sum(weights.values()) or 1.0
        rows: list[RefineryProjection] = []
        for refinery in self.net.refineries:
            loss = min(refinery.throughput_kbpd,
                       residual_kbpd * weights[refinery.id] / total_weight)
            remaining = max(0.0, refinery.throughput_kbpd - loss)
            after = 100 * remaining / refinery.nameplate_kbpd if refinery.nameplate_kbpd else 0
            status = ("offline" if after <= 5 else "critical" if after < 40 else
                      "strained" if after < 70 else "elevated" if loss > 0 else "nominal")
            rows.append(RefineryProjection(
                refinery_id=refinery.id, refinery=refinery.name,
                utilization_before_pct=refinery.utilization,
                utilization_after_pct=round(after, 1),
                throughput_loss_kbpd=round(loss, 1),
                inventory_days=refinery.inventory_days, status=status,
            ))
        return sorted(rows, key=lambda row: row.throughput_loss_kbpd, reverse=True)

    def _spr_schedule(
        self, release_kbpd: float, duration_days: int,
        procurement_plan: list[ProcurementOption], spot_eta_days: int,
    ) -> list[SprSiteSchedule]:
        if release_kbpd <= 0:
            return []
        feasible_etas = [option.eta_days for option in procurement_plan if option.feasible]
        arrival_day = min(feasible_etas + [spot_eta_days]) if feasible_etas else spot_eta_days
        taper_day = arrival_day if arrival_day <= duration_days else None
        draw_days = min(duration_days, max(0, arrival_day - 1))
        total_stored = self.net.spr_total_mmt or 1.0
        rows: list[SprSiteSchedule] = []
        for site in self.net.reserves:
            share = site.stored_mmt / total_stored
            rate = release_kbpd * share
            stored_kbbl = site.stored_mmt * 1_000_000 * self.net.demand.bbl_per_tonne / 1000
            sustainable = stored_kbbl / rate if rate else 0.0
            nearest = sorted(
                self.net.refineries,
                key=lambda refinery: math.hypot(
                    refinery.coords.lat - site.coords.lat,
                    refinery.coords.lon - site.coords.lon,
                ),
            )[:3]
            rows.append(SprSiteSchedule(
                site_id=site.id, site=site.name, release_kbpd=round(rate, 1),
                sustainable_days=round(sustainable, 1),
                projected_draw_mmt=round(
                    rate * draw_days * 1000 /
                    (1_000_000 * self.net.demand.bbl_per_tonne), 3,
                ),
                start_day=1, taper_day=taper_day,
                replenishment_from_day=arrival_day,
                served_refineries=[refinery.name for refinery in nearest],
                rationale=(
                    f"{share:.0%} of national stored SPR; meter until the first "
                    f"verified replacement arrival on day {arrival_day}."
                ),
            ))
        return rows

    # -- main ----------------------------------------------------------------
    def run(
        self,
        spec: ScenarioSpec,
        levers: ResponseLevers | None = None,
        operational: OperationalSnapshot | None = None,
    ) -> SimulationResult:
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

        affected = self._affected_corridors(spec)

        # ---- 1. gross supply disrupted ----------------------------------
        gap = 0.0
        for sup in net.suppliers:
            share_kbpd = sup.import_share * daily_imports
            corridor_fraction = affected.get(sup.corridor_id, 0.0)
            sanction_fraction = (1.0 if (sup.id in s.sanctioned_supplier_ids or sup.sanctioned)
                                 else s.supplier_disruption_fraction.get(sup.id, 0.0))
            # A cargo affected by both sanctions and a corridor closure is still
            # one cargo. Use the strongest shock instead of double-counting it.
            gap += share_kbpd * max(corridor_fraction, sanction_fraction)
        port_losses = dict(s.port_capacity_loss)
        for port_id in s.ports_offline:
            port_losses[port_id] = 1.0
        if port_losses:
            # Port and corridor shocks can constrain the same cargo.  Use the
            # stronger national bottleneck instead of double-counting barrels.
            port_cap = sum(
                p.crude_capacity_kbpd * max(0.0, min(1.0, port_losses.get(p.id, 0.0)))
                for p in net.ports
            )
            gap = max(gap, min(port_cap, daily_imports * 0.45))
            assumptions.append(
                f"Port constraints ({', '.join(sorted(port_losses))}) remove up to "
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
        for cid, block_fraction in affected.items():
            corr = net.corridor(cid)
            if corr and corr.reroute_corridor_id and lev.enable_reroute:
                corr_kbpd = sum(
                    sup.import_share * daily_imports
                    for sup in net.suppliers
                    if sup.corridor_id == cid
                ) * block_fraction
                rerouted += corr_kbpd
                transit_delay = max(transit_delay, corr.reroute_added_days)
                freight_premium = max(freight_premium, corr.reroute_cost_premium_pct)
                assumptions.append(
                    f"{corr.name} cargoes reroute via {corr.reroute_corridor_id} "
                    f"(+{corr.reroute_added_days:.0f} days, +{corr.reroute_cost_premium_pct:.0f}% freight)."
                )
        rerouted = round(min(rerouted, gap), 1)
        lost = gap - rerouted  # volume that must be replaced, not just delayed

        # ---- 3. replacement procurement, with option-specific ETAs --------
        procurement_plan = build_procurement_options(net, spec, lost, operational)
        replaced_spare = round(sum(
            option.volume_kbpd for option in procurement_plan if option.feasible
        ), 1)
        if s.opec_cut_kbpd:
            # The option planner already applies route/supplier constraints; an
            # OPEC cut further limits what can credibly be redirected to India.
            replaced_spare = round(replaced_spare * 0.4, 1)
            scale = 0.4
            procurement_plan = [
                option.model_copy(update={"volume_kbpd": round(option.volume_kbpd * scale, 1)})
                for option in procurement_plan
            ]
            assumptions.append("Procurement volumes cut to 40% under OPEC+ action.")
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
        moving_tankers = sum(operational.vessel_count_map().values()) if operational else 0
        spot_eta_days = 7 + (3 if operational and moving_tankers == 0 else 0)
        daily_balance, spr_consumed_mmt, spr_remaining_mmt, feasibility_warnings = self._daily_horizon(
            spec, gap, rerouted, procurement_plan, replaced_spot,
            desired_spr_release, transit_delay, spot_eta_days,
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
            "each replacement cargo begins only after its route-specific ETA."
        )
        late_volume = sum(option.volume_kbpd for option in procurement_plan
                          if option.feasible and not option.arrives_within_horizon)
        if late_volume:
            feasibility_warnings.append(
                f"{late_volume:,.0f} kbpd of contracted replacement arrives after the "
                f"{s.duration_days}-day disruption horizon."
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
        refinery_projections = self._refinery_projections(residual)

        # ---- 7. market + macro ------------------------------------------
        duration_factor = min(1.6, s.duration_days / 14)
        gap_pressure = 0.45 * (residual / daily_imports) if daily_imports else 0
        observed_brent = operational.market.brent_usd if operational else net.market.brent_usd
        observed_move = max(0.0, operational.market.change_pct / 100) if operational else 0.0
        brent_shock = max(s.market_shock_base, observed_move) * duration_factor + gap_pressure
        brent_proj = round(observed_brent * (1 + brent_shock), 1)
        brent_change_pct = round(brent_shock * 100, 1)

        d_brent = brent_proj - observed_brent
        retail_delta = d_brent * net.market.inr_usd / 159 * BBL_PER_LITRE_RETAIL_FACTOR
        diesel_proj = round(net.market.retail_diesel_inr_per_l + retail_delta, 1)
        petrol_proj = round(net.market.retail_petrol_inr_per_l + retail_delta, 1)

        inflation_bps = round(brent_change_pct * INFLATION_SENSITIVITY, 0)
        gdp_impact = round(-(brent_change_pct / 10) * GDP_SENSITIVITY, 2)
        diesel_output_loss = residual * 0.38
        power_sector_stress = round(min(
            100.0,
            (diesel_output_loss / max(1.0, base_thru * 0.38)) * 70
            + max(0.0, brent_change_pct) * 0.8,
        ), 1)
        spr_schedule = self._spr_schedule(
            spr_release, s.duration_days, procurement_plan,
            spot_eta_days if replaced_spot else s.duration_days + 1,
        )
        assumptions.append(
            "Power/fuel stress is a transparent proxy combining estimated diesel-output loss "
            "with observed/projected crude-price pressure; it is not a grid dispatch forecast."
        )
        if spr_schedule:
            assumptions.append(
                "SPR site rates are allocated by usable stored volume and tapered at the first "
                "modeled replacement-cargo arrival; terminal hydraulics remain an operator input."
            )

        # cost of disruption ≈ premium on rerouted/spot/spot-priced volume
        delivered_options = [option for option in procurement_plan
                             if option.feasible and option.arrives_within_horizon]
        delivered_volume = sum(option.volume_kbpd for option in delivered_options)
        weighted_landed = (sum(option.volume_kbpd * option.landed_premium_usd_bbl
                               for option in delivered_options) / delivered_volume
                           if delivered_volume else 0.0)
        spot_premium_avg = 3.0 + observed_move * 20
        est_daily_cost = round(
            (replaced_spot * 1000 * spot_premium_avg
             + delivered_volume * 1000 * weighted_landed
             + rerouted * 1000 * d_brent * 0.05) / 1_000_000,
            1,
        )

        # ---- 8. NESI recompute ------------------------------------------
        nesi_before = compute_nesi(net).value
        supply_avail = round(100 * (1 - residual / daily_imports), 1) if daily_imports else 100
        strongest_block = max(affected.values(), default=0.0)
        shipping_stab = 70.0 - (60.0 if affected else 0) * strongest_block
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
                       detail=f"{brent_change_pct:+.1f}% vs. observed ${observed_brent:.0f}."),
            ImpactLine(label="Diesel (retail)", value=diesel_proj, unit="INR/L",
                       detail=f"{retail_delta:+.1f} INR/L pass-through."),
            ImpactLine(label="Inflation", value=inflation_bps, unit="bps",
                       detail="Estimated CPI pressure."),
            ImpactLine(label="GDP Impact", value=gdp_impact, unit="%",
                       detail="Annualised, if sustained."),
            ImpactLine(label="Power/Fuel Stress", value=power_sector_stress, unit="%",
                       detail="Diesel-linked generation and backup-fuel stress proxy."),
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
            power_sector_stress_pct=power_sector_stress,
            transit_delay_days=transit_delay, freight_premium_pct=freight_premium,
            est_daily_cost_musd=est_daily_cost,
            nesi_before=nesi_before, nesi_after=nesi_after,
            headline=headline, assumptions=assumptions, impact_lines=impact_lines,
            daily_balance=daily_balance, spr_consumed_mmt=spr_consumed_mmt,
            spr_remaining_mmt=spr_remaining_mmt,
            feasibility_warnings=feasibility_warnings,
            procurement_plan=procurement_plan,
            refinery_projections=refinery_projections,
            spr_drawdown_plan=spr_schedule,
            replacement_arrived_by_horizon_kbpd=round(
                (daily_balance[-1].replacement_arrivals_kbpd if daily_balance else 0.0), 1),
            operational_snapshot_id=operational.id if operational else None,
            input_provenance=(operational.provenance if operational else {"model": "baseline"}),
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
