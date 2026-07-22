"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { X, Zap, AlertTriangle, ShieldAlert, ArrowRight, Activity } from "lucide-react";
import { useCascade } from "@/hooks/useChanakya";
import { Panel, PanelHeader, MetricReadout } from "@/components/primitives";
import type { CascadeImpact } from "@/lib/types";
import type { TwinSelection } from "./EnergyMap";
import { cn, fmtCompact } from "@/lib/utils";

const STATUS_COLOR: Record<string, string> = {
  offline: "#ef4444",
  critical: "#f97316",
  strained: "#eab308",
  elevated: "#eab308",
  nominal: "#10b981",
};

/**
 * The Palantir-style flow, driven by the quantified ontology cascade:
 *   1. PROBLEM   — operator blocks a node (port/corridor/supplier/refinery)
 *   2. VIOLATION — the system propagates magnitude: who starves, who's isolated
 *   3. ACT       — recommended response, SPR bridge, and next steps
 */
export function CascadePanel({
  node,
  onImpactedChange,
  onClose,
}: {
  node: TwinSelection;
  onImpactedChange: (impacted: Record<string, string>) => void;
  onClose: () => void;
}) {
  const [pct, setPct] = useState(100);
  const [run, setRun] = useState(false);
  const nodeId = `${node.kind}:${node.id}`;
  const { data, isFetching } = useCascade(nodeId, pct / 100, run);

  // reset when the selected node changes
  useEffect(() => {
    setRun(false);
    onImpactedChange({});
  }, [nodeId, onImpactedChange]);

  // push impacted refinery ids up to the map for highlighting
  useEffect(() => {
    if (!data) return;
    const map: Record<string, string> = {};
    for (const a of data.affected) {
      if (a.type === "refinery") map[a.id.split(":")[1]] = a.status;
    }
    onImpactedChange(map);
  }, [data, onImpactedChange]);

  const rollup = data?.rollup;

  return (
    <motion.div
      initial={{ opacity: 0, x: 24 }}
      animate={{ opacity: 1, x: 0 }}
      className="flex max-h-[calc(100vh-8rem)] w-[380px] flex-col"
    >
      <Panel raised className="flex min-h-0 flex-col">
        <PanelHeader
          eyebrow="Cascade Simulation"
          title={node.id.replace(/_/g, " ")}
          right={
            <button onClick={onClose} className="text-ink-dim hover:text-ink">
              <X size={16} />
            </button>
          }
        />

        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-4">
          {/* STEP 1 — PROBLEM */}
          <Step index={1} label="Problem" icon={<Zap size={13} />} accent="#22d3ee">
            <p className="text-xs text-ink-dim">
              Disrupt <span className="text-ink">{node.id.replace(/_/g, " ")}</span> and
              propagate the impact through the ontology.
            </p>
            <div className="mt-3">
              <div className="mb-1 flex items-center justify-between text-[11px]">
                <span className="label-terminal">Block level</span>
                <span className="readout text-signal">{pct}%</span>
              </div>
              <input
                type="range"
                min={10}
                max={100}
                step={5}
                value={pct}
                onChange={(e) => setPct(Number(e.target.value))}
                className="w-full accent-signal"
              />
            </div>
            <button
              onClick={() => setRun(true)}
              className="mt-3 flex w-full items-center justify-center gap-2 rounded bg-critical/15 px-3 py-2 text-xs font-semibold text-critical transition-colors hover:bg-critical/25"
            >
              <Activity size={13} />
              {isFetching ? "Propagating…" : "Run cascade"}
            </button>
          </Step>

          {/* STEP 2 — VIOLATION / IMPACT */}
          {rollup && data && (
            <Step index={2} label="Impact" icon={<AlertTriangle size={13} />} accent="#f97316">
              <div className="grid grid-cols-2 gap-2">
                <MetricReadout
                  label="Crude lost"
                  value={fmtCompact(rollup.total_crude_short_kbpd * 1000)}
                  unit="bbl/d"
                  accent="#ef4444"
                />
                <MetricReadout
                  label="of National"
                  value={rollup.pct_national_throughput}
                  unit="%"
                  accent="#f97316"
                />
                <MetricReadout label="Refineries hit" value={rollup.refineries_affected} />
                <MetricReadout
                  label="Isolated"
                  value={rollup.isolated_count}
                  accent="#ef4444"
                />
              </div>

              {data.macro_projection && (
                <div className="mt-3 rounded border border-line bg-panel/60 px-3 py-2 text-[11px]">
                  <div className="flex items-center justify-between">
                    <span className="label-terminal">Security Index</span>
                    <span className="readout text-ink">
                      {data.macro_projection.nesi_before.toFixed(0)} →{" "}
                      <span className="text-critical">
                        {data.macro_projection.nesi_after.toFixed(0)}
                      </span>{" "}
                      <span className="text-ink-dim">({data.macro_projection.nesi_band})</span>
                    </span>
                  </div>
                  <div className="mt-1 flex items-center justify-between">
                    <span className="label-terminal">Brent</span>
                    <span className="readout text-energy">
                      {data.macro_projection.brent_change_pct >= 0 ? "+" : ""}
                      {data.macro_projection.brent_change_pct.toFixed(1)}%
                    </span>
                  </div>
                </div>
              )}

              <div className="mt-3 space-y-1">
                {data.affected.slice(0, 7).map((a) => (
                  <ImpactRow key={a.id} impact={a} />
                ))}
              </div>
            </Step>
          )}

          {/* STEP 3 — ACT / RESPONSE */}
          {rollup && data && (
            <Step index={3} label="Act" icon={<ShieldAlert size={13} />} accent="#10b981">
              <p className="text-xs leading-relaxed text-ink-dim">{data.narrative}</p>
              <div className="mt-3 space-y-1.5">
                <ActionStep>
                  Strategic reserves bridge the gap for{" "}
                  <span className="text-nominal">~{rollup.spr_bridge_days.toFixed(0)} days</span> —
                  authorise phased SPR release to hold refinery run-rates.
                </ActionStep>
                <ActionStep>
                  Re-source{" "}
                  <span className="text-signal">
                    {fmtCompact(rollup.total_crude_short_kbpd * 1000)} bbl/d
                  </span>{" "}
                  via unaffected corridors; issue urgent spot tenders.
                </ActionStep>
                {rollup.isolated_count > 0 && (
                  <ActionStep>
                    Prioritise the{" "}
                    <span className="text-critical">{rollup.isolated_count} isolated refineries</span>{" "}
                    — no alternate intake without rerouting.
                  </ActionStep>
                )}
                <ActionStep>
                  Est. diesel output loss{" "}
                  <span className="text-energy">
                    {fmtCompact(rollup.est_diesel_output_loss_kbpd * 1000)} bbl/d
                  </span>{" "}
                  — brief fuel-security cell.
                </ActionStep>
              </div>
              <div className="mt-3 flex items-center gap-1.5 text-[11px] text-ink-muted">
                <ArrowRight size={12} />
                Convene the Council to rank a full response mission.
              </div>
            </Step>
          )}
        </div>
      </Panel>
    </motion.div>
  );
}

