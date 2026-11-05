// Types mirroring the backend Pydantic schemas (backend/app/schemas).

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface WsMessage<T = unknown> {
  type: string;
  session_id: number | null;
  data: T;
  ts?: string;
}

export interface LogEntry {
  id: number;
  level: string;
  component: string;
  message: string;
  timestamp: string;
}

export interface RuntimeSettings {
  ws_publish_hz: number;
  ui_refresh_seconds: number;
  log_level: string;
  db_log_level: string;
}

export interface SettingsResponse {
  runtime: RuntimeSettings;
  backend: {
    version: string;
    host: string;
    port: number;
    api_rate_limit_per_minute: number;
    log_dir: string;
    frontend_dist: string;
    lower_own_priority: boolean;
  };
  database: {
    url: string;
    dialect: string;
    path?: string;
    size_bytes?: number;
    backup_dir: string;
    last_backup: string | null;
  };
}

export interface Health {
  status: string;
  version: string;
  database: string;
  websocket_clients: number;
  uptime_seconds: number;
  frontend_built: boolean;
}

export interface ProcessUsage {
  pid: number;
  rss_mb: number;
  private_mb: number;
  cpu_percent: number;
  threads: number;
  child_processes: number;
  python: string;
  uptime_seconds: number;
}
