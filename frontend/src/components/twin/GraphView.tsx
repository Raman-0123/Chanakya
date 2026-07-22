"use client";

import { useState, useMemo, useCallback } from "react";
import ReactFlow, {
  Background,
  Controls,
  type Node,
  type Edge,
  MarkerType,
  BackgroundVariant,
} from "reactflow";
import "reactflow/dist/style.css";
import { Search, Zap, Eye, X, Database, Filter, Layers, HelpCircle } from "lucide-react";
import {
  useGraph,
  useOntologyExplore,
  useOntologyImpact,
  useOntologySearch,
  useOntologyStats,
} from "@/hooks/useChanakya";
import { Panel, PanelHeader } from "@/components/primitives";
import { SourceTag } from "@/components/primitives/SourceTag";
import { SEVERITY_META, type Severity } from "@/lib/severity";
import type { GraphNode } from "@/lib/types";
import { cn } from "@/lib/utils";

const TYPE_COLOR: Record<string, string> = {
  supplier: "#f59e0b",
  corridor: "#22d3ee",
  port: "#3b82f6",
  refinery: "#10b981",
  reserve: "#6366f1",
  event: "#ef4444",
  vessel: "#a78bfa",
  country: "#ec4899",
  pipeline: "#14b8a6",
  agency: "#8b5cf6",
  grade: "#f97316",
  indicator: "#06b6d4",
  entity: "#8b99b3",
};

function getNodeColor(type: string, meta: Record<string, unknown> = {}): string {
  if (type === "event") {
    const sev = (meta.severity as Severity) ?? "high";
    return SEVERITY_META[sev]?.color ?? "#ef4444";
  }
  if (type === "refinery") {
    const u = Number(meta.utilization ?? 90);
    return u >= 92 ? "#10b981" : u >= 80 ? "#eab308" : "#f97316";
  }
  return TYPE_COLOR[type] ?? "#8b99b3";
}

function getSublabel(type: string, meta: Record<string, unknown> = {}): string {
  switch (type) {
    case "supplier":
      return `${meta.share ?? meta.import_share ?? "—"}% share${meta.sanctioned ? " · sanctioned" : ""}`;
    case "corridor":
      return `${meta.share ?? meta.import_share ?? "—"}% · ${meta.status ?? "active"}`;
    case "port":
      return `${meta.capacity ?? meta.capacity_kbpd ?? "—"} kbpd`;
    case "refinery":
      return `${meta.utilization ?? "—"}% util`;
    case "reserve":
      return `${meta.fill ?? meta.fill_pct ?? "—"}% full`;
    case "event":
      return `risk ${meta.risk ?? meta.severity ?? "high"}`;
    case "vessel":
      return `${meta.speed_kn ?? "—"} kn`;
    case "agency":
      return `${meta.domain ?? "govt"}`;
    case "pipeline":
      return `${meta.status ?? "operational"}`;
    default:
      return type;
  }
}

