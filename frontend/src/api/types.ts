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
  monitor_active_interval: number;
  monitor_idle_interval: number;
  process_scan_interval: number;
  lhm_enabled: boolean;
  lhm_url: string;
  metrics_retention_days: number;
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

// ----------------------------------------------------------------------------- Phase 2
export interface DiskInfo {
  mount: string;
  available: boolean;
  total_gb?: number;
  used_gb?: number;
  free_gb?: number;
  percent?: number;
}

export interface GpuInfo {
  available: boolean;
  source: string | null;
  reason?: string;
  name?: string;
  util_percent?: number | null;
  mem_used_mb?: number | null;
  mem_total_mb?: number | null;
  temp_c?: number | null;
  power_w?: number | null;
}

export interface Metrics {
  ts: number;
  cpu: { percent: number | null; per_core: number[]; freq_mhz: number | null; logical_cores: number; physical_cores: number };
  memory: { total_mb: number; used_mb: number; available_mb: number; percent: number };
  disks: DiskInfo[];
  disk_io: { read_kbps: number | null; write_kbps: number | null };
  network: { rx_kbps: number | null; tx_kbps: number | null };
  gpu: GpuInfo;
  cpu_temp: { available: boolean; temp_c?: number | null; sensor?: string | null; reason?: string };
  interval_seconds?: number;
  mode?: "active" | "idle";
}

export interface SeriesPoint {
  t: number;
  cpu: number | null;
  ram_pct: number | null;
  gpu_util: number | null;
  gpu_mem_mb: number | null;
  gpu_temp: number | null;
  cpu_temp: number | null;
  net_rx_kbps: number | null;
  net_tx_kbps: number | null;
  disk_read_kbps: number | null;
  disk_write_kbps: number | null;
}

export interface HistoryPoint {
  ts: string;
  samples: number;
  cpu_avg: number | null;
  cpu_max: number | null;
  ram_pct_avg: number | null;
  gpu_util_avg: number | null;
  gpu_temp_max: number | null;
  cpu_temp_max: number | null;
  net_rx_kbps_avg: number | null;
  net_tx_kbps_avg: number | null;
}

export interface ProcessState {
  running: boolean;
  pid?: number;
  started_at?: number;
  uptime_seconds?: number;
  rss_mb?: number | null;
  cpu_percent?: number | null;
}

export interface EnvironmentState {
  steam: { installed: boolean; path?: string | null; source?: string | null; libraries?: string[]; error?: string | null;
    signed_in: boolean | null; process: ProcessState };
  dota: { installed: boolean; path?: string | null; library?: string | null; exe_exists?: boolean; buildid?: string | null;
    state?: string[]; last_updated?: string | null; size_gb?: number | null; error?: string | null; process: ProcessState };
  registry_available: boolean;
  platform: string;
  checked_at: number | null;
}

export interface EventItem {
  id: number;
  ts: string;
  source?: string;
  type: string;
  severity?: string;
  slot_id?: number | null;
  message: string;
  data: Record<string, unknown>;
}

export type SlotStatus = "unbound" | "steam_not_installed" | "steam_stopped" | "steam_running" | "dota_running";

export interface Slot {
  id: number;
  name: string;
  note: string;
  team: "radiant" | "dire";
  binding: "none" | "local_client";
  status: SlotStatus;
  status_label: string;
  updated_at: string;
  observed?: { steam_pid: number | null; dota_pid: number | null; signed_in: boolean | null };
}

// ----------------------------------------------------------------------------- Phase 3 (GSI)
export interface GsiAbility { slot: string; name: string | null; level: number | null; can_cast: boolean | null; passive: boolean | null;
  active: boolean | null; cooldown: number | null; ultimate: boolean | null }
export interface GsiItem { slot: string; name: string | null; charges: number | null; cooldown: number | null; can_cast: boolean | null }

export interface GsiSnapshot {
  provider_name: string | null; provider_version: number | null;
  has_map: boolean; map_name: string | null; match_id: string | null; game_mode: string | null; custom_game_name: string | null;
  game_state: string | null; game_state_label: string | null; game_time: number | null; clock_time: number | null;
  daytime: boolean | null; paused: boolean | null; win_team: string | null; radiant_score: number | null; dire_score: number | null;
  has_player: boolean; activity: string | null; team: string | null; kills: number | null; deaths: number | null; assists: number | null;
  last_hits: number | null; denies: number | null; gold: number | null; gpm: number | null; xpm: number | null;
  has_hero: boolean; hero_internal: string | null; hero_name: string | null; hero_level: number | null; alive: boolean | null;
  respawn_seconds: number | null; health: number | null; max_health: number | null; mana: number | null; max_mana: number | null;
  abilities: GsiAbility[]; items: GsiItem[]; problems: string[];
}

export type GsiStatus = "waiting" | "live" | "delayed" | "stale";

export interface GsiState {
  status: GsiStatus; freshness: "never" | "fresh" | "delayed" | "stale"; dota_running: boolean | null;
  last_update: number | null; age_seconds: number | null; stale_after_seconds: number; updates: number; format_errors: number;
  rejected: number; in_match: boolean; snapshot: GsiSnapshot | null; match: Record<string, unknown> | null;
}

export interface GsiPlan { action: "create" | "update" | "none" | "replace_foreign"; plan_id: string; creates_directory: boolean;
  backup_before_change: boolean; current_content: string | null; new_content: string }

export interface GsiBackup { name: string; size: number; created: string; managed: boolean }

export interface GsiConfig {
  cfg_name: string; error: string | null; available: boolean; installed: boolean; backups: GsiBackup[];
  launch_option: { checked: boolean; found: boolean | null; accounts: number };
  file?: string; dir_exists?: boolean; exists?: boolean; up_to_date?: boolean; managed?: boolean; valid?: boolean | null;
  uri?: string | null; token_matches?: boolean | null; expected_uri?: string; other_configs?: string[]; plan: GsiPlan | null;
}

export interface GsiMatchRow {
  id: number; match_id: string | null; started_at: string; ended_at: string | null; map_name: string | null; hero: string | null;
  hero_name: string | null; team: string | null; result: string; win_team: string | null; game_time: number | null; max_level: number | null;
  radiant_score: number | null; dire_score: number | null; kills: number | null; deaths: number | null; assists: number | null;
  last_hits: number | null; denies: number | null; gpm: number | null; xpm: number | null; updates: number;
}
