import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

interface PanelProps {
  children: ReactNode;
  className?: string;
  raised?: boolean;
  onClick?: () => void;
}

/** Base operational surface. Everything in the command center sits on a Panel. */
export function Panel({ children, className, raised, onClick }: PanelProps) {
  return (
    <div
      onClick={onClick}
      className={cn(raised ? "surface-raised" : "surface", className)}
    >
      {children}
    </div>
  );
}

interface PanelHeaderProps {
  title: string;
  eyebrow?: string;
  right?: ReactNode;
  className?: string;
}

export function PanelHeader({ title, eyebrow, right, className }: PanelHeaderProps) {
  return (
    <div
      className={cn(
        "flex items-center justify-between gap-3 border-b border-line px-4 py-3",
        className,
      )}
    >
      <div className="min-w-0">
        {eyebrow && <div className="label-terminal">{eyebrow}</div>}
        <h3 className="truncate text-sm font-semibold text-ink">{title}</h3>
      </div>
      {right && <div className="flex shrink-0 items-center gap-2">{right}</div>}
    </div>
  );
}
