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
from app.operations import get_operational_service
from app.operations.models import OperationalSnapshot

log = get_logger("agents.council")


class Disagreement(BaseModel):
    topic: str
    positions: list[dict]


class LatencyProfile(BaseModel):
    """End-to-end response time from triggering signal to recommendation.

    `total_pipeline_ms` is the processing latency CHANAKYA itself adds (context
    build + graph execution). `signal_age_seconds` is how old the freshest
    contributing signal was when the recommendation was produced, so
    `end_to_end_seconds` is the full observed-signal → recommendation time the
    rubric grades on.
    """

    context_build_ms: int = 0
    graph_execution_ms: int = 0
    total_pipeline_ms: int = 0
    triggering_signal_at: str | None = None
    signal_age_seconds: float | None = None
    recommendation_at: str = ""
    end_to_end_seconds: float = 0.0


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
    latency: LatencyProfile | None = None
    schema_version: str = "1.0"
    provenance: dict = Field(default_factory=dict)


class CouncilState(TypedDict, total=False):
    context: CouncilContext
    spec: ScenarioSpec
    assessments: Annotated[list[AgentAssessment], operator.add]
    disagreements: list[Disagreement]
    strategies: list[StrategyOption]
    workflow_trace: Annotated[list[WorkflowStep], operator.add]
    operational: OperationalSnapshot


