"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import { motion } from "framer-motion";
import { X, Map as MapIcon, Share2, Satellite } from "lucide-react";
import { useNetwork, useIntelFeed, useSourceStatus } from "@/hooks/useChanakya";
import { Panel, PanelHeader, MetricReadout } from "@/components/primitives";
import { SourceTag } from "@/components/primitives/SourceTag";
import { GraphView } from "./GraphView";
import type { MapMode, TwinSelection } from "./EnergyMap";
import type { NetworkData, SourceStatus } from "@/lib/types";
import { cn, fmtCompact } from "@/lib/utils";

const EnergyMap = dynamic(() => import("./EnergyMap"), {
  ssr: false,
  loading: () => (
    <div className="grid h-full place-items-center blueprint">
      <span className="label-terminal animate-pulse">Initializing digital twin…</span>
    </div>
  ),
});

type View = "map" | "graph";

export function DigitalTwinRoom() {
  const { data: network } = useNetwork();
  const { data: feed } = useIntelFeed();
  const { data: sourceData } = useSourceStatus();
  const [sel, setSel] = useState<TwinSelection | null>(null);
  const [view, setView] = useState<View>("map");
  const [mapMode, setMapMode] = useState<MapMode>("operations");
  const sources = sourceData?.sources ?? [];

  return (
    <div className="relative h-full">
      {/* View switch (top-center overlay) */}
      <div className="pointer-events-none absolute left-1/2 top-4 z-[500] -translate-x-1/2">
        <Panel className="pointer-events-auto flex items-center gap-1 p-1">
          <ViewTab active={view === "map"} onClick={() => setView("map")} icon={<MapIcon size={14} />} label="Geospatial" />
          <ViewTab active={view === "graph"} onClick={() => setView("graph")} icon={<Share2 size={14} />} label="Ontology Explorer" />
          {view === "map" && (
            <>
              <div className="mx-1 h-5 w-px bg-line" />
              <ViewTab
                active={mapMode === "operations"}
                onClick={() => setMapMode("operations")}
                icon={<MapIcon size={14} />}
                label="Ops"
              />
              <ViewTab
                active={mapMode === "satellite"}
                onClick={() => setMapMode("satellite")}
                icon={<Satellite size={14} />}
                label="Satellite"
              />
            </>
          )}
        </Panel>
      </div>

      {view === "graph" && <GraphView />}
      {view === "map" &&
        (network ? (
          <EnergyMap
            network={network}
            vessels={feed?.vessels ?? []}
            events={feed?.events ?? []}
            mapMode={mapMode}
            onSelect={setSel}
          />
        ) : (
          <div className="grid h-full place-items-center blueprint">
            <span className="label-terminal animate-pulse">Loading network…</span>
          </div>
        ))}

      {/* Aggregates strip (top-left overlay) */}
      {view === "map" && network && (
        <div className="pointer-events-none absolute left-4 top-4 z-[500]">
          <Panel className="pointer-events-auto flex items-center gap-5 px-4 py-2.5">
            <MetricReadout label="Refining" value={fmtCompact(network.aggregates.total_refining_capacity_kbpd * 1000)} unit="bbl/d" />
            <MetricReadout label="Imports" value={fmtCompact(network.aggregates.daily_crude_imports_kbpd * 1000)} unit="bbl/d" accent="#f59e0b" />
            <MetricReadout label="SPR Cover" value={network.aggregates.spr_coverage_days} unit="days" accent="#6366f1" />
            <MetricReadout label="HHI" value={network.aggregates.supplier_hhi} accent="#22d3ee" />
          </Panel>
        </div>
      )}

      {/* Legend (bottom-left) */}
      {view === "map" && (
        <div className="pointer-events-none absolute bottom-4 left-4 z-[500]">
          <Panel className="px-3 py-2">
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-ink-muted">
              <Legend color="#f59e0b" label="Supplier" />
              <Legend color="#22d3ee" label="Port" />
              <Legend color="#10b981" label="Refinery" />
              <Legend color="#6366f1" label="SPR" />
              <Legend color="#e6edf7" label="Tanker" />
              <Legend color="#ef4444" label="Satellite / risk event" />
            </div>
          </Panel>
        </div>
      )}

      {view === "map" && sources.length > 0 && (
        <div className="pointer-events-none absolute bottom-4 right-4 z-[500] w-[min(380px,calc(100vw-2rem))]">
          <SourceLayerPanel sources={sources} />
        </div>
      )}

      {/* Inspector (right overlay) */}
      {sel && network && (
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          className="absolute right-4 top-20 z-[500] w-80"
        >
          <Inspector sel={sel} network={network} onClose={() => setSel(null)} />
        </motion.div>
      )}
    </div>
  );
}

function ViewTab({
  active,
  onClick,
  icon,
  label,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "flex items-center gap-1.5 rounded px-3 py-1.5 text-xs font-medium transition-colors",
        active ? "bg-signal/15 text-signal" : "text-ink-dim hover:text-ink",
      )}
    >
      {icon}
      {label}
    </button>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <span className="flex items-center gap-1">
      <span className="h-2 w-2 rounded-full" style={{ backgroundColor: color }} />
      {label}
    </span>
  );
}

