"use client";

import { useScenarios } from "@/hooks/useChanakya";
import { useMission } from "@/stores/useMission";
import { Panel, PanelHeader } from "@/components/primitives";
import { cn } from "@/lib/utils";

const CATEGORY_COLOR: Record<string, string> = {
  chokepoint: "#ef4444",
  market: "#f59e0b",
  sanctions: "#6366f1",
  weather: "#22d3ee",
  demand: "#eab308",
};

/** Scenario picker + response levers — writes to the shared mission store. */
export function ScenarioControls() {
  const { data: scenarios } = useScenarios();
  const { scenarioId, levers, setScenario, setLevers } = useMission();

  return (
    <div className="flex h-full flex-col gap-3">
      <Panel className="flex min-h-0 flex-1 flex-col">
        <PanelHeader eyebrow="Crisis Library" title="Select Scenario" />
        <div className="min-h-0 flex-1 space-y-1.5 overflow-y-auto p-3">
          {scenarios?.map((s) => (
            <button
              key={s.id}
              onClick={() => setScenario(s.id)}
              className={cn(
                "w-full rounded-md border px-3 py-2.5 text-left transition-colors",
                scenarioId === s.id
                  ? "border-signal/50 bg-signal/5"
                  : "border-line bg-panel/50 hover:border-line-strong",
              )}
            >
              <div className="flex items-center gap-2">
                <span
                  className="h-2 w-2 rounded-full"
                  style={{ backgroundColor: CATEGORY_COLOR[s.category] ?? "#8b99b3" }}
                />
                <span className="text-sm font-medium text-ink">{s.name}</span>
              </div>
              <p className="mt-1 line-clamp-2 text-xs text-ink-muted">{s.description}</p>
            </button>
          ))}
        </div>
      </Panel>

      <Panel>
        <PanelHeader eyebrow="Response Levers" title="Decision Variables" />
        <div className="space-y-4 p-4">
          <div>
            <div className="mb-1 flex items-center justify-between">
              <span className="label-terminal">SPR Release</span>
              <span className="readout text-sm font-semibold text-signal">
                {levers.spr_release_pct}%
              </span>
            </div>
            <input
              type="range"
              min={0}
              max={100}
              value={levers.spr_release_pct}
              onChange={(e) => setLevers({ spr_release_pct: Number(e.target.value) })}
              className="w-full accent-signal"
            />
          </div>
          <div className="flex gap-2">
            <Toggle
              label="Reroute"
              on={levers.enable_reroute}
              onClick={() => setLevers({ enable_reroute: !levers.enable_reroute })}
            />
            <Toggle
              label="Spot Buy"
              on={levers.enable_spot}
              onClick={() => setLevers({ enable_spot: !levers.enable_spot })}
            />
          </div>
        </div>
      </Panel>
    </div>
  );
}

function Toggle({ label, on, onClick }: { label: string; on: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "flex-1 rounded-md border px-3 py-2 font-mono text-xs uppercase tracking-wider transition-colors",
        on
          ? "border-nominal/50 bg-nominal/10 text-nominal"
          : "border-line bg-panel text-ink-dim",
      )}
    >
      {label} · {on ? "ON" : "OFF"}
    </button>
  );
}
