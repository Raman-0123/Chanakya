"""AI Decision Engine — the 'Chief of Staff'.

Generates three candidate national response strategies, each a concrete set of
response levers RE-SIMULATED through the domain engine to get real projected
outcomes, then scores them across four objectives (continuity, resilience,
affordability, reserve preservation) and ranks them.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.engine import SimulationEngine
from app.domain.logistics import ProcurementOption, build_procurement_options
from app.domain.scenarios import ResponseLevers, ScenarioSpec
from app.operations.models import OperationalSnapshot

class EvidenceCitation(BaseModel):
    source: str
    event_id: str | None = None
    title: str
    confidence: float
    category: str = "baseline"


ProcurementAlternative = ProcurementOption


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
    optimization: dict = Field(default_factory=dict)


# objective weights
_W = {"continuity": 0.30, "resilience": 0.16, "affordability": 0.10,
      "reserve": 0.10, "feasibility": 0.14, "evidence": 0.05,
      "council_alignment": 0.15}


def _score(proj: StrategyProjection, daily_imports: float,
           alternatives: list[ProcurementAlternative], levers: ResponseLevers,
           target: ResponseLevers) -> dict[str, float]:
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
    feasible_volume = sum(a.volume_kbpd for a in alternatives
                          if a.feasible and a.arrives_within_horizon)
    required = max(1.0, proj.residual_shortfall_kbpd)
    feasibility = min(100.0, 55 + 45 * min(1.0, feasible_volume / required))
    evidenced = [a for a in alternatives if a.feasible]
    evidence = (sum(a.confidence for a in evidenced) / len(evidenced)
                if evidenced else 35.0)
    spr_distance = abs(levers.spr_release_pct - target.spr_release_pct)
    flag_penalty = (18 if levers.enable_reroute != target.enable_reroute else 0) + \
                   (18 if levers.enable_spot != target.enable_spot else 0)
    alignment = max(0.0, 100 - spr_distance * 1.25 - flag_penalty)

    return {
        "continuity": round(continuity, 1),
        "resilience": round(resilience, 1),
        "affordability": round(affordability, 1),
        "reserve": round(reserve, 1),
        "feasibility": round(feasibility, 1),
        "evidence": round(evidence, 1),
        "council_alignment": round(alignment, 1),
    }


def build_procurement_alternatives(
    engine: SimulationEngine, spec: ScenarioSpec, required_kbpd: float,
    operational: OperationalSnapshot | None = None,
) -> list[ProcurementAlternative]:
    return build_procurement_options(engine.net, spec, required_kbpd, operational)[:6]


def build_evidence_chain(
    spec: ScenarioSpec, alternatives: list[ProcurementAlternative],
    operational: OperationalSnapshot | None = None,
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
    # 5. The exact snapshot evidence used for this calculation.  This replaces
    # the old best-effort synchronous repository lookup, which was skipped while
    # the council event loop was running.
    if operational is not None:
        for event in operational.evidence_events[:4]:
            citations.append(EvidenceCitation(
                source=event.get("source", "Operational snapshot"),
                event_id=event.get("id"),
                title=event.get("title", "Current intelligence signal"),
                confidence=float(event.get("confidence", 60)),
                category="live_intelligence",
            ))
    # 6. Baseline data evidence
    citations.append(EvidenceCitation(
        source="CHANAKYA Baseline Network v1",
        title="Supplier capacities, refinery grades, port throughput from versioned domain model",
        confidence=95, category="baseline",
    ))
    return citations


def rank_strategies(
    engine: SimulationEngine, spec: ScenarioSpec, daily_imports: float,
    assessments: list | None = None,
    operational: OperationalSnapshot | None = None,
) -> list[StrategyOption]:
    target = _council_target(assessments or [], spec.default_levers)
    spr_levels = set(range(0, 101, 10))
    spr_levels.add(int(round(target.spr_release_pct / 5) * 5))
    candidates = [
        ResponseLevers(spr_release_pct=spr, enable_reroute=reroute, enable_spot=spot)
        for spr in sorted(spr_levels)
        for reroute in (False, True)
        for spot in (False, True)
    ]
    options: list[StrategyOption] = []
    for levers in candidates:
        r = engine.run(spec, levers, operational)
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
        alternatives = r.procurement_plan[:6]
        scores = _score(proj, daily_imports, alternatives, levers, target)
        total = round(sum(scores[k] * _W[k] for k in _W), 1)
        feasible_volume = sum(a.volume_kbpd for a in alternatives
                              if a.feasible and a.arrives_within_horizon)
        infeasibility = []
        if r.residual_shortfall_kbpd > 0 and feasible_volume <= 0:
            infeasibility.append("No feasible replacement cargo is available within the modeled network.")
        if r.feasibility_warnings:
            infeasibility.extend(r.feasibility_warnings)
        evidence_chain = build_evidence_chain(spec, alternatives, operational)
        sid = (f"response_spr{int(levers.spr_release_pct):03d}_"
               f"r{int(levers.enable_reroute)}_s{int(levers.enable_spot)}")
        title, thesis = _strategy_identity(levers, r)
        options.append(StrategyOption(
            id=sid, title=title, thesis=thesis, levers=levers,
            benefits=_benefits(levers, proj),
            tradeoffs=_tradeoffs(levers, proj),
            implementation_steps=_steps(levers, alternatives, r),
            projection=proj, scores=scores, score=total,
            confidence=round(min(95, 55 + total * 0.35), 1),
            procurement_alternatives=alternatives,
            evidence_chain=evidence_chain,
            feasible=not infeasibility,
            infeasibility_reasons=infeasibility,
            optimization={
                "method": "enumerated constraint search",
                "candidate_count": len(candidates),
                "operational_snapshot_id": operational.id if operational else None,
                "council_target": target.model_dump(),
                "council_alignment": scores["council_alignment"],
            },
        ))

    options.sort(key=lambda o: (o.feasible, o.score), reverse=True)
    # Return three materially distinct plans rather than three labels over almost
    # identical settings.
    selected: list[StrategyOption] = []
    for option in options:
        if not selected or all(
            abs(option.levers.spr_release_pct - chosen.levers.spr_release_pct) >= 15
            or option.levers.enable_reroute != chosen.levers.enable_reroute
            or option.levers.enable_spot != chosen.levers.enable_spot
            for chosen in selected
        ):
            selected.append(option)
        if len(selected) == 3:
            break
    if len(selected) < 3:
        remaining_options = [option for option in options if option not in selected]
        selected.extend(remaining_options[:3 - len(selected)])
    for i, o in enumerate(selected):
        o.rank = i + 1
    return selected


def _benefits(levers: ResponseLevers, p: StrategyProjection) -> list[str]:
    common = [f"Refinery utilisation held at {p.national_utilization_pct:.0f}%.",
              f"Security Index projected at {p.nesi_after:.0f}."]
    if levers.spr_release_pct >= 60:
        return ["Fastest closure of the physical supply gap.",
                f"Residual shortfall cut to {p.residual_shortfall_kbpd:,.0f} kbpd."] + common
    if levers.enable_reroute and levers.enable_spot:
        return ["Balances supply continuity with reserve preservation.",
                "Limits fiscal and reserve exposure."] + common
    return ["Maximum strategic-reserve preservation.",
            f"Reserve draw minimised to {p.spr_release_kbpd:,.0f} kbpd."] + common


def _tradeoffs(levers: ResponseLevers, p: StrategyProjection) -> list[str]:
    if levers.spr_release_pct >= 60:
        return [f"Heavy SPR draw ({p.spr_release_kbpd:,.0f} kbpd) erodes buffer.",
                "Vulnerable if the disruption extends beyond forecast."]
    if levers.enable_reroute and levers.enable_spot:
        return [f"Leaves {p.residual_shortfall_kbpd:,.0f} kbpd residual if spare is thin.",
                "Exposed to spot-price spikes."]
    return [f"Largest residual shortfall ({p.residual_shortfall_kbpd:,.0f} kbpd).",
            f"Higher price pass-through (Brent {p.brent_change_pct:+.0f}%)."]


def _steps(
    levers: ResponseLevers,
    alternatives: list[ProcurementAlternative],
    result,
) -> list[str]:
    base = ["Convene inter-ministerial crisis cell.",
            "Notify IOCL / BPCL / HPCL procurement desks."]
    steps = list(base)
    for option in [a for a in alternatives if a.feasible][:3]:
        timing = "within horizon" if option.arrives_within_horizon else "replenishment phase"
        steps.append(
            f"Tender {option.volume_kbpd:,.0f} kbpd {option.crude_grade} from "
            f"{option.supplier} via {option.route}; ETA {option.eta_days} days, "
            f"landed premium +${option.landed_premium_usd_bbl:.1f}/bbl ({timing})."
        )
    if levers.spr_release_pct > 0:
        steps.append(
            f"Authorise a metered SPR draw up to {result.spr_release_kbpd:,.0f} kbpd; "
            "record daily site inventory and stop conditions."
        )
    if levers.enable_reroute and result.rerouted_kbpd > 0:
        steps.append(
            f"Secure tonnage for {result.rerouted_kbpd:,.0f} kbpd of rerouted cargo "
            f"with {result.transit_delay_days:.0f}-day added transit."
        )
    if not levers.enable_spot:
        steps.append("Hold spot buying; pre-authorise only if the residual gap breaches threshold.")
    return steps


def _council_target(assessments: list, fallback: ResponseLevers) -> ResponseLevers:
    proposed = [(getattr(item, "proposed_levers", None),
                 max(1.0, float(getattr(item, "confidence", 60)))) for item in assessments]
    proposed = [(lever, weight) for lever, weight in proposed if lever is not None]
    if not proposed:
        return fallback
    total = sum(weight for _, weight in proposed)
    spr = sum(lever.spr_release_pct * weight for lever, weight in proposed) / total
    reroute = sum(weight for lever, weight in proposed if lever.enable_reroute) >= total / 2
    spot = sum(weight for lever, weight in proposed if lever.enable_spot) >= total / 2
    return ResponseLevers(spr_release_pct=round(spr / 5) * 5,
                          enable_reroute=reroute, enable_spot=spot)


def _strategy_identity(levers: ResponseLevers, result) -> tuple[str, str]:
    if levers.spr_release_pct >= 60:
        return (
            "Accelerated Reserve Bridge",
            "Use a high but bounded SPR release while verified replacement cargoes travel.",
        )
    if levers.enable_reroute and levers.enable_spot:
        return (
            "Adaptive Diversification",
            "Combine feasible route diversion, grade-compatible tenders and a measured reserve bridge.",
        )
    if levers.spr_release_pct <= 20:
        return (
            "Reserve Conservation",
            "Preserve strategic inventory and accept tightly managed demand or run-rate reductions.",
        )
    return (
        "Balanced Continuity",
        f"Balance a {levers.spr_release_pct:.0f}% reserve posture against verified cargo arrivals.",
    )
