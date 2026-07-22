"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowUpRight } from "lucide-react";
import { ROOMS, OPERATING_LOOP } from "@/config/navigation";
import { SecurityIndexGauge } from "@/components/primitives/SecurityIndexGauge";
import { Panel } from "@/components/primitives";
import { useSecurityIndex } from "@/stores/useSecurityIndex";

export default function OverviewPage() {
  const nesi = useSecurityIndex((s) => s.value);
  const trend = useSecurityIndex((s) => s.trend);

  return (
    <div className="h-full overflow-y-auto blueprint">
      <div className="mx-auto max-w-7xl space-y-6 p-6">
        {/* Posture header */}
        <Panel className="overflow-hidden">
          <div className="relative flex flex-col gap-6 p-6 md:flex-row md:items-center md:justify-between">
            <div className="pointer-events-none absolute inset-0 bg-radial-fade" />
            <div className="relative space-y-3">
              <div className="label-terminal">National Energy Security Posture</div>
              <h1 className="max-w-xl text-2xl font-semibold leading-tight text-ink">
                Sensing global disruption. Coordinating national response.
              </h1>
              <div className="flex flex-wrap items-center gap-1.5 pt-1">
                {OPERATING_LOOP.map((step, i) => (
                  <span key={step} className="flex items-center gap-1.5">
                    <span className="rounded border border-line-strong bg-panel px-2 py-0.5 font-mono text-micro uppercase tracking-wider text-ink-muted">
                      {step}
                    </span>
                    {i < OPERATING_LOOP.length - 1 && (
                      <span className="text-ink-dim">→</span>
                    )}
                  </span>
                ))}
              </div>
            </div>
            <div className="relative shrink-0">
              <SecurityIndexGauge value={nesi} trend={trend} size="lg" />
            </div>
          </div>
        </Panel>

        {/* Rooms grid */}
        <div>
          <div className="label-terminal mb-3">Operational Rooms</div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {ROOMS.map((room, i) => {
              const Icon = room.icon;
              return (
                <motion.div
                  key={room.id}
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.05, duration: 0.35 }}
                >
                  <Link href={room.href} className="group block h-full">
                    <Panel className="h-full p-5 transition-colors hover:border-signal/40 hover:shadow-glow-signal">
                      <div className="flex items-start justify-between">
                        <div className="grid h-10 w-10 place-items-center rounded-md border border-line-strong bg-panel-raised text-signal">
                          <Icon size={20} strokeWidth={1.75} />
                        </div>
                        <ArrowUpRight
                          size={16}
                          className="text-ink-dim transition-colors group-hover:text-signal"
                        />
                      </div>
                      <div className="mt-4">
                        <div className="label-terminal">Room {room.room}</div>
                        <h3 className="mt-0.5 text-base font-semibold text-ink">
                          {room.label}
                        </h3>
                        <p className="mt-1.5 text-sm leading-relaxed text-ink-muted">
                          {room.description}
                        </p>
                      </div>
                    </Panel>
                  </Link>
                </motion.div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
