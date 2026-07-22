"use client";

import { useBaselineNesi } from "@/hooks/useNetwork";

/** Invisible mounter: pulls the real baseline NESI into the global store. */
export function NesiSync() {
  useBaselineNesi();
  return null;
}
