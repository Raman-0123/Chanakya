"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { Radar, Ship, ShoppingCart, Database, LineChart, Landmark, GitFork, GitBranch } from "lucide-react";
import { useCouncil } from "@/hooks/useChanakya";
import { useMission } from "@/stores/useMission";
import { Panel, PanelHeader, ConfidenceBar } from "@/components/primitives";
import { SourceTag } from "@/components/primitives/SourceTag";
import { WorkflowTrace } from "./WorkflowTrace";
import type { AgentAssessment } from "@/lib/types";
import { cn } from "@/lib/utils";

const AGENT_ICON: Record<string, any> = {
  intelligence: Radar,
  maritime: Ship,
  procurement: ShoppingCart,
  reserve: Database,
  economic: LineChart,
  policy: Landmark,
};

export function CouncilRoom() {
  const { scenarioId, levers } = useMission();
  const { data, isLoading } = useCouncil(scenarioId, levers);
  const [showWorkflow, setShowWorkflow] = useState(true);

  return (
    <div className="flex h-full flex-col gap-3 overflow-y-auto p-4 blueprint">
      {/* Council header */}
      <Panel className="flex items-center justify-between px-4 py-3">
        <div>
          <div className="label-terminal">Intelligence Council · {data?.scenario_name ?? "…"}</div>
          <div className="text-sm font-semibold text-ink">
            Six advisors convened{" "}
            {data && (
              <span className="text-ink-dim">
                · consensus {data.consensus_confidence}% · {data.assessments.length} assessments
              </span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {data && (
            <button
              onClick={() => setShowWorkflow(!showWorkflow)}
              className={cn(
                "flex items-center gap-1.5 rounded px-2.5 py-1 text-xs font-medium transition-colors border",
                showWorkflow
                  ? "border-signal/40 bg-signal/10 text-signal"
                  : "border-line bg-panel text-ink-muted hover:text-ink"
              )}
            >
              <GitBranch size={13} />
              LangGraph DAG {showWorkflow ? "ON" : "OFF"}
            </button>
          )}
          {data && <SourceTag kind={data.reasoning_mode} />}
        </div>
      </Panel>

      {/* LangGraph Workflow DAG Trace */}
      {data && showWorkflow && data.workflow_trace && data.workflow_trace.length > 0 && (
        <WorkflowTrace
          steps={data.workflow_trace}
          runId={data.workflow_run_id}
          consensusConfidence={data.consensus_confidence}
        />
      )}

      {/* Disagreements */}
      {data && data.disagreements.length > 0 && (
        <Panel className="border-elevated/30">
          <PanelHeader
            eyebrow="Points of Contention"
            title="Council Disagreements"
            right={<GitFork size={15} className="text-elevated" />}
          />
          <div className="space-y-3 p-4">
            {data.disagreements.map((d, i) => (
              <div key={i}>
                <div className="mb-1.5 text-sm font-medium text-elevated">{d.topic}</div>
                <div className="grid gap-2 sm:grid-cols-2">
                  {d.positions.map((p, j) => (
                    <div key={j} className="rounded border border-line bg-panel/50 px-3 py-2">
                      <div className="label-terminal">{p.agent}</div>
                      <div className="text-xs text-ink">{p.stance}</div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </Panel>
      )}

      {/* Agent grid */}
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
        {isLoading &&
          Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-52 animate-pulse rounded-lg bg-panel/60" />
          ))}
        {data?.assessments.map((a, i) => (
          <AgentCard key={a.agent_id} a={a} index={i} />
        ))}
      </div>
    </div>
  );
}

function AgentCard({ a, index }: { a: AgentAssessment; index: number }) {
  const Icon = AGENT_ICON[a.agent_id] ?? Radar;
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.06 }}
    >
      <Panel className="flex h-full flex-col p-4">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2.5">
            <div className="grid h-9 w-9 place-items-center rounded-md border border-line-strong bg-panel-raised text-signal">
              <Icon size={17} strokeWidth={1.75} />
            </div>
            <div>
              <div className="text-sm font-semibold text-ink">{a.agent_name}</div>
              <div className="label-terminal">{a.role}</div>
            </div>
          </div>
          <SourceTag kind={a.reasoning_mode} />
        </div>

        <div className="mt-3 rounded border border-signal/20 bg-signal/5 px-3 py-2">
          <div className="label-terminal">Position</div>
          <div className="text-sm font-medium text-ink">{a.stance}</div>
        </div>

        <ul className="mt-3 space-y-1">
          {a.observations.map((o, i) => (
            <li key={i} className="flex gap-2 text-xs text-ink-muted">
              <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-ink-dim" />
              {o}
            </li>
          ))}
        </ul>

        <p className="mt-2 text-xs leading-relaxed text-ink-muted">{a.reasoning}</p>

        <div className="mt-3 rounded bg-panel/60 px-3 py-2">
          <div className="label-terminal">Recommendation</div>
          <div className="text-xs text-ink">{a.recommendation}</div>
        </div>

        {a.proposed_levers && (
          <div className="mt-2 grid grid-cols-3 gap-1 rounded border border-line bg-base/40 p-2 text-center font-mono">
            <div><div className="text-xs font-bold text-signal">{a.proposed_levers.spr_release_pct}%</div><div className="text-[8px] uppercase text-ink-dim">SPR</div></div>
            <div><div className="text-xs font-bold text-signal">{a.proposed_levers.enable_reroute ? "ON" : "OFF"}</div><div className="text-[8px] uppercase text-ink-dim">Reroute</div></div>
            <div><div className="text-xs font-bold text-signal">{a.proposed_levers.enable_spot ? "ON" : "OFF"}</div><div className="text-[8px] uppercase text-ink-dim">Spot</div></div>
          </div>
        )}

        <div className="mt-2 font-mono text-[9px] uppercase text-ink-dim">
          {a.reasoning_mode === "llm"
            ? `${a.llm_provider ?? "LLM"} · ${a.llm_model ?? "model"} · ${a.llm_latency_ms ?? "—"}ms`
            : "Grounded deterministic fallback · no model call"}
        </div>

        {a.concerns.length > 0 && (
          <div className="mt-2 text-xs text-elevated">
            ⚠ {a.concerns.join(" · ")}
          </div>
        )}

        <div className="mt-auto pt-3">
          <ConfidenceBar value={a.confidence} label="Confidence" />
        </div>
      </Panel>
    </motion.div>
  );
}
