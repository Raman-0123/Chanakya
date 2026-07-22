"use client";

import { motion } from "framer-motion";
import { useSimulation } from "@/hooks/useChanakya";
import { useMission } from "@/stores/useMission";
import { Panel, PanelHeader } from "@/components/primitives";
import { SecurityIndexGauge } from "@/components/primitives/SecurityIndexGauge";
import type { SimulationResult } from "@/lib/types";
import { cn } from "@/lib/utils";

/** Live impact readout — recomputes instantly as scenario/levers change. */
export function ImpactReadout() {
  const { scenarioId, levers } = useMission();
  const { data: sim, isFetching } = useSimulation(scenarioId, levers);

  if (!sim)
    return (
      <Panel className="grid h-full place-items-center">
        <span className="label-terminal animate-pulse">Computing impact…</span>
      </Panel>
    );

  return (
    <div className="flex h-full flex-col gap-3 overflow-y-auto">
      {/* Headline + NESI */}
      <Panel className="relative overflow-hidden">
        <div className="pointer-events-none absolute inset-0 bg-radial-fade" />
        <div className="relative flex items-center justify-between gap-4 p-5">
          <div className="space-y-2">
            <div className="label-terminal">Simulation Result</div>
            <p className="max-w-lg text-sm leading-relaxed text-ink">{sim.headline}</p>
            {isFetching && <span className="label-terminal text-signal">recomputing…</span>}
          </div>
          <div className="flex items-center gap-4">
            <NesiDelta before={sim.nesi_before} after={sim.nesi_after.value} />
            <SecurityIndexGauge value={sim.nesi_after.value} size="lg" />
          </div>
        </div>
      </Panel>

      {/* Impact grid */}
      <Panel>
        <PanelHeader eyebrow="Cascading Impact" title="Projected Outcomes" />
        <div className="grid grid-cols-2 gap-px bg-line sm:grid-cols-3 lg:grid-cols-4">
          {sim.impact_lines.map((line) => (
            <ImpactCell key={line.label} line={line} />
          ))}
        </div>
      </Panel>

      {/* Supply cascade + assumptions */}
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        <SupplyCascade sim={sim} />
        <Panel>
          <PanelHeader eyebrow="Evidence Engine" title="Model Assumptions" />
          <ul className="space-y-1.5 p-4">
            {sim.assumptions.map((a, i) => (
              <li key={i} className="flex gap-2 text-xs text-ink-muted">
                <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-signal" />
                {a}
              </li>
            ))}
          </ul>
        </Panel>
      </div>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        <Panel>
          <PanelHeader eyebrow="Strategic Reserve Optimizer" title="Site Drawdown & Replenishment" />
          <div className="divide-y divide-line">
            {sim.spr_drawdown_plan.length ? sim.spr_drawdown_plan.map((site) => (
              <div key={site.site_id} className="grid grid-cols-[1fr_auto] gap-3 px-4 py-3">
                <div>
                  <div className="text-xs font-semibold text-ink">{site.site}</div>
                  <div className="mt-0.5 text-[10px] text-ink-muted">{site.rationale}</div>
                  <div className="mt-1 font-mono text-[9px] text-ink-dim">Feeds {site.served_refineries.join(" · ")}</div>
                </div>
                <div className="text-right font-mono">
                  <div className="text-sm font-bold text-signal">{site.release_kbpd.toLocaleString()} kbpd</div>
                  <div className="text-[9px] text-ink-dim">{site.sustainable_days.toFixed(0)}d sustainable · taper {site.taper_day ? `D${site.taper_day}` : "post-horizon"}</div>
                  <div className="text-[9px] text-nominal">replenish D{site.replenishment_from_day ?? "—"}</div>
                </div>
              </div>
            )) : <div className="p-4 text-xs text-ink-muted">No SPR draw selected for this response.</div>}
          </div>
        </Panel>

        <Panel>
          <PanelHeader eyebrow="Downstream Digital Twin" title="Refinery Run-Rate Projection" />
          <div className="max-h-64 overflow-y-auto divide-y divide-line">
            {sim.refinery_projections.slice(0, 8).map((refinery) => (
              <div key={refinery.refinery_id} className="flex items-center gap-3 px-4 py-2.5">
                <div className="min-w-0 flex-1">
                  <div className="truncate text-xs font-medium text-ink">{refinery.refinery}</div>
                  <div className="font-mono text-[9px] uppercase text-ink-dim">inventory {refinery.inventory_days}d · {refinery.status}</div>
                </div>
                <div className="w-28">
                  <div className="h-1.5 overflow-hidden rounded-full bg-line">
                    <div className="h-full bg-signal" style={{ width: `${Math.min(100, refinery.utilization_after_pct)}%` }} />
                  </div>
                </div>
                <div className="readout w-20 text-right text-[10px] text-ink">
                  {refinery.utilization_before_pct.toFixed(0)}→{refinery.utilization_after_pct.toFixed(0)}%
                </div>
              </div>
            ))}
          </div>
        </Panel>
      </div>

      {sim.feasibility_warnings.length > 0 && (
        <Panel className="border-elevated/40 bg-elevated/5 p-3">
          <div className="label-terminal text-elevated">Feasibility warnings</div>
          {sim.feasibility_warnings.map((warning) => <div key={warning} className="mt-1 text-xs text-ink-muted">• {warning}</div>)}
        </Panel>
      )}
    </div>
  );
}