function SourceLayerPanel({ sources }: { sources: SourceStatus[] }) {
  const ordered = [...sources].sort((a, b) => {
    const order = ["gdelt", "open_meteo", "ais", "nasa_firms", "prices", "opensanctions", "ppac"];
    return order.indexOf(a.source) - order.indexOf(b.source);
  });

  return (
    <Panel className="pointer-events-auto px-3 py-2.5">
      <div className="mb-2 flex items-center justify-between gap-3">
        <div>
          <div className="label-terminal">Evidence Sources</div>
          <div className="text-[11px] text-ink-dim">Live status of map and intelligence layers</div>
        </div>
        <Satellite size={15} className="text-ink-dim" />
      </div>
      <div className="grid grid-cols-2 gap-1.5">
        {ordered.map((source) => (
          <div key={source.source} className="rounded border border-line bg-panel/70 px-2 py-1.5">
            <div className="flex items-center justify-between gap-2">
              <span className="truncate font-mono text-[10px] uppercase text-ink-muted">
                {labelForSource(source.source)}
              </span>
              <SourceTag kind={source.provenance} />
            </div>
            <div className="mt-1 flex items-center justify-between gap-2">
              <span className={cn("text-[10px]", source.healthy ? "text-nominal" : "text-critical")}>
                {source.healthy ? "connected" : "unavailable"}
              </span>
              <span className="readout text-[10px] text-ink-dim">{source.event_count}</span>
            </div>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function labelForSource(source: string): string {
  const labels: Record<string, string> = {
    ais: "AIS tankers",
    gdelt: "GDELT news",
    nasa_firms: "FIRMS thermal",
    open_meteo: "Open-Meteo",
    opensanctions: "Sanctions",
    ppac: "PPAC",
    prices: "Prices",
  };
  return labels[source] ?? source.replace("_", " ");
}

function Inspector({
  sel,
  network,
  onClose,
}: {
  sel: TwinSelection;
  network: NetworkData;
  onClose: () => void;
}) {
  const body = renderInspector(sel, network);
  return (
    <Panel raised>
      <PanelHeader
        eyebrow={sel.kind}
        title={body.title}
        right={
          <button onClick={onClose} className="text-ink-dim hover:text-ink">
            <X size={16} />
          </button>
        }
      />
      <div className="space-y-2 p-4 text-sm">{body.rows}</div>
    </Panel>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <span className="label-terminal">{label}</span>
      <span className="readout text-ink">{value}</span>
    </div>
  );
}

function renderInspector(sel: TwinSelection, net: NetworkData): { title: string; rows: React.ReactNode } {
  if (sel.kind === "refinery") {
    const r = net.refineries.find((x) => x.id === sel.id)!;
    return {
      title: r.name,
      rows: (
        <>
          <Row label="Operator" value={r.operator} />
          <Row label="Nameplate" value={`${r.nameplate_kbpd} kbpd`} />
          <Row label="Throughput" value={`${r.throughput_kbpd} kbpd`} />
          <Row label="Utilisation" value={`${r.utilization}%`} />
          <Row label="Crude grade" value={r.preferred_grade.replace("_", " ")} />
          <Row label="Inventory" value={`${r.inventory_days} days`} />
          <Row label="Coast" value={r.coast} />
          <Row label="Status" value={r.status} />
        </>
      ),
    };
  }
  if (sel.kind === "supplier") {
    const s = net.suppliers.find((x) => x.id === sel.id)!;
    return {
      title: s.country,
      rows: (
        <>
          <Row label="Import share" value={`${(s.import_share * 100).toFixed(0)}%`} />
          <Row label="Crude grade" value={s.grade.replace("_", " ")} />
          <Row label="Corridor" value={s.corridor_id} />
          <Row label="Reliability" value={`${s.reliability}/100`} />
          <Row label="Spare capacity" value={`${s.spare_capacity_kbpd} kbpd`} />
          <Row label="Sanctioned" value={s.sanctioned ? "Yes" : "No"} />
        </>
      ),
    };
  }
  if (sel.kind === "port") {
    const p = net.ports.find((x) => x.id === sel.id)!;
    return {
      title: p.name,
      rows: (
        <>
          <Row label="Coast" value={p.coast} />
          <Row label="Crude capacity" value={`${p.crude_capacity_kbpd} kbpd`} />
          <Row label="Status" value={p.status} />
        </>
      ),
    };
  }
  if (sel.kind === "reserve") {
    const r = net.reserves.find((x) => x.id === sel.id)!;
    return {
      title: r.name,
      rows: (
        <>
          <Row label="Capacity" value={`${r.capacity_mmt} MMT`} />
          <Row label="Fill" value={`${r.fill_pct}%`} />
          <Row label="Stored" value={`${r.stored_mmt} MMT`} />
        </>
      ),
    };
  }
  const c = net.corridors.find((x) => x.id === sel.id)!;
  return {
    title: c.name,
    rows: (
      <>
        <Row label="Chokepoint" value={c.chokepoint} />
        <Row label="Import share" value={`${(c.import_share * 100).toFixed(0)}%`} />
        <Row label="Transit" value={`${c.base_transit_days} days`} />
        <Row label="Status" value={c.status} />
      </>
    ),
  };
}
