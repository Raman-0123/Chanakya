"use client";

import { motion } from "framer-motion";
import { CheckCircle2, Clock, GitBranch, Shield, Zap } from "lucide-react";
import { Panel, PanelHeader } from "@/components/primitives";
import type { WorkflowStep } from "@/lib/types";
import { cn } from "@/lib/utils";

interface WorkflowTraceProps {
  steps: WorkflowStep[];
  runId: string;
  consensusConfidence: number;
}

export function WorkflowTrace({ steps, runId, consensusConfidence }: WorkflowTraceProps) {
  const chief = steps.find((s) => s.node === "chief");
  const specialists = steps.filter((s) => s.node.startsWith("specialist_"));
  const reconcile = steps.find((s) => s.node === "reconcile");
  const decision = steps.find((s) => s.node === "decision");
  const timestamps = steps.flatMap((step) => [Date.parse(step.started_at), Date.parse(step.completed_at)]).filter(Number.isFinite);
  const totalDuration = timestamps.length > 1
    ? Math.max(0, Math.max(...timestamps) - Math.min(...timestamps))
    : steps.reduce((sum, step) => sum + (step.duration_ms || 0), 0);

  return (
    <Panel className="border-signal/30 bg-panel/90 p-4">
      <PanelHeader
        eyebrow="LangGraph Orchestration Trace"
        title="Agent Council Multi-Graph Execution"
        right={
          <div className="flex items-center gap-3 text-xs text-ink-dim">
            <span className="flex items-center gap-1 font-mono text-[10px]">
              <Clock size={12} className="text-signal" />
              {totalDuration}ms total
            </span>
            <span className="flex items-center gap-1 font-mono text-[10px]">
              <Zap size={12} className="text-nominal" />
              Run: {runId.slice(0, 10)}…
            </span>
          </div>
        }
      />

      <div className="mt-4 space-y-4">
        {/* Stage 1: Chief Coordinator */}
        <div className="flex items-start gap-3">
          <NodeBadge label="START / CHIEF" activeIcon={<Shield size={14} className="text-signal" />} />
          <div className="flex-1 rounded border border-line bg-panel-raised p-2.5">
            <div className="flex items-center justify-between text-xs font-semibold text-ink">
              <span>{chief?.label ?? "Chief Coordinator"}</span>
              <span className="font-mono text-[10px] text-ink-dim">State Initialized</span>
            </div>
            <p className="mt-1 text-xs text-ink-muted">
              {chief?.outputs_summary || "Parallelizing state brief across 6 domain-expert reasoners."}
            </p>
          </div>
        </div>

        {/* Stage 2: Specialist Execution (Parallel DAG) */}
        <div className="relative pl-5 before:absolute before:left-3 before:top-0 before:h-full before:w-0.5 before:bg-line-strong">
          <div className="mb-2 flex items-center gap-2">
            <GitBranch size={13} className="text-signal" />
            <span className="label-terminal text-[10px]">Parallel Branch Execution (6 Agents)</span>
          </div>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {specialists.map((step, i) => (
              <motion.div
                key={step.node}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.04 }}
                className="rounded border border-line/80 bg-panel/60 p-2 text-xs"
              >
                <div className="flex items-center justify-between">
                  <span className="font-medium text-ink">{step.label}</span>
                  <span className="flex items-center gap-1 font-mono text-[9px] text-nominal">
                    <CheckCircle2 size={10} />
                    {step.duration_ms}ms
                  </span>
                </div>
                <div className="mt-1 line-clamp-2 font-mono text-[10px] text-ink-muted">
                  {step.outputs_summary}
                </div>
              </motion.div>
            ))}
          </div>
        </div>

        {/* Stage 3: Reconciliation & Decision Engine */}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {/* Reconcile Node */}
          <div className="flex items-start gap-3">
            <NodeBadge label="RECONCILE" activeIcon={<GitBranch size={14} className="text-elevated" />} />
            <div className="flex-1 rounded border border-line bg-panel-raised p-2.5 text-xs">
              <div className="flex items-center justify-between font-semibold text-ink">
                <span>{reconcile?.label ?? "Reconciliation Node"}</span>
                <span className="font-mono text-[10px] text-nominal">{reconcile?.duration_ms}ms</span>
              </div>
              <p className="mt-1 text-ink-muted">{reconcile?.outputs_summary || "No contention detected."}</p>
            </div>
          </div>

          {/* Decision Node */}
          <div className="flex items-start gap-3">
            <NodeBadge label="DECIDE" activeIcon={<Zap size={14} className="text-signal" />} />
            <div className="flex-1 rounded border border-signal/40 bg-signal/5 p-2.5 text-xs">
              <div className="flex items-center justify-between font-semibold text-signal">
                <span>{decision?.label ?? "Decision Engine"}</span>
                <span className="font-mono text-[10px] text-nominal">{decision?.duration_ms}ms</span>
              </div>
              <p className="mt-1 text-ink-muted">{decision?.outputs_summary || "Strategies ranked successfully."}</p>
            </div>
          </div>
        </div>
      </div>
    </Panel>
  );
}

function NodeBadge({ label, activeIcon }: { label: string; activeIcon: React.ReactNode }) {
  return (
    <div className="flex shrink-0 flex-col items-center gap-1">
      <div className="grid h-7 w-7 place-items-center rounded bg-panel-raised border border-line-strong">
        {activeIcon}
      </div>
      <span className="font-mono text-[8px] uppercase tracking-wider text-ink-dim">{label}</span>
    </div>
  );
}
