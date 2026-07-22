"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { Rocket, FileText, CheckCircle2, Circle, Loader2, AlertOctagon, Download } from "lucide-react";
import { useCouncil, useLatestMission, useMissionRecord } from "@/hooks/useChanakya";
import { useMission } from "@/stores/useMission";
import { Panel, PanelHeader } from "@/components/primitives";
import { CrisisTimeline } from "./CrisisTimeline";
import type { MissionRecord, MissionTask, StrategyOption } from "@/lib/types";
import { cn } from "@/lib/utils";
import { apiPostOperator } from "@/lib/api";
import { useQueryClient } from "@tanstack/react-query";

function agencyFor(step: string): string {
  const t = step.toLowerCase();
  if (t.includes("spr") || t.includes("reserve")) return "ISPRL";
  if (t.includes("tender") || t.includes("procure") || t.includes("cargo") || t.includes("iocl"))
    return "IOCL / BPCL / HPCL";
  if (t.includes("tanker") || t.includes("route") || t.includes("insurance"))
    return "DG Shipping";
  if (t.includes("advisory") || t.includes("demand")) return "MoPNG";
  if (t.includes("cell") || t.includes("cabinet")) return "Crisis Cell";
  return "MoPNG";
}

function priorityFor(i: number): string {
  return i === 0 ? "P0" : i <= 2 ? "P1" : "P2";
}

export function ExecutionRoom() {
  const queryClient = useQueryClient();
  const { scenarioId, levers, selectedStrategyId, activated, activateMission } = useMission();
  const { data: council, isLoading: councilLoading } = useCouncil(scenarioId, levers);
  const { data: latestMission, isLoading: missionLoading } = useLatestMission(scenarioId);
  const [activationError, setActivationError] = useState<string | null>(null);
  const [activating, setActivating] = useState(false);

  const missionId = council?.mission_id ?? latestMission?.id ?? null;
  const { data: missionRecord } = useMissionRecord(missionId);
  const mission = missionRecord ?? latestMission;
  const missionActive = activated || mission?.status === "active" || mission?.status === "completed";
  const strategy =
    council?.strategies.find((s) => s.id === (selectedStrategyId ?? council.recommended_strategy_id)) ??
    mission?.strategy ??
    null;
  const scenarioName = council?.scenario_name ?? scenarioId.replaceAll("_", " ");
  const sourceLabel = council
    ? "LIVE COUNCIL REASONING"
    : latestMission
      ? "RECOVERED MISSION AUDIT"
      : "AWAITING DECISION";
  const titleLine = strategy
    ? strategy.title
    : councilLoading || missionLoading
      ? "Loading mission brief…"
      : "No mission record yet";

  const launch = async () => {
    if (!missionId || !strategy) {
      setActivationError("No mission record is available yet. Run the Decision Center first.");
      return;
    }
    const pin = window.prompt("Operator PIN required to activate national mission playback");
    if (!pin) return;
    setActivating(true);
    setActivationError(null);
    try {
      await apiPostOperator<MissionRecord>(`/api/missions/${missionId}/activate`, pin, {
        strategy_id: strategy.id,
      });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["mission", missionId] }),
        queryClient.invalidateQueries({ queryKey: ["mission-latest", scenarioId] }),
      ]);
      activateMission();
    } catch (error) {
      setActivationError(error instanceof Error ? error.message : "Mission activation failed");
    } finally {
      setActivating(false);
    }
  };

  return (
    <div className="flex h-full flex-col gap-3 overflow-y-auto p-4 blueprint select-none">
      {/* Header Banner */}
      <div className="tactical-panel flex items-center justify-between px-4 py-3 bg-panel/95">
        <div>
          <div className="label-terminal font-bold text-signal">Mission Execution Deck · {scenarioName}</div>
          <div className="text-base font-bold text-ink font-mono">{titleLine}</div>
          <div className="mt-0.5 text-[9px] uppercase tracking-[0.2em] text-ink-dim font-mono flex items-center gap-2">
            <span className="h-1.5 w-1.5 rounded-full bg-signal animate-pulse" />
            STATUS: {sourceLabel}
          </div>
        </div>

        <button
          disabled={!strategy || missionActive || activating}
          onClick={() => void launch()}
          className={cn(
            "flex items-center gap-2 rounded px-4 py-2 font-mono text-xs font-bold uppercase tracking-wider transition-all",
            missionActive
              ? "border border-emerald-500/50 bg-emerald-500/15 text-emerald-500 shadow-glow-nominal"
              : "border border-signal/50 bg-signal/15 text-signal hover:bg-signal/25 shadow-glow-signal disabled:opacity-40",
          )}
        >
          <Rocket size={15} />
          {missionActive ? `MISSION ${mission?.status.toUpperCase() ?? "ACTIVE"}` : activating ? "AUTHORISING PIN…" : "LAUNCH MISSION PLAYBOOK"}
        </button>
      </div>

      {activationError && (
        <div className="rounded border border-red-500/50 bg-red-950/40 px-3 py-2 font-mono text-xs text-red-400 flex items-center gap-2">
          <AlertOctagon size={14} />
          {activationError}
        </div>
      )}

      {strategy ? (
        <>
          <CrisisTimeline />
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-[1.1fr_1fr]">
            <MissionChecklist strategy={strategy} mission={mission ?? null} missionId={missionId} activated={missionActive} />
            <BriefingPack strategy={strategy} scenario={scenarioName} />
          </div>
        </>
      ) : councilLoading || missionLoading ? (
        <div className="tactical-panel grid flex-1 place-items-center p-8">
          <div className="text-center font-mono">
            <div className="text-sm font-bold text-signal animate-pulse">Generating Mission Playbook…</div>
            <p className="mt-1 text-xs text-ink-muted">
              Synthesizing agent council consensus and persisted mission parameters.
            </p>
          </div>
        </div>
      ) : (
        <div className="tactical-panel grid flex-1 place-items-center p-8">
          <p className="text-xs font-mono text-ink-muted">
            No mission record exists for this scenario yet. Run the Decision Center to generate
            one, then return here to activate playback.
          </p>
        </div>
      )}
    </div>
  );
}

