"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { AlertTriangle, ExternalLink, Radio, TrendingUp, TrendingDown, Wind } from "lucide-react";
import { useIntelFeed, useSourceStatus } from "@/hooks/useChanakya";
import { Panel, PanelHeader, SeverityTag, ConfidenceBar } from "@/components/primitives";
import { SourceTag } from "@/components/primitives/SourceTag";
import { StatusLight } from "@/components/primitives/StatusLight";
import type { IntelEvent } from "@/lib/types";
import { cn, fmtUsd } from "@/lib/utils";

export function IntelligenceRoom() {
  const { data, isLoading, isError } = useIntelFeed();
  const { data: sourceData } = useSourceStatus();
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const events = data?.events ?? [];
  const selected = events.find((e) => e.id === selectedId) ?? events[0];

  return (
    <div className="flex h-full flex-col gap-3 overflow-hidden p-4 blueprint">
      {/* Threat summary strip */}
      <ThreatStrip data={data} loading={isLoading} error={isError} />
      <SourceStatusRail sources={sourceData?.sources ?? []} />

      <div className="grid min-h-0 flex-1 grid-cols-1 gap-3 lg:grid-cols-[1.4fr_1fr]">
        {/* Event stream */}
        <Panel className="flex min-h-0 flex-col">
          <PanelHeader
            eyebrow="Layer 1 · Situational Feed"
            title="Global Intelligence Stream"
            right={
              <span className="label-terminal">
                {events.length} events
              </span>
            }
          />
          <div className="min-h-0 flex-1 space-y-2 overflow-y-auto p-3">
            {isLoading && <SkeletonRows />}
            {events.map((ev, i) => (
              <EventRow
                key={ev.id}
                ev={ev}
                active={selected?.id === ev.id}
                index={i}
                onClick={() => setSelectedId(ev.id)}
              />
            ))}
          </div>
        </Panel>

        {/* Detail + markets */}
        <div className="flex min-h-0 flex-col gap-3">
          <PriceTicker data={data} />
          <Panel className="flex min-h-0 flex-1 flex-col">
            <PanelHeader eyebrow="Evidence Engine" title="Event Assessment" />
            <div className="min-h-0 flex-1 overflow-y-auto p-4">
              <AnimatePresence mode="wait">
                {selected ? (
                  <EventDetail key={selected.id} ev={selected} />
                ) : (
                  <p className="text-sm text-ink-muted">Select an event to inspect.</p>
                )}
              </AnimatePresence>
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}

function SourceStatusRail({ sources }: { sources: import("@/lib/types").SourceStatus[] }) {
  if (!sources.length) return null;
  return (
    <div className="flex gap-2 overflow-x-auto rounded-md border border-line bg-base/70 px-3 py-2">
      <span className="label-terminal mr-1 self-center">Sensors</span>
      {sources.map((source) => (
        <div key={source.source} className="flex shrink-0 items-center gap-1.5 rounded border border-line bg-panel/60 px-2 py-1">
          <span className="font-mono text-[10px] uppercase text-ink-muted">{source.source.replace("_", " ")}</span>
          <SourceTag kind={source.provenance} />
          <span className="readout text-[9px] text-ink-dim">{source.event_count}</span>
        </div>
      ))}
    </div>
  );
}

function ThreatStrip({ data, loading, error }: { data: any; loading: boolean; error: boolean }) {
  const s = data?.summary;
  const threat = (s?.threat_level ?? "nominal") as any;
  return (
    <Panel className="flex items-center justify-between gap-4 px-4 py-3">
      <div className="flex items-center gap-3">
        <StatusLight severity={threat} pulse size={12} />
        <div>
          <div className="label-terminal">National Threat Level</div>
          <div className="flex items-center gap-2">
            <SeverityTag severity={threat} />
            {error && <span className="text-xs text-critical">backend offline</span>}
            {loading && <span className="text-xs text-ink-dim">linking…</span>}
          </div>
        </div>
      </div>
      <div className="flex items-center gap-6">
        <Stat icon={<Radio size={14} />} label="Events" value={s?.event_count ?? "—"} />
        <Stat icon={<AlertTriangle size={14} />} label="Peak Risk" value={s?.peak_risk_score ? `${Math.round(s.peak_risk_score)}` : "—"} />
        <div className="hidden items-center gap-2 md:flex">
          <span className="label-terminal">Sources</span>
          {s?.provenance &&
            Object.keys(s.provenance).map((k) => <SourceTag key={k} kind={k} />)}
        </div>
      </div>
    </Panel>
  );
}

function Stat({ icon, label, value }: { icon: React.ReactNode; label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-ink-dim">{icon}</span>
      <div>
        <div className="label-terminal">{label}</div>
        <div className="readout text-sm font-semibold text-ink">{value}</div>
      </div>
    </div>
  );
}

function EventRow({
  ev,
  active,
  index,
  onClick,
}: {
  ev: IntelEvent;
  active: boolean;
  index: number;
  onClick: () => void;
}) {
  return (
    <motion.button
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: Math.min(index * 0.03, 0.3) }}
      onClick={onClick}
      className={cn(
        "group flex w-full items-start gap-3 rounded-md border px-3 py-2.5 text-left transition-colors",
        active
          ? "border-signal/40 bg-signal/5"
          : "border-line bg-panel/50 hover:border-line-strong hover:bg-panel",
      )}
    >
      <StatusLight severity={ev.severity} size={8} className="mt-1.5" />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="truncate text-sm font-medium text-ink">{ev.title}</span>
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-1.5">
          <SeverityTag severity={ev.severity} showDot={false} />
          <SourceTag kind={ev.source_kind} />
          {ev.stale && <span className="font-mono text-[10px] uppercase text-elevated">stale</span>}
          <span className="readout text-[10px] text-ink-dim">risk {Math.round(ev.risk_score)}</span>
          {ev.affected_corridors.map((c) => (
            <span key={c} className="rounded bg-energy/10 px-1.5 py-0.5 font-mono text-[10px] uppercase text-energy">
              {c}
            </span>
          ))}
        </div>
      </div>
    </motion.button>
  );
}

