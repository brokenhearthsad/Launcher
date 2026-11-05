export const HEALTH = { status: "ok", version: "2.0.0-phase1", database: "ok", websocket_clients: 1, uptime_seconds: 125, frontend_built: true };
export const PROCESS = { pid: 4242, rss_mb: 62.5, private_mb: 55.1, cpu_percent: 0.12, threads: 6, child_processes: 0, python: "3.12.7", uptime_seconds: 125 };
export const SETTINGS = {
  runtime: { ws_publish_hz: 4, ui_refresh_seconds: 5, log_level: "INFO", db_log_level: "INFO", monitor_active_interval: 2,
    monitor_idle_interval: 15, process_scan_interval: 5, lhm_enabled: false, lhm_url: "http://127.0.0.1:8085/data.json", metrics_retention_days: 14 },
  backend: { version: "2.0.0-phase1", host: "127.0.0.1", port: 8000, api_rate_limit_per_minute: 600, log_dir: "logs", frontend_dist: "dist", lower_own_priority: false },
  database: { url: "sqlite://", dialect: "sqlite", path: "C:/Launcher/backend/data/match_lab.db", size_bytes: 4096, backup_dir: "backups", last_backup: "backups/match_lab-pre-0002.db" },
};
export const EMPTY_PAGE = { items: [], total: 0, page: 1, page_size: 50 };

export const METRICS = {
  ts: 1_762_340_000, interval_seconds: 2, mode: "active",
  cpu: { percent: 12.5, per_core: [10, 20, 5, 15], freq_mhz: 3700, logical_cores: 12, physical_cores: 6 },
  memory: { total_mb: 32768, used_mb: 14336, available_mb: 18432, percent: 43.8 },
  disks: [{ mount: "C:\\", available: true, total_gb: 512, used_gb: 300, free_gb: 212, percent: 58.6 }, { mount: "D:\\", available: false }],
  disk_io: { read_kbps: 120, write_kbps: null }, network: { rx_kbps: 2048, tx_kbps: 15 },
  gpu: { available: false, source: null, reason: "NVML: driver not loaded; nvidia-smi not found" },
  cpu_temp: { available: false, reason: "LibreHardwareMonitor integration is disabled" },
};
export const ENV = {
  steam: { installed: true, path: "C:\\Program Files (x86)\\Steam", source: "registry", libraries: ["C:\\Steam", "D:\\SteamLibrary"],
    error: null, signed_in: true, process: { running: true, pid: 4321, started_at: 1_762_300_000, uptime_seconds: 3725, rss_mb: 210.5, cpu_percent: 0.4 } },
  dota: { installed: true, path: "D:\\SteamLibrary\\steamapps\\common\\dota 2 beta", library: "D:\\SteamLibrary", exe_exists: true,
    buildid: "20512345", state: ["fully_installed"], last_updated: "2026-11-01T10:00:00+00:00", size_gb: 38.9, error: null,
    process: { running: false } },
  registry_available: true, platform: "win32", checked_at: 1_762_340_000,
};
export const SLOTS = Array.from({ length: 10 }, (_, i) => ({
  id: i + 1, name: `Slot ${i + 1}`, note: i === 0 ? "основной" : "", team: i < 5 ? "radiant" : "dire",
  binding: i === 0 ? "local_client" : "none", status: i === 0 ? "steam_running" : "unbound",
  status_label: i === 0 ? "Steam запущен" : "Не привязан", updated_at: "2026-11-05T10:00:00Z",
  ...(i === 0 ? { observed: { steam_pid: 4321, dota_pid: null, signed_in: true } } : {}),
}));

export function routes(extra: [RegExp, unknown][] = []): [RegExp, unknown][] {
  return [
    ...extra,
    [/GET \/api\/health/, HEALTH], [/GET \/api\/system\/process/, PROCESS], [/GET \/api\/settings/, SETTINGS],
    [/GET \/api\/logs\/components/, ["app", "db"]], [/GET \/api\/logs/, EMPTY_PAGE],
    [/GET \/api\/monitoring\/current/, METRICS], [/GET \/api\/monitoring\/recent/, { points: [] }],
    [/GET \/api\/monitoring\/history/, { points: [] }], [/GET \/api\/environment/, ENV],
    [/GET \/api\/events/, EMPTY_PAGE], [/GET \/api\/slots\/\d+\/history/, EMPTY_PAGE], [/GET \/api\/slots/, SLOTS],
  ];
}
