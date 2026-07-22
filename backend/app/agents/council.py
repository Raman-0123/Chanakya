"""LangGraph council: graph-grounded specialists -> reconciliation -> decision."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import operator
import time
from typing import Annotated, TypedDict
from uuid import uuid4

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from app.agents.base import AgentAssessment
from app.agents.context import CouncilContext
from app.agents.decision import StrategyOption, rank_strategies
from app.agents.roster import COUNCIL_AGENTS
from app.core.logging import get_logger
from app.db import get_repositories
from app.domain import SimulationEngine, build_energy_network
from app.domain.scenarios import ResponseLevers, ScenarioSpec, get_scenario
from app.ingestion.models import SourceKind
from app.rag import evidence_store

log = get_logger("agents.council")


class Disagreement(BaseModel):
    topic: str
    positions: list[dict]


class WorkflowStep(BaseModel):
    node: str
    label: str
    started_at: str
    completed_at: str
    duration_ms: int
    status: str = "completed"
    outputs_summary: str = ""


class CouncilResult(BaseModel):
    scenario_id: str
    scenario_name: str
    assessments: list[AgentAssessment]
    strategies: list[StrategyOption]
    disagreements: list[Disagreement]
    consensus_confidence: float
    reasoning_mode: str
    recommended_strategy_id: str
    workflow_run_id: str
    workflow_trace: list[WorkflowStep] = Field(default_factory=list)
    mission_id: str | None = None
    schema_version: str = "1.0"
    provenance: dict = Field(default_factory=dict)


class CouncilState(TypedDict, total=False):
    context: CouncilContext
    spec: ScenarioSpec
    assessments: Annotated[list[AgentAssessment], operator.add]
    disagreements: list[Disagreement]
    strategies: list[StrategyOption]
    workflow_trace: Annotated[list[WorkflowStep], operator.add]


class Council:
    def __init__(self):
        self._net = build_energy_network()
        self._engine = SimulationEngine(self._net)
        self._graph = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(CouncilState)

        async def chief(state: CouncilState) -> dict:
            step = WorkflowStep(
                node="chief", label="Chief Coordinator",
                started_at=datetime.now(timezone.utc).isoformat(),
                completed_at=datetime.now(timezone.utc).isoformat(),
                duration_ms=0, status="completed",
                outputs_summary="Distributed context to specialist agents.",
            )
            return {"workflow_trace": [step]}

        graph.add_node("chief", chief)
        agent_nodes: list[str] = []
        for agent in COUNCIL_AGENTS:
            node_name = f"specialist_{agent.id}"
            agent_nodes.append(node_name)

            async def run_specialist(state: CouncilState, selected=agent) -> dict:
                t0 = time.monotonic()
                started = datetime.now(timezone.utc).isoformat()
                assessment = await selected.run(state["context"])
                elapsed = int((time.monotonic() - t0) * 1000)
                step = WorkflowStep(
                    node=f"specialist_{selected.id}", label=selected.name,
                    started_at=started,
                    completed_at=datetime.now(timezone.utc).isoformat(),
                    duration_ms=elapsed, status="completed",
                    outputs_summary=f"{assessment.stance} (confidence {assessment.confidence:.0f}%)",
                )
                return {"assessments": [assessment], "workflow_trace": [step]}

            graph.add_node(node_name, run_specialist)

        async def reconcile(state: CouncilState) -> dict:
            t0 = time.monotonic()
            started = datetime.now(timezone.utc).isoformat()
            disagreements = _detect_disagreements(state["assessments"])
            elapsed = int((time.monotonic() - t0) * 1000)
            step = WorkflowStep(
                node="reconcile", label="Reconciliation",
                started_at=started,
                completed_at=datetime.now(timezone.utc).isoformat(),
                duration_ms=elapsed, status="completed",
                outputs_summary=f"{len(disagreements)} disagreements detected.",
            )
            return {"disagreements": disagreements, "workflow_trace": [step]}

        async def decide(state: CouncilState) -> dict:
            t0 = time.monotonic()
            started = datetime.now(timezone.utc).isoformat()
            strategies = rank_strategies(
                self._engine, state["spec"], round(self._net.daily_crude_imports_kbpd, 1)
            )
            elapsed = int((time.monotonic() - t0) * 1000)
            step = WorkflowStep(
                node="decision", label="Decision Engine",
                started_at=started,
                completed_at=datetime.now(timezone.utc).isoformat(),
                duration_ms=elapsed, status="completed",
                outputs_summary=f"{len(strategies)} strategies ranked. Top: {strategies[0].title if strategies else 'none'}.",
            )
            return {"strategies": strategies, "workflow_trace": [step]}

        graph.add_node("reconcile", reconcile)
        graph.add_node("decision", decide)
        graph.add_edge(START, "chief")
        for node_name in agent_nodes:
            graph.add_edge("chief", node_name)
        graph.add_edge(agent_nodes, "reconcile")
        graph.add_edge("reconcile", "decision")
        graph.add_edge("decision", END)
        return graph.compile(checkpointer=MemorySaver())

    async def _build_context(
        self, spec: ScenarioSpec, levers: ResponseLevers | None
    ) -> CouncilContext:
        sim = self._engine.run(spec, levers)
        rows = await get_repositories().list_events(limit=100)
        severity = Counter(row.get("severity", "nominal") for row in rows)
        corridors = Counter(c for row in rows for c in row.get("affected_corridors", []))
        threat = ("critical" if severity.get("critical") else
                  "high" if severity.get("high") else
                  "elevated" if severity.get("elevated") else "nominal")
        provenance = Counter(row.get("provenance", "unavailable") for row in rows)
        summary = {
            "threat_level": threat, "event_count": len(rows),
            "corridors_flagged": dict(corridors),
            "peak_risk_score": max((row.get("risk_score", 0) for row in rows), default=0),
            "is_live": bool(provenance.get(SourceKind.LIVE.value)),
            "provenance": dict(provenance),
        }
        top = [{"title": row.get("title"), "severity": row.get("severity"),
                "affected_corridors": row.get("affected_corridors", []),
                "source": row.get("source"), "source_url": row.get("source_url")}
               for row in rows[:6]]
        evidence = await evidence_store.search(f"{spec.name} {spec.description}", limit=4)
        return CouncilContext(
            scenario_id=spec.id, scenario_name=spec.name,
            scenario_description=spec.description, sim=sim,
            intel_summary=summary, top_events=top, retrieved_evidence=evidence,
        )

    async def convene(
        self, scenario_id: str, levers: ResponseLevers | None = None
    ) -> CouncilResult:
        spec = get_scenario(scenario_id)
        if not spec:
            raise ValueError(f"Unknown scenario '{scenario_id}'")
        ctx = await self._build_context(spec, levers)
        run_id = f"wf-{uuid4().hex[:12]}"
        state = await self._graph.ainvoke(
            {"context": ctx, "spec": spec, "assessments": []},
            config={"configurable": {"thread_id": run_id}},
        )
        assessments = state.get("assessments", [])
        strategies = state.get("strategies", [])
        workflow_trace = state.get("workflow_trace", [])
        consensus = round(sum(a.confidence for a in assessments) / len(assessments), 1)
        modes = [a.reasoning_mode for a in assessments]
        mode = "llm" if modes.count("llm") > len(modes) / 2 else "grounded"
        recommended = strategies[0].id if strategies else ""
        result = CouncilResult(
            scenario_id=spec.id, scenario_name=spec.name, assessments=assessments,
            strategies=strategies, disagreements=state.get("disagreements", []),
            consensus_confidence=consensus, reasoning_mode=mode,
            recommended_strategy_id=recommended, workflow_run_id=run_id,
            workflow_trace=workflow_trace,
            provenance={"events": ctx.intel_summary.get("provenance", {}),
                        "evidence_documents": len(ctx.retrieved_evidence)},
        )
        persisted = await get_repositories().save_workflow({
            "workflow_run_id": run_id, "scenario_id": scenario_id, "status": "completed",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "result": result.model_dump(mode="json"),
        })
        if strategies:
            mission = await get_repositories().create_mission(
                scenario_id, recommended, run_id,
                {"strategy": strategies[0].model_dump(mode="json"),
                 "workflow": persisted["workflow_run_id"]},
            )
            result.mission_id = mission["id"]
            await get_repositories().save_workflow({
                **persisted, "result": result.model_dump(mode="json"),
            })
        return result


def _detect_disagreements(assessments: list[AgentAssessment]) -> list[Disagreement]:
    out: list[Disagreement] = []
    by_id = {a.agent_id: a for a in assessments}
    reserve, economic, procurement = (by_id.get("reserve"), by_id.get("economic"),
                                      by_id.get("procurement"))
    if reserve and "conserve" in reserve.stance.lower():
        opponents = [agent for agent in (economic, procurement) if agent and
                     any(word in agent.stance.lower() for word in ("buffer", "short"))]
        if opponents:
            out.append(Disagreement(
                topic="Strategic reserve release vs. preservation",
                positions=[{"agent": reserve.agent_name, "stance": reserve.stance}] +
                          [{"agent": agent.agent_name, "stance": agent.stance}
                           for agent in opponents],
            ))
    maritime = by_id.get("maritime")
    if maritime and procurement and "bypass" in maritime.stance.lower() and \
            "short" in procurement.stance.lower():
        out.append(Disagreement(
            topic="Rerouting cannot close the gap — sourcing must",
            positions=[{"agent": maritime.agent_name, "stance": maritime.stance},
                       {"agent": procurement.agent_name, "stance": procurement.stance}],
        ))
    return out


_council = Council()


def get_council() -> Council:
    return _council
