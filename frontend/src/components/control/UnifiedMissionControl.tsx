"use client";

import { useState, useMemo, useEffect } from "react";
import dynamic from "next/dynamic";
import { usePathname, useRouter } from "next/navigation";
import {
  Radar, Globe2, Share2, Users, Brain, Rocket, Crosshair, Minimize2, Maximize2, Search, Sliders, Play, Layers
} from "lucide-react";
import {
  useIntelFeed, useNetwork, useScenarios, useSimulation, useCouncil, useSourceStatus
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
  
  const [activating, setActivating] = useState(false);

  // Workspace View State
  const [mapMode, setMapMode] = useState<MapMode>("satellite");
  const [selectedTwinItem, setSelectedTwinItem] = useState<TwinSelection | null>(null);
  
  // Drawer States
  const [leftDrawer, setLeftDrawer] = useState<"intel" | "none">(pathname === "/intelligence" ? "intel" : pathname === "/" ? "intel" : "none");
  const [rightDrawer, setRightDrawer] = useState<"council" | "ontology" | "decision" | "none">(
    pathname === "/council" ? "council" : pathname === "/decision" ? "decision" : pathname === "/digital-twin" ? "ontology" : "none"
  );
  const [bottomDrawer, setBottomDrawer] = useState<"timeline" | "none">(
    pathname === "/execution" || pathname === "/simulation" || activated ? "timeline" : "none"
  );

  // Sync pathname changes to drawer states
  useEffect(() => {
    if (pathname === "/intelligence") { setLeftDrawer("intel"); setRightDrawer("none"); }
    else if (pathname === "/council") { setRightDrawer("council"); }
    else if (pathname === "/decision") { setRightDrawer("decision"); }
    else if (pathname === "/digital-twin") { setRightDrawer("ontology"); }
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
    <div className="relative h-full w-full overflow-hidden bg-[#04060a] text-[#e6edf7] font-sans select-none">
      
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
            onSelect={(item) => {
              setSelectedTwinItem(item);
              setRightDrawer("ontology");
            }}
          />
        )}
        
        {/* Map Context Overlay (Top Center inside map) */}
        <div className="absolute top-16 left-1/2 -translate-x-1/2 z-10 flex gap-4 pointer-events-auto items-start">
          <div className="tactical-panel flex items-center gap-2 p-1.5 bg-[#080d1a]/95">
            <button
              onClick={() => setMapMode("satellite")}
              className={cn("px-2 py-1 font-mono text-[10px] uppercase font-bold rounded transition-colors", mapMode === "satellite" ? "bg-[#00f0ff]/15 text-[#00f0ff] border border-[#00f0ff]/40" : "text-[#5a677f]")}
            >
              Satellite
            </button>
            <button
              onClick={() => setMapMode("operations")}
              className={cn("px-2 py-1 font-mono text-[10px] uppercase font-bold rounded transition-colors", mapMode === "operations" ? "bg-[#00f0ff]/15 text-[#00f0ff] border border-[#00f0ff]/40" : "text-[#5a677f]")}
            >
              Operations
            </button>
          </div>
          
          {/* Active Mission Parameters overlay */}
          <div className="tactical-panel p-2 space-y-1.5 w-64 bg-[#080d1a]/90">
            <div className="flex items-center justify-between">
              <span className="label-terminal">SCENARIO</span>
              <select
                value={scenarioId}
                onChange={(e) => setScenario(e.target.value)}
                className="bg-transparent text-[#00f0ff] font-mono text-xs font-bold outline-none cursor-pointer text-right"
              >
                {scenarios?.map(s => <option key={s.id} value={s.id} className="bg-void">{s.name}</option>)}
              </select>
            </div>
            <div className="h-px w-full bg-[#1b2a4a]" />
            <div className="flex justify-between font-mono text-[10px]">
              <span className="text-[#8b99b3]">Gap:</span>
              <span className="text-red-400 font-bold">{simResult?.supply_gap_kbpd?.toLocaleString() ?? "0"} kbpd</span>
            </div>
            <div className="flex justify-between font-mono text-[10px]">
              <span className="text-[#8b99b3]">Residual:</span>
              <span className="text-amber-400 font-bold">{simResult?.residual_shortfall_kbpd?.toLocaleString() ?? "0"} kbpd</span>
            </div>
            <div className="flex justify-between font-mono text-[10px]">
              <span className="text-[#8b99b3]">Brent Δ:</span>
              <span className="text-amber-400 font-bold">{(simResult?.brent_change_pct ?? 0) > 0 ? "+" : ""}{(simResult?.brent_change_pct ?? 0).toFixed(1)}%</span>
            </div>
          </div>
        </div>
      </div>

      {/* =========================================================================
          FOREGROUND LAYER: Floating Drawers & HUD (Pointer Events Pass-Through)
          ========================================================================= */}
      <div className="pointer-events-none absolute inset-0 z-20 flex flex-col justify-between overflow-hidden">
        
        {/* CENTER MIDDLE: Left and Right Drawers */}
        <div className="flex flex-1 items-start justify-between py-4 pr-4 pl-[72px] overflow-hidden mt-12">
          
          {/* LEFT DRAWER: Global Intel Feed */}
          {leftDrawer === "intel" && (
            <div className="pointer-events-auto h-full w-80 tactical-panel bg-[#060a12]/90 flex flex-col animate-in slide-in-from-left-8">
              <div className="flex items-center justify-between border-b border-[#1b2a4a] p-2 bg-[#080d1a]">
                <span className="font-mono text-xs font-bold text-[#00f0ff] flex items-center gap-1.5">
                  <Radar size={13} /> Global Intelligence
                </span>
                <button onClick={() => setLeftDrawer("none")} className="text-[#5a677f] hover:text-[#e6edf7]"><Minimize2 size={13}/></button>
              </div>
              <div className="flex-1 overflow-y-auto p-2 space-y-2">
                {intelFeed?.events.map(evt => (
                  <div key={evt.id} className="rounded border border-[#1b2a4a] bg-[#0c1220]/80 p-2 cursor-pointer hover:border-[#00f0ff]/50 transition-colors">
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-mono text-[8px] uppercase font-bold px-1.5 py-0.5 rounded" style={{ backgroundColor: `${CATEGORY_COLORS[evt.category]}25`, color: CATEGORY_COLORS[evt.category] }}>
                        {evt.category}
                      </span>
                      <SourceTag kind={evt.source_kind} />
                    </div>
                    <div className="text-xs font-bold text-[#e6edf7] mb-1">{evt.title}</div>
                    <div className="text-[10px] text-[#8b99b3] line-clamp-2 leading-relaxed">{evt.summary}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
          {!leftDrawer || leftDrawer === "none" && <div />} {/* Spacer */}

          {/* RIGHT DRAWER: Multi-purpose Inspector */}
          {rightDrawer !== "none" && (
            <div className="pointer-events-auto h-full w-96 tactical-panel bg-[#060a12]/95 flex flex-col animate-in slide-in-from-right-8">
              
              {/* Drawer Header */}
              <div className="flex items-center justify-between border-b border-[#1b2a4a] p-2 bg-[#080d1a]">
                <div className="flex gap-2">
                  <button onClick={() => setRightDrawer("council")} className={cn("font-mono text-[10px] uppercase font-bold px-2 py-1 rounded transition-colors", rightDrawer === "council" ? "bg-[#00f0ff]/15 text-[#00f0ff]" : "text-[#5a677f] hover:text-[#e6edf7]")}>Council</button>
                  <button onClick={() => setRightDrawer("decision")} className={cn("font-mono text-[10px] uppercase font-bold px-2 py-1 rounded transition-colors", rightDrawer === "decision" ? "bg-[#00f0ff]/15 text-[#00f0ff]" : "text-[#5a677f] hover:text-[#e6edf7]")}>Decision</button>
                  <button onClick={() => setRightDrawer("ontology")} className={cn("font-mono text-[10px] uppercase font-bold px-2 py-1 rounded transition-colors", rightDrawer === "ontology" ? "bg-[#00f0ff]/15 text-[#00f0ff]" : "text-[#5a677f] hover:text-[#e6edf7]")}>Ontology</button>
                </div>
                <button onClick={() => setRightDrawer("none")} className="text-[#5a677f] hover:text-[#e6edf7]"><Minimize2 size={13}/></button>
              </div>

              {/* Drawer Content */}
              <div className="flex-1 overflow-y-auto p-3">
                
                {/* AI Council Chat Log Mode */}
                {rightDrawer === "council" && (
                  <div className="space-y-4">
                    <div className="flex items-center justify-between mb-4">
                      <span className="label-terminal">Live Reasoning Feed</span>
                      <span className="font-mono text-xs font-bold text-[#00f0ff]">Consensus: {councilResult?.consensus_confidence}%</span>
                    </div>
                    {councilResult?.assessments.map(a => (
                      <div key={a.agent_id} className="border-l-2 border-[#00f0ff] pl-3 py-1 space-y-1">
                        <div className="flex items-center justify-between">
                          <span className="font-mono text-[10px] font-bold text-[#e6edf7]">{a.agent_name}</span>
                          <span className="text-[9px] text-[#00f0ff]">{a.confidence}% conf</span>
                        </div>
                        <div className="font-mono text-[10px] text-[#00f0ff]">{a.stance}</div>
                        <p className="text-[11px] text-[#8b99b3] leading-relaxed">{a.reasoning}</p>
                      </div>
                    ))}
                  </div>
                )}

                {/* Decision / Strategies Mode */}
                {rightDrawer === "decision" && (
                  <div className="space-y-3">
                    <div className="label-terminal mb-2">Ranked Operational Doctrines</div>
                    {councilResult?.strategies.map(strat => (
                      <div key={strat.id} onClick={() => selectStrategy(strat.id)} className={cn("tactical-panel p-3 cursor-pointer transition-colors", strat.id === activeStrategyId ? "border-[#00f0ff]/50 bg-[#00f0ff]/10" : "hover:border-[#1b2a4a]")}>
                        <div className="flex items-center justify-between font-mono text-[10px] font-bold">
                          <span className="text-[#e6edf7]">{strat.title}</span>
                          <span className="text-[#00f0ff]">{strat.score.toFixed(0)} pts</span>
                        </div>
                        <p className="mt-2 text-[10px] text-[#8b99b3]">{strat.thesis}</p>
                        <button onClick={() => { selectStrategy(strat.id); setBottomDrawer("timeline"); }} className="mt-3 w-full rounded border border-[#00f0ff]/30 bg-[#00f0ff]/10 py-1.5 font-mono text-[10px] font-bold text-[#00f0ff] uppercase hover:bg-[#00f0ff]/20">
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
                    <div className="flex-1 bg-[#04060a] rounded border border-[#1b2a4a] overflow-hidden">
                      <GraphView forceExploreId={selectedTwinItem?.id} />
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* BOTTOM DECK: Simulation Levers & Mission Timeline */}
        <div className="pointer-events-auto mt-auto flex flex-col border-t border-[#1b2a4a] bg-[#060a12]/95 backdrop-blur pl-[56px]">
          
          {/* Mission Timeline Drawer */}
          {bottomDrawer === "timeline" && (
            <div className="border-b border-[#1b2a4a] p-3 animate-in slide-in-from-bottom-4">
              <div className="flex items-center justify-between mb-2">
                <span className="font-mono text-xs font-bold text-[#00f0ff]">Mission Operations Timeline</span>
                <button onClick={() => setBottomDrawer("none")} className="text-[#5a677f] hover:text-[#e6edf7]"><Minimize2 size={13}/></button>
              </div>
              <CrisisTimeline />
            </div>
          )}

          {/* Simulation Levers Bar */}
          <div className="flex items-center justify-between px-4 py-2.5">
            <div className="flex items-center gap-6">
              <div className="flex items-center gap-2 border-r border-[#1b2a4a] pr-4">
                <Sliders size={15} className={activated ? "text-red-400" : "text-[#00f0ff]"} />
                <span className={cn("font-mono text-xs font-bold tracking-wider", activated ? "text-red-400" : "text-[#e6edf7]")}>
                  {activated ? "MISSION PARAMETERS:" : "SIMULATION LEVERS:"}
                </span>
              </div>
              <div className="flex items-center gap-3">
                <span className="label-terminal text-[10px]">SPR Release:</span>
                <input type="range" min={0} max={100} step={5} value={levers.spr_release_pct} onChange={(e) => setLevers({ spr_release_pct: Number(e.target.value) })} disabled={activated} className="w-24 accent-[#00f0ff]" />
                <span className="readout text-[11px] font-bold text-[#00f0ff] w-8">{levers.spr_release_pct}%</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="label-terminal text-[10px]">Reroute Cape:</span>
                <button onClick={() => setLevers({ enable_reroute: !levers.enable_reroute })} disabled={activated} className={cn("rounded px-2.5 py-0.5 font-mono text-[10px] uppercase font-bold border", levers.enable_reroute ? "border-emerald-500/40 bg-emerald-500/15 text-emerald-400" : "border-[#1b2a4a] bg-[#080d1a] text-[#5a677f]")}>{levers.enable_reroute ? "ENABLED" : "OFF"}</button>
              </div>
            </div>

            {/* Mission Activation */}
            {!activated ? (
              <button disabled={activating} onClick={handleInitiateMission} className="flex items-center gap-2 rounded border border-[#00f0ff]/50 bg-[#00f0ff]/15 px-4 py-1.5 font-mono text-xs font-bold text-[#00f0ff] hover:bg-[#00f0ff]/25 shadow-[0_0_16px_rgba(0,240,255,0.2)] transition-all disabled:opacity-50">
                <Rocket size={14} /> {activating ? "AUTHORISING..." : "INITIATE MISSION"}
              </button>
            ) : (
              <div className="flex items-center gap-2 rounded border border-red-500/50 bg-red-950/40 px-4 py-1.5 font-mono text-xs font-bold text-red-400 shadow-[0_0_16px_rgba(239,68,68,0.2)] animate-pulse">
                <Rocket size={14} /> MISSION EXECUTING
              </div>
            )}
          </div>
        </div>

      </div>
    </div>
  );
}