function Step({
  index,
  label,
  icon,
  accent,
  children,
}: {
  index: number;
  label: string;
  icon: React.ReactNode;
  accent: string;
  children: React.ReactNode;
}) {
  return (
    <div className="relative rounded-lg border border-line bg-panel/40 p-3">
      <div className="mb-2 flex items-center gap-2">
        <span
          className="grid h-6 w-6 place-items-center rounded-full text-[11px] font-bold"
          style={{ backgroundColor: `${accent}22`, color: accent }}
        >
          {index}
        </span>
        <span className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide" style={{ color: accent }}>
          {icon}
          {label}
        </span>
      </div>
      {children}
    </div>
  );
}

function ImpactRow({ impact }: { impact: CascadeImpact }) {
  const color = STATUS_COLOR[impact.status] ?? "#8aa0bf";
  return (
    <div className="flex items-center justify-between gap-2 rounded border border-line/60 bg-panel/50 px-2 py-1">
      <span className="flex items-center gap-1.5 truncate text-[11px] text-ink">
        <span className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: color }} />
        {impact.label}
        {impact.isolated && (
          <span className="rounded bg-critical/20 px-1 text-[9px] font-bold text-critical">ISOLATED</span>
        )}
      </span>
      <span className="readout shrink-0 text-[10px]" style={{ color }}>
        {impact.utilization_after !== null
          ? `${impact.utilization_before?.toFixed(0)}→${impact.utilization_after.toFixed(0)}%`
          : `-${fmtCompact(impact.crude_short_kbpd * 1000)}`}
      </span>
    </div>
  );
}

function ActionStep({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex gap-2 rounded border border-line/60 bg-panel/50 px-2.5 py-1.5 text-[11px] leading-relaxed text-ink-dim">
      <span className={cn("mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full bg-nominal")} />
      <span>{children}</span>
    </div>
  );
}
