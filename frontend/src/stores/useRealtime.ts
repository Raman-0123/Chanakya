"use client";

import { create } from "zustand";

export type RealtimeStatus = "connecting" | "live" | "reconnecting" | "degraded" | "offline";

interface RealtimeState {
  status: RealtimeStatus;
  cursor: string | null;
  lastMessageAt: string | null;
  reconnectAttempt: number;
  setRealtime: (patch: Partial<Omit<RealtimeState, "setRealtime">>) => void;
}

export const useRealtime = create<RealtimeState>((set) => ({
  status: "connecting",
  cursor: null,
  lastMessageAt: null,
  reconnectAttempt: 0,
  setRealtime: (patch) => set(patch),
}));
