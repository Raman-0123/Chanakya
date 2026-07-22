import { cn } from "@/lib/utils";
import { severityFromScore, SEVERITY_META } from "@/lib/severity";

interface SecurityIndexGaugeProps {
  /** 0–100 National Energy Security Index (higher = more secure). */
  value: number;
  trend?: number;
  size?: "sm" | "lg";
  className?: string;
}

/**
 * National Energy Security Index — the single resilience number. Rendered as a
 * radial gauge. Note: a LOW index is dangerous, so we invert the severity band
 * (a low security score maps to a critical color).
 */
export function SecurityIndexGauge({
  value,
  trend,
  size = "sm",
  className,
}: SecurityIndexGaugeProps) {
  const severity = severityFromScore(100 - value); // invert: low security = critical
  const color = SEVERITY_META[severity].color;
  const dim = size === "lg" ? 120 : 44;
  const stroke = size === "lg" ? 9 : 4;
  const r = (dim - stroke) / 2;
  const c = 2 * Math.PI * r;
  const offset = c * (1 - value / 100);

  return (
    <div className={cn("flex items-center gap-3", className)}>
      <div className="relative" style={{ width: dim, height: dim }}>
        <svg width={dim} height={dim} className="-rotate-90">
          <circle
            cx={dim / 2}
            cy={dim / 2}
            r={r}
            fill="none"
            stroke="#1b2536"
            strokeWidth={stroke}
          />
          <circle
            cx={dim / 2}
            cy={dim / 2}
            r={r}
            fill="none"
            stroke={color}
            strokeWidth={stroke}
            strokeDasharray={c}
            strokeDashoffset={offset}
            strokeLinecap="round"
            style={{
              filter: `drop-shadow(0 0 4px ${color})`,
              transition: "stroke-dashoffset 700ms ease, stroke 400ms ease",
            }}
          />
        </svg>
        <div className="absolute inset-0 grid place-items-center">
          <span
            className={cn("readout font-bold", size === "lg" ? "text-3xl" : "text-sm")}
            style={{ color }}
          >
            {Math.round(value)}
          </span>
        </div>
      </div>
      {size === "lg" && (
        <div>
          <div className="label-terminal">Energy Security Index</div>
          <div className="text-sm font-semibold" style={{ color }}>
            {SEVERITY_META[severity].label === "Critical"
              ? "Critical Exposure"
              : SEVERITY_META[severity].label}
          </div>
          {trend !== undefined && (
            <div
              className={cn(
                "readout text-xs",
                trend >= 0 ? "text-nominal" : "text-critical",
              )}
            >
              {trend >= 0 ? "▲" : "▼"} {Math.abs(trend).toFixed(1)} 24h
            </div>
          )}
        </div>
      )}
    </div>
  );
}