class Council:
    def __init__(self):
        self._net = build_energy_network()
        self._engine = SimulationEngine(self._net)
        self._graph = self._build_graph()
        self._result_cache: dict[str, CouncilResult] = {}

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
                self._engine, state["spec"], round(self._net.daily_crude_imports_kbpd, 1),
                assessments=state.get("assessments", []),
                operational=state.get("operational"),
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
        self, spec: ScenarioSpec, levers: ResponseLevers | None,
        operational: OperationalSnapshot,
    ) -> CouncilContext:
        sim = self._engine.run(spec, levers, operational)
        rows = operational.evidence_events
        severity = Counter(row.get("severity", "nominal") for row in rows)
        corridors = Counter(c for row in rows for c in row.get("affected_corridors", []))
        threat = ("critical" if severity.get("critical") else
                  "high" if severity.get("high") else
                  "elevated" if severity.get("elevated") else "nominal")
        provenance = Counter(row.get("source_kind", "unavailable") for row in rows)
        observed_times = [row.get("published_at") for row in rows if row.get("published_at")]
        summary = {
            "threat_level": threat, "event_count": len(rows),
            "corridors_flagged": dict(corridors),
            "peak_risk_score": max((row.get("risk_score", 0) for row in rows), default=0),
            "is_live": operational.is_live,
            "provenance": dict(provenance),
            # ISO-8601 UTC strings sort chronologically — freshest is the max.
            "freshest_signal_at": max(observed_times) if observed_times else None,
            "oldest_signal_at": min(observed_times) if observed_times else None,
        }
        top = [{"title": row.get("title"), "severity": row.get("severity", "elevated"),
                "affected_corridors": row.get("affected_corridors", []),
                "source": row.get("source"), "source_url": row.get("url")}
               for row in rows[:6]]
        evidence = await evidence_store.search(f"{spec.name} {spec.description}", limit=4)
        return CouncilContext(
            scenario_id=spec.id, scenario_name=spec.name,
            scenario_description=spec.description, sim=sim,
            intel_summary=summary, top_events=top, retrieved_evidence=evidence,
            operational_snapshot={
                "id": operational.id, "is_live": operational.is_live,
                "data_quality_score": operational.data_quality_score,
                "brent_usd": operational.market.brent_usd,
                "provenance": operational.provenance,
            },
        )

    async def convene(
        self, scenario_id: str, levers: ResponseLevers | None = None,
        operational: OperationalSnapshot | None = None,
    ) -> CouncilResult:
        operational = operational or await get_operational_service().current()
        spec = (operational.active_scenario if scenario_id == "auto_live"
                else get_scenario(scenario_id))
        if not spec:
            raise ValueError(f"Unknown scenario '{scenario_id}'")
        effective_levers = levers or spec.default_levers
        cache_key = (
            f"{scenario_id}:{operational.id}:"
            f"{effective_levers.spr_release_pct:.1f}:"
            f"{int(effective_levers.enable_reroute)}:{int(effective_levers.enable_spot)}"
        )
        if cache_key in self._result_cache:
            return self._result_cache[cache_key].model_copy(deep=True)
        ctx_t0 = time.monotonic()
        ctx = await self._build_context(spec, levers, operational)
        context_build_ms = int((time.monotonic() - ctx_t0) * 1000)
        run_id = f"wf-{uuid4().hex[:12]}"
        graph_t0 = time.monotonic()
        state = await self._graph.ainvoke(
            {"context": ctx, "spec": spec, "assessments": [],
             "operational": operational},
            config={"configurable": {"thread_id": run_id}},
        )
        graph_execution_ms = int((time.monotonic() - graph_t0) * 1000)
        latency = _build_latency(ctx, context_build_ms, graph_execution_ms)
        assessments = state.get("assessments", [])
        strategies = state.get("strategies", [])
        workflow_trace = state.get("workflow_trace", [])
        consensus = _consensus_score(assessments)
        modes = [a.reasoning_mode for a in assessments]
        mode = "llm" if modes.count("llm") > len(modes) / 2 else "grounded"
        recommended = strategies[0].id if strategies else ""
        result = CouncilResult(
            scenario_id=spec.id, scenario_name=spec.name, assessments=assessments,
            strategies=strategies, disagreements=state.get("disagreements", []),
            consensus_confidence=consensus, reasoning_mode=mode,
            recommended_strategy_id=recommended, workflow_run_id=run_id,
            workflow_trace=workflow_trace, latency=latency,
            provenance={"events": ctx.intel_summary.get("provenance", {}),
                        "evidence_documents": len(ctx.retrieved_evidence),
                        "operational_snapshot_id": operational.id,
                        "data_quality_score": operational.data_quality_score,
                        "market": operational.market.model_dump(mode="json")},
        )
        persisted = await get_repositories().save_workflow({
            "workflow_run_id": run_id, "scenario_id": scenario_id, "status": "completed",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "result": result.model_dump(mode="json"),
        })
        if strategies:
            tasks = _mission_tasks(strategies[0])
            mission = await get_repositories().create_mission(
                scenario_id, recommended, run_id,
                {"strategy": strategies[0].model_dump(mode="json"),
                 "workflow": persisted["workflow_run_id"],
                 "operational_snapshot_id": operational.id,
                 "tasks": tasks},
            )
            result.mission_id = mission["id"]
            await get_repositories().save_workflow({
                **persisted, "result": result.model_dump(mode="json"),
            })
        self._result_cache[cache_key] = result.model_copy(deep=True)
        if len(self._result_cache) > 64:
            self._result_cache.pop(next(iter(self._result_cache)))
        return result


def _build_latency(
    ctx: CouncilContext, context_build_ms: int, graph_execution_ms: int
) -> LatencyProfile:
    """Assemble the signal→recommendation latency profile for this run."""
    recommendation_at = datetime.now(timezone.utc)
    total_pipeline_ms = context_build_ms + graph_execution_ms
    freshest = ctx.intel_summary.get("freshest_signal_at")
    signal_age_seconds: float | None = None
    if freshest:
        try:
            observed = datetime.fromisoformat(freshest)
            if observed.tzinfo is None:
                observed = observed.replace(tzinfo=timezone.utc)
            signal_age_seconds = max(0.0, (recommendation_at - observed).total_seconds())
        except (ValueError, TypeError):
            signal_age_seconds = None
    end_to_end_seconds = (signal_age_seconds if signal_age_seconds is not None
                          else round(total_pipeline_ms / 1000, 3))
    return LatencyProfile(
        context_build_ms=context_build_ms,
        graph_execution_ms=graph_execution_ms,
        total_pipeline_ms=total_pipeline_ms,
        triggering_signal_at=freshest,
        signal_age_seconds=round(signal_age_seconds, 1) if signal_age_seconds is not None else None,
        recommendation_at=recommendation_at.isoformat(),
        end_to_end_seconds=round(end_to_end_seconds, 1),
    )


