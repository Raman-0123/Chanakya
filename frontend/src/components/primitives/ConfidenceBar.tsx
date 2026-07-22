import { cn } from "@/lib/utils";
import { clamp } from "@/lib/utils";

interface ConfidenceBarProps {
  /** 0–100 */
  value: number;
  label?: string;
  className?: string;
  accent?: string;
}

/** Confidence / probability meter — a labelled segmented bar. */
export function ConfidenceBar({
  value,
  label = "Confidence",
  className,
  accent = "#22d3ee",
}: ConfidenceBarProps) {
  const v = clamp(value);
  return (
    <div className={cn("space-y-1", className)}>
      <div className="flex items-center justify-between">
        <span className="label-terminal">{label}</span>
        <span className="readout text-xs font-semibold" style={{ color: accent }}>
          {Math.round(v)}%
        </span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-line">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{
            width: `${v}%`,
            background: `linear-gradient(90deg, ${accent}55, ${accent})`,
            boxShadow: `0 0 10px ${accent}88`,
          }}
        />
      </div>
    </div>
  );
}
