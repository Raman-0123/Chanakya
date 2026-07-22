"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Rocket, FileText, CheckCircle2, Circle, Loader2, ShieldCheck, AlertOctagon, Download } from "lucide-react";
import { useCouncil, useLatestMission } from "@/hooks/useChanakya";
import { useMission } from "@/stores/useMission";
import { Panel, PanelHeader } from "@/components/primitives";
import { CrisisTimeline } from "./CrisisTimeline";
import type { StrategyOption } from "@/lib/types";
import { cn } from "@/lib/utils";
import { apiPostOperator } from "@/lib/api";

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
  const { scenarioId, levers, selectedStrategyId, activated, activateMission } = useMission();
  const { data: council, isLoading: councilLoading } = useCouncil(scenarioId, levers);
  const { data: latestMission, isLoading: missionLoading } = useLatestMission(scenarioId);
  const [activationError, setActivationError] = useState<string | null>(null);
  const [activating, setActivating] = useState(false);

  const strategy =
    council?.strategies.find((s) => s.id === (selectedStrategyId ?? council.recommended_strategy_id)) ??
    latestMission?.strategy ??
    null;
  const missionId = council?.mission_id ?? latestMission?.id ?? null;
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
    if (!missionId) {
      setActivationError("No mission record is available yet. Run the Decision Center first.");
      return;
    }
    const pin = window.prompt("Operator PIN required to activate national mission playback");
    if (!pin) return;
    setActivating(true);
    setActivationError(null);
    try {
      await apiPostOperator(`/api/missions/${missionId}/activate`, pin);
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
      <div className="tactical-panel flex items-center justify-between px-4 py-3 bg-[#080d1a]/95">
        <div>
          <div className="label-terminal font-bold text-[#00f0ff]">Mission Execution Deck · {scenarioName}</div>
          <div className="text-base font-bold text-[#e6edf7] font-mono">{titleLine}</div>
          <div className="mt-0.5 text-[9px] uppercase tracking-[0.2em] text-[#5a677f] font-mono flex items-center gap-2">
            <span className="h-1.5 w-1.5 rounded-full bg-[#00f0ff] animate-pulse" />
            STATUS: {sourceLabel}
          </div>
        </div>

        <button
          disabled={!strategy || activated || activating}
          onClick={() => void launch()}
          className={cn(
            "flex items-center gap-2 rounded px-4 py-2 font-mono text-xs font-bold uppercase tracking-wider transition-all",
            activated
              ? "border border-emerald-500/50 bg-emerald-500/15 text-emerald-400 shadow-[0_0_16px_rgba(16,185,129,0.3)]"
              : "border border-[#00f0ff]/50 bg-[#00f0ff]/15 text-[#00f0ff] hover:bg-[#00f0ff]/25 shadow-[0_0_16px_rgba(0,240,255,0.3)] disabled:opacity-40",
          )}
        >
          <Rocket size={15} />
          {activated ? "MISSION ACTIVE" : activating ? "AUTHORISING PIN…" : "LAUNCH MISSION PLAYBOOK"}
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
            <MissionChecklist strategy={strategy} activated={activated} />
            <BriefingPack strategy={strategy} scenario={scenarioName} />
          </div>
        </>
      ) : councilLoading || missionLoading ? (
        <div className="tactical-panel grid flex-1 place-items-center p-8">
          <div className="text-center font-mono">
            <div className="text-sm font-bold text-[#00f0ff] animate-pulse">Generating Mission Playbook…</div>
            <p className="mt-1 text-xs text-[#8b99b3]">
              Synthesizing agent council consensus and persisted mission parameters.
            </p>
          </div>
        </div>
      ) : (
        <div className="tactical-panel grid flex-1 place-items-center p-8">
          <p className="text-xs font-mono text-[#8b99b3]">
            No mission record exists for this scenario yet. Run the Decision Center to generate
            one, then return here to activate playback.
          </p>
        </div>
      )}
    </div>
  );
}

function MissionChecklist({ strategy, activated }: { strategy: StrategyOption; activated: boolean }) {
  const [done, setDone] = useState<number>(0);

  // when activated, progress the checklist over time
  useEffect(() => {
    if (!activated) {
      setDone(0);
      return;
    }
    setDone(0);
    const id = setInterval(() => {
      setDone((d) => {
        if (d >= strategy.implementation_steps.length) {
          clearInterval(id);
          return d;
        }
        return d + 1;
      });
    }, 1100);
    return () => clearInterval(id);
  }, [activated, strategy.implementation_steps.length]);

  return (
    <div className="tactical-panel">
      <PanelHeader eyebrow="Operational Playbook" title="Action Checklist & Inter-Agency Sequence" />
      <div className="divide-y divide-[#1b2a4a]">
        {strategy.implementation_steps.map((step, i) => {
          const state = !activated ? "pending" : i < done ? "done" : i === done ? "active" : "pending";
          return (
            <motion.div
              key={i}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.05 }}
              className="flex items-start gap-3 px-4 py-3 hover:bg-[#0c1220]/50 transition-colors"
            >
              <span className="mt-0.5">
                {state === "done" ? (
                  <CheckCircle2 size={16} className="text-emerald-400" />
                ) : state === "active" ? (
                  <Loader2 size={16} className="animate-spin text-[#00f0ff]" />
                ) : (
                  <Circle size={16} className="text-[#5a677f]" />
                )}
              </span>
              <div className="min-w-0 flex-1">
                <div className="text-xs font-semibold text-[#e6edf7] font-mono">{step}</div>
                <div className="mt-1 flex items-center gap-2">
                  <span className="rounded bg-[#0c1220] border border-[#1b2a4a] px-2 py-0.5 font-mono text-[10px] uppercase text-[#00f0ff] font-bold">
                    {agencyFor(step)}
                  </span>
                  <span
                    className={cn(
                      "font-mono text-[10px] font-bold px-1.5 py-0.2 rounded",
                      i === 0 ? "bg-red-950/60 text-red-400 border border-red-800/40" : i <= 2 ? "bg-amber-950/60 text-amber-400 border border-amber-800/40" : "bg-[#0c1220] text-[#8b99b3]",
                    )}
                  >
                    {priorityFor(i)}
                  </span>
                  <span className="font-mono text-[10px] uppercase text-[#5a677f]">{state}</span>
                </div>
              </div>
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
        right={<FileText size={15} className="text-[#00f0ff]" />}
      />
      <div className="space-y-2.5 p-4">
        {briefs.map((b, i) => (
          <motion.div
            key={b.title}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.08 }}
            className="rounded border border-[#1b2a4a] bg-[#0c1220]/80 p-3 hover:border-[#00f0ff]/40 transition-colors"
          >
            <div className="mb-1 flex items-center justify-between text-xs font-bold text-[#00f0ff] font-mono">
              <span>{b.title}</span>
              <Download size={13} className="text-[#5a677f] hover:text-[#00f0ff] cursor-pointer" />
            </div>
            <p className="text-xs leading-relaxed text-[#8b99b3] font-sans">{b.body}</p>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
