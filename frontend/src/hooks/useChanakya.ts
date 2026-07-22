"use client";

import { useQuery } from "@tanstack/react-query";
import { ApiError, apiGet, apiPost } from "@/lib/api";
import type {
  CascadeResult,
  CouncilResult,
  GraphData,
  IntelFeed,
  MissionRecord,
  NetworkData,
  SatelliteLayersResponse,
  ScenarioSpec,
  SimulationResult,
  ResponseLevers,
  SourceStatus,
  OntologyExploreResult,
  OntologyImpactResult,
  OntologySearchResult,
  OntologyStats,
  OntologySchema,
  OperationalSnapshot,
} from "@/lib/types";

/** Live fused intelligence feed (events + prices + weather + vessels). */
export function useIntelFeed() {
  return useQuery<IntelFeed>({
    queryKey: ["intel-feed"],
    queryFn: () => apiGet<IntelFeed>("/api/intelligence/feed"),
    refetchInterval: 30_000,
  });
}

/** The digital-twin network (static baseline). */
export function useNetwork() {
  return useQuery<NetworkData>({
    queryKey: ["network"],
    queryFn: () => apiGet<NetworkData>("/api/network"),
    staleTime: Infinity,
  });
}

/** Scenario catalog. */
export function useScenarios() {
  return useQuery<ScenarioSpec[]>({
    queryKey: ["scenarios"],
    queryFn: () => apiGet<ScenarioSpec[]>("/api/simulation/scenarios"),
    staleTime: 20_000,
    refetchInterval: 30_000,
  });
}

/** Run the deterministic simulation for a scenario + levers (instant). */
export function useSimulation(scenarioId: string, levers: ResponseLevers) {
  return useQuery<SimulationResult>({
    queryKey: ["simulation", scenarioId, levers],
    queryFn: () =>
      apiPost<SimulationResult>("/api/simulation/run", {
        scenario_id: scenarioId,
        levers,
    }),
    staleTime: 5_000,
    refetchInterval: scenarioId === "auto_live" ? 30_000 : false,
  });
}

/** Knowledge graph (entity relationships + live event links). */
export function useGraph() {
  return useQuery<GraphData>({
    queryKey: ["graph"],
    queryFn: () => apiGet<GraphData>("/api/graph"),
    refetchInterval: 120_000,
  });
}

/** Explore N-hop neighborhood of a given ontology entity. */
export function useOntologyExplore(entityId: string | null, depth: number = 2) {
  return useQuery<OntologyExploreResult>({
    queryKey: ["ontology-explore", entityId, depth],
    queryFn: () => apiGet<OntologyExploreResult>(`/api/ontology/explore/${encodeURIComponent(entityId!)}?depth=${depth}`),
    enabled: Boolean(entityId),
    staleTime: 30_000,
  });
}

/** Trace impact propagation from a specific disruption event. */
export function useOntologyImpact(eventId: string | null) {
  return useQuery<OntologyImpactResult>({
    queryKey: ["ontology-impact", eventId],
    queryFn: () => apiGet<OntologyImpactResult>(`/api/ontology/impact/${encodeURIComponent(eventId!)}`),
    enabled: Boolean(eventId),
    staleTime: 30_000,
  });
}

/** Search ontology entities by keyword. */
export function useOntologySearch(query: string) {
  return useQuery<OntologySearchResult>({
    queryKey: ["ontology-search", query],
    queryFn: () => apiGet<OntologySearchResult>(`/api/ontology/search?q=${encodeURIComponent(query)}`),
    enabled: query.trim().length > 0,
    staleTime: 10_000,
  });
}

/** Get schema statistics for the ontology. */
export function useOntologyStats() {
  return useQuery<OntologyStats>({
    queryKey: ["ontology-stats"],
    queryFn: () => apiGet<OntologyStats>("/api/ontology/stats"),
    refetchInterval: 60_000,
  });
}

/** Versioned ontology classes, relationship rules and provenance contract. */
export function useOntologySchema() {
  return useQuery<OntologySchema>({
    queryKey: ["ontology-schema"],
    queryFn: () => apiGet<OntologySchema>("/api/ontology/schema"),
    staleTime: Infinity,
  });
}

/** NASA GIBS satellite imagery tile-layer config (keyless). */
export function useSatelliteLayers() {
  return useQuery<SatelliteLayersResponse>({
    queryKey: ["satellite-layers"],
    queryFn: () => apiGet<SatelliteLayersResponse>("/api/satellite/layers"),
    staleTime: 3_600_000, // imagery date changes daily
  });
}

/** Quantified ontology cascade: block a node by a fraction, see downstream impact. */
export function useCascade(nodeId: string | null, blockFraction: number, enabled: boolean) {
  return useQuery<CascadeResult>({
    queryKey: ["cascade", nodeId, blockFraction],
    queryFn: () =>
      apiGet<CascadeResult>(
        `/api/ontology/cascade/${encodeURIComponent(nodeId!)}?block_fraction=${blockFraction}`,
      ),
    enabled: enabled && Boolean(nodeId),
    staleTime: 10_000,
  });
}

export function useSourceStatus() {
  return useQuery<{ schema_version: string; sources: SourceStatus[] }>({
    queryKey: ["source-status"],
    queryFn: () => apiGet("/api/sources/status"),
    refetchInterval: 60_000,
  });
}

/** One fused state shared by map, scenario engine, optimizer and council. */
export function useOperationalSnapshot() {
  return useQuery<OperationalSnapshot>({
    queryKey: ["operational-snapshot"],
    queryFn: () => apiGet<OperationalSnapshot>("/api/operations/snapshot"),
    refetchInterval: 15_000,
    staleTime: 10_000,
  });
}

/** Convene the six-agent council + decision engine. */
export function useCouncil(scenarioId: string, levers: ResponseLevers) {
  return useQuery<CouncilResult>({
    queryKey: ["council", scenarioId, levers],
    queryFn: () =>
      apiPost<CouncilResult>("/api/council/convene", {
        scenario_id: scenarioId,
        levers,
      }),
    staleTime: 10_000,
  });
}

/** Most recent persistent mission for the current scenario. */
export function useLatestMission(scenarioId: string) {
  return useQuery<MissionRecord | null>({
    queryKey: ["mission-latest", scenarioId],
    queryFn: async () => {
      try {
        return await apiGet<MissionRecord>(`/api/missions/latest?scenario_id=${scenarioId}`);
      } catch (error) {
        if (error instanceof ApiError && error.status === 404) {
          return null;
        }
        throw error;
      }
    },
    staleTime: 10_000,
    retry: false,
  });
}


export function useMissionRecord(missionId: string | null) {
  return useQuery<MissionRecord>({
    queryKey: ["mission", missionId],
    queryFn: () => apiGet<MissionRecord>(`/api/missions/${encodeURIComponent(missionId!)}`),
    enabled: Boolean(missionId),
    refetchInterval: 5_000,
  });
}
