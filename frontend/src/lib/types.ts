/** Shared API response types mirroring the FastAPI/domain models. */

import type { Severity } from "./severity";

// ---- Intelligence ----
export interface IntelEvent {
  id: string;
  title: string;
  summary: string;
  category: "geopolitical" | "shipping" | "market" | "weather" | "sanctions" | "satellite";
  severity: Severity;
  confidence: number;
  risk_score: number;
  affected_countries: string[];
  affected_corridors: string[];
  estimated_duration_days: number | null;
  lat: number | null;
  lon: number | null;
  source: string;
  source_kind: "live" | "cached" | "replay" | "simulated" | "unavailable";
  published_at: string;
  provenance?: string;
  freshness_seconds?: number;
  stale?: boolean;
  schema_version?: string;
  evidence: { label: string; detail: string; url?: string | null }[];
}

export interface PriceQuote {
  symbol: string;
  price_usd: number;
  change_pct: number;
  source: string;
  source_kind: string;
}

export interface WeatherObs {
  location_id: string;
  location_name: string;
  lat: number;
  lon: number;
  wind_kph: number;
  wave_m: number | null;
  condition: string;
  shipping_risk: Severity;
  source_kind: string;
}

export interface Vessel {
  id: string;
  name: string;
  kind: string;
  lat: number;
  lon: number;
  heading: number;
  speed_kn: number;
  corridor_id: string | null;
  origin: string | null;
  destination: string | null;
  cargo_kbbl: number | null;
  track?: [number, number][];
}

// ---- Satellite imagery (NASA GIBS) ----
export interface SatelliteLayer {
  id: string;
  label: string;
  kind: "base" | "overlay";
  max_native_zoom: number;
  ext: string;
  url_template: string;
}
export interface SatelliteLayersResponse {
  provider: string;
  keyless: boolean;
  date: string;
  attribution: string;
  layers: SatelliteLayer[];
}

// ---- Ontology cascade ----
export interface CascadeImpact {
  id: string;
  type: string;
  label: string;
  relation: string;
  crude_short_kbpd: number;
  utilization_before: number | null;
  utilization_after: number | null;
  status: "nominal" | "elevated" | "strained" | "critical" | "offline";
  isolated: boolean;
  note: string;
}
export interface CascadeMacro {
  nesi_before: number;
  nesi_after: number;
  nesi_band: string;
  brent_change_pct: number;
  residual_shortfall_kbpd: number;
  diesel_projected_inr: number;
}
export interface CascadeResult {
  origin: { id: string; type: string; label: string };
  block_fraction: number;
  affected: CascadeImpact[];
  hops: { source: string; target: string; relation: string; magnitude_kbpd: number }[];
  isolated: string[];
  rollup: {
    total_crude_short_kbpd: number;
    pct_national_throughput: number;
    refineries_affected: number;
    refineries_offline: number;
    refineries_critical: number;
    isolated_count: number;
    spr_bridge_days: number;
    est_diesel_output_loss_kbpd: number;
  };
  macro_projection: CascadeMacro | null;
  narrative: string;
}

export interface IntelSummary {
  event_count: number;
  by_severity: Record<string, number>;
  corridors_flagged: Record<string, number>;
  provenance: Record<string, number>;
  peak_risk_score: number;
  threat_level: Severity;
  is_live: boolean;
}

export interface IntelFeed {
  summary: IntelSummary;
  events: IntelEvent[];
  prices: PriceQuote[];
  weather: WeatherObs[];
  vessels: Vessel[];
  sanctions: {
    id: string;
    program: string;
    target: string;
    description: string;
    affected_countries: string[];
    source_kind: string;
  }[];
}

