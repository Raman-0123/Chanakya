"use client";

import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { apiGet, type NesiResult } from "@/lib/api";
import { useSecurityIndex } from "@/stores/useSecurityIndex";

/** Baseline NESI from the domain core; syncs the global gauge store. */
export function useBaselineNesi() {
  const set = useSecurityIndex((s) => s.set);
  const query = useQuery<NesiResult>({
    queryKey: ["nesi-baseline"],
    queryFn: () => apiGet<NesiResult>("/api/network/nesi"),
    staleTime: 60_000,
  });

  useEffect(() => {
    if (query.data) set(query.data.value);
  }, [query.data, set]);

  return query;
}
