export const HEALTH = { status: "ok", version: "2.0.0-phase1", database: "ok", websocket_clients: 1, uptime_seconds: 125, frontend_built: true };
export const PROCESS = { pid: 4242, rss_mb: 62.5, private_mb: 55.1, cpu_percent: 0.12, threads: 6, child_processes: 0, python: "3.12.7", uptime_seconds: 125 };
export const SETTINGS = {
  runtime: { ws_publish_hz: 4, ui_refresh_seconds: 5, log_level: "INFO", db_log_level: "INFO" },
  backend: { version: "2.0.0-phase1", host: "127.0.0.1", port: 8000, api_rate_limit_per_minute: 600, log_dir: "logs", frontend_dist: "dist", lower_own_priority: false },
  database: { url: "sqlite://", dialect: "sqlite", path: "C:/Launcher/backend/data/match_lab.db", size_bytes: 4096, backup_dir: "backups", last_backup: "backups/match_lab-pre-0002.db" },
};
export const EMPTY_PAGE = { items: [], total: 0, page: 1, page_size: 50 };

export function routes(extra: [RegExp, unknown][] = []): [RegExp, unknown][] {
  return [
    ...extra,
    [/GET \/api\/health/, HEALTH], [/GET \/api\/system\/process/, PROCESS], [/GET \/api\/settings/, SETTINGS],
    [/GET \/api\/logs\/components/, ["app", "db"]], [/GET \/api\/logs/, EMPTY_PAGE],
  ];
}
