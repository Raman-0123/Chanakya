import { cn } from "@/lib/utils";
import { SEVERITY_META, type Severity } from "@/lib/severity";

interface SeverityTagProps {
  severity: Severity;
  className?: string;
  showDot?: boolean;
}

export function SeverityTag({ severity, className, showDot = true }: SeverityTagProps) {
  const meta = SEVERITY_META[severity];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded border px-2 py-0.5 font-mono text-micro uppercase tracking-wider",
        className,
      )}
      style={{
        color: meta.color,
        borderColor: `${meta.color}55`,
        backgroundColor: `${meta.color}12`,
      }}
    >
      {showDot && (
        <span
          className="h-1.5 w-1.5 rounded-full"
          style={{ backgroundColor: meta.color, boxShadow: `0 0 6px ${meta.color}` }}
        />
      )}
      {meta.label}
    </span>
  );
}