function MissionChecklist({
  strategy, mission, missionId, activated,
}: {
  strategy: StrategyOption;
  mission: MissionRecord | null;
  missionId: string | null;
  activated: boolean;
}) {
  const queryClient = useQueryClient();
  const [updating, setUpdating] = useState<string | null>(null);
  const [taskError, setTaskError] = useState<string | null>(null);
  const fallbackTasks: MissionTask[] = strategy.implementation_steps.map((action, index) => ({
    id: `draft-${index + 1}`, sequence: index + 1, action,
    agency: agencyFor(action), priority: priorityFor(index), status: "pending",
    acknowledged_at: null, completed_at: null, note: null,
  }));
  const tasks = mission?.tasks?.length ? mission.tasks : fallbackTasks;

  const advance = async (task: MissionTask, status: MissionTask["status"]) => {
    if (!missionId || task.id.startsWith("draft-")) {
      setTaskError("Activate a persisted mission before updating agency tasks.");
      return;
    }
    const pin = window.prompt(`Operator PIN required to mark ${task.agency} task ${status}`);
    if (!pin) return;
    const note = status === "blocked" ? window.prompt("Blocking note (optional)") : null;
    setUpdating(task.id);
    setTaskError(null);
    try {
      await apiPostOperator<MissionRecord>(`/api/missions/${missionId}/tasks/${task.id}`, pin, { status, note });
      await queryClient.invalidateQueries({ queryKey: ["mission", missionId] });
    } catch (error) {
      setTaskError(error instanceof Error ? error.message : "Task update failed");
    } finally {
      setUpdating(null);
    }
  };

  const nextStatus = (status: MissionTask["status"]): MissionTask["status"] | null => {
    if (status === "queued" || status === "pending") return "acknowledged";
    if (status === "acknowledged" || status === "blocked") return "in_progress";
    if (status === "in_progress") return "completed";
    return null;
  };

  return (
    <div className="tactical-panel">
      <PanelHeader eyebrow="Operational Playbook" title="Action Checklist & Inter-Agency Sequence" />
      {taskError && <div className="mx-4 mt-3 rounded border border-critical/40 bg-critical/10 px-3 py-2 font-mono text-[10px] text-critical">{taskError}</div>}
      <div className="divide-y divide-line">
        {tasks.map((task, i) => {
          const state = task.status;
          const next = nextStatus(state);
          return (
            <motion.div
              key={task.id}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.05 }}
              className="flex items-start gap-3 px-4 py-3 hover:bg-panel-hover transition-colors"
            >
              <span className="mt-0.5">
                {state === "completed" ? (
                  <CheckCircle2 size={16} className="text-emerald-500" />
                ) : state === "in_progress" || updating === task.id ? (
                  <Loader2 size={16} className="animate-spin text-signal" />
                ) : (
                  <Circle size={16} className="text-ink-dim" />
                )}
              </span>
              <div className="min-w-0 flex-1">
                <div className="text-xs font-semibold text-ink font-mono">{task.action}</div>
                <div className="mt-1 flex items-center gap-2">
                  <span className="rounded bg-panel border border-line px-2 py-0.5 font-mono text-[10px] uppercase text-signal font-bold">
                    {task.agency}
                  </span>
                  <span
                    className={cn(
                      "font-mono text-[10px] font-bold px-1.5 py-0.2 rounded",
                      task.priority === "P0" ? "bg-red-950/60 text-red-500 border border-red-800/40" : task.priority === "P1" ? "bg-amber-950/60 text-amber-500 border border-amber-800/40" : "bg-panel text-ink-muted",
                    )}
                  >
                    {task.priority}
                  </span>
                  <span className="font-mono text-[10px] uppercase text-ink-dim">{state}</span>
                </div>
                {task.note && <div className="mt-1 text-[10px] text-critical">Blocked: {task.note}</div>}
              </div>
              {activated && next && (
                <div className="flex shrink-0 gap-1">
                  {state !== "blocked" && state !== "in_progress" && (
                    <button
                      disabled={updating === task.id}
                      onClick={() => void advance(task, "blocked")}
                      className="rounded border border-critical/30 px-2 py-1 font-mono text-[9px] uppercase text-critical hover:bg-critical/10 disabled:opacity-40"
                    >Block</button>
                  )}
                  <button
                    disabled={updating === task.id}
                    onClick={() => void advance(task, next)}
                    className="rounded border border-signal/40 bg-signal/10 px-2 py-1 font-mono text-[9px] uppercase text-signal hover:bg-signal/20 disabled:opacity-40"
                  >{next.replace("in_progress", "start")}</button>
                </div>
              )}
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}

function BriefingPack({ strategy, scenario }: { strategy: StrategyOption; scenario: string }) {
  const p = strategy.projection;
  const briefs = [
    {
      title: "Cabinet Committee Briefing Note",
      body: `Scenario: ${scenario}. Recommended posture: ${strategy.title}. Projected national refinery utilisation ${p.national_utilization_pct.toFixed(
        0,
      )}%, residual shortfall ${p.residual_shortfall_kbpd.toLocaleString()} kbpd, security index ${p.nesi_after.toFixed(
        0,
      )}. Crude price impact ${p.brent_change_pct >= 0 ? "+" : ""}${p.brent_change_pct.toFixed(0)}%.`,
    },
    {
      title: "Procurement Order Directive",
      body: `Issue urgent replacement sourcing directives. Activate spare capacity and spot tenders to cover the supply gap; sequence cargoes to sustain refinery run rates. Estimated incremental cost ~$${p.est_daily_cost_musd.toFixed(
        1,
      )}M/day.`,
    },
    {
      title: "SPR Release Operational Schedule",
      body: `Authorise phased drawdown of ${p.spr_release_kbpd.toLocaleString()} kbpd across Visakhapatnam, Mangalore and Padur, sustainable ~${p.spr_days_remaining.toFixed(
        0,
      )} days at this rate. Refill behind replacement cargoes.`,
    },
    {
      title: "Public Advisory Draft (Finance / MoPNG)",
      body: `Projected retail diesel ₹${p.diesel_projected_inr.toFixed(
        1,
      )}/L. Prepare fiscal buffer and consumer-communication plan to manage pass-through and prevent panic demand.`,
    },
  ];
  return (
    <div className="tactical-panel">
      <PanelHeader
        eyebrow="Mission Report Generator"
        title="Executive Briefing Pack"
        right={<FileText size={15} className="text-signal" />}
      />
      <div className="space-y-2.5 p-4">
        {briefs.map((b, i) => (
          <motion.div
            key={b.title}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.08 }}
            className="rounded border border-line bg-panel-hover/80 p-3 hover:border-signal/40 transition-colors"
          >
            <div className="mb-1 flex items-center justify-between text-xs font-bold text-signal font-mono">
              <span>{b.title}</span>
              <Download size={13} className="text-ink-dim hover:text-signal cursor-pointer" />
            </div>
            <p className="text-xs leading-relaxed text-ink-muted font-sans">{b.body}</p>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
