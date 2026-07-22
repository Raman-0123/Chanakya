"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import { ROOMS } from "@/config/navigation";
import { cn } from "@/lib/utils";
import { LayoutDashboard, Radio } from "lucide-react";

export function NavRail() {
  const pathname = usePathname();
  const isHome = pathname === "/";

  return (
    <nav className="flex h-full w-14 shrink-0 flex-col items-center gap-2 border-r border-[#1b2a4a] bg-[#060a12]/95 py-3 backdrop-blur z-40 select-none">
      {/* Overview / Unified Command Desk Link */}
      <Link
        href="/"
        title="Unified Command Desk (Chakraview)"
        className={cn(
          "group relative grid h-10 w-10 place-items-center rounded border transition-all duration-200",
          isHome
            ? "border-[#00f0ff]/60 bg-[#00f0ff]/15 text-[#00f0ff] shadow-[0_0_12px_rgba(0,240,255,0.4)]"
            : "border-[#1b2a4a] bg-[#080d1a] text-[#5a677f] hover:border-[#00f0ff]/30 hover:text-[#e6edf7]"
        )}
      >
        <LayoutDashboard size={18} />
        <span className="pointer-events-none absolute left-14 z-50 hidden whitespace-nowrap rounded border border-[#1b2a4a] bg-[#0c1220] px-2.5 py-1 font-mono text-xs text-[#e6edf7] shadow-xl group-hover:block">
          <span className="text-[#00f0ff] font-bold">R0.</span> Unified Command Center
        </span>
      </Link>

      <div className="my-1 h-px w-8 bg-[#1b2a4a]" />

      {/* Six Operational Rooms */}
      <div className="flex flex-1 flex-col gap-1.5">
        {ROOMS.map((room) => {
          const active = !isHome && pathname.startsWith(room.href);
          const Icon = room.icon;
          return (
            <Link
              key={room.id}
              href={room.href}
              title={`Room ${room.room}: ${room.label}`}
              className={cn(
                "group relative grid h-10 w-10 place-items-center rounded transition-all duration-200 border",
                active
                  ? "border-[#00f0ff]/60 bg-[#00f0ff]/15 text-[#00f0ff] shadow-[0_0_14px_rgba(0,240,255,0.35)]"
                  : "border-transparent text-[#5a677f] hover:border-[#1b2a4a] hover:bg-[#080d1a] hover:text-[#e6edf7]"
              )}
            >
              {active && (
                <motion.span
                  layoutId="nav-active"
                  className="absolute -left-2.5 h-6 w-1 rounded-r bg-[#00f0ff] shadow-[0_0_10px_#00f0ff]"
                />
              )}
              <Icon size={18} strokeWidth={1.75} />
              <span className="pointer-events-none absolute left-14 z-50 hidden whitespace-nowrap rounded border border-[#1b2a4a] bg-[#0c1220] px-2.5 py-1.5 font-mono text-xs text-[#e6edf7] shadow-xl group-hover:block">
                <span className="text-[#00f0ff] font-bold">R{room.room}.</span> {room.label}
                <div className="text-[10px] text-[#8b99b3] font-sans font-normal mt-0.5">{room.description}</div>
              </span>
            </Link>
          );
        })}
      </div>

      {/* Live Stream Pulse Footer */}
      <div className="mt-auto flex flex-col items-center gap-1">
        <div className="grid h-8 w-8 place-items-center rounded bg-[#080d1a] border border-[#1b2a4a]" title="Live Event Pipeline Active">
          <Radio size={14} className="text-emerald-400 animate-pulse" />
        </div>
      </div>
    </nav>
  );
}
