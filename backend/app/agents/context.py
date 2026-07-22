"""Grounded context shared by every council agent.

Bundles the scenario simulation (real numbers from the domain engine) with the
live intel feed summary, and renders a compact brief for the LLM. Because all
agents read the same grounded context, their evidence cites real figures.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.engine import SimulationResult


class CouncilContext(BaseModel):
    scenario_id: str
    scenario_name: str
    scenario_description: str
    sim: SimulationResult
    intel_summary: dict
    top_events: list[dict]           # compact event dicts (title, severity, corridors)
    retrieved_evidence: list[dict] = Field(default_factory=list)

    def brief(self) -> str:
        """Compact, factual brief handed to each agent's LLM prompt."""
        s = self.sim
        events = "\n".join(
            f"  - [{e.get('severity','?')}] {e.get('title','')} "
            f"(corridors: {', '.join(e.get('affected_corridors', []) or ['—'])})"
            for e in self.top_events[:6]
        )
        evidence = "\n".join(
            f"  - {item.get('publisher', 'Source')}: {item.get('title', '')} "
            f"({item.get('url', '')})"
            for item in self.retrieved_evidence[:4]
        )
        return f"""SCENARIO: {self.scenario_name}
{self.scenario_description}

SIMULATION (deterministic domain engine):
- Duration: {s.duration_days} days
- Gross supply gap: {s.supply_gap_kbpd:,.0f} kbpd
- Rerouted: {s.rerouted_kbpd:,.0f} kbpd | Spare-replaced: {s.replaced_spare_kbpd:,.0f} | Spot: {s.replaced_spot_kbpd:,.0f}
- SPR release: {s.spr_release_kbpd:,.0f} kbpd (sustainable ~{s.spr_days_remaining:.0f} days)
- Residual shortfall: {s.residual_shortfall_kbpd:,.0f} kbpd
- National refinery utilisation: {s.national_utilization_pct:.1f}%
- Stressed refineries: {', '.join(s.stressed_refineries) or 'none'}
- Brent: ${s.brent_projected_usd:.0f} ({s.brent_change_pct:+.1f}%) | Diesel: ₹{s.diesel_projected_inr:.1f}/L
- Inflation: {s.inflation_bps:.0f} bps | GDP impact: {s.gdp_impact_pct:.2f}%
- Transit delay: {s.transit_delay_days:.0f} days | Freight premium: {s.freight_premium_pct:.0f}%
- Security Index (NESI): {s.nesi_before:.0f} -> {s.nesi_after.value:.0f} ({s.nesi_after.band})

INTELLIGENCE FEED: threat={self.intel_summary.get('threat_level')}, \
events={self.intel_summary.get('event_count')}, \
corridors flagged={self.intel_summary.get('corridors_flagged')}
TOP EVENTS:
{events}
AUTHORITATIVE EVIDENCE:
{evidence or '  - No corpus evidence available.'}
"""
