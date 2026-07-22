import { cn } from "@/lib/utils";

const META: Record<string, { label: string; color: string }> = {
  live: { label: "LIVE", color: "#10b981" },
  cached: { label: "CACHED", color: "#22d3ee" },
  replay: { label: "REPLAY", color: "#f59e0b" },
  simulated: { label: "SIM", color: "#8b99b3" },
  unavailable: { label: "N/A", color: "#ef4444" },
  llm: { label: "LLM", color: "#6366f1" },
  grounded: { label: "GROUNDED", color: "#22d3ee" },
};

/** Provenance badge — the platform is always honest about where data came from. */
export function SourceTag({ kind, className }: { kind: string; className?: string }) {
  const m = META[kind] ?? { label: kind.toUpperCase(), color: "#8b99b3" };
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded px-1.5 py-0.5 font-mono text-[10px] font-medium uppercase tracking-wider",
        className,
      )}
      style={{ color: m.color, backgroundColor: `${m.color}18`, border: `1px solid ${m.color}44` }}
    >
      {kind === "live" && (
        <span className="h-1 w-1 animate-flicker rounded-full" style={{ backgroundColor: m.color }} />
      )}
      {m.label}
    </span>
  );
}
