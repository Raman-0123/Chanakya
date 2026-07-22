/**
 * Thin, typed API layer over the FastAPI backend. Every network call in the
 * app goes through `apiGet` / `apiPost` so base URL, errors, and JSON handling
 * live in exactly one place.
 */

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8010";
export const WS_BASE =
  process.env.NEXT_PUBLIC_WS_BASE_URL ?? "ws://localhost:8010";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    throw new ApiError(res.status, `${init?.method ?? "GET"} ${path} → ${res.status}`);
  }
  return (await res.json()) as T;
}

export function apiGet<T>(path: string): Promise<T> {
  return request<T>(path);
}

export function apiPost<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    body: body ? JSON.stringify(body) : undefined,
  });
}

export function apiPostOperator<T>(path: string, pin: string, body?: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Operator-Pin": pin },
    body: body ? JSON.stringify(body) : undefined,
  });
}

// ---- typed responses ----
export interface SystemHealth {
  status: string;
  version: string;
  environment: string;
  datastores: Record<string, boolean>;
  llm: {
    available: boolean;
    configured?: boolean;
    runtime_verified?: boolean;
    providers: string[];
    verified_providers?: string[];
    runtime?: Record<string, {
      configured: boolean;
      verified: boolean;
      successes: number;
      failures: number;
      last_success_at: string | null;
      last_failure_at: string | null;
      last_error: string | null;
      last_model: string | null;
      last_latency_ms: number | null;
    }>;
  };
  data_sources: Record<string, boolean>;
  process_role?: string;
  websocket_clients?: number;
}

export interface NesiComponent {
  key: string;
  label: string;
  score: number;
  weight: number;
  detail: string;
}

export interface NesiResult {
  value: number;
  band: string;
  components: NesiComponent[];
}
