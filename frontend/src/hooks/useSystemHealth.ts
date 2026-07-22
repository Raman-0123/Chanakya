"use client";

import { useQuery } from "@tanstack/react-query";
import { apiGet, type SystemHealth } from "@/lib/api";

/** Polls backend capability/health so the shell can show what is live. */
export function useSystemHealth() {
  return useQuery<SystemHealth>({
    queryKey: ["system-health"],
    queryFn: () => apiGet<SystemHealth>("/api/health"),
    refetchInterval: 15_000,
    retry: 1,
  });
}