export function GraphView() {
  const { data: baseGraph, isLoading: baseLoading } = useGraph();
  const { data: stats } = useOntologyStats();

  const [activeTab, setActiveTab] = useState<"network" | "explore" | "impact">("network");
  const [selectedEntityId, setSelectedEntityId] = useState<string | null>(null);
  const [selectedEventId, setSelectedEventId] = useState<string>("hormuz_closure");
  const [searchQuery, setSearchQuery] = useState("");
  const [showEdgeLabels, setShowEdgeLabels] = useState(true);
  const [selectedNodeDetail, setSelectedNodeDetail] = useState<{
    id: string;
    type: string;
    label: string;
    meta: Record<string, unknown>;
  } | null>(null);

  // Queries for interactive modes
  const { data: exploreData, isLoading: exploreLoading } = useOntologyExplore(
    activeTab === "explore" ? selectedEntityId : null,
    2
  );
  const { data: impactData, isLoading: impactLoading } = useOntologyImpact(
    activeTab === "impact" ? selectedEventId : null
  );
  const { data: searchData } = useOntologySearch(searchQuery);

  // Transform data into ReactFlow nodes & edges
  const { nodes, edges, backendMode, isDegraded } = useMemo(() => {
    let rawNodes: any[] = [];
    let rawEdges: any[] = [];
    let backend = baseGraph?.backend ?? "in_memory";
    let degraded = baseGraph?.degraded ?? true;

    if (activeTab === "explore" && exploreData) {
      backend = exploreData.backend;
      degraded = exploreData.degraded;
      rawNodes = exploreData.nodes.map((n, idx) => ({
        id: n.id,
        type: n.type,
        label: n.label,
        position: { x: (idx % 4) * 220 + 50, y: Math.floor(idx / 4) * 120 + 50 },
        meta: n.meta,
      }));
      rawEdges = exploreData.edges.map((e, idx) => ({
        id: `e-${idx}`,
        source: e.source,
        target: e.target,
        label: e.label,
        kind: e.label === "AFFECTS" ? "threat" : "normal",
      }));
    } else if (activeTab === "impact" && impactData) {
      backend = impactData.backend;
      degraded = impactData.degraded;
      rawNodes = impactData.nodes.map((n, idx) => ({
        id: n.id,
        type: n.type,
        label: n.label,
        position: { x: idx * 180 + 40, y: 150 + (idx % 2) * 80 },
        meta: n.meta,
      }));
      rawEdges = impactData.edges.map((e, idx) => ({
        id: `e-${idx}`,
        source: e.source,
        target: e.target,
        label: e.label,
        kind: "threat",
      }));
    } else if (baseGraph) {
      rawNodes = baseGraph.nodes;
      rawEdges = baseGraph.edges;
    }

    const flowNodes: Node[] = rawNodes.map((n) => {
      const color = getNodeColor(n.type, n.meta);
      const isSelected = selectedNodeDetail?.id === n.id || selectedEntityId === n.id;
      return {
        id: n.id,
        position: n.position || { x: 100, y: 100 },
        data: {
          label: (
            <div className="text-left">
              <div className="flex items-center justify-between gap-1">
                <span className="text-[11px] font-semibold leading-tight truncate" style={{ color }}>
                  {n.label}
                </span>
                <span className="rounded bg-panel-raised px-1 py-0.2 font-mono text-[8px] uppercase text-ink-dim">
                  {n.type}
                </span>
              </div>
              <div className="text-[9px] text-ink-dim">{getSublabel(n.type, n.meta)}</div>
            </div>
          ),
        },
        style: {
          background: isSelected ? "#172234" : "#0e1420",
          border: isSelected ? `2px solid ${color}` : `1px solid ${color}66`,
          borderRadius: 8,
          padding: "6px 10px",
          width: 160,
          boxShadow: isSelected ? `0 0 16px ${color}` : `0 0 12px -6px ${color}`,
          cursor: "pointer",
        },
      };
    });

    const flowEdges: Edge[] = rawEdges.map((e) => {
      const threat = e.kind === "threat" || e.label === "AFFECTS" || e.label === "TRANSITS";
      return {
        id: e.id,
        source: e.source,
        target: e.target,
        label: showEdgeLabels ? e.label : undefined,
        labelStyle: { fill: "#8b99b3", fontSize: 9, fontWeight: 500 },
        labelBgStyle: { fill: "#0a0f18", fillOpacity: 0.8 },
        animated: threat,
        style: {
          stroke: threat ? "#ef4444" : "#26344a",
          strokeWidth: threat ? 1.75 : 1,
        },
        markerEnd: { type: MarkerType.ArrowClosed, color: threat ? "#ef4444" : "#26344a" },
      };
    });

    return {
      nodes: flowNodes,
      edges: flowEdges,
      backendMode: backend,
      isDegraded: degraded,
    };
  }, [baseGraph, activeTab, exploreData, impactData, selectedEntityId, selectedNodeDetail, showEdgeLabels]);

  const handleNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      const found =
        baseGraph?.nodes.find((n) => n.id === node.id) ||
        exploreData?.nodes.find((n) => n.id === node.id) ||
        impactData?.nodes.find((n) => n.id === node.id);

      const detail = {
        id: node.id,
        type: found?.type || "entity",
        label: (node.data.label as any)?.props?.children[0]?.props?.children[0]?.props?.children || node.id,
        meta: found?.meta || {},
      };
      setSelectedNodeDetail(detail);
      setSelectedEntityId(node.id);
    },
    [baseGraph, exploreData, impactData]
  );

  if (baseLoading) {
    return (
      <div className="grid h-full place-items-center blueprint">
        <span className="label-terminal animate-pulse">Initializing Neo4j Operational Ontology…</span>
      </div>
    );
  }

  return (
    <div className="relative h-full w-full bg-void">
      {/* Top Toolbar Overlay */}
      <div className="pointer-events-none absolute left-4 right-4 top-4 z-[450] flex flex-wrap items-center justify-between gap-3">
        {/* Left: Mode selector */}
        <Panel className="pointer-events-auto flex items-center gap-1 p-1">
          <button
            onClick={() => setActiveTab("network")}
            className={cn(
              "flex items-center gap-1.5 rounded px-3 py-1.5 text-xs font-medium transition-colors",
              activeTab === "network" ? "bg-signal/15 text-signal" : "text-ink-dim hover:text-ink"
            )}
          >
            <Layers size={13} /> Full Graph
          </button>
          <button
            onClick={() => setActiveTab("explore")}
            className={cn(
              "flex items-center gap-1.5 rounded px-3 py-1.5 text-xs font-medium transition-colors",
              activeTab === "explore" ? "bg-signal/15 text-signal" : "text-ink-dim hover:text-ink"
            )}
          >
            <Eye size={13} /> 2-Hop Explorer
          </button>
          <button
            onClick={() => setActiveTab("impact")}
            className={cn(
              "flex items-center gap-1.5 rounded px-3 py-1.5 text-xs font-medium transition-colors",
              activeTab === "impact" ? "bg-signal/15 text-signal" : "text-ink-dim hover:text-ink"
            )}
          >
            <Zap size={13} /> Impact Trace
          </button>
        </Panel>

        {/* Search & Statistics Bar */}
        <Panel className="pointer-events-auto flex items-center gap-3 px-3 py-1.5">
          {/* Search Input */}
          <div className="relative flex items-center">
            <Search size={13} className="absolute left-2.5 text-ink-dim" />
            <input
              type="text"
              placeholder="Search ontology entities…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-48 rounded border border-line bg-panel-raised pl-8 pr-3 py-1 text-xs text-ink placeholder:text-ink-dim focus:border-signal/50 focus:outline-none"
            />
            {searchData && searchData.results.length > 0 && searchQuery && (
              <div className="absolute top-full left-0 mt-1 w-64 max-h-48 overflow-y-auto rounded border border-line bg-panel-raised p-1 shadow-lg z-[500]">
                {searchData.results.map((hit) => (
                  <button
                    key={hit.id}
                    onClick={() => {
                      setSelectedEntityId(hit.id);
                      setActiveTab("explore");
                      setSearchQuery("");
                    }}
                    className="flex w-full items-center justify-between rounded px-2 py-1 text-left text-xs hover:bg-panel"
                  >
                    <span className="truncate text-ink font-medium">{hit.label}</span>
                    <span className="font-mono text-[9px] uppercase text-ink-dim">{hit.type}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Edge Label Toggle */}
          <button
            onClick={() => setShowEdgeLabels(!showEdgeLabels)}
            className={cn(
              "flex items-center gap-1 rounded border px-2 py-1 text-[11px] font-mono",
              showEdgeLabels ? "border-signal/40 text-signal" : "border-line text-ink-dim"
            )}
          >
            Labels: {showEdgeLabels ? "ON" : "OFF"}
          </button>

          {/* Stats Badges */}
          {stats && (
            <div className="flex items-center gap-2 border-l border-line pl-3 text-[10px] text-ink-dim font-mono">
              <span>{stats.total_nodes} nodes</span>
              <span>·</span>
              <span>{stats.total_relationships} edges</span>
            </div>
          )}

          {/* Backend Status Tag */}
          <SourceTag kind={isDegraded ? "simulated" : "live"} />
        </Panel>
      </div>

      {/* Main ReactFlow Graph */}
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodeClick={handleNodeClick}
        fitView
        minZoom={0.15}
        proOptions={{ hideAttribution: true }}
        nodesDraggable
        nodesConnectable={false}
      >
        <Background variant={BackgroundVariant.Dots} gap={28} size={1} color="#1b2536" />
        <Controls className="!border-line !bg-panel" />
      </ReactFlow>

      {/* Impact Trace Chain Overlay (bottom center) */}
      {activeTab === "impact" && impactData && impactData.chain && (
        <div className="pointer-events-none absolute bottom-4 left-1/2 -translate-x-1/2 z-[450] max-w-3xl w-full px-4">
          <Panel className="pointer-events-auto p-3">
            <div className="mb-1.5 flex items-center justify-between text-xs">
              <span className="font-semibold text-critical flex items-center gap-1">
                <Zap size={14} /> Causal Disruption Chain
              </span>
              <span className="font-mono text-[10px] text-ink-dim">
                Event: {impactData.event_id}
              </span>
            </div>
            <div className="flex flex-wrap items-center gap-2 text-xs">
              {impactData.chain.map((step, idx) => (
                <div key={idx} className="flex items-center gap-1.5">
                  <span className="rounded border border-line-strong bg-panel-raised px-2 py-0.5 font-mono text-[10px] text-ink">
                    {step.label}
                  </span>
                  {idx < impactData.chain.length - 1 && <span className="text-critical font-bold">→</span>}
                </div>
              ))}
            </div>
          </Panel>
        </div>
      )}

      {/* Slide-out Entity Detail Panel (right) */}
      {selectedNodeDetail && (
        <div className="absolute right-4 top-20 z-[500] w-80">
          <Panel raised className="p-4">
            <PanelHeader
              eyebrow={selectedNodeDetail.type}
              title={selectedNodeDetail.label}
              right={
                <button onClick={() => setSelectedNodeDetail(null)} className="text-ink-dim hover:text-ink">
                  <X size={16} />
                </button>
              }
            />
            <div className="mt-3 space-y-2 text-xs">
              <div className="flex justify-between border-b border-line pb-1">
                <span className="text-ink-dim">Entity ID</span>
                <span className="font-mono text-ink">{selectedNodeDetail.id}</span>
              </div>
              {Object.entries(selectedNodeDetail.meta).map(([key, val]) => (
                <div key={key} className="flex justify-between border-b border-line/40 pb-1">
                  <span className="text-ink-dim uppercase font-mono text-[10px]">{key}</span>
                  <span className="readout text-ink truncate max-w-[160px]">
                    {typeof val === "object" ? JSON.stringify(val) : String(val)}
                  </span>
                </div>
              ))}

              <div className="mt-4 flex gap-2">
                <button
                  onClick={() => {
                    setSelectedEntityId(selectedNodeDetail.id);
                    setActiveTab("explore");
                  }}
                  className="flex-1 rounded border border-signal/40 bg-signal/10 py-1.5 text-xs font-medium text-signal hover:bg-signal/20"
                >
                  Explore 2-Hop Graph
                </button>
              </div>
            </div>
          </Panel>
        </div>
      )}
    </div>
  );
}
