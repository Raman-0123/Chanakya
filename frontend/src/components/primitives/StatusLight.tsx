import { cn } from "@/lib/utils";
import { SEVERITY_META, type Severity } from "@/lib/severity";

interface StatusLightProps {
  severity?: Severity;
  pulse?: boolean;
  size?: number;
  className?: string;
}

/** A glowing operational status dot with an optional radar-pulse ring. */
export function StatusLight({
  severity = "nominal",
  pulse = false,
  size = 8,
  className,
}: StatusLightProps) {
  const color = SEVERITY_META[severity].color;
  return (
    <span
      className={cn("relative inline-flex", className)}
      style={{ width: size, height: size }}
    >
      {pulse && (
        <span
          className="absolute inset-0 animate-pulse-ring rounded-full"
          style={{ backgroundColor: color }}
        />
      )}
      <span
        className="relative inline-flex rounded-full"
        style={{
          width: size,
          height: size,
          backgroundColor: color,
          boxShadow: `0 0 8px ${color}`,
        }}
      />
    </span>
  );
}