// ---- Network / Digital Twin ----
export interface GeoPoint {
  lat: number;
  lon: number;
}
export interface Corridor {
  id: string;
  name: string;
  chokepoint: string;
  import_share: number;
  base_transit_days: number;
  status: string;
  path: GeoPoint[];
}
export interface Supplier {
  id: string;
  country: string;
  import_share: number;
  grade: string;
  corridor_id: string;
  reliability: number;
  spare_capacity_kbpd: number;
  sanctioned: boolean;
  coords: GeoPoint;
}
export interface Port {
  id: string;
  name: string;
  coast: string;
  coords: GeoPoint;
  crude_capacity_kbpd: number;
  status: string;
}
export interface Refinery {
  id: string;
  name: string;
  operator: string;
  coords: GeoPoint;
  coast: string;
  nameplate_kbpd: number;
  throughput_kbpd: number;
  preferred_grade: string;
  inventory_days: number;
  status: string;
  utilization: number;
}
export interface ReserveSite {
  id: string;
  name: string;
  coords: GeoPoint;
  capacity_mmt: number;
  fill_pct: number;
  stored_mmt: number;
}
export interface NetworkData {
  suppliers: Supplier[];
  corridors: Corridor[];
  ports: Port[];
  refineries: Refinery[];
  reserves: ReserveSite[];
  market: { brent_usd: number; inr_usd: number; retail_diesel_inr_per_l: number; retail_petrol_inr_per_l: number };
  demand: { refinery_demand_kbpd: number; import_dependence_pct: number };
  aggregates: {
    total_refining_capacity_kbpd: number;
    total_throughput_kbpd: number;
    daily_crude_imports_kbpd: number;
    spr_total_mmt: number;
    spr_coverage_days: number;
    supplier_hhi: number;
  };
}

// ---- Scenarios / Simulation ----
export interface ResponseLevers {
  spr_release_pct: number;
  enable_reroute: boolean;
  enable_spot: boolean;
}
export interface ScenarioSpec {
  id: string;
  name: string;
  category: string;
  description: string;
  shock: Record<string, unknown>;
  default_levers: ResponseLevers;
}
export interface ImpactLine {
  label: string;
  value: number;
  unit: string;
  detail: string;
}
export interface NesiComponentT {
  key: string;
  label: string;
  score: number;
  weight: number;
  detail: string;
}
export interface SimulationResult {
  scenario_id: string;
  scenario_name: string;
  duration_days: number;
  supply_gap_kbpd: number;
  rerouted_kbpd: number;
  replaced_spare_kbpd: number;
  replaced_spot_kbpd: number;
  spr_release_kbpd: number;
  residual_shortfall_kbpd: number;
  spr_days_remaining: number;
  national_utilization_pct: number;
  stressed_refineries: string[];
  brent_projected_usd: number;
  brent_change_pct: number;
  diesel_projected_inr: number;
  petrol_projected_inr: number;
  inflation_bps: number;
  gdp_impact_pct: number;
  transit_delay_days: number;
  freight_premium_pct: number;
  est_daily_cost_musd: number;
  nesi_before: number;
  nesi_after: { value: number; band: string; components: NesiComponentT[] };
  headline: string;
  assumptions: string[];
  impact_lines: ImpactLine[];
  daily_balance: {
    day: number;
    disrupted_kbpd: number;
    reroute_arrivals_kbpd: number;
    replacement_arrivals_kbpd: number;
    inventory_draw_kbpd: number;
    spr_draw_kbpd: number;
    residual_shortfall_kbpd: number;
    spr_remaining_mmt: number;
  }[];
  spr_consumed_mmt: number;
  spr_remaining_mmt: number;
  feasibility_warnings: string[];
}

