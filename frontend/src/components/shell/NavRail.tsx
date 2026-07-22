"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import { ROOMS } from "@/config/navigation";
import { cn } from "@/lib/utils";
import { useTheme } from "next-themes";
import { LayoutDashboard, Radio, Sun, Moon } from "lucide-react";

export function NavRail() {
  const pathname = usePathname();
  const isHome = pathname === "/";

  const { theme, setTheme } = useTheme();

  return (
    <nav className="flex h-full w-14 shrink-0 flex-col items-center gap-2 border-r border-line bg-panel/95 py-3 backdrop-blur-md z-40 select-none">
      {/* Overview / Unified Command Desk Link */}
      <Link
        href="/"
        title="Unified Command Desk (Chakraview)"
        className={cn(
          "group relative grid h-10 w-10 place-items-center rounded border transition-all duration-200",
          isHome
            ? "border-signal/60 bg-signal/15 text-signal shadow-glow-signal"
            : "border-line bg-panel-hover text-ink-dim hover:border-signal/30 hover:text-ink"
        )}
      >
        <LayoutDashboard size={18} />
        <span className="pointer-events-none absolute left-14 z-50 hidden whitespace-nowrap rounded border border-line bg-panel-hover px-2.5 py-1 font-mono text-xs text-ink shadow-xl group-hover:block">
          <span className="text-signal font-bold">R0.</span> Unified Command Center
        </span>
      </Link>

      <div className="my-1 h-px w-8 bg-line" />

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
                  ? "border-signal/60 bg-signal/15 text-signal shadow-glow-signal"
                  : "border-transparent text-ink-dim hover:border-line hover:bg-panel-hover hover:text-ink"
              )}
            >
              {active && (
                <motion.span
                  layoutId="nav-active"
                  className="absolute -left-2.5 h-6 w-1 rounded-r bg-signal shadow-glow-signal"
                />
              )}
              <Icon size={18} strokeWidth={1.75} />
              <span className="pointer-events-none absolute left-14 z-50 hidden whitespace-nowrap rounded border border-line bg-panel-hover px-2.5 py-1.5 font-mono text-xs text-ink shadow-xl group-hover:block">
                <span className="text-signal font-bold">R{room.room}.</span> {room.label}
                <div className="text-[10px] text-ink-muted font-sans font-normal mt-0.5">{room.description}</div>
              </span>
            </Link>
          );
        })}
      </div>

      {/* Live Stream Pulse Footer */}
      <div className="mt-auto flex flex-col items-center gap-3">
        <button
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          className="grid h-8 w-8 place-items-center rounded border border-line bg-panel-hover text-ink-dim hover:border-signal/30 hover:text-ink transition-colors"
          title="Toggle Theme"
        >
          {theme === "dark" ? <Sun size={15} /> : <Moon size={15} />}
        </button>

        <div className="grid h-8 w-8 place-items-center rounded bg-panel-hover border border-line" title="Live Event Pipeline Active">
          <Radio size={14} className="text-emerald-400 animate-pulse" />
        </div>
      </div>
    </nav>
  );
}
