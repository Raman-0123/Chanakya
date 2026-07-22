import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

interface MetricReadoutProps {
  label: string;
  value: ReactNode;
  unit?: string;
  delta?: number;
  accent?: string;
  className?: string;
}

/** Terminal-style KPI: micro label over a large mono value with optional delta. */
export function MetricReadout({
  label,
  value,
  unit,
  delta,
  accent = "#e6edf7",
  className,
}: MetricReadoutProps) {
  const deltaColor =
    delta === undefined ? "" : delta > 0 ? "text-critical" : delta < 0 ? "text-nominal" : "text-ink-dim";
  return (
    <div className={cn("space-y-1", className)}>
      <div className="label-terminal">{label}</div>
      <div className="flex items-baseline gap-1.5">
        <span className="readout text-2xl font-semibold leading-none" style={{ color: accent }}>
          {value}
        </span>
        {unit && <span className="text-xs text-ink-dim">{unit}</span>}
        {delta !== undefined && (
          <span className={cn("readout text-xs font-medium", deltaColor)}>
            {delta > 0 ? "▲" : delta < 0 ? "▼" : "—"} {Math.abs(delta).toFixed(1)}
          </span>
        )}
      </div>
    </div>
  );
}
