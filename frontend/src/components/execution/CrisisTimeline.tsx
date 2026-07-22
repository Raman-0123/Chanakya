"use client";

import { motion } from "framer-motion";
import {
  Radar, ShieldAlert, Globe2, Activity, Users, FlaskConical,
  Brain, CheckCircle2, Rocket, Repeat,
} from "lucide-react";
import { useCouncil, useSimulation } from "@/hooks/useChanakya";
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

/** Chronological, replayable operational history of the active crisis. */
export function CrisisTimeline() {
  const { scenarioId, levers, activated } = useMission();
  const { data: sim } = useSimulation(scenarioId, levers);
  const { data: council } = useCouncil(scenarioId, levers);

  if (!sim || !council) return null;

  const rec = council.strategies.find((s) => s.id === council.recommended_strategy_id);
  const stages: Stage[] = [
    { icon: Radar, title: "Geopolitical event detected", detail: council.scenario_name, t: "T+0m", done: true },
    { icon: ShieldAlert, title: "Threat validated", detail: `Council convened · consensus ${council.consensus_confidence}%`, t: "T+2m", done: true },
    { icon: Globe2, title: "Digital twin updated", detail: `${sim.stressed_refineries.length || "no"} refineries flagged`, t: "T+3m", done: true },
    { icon: Activity, title: "AI risk assessment", detail: `Security Index ${sim.nesi_before.toFixed(0)} → ${sim.nesi_after.value.toFixed(0)}`, t: "T+4m", done: true },
    { icon: Users, title: "Intelligence council reasoned", detail: `${council.assessments.length} agents · ${council.disagreements.length} disagreement(s)`, t: "T+6m", done: true },
    { icon: FlaskConical, title: "Scenario simulation completed", detail: `Residual ${sim.residual_shortfall_kbpd.toLocaleString()} kbpd · Brent ${sim.brent_change_pct >= 0 ? "+" : ""}${sim.brent_change_pct.toFixed(0)}%`, t: "T+8m", done: true },
    { icon: Brain, title: "Recommendation generated", detail: rec ? `${rec.title} (score ${rec.score.toFixed(0)})` : "—", t: "T+9m", done: true },
    { icon: CheckCircle2, title: "Mission approved", detail: activated ? "Cabinet authorisation granted" : "Awaiting approval", t: "T+12m", done: activated },
    { icon: Rocket, title: "Execution started", detail: activated ? "Playbook dispatched to agencies" : "Pending", t: "T+13m", done: activated },
    { icon: Repeat, title: "Continuous monitoring", detail: activated ? "Live tracking active" : "Standby", t: "ongoing", done: activated },
  ];

  return (
    <Panel>
      <PanelHeader eyebrow="Decision Timeline" title="Crisis Response History" />
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
                <div className={cn("absolute left-1/2 top-4 h-0.5 w-full", s.done ? "bg-signal/40" : "bg-line")} />
              )}
              <div
                className={cn(
                  "relative z-10 grid h-8 w-8 place-items-center rounded-full border",
                  s.done
                    ? "border-signal/50 bg-signal/10 text-signal"
                    : "border-line bg-panel text-ink-dim",
                )}
              >
                <Icon size={15} strokeWidth={1.75} />
              </div>
              <div className="readout mt-1 text-[10px] text-ink-dim">{s.t}</div>
              <div className="mt-0.5 text-xs font-medium leading-tight text-ink">{s.title}</div>
              <div className="mt-0.5 text-[10px] leading-tight text-ink-muted">{s.detail}</div>
            </motion.div>
          );
        })}
      </div>
    </Panel>
  );
}