def _detect_disagreements(assessments: list[AgentAssessment]) -> list[Disagreement]:
    out: list[Disagreement] = []
    by_id = {a.agent_id: a for a in assessments}
    reserve, economic, procurement = (by_id.get("reserve"), by_id.get("economic"),
                                      by_id.get("procurement"))
    if reserve and reserve.proposed_levers:
        opponents = [agent for agent in (economic, procurement)
                     if agent and agent.proposed_levers and
                     abs(agent.proposed_levers.spr_release_pct -
                         reserve.proposed_levers.spr_release_pct) >= 25]
        if opponents:
            out.append(Disagreement(
                topic="Strategic reserve release vs. preservation",
                positions=[{"agent": reserve.agent_name,
                            "stance": f"SPR {reserve.proposed_levers.spr_release_pct:.0f}% — {reserve.stance}"}] +
                          [{"agent": agent.agent_name,
                            "stance": f"SPR {agent.proposed_levers.spr_release_pct:.0f}% — {agent.stance}"}
                           for agent in opponents],
            ))
    maritime = by_id.get("maritime")
    if (maritime and procurement and maritime.proposed_levers and
            procurement.proposed_levers and
            maritime.proposed_levers.enable_reroute != procurement.proposed_levers.enable_reroute):
        out.append(Disagreement(
            topic="Rerouting posture",
            positions=[{"agent": maritime.agent_name, "stance": maritime.stance},
                       {"agent": procurement.agent_name, "stance": procurement.stance}],
        ))
    return out


def _consensus_score(assessments: list[AgentAssessment]) -> float:
    """Confidence adjusted by measured agreement on structured control levers."""
    if not assessments:
        return 0.0
    mean_confidence = sum(item.confidence for item in assessments) / len(assessments)
    proposed = [item.proposed_levers for item in assessments if item.proposed_levers]
    if not proposed:
        return round(mean_confidence * 0.6, 1)
    mean_spr = sum(item.spr_release_pct for item in proposed) / len(proposed)
    spr_dispersion = sum(abs(item.spr_release_pct - mean_spr) for item in proposed) / len(proposed)
    reroute_share = sum(item.enable_reroute for item in proposed) / len(proposed)
    spot_share = sum(item.enable_spot for item in proposed) / len(proposed)
    binary_disagreement = (min(reroute_share, 1 - reroute_share) +
                           min(spot_share, 1 - spot_share)) * 45
    agreement = max(0.0, 100 - spr_dispersion * 1.4 - binary_disagreement)
    return round(mean_confidence * 0.55 + agreement * 0.45, 1)


def _mission_tasks(strategy: StrategyOption) -> list[dict]:
    def agency(step: str) -> str:
        value = step.lower()
        if "spr" in value or "reserve" in value:
            return "ISPRL"
        if any(token in value for token in ("tender", "procure", "cargo", "iocl")):
            return "IOCL / BPCL / HPCL"
        if any(token in value for token in ("tanker", "route", "tonnage", "insurance")):
            return "DG Shipping"
        if "cabinet" in value or "crisis cell" in value:
            return "National Crisis Cell"
        return "MoPNG"

    return [
        {
            "id": f"task-{index + 1:02d}", "sequence": index + 1,
            "action": step, "agency": agency(step),
            "priority": "P0" if index == 0 else "P1" if index <= 3 else "P2",
            "status": "pending", "acknowledged_at": None,
            "completed_at": None, "note": None,
        }
        for index, step in enumerate(strategy.implementation_steps)
    ]


_council = Council()


def get_council() -> Council:
    return _council
