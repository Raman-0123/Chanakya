"use client";

import { motion } from "framer-motion";
import {
  Radar, ShieldAlert, Globe2, Activity, Users, FlaskConical,
  Brain, CheckCircle2, Rocket, Repeat,
} from "lucide-react";
import { useCouncil, useMissionRecord, useSimulation } from "@/hooks/useChanakya";
import { useMission } from "@/stores/useMission";
import { Panel, PanelHeader } from "@/components/primitives";
import { cn } from "@/lib/utils";

interface Stage {
  icon: any;
  title: string;
  detail: string;
  t: string;
  done: boolean;
}

export function CrisisTimeline() {
  const { scenarioId, levers, activated, selectedStrategyId } = useMission();
  const { data: sim } = useSimulation(scenarioId, levers);
  const { data: council } = useCouncil(scenarioId, levers);
  const { data: mission } = useMissionRecord(council?.mission_id ?? null);

  if (!sim || !council) return null;

  const rec = mission?.strategy ?? council.strategies.find(
    (s) => s.id === (selectedStrategyId ?? council.recommended_strategy_id),
  );
  const trace = council.workflow_trace ?? [];
  const traceStart = Math.min(...trace.map((step) => Date.parse(step.started_at)).filter(Number.isFinite));
  const elapsedAt = (node: string) => {
    const step = trace.find((item) => item.node === node);
    if (!step || !Number.isFinite(traceStart)) return "—";
    return `+${Math.max(0, Date.parse(step.completed_at) - traceStart)}ms`;
  };
  const signalAge = council.latency?.signal_age_seconds;
  const missionActive = activated || mission?.status === "active" || mission?.status === "completed";
  const completedTasks = mission?.tasks?.filter((task) => task.status === "completed").length ?? 0;
  const totalTasks = mission?.tasks?.length ?? rec?.implementation_steps.length ?? 0;
  const stages: Stage[] = [
    { icon: Radar, title: "Signal observed", detail: council.latency?.triggering_signal_at ? `${council.scenario_name} · source timestamp retained` : `${council.scenario_name} · no source timestamp`, t: signalAge == null ? "OBS —" : `OBS -${formatDuration(signalAge * 1000)}`, done: true },
    { icon: ShieldAlert, title: "Operational state fused", detail: `Snapshot ${sim.operational_snapshot_id?.slice(-8) ?? "—"} · ${String(sim.input_provenance.live ?? 0)} live inputs`, t: `+${council.latency?.context_build_ms ?? 0}ms`, done: true },
    { icon: Globe2, title: "Digital twin updated", detail: `${sim.stressed_refineries.length || "no"} refineries flagged`, t: elapsedAt("chief"), done: true },
    { icon: Activity, title: "AI risk assessment", detail: `Security Index ${sim.nesi_before.toFixed(0)} → ${sim.nesi_after.value.toFixed(0)}`, t: elapsedAt("specialist_intelligence"), done: true },
    { icon: Users, title: "Council agents completed", detail: `${council.assessments.length} agents · ${council.disagreements.length} measured disagreement(s)`, t: `${council.latency?.graph_execution_ms ?? 0}ms graph`, done: true },
    { icon: FlaskConical, title: "Scenario optimization completed", detail: `${rec?.optimization?.candidate_count ?? 0} control plans · residual ${sim.residual_shortfall_kbpd.toLocaleString()} kbpd`, t: elapsedAt("decision"), done: true },
    { icon: Brain, title: "Recommendation generated", detail: rec ? `${rec.title} (score ${rec.score.toFixed(0)})` : "—", t: `${council.latency?.total_pipeline_ms ?? 0}ms`, done: true },
    { icon: CheckCircle2, title: "Mission approved", detail: missionActive ? `Operator authorised ${mission?.activated_at ? new Date(mission.activated_at).toLocaleTimeString() : ""}` : "Awaiting operator PIN", t: mission?.activated_at ? new Date(mission.activated_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "pending", done: missionActive },
    { icon: Rocket, title: "Execution tracked", detail: missionActive ? `${completedTasks}/${totalTasks} agency tasks completed` : "Not dispatched", t: missionActive ? mission?.status.toUpperCase() ?? "ACTIVE" : "pending", done: missionActive },
    { icon: Repeat, title: "Continuous monitoring", detail: missionActive ? "Operational snapshot refresh active" : "Standby", t: "15s refresh", done: missionActive },
  ];

  return (
    <div className="tactical-panel select-none">
      <PanelHeader eyebrow="Decision Timeline & Audit Trail" title="Crisis Response Sequence" />
      <div className="flex gap-4 overflow-x-auto p-4">
        {stages.map((s, i) => {
          const Icon = s.icon;
          return (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
              className="relative flex w-40 shrink-0 flex-col items-center text-center"
            >
              {i < stages.length - 1 && (
                <div
                  className={cn(
                    "absolute left-1/2 top-4 h-0.5 w-full transition-colors",
                    s.done ? "bg-signal/60 shadow-glow-signal" : "bg-line"
                  )}
                />
              )}
              <div
                className={cn(
                  "relative z-10 grid h-8 w-8 place-items-center rounded-full border transition-all",
                  s.done
                    ? "border-signal/60 bg-signal/15 text-signal shadow-glow-signal"
                    : "border-line bg-panel-hover text-ink-dim"
                )}
              >
                <Icon size={15} strokeWidth={1.75} />
              </div>
              <div className="readout mt-1 font-mono text-[10px] text-signal font-bold">{s.t}</div>
              <div className="mt-0.5 text-xs font-semibold leading-tight text-ink font-mono">{s.title}</div>
              <div className="mt-0.5 text-[10px] leading-tight text-ink-muted">{s.detail}</div>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}

function formatDuration(ms: number): string {
  if (ms < 1_000) return `${Math.round(ms)}ms`;
  if (ms < 60_000) return `${Math.round(ms / 1_000)}s`;
  if (ms < 3_600_000) return `${Math.round(ms / 60_000)}m`;
  return `${(ms / 3_600_000).toFixed(1)}h`;
}
