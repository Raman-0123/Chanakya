"use client";

import { usePathname } from "next/navigation";
import { ROOMS } from "@/config/navigation";
import { SecurityIndexGauge } from "@/components/primitives/SecurityIndexGauge";
import { LiveClock } from "./LiveClock";
import { SystemStatus } from "./SystemStatus";
import { useSecurityIndex } from "@/stores/useSecurityIndex";

/** Top operational status bar — identity, current room, NESI, clock, health. */
export function StatusBar() {
  const pathname = usePathname();
  const active = ROOMS.find((r) => pathname.startsWith(r.href));
  const nesi = useSecurityIndex((s) => s.value);
  const trend = useSecurityIndex((s) => s.trend);

  return (
    <header className="flex h-14 items-center justify-between border-b border-line bg-base/80 px-4 backdrop-blur">
      <div className="flex items-center gap-4">
        <div className="flex items-baseline gap-2">
          <span className="font-mono text-sm font-bold tracking-[0.2em] text-ink">
            CHANAKYA
          </span>
          <span className="hidden text-micro text-ink-dim md:inline">
            ENERGY CRISIS OPERATING SYSTEM
          </span>
        </div>
        {active && (
          <>
            <span className="text-ink-dim">/</span>
            <span className="label-terminal !text-signal">
              R{active.room} · {active.label}
            </span>
          </>
        )}
      </div>

      <div className="flex items-center gap-6">
        <SystemStatus />
        <div className="hidden h-6 w-px bg-line lg:block" />
        <LiveClock />
        <div className="h-6 w-px bg-line" />
        <div className="flex items-center gap-2">
          <span className="label-terminal hidden sm:inline">NESI</span>
          <SecurityIndexGauge value={nesi} trend={trend} />
        </div>
      </div>
    </header>
  );
}
