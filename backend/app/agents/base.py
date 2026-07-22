"""Agent contract + base class with LLM-or-grounded execution."""

from __future__ import annotations

import abc

from pydantic import BaseModel, Field

from app.agents.context import CouncilContext
from app.core.logging import get_logger
from app.llm import LLMMessage, Role
from app.llm.router import get_llm_router
from app.domain.scenarios import ResponseLevers

log = get_logger("agents")


class EvidenceItem(BaseModel):
    label: str
    detail: str
    url: str | None = None
    publisher: str | None = None


class AgentAssessment(BaseModel):
    agent_id: str
    agent_name: str
    role: str
    stance: str                       # one-line position (enables disagreement view)
    observations: list[str] = Field(default_factory=list)
    reasoning: str = ""
    recommendation: str = ""
    concerns: list[str] = Field(default_factory=list)
    confidence: float = 60.0
    evidence: list[EvidenceItem] = Field(default_factory=list)
    key_metrics: dict[str, float | str] = Field(default_factory=dict)
    reasoning_mode: str = "grounded"  # "llm" | "grounded"
    proposed_levers: ResponseLevers | None = None
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_latency_ms: int | None = None


class BaseAgent(abc.ABC):
    id: str
    name: str
    role: str
    system_prompt: str

    async def run(self, ctx: CouncilContext) -> AgentAssessment:
        router = get_llm_router()
        if router.available:
            try:
                result = await self._run_llm(ctx, router)
                return self._attach_corpus_evidence(result, ctx)
            except Exception as exc:  # noqa: BLE001
                log.warning("agent.llm_failed", agent=self.id, error=str(exc))
        result = self.reason(ctx)
        result.proposed_levers = result.proposed_levers or self._grounded_proposal(ctx)
        return self._attach_corpus_evidence(result, ctx)

    @staticmethod
    def _attach_corpus_evidence(result: AgentAssessment,
                                ctx: CouncilContext) -> AgentAssessment:
        for item in ctx.retrieved_evidence[:2]:
            result.evidence.append(EvidenceItem(
                label=item.get("title", "Authoritative source"),
                detail=item.get("section", item.get("publisher", "Evidence corpus")),
                url=item.get("url"), publisher=item.get("publisher"),
            ))
        return result

    async def _run_llm(self, ctx: CouncilContext, router) -> AgentAssessment:
        prompt = (
            f"{self.system_prompt}\n\n{ctx.brief()}\n\n"
            "Respond as STRICT JSON with keys: stance (string, <=12 words), "
            "observations (array of 2-4 short strings), reasoning (string, 2-3 "
            "sentences), recommendation (string, 1-2 sentences), concerns (array "
            "of 1-3 short strings), confidence (number 0-100), spr_release_pct "
            "(number 0-100), enable_reroute (boolean), enable_spot (boolean). "
            "Ground every claim "
            "in the numbers above. Do not invent figures."
        )
        data = await router.complete_json(
            [
                LLMMessage(role=Role.SYSTEM, content="You are a precise national-security analyst. Output JSON only."),
                LLMMessage(role=Role.USER, content=prompt),
            ],
            temperature=0.5,
            max_tokens=700,
        )
        base = self.reason(ctx)  # grounded evidence + metrics as the backbone
        fallback_levers = base.proposed_levers or self._grounded_proposal(ctx)
        try:
            proposed = ResponseLevers(
                spr_release_pct=data.get("spr_release_pct", fallback_levers.spr_release_pct),
                enable_reroute=data.get("enable_reroute", fallback_levers.enable_reroute),
                enable_spot=data.get("enable_spot", fallback_levers.enable_spot),
            )
        except Exception:  # malformed LLM control values never escape validation
            proposed = fallback_levers
        meta = data.get("_llm_meta", {})
        return AgentAssessment(
            agent_id=self.id, agent_name=self.name, role=self.role,
            stance=str(data.get("stance", base.stance))[:120],
            observations=[str(o) for o in data.get("observations", base.observations)][:4],
            reasoning=str(data.get("reasoning", base.reasoning)),
            recommendation=str(data.get("recommendation", base.recommendation)),
            concerns=[str(c) for c in data.get("concerns", base.concerns)][:3],
            confidence=float(data.get("confidence", base.confidence)),
            evidence=base.evidence,
            key_metrics=base.key_metrics,
            reasoning_mode="llm",
            proposed_levers=proposed,
            llm_provider=meta.get("provider"), llm_model=meta.get("model"),
            llm_latency_ms=meta.get("latency_ms"),
        )

    def _grounded_proposal(self, ctx: CouncilContext) -> ResponseLevers:
        """Typed action proposal consumed by the optimization node.

        This is also the safe fallback when an LLM provider is unavailable or
        emits invalid control values.
        """
        sim = ctx.sim
        residual_pct = min(100.0, 100 * sim.residual_shortfall_kbpd / 900.0)
        if self.id == "reserve":
            spr = max(10.0, min(100.0, residual_pct + 20))
        elif self.id == "economic":
            spr = 55.0 if sim.brent_change_pct >= 15 else 25.0
        elif self.id == "intelligence":
            threat = ctx.intel_summary.get("threat_level", "nominal")
            spr = {"critical": 55.0, "high": 45.0,
                   "elevated": 25.0}.get(threat, 10.0)
        elif self.id == "procurement":
            spr = 35.0 if sim.residual_shortfall_kbpd > 0 else 15.0
        elif self.id == "maritime":
            spr = 25.0
        else:
            spr = 45.0 if sim.residual_shortfall_kbpd > 0 else 20.0
        return ResponseLevers(
            spr_release_pct=spr,
            enable_reroute=sim.rerouted_kbpd > 0 or sim.supply_gap_kbpd > 0,
            enable_spot=sim.residual_shortfall_kbpd > 0 or self.id in {"procurement", "policy"},
        )

    @abc.abstractmethod
    def reason(self, ctx: CouncilContext) -> AgentAssessment:
        """Deterministic, simulation-grounded reasoning (LLM-free fallback)."""