function NesiDelta({ before, after }: { before: number; after: number }) {
  const delta = after - before;
  return (
    <div className="text-right">
      <div className="label-terminal">NESI Δ</div>
      <div className={cn("readout text-xl font-bold", delta < 0 ? "text-critical" : "text-nominal")}>
        {delta >= 0 ? "+" : ""}
        {delta.toFixed(0)}
      </div>
      <div className="readout text-[10px] text-ink-dim">
        {before.toFixed(0)} → {after.toFixed(0)}
      </div>
    </div>
  );
}

function ImpactCell({ line }: { line: SimulationResult["impact_lines"][number] }) {
  return (
    <motion.div
      key={line.value}
      initial={{ opacity: 0.4 }}
      animate={{ opacity: 1 }}
      className="bg-panel p-3"
    >
      <div className="label-terminal">{line.label}</div>
      <div className="readout mt-0.5 text-lg font-semibold text-ink">
        {line.value.toLocaleString()} <span className="text-xs text-ink-dim">{line.unit}</span>
      </div>
      <div className="mt-0.5 text-[10px] leading-tight text-ink-dim">{line.detail}</div>
    </motion.div>
  );
}

function SupplyCascade({ sim }: { sim: SimulationResult }) {
  const rows = [
    { label: "Gross supply gap", value: sim.supply_gap_kbpd, color: "#ef4444" },
    { label: "Rerouted", value: sim.rerouted_kbpd, color: "#22d3ee" },
    { label: "Spare-replaced", value: sim.replaced_spare_kbpd, color: "#10b981" },
    { label: "Spot procurement", value: sim.replaced_spot_kbpd, color: "#f59e0b" },
    { label: "SPR release", value: sim.spr_release_kbpd, color: "#6366f1" },
    { label: "Residual shortfall", value: sim.residual_shortfall_kbpd, color: "#ef4444" },
  ];
  const max = Math.max(...rows.map((r) => r.value), 1);
  return (
    <Panel>
      <PanelHeader eyebrow="Supply Chain" title="Mitigation Cascade (kbpd)" />
      <div className="space-y-2 p-4">
        {rows.map((r) => (
          <div key={r.label} className="flex items-center gap-3">
            <span className="w-32 shrink-0 text-xs text-ink-muted">{r.label}</span>
            <div className="h-2 flex-1 overflow-hidden rounded-full bg-line">
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{ width: `${(r.value / max) * 100}%`, backgroundColor: r.color }}
              />
            </div>
            <span className="readout w-14 shrink-0 text-right text-xs text-ink">
              {r.value.toLocaleString()}
            </span>
          </div>
        ))}
      </div>
    </Panel>
  );
}
