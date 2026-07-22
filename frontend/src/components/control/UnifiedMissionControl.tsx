"use client";

import { useState, useMemo } from "react";
import dynamic from "next/dynamic";
import { motion, AnimatePresence } from "framer-motion";
import {
  Radar,
  Globe2,
  Share2,
  Users,
  Brain,
  Rocket,
  ShieldAlert,
  Search,
  Sliders,
  Play,
  CheckCircle2,
  Clock,
  ArrowRight,
  Maximize2,
  Minimize2,
  Zap,
  Activity,
  Layers,
  ChevronRight,
  TrendingUp,
  AlertTriangle,
  RefreshCw,
} from "lucide-react";
import { useRouter } from "next/navigation";
import {
  useIntelFeed,
  useNetwork,
  useScenarios,
  useSimulation,
  useCouncil,
  useSourceStatus,
} from "@/hooks/useChanakya";
import { useMission } from "@/stores/useMission";
import { useSecurityIndex } from "@/stores/useSecurityIndex";
import { Panel, PanelHeader, MetricReadout, ConfidenceBar } from "@/components/primitives";
import { SecurityIndexGauge } from "@/components/primitives/SecurityIndexGauge";
import { SourceTag } from "@/components/primitives/SourceTag";
import { GraphView } from "@/components/twin/GraphView";
import { WorkflowTrace } from "@/components/council/WorkflowTrace";
import type { MapMode, TwinSelection } from "@/components/twin/EnergyMap";
import type { IntelEvent, StrategyOption, AgentAssessment } from "@/lib/types";
import { cn, fmtCompact } from "@/lib/utils";

const EnergyMap = dynamic(() => import("@/components/twin/EnergyMap"), {
  ssr: false,
  loading: () => (
    <div className="grid h-full place-items-center blueprint">
      <span className="label-terminal animate-pulse text-signal">Initializing Geospatial Twin…</span>
    </div>
  ),
});

const CATEGORY_COLORS: Record<string, string> = {
  geopolitical: "#ef4444",
  shipping: "#22d3ee",
  market: "#f59e0b",
  weather: "#10b981",
  sanctions: "#a78bfa",
  satellite: "#6366f1",
};

