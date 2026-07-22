"use client";

import { useState, useMemo, useEffect } from "react";
import dynamic from "next/dynamic";
import { usePathname, useRouter } from "next/navigation";
import {
  Radar, Globe2, Share2, Users, Brain, Rocket, Crosshair, Minimize2, Maximize2, Search, Sliders, Play, Layers, X, Zap
} from "lucide-react";
import {
  useIntelFeed, useNetwork, useScenarios, useSimulation, useCouncil, useSourceStatus, useSatelliteLayers
} from "@/hooks/useChanakya";
import { useMission } from "@/stores/useMission";
import { useSecurityIndex } from "@/stores/useSecurityIndex";
import { MetricReadout, Panel } from "@/components/primitives";
import { SourceTag } from "@/components/primitives/SourceTag";
import type { MapMode, TwinSelection } from "@/components/twin/EnergyMap";
import { cn } from "@/lib/utils";
import { apiPostOperator } from "@/lib/api";

// Drawers & Modals
import { GraphView } from "@/components/twin/GraphView";
import { LayerSwitcher } from "@/components/twin/LayerSwitcher";
import { CascadePanel } from "@/components/twin/CascadePanel";
import { WorkflowTrace } from "@/components/council/WorkflowTrace";
import { CrisisTimeline } from "@/components/execution/CrisisTimeline";

const EnergyMap = dynamic(() => import("@/components/twin/EnergyMap"), {
  ssr: false,
  loading: () => null,
});

const CATEGORY_COLORS: Record<string, string> = {
  geopolitical: "#ef4444",
  shipping: "#00f0ff",
  market: "#f59e0b",
  weather: "#10b981",
  sanctions: "#a78bfa",
  satellite: "#6366f1",
};