// ---- Council / Decision ----
export interface AgentAssessment {
  agent_id: string;
  agent_name: string;
  role: string;
  stance: string;
  observations: string[];
  reasoning: string;
  recommendation: string;
  concerns: string[];
  confidence: number;
  evidence: { label: string; detail: string; url?: string | null; publisher?: string | null }[];
  key_metrics: Record<string, number | string>;
  reasoning_mode: "llm" | "grounded";
}
export interface StrategyOption {
  id: string;
  title: string;
  thesis: string;
  levers: ResponseLevers;
  benefits: string[];
  tradeoffs: string[];
  implementation_steps: string[];
  projection: {
    residual_shortfall_kbpd: number;
    national_utilization_pct: number;
    brent_change_pct: number;
    diesel_projected_inr: number;
    spr_release_kbpd: number;
    spr_days_remaining: number;
    nesi_after: number;
    est_daily_cost_musd: number;
  };
  scores: Record<string, number>;
  score: number;
  confidence: number;
  rank: number;
  feasible: boolean;
  infeasibility_reasons: string[];
  procurement_alternatives: ProcurementAlternative[];
  evidence_chain?: EvidenceCitation[];
}
export interface ProcurementAlternative {
  supplier_id: string;
  supplier: string;
  crude_grade: string;
  compatible_refineries: string[];
  volume_kbpd: number;
  route: string;
  eta_days: number;
  transit_delay_days: number;
  estimated_premium_usd_bbl: number;
  capacity_constraint: string;
  confidence: number;
  feasible: boolean;
  evidence: string[];
}
export interface CouncilResult {
  scenario_id: string;
  scenario_name: string;
  assessments: AgentAssessment[];
  strategies: StrategyOption[];
  disagreements: { topic: string; positions: { agent: string; stance: string }[] }[];
  consensus_confidence: number;
  reasoning_mode: "llm" | "grounded";
  recommended_strategy_id: string;
  workflow_run_id: string;
  workflow_trace?: WorkflowStep[];
  mission_id: string | null;
  schema_version: string;
  provenance: Record<string, unknown>;
}

export interface MissionRecord extends Record<string, unknown> {
  id: string;
  workflow_run_id: string | null;
  scenario_id: string;
  strategy_id: string;
  status: string;
  created_at: string;
  activated_at: string | null;
  strategy?: StrategyOption;
  workflow?: Record<string, unknown> | null;
}

// ---- Knowledge Graph ----
export interface GraphNode {
  id: string;
  type: "supplier" | "corridor" | "port" | "refinery" | "reserve" | "event" | "vessel";
  label: string;
  position: { x: number; y: number };
  meta: Record<string, unknown>;
}
export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  label: string;
  kind?: string;
}
export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  backend?: "neo4j" | "in_memory";
  degraded?: boolean;
  schema_version?: string;
}

export interface SourceStatus {
  source: string;
  healthy: boolean;
  provenance: "live" | "cached" | "replay" | "simulated" | "unavailable";
  last_checked_at: string;
  last_success_at?: string;
  last_failure_at?: string;
  last_event_at?: string;
  event_count: number;
  last_error?: string | null;
  configured?: boolean;
}

// ---- Ontology Explorer ----
export interface OntologyEntity {
  id: string;
  type: string;
  label: string;
  neo4j_label?: string;
  meta: Record<string, unknown>;
}
export interface OntologyRelationship {
  source: string;
  target: string;
  label: string;
  meta: Record<string, unknown>;
}
export interface OntologyExploreResult {
  nodes: OntologyEntity[];
  edges: OntologyRelationship[];
  center: string;
  depth: number;
  backend: "neo4j" | "in_memory";
  degraded: boolean;
}
export interface OntologyImpactChainStep {
  id: string;
  type: string;
  label: string;
  step?: string;
}
export interface OntologyImpactResult {
  nodes: OntologyEntity[];
  edges: OntologyRelationship[];
  chain: OntologyImpactChainStep[];
  event_id: string;
  backend: "neo4j" | "in_memory";
  degraded: boolean;
}
export interface OntologySearchResult {
  results: OntologyEntity[];
  query: string;
  backend: "neo4j" | "in_memory";
  degraded: boolean;
}
export interface OntologyStats {
  node_counts: Record<string, number>;
  relationship_counts: Record<string, number>;
  total_nodes: number;
  total_relationships: number;
  backend: "neo4j" | "in_memory";
  degraded: boolean;
}

// ---- Workflow Trace ----
export interface WorkflowStep {
  node: string;
  label: string;
  started_at: string;
  completed_at: string;
  duration_ms: number;
  status: string;
  outputs_summary: string;
}

// ---- Evidence Chain ----
export interface EvidenceCitation {
  source: string;
  event_id?: string | null;
  title: string;
  confidence: number;
  category: string;
}

