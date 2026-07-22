"""The six specialized council agents.

Each grounded reasoner derives its assessment from the simulation result, so
different scenarios genuinely produce different stances — and agents optimising
for different objectives (e.g. reserve preservation vs price stability) will
disagree. That disagreement is a feature the Decision Engine reconciles.
"""

from __future__ import annotations

from app.agents.base import AgentAssessment, BaseAgent, EvidenceItem
from app.agents.context import CouncilContext


def _clamp(v: float, lo: float = 5, hi: float = 98) -> float:
    return round(max(lo, min(hi, v)), 1)


# ---------------------------------------------------------------------------
class IntelligenceAgent(BaseAgent):
    id = "intelligence"
    name = "Intelligence Agent"
    role = "Geopolitical understanding & escalation probability"
    system_prompt = (
        "You are the Intelligence Agent. Assess geopolitical escalation risk to "
        "India's energy imports. Quantify likelihood and strategic consequence."
    )

    def reason(self, ctx: CouncilContext) -> AgentAssessment:
        s = ctx.sim
        summ = ctx.intel_summary
        threat = summ.get("threat_level", "elevated")
        flagged = summ.get("corridors_flagged", {})
        peak = summ.get("peak_risk_score", 50)
        escalating = threat in ("high", "critical") or s.residual_shortfall_kbpd > 0
        conf = _clamp(50 + peak * 0.4 + (10 if summ.get("is_live") else 0))
        stance = ("High escalation risk to Gulf supply" if escalating
                  else "Regional risk contained for now")
        return AgentAssessment(
            agent_id=self.id, agent_name=self.name, role=self.role,
            stance=stance,
            observations=[
                f"Threat level {threat}; peak event risk {peak:.0f}/100.",
                f"Corridors flagged: {', '.join(flagged) or 'none'}.",
                f"{summ.get('event_count', 0)} active events across sources.",
            ],
            reasoning=(
                f"Signal density points to a {threat} posture. With residual "
                f"shortfall of {s.residual_shortfall_kbpd:,.0f} kbpd, the event "
                "carries direct strategic consequence for import continuity."
            ),
            recommendation=(
                "Elevate monitoring on flagged corridors and pre-position "
                "diplomatic and naval options." if escalating else
                "Maintain watch; no immediate escalation trigger."
            ),
            concerns=["Escalation could compound across multiple chokepoints."]
            if len(flagged) > 1 else [],
            confidence=conf,
            evidence=[
                EvidenceItem(label="Threat level", detail=str(threat)),
                EvidenceItem(label="Peak risk score", detail=f"{peak:.0f}/100"),
            ],
            key_metrics={"threat_level": threat, "peak_risk": peak,
                         "corridors_flagged": len(flagged)},
        )


# ---------------------------------------------------------------------------
class MaritimeLogisticsAgent(BaseAgent):
    id = "maritime"
    name = "Maritime Logistics Agent"
    role = "Routes, ports, shipping & rerouting"
    system_prompt = (
        "You are the Maritime Logistics Agent. Evaluate rerouting feasibility, "
        "transit delay, freight cost, and port/corridor status."
    )

    def reason(self, ctx: CouncilContext) -> AgentAssessment:
        s = ctx.sim
        has_reroute = s.rerouted_kbpd > 0
        no_bypass = s.residual_shortfall_kbpd > 0 and s.rerouted_kbpd == 0
        conf = _clamp(78 - (18 if no_bypass else 0))
        if has_reroute:
            stance = f"Reroute {s.rerouted_kbpd:,.0f} kbpd via alternative corridor"
        elif no_bypass:
            stance = "No maritime bypass — volume must be replaced, not rerouted"
        else:
            stance = "Corridors stable; maintain current routing"
        return AgentAssessment(
            agent_id=self.id, agent_name=self.name, role=self.role,
            stance=stance,
            observations=[
                f"Reroutable volume: {s.rerouted_kbpd:,.0f} kbpd.",
                f"Added transit: {s.transit_delay_days:.0f} days; "
                f"freight premium {s.freight_premium_pct:.0f}%.",
                f"Stressed refineries: {', '.join(s.stressed_refineries) or 'none'}.",
            ],
            reasoning=(
                "Rerouting preserves supply at a time/cost penalty where a bypass "
                "exists; Gulf-origin volume behind a closed chokepoint has none and "
                "must be sourced elsewhere."
            ),
            recommendation=(
                "Book Cape-route tanker capacity now and secure war-risk insurance."
                if has_reroute else
                "Prioritise replacement sourcing; rerouting cannot close this gap."
                if no_bypass else "Hold routing; monitor congestion."
            ),
            concerns=["Tanker availability tightens as rerouting demand spikes."]
            if has_reroute else [],
            confidence=conf,
            evidence=[
                EvidenceItem(label="Rerouted", detail=f"{s.rerouted_kbpd:,.0f} kbpd"),
                EvidenceItem(label="Transit delay", detail=f"{s.transit_delay_days:.0f} days"),
            ],
            key_metrics={"rerouted_kbpd": s.rerouted_kbpd,
                         "transit_delay_days": s.transit_delay_days,
                         "freight_premium_pct": s.freight_premium_pct},
        )


