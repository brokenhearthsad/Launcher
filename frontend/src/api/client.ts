// Thin typed HTTP client for the backend REST API.
import type {
  Health,
  HistoryItem,
  LogEntry,
  MatchEventRow,
  MatchSession,
  Meta,
  Overview,
  Page,
  Player,
  PlayerAggregate,
  PlayerCreate,
  PlayerUpdate,
  RuntimeSettings,
  SessionAggregate,
  SessionCreate,
  SessionDetail,
  SessionStatistics,
  SettingsResponse,
  TeamAggregate,
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

async function request<T>(method: string, path: string, body?: unknown, query?: Query): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}${buildQuery(query)}`, {
      method,
      headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch (e) {
    throw new ApiError(0, "network_error", "Backend is unreachable. Is it running on 127.0.0.1:8000?", e);
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
  meta: () => request<Meta>("GET", "/api/meta"),

  players: (team?: string) => request<Player[]>("GET", "/api/players", undefined, { team }),
  createPlayer: (data: PlayerCreate) => request<Player>("POST", "/api/players", data),
  updatePlayer: (id: number, data: PlayerUpdate) => request<Player>("PUT", `/api/players/${id}`, data),
  deletePlayer: (id: number) => request<void>("DELETE", `/api/players/${id}`),

  sessions: (q?: { page?: number; page_size?: number; status?: string }) =>
    request<Page<MatchSession>>("GET", "/api/sessions", undefined, q),
  createSession: (data: SessionCreate) => request<SessionDetail>("POST", "/api/sessions", data),
  session: (id: number) => request<SessionDetail>("GET", `/api/sessions/${id}`),
  startSession: (id: number) => request<MatchSession>("POST", `/api/sessions/${id}/start`),
  pauseSession: (id: number) => request<MatchSession>("POST", `/api/sessions/${id}/pause`),
  resumeSession: (id: number) => request<MatchSession>("POST", `/api/sessions/${id}/resume`),
  stopSession: (id: number) => request<MatchSession>("POST", `/api/sessions/${id}/stop`),
  setSpeed: (id: number, speed: number) => request<MatchSession>("POST", `/api/sessions/${id}/speed`, { speed }),
  statistics: (id: number) => request<SessionStatistics>("GET", `/api/sessions/${id}/statistics`),
  events: (id: number, q?: { page?: number; page_size?: number; event_type?: string }) =>
    request<Page<MatchEventRow>>("GET", `/api/sessions/${id}/events`, undefined, q),

  history: (q?: { page?: number; page_size?: number; winner?: string; scenario?: string; status?: string }) =>
    request<Page<HistoryItem>>("GET", "/api/matches/history", undefined, q),

  overview: () => request<Overview>("GET", "/api/analytics/overview"),
  analyticsPlayers: (q?: Query) => request<PlayerAggregate[]>("GET", "/api/analytics/players", undefined, q),
  analyticsTeams: (q?: Query) => request<TeamAggregate[]>("GET", "/api/analytics/teams", undefined, q),
  analyticsSessions: (q?: Query) => request<SessionAggregate[]>("GET", "/api/analytics/sessions", undefined, q),
  exportUrl: (format: "csv" | "json", q?: Query) =>
    `${API_BASE}/api/analytics/export${buildQuery({ ...q, format })}`,

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
