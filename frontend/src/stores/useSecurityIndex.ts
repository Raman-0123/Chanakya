"use client";

import { create } from "zustand";

interface SecurityIndexState {
  /** 0–100 National Energy Security Index (higher = more secure). */
  value: number;
  /** 24h trend delta. */
  trend: number;
  history: number[];
  set: (value: number, trend?: number) => void;
}

/**
 * Global NESI store. Seeded to a realistic baseline ("Elevated exposure")
 * reflecting India's structural import dependence; Phase 2's scenario engine
 * recomputes and drives this in real time.
 */
export const useSecurityIndex = create<SecurityIndexState>((set) => ({
  value: 61,
  trend: -2.4,
  history: [68, 66, 67, 64, 63, 61],
  set: (value, trend) =>
    set((s) => ({
      value,
      trend: trend ?? value - s.value,
      history: [...s.history.slice(-23), value],
    })),
}));
