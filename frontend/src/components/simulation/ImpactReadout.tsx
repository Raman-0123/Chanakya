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
