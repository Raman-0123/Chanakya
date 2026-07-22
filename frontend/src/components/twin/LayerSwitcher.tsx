"use client";

import { Check } from "lucide-react";
import { Panel, PanelHeader } from "@/components/primitives";
import type { SatelliteLayer } from "@/lib/types";
import { cn } from "@/lib/utils";

/** Base-imagery picker + overlay toggles for the NASA GIBS satellite layers. */
export function LayerSwitcher({
  baseOptions,
  overlayOptions,
  base,
  overlays,
  date,
  onBase,
  onToggleOverlay,
}: {
  baseOptions: SatelliteLayer[];
  overlayOptions: SatelliteLayer[];
  base: string;
  overlays: string[];
  date?: string;
  onBase: (id: string) => void;
  onToggleOverlay: (id: string) => void;
}) {
  return (
    <Panel raised className="pointer-events-auto">
      <PanelHeader
        eyebrow="NASA GIBS"
        title="Imagery"
        right={<span className="readout text-[10px] text-ink-dim">{date}</span>}
      />
      <div className="space-y-3 p-3">
        <div>
          <div className="label-terminal mb-1.5">Base layer</div>
          <div className="space-y-1">
            {baseOptions.map((l) => (
              <button
                key={l.id}
                onClick={() => onBase(l.id)}
                className={cn(
                  "flex w-full items-center justify-between gap-2 rounded border px-2.5 py-1.5 text-left text-[11px] transition-colors",
                  base === l.id
                    ? "border-signal/40 bg-signal/10 text-signal"
                    : "border-line bg-panel/60 text-ink-dim hover:text-ink",
                )}
              >
                <span className="truncate">{l.label}</span>
                {base === l.id && <Check size={13} className="shrink-0" />}
              </button>
            ))}
          </div>
        </div>
        {overlayOptions.length > 0 && (
          <div>
            <div className="label-terminal mb-1.5">Overlays</div>
            <div className="space-y-1">
              {overlayOptions.map((l) => {
                const on = overlays.includes(l.id);
                return (
                  <button
                    key={l.id}
                    onClick={() => onToggleOverlay(l.id)}
                    className={cn(
                      "flex w-full items-center justify-between gap-2 rounded border px-2.5 py-1.5 text-left text-[11px] transition-colors",
                      on
                        ? "border-energy/40 bg-energy/10 text-energy"
                        : "border-line bg-panel/60 text-ink-dim hover:text-ink",
                    )}
                  >
                    <span className="truncate">{l.label}</span>
                    <span
                      className={cn(
                        "grid h-3.5 w-3.5 shrink-0 place-items-center rounded-sm border",
                        on ? "border-energy bg-energy/20" : "border-line",
                      )}
                    >
                      {on && <Check size={10} />}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </Panel>
  );
}
