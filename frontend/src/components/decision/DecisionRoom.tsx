"use client";

import { motion } from "framer-motion";
import { Link2, Check, Trophy, Route, ShieldAlert } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCouncil } from "@/hooks/useChanakya";
import { useMission } from "@/stores/useMission";
import { Panel, PanelHeader } from "@/components/primitives";
import type { StrategyOption, EvidenceCitation } from "@/lib/types";
import { cn } from "@/lib/utils";

const OBJECTIVE_LABEL: Record<string, string> = {
  continuity: "Supply Continuity",
  resilience: "Resilience (NESI)",
  affordability: "Affordability",
  reserve: "Reserve Preservation",
  feasibility: "Operational Feasibility",
  evidence: "Evidence Confidence",
  council_alignment: "Council Alignment",
};

export function DecisionRoom() {
  const router = useRouter();
  const { scenarioId, levers, selectedStrategyId, selectStrategy } = useMission();
  const { data, isLoading } = useCouncil(scenarioId, levers);

  const strategies = data?.strategies ?? [];
  const activeId = selectedStrategyId ?? data?.recommended_strategy_id;
  const activeStrategy = strategies.find((strategy) => strategy.id === activeId);

  return (
    <div className="flex h-full flex-col gap-3 overflow-y-auto p-4 blueprint">
      <Panel className="flex items-center justify-between px-4 py-3">
        <div>
          <div className="label-terminal">Decision Engine · {data?.scenario_name ?? "…"}</div>
          <div className="text-sm font-semibold text-ink">
            Three ranked national response strategies
          </div>
        </div>
        {data && (
          <div className="flex items-center gap-1.5 text-xs text-signal">
            <Trophy size={14} />
            <span className="readout uppercase">{data.recommended_strategy_id.replace("_", " ")}</span>
          </div>
        )}
      </Panel>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
        {isLoading &&
          Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-96 animate-pulse rounded-lg bg-panel/60" />
          ))}
        {strategies.map((s, i) => (
          <StrategyCard
            key={s.id}
            s={s}
            index={i}
            active={activeId === s.id}
            recommended={data?.recommended_strategy_id === s.id}
            onSelect={() => selectStrategy(s.id)}
            onExecute={() => {
              selectStrategy(s.id);
              router.push("/execution");
            }}
          />
        ))}
      </div>
      {activeStrategy && <ProcurementTable strategy={activeStrategy} />}
    </div>
  );
}

function StrategyCard({
  s,
  index,
  active,
  recommended,
  onSelect,
  onExecute,
}: {
  s: StrategyOption;
  index: number;
  active: boolean;
  recommended: boolean;
  onSelect: () => void;
  onExecute: () => void;
}) {
  const p = s.projection;
  const infeasibilityReasons = s.infeasibility_reasons ?? [];
  const benefits = s.benefits ?? [];
  const tradeoffs = s.tradeoffs ?? [];
  const scores = s.scores ?? {};
  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.08 }}
    >
      <Panel
        className={cn(
          "flex h-full flex-col p-4 transition-colors",
          active ? "border-signal/50 shadow-glow-signal" : "",
        )}
        onClick={onSelect}
      >
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2">
              <span className="readout text-xs text-ink-dim">#{s.rank}</span>
              {recommended && (
                <span className="rounded bg-signal/15 px-1.5 py-0.5 font-mono text-[10px] uppercase text-signal">
                  Recommended
                </span>
              )}
            </div>
            <h3 className="mt-1 text-base font-semibold text-ink">{s.title}</h3>
          </div>
          <div className="text-right">
            <div className="label-terminal">Score</div>
            <div className="readout text-2xl font-bold text-signal">{s.score.toFixed(0)}</div>
          </div>
        </div>

        <p className="mt-2 text-xs leading-relaxed text-ink-muted">{s.thesis}</p>
        {s.optimization && (
          <div className="mt-2 flex items-center justify-between rounded border border-line bg-base/40 px-2 py-1.5 font-mono text-[9px] uppercase text-ink-dim">
            <span>{s.optimization.method.replaceAll("_", " ")}</span>
            <span className="text-signal">{s.optimization.candidate_count} candidates</span>
          </div>
        )}
        {!s.feasible && (
          <div className="mt-2 flex gap-1.5 rounded border border-critical/30 bg-critical/10 p-2 text-[11px] text-critical">
            <ShieldAlert size={13} className="shrink-0" />
            {infeasibilityReasons[0] ?? "Operational constraints are unresolved."}
          </div>
        )}

        {/* Objective scores */}
        <div className="mt-3 space-y-1.5">
          {Object.entries(scores).map(([k, v]) => (
            <div key={k} className="flex items-center gap-2">
              <span className="w-28 shrink-0 text-[10px] uppercase tracking-wider text-ink-dim">
                {OBJECTIVE_LABEL[k] ?? k}
              </span>
              <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-line">
                <div className="h-full rounded-full bg-signal/70" style={{ width: `${v}%` }} />
              </div>
              <span className="readout w-8 text-right text-[10px] text-ink">{v.toFixed(0)}</span>
            </div>
          ))}
        </div>

        {/* Projection metrics */}
        <div className="mt-3 grid grid-cols-2 gap-2 rounded border border-line bg-panel/50 p-2.5">
          <Metric label="Residual" value={`${p.residual_shortfall_kbpd.toLocaleString()} kbpd`} />
          <Metric label="Utilisation" value={`${p.national_utilization_pct.toFixed(0)}%`} />
          <Metric label="Brent" value={`${p.brent_change_pct >= 0 ? "+" : ""}${p.brent_change_pct.toFixed(0)}%`} />
          <Metric label="NESI" value={p.nesi_after.toFixed(0)} />
          <Metric label="SPR draw" value={`${p.spr_release_kbpd.toLocaleString()} kbpd`} />
          <Metric label="Diesel" value={`₹${p.diesel_projected_inr.toFixed(1)}`} />
        </div>

        <div className="mt-3 grid grid-cols-1 gap-2 text-xs">
          <div>
            <div className="label-terminal mb-1 text-nominal">Benefits</div>
            {benefits.slice(0, 2).map((b, i) => (
              <div key={i} className="flex gap-1.5 text-ink-muted">
                <Check size={12} className="mt-0.5 shrink-0 text-nominal" />
                {b}
              </div>
            ))}
          </div>
          <div>
            <div className="label-terminal mb-1 text-elevated">Trade-offs</div>
            {tradeoffs.slice(0, 2).map((t, i) => (
              <div key={i} className="flex gap-1.5 text-ink-muted">
                <span className="mt-0.5 shrink-0 text-elevated">–</span>
                {t}
              </div>
            ))}
          </div>
        </div>

        {/* Evidence Chain */}
        {s.evidence_chain && s.evidence_chain.length > 0 && (
          <div className="mt-3 rounded border border-line/60 bg-panel/40 p-2 text-xs">
            <div className="label-terminal mb-1.5 flex items-center justify-between text-signal">
              <span>Supporting Evidence Chain</span>
              <span className="font-mono text-[9px] text-ink-dim">{s.evidence_chain.length} citations</span>
            </div>
            <div className="space-y-1">
              {s.evidence_chain.slice(0, 3).map((item: EvidenceCitation, idx: number) => (
                <div key={idx} className="flex items-start justify-between gap-2 text-[11px]">
                  <span className="text-ink-muted line-clamp-1 flex-1">
                    <span className="font-mono text-[9px] text-ink-dim uppercase">[{item.source}]</span>{" "}
                    {item.title}
                  </span>
                  <span className="font-mono text-[9px] text-nominal shrink-0">{item.confidence}%</span>
                </div>
              ))}
            </div>
          </div>
        )}

        <button
          onClick={(e) => {
            e.stopPropagation();
            onExecute();
          }}
          className="mt-4 flex items-center justify-center gap-1.5 rounded-md border border-signal/40 bg-signal/10 py-2 text-xs font-semibold uppercase tracking-wider text-signal transition-colors hover:bg-signal/20"
        >
          <Link2 size={13} /> Send to Mission Execution
        </button>
      </Panel>
    </motion.div>
  );
}