function EventDetail({ ev }: { ev: IntelEvent }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      className="space-y-4"
    >
      <div>
        <div className="flex items-center gap-2">
          <SeverityTag severity={ev.severity} />
          <SourceTag kind={ev.source_kind} />
        </div>
        <h3 className="mt-2 text-base font-semibold leading-snug text-ink">{ev.title}</h3>
        <p className="mt-1 text-sm text-ink-muted">{ev.summary}</p>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <ConfidenceBar value={ev.confidence} label="Confidence" />
        <ConfidenceBar value={ev.risk_score} label="Risk Score" accent="#f97316" />
      </div>

      <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
        <DetailRow label="Category" value={ev.category} />
        <DetailRow label="Est. Duration" value={ev.estimated_duration_days ? `${ev.estimated_duration_days} days` : "—"} />
        <DetailRow label="Countries" value={ev.affected_countries.join(", ") || "—"} />
        <DetailRow label="Corridors" value={ev.affected_corridors.join(", ") || "—"} />
        <DetailRow label="Source" value={ev.source} />
        <DetailRow label="Observed" value={new Date(ev.published_at).toLocaleString()} />
      </div>

      {ev.evidence.length > 0 && (
        <div>
          <div className="label-terminal mb-2">Supporting Evidence</div>
          <div className="space-y-1.5">
            {ev.evidence.map((e, i) => (
              <div key={i} className="rounded border border-line bg-panel/50 px-3 py-2">
                <div className="flex items-center justify-between gap-2">
                  <div className="text-xs font-medium text-ink">{e.label}</div>
                  {e.url && (
                    <a href={e.url} target="_blank" rel="noreferrer"
                       className="text-signal hover:text-white" aria-label="Open source evidence">
                      <ExternalLink size={12} />
                    </a>
                  )}
                </div>
                <div className="text-xs text-ink-muted">{e.detail}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </motion.div>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="label-terminal">{label}</div>
      <div className="truncate capitalize text-ink">{value}</div>
    </div>
  );
}

function PriceTicker({ data }: { data: any }) {
  const prices = data?.prices ?? [];
  const weather = (data?.weather ?? []).filter((w: any) => w.shipping_risk !== "nominal");
  return (
    <Panel className="p-3">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          {prices.map((p: any) => (
            <div key={p.symbol} className="flex items-center gap-2">
              <span className="label-terminal">{p.symbol}</span>
              <span className="readout text-sm font-semibold text-ink">{fmtUsd(p.price_usd)}</span>
              <span className={cn("flex items-center gap-0.5 readout text-xs", p.change_pct >= 0 ? "text-critical" : "text-nominal")}>
                {p.change_pct >= 0 ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
                {Math.abs(p.change_pct).toFixed(1)}%
              </span>
            </div>
          ))}
        </div>
        {weather.length > 0 && (
          <div className="flex items-center gap-1.5 text-xs text-elevated">
            <Wind size={13} />
            <span className="readout">{weather.length} weather alert{weather.length > 1 ? "s" : ""}</span>
          </div>
        )}
      </div>
    </Panel>
  );
}

function SkeletonRows() {
  return (
    <div className="space-y-2">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="h-14 animate-pulse rounded-md bg-panel/60" />
      ))}
    </div>
  );
}