export function UnifiedMissionControl() {
  const router = useRouter();
  const { scenarioId, levers, selectedStrategyId, setScenario, setLevers, selectStrategy } = useMission();
  const nesi = useSecurityIndex((s) => s.value);
  const trend = useSecurityIndex((s) => s.trend);

  // Data hooks
  const { data: scenarios } = useScenarios();
  const { data: network } = useNetwork();
  const { data: intelFeed } = useIntelFeed();
  const { data: simResult, isLoading: simLoading } = useSimulation(scenarioId, levers);
  const { data: councilResult, isLoading: councilLoading } = useCouncil(scenarioId, levers);
  const { data: sourceStatus } = useSourceStatus();

  // Local UI state
  const [centerView, setCenterView] = useState<"map" | "graph">("map");
  const [mapMode, setMapMode] = useState<MapMode>("operations");
  const [leftTab, setLeftTab] = useState<"intel" | "sources">("intel");
  const [rightTab, setRightTab] = useState<"council" | "workflow" | "strategies">("council");
  const [intelCategory, setIntelCategory] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedTwinItem, setSelectedTwinItem] = useState<TwinSelection | null>(null);
  const [expandedDock, setExpandedDock] = useState<"none" | "left" | "right">("none");

  const currentScenario = scenarios?.find((s) => s.id === scenarioId);
  const activeStrategyId = selectedStrategyId || councilResult?.recommended_strategy_id;
  const activeStrategy = councilResult?.strategies.find((s) => s.id === activeStrategyId);

  // Filtered intel events
  const filteredEvents = useMemo(() => {
    if (!intelFeed?.events) return [];
    return intelFeed.events.filter((evt) => {
      const matchCat = intelCategory === "all" || evt.category === intelCategory;
      const matchSearch =
        !searchQuery ||
        evt.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        evt.summary.toLowerCase().includes(searchQuery.toLowerCase());
      return matchCat && matchSearch;
    });
  }, [intelFeed, intelCategory, searchQuery]);

  return (
    <div className="flex h-full w-full flex-col overflow-hidden bg-void font-sans blueprint">
      {/* Real-time Ticker & Header Control Bar */}
      <header className="flex shrink-0 items-center justify-between border-b border-line bg-base/90 px-4 py-2 backdrop-blur z-30">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <div className="relative grid h-7 w-7 place-items-center rounded border border-signal/40 bg-signal/10 shadow-glow-signal">
              <Activity size={15} className="animate-pulse text-signal" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs font-bold tracking-[0.2em] text-ink">CHANAKYA</span>
                <span className="rounded bg-signal/15 px-1.5 py-0.2 font-mono text-[9px] uppercase tracking-wider text-signal border border-signal/30">
                  Mission Control
                </span>
              </div>
              <div className="label-terminal !text-[9px]">National Energy Supply Chain Operating System</div>
            </div>
          </div>

          <div className="hidden h-5 w-px bg-line md:block" />

          {/* Active Scenario Selector Dropdown */}
          <div className="flex items-center gap-2">
            <span className="label-terminal hidden sm:inline">Active Threat:</span>
            <select
              value={scenarioId}
              onChange={(e) => setScenario(e.target.value)}
              className="rounded border border-line-strong bg-panel-raised px-2.5 py-1 text-xs font-semibold text-ink focus:border-signal/60 focus:outline-none cursor-pointer"
            >
              {scenarios?.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Live Intel Ticker (center marquee) */}
        <div className="hidden max-w-xl flex-1 overflow-hidden lg:block mx-4">
          <div className="flex items-center gap-3 rounded border border-line/60 bg-panel/70 px-3 py-1 text-xs">
            <span className="flex shrink-0 items-center gap-1 font-mono text-[10px] uppercase tracking-wider text-critical font-bold">
              <span className="h-1.5 w-1.5 rounded-full bg-critical animate-pulse" />
              LIVE TELEMETRY
            </span>
            <div className="truncate text-ink-muted text-[11px]">
              {intelFeed?.events[0] ? (
                <>
                  <span className="font-semibold text-ink">[{intelFeed.events[0].source}]</span>{" "}
                  {intelFeed.events[0].title} — {intelFeed.events[0].summary}
                </>
              ) : (
                "Continuous ingestion active across GDELT, AISstream, OpenMeteo, EIA, and PPAC feeds."
              )}
            </div>
          </div>
        </div>

        {/* Posture Index Gauge & Actions */}
        <div className="flex items-center gap-4 shrink-0">
          <div className="flex items-center gap-2 border-r border-line pr-4">
            <span className="label-terminal hidden sm:inline">National Posture:</span>
            <SecurityIndexGauge value={nesi} trend={trend} size="sm" />
          </div>

          <button
            onClick={() => router.push("/execution")}
            className="flex items-center gap-1.5 rounded border border-signal/50 bg-signal/15 px-3 py-1.5 text-xs font-semibold text-signal shadow-glow-signal transition-colors hover:bg-signal/25"
          >
            <Rocket size={14} /> Playbook Execution
          </button>
        </div>
      </header>

      {/* Main Command Workspace (3 Docks: Left Intel | Center Canvas | Right AI Council) */}
      <div className="relative flex min-h-0 flex-1 overflow-hidden">
        {/* LEFT DOCK: Live Intelligence & Data Sources */}
        <div
          className={cn(
            "flex flex-col border-r border-line bg-base/80 backdrop-blur transition-all duration-300 z-20",
            expandedDock === "left"
              ? "w-96"
              : expandedDock === "right"
              ? "w-0 overflow-hidden border-none"
              : "w-80"
          )}
        >
          {/* Left Dock Header */}
          <div className="flex items-center justify-between border-b border-line px-3 py-2">
            <div className="flex items-center gap-1">
              <button
                onClick={() => setLeftTab("intel")}
                className={cn(
                  "flex items-center gap-1.5 rounded px-2.5 py-1 text-xs font-medium transition-colors",
                  leftTab === "intel" ? "bg-signal/15 text-signal" : "text-ink-dim hover:text-ink"
                )}
              >
                <Radar size={13} /> Live Intel ({filteredEvents.length})
              </button>
              <button
                onClick={() => setLeftTab("sources")}
                className={cn(
                  "flex items-center gap-1.5 rounded px-2.5 py-1 text-xs font-medium transition-colors",
                  leftTab === "sources" ? "bg-signal/15 text-signal" : "text-ink-dim hover:text-ink"
                )}
              >
                <Layers size={13} /> Sources
              </button>
            </div>
            <button
              onClick={() => setExpandedDock(expandedDock === "left" ? "none" : "left")}
              className="text-ink-dim hover:text-ink"
            >
              {expandedDock === "left" ? <Minimize2 size={13} /> : <Maximize2 size={13} />}
            </button>
          </div>

          {/* Left Dock Content */}
          {leftTab === "intel" && (
            <div className="flex flex-1 flex-col overflow-hidden p-2.5 gap-2">
              {/* Filter controls */}
              <div className="flex items-center gap-1.5">
                <div className="relative flex-1">
                  <Search size={12} className="absolute left-2.5 top-2 text-ink-dim" />
                  <input
                    type="text"
                    placeholder="Filter signals…"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full rounded border border-line bg-panel-raised pl-7 pr-2 py-1 text-xs text-ink placeholder:text-ink-dim focus:border-signal/50 focus:outline-none"
                  />
                </div>
              </div>

              {/* Category chips */}
              <div className="flex flex-wrap items-center gap-1">
                {["all", "geopolitical", "shipping", "market", "weather", "sanctions"].map((cat) => (
                  <button
                    key={cat}
                    onClick={() => setIntelCategory(cat)}
                    className={cn(
                      "rounded px-2 py-0.5 font-mono text-[9px] uppercase tracking-wider transition-colors border",
                      intelCategory === cat
                        ? "border-signal/40 bg-signal/15 text-signal font-semibold"
                        : "border-line bg-panel/60 text-ink-dim hover:text-ink"
                    )}
                  >
                    {cat}
                  </button>
                ))}
              </div>

              {/* Event list */}
              <div className="flex-1 space-y-2 overflow-y-auto pr-1">
                {filteredEvents.length === 0 ? (
                  <div className="grid h-32 place-items-center text-xs text-ink-dim">
                    No intelligence signals matching filter.
                  </div>
                ) : (
                  filteredEvents.map((evt) => (
                    <div
                      key={evt.id}
                      className="rounded border border-line/80 bg-panel/80 p-2.5 transition-colors hover:border-signal/40 cursor-pointer"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span
                          className="rounded px-1.5 py-0.2 font-mono text-[9px] uppercase font-bold text-ink"
                          style={{ backgroundColor: `${CATEGORY_COLORS[evt.category] || "#8b99b3"}33`, color: CATEGORY_COLORS[evt.category] }}
                        >
                          {evt.category}
                        </span>
                        <div className="flex items-center gap-1">
                          <SourceTag kind={evt.source_kind} />
                          <span className="font-mono text-[9px] text-ink-dim">
                            Risk {evt.risk_score}
                          </span>
                        </div>
                      </div>

                      <h4 className="mt-1 text-xs font-semibold leading-snug text-ink">{evt.title}</h4>
                      <p className="mt-1 line-clamp-2 text-[11px] leading-relaxed text-ink-muted">
                        {evt.summary}
                      </p>

                      {evt.affected_corridors && evt.affected_corridors.length > 0 && (
                        <div className="mt-1.5 flex flex-wrap gap-1">
                          {evt.affected_corridors.map((c) => (
                            <span key={c} className="rounded bg-panel-raised px-1.5 py-0.2 font-mono text-[8px] uppercase text-ink-dim">
                              {c}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>
            </div>
          )}

          {leftTab === "sources" && (
            <div className="flex-1 overflow-y-auto p-3 space-y-2">
              <div className="label-terminal mb-2">Ingestion Layer Health</div>
              {sourceStatus?.sources.map((src) => (
                <div key={src.source} className="rounded border border-line bg-panel/60 p-2.5">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs font-semibold text-ink uppercase">
                      {src.source}
                    </span>
                    <SourceTag kind={src.provenance} />
                  </div>
                  <div className="mt-1 flex items-center justify-between text-[11px]">
                    <span className={src.healthy ? "text-nominal" : "text-critical"}>
                      {src.healthy ? "Healthy" : "Degraded"}
                    </span>
                    <span className="readout text-ink-dim">{src.event_count} events</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* CENTER CANVAS: Geospatial Digital Twin & Neo4j Ontology Graph */}
        <div className="relative flex flex-1 flex-col overflow-hidden bg-void">
          {/* Canvas Top Overlay Controls */}
          <div className="pointer-events-none absolute left-4 top-4 z-30 flex items-center gap-2">
            <Panel className="pointer-events-auto flex items-center gap-1 p-1">
              <button
                onClick={() => setCenterView("map")}
                className={cn(
                  "flex items-center gap-1.5 rounded px-3 py-1.5 text-xs font-semibold transition-colors",
                  centerView === "map" ? "bg-signal/15 text-signal shadow-glow-signal" : "text-ink-dim hover:text-ink"
                )}
              >
                <Globe2 size={14} /> Geospatial Twin
              </button>
              <button
                onClick={() => setCenterView("graph")}
                className={cn(
                  "flex items-center gap-1.5 rounded px-3 py-1.5 text-xs font-semibold transition-colors",
                  centerView === "graph" ? "bg-signal/15 text-signal shadow-glow-signal" : "text-ink-dim hover:text-ink"
                )}
              >
                <Share2 size={14} /> Ontology Explorer
              </button>

              {centerView === "map" && (
                <>
                  <div className="mx-1 h-4 w-px bg-line" />
                  <button
                    onClick={() => setMapMode(mapMode === "operations" ? "satellite" : "operations")}
                    className="flex items-center gap-1 rounded px-2 py-1 text-[11px] font-mono text-ink-muted hover:text-ink"
                  >
                    Mode: {mapMode}
                  </button>
                </>
              )}
            </Panel>
          </div>

          {/* Canvas Content */}
          <div className="relative flex-1">
            {centerView === "map" ? (
              network ? (
                <EnergyMap
                  network={network}
                  vessels={intelFeed?.vessels ?? []}
                  events={intelFeed?.events ?? []}
                  mapMode={mapMode}
                  onSelect={setSelectedTwinItem}
                />
              ) : (
                <div className="grid h-full place-items-center blueprint">
                  <span className="label-terminal animate-pulse text-signal">Loading Energy Network…</span>
                </div>
              )
            ) : (
              <GraphView />
            )}
          </div>
        </div>

        {/* RIGHT DOCK: Multi-Agent Council & Decision Center */}
        <div
          className={cn(
            "flex flex-col border-l border-line bg-base/80 backdrop-blur transition-all duration-300 z-20",
            expandedDock === "right"
              ? "w-96"
              : expandedDock === "left"
              ? "w-0 overflow-hidden border-none"
              : "w-88"
          )}
        >
          {/* Right Dock Header */}
          <div className="flex items-center justify-between border-b border-line px-3 py-2">
            <div className="flex items-center gap-1">
              <button
                onClick={() => setRightTab("council")}
                className={cn(
                  "flex items-center gap-1 text-xs font-medium rounded px-2.5 py-1 transition-colors",
                  rightTab === "council" ? "bg-signal/15 text-signal" : "text-ink-dim hover:text-ink"
                )}
              >
                <Users size={13} /> Council
              </button>
              <button
                onClick={() => setRightTab("workflow")}
                className={cn(
                  "flex items-center gap-1 text-xs font-medium rounded px-2.5 py-1 transition-colors",
                  rightTab === "workflow" ? "bg-signal/15 text-signal" : "text-ink-dim hover:text-ink"
                )}
              >
                <Activity size={13} /> LangGraph
              </button>
              <button
                onClick={() => setRightTab("strategies")}
                className={cn(
                  "flex items-center gap-1 text-xs font-medium rounded px-2.5 py-1 transition-colors",
                  rightTab === "strategies" ? "bg-signal/15 text-signal" : "text-ink-dim hover:text-ink"
                )}
              >
                <Brain size={13} /> Decision
              </button>
            </div>
            <button
              onClick={() => setExpandedDock(expandedDock === "right" ? "none" : "right")}
              className="text-ink-dim hover:text-ink"
            >
              {expandedDock === "right" ? <Minimize2 size={13} /> : <Maximize2 size={13} />}
            </button>
          </div>

          {/* Right Dock Content */}
          <div className="flex-1 overflow-y-auto p-3 space-y-3">
            {/* Right Tab 1: Agent Council */}
            {rightTab === "council" && (
              <>
                <div className="flex items-center justify-between rounded border border-line bg-panel/60 p-2.5">
                  <div>
                    <div className="label-terminal">Consensus Score</div>
                    <div className="readout text-lg font-bold text-signal">
                      {councilResult?.consensus_confidence ?? "—"}%
                    </div>
                  </div>
                  {councilResult && <SourceTag kind={councilResult.reasoning_mode} />}
                </div>

                {councilResult?.assessments.map((a) => (
                  <div key={a.agent_id} className="rounded border border-line/80 bg-panel/70 p-2.5 text-xs">
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-ink">{a.agent_name}</span>
                      <span className="readout text-[10px] text-signal">{a.confidence}% conf</span>
                    </div>
                    <div className="mt-1 rounded bg-signal/10 p-1.5 text-[11px] font-medium text-signal">
                      {a.stance}
                    </div>
                    <p className="mt-1.5 text-ink-muted text-[11px] line-clamp-2">{a.reasoning}</p>
                  </div>
                ))}
              </>
            )}

            {/* Right Tab 2: LangGraph Workflow DAG */}
            {rightTab === "workflow" && councilResult?.workflow_trace && (
              <WorkflowTrace
                steps={councilResult.workflow_trace}
                runId={councilResult.workflow_run_id}
                consensusConfidence={councilResult.consensus_confidence}
              />
            )}

            {/* Right Tab 3: Ranked Decision Strategies */}
            {rightTab === "strategies" && (
              <>
                <div className="label-terminal mb-2">Ranked Response Doctrines</div>
                {councilResult?.strategies.map((strat) => {
                  const isActive = activeStrategyId === strat.id;
                  return (
                    <div
                      key={strat.id}
                      onClick={() => selectStrategy(strat.id)}
                      className={cn(
                        "rounded border p-3 text-xs transition-colors cursor-pointer space-y-2",
                        isActive ? "border-signal/60 bg-signal/5 shadow-glow-signal" : "border-line bg-panel/60 hover:border-line-strong"
                      )}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className="readout font-bold text-signal">#{strat.rank}</span>
                          <span className="font-semibold text-ink">{strat.title}</span>
                        </div>
                        <span className="readout text-sm font-bold text-signal">{strat.score.toFixed(0)} pts</span>
                      </div>

                      <p className="text-ink-muted text-[11px] leading-relaxed">{strat.thesis}</p>

                      <div className="grid grid-cols-2 gap-1.5 rounded bg-panel-raised p-1.5 text-[10px]">
                        <div>Residual: <span className="readout text-ink font-semibold">{strat.projection.residual_shortfall_kbpd.toLocaleString()} kbpd</span></div>
                        <div>NESI: <span className="readout text-signal font-semibold">{strat.projection.nesi_after.toFixed(0)}</span></div>
                        <div>Utilisation: <span className="readout text-ink font-semibold">{strat.projection.national_utilization_pct.toFixed(0)}%</span></div>
                        <div>Brent: <span className="readout text-energy font-semibold">{strat.projection.brent_change_pct >= 0 ? "+" : ""}{strat.projection.brent_change_pct.toFixed(0)}%</span></div>
                      </div>

                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          selectStrategy(strat.id);
                          router.push("/execution");
                        }}
                        className="w-full flex items-center justify-center gap-1 rounded bg-signal/15 py-1.5 text-[11px] font-semibold uppercase text-signal hover:bg-signal/25"
                      >
                        Execute Strategy <ArrowRight size={12} />
                      </button>
                    </div>
                  );
                })}
              </>
            )}
          </div>
        </div>
      </div>

      {/* BOTTOM CONTROL DECK: Real-time Simulation Levers */}
      <div className="flex shrink-0 items-center justify-between border-t border-line bg-base/90 px-4 py-2.5 backdrop-blur z-30">
        {/* Levers Section */}
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2 border-r border-line pr-4">
            <Sliders size={15} className="text-signal" />
            <span className="label-terminal font-semibold text-ink">Sim Levers:</span>
          </div>

          {/* Lever 1: SPR Drawdown % Slider */}
          <div className="flex items-center gap-3">
            <span className="label-terminal text-[10px]">SPR Release:</span>
            <input
              type="range"
              min={0}
              max={100}
              step={5}
              value={levers.spr_release_pct}
              onChange={(e) => setLevers({ spr_release_pct: Number(e.target.value) })}
              className="w-28 cursor-pointer accent-signal"
            />
            <span className="readout text-xs font-bold text-signal w-8">{levers.spr_release_pct}%</span>
          </div>

          {/* Lever 2: Reroute Toggle */}
          <div className="flex items-center gap-2">
            <span className="label-terminal text-[10px]">Reroute Cape:</span>
            <button
              onClick={() => setLevers({ enable_reroute: !levers.enable_reroute })}
              className={cn(
                "rounded px-2 py-0.5 font-mono text-[10px] uppercase font-bold transition-colors border",
                levers.enable_reroute
                  ? "border-nominal/40 bg-nominal/15 text-nominal"
                  : "border-line bg-panel text-ink-dim"
              )}
            >
              {levers.enable_reroute ? "ENABLED" : "OFF"}
            </button>
          </div>

          {/* Lever 3: Spot Sourcing Toggle */}
          <div className="flex items-center gap-2">
            <span className="label-terminal text-[10px]">Spot Tender:</span>
            <button
              onClick={() => setLevers({ enable_spot: !levers.enable_spot })}
              className={cn(
                "rounded px-2 py-0.5 font-mono text-[10px] uppercase font-bold transition-colors border",
                levers.enable_spot
                  ? "border-nominal/40 bg-nominal/15 text-nominal"
                  : "border-line bg-panel text-ink-dim"
              )}
            >
              {levers.enable_spot ? "ENABLED" : "OFF"}
            </button>
          </div>
        </div>

        {/* Live Simulation Projection Metrics */}
        {simResult && (
          <div className="flex items-center gap-5">
            <div className="hidden sm:flex items-center gap-4 text-xs">
              <MetricReadout
                label="Gross Gap"
                value={`${simResult.supply_gap_kbpd.toLocaleString()}`}
                unit="kbpd"
                accent="#ef4444"
              />
              <MetricReadout
                label="Residual Shortfall"
                value={`${simResult.residual_shortfall_kbpd.toLocaleString()}`}
                unit="kbpd"
                accent={simResult.residual_shortfall_kbpd > 0 ? "#f59e0b" : "#10b981"}
              />
              <MetricReadout
                label="Refinery Util"
                value={`${simResult.national_utilization_pct.toFixed(0)}%`}
                accent="#22d3ee"
              />
              <MetricReadout
                label="Brent Move"
                value={`${simResult.brent_change_pct >= 0 ? "+" : ""}${simResult.brent_change_pct.toFixed(1)}%`}
                accent="#eab308"
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
