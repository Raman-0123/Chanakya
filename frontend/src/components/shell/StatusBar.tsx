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
    <header className="flex h-12 shrink-0 items-center justify-between border-b border-[#1b2a4a] bg-[#060a12]/95 px-4 backdrop-blur z-40 select-none">
      {/* Left Identity & Classification */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <div className="grid h-6 w-6 place-items-center rounded bg-[#00f0ff]/10 border border-[#00f0ff]/40 shadow-[0_0_10px_rgba(0,240,255,0.3)]">
            <Shield size={13} className="text-[#00f0ff]" />
          </div>
          <span className="font-mono text-xs font-bold tracking-[0.25em] text-[#e6edf7]">
            CHANAKYA
          </span>
        </div>

        <span className="hidden font-mono text-[9px] uppercase tracking-wider text-[#5a677f] md:inline border-l border-[#1b2a4a] pl-3">
          NATIONAL ENERGY SECURITY OPERATING SYSTEM
        </span>

        {/* Classification Badge */}
        <span className="hidden lg:inline font-mono text-[9px] uppercase tracking-widest px-2 py-0.5 rounded bg-red-950/40 text-red-400 border border-red-800/40">
          RESTRICTED // GOVT OF INDIA
        </span>

        {active && (
          <div className="flex items-center gap-2 border-l border-[#1b2a4a] pl-3">
            <span className="font-mono text-[10px] uppercase font-bold text-[#00f0ff] flex items-center gap-1">
              <span className="h-1.5 w-1.5 rounded-full bg-[#00f0ff] animate-ping" />
              R{active.room} · {active.label}
            </span>
          </div>
        )}
      </div>

      {/* Center Threat Posture Indicator */}
      <div className="hidden xl:flex items-center gap-2 px-3 py-1 rounded bg-[#080d1a] border border-[#1b2a4a]">
        <Activity size={13} className={isThreatHigh ? "text-red-500 animate-pulse" : "text-emerald-400"} />
        <span className="font-mono text-[10px] uppercase tracking-wider text-[#8b99b3]">POSTURE:</span>
        <span className={`font-mono text-[10px] font-bold uppercase tracking-wider ${isThreatHigh ? "text-red-400" : "text-emerald-400"}`}>
          {isThreatHigh ? "DEFCON 2 // HIGH ALERT" : "DEFCON 4 // NOMINAL"}
        </span>
      </div>

      {/* Right Telemetry, Clocks & NESI */}
      <div className="flex items-center gap-4">
        <SystemStatus />
        <div className="hidden h-4 w-px bg-[#1b2a4a] lg:block" />
        <LiveClock />
        <div className="h-4 w-px bg-[#1b2a4a]" />
        <div className="flex items-center gap-2">
          <span className="font-mono text-[10px] uppercase tracking-wider text-[#5a677f] hidden sm:inline">NESI INDEX:</span>
          <SecurityIndexGauge value={nesi} trend={trend} size="sm" />
        </div>
      </div>
    </header>
  );
}
