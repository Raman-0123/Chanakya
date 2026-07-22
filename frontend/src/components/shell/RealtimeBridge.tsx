"use client";

import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { WS_BASE } from "@/lib/api";
import { useRealtime } from "@/stores/useRealtime";

/** WebSocket-first cache invalidation with bounded reconnect and REST recovery. */
export function RealtimeBridge() {
  const queryClient = useQueryClient();
  const setRealtime = useRealtime((state) => state.setRealtime);

  useEffect(() => {
    let socket: WebSocket | null = null;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;
    let heartbeatTimer: ReturnType<typeof setInterval> | null = null;
    let stopped = false;
    let attempt = 0;
    const seen = new Set<string>();
    let cursor = window.localStorage.getItem("chanakya:event-cursor");

    const invalidateOperationalCaches = () => {
      void queryClient.invalidateQueries({ queryKey: ["intel-feed"] });
      void queryClient.invalidateQueries({ queryKey: ["graph"] });
      void queryClient.invalidateQueries({ queryKey: ["source-status"] });
      void queryClient.invalidateQueries({ queryKey: ["system-health"] });
      void queryClient.invalidateQueries({ queryKey: ["operational-snapshot"] });
    };

    const connect = () => {
      if (stopped) return;
      setRealtime({ status: attempt ? "reconnecting" : "connecting", reconnectAttempt: attempt });
      socket = new WebSocket(`${WS_BASE}/api/ws/intelligence`);

      socket.onopen = () => {
        attempt = 0;
        setRealtime({ status: "live", reconnectAttempt: 0 });
        invalidateOperationalCaches();
        socket?.send(JSON.stringify({ type: "ping", cursor }));
        heartbeatTimer = setInterval(() => {
          if (socket?.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({ type: "ping", cursor }));
          }
        }, 20_000);
      };

      socket.onmessage = (message) => {
        try {
          const payload = JSON.parse(message.data) as { type: string; cursor?: string };
          if (payload.cursor && seen.has(payload.cursor)) return;
          if (payload.cursor) {
            seen.add(payload.cursor);
            if (seen.size > 500) seen.delete(seen.values().next().value as string);
            cursor = payload.cursor;
            window.localStorage.setItem("chanakya:event-cursor", payload.cursor);
          }
          setRealtime({ status: "live", cursor,
            lastMessageAt: new Date().toISOString() });
          if (payload.type === "intelligence.event" || payload.type === "source.status" ||
              payload.type === "operations.snapshot") {
            invalidateOperationalCaches();
            if (payload.type === "operations.snapshot") {
              void queryClient.invalidateQueries({ queryKey: ["simulation", "auto_live"] });
              void queryClient.invalidateQueries({ queryKey: ["scenarios"] });
            }
          }
          if (payload.type === "operations.recommendation") {
            void queryClient.invalidateQueries({ queryKey: ["mission-latest"] });
            void queryClient.invalidateQueries({ queryKey: ["mission"] });
          }
        } catch {
          setRealtime({ status: "degraded" });
        }
      };

      socket.onclose = () => {
        if (heartbeatTimer) clearInterval(heartbeatTimer);
        if (stopped) return;
        attempt += 1;
        const delay = Math.min(30_000, 1_000 * 2 ** Math.min(attempt, 5));
        setRealtime({ status: attempt > 5 ? "degraded" : "reconnecting",
          reconnectAttempt: attempt });
        retryTimer = setTimeout(connect, delay + Math.random() * 500);
      };
      socket.onerror = () => socket?.close();
    };

    connect();
    return () => {
      stopped = true;
      if (retryTimer) clearTimeout(retryTimer);
      if (heartbeatTimer) clearInterval(heartbeatTimer);
      socket?.close();
      setRealtime({ status: "offline" });
    };
  }, [queryClient, setRealtime]);

  return null;
}