# ---------------------------------------------------------------------------
class ProcurementAgent(BaseAgent):
    id = "procurement"
    name = "Procurement Agent"
    role = "Supplier optimization & alternative sourcing"
    system_prompt = (
        "You are the Procurement Agent, acting as a national oil company's head "
        "of procurement. Rank alternative crude sourcing by feasibility and cost."
    )

    def reason(self, ctx: CouncilContext) -> AgentAssessment:
        s = ctx.sim
        replaced = s.replaced_spare_kbpd + s.replaced_spot_kbpd
        insufficient = s.residual_shortfall_kbpd > 0
        conf = _clamp(72 - (insufficient * 12) + (s.replaced_spare_kbpd > 0) * 6)
        stance = ("Activate spare + spot; still short of demand" if insufficient
                  else "Spare capacity + spot fully cover the gap")
        return AgentAssessment(
            agent_id=self.id, agent_name=self.name, role=self.role,
            stance=stance,
            observations=[
                f"Spare-capacity replacement: {s.replaced_spare_kbpd:,.0f} kbpd.",
                f"Spot procurement: {s.replaced_spot_kbpd:,.0f} kbpd.",
                f"Uncovered after sourcing: {max(0, s.residual_shortfall_kbpd):,.0f} kbpd.",
            ],
            reasoning=(
                f"Diversified sourcing replaces {replaced:,.0f} kbpd. "
                + ("Remaining gap forces reliance on reserves and demand measures."
                   if insufficient else
                   "This restores balance without drawing down strategic reserves.")
            ),
            recommendation=(
                "Issue urgent tenders to Gulf/Atlantic spare holders and lock spot "
                "cargoes before premiums widen." if insufficient else
                "Execute diversified term+spot mix; avoid overpaying on spot."
            ),
            concerns=["Grade compatibility may limit some refineries' substitutes."],
            confidence=conf,
            evidence=[
                EvidenceItem(label="Spare replaced", detail=f"{s.replaced_spare_kbpd:,.0f} kbpd"),
                EvidenceItem(label="Spot", detail=f"{s.replaced_spot_kbpd:,.0f} kbpd"),
            ],
            key_metrics={"replaced_spare_kbpd": s.replaced_spare_kbpd,
                         "replaced_spot_kbpd": s.replaced_spot_kbpd,
                         "residual_kbpd": s.residual_shortfall_kbpd},
        )


# ---------------------------------------------------------------------------
class StrategicReserveAgent(BaseAgent):
    id = "reserve"
    name = "Strategic Reserve Agent"
    role = "SPR drawdown optimization"
    system_prompt = (
        "You are the Strategic Reserve Agent. Decide how much SPR to release and "
        "for how long, balancing immediate shortfall against disruption duration."
    )

    def reason(self, ctx: CouncilContext) -> AgentAssessment:
        s = ctx.sim
        short_event = s.duration_days <= 7
        gap_remains = s.residual_shortfall_kbpd > 0
        # tension: conserve for short shocks, release for gaps
        if gap_remains:
            stance = "Increase SPR release to close residual gap"
            rec = ("Raise release rate; residual shortfall justifies deeper draw "
                   "given coverage headroom.")
            conf = _clamp(70)
        elif short_event and s.spr_release_kbpd > 0:
            stance = "Conserve SPR — disruption too short to justify draw"
            rec = "Throttle release; a sub-week disruption rarely warrants drawdown."
            conf = _clamp(74)
        else:
            stance = "Current SPR posture is balanced"
            rec = "Hold release rate; reassess if duration extends."
            conf = _clamp(68)
        return AgentAssessment(
            agent_id=self.id, agent_name=self.name, role=self.role,
            stance=stance,
            observations=[
                f"Release rate: {s.spr_release_kbpd:,.0f} kbpd.",
                f"Sustainable ~{s.spr_days_remaining:.0f} days at that rate.",
                f"Disruption horizon: {s.duration_days} days.",
            ],
            reasoning=(
                "Reserves are a finite bridge, not a substitute for supply. Match "
                "the drawdown to disruption duration and the size of the unmet gap."
            ),
            recommendation=rec,
            concerns=["Over-releasing early leaves no buffer if the crisis extends."]
            if s.spr_release_kbpd > 400 else [],
            confidence=conf,
            evidence=[
                EvidenceItem(label="Release", detail=f"{s.spr_release_kbpd:,.0f} kbpd"),
                EvidenceItem(label="Coverage", detail=f"~{s.spr_days_remaining:.0f} days"),
            ],
            key_metrics={"spr_release_kbpd": s.spr_release_kbpd,
                         "spr_days_remaining": s.spr_days_remaining,
                         "duration_days": s.duration_days},
        )


