"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Rocket, FileText, CheckCircle2, Circle, Loader2 } from "lucide-react";
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
    ? "Live council"
    : latestMission
      ? "Recovered mission"
      : "Waiting for mission";
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
    const pin = window.prompt("Operator PIN required to activate this mission");
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
    <div className="flex h-full flex-col gap-3 overflow-y-auto p-4 blueprint">
      <Panel className="flex items-center justify-between px-4 py-3">
        <div>
          <div className="label-terminal">Mission Execution · {scenarioName}</div>
          <div className="text-sm font-semibold text-ink">{titleLine}</div>
          <div className="mt-0.5 text-[11px] uppercase tracking-[0.2em] text-ink-dim">
            {sourceLabel}
          </div>
        </div>
        <button
          disabled={!strategy || activated || activating}
          onClick={() => void launch()}
          className={cn(
            "flex items-center gap-2 rounded-md border px-4 py-2 text-xs font-semibold uppercase tracking-wider transition-colors",
            activated
              ? "border-nominal/40 bg-nominal/10 text-nominal"
              : "border-signal/40 bg-signal/10 text-signal hover:bg-signal/20 disabled:opacity-40",
          )}
        >
          <Rocket size={14} />
          {activated ? "Mission Active" : activating ? "Authorising…" : "Launch Mission"}
        </button>
      </Panel>
      {activationError && (
        <div className="rounded border border-critical/40 bg-critical/10 px-3 py-2 text-xs text-critical">
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
        <Panel className="grid flex-1 place-items-center">
          <div className="text-center">
            <div className="text-sm font-semibold text-ink">Generating mission brief…</div>
            <p className="mt-1 text-sm text-ink-muted">
              Pulling the latest council result and persisted mission record.
            </p>
          </div>
        </Panel>
      ) : (
        <Panel className="grid flex-1 place-items-center">
          <p className="text-sm text-ink-muted">
            No mission record exists for this scenario yet. Run the Decision Center to generate
            one, then return here.
          </p>
        </Panel>
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
    <Panel>
      <PanelHeader eyebrow="Operational Playbook" title="Mission Checklist" />
      <div className="divide-y divide-line">
        {strategy.implementation_steps.map((step, i) => {
          const state = !activated ? "pending" : i < done ? "done" : i === done ? "active" : "pending";
          return (
            <motion.div
              key={i}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.05 }}
              className="flex items-start gap-3 px-4 py-3"
            >
              <span className="mt-0.5">
                {state === "done" ? (
                  <CheckCircle2 size={16} className="text-nominal" />
                ) : state === "active" ? (
                  <Loader2 size={16} className="animate-spin text-signal" />
                ) : (
                  <Circle size={16} className="text-ink-dim" />
                )}
              </span>
              <div className="min-w-0 flex-1">
                <div className="text-sm text-ink">{step}</div>
                <div className="mt-0.5 flex items-center gap-2">
                  <span className="rounded bg-panel px-1.5 py-0.5 font-mono text-[10px] uppercase text-ink-muted">
                    {agencyFor(step)}
                  </span>
                  <span
                    className={cn(
                      "font-mono text-[10px]",
                      i === 0 ? "text-critical" : i <= 2 ? "text-elevated" : "text-ink-dim",
                    )}
                  >
                    {priorityFor(i)}
                  </span>
                  <span className="font-mono text-[10px] uppercase text-ink-dim">{state}</span>
                </div>
              </div>
            </motion.div>
          );
        })}
      </div>
    </Panel>
  );
}

function BriefingPack({ strategy, scenario }: { strategy: StrategyOption; scenario: string }) {
  const p = strategy.projection;
  const briefs = [
    {
      title: "Cabinet Committee Brief",
      body: `Scenario: ${scenario}. Recommended posture: ${strategy.title}. Projected national refinery utilisation ${p.national_utilization_pct.toFixed(
        0,
      )}%, residual shortfall ${p.residual_shortfall_kbpd.toLocaleString()} kbpd, security index ${p.nesi_after.toFixed(
        0,
      )}. Crude price impact ${p.brent_change_pct >= 0 ? "+" : ""}${p.brent_change_pct.toFixed(0)}%.`,
    },
    {
      title: "Procurement Order",
      body: `Issue urgent replacement sourcing. Activate spare capacity and spot tenders to cover the supply gap; sequence cargoes to sustain refinery run rates. Estimated incremental cost ~$${p.est_daily_cost_musd.toFixed(
        1,
      )}M/day.`,
    },
    {
      title: "SPR Release Plan",
      body: `Authorise phased drawdown of ${p.spr_release_kbpd.toLocaleString()} kbpd across Visakhapatnam, Mangalore and Padur, sustainable ~${p.spr_days_remaining.toFixed(
        0,
      )} days at this rate. Refill behind replacement cargoes.`,
    },
    {
      title: "Public Advisory (Finance / MoPNG)",
      body: `Projected diesel ₹${p.diesel_projected_inr.toFixed(
        1,
      )}/L. Prepare fiscal buffer and consumer-communication plan to manage pass-through and prevent panic demand.`,
    },
  ];
  return (
    <Panel>
      <PanelHeader
        eyebrow="Mission Report Generator"
        title="Executive Briefing Pack"
        right={<FileText size={15} className="text-ink-dim" />}
      />
      <div className="space-y-2.5 p-4">
        {briefs.map((b, i) => (
          <motion.div
            key={b.title}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.08 }}
            className="rounded-md border border-line bg-panel/50 p-3"
          >
            <div className="mb-1 text-sm font-semibold text-signal">{b.title}</div>
            <p className="text-xs leading-relaxed text-ink-muted">{b.body}</p>
          </motion.div>
        ))}
      </div>
    </Panel>
  );
}
