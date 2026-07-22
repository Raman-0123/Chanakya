"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import { ROOMS } from "@/config/navigation";
import { cn } from "@/lib/utils";

/** Left navigation rail — the six operational rooms as an icon column. */
export function NavRail() {
  const pathname = usePathname();

  return (
    <nav className="flex h-full w-16 flex-col items-center gap-1 border-r border-line bg-base/90 py-3 backdrop-blur">
      <Link href="/" className="mb-3 grid place-items-center">
        <div className="grid h-9 w-9 place-items-center rounded-md border border-signal/40 bg-signal/10 shadow-glow-signal">
          <span className="font-mono text-sm font-bold text-signal">C</span>
        </div>
      </Link>

      <div className="flex flex-1 flex-col gap-1">
        {ROOMS.map((room) => {
          const active = pathname.startsWith(room.href);
          const Icon = room.icon;
          return (
            <Link
              key={room.id}
              href={room.href}
              title={`${room.room}. ${room.label}`}
              className={cn(
                "group relative grid h-11 w-11 place-items-center rounded-md transition-colors",
                active
                  ? "bg-signal/10 text-signal"
                  : "text-ink-dim hover:bg-panel hover:text-ink",
              )}
            >
              {active && (
                <motion.span
                  layoutId="nav-active"
                  className="absolute -left-3 h-6 w-1 rounded-full bg-signal shadow-glow-signal"
                />
              )}
              <Icon size={19} strokeWidth={1.75} />
              <span className="pointer-events-none absolute left-14 z-50 hidden whitespace-nowrap rounded border border-line-strong bg-panel-raised px-2 py-1 text-xs text-ink shadow-panel group-hover:block">
                <span className="font-mono text-ink-dim">R{room.room}</span>{" "}
                {room.label}
              </span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
