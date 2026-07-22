/**
 * Shared operational severity model. One source of truth for the colors,
 * labels, and thresholds used across events, risk scores, and status lights.
 */

export type Severity = "nominal" | "elevated" | "high" | "critical";

export const SEVERITY_ORDER: Severity[] = [
  "nominal",
  "elevated",
  "high",
  "critical",
];

export const SEVERITY_META: Record<
  Severity,
  { label: string; color: string; text: string; ring: string; glow: string }
> = {
  nominal: {
    label: "Nominal",
    color: "#10b981",
    text: "text-nominal",
    ring: "ring-nominal/40",
    glow: "shadow-glow-nominal",
  },
  elevated: {
    label: "Elevated",
    color: "#eab308",
    text: "text-elevated",
    ring: "ring-elevated/40",
    glow: "",
  },
  high: {
    label: "High",
    color: "#f97316",
    text: "text-high",
    ring: "ring-high/40",
    glow: "",
  },
  critical: {
    label: "Critical",
    color: "#ef4444",
    text: "text-critical",
    ring: "ring-critical/50",
    glow: "shadow-glow-critical",
  },
};

/** Map a 0–100 risk score to a severity band. */
export function severityFromScore(score: number): Severity {
  if (score >= 75) return "critical";
  if (score >= 50) return "high";
  if (score >= 25) return "elevated";
  return "nominal";
}
