"""Agent contract + base class with LLM-or-grounded execution."""

from __future__ import annotations

import abc

from pydantic import BaseModel, Field

from app.agents.context import CouncilContext
from app.core.logging import get_logger
from app.llm import LLMMessage, Role
from app.llm.router import get_llm_router

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
        return self._attach_corpus_evidence(self.reason(ctx), ctx)

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
            "of 1-3 short strings), confidence (number 0-100). Ground every claim "
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
        )

    @abc.abstractmethod
    def reason(self, ctx: CouncilContext) -> AgentAssessment:
        """Deterministic, simulation-grounded reasoning (LLM-free fallback)."""
