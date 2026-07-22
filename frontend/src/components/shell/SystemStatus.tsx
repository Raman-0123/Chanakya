"use client";

import { useSystemHealth } from "@/hooks/useSystemHealth";
import { cn } from "@/lib/utils";
import { useRealtime } from "@/stores/useRealtime";

/** Compact live indicator of backend + datastore + LLM availability. */
export function SystemStatus() {
  const { data, isError, isLoading } = useSystemHealth();
  const realtime = useRealtime((state) => state.status);

  const online = !isError && !isLoading && data?.status === "ok";
  const llmVerified = data?.llm.runtime_verified ?? false;
  const llmConfigured = data?.llm.configured ?? data?.llm.available ?? false;
  const stores = data?.datastores ?? {};
  const storesUp = Object.values(stores).filter(Boolean).length;
  const storesTotal = Object.keys(stores).length;

  return (
    <div className="flex items-center gap-4">
      <Indicator
        on={online}
        label="Core"
        detail={isLoading ? "linking" : online ? "online" : "offline"}
      />
      <Indicator
        on={realtime === "live"}
        label="Socket"
        detail={realtime === "live" ? "connected" : realtime}
      />
      <Indicator
        on={llmVerified}
        label="LLM"
        detail={
          llmVerified
            ? `${data?.llm.verified_providers?.[0] ?? "provider"} verified`
            : llmConfigured
              ? `${data?.llm.providers.length ?? 0} configured · unverified`
              : "no key"
        }
      />
      <Indicator
        on={storesUp > 0}
        label="Stores"
        detail={storesTotal ? `${storesUp}/${storesTotal}` : "—"}
      />
    </div>
  );
}

function Indicator({
  on,
  label,
  detail,
}: {
  on: boolean;
  label: string;
  detail: string;
}) {
  return (
    <div className="flex items-center gap-1.5">
      <span
        className={cn(
          "h-1.5 w-1.5 rounded-full",
          on ? "bg-nominal animate-flicker" : "bg-critical",
        )}
        style={{ boxShadow: on ? "0 0 8px #10b981" : "0 0 8px #ef4444" }}
      />
      <span className="label-terminal !text-ink-muted">{label}</span>
      <span className="readout text-micro text-ink-dim">{detail}</span>
    </div>
  );
}
