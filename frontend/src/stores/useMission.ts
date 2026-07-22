"use client";

import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import type { ResponseLevers } from "@/lib/types";

const DEFAULT_LEVERS: ResponseLevers = {
  spr_release_pct: 45,
  enable_reroute: true,
  enable_spot: true,
};

interface MissionState {
  scenarioId: string;
  levers: ResponseLevers;
  selectedStrategyId: string | null;
  activated: boolean; // mission execution launched
  setScenario: (id: string) => void;
  setLevers: (patch: Partial<ResponseLevers>) => void;
  selectStrategy: (id: string) => void;
  activateMission: () => void;
  reset: () => void;
}

/**
 * The operational thread shared across rooms: the currently-selected crisis
 * scenario and response levers drive the Simulation Lab, Council, Decision
 * Center, and Mission Execution as one continuous pipeline.
 */
export const useMission = create<MissionState>()(
  persist(
    (set) => ({
      scenarioId: "hormuz_closure",
      levers: DEFAULT_LEVERS,
      selectedStrategyId: null,
      activated: false,
      setScenario: (id) =>
        set({ scenarioId: id, selectedStrategyId: null, activated: false }),
      setLevers: (patch) =>
        set((s) => ({ levers: { ...s.levers, ...patch }, activated: false })),
      selectStrategy: (id) => set({ selectedStrategyId: id, activated: false }),
      activateMission: () => set({ activated: true }),
      reset: () =>
        set({
          scenarioId: "hormuz_closure",
          levers: DEFAULT_LEVERS,
          selectedStrategyId: null,
          activated: false,
        }),
    }),
    {
      name: "chanakya-mission-state",
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        scenarioId: state.scenarioId,
        levers: state.levers,
        selectedStrategyId: state.selectedStrategyId,
        activated: state.activated,
      }),
    },
  ),
);
