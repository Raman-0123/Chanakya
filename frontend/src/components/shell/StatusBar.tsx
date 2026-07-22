"use client";

import { usePathname } from "next/navigation";
import { ROOMS } from "@/config/navigation";
import { SecurityIndexGauge } from "@/components/primitives/SecurityIndexGauge";
import { LiveClock } from "./LiveClock";
import { SystemStatus } from "./SystemStatus";
import { useSecurityIndex } from "@/stores/useSecurityIndex";
import { Shield, ShieldAlert, Activity, Wifi } from "lucide-react";

export function StatusBar() {
  const pathname = usePathname();
  const active = ROOMS.find((r) => pathname.startsWith(r.href));
  const nesi = useSecurityIndex((s) => s.value);
  const trend = useSecurityIndex((s) => s.trend);

  const isThreatHigh = nesi < 65;

  return (
    <header className="flex h-12 shrink-0 items-center justify-between border-b border-line bg-panel/95 px-4 backdrop-blur-md z-40 select-none">
      {/* Left Identity & Classification */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <div className="grid h-6 w-6 place-items-center rounded bg-signal/10 border border-signal/40 shadow-glow-signal">
            <Shield size={13} className="text-signal" />
          </div>
          <span className="font-mono text-xs font-bold tracking-[0.25em] text-ink">
            CHANAKYA
          </span>
        </div>

        <span className="hidden font-mono text-[9px] uppercase tracking-wider text-ink-dim md:inline border-l border-line pl-3">
          NATIONAL ENERGY SECURITY OPERATING SYSTEM
        </span>

        {/* Classification Badge */}
        <span className="hidden lg:inline font-mono text-[9px] uppercase tracking-widest px-2 py-0.5 rounded bg-red-950/40 text-red-400 border border-red-800/40">
          RESTRICTED // GOVT OF INDIA
        </span>

        {active && (
          <div className="flex items-center gap-2 border-l border-line pl-3">
            <span className="font-mono text-[10px] uppercase font-bold text-signal flex items-center gap-1">
              <span className="h-1.5 w-1.5 rounded-full bg-signal animate-ping" />
              R{active.room} · {active.label}
            </span>
          </div>
        )}
      </div>

      {/* Center Threat Posture Indicator */}
      <div className="hidden xl:flex items-center gap-2 px-3 py-1 rounded bg-panel border border-line">
        <Activity size={13} className={isThreatHigh ? "text-red-500 animate-pulse" : "text-emerald-400"} />
        <span className="font-mono text-[10px] uppercase tracking-wider text-ink-muted">POSTURE:</span>
        <span className={`font-mono text-[10px] font-bold uppercase tracking-wider ${isThreatHigh ? "text-red-500" : "text-emerald-500"}`}>
          {isThreatHigh ? "DEFCON 2 // HIGH ALERT" : "DEFCON 4 // NOMINAL"}
        </span>
      </div>

      {/* Right Telemetry, Clocks & NESI */}
      <div className="flex items-center gap-4">
        <SystemStatus />
        <div className="hidden h-4 w-px bg-line lg:block" />
        <LiveClock />
        <div className="h-4 w-px bg-line" />
        <div className="flex items-center gap-2">
          <span className="font-mono text-[10px] uppercase tracking-wider text-ink-dim hidden sm:inline">NESI INDEX:</span>
          <SecurityIndexGauge value={nesi} trend={trend} size="sm" />
        </div>
      </div>
    </header>
  );
}
