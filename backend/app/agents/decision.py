"""AI Decision Engine — the 'Chief of Staff'.

Generates three candidate national response strategies, each a concrete set of
response levers RE-SIMULATED through the domain engine to get real projected
outcomes, then scores them across four objectives (continuity, resilience,
affordability, reserve preservation) and ranks them.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.engine import SimulationEngine
from app.domain.scenarios import ResponseLevers, ScenarioSpec
from app.db import get_repositories
from app.core.logging import get_logger

log = get_logger("agents.decision")


class EvidenceCitation(BaseModel):
    source: str
    event_id: str | None = None
    title: str
    confidence: float
    category: str = "baseline"


class ProcurementAlternative(BaseModel):
    supplier_id: str
    supplier: str
    crude_grade: str
    compatible_refineries: list[str] = Field(default_factory=list)
    volume_kbpd: float
    route: str
    eta_days: int
    transit_delay_days: float
    estimated_premium_usd_bbl: float
    capacity_constraint: str
    confidence: float
    feasible: bool
    evidence: list[str] = Field(default_factory=list)


class StrategyProjection(BaseModel):
    residual_shortfall_kbpd: float
    national_utilization_pct: float
    brent_change_pct: float
    diesel_projected_inr: float
    spr_release_kbpd: float
    spr_days_remaining: float
    nesi_after: float
    est_daily_cost_musd: float


class StrategyOption(BaseModel):
    id: str
    title: str
    thesis: str
    levers: ResponseLevers
    benefits: list[str] = Field(default_factory=list)
    tradeoffs: list[str] = Field(default_factory=list)
    implementation_steps: list[str] = Field(default_factory=list)
    projection: StrategyProjection
    scores: dict[str, float]
    score: float
    confidence: float
    rank: int = 0
    procurement_alternatives: list[ProcurementAlternative] = Field(default_factory=list)
    evidence_chain: list[EvidenceCitation] = Field(default_factory=list)
    feasible: bool = True
    infeasibility_reasons: list[str] = Field(default_factory=list)


# objective weights
_W = {"continuity": 0.35, "resilience": 0.20, "affordability": 0.12,
      "reserve": 0.13, "feasibility": 0.15, "evidence": 0.05}

# lever presets — three doctrines
_PRESETS = [
    ("reserve_led", "Reserve-Led Stabilization",
     "Bridge the shortfall aggressively with SPR while sourcing catches up.",
     ResponseLevers(spr_release_pct=75, enable_reroute=True, enable_spot=True)),
    ("diversified", "Market Diversification",
     "Lean on spare capacity, spot cargoes and rerouting; use SPR sparingly.",
     ResponseLevers(spr_release_pct=30, enable_reroute=True, enable_spot=True)),
    ("measured", "Measured Conservation",
     "Preserve reserves; absorb via rerouting and demand discipline.",
     ResponseLevers(spr_release_pct=10, enable_reroute=True, enable_spot=True)),
]


def _score(proj: StrategyProjection, daily_imports: float,
           alternatives: list[ProcurementAlternative]) -> dict[str, float]:
    # Continuity is driven by the physical residual shortfall — an unmet gap is
    # penalised ~3x its import share, so a strategy that starves refineries can
    # never rank well no matter how many reserves it preserves.
    residual_ratio = proj.residual_shortfall_kbpd / daily_imports if daily_imports else 0
    continuity = max(0.0, 100 - residual_ratio * 300)

    resilience = proj.nesi_after
    affordability = max(0.0, 100 - proj.brent_change_pct * 2.2)

    # Reserve preservation only counts when supply is actually secure — hoarding
    # SPR while short is a false economy, so gate it by the residual ratio.
    reserve_raw = max(0.0, 100 - proj.spr_release_kbpd / 9)
    reserve = reserve_raw * max(0.0, 1 - 2 * residual_ratio)
    feasible_volume = sum(a.volume_kbpd for a in alternatives if a.feasible)
    required = max(1.0, proj.residual_shortfall_kbpd)
    feasibility = min(100.0, 55 + 45 * min(1.0, feasible_volume / required))
    evidence = (sum(a.confidence for a in alternatives) / len(alternatives)
                if alternatives else 45.0)

    return {
        "continuity": round(continuity, 1),
        "resilience": round(resilience, 1),
        "affordability": round(affordability, 1),
        "reserve": round(reserve, 1),
        "feasibility": round(feasibility, 1),
        "evidence": round(evidence, 1),
    }


def build_procurement_alternatives(
    engine: SimulationEngine, spec: ScenarioSpec, required_kbpd: float,
) -> list[ProcurementAlternative]:
    affected = {spec.shock.corridor_id} if spec.shock.corridor_id else set()
    sanctioned = set(spec.shock.sanctioned_supplier_ids)
    alternatives: list[ProcurementAlternative] = []
    remaining = max(required_kbpd, engine.net.daily_crude_imports_kbpd * 0.05)
    for supplier in sorted(engine.net.suppliers,
                           key=lambda s: (s.corridor_id in affected,
                                          -s.spare_capacity_kbpd,
                                          s.spot_premium_usd)):
        corridor = engine.net.corridor(supplier.corridor_id)
        route_blocked = supplier.corridor_id in affected
        is_sanctioned = supplier.id in sanctioned or supplier.sanctioned
        compatible = [
            refinery for refinery in engine.net.refineries
            if (refinery.preferred_grade == supplier.grade or
                supplier.grade.value == "medium_sour" or
                refinery.preferred_grade.value == "medium_sour")
        ]
        compatible_capacity = sum(refinery.nameplate_kbpd for refinery in compatible)
        receiving_port_ids = {port_id for refinery in compatible for port_id in refinery.port_ids}
        receiving_capacity = sum(
            port.crude_capacity_kbpd for port in engine.net.ports
            if port.id in receiving_port_ids and port.id not in spec.shock.ports_offline
        )
        volume = min(supplier.spare_capacity_kbpd, remaining,
                     compatible_capacity, receiving_capacity)
        feasible = bool(volume > 0 and compatible and not route_blocked and not is_sanctioned)
        if feasible:
            remaining = max(0.0, remaining - volume)
        reasons = []
        if route_blocked:
            reasons.append("route disrupted")
        if is_sanctioned:
            reasons.append("sanctions constraint")
        if not compatible:
            reasons.append("no grade-compatible refinery")
        alternatives.append(ProcurementAlternative(
            supplier_id=supplier.id, supplier=supplier.country,
            crude_grade=supplier.grade.value,
            compatible_refineries=[refinery.name for refinery in compatible[:6]],
            volume_kbpd=round(volume, 1),
            route=corridor.name if corridor else supplier.corridor_id,
            eta_days=round(corridor.base_transit_days if corridor else 14),
            transit_delay_days=0.0,
            estimated_premium_usd_bbl=supplier.spot_premium_usd,
            capacity_constraint=("; ".join(reasons) if reasons else
                                 f"Supplier {supplier.spare_capacity_kbpd:,.0f}; "
                                 f"compatible refining {compatible_capacity:,.0f}; "
                                 f"receiving ports {receiving_capacity:,.0f} kbpd"),
            confidence=round(min(92, supplier.reliability * (0.75 if feasible else 0.45)), 1),
            feasible=feasible,
            evidence=[
                "Supplier capacity and grade from CHANAKYA versioned baseline.",
                "Route feasibility evaluated against the active scenario shock.",
            ],
        ))
    alternatives.sort(key=lambda item: (not item.feasible, -item.confidence,
                                        item.estimated_premium_usd_bbl))
    return alternatives[:6]


def build_evidence_chain(
    spec: ScenarioSpec, alternatives: list[ProcurementAlternative],
) -> list[EvidenceCitation]:
    """Build evidence citations linking a strategy to its supporting data.

    Collects from: scenario definition, baseline network, active events
    (via repository), and procurement feasibility analysis.
    """
    citations: list[EvidenceCitation] = []
    # 1. Scenario definition itself is evidence
    citations.append(EvidenceCitation(
        source="CHANAKYA Scenario Engine",
        title=f"Scenario: {spec.name} — {spec.description[:80]}",
        confidence=95, category="scenario",
    ))
    # 2. Corridor disruption evidence
    if spec.shock.corridor_id:
        citations.append(EvidenceCitation(
            source="Ontology / Corridor Network",
            title=f"Disrupted corridor: {spec.shock.corridor_id} "
                  f"({spec.shock.block_fraction*100:.0f}% volume loss)",
            confidence=92, category="geopolitical",
        ))
    # 3. Sanctioned suppliers
    for sid in spec.shock.sanctioned_supplier_ids:
        citations.append(EvidenceCitation(
            source="OpenSanctions / OFAC",
            title=f"Supplier {sid} under sanctions constraint",
            confidence=88, category="sanctions",
        ))
    # 4. Procurement alternative feasibility
    feasible_alts = [a for a in alternatives if a.feasible]
    if feasible_alts:
        top = feasible_alts[0]
        citations.append(EvidenceCitation(
            source="Procurement Analysis",
            title=f"Top replacement: {top.supplier} ({top.crude_grade}) "
                  f"via {top.route} — {top.volume_kbpd:.0f} kbpd @ +${top.estimated_premium_usd_bbl:.1f}/bbl",
            confidence=top.confidence, category="procurement",
        ))
    # 5. Try to pull recent events from the repository (non-blocking)
    try:
        import asyncio
        repo = get_repositories()
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're already in an async context; can't await here,
            # but rank_strategies is sync. Add baseline evidence instead.
            pass
        else:
            events = loop.run_until_complete(repo.list_events(limit=5))
            for evt in events[:3]:
                citations.append(EvidenceCitation(
                    source=evt.get("source", "Intelligence Feed"),
                    event_id=evt.get("id"),
                    title=evt.get("title", "Live intelligence event"),
                    confidence=evt.get("confidence", 60),
                    category=evt.get("category", "geopolitical"),
                ))
    except Exception:  # noqa: BLE001
        pass
    # 6. Baseline data evidence
    citations.append(EvidenceCitation(
        source="CHANAKYA Baseline Network v1",
        title="Supplier capacities, refinery grades, port throughput from versioned domain model",
        confidence=95, category="baseline",
    ))
    return citations


def rank_strategies(
    engine: SimulationEngine, spec: ScenarioSpec, daily_imports: float
) -> list[StrategyOption]:
    options: list[StrategyOption] = []
    for sid, title, thesis, levers in _PRESETS:
        r = engine.run(spec, levers)
        proj = StrategyProjection(
            residual_shortfall_kbpd=r.residual_shortfall_kbpd,
            national_utilization_pct=r.national_utilization_pct,
            brent_change_pct=r.brent_change_pct,
            diesel_projected_inr=r.diesel_projected_inr,
            spr_release_kbpd=r.spr_release_kbpd,
            spr_days_remaining=r.spr_days_remaining,
            nesi_after=r.nesi_after.value,
            est_daily_cost_musd=r.est_daily_cost_musd,
        )
        alternatives = build_procurement_alternatives(engine, spec, r.supply_gap_kbpd)
        scores = _score(proj, daily_imports, alternatives)
        total = round(sum(scores[k] * _W[k] for k in _W), 1)
        feasible_volume = sum(a.volume_kbpd for a in alternatives if a.feasible)
        infeasibility = []
        if r.residual_shortfall_kbpd > 0 and feasible_volume <= 0:
            infeasibility.append("No feasible replacement cargo is available within the modeled network.")
        if r.feasibility_warnings:
            infeasibility.extend(r.feasibility_warnings)
        evidence_chain = build_evidence_chain(spec, alternatives)
        options.append(StrategyOption(
            id=sid, title=title, thesis=thesis, levers=levers,
            benefits=_benefits(sid, proj),
            tradeoffs=_tradeoffs(sid, proj),
            implementation_steps=_steps(sid),
            projection=proj, scores=scores, score=total,
            confidence=round(min(95, 55 + total * 0.35), 1),
            procurement_alternatives=alternatives,
            evidence_chain=evidence_chain,
            feasible=not infeasibility,
            infeasibility_reasons=infeasibility,
        ))

    options.sort(key=lambda o: (o.feasible, o.score), reverse=True)
    for i, o in enumerate(options):
        o.rank = i + 1
    return options


def _benefits(sid: str, p: StrategyProjection) -> list[str]:
    common = [f"Refinery utilisation held at {p.national_utilization_pct:.0f}%.",
              f"Security Index projected at {p.nesi_after:.0f}."]
    if sid == "reserve_led":
        return ["Fastest closure of the physical supply gap.",
                f"Residual shortfall cut to {p.residual_shortfall_kbpd:,.0f} kbpd."] + common
    if sid == "diversified":
        return ["Balances supply continuity with reserve preservation.",
                "Limits fiscal and reserve exposure."] + common
    return ["Maximum strategic-reserve preservation.",
            f"Reserve draw minimised to {p.spr_release_kbpd:,.0f} kbpd."] + common


def _tradeoffs(sid: str, p: StrategyProjection) -> list[str]:
    if sid == "reserve_led":
        return [f"Heavy SPR draw ({p.spr_release_kbpd:,.0f} kbpd) erodes buffer.",
                "Vulnerable if the disruption extends beyond forecast."]
    if sid == "diversified":
        return [f"Leaves {p.residual_shortfall_kbpd:,.0f} kbpd residual if spare is thin.",
                "Exposed to spot-price spikes."]
    return [f"Largest residual shortfall ({p.residual_shortfall_kbpd:,.0f} kbpd).",
            f"Higher price pass-through (Brent {p.brent_change_pct:+.0f}%)."]


def _steps(sid: str) -> list[str]:
    base = ["Convene inter-ministerial crisis cell.",
            "Notify IOCL / BPCL / HPCL procurement desks."]
    if sid == "reserve_led":
        return base + ["Authorise phased SPR drawdown from Vizag/Mangalore/Padur.",
                       "Sequence replacement cargoes to refill behind the draw."]
    if sid == "diversified":
        return base + ["Issue urgent spot tenders to Gulf/Atlantic spare holders.",
                       "Reserve Cape-route tanker capacity + war-risk cover."]
    return base + ["Hold SPR; issue demand-management advisory.",
                   "Stage contingency SPR authorisation if duration extends."]