function ProcurementTable({ strategy }: { strategy: StrategyOption }) {
  const alternatives = strategy.procurement_alternatives ?? [];
  return (
    <Panel>
      <PanelHeader
        eyebrow="Executable Sourcing · Selected Doctrine"
        title="Replacement Cargo Board"
        right={<div className="flex items-center gap-1.5 text-xs text-signal"><Route size={14} />
          {alternatives.filter((item) => item.feasible).length} feasible</div>}
      />
      <div className="overflow-x-auto">
        <table className="w-full min-w-[1100px] border-collapse text-left text-xs">
          <thead className="label-terminal border-b border-line bg-base/70">
            <tr>{["Supplier / grade", "Volume", "Route", "Arrival", "Landed premium", "Tanker / port", "Refinery fit", "Constraint", "Evidence"].map((label) =>
              <th key={label} className="px-3 py-2 font-medium">{label}</th>)}</tr>
          </thead>
          <tbody className="divide-y divide-line">
            {alternatives.map((item) => (
              <tr key={item.supplier_id} className={item.feasible ? "bg-nominal/[0.025]" : "opacity-55"}>
                <td className="px-3 py-2.5"><div className="font-semibold text-ink">{item.supplier}</div>
                  <div className="font-mono text-[10px] uppercase text-ink-dim">{item.crude_grade.replaceAll("_", " ")}</div></td>
                <td className="readout px-3 py-2.5 text-ink">{item.volume_kbpd.toLocaleString()} kbpd</td>
                <td className="px-3 py-2.5 text-ink-muted">{item.route}</td>
                <td className="readout px-3 py-2.5 text-ink">
                  <div>T+{item.eta_days}d</div>
                  <div className={item.arrives_within_horizon ? "text-[9px] text-nominal" : "text-[9px] text-critical"}>{item.arrives_within_horizon ? "within horizon" : "late cargo"}</div>
                </td>
                <td className="readout px-3 py-2.5 text-energy">
                  <div>+${item.landed_premium_usd_bbl.toFixed(1)}/bbl</div>
                  <div className="text-[9px] text-ink-dim">war risk ${item.war_risk_premium_usd_bbl.toFixed(1)}</div>
                </td>
                <td className="px-3 py-2.5 text-ink-muted">
                  <div>{item.tanker_status}</div>
                  <div className="font-mono text-[9px]">port +{item.port_congestion_days.toFixed(1)}d · charter +{item.charter_delay_days.toFixed(1)}d</div>
                </td>
                <td className="max-w-[190px] px-3 py-2.5 text-ink-muted">{item.compatible_refineries.slice(0, 2).join(", ") || "None"}</td>
                <td className="max-w-[220px] px-3 py-2.5">
                  <span className={item.feasible ? "text-nominal" : "text-critical"}>{item.capacity_constraint}</span>
                </td>
                <td className="px-3 py-2.5">
                  <div className="readout text-ink">{item.confidence.toFixed(0)}%</div>
                  <div className="font-mono text-[9px] uppercase text-ink-dim">{Object.values(item.provenance).join(" · ")}</div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="label-terminal">{label}</div>
      <div className="readout text-sm font-semibold text-ink">{value}</div>
    </div>
  );
}
