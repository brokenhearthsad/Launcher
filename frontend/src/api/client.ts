// Thin typed HTTP client for the backend REST API.
import type {
  EnvironmentState, EventItem, Health, HistoryPoint, LogEntry, Metrics, Page, ProcessUsage, RuntimeSettings, SeriesPoint,
  SettingsResponse, Slot,
} from "./types";

export const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? "";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: unknown,
  ) {
    super(message);
  }
}

type Query = Record<string, string | number | boolean | null | undefined | (string | number)[]>;

export function buildQuery(q?: Query): string {
  if (!q) return "";
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(q)) {
    if (v === undefined || v === null || v === "") continue;
    if (Array.isArray(v)) v.forEach((x) => p.append(k, String(x)));
    else p.append(k, String(v));
  }
  const s = p.toString();
  return s ? `?${s}` : "";
}

async function request<T>(method: string, path: string, body?: unknown, query?: Query,
  extraHeaders?: Record<string, string>): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}${buildQuery(query)}`, {
      method,
      headers: { ...(body !== undefined ? { "Content-Type": "application/json" } : {}), ...extraHeaders },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch (e) {
    throw new ApiError(0, "network_error", "Launcher недоступен. Запущен ли он (start.bat)?", e);
  }
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  let data: unknown = undefined;
  try {
    data = text ? JSON.parse(text) : undefined;
  } catch {
    data = text;
  }
  if (!res.ok) {
    const err = (data as { error?: { code?: string; message?: string; details?: unknown } })?.error;
    throw new ApiError(res.status, err?.code ?? "http_error", err?.message ?? `HTTP ${res.status}`, err?.details);
  }
  return data as T;
}

export const api = {
  health: () => request<Health>("GET", "/api/health"),
  process: () => request<ProcessUsage>("GET", "/api/system/process"),
  shutdown: () => request<{ status: string }>("POST", "/api/system/shutdown", undefined, undefined, { "X-Launcher-Request": "1" }),

  metrics: () => request<Metrics>("GET", "/api/monitoring/current"),
  recent: (seconds = 900) => request<{ points: SeriesPoint[] }>("GET", "/api/monitoring/recent", undefined, { seconds }),
  history: (hours = 24) => request<{ points: HistoryPoint[] }>("GET", "/api/monitoring/history", undefined, { hours }),

  environment: () => request<EnvironmentState>("GET", "/api/environment"),
  refreshEnvironment: () => request<EnvironmentState>("POST", "/api/environment/refresh"),
  events: (q?: Query) => request<Page<EventItem>>("GET", "/api/events", undefined, q),

  slots: () => request<Slot[]>("GET", "/api/slots"),
  updateSlot: (id: number, data: Partial<Pick<Slot, "name" | "note" | "binding">>) => request<Slot>("PUT", `/api/slots/${id}`, data),
  slotHistory: (id: number, q?: Query) => request<Page<EventItem>>("GET", `/api/slots/${id}/history`, undefined, q),

  logs: (q?: Query) => request<Page<LogEntry>>("GET", "/api/logs", undefined, q),
  logComponents: () => request<string[]>("GET", "/api/logs/components"),

  settings: () => request<SettingsResponse>("GET", "/api/settings"),
  updateSettings: (data: Partial<RuntimeSettings>) => request<RuntimeSettings>("PUT", "/api/settings", data),
  vacuum: () => request<{ size_before: number; size_after: number }>("POST", "/api/settings/database/vacuum"),
  purgeLogs: (older_than_days: number) =>
    request<{ deleted: number }>("POST", "/api/settings/database/purge-logs", { older_than_days }),
};

export function wsUrl(): string {
  const base = API_BASE || window.location.origin;
  return base.replace(/^http/, "ws") + "/ws/events";
}
