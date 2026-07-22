import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** Merge conditional + Tailwind classes with conflict resolution. */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

/** Compact number formatting for operational readouts (1.2M, 940K, 88%). */
export function fmt(value: number, opts: Intl.NumberFormatOptions = {}): string {
  return new Intl.NumberFormat("en-IN", opts).format(value);
}

export function fmtCompact(value: number): string {
  return new Intl.NumberFormat("en-US", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(value);
}

export function fmtUsd(value: number): string {
  return `$${value.toFixed(2)}`;
}

export function clamp(v: number, min = 0, max = 100): number {
  return Math.min(max, Math.max(min, v));
}