# ---------------------------------------------------------------------------
class EconomicImpactAgent(BaseAgent):
    id = "economic"
    name = "Economic Impact Agent"
    role = "Inflation, GDP & downstream effects"
    system_prompt = (
        "You are the Economic Impact Agent. Quantify price, inflation and GDP "
        "consequences and advise on buffering measures."
    )

    def reason(self, ctx: CouncilContext) -> AgentAssessment:
        s = ctx.sim
        severe = s.brent_change_pct >= 15
        conf = _clamp(66 + min(20, s.brent_change_pct))
        stance = ("Material inflationary shock — buffer retail prices" if severe
                  else "Manageable price impact")
        return AgentAssessment(
            agent_id=self.id, agent_name=self.name, role=self.role,
            stance=stance,
            observations=[
                f"Brent {s.brent_change_pct:+.1f}% to ${s.brent_projected_usd:.0f}.",
                f"Diesel to ₹{s.diesel_projected_inr:.1f}/L.",
                f"Inflation +{s.inflation_bps:.0f} bps; GDP {s.gdp_impact_pct:.2f}%.",
            ],
            reasoning=(
                "Crude price transmits to freight, power and CPI. A sustained "
                f"{s.brent_change_pct:.0f}% Brent move meaningfully pressures the "
                "fiscal and inflation outlook."
            ),
            recommendation=(
                "Prepare excise/subsidy buffer and brief the Finance Ministry on "
                "pass-through options." if severe else
                "Monitor; no emergency fiscal action required yet."
            ),
            concerns=["Fiscal cost of shielding consumers rises with duration."]
            if severe else [],
            confidence=conf,
            evidence=[
                EvidenceItem(label="Brent", detail=f"${s.brent_projected_usd:.0f} ({s.brent_change_pct:+.1f}%)"),
                EvidenceItem(label="Inflation", detail=f"+{s.inflation_bps:.0f} bps"),
            ],
            key_metrics={"brent_change_pct": s.brent_change_pct,
                         "inflation_bps": s.inflation_bps,
                         "gdp_impact_pct": s.gdp_impact_pct},
        )


# ---------------------------------------------------------------------------
class PolicyAdvisorAgent(BaseAgent):
    id = "policy"
    name = "Policy Advisor Agent"
    role = "Executive recommendation & synthesis"
    system_prompt = (
        "You are the Policy Advisor Agent. Synthesise the council into a concise, "
        "actionable executive recommendation for national decision-makers."
    )

    def reason(self, ctx: CouncilContext) -> AgentAssessment:
        s = ctx.sim
        nesi = s.nesi_after.value
        critical = nesi < 50 or s.residual_shortfall_kbpd > 0
        conf = _clamp(64 + (10 if not critical else 0))
        stance = ("Coordinated national response required" if critical
                  else "Managed monitoring posture sufficient")
        return AgentAssessment(
            agent_id=self.id, agent_name=self.name, role=self.role,
            stance=stance,
            observations=[
                f"Security Index {s.nesi_before:.0f} → {nesi:.0f} ({s.nesi_after.band}).",
                f"Residual shortfall {s.residual_shortfall_kbpd:,.0f} kbpd.",
                f"Refinery utilisation {s.national_utilization_pct:.0f}%.",
            ],
            reasoning=(
                "The council's inputs converge on a resilience trajectory that "
                + ("demands coordinated cross-agency action." if critical else
                   "is currently absorbable with standard measures.")
            ),
            recommendation=(
                "Convene crisis response: pair replacement sourcing with a phased "
                "SPR release and a fiscal buffer; brief the Cabinet." if critical
                else "Sustain monitoring; ready contingency playbooks."
            ),
            concerns=["Agency disagreement on SPR vs sourcing must be reconciled fast."],
            confidence=conf,
            evidence=[
                EvidenceItem(label="NESI", detail=f"{s.nesi_before:.0f} → {nesi:.0f}"),
                EvidenceItem(label="Band", detail=s.nesi_after.band),
            ],
            key_metrics={"nesi_after": nesi, "residual_kbpd": s.residual_shortfall_kbpd},
        )


COUNCIL_AGENTS: list[BaseAgent] = [
    IntelligenceAgent(),
    MaritimeLogisticsAgent(),
    ProcurementAgent(),
    StrategicReserveAgent(),
    EconomicImpactAgent(),
    PolicyAdvisorAgent(),
]
