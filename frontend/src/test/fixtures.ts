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

// Synthetic GSI data for UI tests only (not a real match).
export const GSI_SNAPSHOT = {
  provider_name: "Dota 2", provider_version: 47, has_map: true, map_name: "start", match_id: "9000000001", game_mode: null,
  custom_game_name: null, game_state: "DOTA_GAMERULES_STATE_GAME_IN_PROGRESS", game_state_label: "Игра идёт", game_time: 754,
  clock_time: 664, daytime: true, paused: false, win_team: null, radiant_score: 7, dire_score: 4, has_player: true,
  activity: "playing", team: "radiant", kills: 3, deaths: 1, assists: 5, last_hits: 61, denies: 7, gold: 1325, gpm: 412, xpm: 455,
  has_hero: true, hero_internal: "npc_dota_hero_antimage", hero_name: "Anti-Mage", hero_level: 11, alive: true, respawn_seconds: 0,
  health: 812, max_health: 1210, mana: null, max_mana: null,
  abilities: [{ slot: "ability1", name: "antimage_blink", level: 4, can_cast: true, passive: false, active: true, cooldown: 3, ultimate: false }],
  items: [{ slot: "slot0", name: "item_power_treads", charges: null, cooldown: 0, can_cast: true }], problems: [],
};
export const gsiState = (over: Record<string, unknown> = {}) => ({
  status: "live", freshness: "fresh", dota_running: true, last_update: Date.now() / 1000, age_seconds: 0.4, stale_after_seconds: 40,
  updates: 42, format_errors: 0, rejected: 0, in_match: true, snapshot: GSI_SNAPSHOT, match: null, ...over,
});
export const GSI_WAITING = { status: "waiting", freshness: "never", dota_running: false, last_update: null, age_seconds: null,
  stale_after_seconds: 40, updates: 0, format_errors: 0, rejected: 0, in_match: false, snapshot: null, match: null };
export const GSI_CONFIG = {
  cfg_name: "gamestate_integration_launcher.cfg", error: null, available: true, installed: false, backups: [
    { name: "20261105-120000-before_install.cfg", size: 120, created: "2026-11-05T12:00:00", managed: false }],
  launch_option: { checked: true, found: false, accounts: 1 },
  file: "D:\\SteamLibrary\\steamapps\\common\\dota 2 beta\\game\\dota\\cfg\\gamestate_integration\\gamestate_integration_launcher.cfg",
  dir_exists: true, exists: false, up_to_date: false, managed: false, valid: null, uri: null, token_matches: null,
  expected_uri: "http://127.0.0.1:8000/gsi", other_configs: ["gamestate_integration_obs.cfg"],
  plan: { action: "create", plan_id: "a".repeat(128), creates_directory: false, backup_before_change: false, current_content: null,
    new_content: '// Managed by Launcher\n"Launcher GSI" { "uri" "http://127.0.0.1:8000/gsi" "auth" { "token" "••••••••abcd" } }' },
};

export function routes(extra: [RegExp, unknown][] = []): [RegExp, unknown][] {
  return [
    ...extra,
    [/GET \/api\/health/, HEALTH], [/GET \/api\/system\/process/, PROCESS], [/GET \/api\/settings/, SETTINGS],
    [/GET \/api\/logs\/components/, ["app", "db"]], [/GET \/api\/logs/, EMPTY_PAGE],
    [/GET \/api\/monitoring\/current/, METRICS], [/GET \/api\/monitoring\/recent/, { points: [] }],
    [/GET \/api\/monitoring\/history/, { points: [] }], [/GET \/api\/environment/, ENV],
    [/GET \/api\/events/, EMPTY_PAGE], [/GET \/api\/gsi\/state/, GSI_WAITING], [/GET \/api\/gsi\/config/, GSI_CONFIG],
    [/GET \/api\/gsi\/matches/, EMPTY_PAGE], [/GET \/api\/slots\/\d+\/history/, EMPTY_PAGE], [/GET \/api\/slots/, SLOTS],
  ];
}