export function UnifiedMissionControl() {
  const router = useRouter();
  const pathname = usePathname();
  const { scenarioId, levers, selectedStrategyId, setScenario, setLevers, selectStrategy, activated, activateMission } = useMission();
  const nesi = useSecurityIndex((s) => s.value);

  // Data
  const { data: scenarios } = useScenarios();
  const { data: network } = useNetwork();
  const { data: intelFeed } = useIntelFeed();
  const { data: simResult } = useSimulation(scenarioId, levers);
  const { data: councilResult } = useCouncil(scenarioId, levers);
  const { data: satellite } = useSatelliteLayers();

  const [activating, setActivating] = useState(false);

  // Workspace View State
  const [mapMode, setMapMode] = useState<MapMode>("satellite");
  const [selectedTwinItem, setSelectedTwinItem] = useState<TwinSelection | null>(null);

  // Satellite imagery layer selection — default to clean natural-earth (Blue Marble)
  const [baseLayer, setBaseLayer] = useState("blue_marble");
  const [overlays, setOverlays] = useState<string[]>([]);
  const [layersOpen, setLayersOpen] = useState(false);
  const satLayers = satellite?.layers ?? [];
  const baseOptions = satLayers.filter((l) => l.kind === "base");
  const overlayOptions = satLayers.filter((l) => l.kind === "overlay");
  const effectiveBase = baseLayer || baseOptions[0]?.id || "";
  const toggleOverlay = (id: string) =>
    setOverlays((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));

  // Cascade (block a node -> quantified downstream impact)
  const [cascadeOpen, setCascadeOpen] = useState(false);
  const [impacted, setImpacted] = useState<Record<string, string>>({});
  
  // Drawer States
  const [leftDrawer, setLeftDrawer] = useState<"intel" | "none">(pathname === "/intelligence" ? "intel" : pathname === "/" ? "intel" : "none");
  const [rightDrawer, setRightDrawer] = useState<"council" | "ontology" | "decision" | "none">(
    pathname === "/council" ? "council" : pathname === "/decision" ? "decision" : pathname === "/digital-twin" ? "ontology" : "none"
  );
  const [bottomDrawer, setBottomDrawer] = useState<"timeline" | "none">(
    pathname === "/execution" || pathname === "/simulation" || activated ? "timeline" : "none"
  );
  const [rightDrawerWidth, setRightDrawerWidth] = useState(850);
  const [isResizing, setIsResizing] = useState(false);

  const startResizing = (e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
    const startX = e.clientX;
    const startWidth = rightDrawerWidth;
    
    const onMouseMove = (moveEvent: MouseEvent) => {
       const delta = startX - moveEvent.clientX;
       const maxAllowed = typeof window !== "undefined" ? window.innerWidth - 80 : 1400;
       setRightDrawerWidth(Math.max(340, Math.min(maxAllowed, startWidth + delta)));
    };
    const onMouseUp = () => {
      setIsResizing(false);
      document.removeEventListener("mousemove", onMouseMove);
      document.removeEventListener("mouseup", onMouseUp);
    };
    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);
  };

  const toggleMaximizeDrawer = () => {
    const maxAllowed = typeof window !== "undefined" ? window.innerWidth - 120 : 1200;
    if (rightDrawerWidth >= maxAllowed - 50) {
      setRightDrawerWidth(640);
    } else {
      setRightDrawerWidth(maxAllowed);
    }
  };

  // Sync pathname changes to drawer states
  useEffect(() => {
    if (pathname === "/intelligence") { setLeftDrawer("intel"); setRightDrawer("none"); }
    else if (pathname === "/council") { setRightDrawer("council"); }
    else if (pathname === "/decision") { setRightDrawer("decision"); }
    else if (pathname === "/digital-twin") { setRightDrawer("ontology"); setRightDrawerWidth(850); }
    else if (pathname === "/execution") { setBottomDrawer("timeline"); setRightDrawer("none"); }
    else if (pathname === "/") { setLeftDrawer("intel"); setRightDrawer("none"); setBottomDrawer("none"); }
  }, [pathname]);

  const activeStrategyId = selectedStrategyId || councilResult?.recommended_strategy_id;
  const missionId = councilResult?.mission_id;

  const handleInitiateMission = async () => {
    if (!missionId) {
      alert("No mission generated yet. Please select a strategy first.");
      return;
    }
    const pin = window.prompt("Operator PIN required to activate national mission playback");
    if (!pin) return;
    
    setActivating(true);
    try {
      await apiPostOperator(`/api/missions/${missionId}/activate`, pin);
      activateMission();
      setBottomDrawer("timeline");
      setRightDrawer("none");
      setLeftDrawer("none");
    } catch (error) {
      alert(error instanceof Error ? error.message : "Mission activation failed");
    } finally {
      setActivating(false);
    }
  };

  return (
    <div className="relative h-full w-full overflow-hidden bg-canvas text-ink font-sans select-none">
      
      {/* =========================================================================
          BACKGROUND LAYER: 100% Fullscreen Geospatial Twin (Map)
          ========================================================================= */}
      <div className="absolute inset-0 z-0">
        {network && (
          <EnergyMap
            network={network}
            vessels={intelFeed?.vessels ?? []}
            events={intelFeed?.events ?? []}
            mapMode={mapMode}
            scenarioId={scenarioId}
            activated={activated}
            satelliteLayers={satellite?.layers}
            baseLayerId={effectiveBase}
            overlayIds={overlays}
            impacted={impacted}
            onSelect={(item) => {
              setSelectedTwinItem(item);
              setRightDrawer("ontology");
            }}
          />
        )}
        
        {mapMode === "satellite" && (
          <div className="satellite-overlay pointer-events-none" />
        )}
        
        {/* Map Context Overlay (Top Center inside map) */}
        <div className="absolute top-16 left-1/2 -translate-x-1/2 z-10 flex gap-4 pointer-events-auto items-start">
          <div className="relative flex flex-col items-center gap-2">
            <div className="tactical-panel flex items-center gap-2 p-1.5 bg-panel/95">
              <button
                onClick={() => setMapMode("satellite")}
                className={cn("px-2 py-1 font-mono text-[10px] uppercase font-bold rounded transition-colors", mapMode === "satellite" ? "bg-signal/15 text-signal border border-signal/40" : "text-ink-dim hover:text-ink")}
              >
                Satellite
              </button>
              <button
                onClick={() => setMapMode("operations")}
                className={cn("px-2 py-1 font-mono text-[10px] uppercase font-bold rounded transition-colors", mapMode === "operations" ? "bg-signal/15 text-signal border border-signal/40" : "text-ink-dim hover:text-ink")}
              >
                Operations
              </button>
              {mapMode === "satellite" && baseOptions.length > 0 && (
                <button
                  onClick={() => setLayersOpen((o) => !o)}
                  className={cn("flex items-center gap-1 px-2 py-1 font-mono text-[10px] uppercase font-bold rounded transition-colors", layersOpen ? "bg-signal/15 text-signal border border-signal/40" : "text-ink-dim hover:text-ink")}
                >
                  <Layers size={11} /> Imagery
                </button>
              )}
              {selectedTwinItem && selectedTwinItem.kind !== "reserve" && (
                <button
                  onClick={() => setCascadeOpen(true)}
                  className="flex items-center gap-1 px-2 py-1 font-mono text-[10px] uppercase font-bold rounded border border-critical/40 bg-critical/15 text-critical transition-colors hover:bg-critical/25"
                >
                  <Zap size={11} /> Cascade
                </button>
              )}
            </div>
            {mapMode === "satellite" && layersOpen && baseOptions.length > 0 && (
              <div className="w-[300px]">
                <LayerSwitcher
                  baseOptions={baseOptions}
                  overlayOptions={overlayOptions}
                  base={effectiveBase}
                  overlays={overlays}
                  date={satellite?.date}
                  onBase={setBaseLayer}
                  onToggleOverlay={toggleOverlay}
                />
              </div>
            )}
          </div>
          
          {/* Active Mission Parameters overlay */}
          <div className="tactical-panel p-2 space-y-1.5 w-64 bg-panel/90">
            <div className="flex items-center justify-between">
              <span className="label-terminal">SCENARIO</span>
              <select
                value={scenarioId}
                onChange={(e) => setScenario(e.target.value)}
                className="bg-transparent text-signal font-mono text-xs font-bold outline-none cursor-pointer text-right"
              >
                {scenarios?.map(s => <option key={s.id} value={s.id} className="bg-panel text-ink">{s.name}</option>)}
              </select>
            </div>
            <div className="h-px w-full bg-line" />
            <div className="flex justify-between font-mono text-[10px]">
              <span className="text-ink-muted">Gap:</span>
              <span className="text-red-400 font-bold">{simResult?.supply_gap_kbpd?.toLocaleString() ?? "0"} kbpd</span>
            </div>
            <div className="flex justify-between font-mono text-[10px]">
              <span className="text-ink-muted">Residual:</span>
              <span className="text-amber-500 font-bold">{simResult?.residual_shortfall_kbpd?.toLocaleString() ?? "0"} kbpd</span>
            </div>
            <div className="flex justify-between font-mono text-[10px]">
              <span className="text-ink-muted">Brent Δ:</span>
              <span className="text-amber-500 font-bold">{(simResult?.brent_change_pct ?? 0) > 0 ? "+" : ""}{(simResult?.brent_change_pct ?? 0).toFixed(1)}%</span>
            </div>
          </div>
        </div>
      </div>

      {/* FOREGROUND LAYER: Floating Drawers & HUD (Pointer Events Pass-Through) */}
      <div className="pointer-events-none absolute inset-0 z-20 flex flex-col justify-between overflow-hidden">
        
        {/* Global pointer overlay during resize drag to prevent iframe/canvas event drops */}
        {isResizing && (
          <div className="fixed inset-0 z-[9999] cursor-col-resize select-none pointer-events-auto" />
        )}

        {/* CENTER MIDDLE: Left and Right Floating Drawers */}
        <div className="relative flex-1 mt-12 overflow-hidden">
          
          {/* LEFT DRAWER: Global Intel Feed */}
          {leftDrawer === "intel" && (
            <div className="pointer-events-auto absolute left-[72px] top-4 bottom-4 w-80 tactical-panel bg-panel-hover/90 flex flex-col animate-in slide-in-from-left-8 z-30">
              <div className="flex items-center justify-between border-b border-line p-2 bg-panel">
                <span className="font-mono text-xs font-bold text-signal flex items-center gap-1.5">
                  <Radar size={13} /> Global Intelligence
                </span>
                <button onClick={() => setLeftDrawer("none")} className="text-ink-dim hover:text-ink transition-colors"><Minimize2 size={13}/></button>
              </div>
              <div className="flex-1 overflow-y-auto p-2 space-y-2">
                {intelFeed?.events.map(evt => (
                  <div key={evt.id} className="rounded border border-line bg-panel-hover/80 p-2 cursor-pointer hover:border-signal/50 transition-colors">
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-mono text-[8px] uppercase font-bold px-1.5 py-0.5 rounded" style={{ backgroundColor: `${CATEGORY_COLORS[evt.category]}25`, color: CATEGORY_COLORS[evt.category] }}>
                        {evt.category}
                      </span>
                      <SourceTag kind={evt.source_kind} />
                    </div>
                    <div className="text-xs font-bold text-ink mb-1">{evt.title}</div>
                    <div className="text-[10px] text-ink-muted line-clamp-2 leading-relaxed">{evt.summary}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* CASCADE PANEL: Palantir-style problem -> impact -> act flow */}
          {cascadeOpen && selectedTwinItem && (
            <div className="pointer-events-auto absolute left-[72px] top-4 z-40">
              <CascadePanel
                node={selectedTwinItem}
                onImpactedChange={setImpacted}
                onClose={() => {
                  setCascadeOpen(false);
                  setImpacted({});
                }}
              />
            </div>
          )}

          {/* RIGHT DRAWER: Multi-purpose Inspector */}
          {rightDrawer !== "none" && (
            <div 
              className={cn("pointer-events-auto absolute right-4 top-4 bottom-4 tactical-panel bg-panel-hover/95 flex flex-col animate-in slide-in-from-right-8 z-30", isResizing && "select-none")}
              style={{ width: rightDrawerWidth, maxWidth: "calc(100vw - 90px)", transitionDuration: isResizing ? "0ms" : undefined }}
            >
              {/* Drag Resizer Edge Handle */}
              <div 
                onMouseDown={startResizing}
                title="Drag to resize panel width"
                className="absolute -left-3 top-0 bottom-0 w-6 cursor-col-resize z-50 flex items-center justify-center group pointer-events-auto"
              >
                {/* Visual Accent Line */}
                <div className="h-16 w-1 rounded-full bg-signal/30 group-hover:bg-signal group-hover:h-24 group-hover:shadow-[0_0_8px_rgba(0,240,255,0.8)] transition-all" />
              </div>
              
              {/* Drawer Header */}
              <div className="flex items-center justify-between border-b border-line p-2 bg-panel">
                <div className="flex items-center gap-2">
                  <button onClick={() => setRightDrawer("council")} className={cn("font-mono text-[10px] uppercase font-bold px-2 py-1 rounded transition-colors", rightDrawer === "council" ? "bg-signal/15 text-signal" : "text-ink-dim hover:text-ink hover:bg-panel-hover")}>Council</button>
                  <button onClick={() => setRightDrawer("decision")} className={cn("font-mono text-[10px] uppercase font-bold px-2 py-1 rounded transition-colors", rightDrawer === "decision" ? "bg-signal/15 text-signal" : "text-ink-dim hover:text-ink hover:bg-panel-hover")}>Decision</button>
                  <button onClick={() => { setRightDrawer("ontology"); if (rightDrawerWidth < 800) setRightDrawerWidth(850); }} className={cn("font-mono text-[10px] uppercase font-bold px-2 py-1 rounded transition-colors", rightDrawer === "ontology" ? "bg-signal/15 text-signal" : "text-ink-dim hover:text-ink hover:bg-panel-hover")}>Ontology</button>
                </div>

                {/* Quick Width Presets & Maximize Controls */}
                <div className="flex items-center gap-1.5 font-mono text-[9px]">
                  <span className="text-ink-dim uppercase hidden sm:inline">Width:</span>
                  <button 
                    onClick={() => setRightDrawerWidth(550)}
                    className={cn("px-1.5 py-0.5 rounded border transition-colors", rightDrawerWidth === 550 ? "border-signal/50 text-signal bg-signal/10" : "border-line text-ink-dim hover:text-ink")}
                  >
                    550
                  </button>
                  <button 
                    onClick={() => setRightDrawerWidth(850)}
                    className={cn("px-1.5 py-0.5 rounded border transition-colors", rightDrawerWidth === 850 ? "border-signal/50 text-signal bg-signal/10" : "border-line text-ink-dim hover:text-ink")}
                  >
                    850
                  </button>
                  <button 
                    onClick={toggleMaximizeDrawer} 
                    title="Toggle Maximize Width" 
                    className="p-1 text-ink-dim hover:text-signal transition-colors ml-1"
                  >
                    {rightDrawerWidth > 1000 ? <Minimize2 size={13} /> : <Maximize2 size={13} />}
                  </button>
                  <button onClick={() => setRightDrawer("none")} className="p-1 text-ink-dim hover:text-ink transition-colors"><X size={13}/></button>
                </div>
              </div>

              {/* Drawer Content */}
              <div className="flex-1 overflow-y-auto p-3">
                
                {/* AI Council Chat Log Mode */}
                {rightDrawer === "council" && (
                  <div className="space-y-4">
                    <div className="flex items-center justify-between mb-4">
                      <span className="label-terminal">Live Reasoning Feed</span>
                      <span className="font-mono text-xs font-bold text-signal">Consensus: {councilResult?.consensus_confidence}%</span>
                    </div>
                    {councilResult?.assessments.map(a => (
                      <div key={a.agent_id} className="border-l-2 border-signal pl-3 py-1 space-y-1">
                        <div className="flex items-center justify-between">
                          <span className="font-mono text-[10px] font-bold text-ink">{a.agent_name}</span>
                          <span className="text-[9px] text-signal">{a.confidence}% conf</span>
                        </div>
                        <div className="font-mono text-[10px] text-signal">{a.stance}</div>
                        <p className="text-[11px] text-ink-muted leading-relaxed">{a.reasoning}</p>
                      </div>
                    ))}
                  </div>
                )}

                {/* Decision / Strategies Mode */}
                {rightDrawer === "decision" && (
                  <div className="space-y-3">
                    <div className="label-terminal mb-2">Ranked Operational Doctrines</div>
                    {councilResult?.strategies.map(strat => (
                      <div key={strat.id} onClick={() => selectStrategy(strat.id)} className={cn("tactical-panel p-3 cursor-pointer transition-colors", strat.id === activeStrategyId ? "border-signal/50 bg-signal/10 shadow-glow-signal" : "hover:border-line")}>
                        <div className="flex items-center justify-between font-mono text-[10px] font-bold">
                          <span className="text-ink">{strat.title}</span>
                          <span className="text-signal">{strat.score.toFixed(0)} pts</span>
                        </div>
                        <p className="mt-2 text-[10px] text-ink-muted">{strat.thesis}</p>
                        <button onClick={() => { selectStrategy(strat.id); setBottomDrawer("timeline"); }} className="mt-3 w-full rounded border border-signal/30 bg-signal/10 py-1.5 font-mono text-[10px] font-bold text-signal uppercase hover:bg-signal/20 transition-colors">
                          Stage for Execution
                        </button>
                      </div>
                    ))}
                  </div>
                )}

                {/* Ontology Context Mode */}
                {rightDrawer === "ontology" && (
                  <div className="h-full flex flex-col">
                    <div className="label-terminal mb-2">
                      {selectedTwinItem ? `1-Hop Dependencies: ${selectedTwinItem.id}` : "Full Ontology Context"}
                    </div>
                    <div className="flex-1 bg-canvas rounded border border-line overflow-hidden">
                      <GraphView forceExploreId={selectedTwinItem?.id} />
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* BOTTOM DECK: Simulation Levers & Mission Timeline */}
        <div className="pointer-events-auto mt-auto flex flex-col border-t border-line bg-panel/95 backdrop-blur-md pl-[56px] transition-all">
          
          {/* Mission Timeline Drawer */}
          {bottomDrawer === "timeline" && (
            <div className="border-b border-line p-3 animate-in slide-in-from-bottom-4">
              <div className="flex items-center justify-between mb-2">
                <span className="font-mono text-xs font-bold text-signal">Mission Operations Timeline</span>
                <button onClick={() => setBottomDrawer("none")} className="text-ink-dim hover:text-ink"><Minimize2 size={13}/></button>
              </div>
              <CrisisTimeline />
            </div>
          )}

          {/* Simulation Levers Bar */}
          <div className="flex items-center justify-between px-4 py-2.5">
            <div className="flex items-center gap-6">
              <div className="flex items-center gap-2 border-r border-line pr-4">
                <Sliders size={15} className={activated ? "text-red-500" : "text-signal"} />
                <span className={cn("font-mono text-xs font-bold tracking-wider", activated ? "text-red-500" : "text-ink")}>
                  {activated ? "MISSION PARAMETERS:" : "SIMULATION LEVERS:"}
                </span>
              </div>
              <div className="flex items-center gap-3">
                <span className="label-terminal text-[10px]">SPR Release:</span>
                <input type="range" min={0} max={100} step={5} value={levers.spr_release_pct} onChange={(e) => setLevers({ spr_release_pct: Number(e.target.value) })} disabled={activated} className="w-24 accent-signal" />
                <span className="readout text-[11px] font-bold text-signal w-8">{levers.spr_release_pct}%</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="label-terminal text-[10px]">Reroute Cape:</span>
                <button onClick={() => setLevers({ enable_reroute: !levers.enable_reroute })} disabled={activated} className={cn("rounded px-2.5 py-0.5 font-mono text-[10px] uppercase font-bold border transition-colors", levers.enable_reroute ? "border-emerald-500/40 bg-emerald-500/15 text-emerald-500 shadow-glow-nominal" : "border-line bg-panel text-ink-dim hover:text-ink")}>{levers.enable_reroute ? "ENABLED" : "OFF"}</button>
              </div>
            </div>

            {/* Mission Activation */}
            {!activated ? (
              <button disabled={activating} onClick={handleInitiateMission} className="flex items-center gap-2 rounded border border-signal/50 bg-signal/15 px-4 py-1.5 font-mono text-xs font-bold text-signal hover:bg-signal/25 shadow-glow-signal transition-all disabled:opacity-50">
                <Rocket size={14} /> {activating ? "AUTHORISING..." : "INITIATE MISSION"}
              </button>
            ) : (
              <div className="flex items-center gap-2 rounded border border-red-500/50 bg-red-950/40 px-4 py-1.5 font-mono text-xs font-bold text-red-500 shadow-[0_0_16px_rgba(239,68,68,0.2)] animate-pulse">
                <Rocket size={14} /> MISSION EXECUTING
              </div>
            )}
          </div>
        </div>

      </div>
    </div>
  );
}
