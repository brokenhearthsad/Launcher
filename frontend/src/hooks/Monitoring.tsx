// Shared live data: machine metrics + Steam/Dota environment (one WebSocket for the whole app).
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api, ApiError } from "../api/client";
import type { EnvironmentState, Metrics, SeriesPoint } from "../api/types";
import { useLiveEvent } from "./LiveEvents";

const MAX_POINTS = 450; // ~15 minutes at the 2 s interval

interface MonitoringValue {
  metrics: Metrics | null;
  series: SeriesPoint[];
  environment: EnvironmentState | null;
  error: ApiError | null;
  setEnvironment: (e: EnvironmentState) => void;
}

const Ctx = createContext<MonitoringValue>({ metrics: null, series: [], environment: null, error: null, setEnvironment: () => {} });

export function toPoint(m: Metrics): SeriesPoint {
  const g = m.gpu.available ? m.gpu : null;
  return {
    t: m.ts, cpu: m.cpu.percent, ram_pct: m.memory.percent, gpu_util: g?.util_percent ?? null, gpu_mem_mb: g?.mem_used_mb ?? null,
    gpu_temp: g?.temp_c ?? null, cpu_temp: m.cpu_temp.available ? m.cpu_temp.temp_c ?? null : null,
    net_rx_kbps: m.network.rx_kbps, net_tx_kbps: m.network.tx_kbps, disk_read_kbps: m.disk_io.read_kbps, disk_write_kbps: m.disk_io.write_kbps,
  };
}

export function MonitoringProvider({ children }: { children: ReactNode }) {
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [series, setSeries] = useState<SeriesPoint[]>([]);
  const [environment, setEnvironment] = useState<EnvironmentState | null>(null);
  const [error, setError] = useState<ApiError | null>(null);

  useEffect(() => {
    let alive = true;
    api.metrics().then((m) => alive && setMetrics(m)).catch((e) => alive && setError(e as ApiError));
    api.recent().then((r) => alive && setSeries(r.points.slice(-MAX_POINTS))).catch(() => {});
    api.environment().then((e) => alive && setEnvironment(e)).catch((e) => alive && setError(e as ApiError));
    return () => { alive = false; };
  }, []);

  useLiveEvent(["metrics_updated"], (m) => {
    const data = m.data as Metrics;
    setMetrics((prev) => ({ ...data, interval_seconds: prev?.interval_seconds, mode: "active" }));
    setSeries((prev) => [...prev, toPoint(data)].slice(-MAX_POINTS));
    setError(null);
  });
  useLiveEvent(["environment_updated"], (m) => setEnvironment(m.data as EnvironmentState));

  return <Ctx.Provider value={{ metrics, series, environment, error, setEnvironment }}>{children}</Ctx.Provider>;
}

export function useMonitoring(): MonitoringValue {
  return useContext(Ctx);
}
