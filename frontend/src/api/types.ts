// Types mirroring the backend Pydantic schemas (backend/app/schemas).

export type TeamName = "radiant" | "dire";
export type PlayerStatus = "offline" | "ready" | "running" | "paused" | "error" | "finished";
export type SessionStatus = "created" | "running" | "paused" | "finished" | "stopped" | "error";

export interface AIParams {
  bot_difficulty: string;
  aggression: number;
  farming_priority: number;
  team_coordination: number;
  risk_tolerance: number;
  objective_priority: number;
}

export interface Player extends AIParams {
  id: number;
  name: string;
  team: TeamName;
  slot: number;
  role: string;
  hero: string;
  status: PlayerStatus;
  created_at: string;
  updated_at: string;
}

export type PlayerUpdate = Partial<Omit<Player, "id" | "created_at" | "updated_at">>;
export type PlayerCreate = Omit<Player, "id" | "created_at" | "updated_at">;

export interface HeroOption {
  key: string;
  name: string;
  primary: string;
  roles: string[];
  attack_range: number;
  abilities: string[];
}

export interface EnvironmentInfo {
  name: string;
  title: string;
  description: string;
  available: boolean;
  is_simulation: boolean;
  capabilities: Record<string, boolean>;
  notes: string[];
}

export interface Meta {
  teams: TeamName[];
  roles: string[];
  difficulties: string[];
  player_statuses: PlayerStatus[];
  scenarios: string[];
  game_modes: string[];
  environments: EnvironmentInfo[];
  heroes: HeroOption[];
  items: { key: string; name: string; cost: number; category: string }[];
}

export interface Participant {
  id: number;
  player_id: number;
  team: TeamName;
  hero: string;
  role: string;
  ai_profile: Record<string, unknown>;
  player_name: string | null;
}

export interface MatchSession {
  id: number;
  name: string;
  status: SessionStatus;
  environment: string;
  map: string;
  scenario: string;
  game_mode: string;
  seed: number;
  speed: number;
  max_game_seconds: number;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  winner: TeamName | null;
  win_condition: string | null;
  duration_seconds: number | null;
  radiant_score: number;
  dire_score: number;
  events_count: number;
  error_message: string | null;
}

export interface SessionDetail extends MatchSession {
  participants: Participant[];
  live: LiveSnapshot | null;
}

export interface SessionCreate {
  name: string;
  environment: string;
  scenario: string;
  game_mode: string;
  seed?: number | null;
  speed?: number | null;
  max_game_seconds?: number | null;
  participants?: { player_id: number; team?: TeamName; hero?: string; role?: string }[];
}

export interface HeroState {
  player_id: number;
  uid: string;
  name: string;
  hero: string;
  hero_name: string;
  team: TeamName;
  role: string;
  lane: string;
  alive: boolean;
  respawn_in: number;
  pos: [number, number];
  hp: number;
  max_hp: number;
  mana: number;
  max_mana: number;
  level: number;
  xp: number;
  gold: number;
  gold_earned: number;
  net_worth: number;
  items: string[];
  kills: number;
  deaths: number;
  assists: number;
  last_hits: number;
  denies: number;
  hero_damage: number;
  tower_damage: number;
  healing: number;
  has_aegis: boolean;
  action: string;
}

export interface TowerState {
  uid: string;
  team: TeamName;
  tier: string;
  lane: string;
  alive: boolean;
  hp: number;
  max_hp: number;
  pos: [number, number];
}

export interface PlayerStatsRow {
  player_id: number;
  player_name: string | null;
  team: TeamName;
  hero: string;
  kills: number;
  deaths: number;
  assists: number;
  last_hits: number;
  denies: number;
  gpm: number;
  xpm: number;
  net_worth: number;
  hero_damage: number;
  tower_damage: number;
  healing: number;
  level: number;
  items: string[];
  kda: number;
  is_final?: boolean;
}

export interface LiveSnapshot {
  time: number;
  finished: boolean;
  winner: TeamName | null;
  win_condition: string | null;
  score: Record<TeamName, number>;
  net_worth: Record<TeamName, number>;
  heroes: HeroState[];
  towers: TowerState[];
  creeps: Record<string, { radiant: number; dire: number; front: [number, number] | null }>;
  roshan: { alive: boolean; hp: number; kills: number };
  wards: { team: TeamName; pos: [number, number] }[];
  directives?: Record<TeamName, { kind: string; lane: string | null; target: string | null; reason: string }>;
  speed?: number;
  paused?: boolean;
  environment?: string;
  is_simulation?: boolean;
  statistics?: PlayerStatsRow[];
}

export interface GameEventMsg {
  type: string;
  time: number;
  player_id: number | null;
  data: Record<string, unknown>;
}

export interface BotActionMsg {
  player_id: number;
  time: number;
  action: string;
  source: string;
  score: number;
  ok: boolean;
  reason: string;
}

export interface WsMessage<T = unknown> {
  type: string;
  session_id: number | null;
  data: T;
  ts?: string;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface HistoryItem {
  id: number;
  name: string;
  status: SessionStatus;
  scenario: string;
  game_mode: string;
  seed: number;
  created_at: string;
  finished_at: string | null;
  winner: TeamName | null;
  win_condition: string | null;
  duration_seconds: number | null;
  radiant_score: number;
  dire_score: number;
  events_count: number;
}

export interface LogEntry {
  id: number;
  level: string;
  component: string;
  message: string;
  timestamp: string;
}

export interface MatchEventRow {
  id: number;
  session_id: number;
  player_id: number | null;
  event_type: string;
  event_data: Record<string, unknown>;
  game_time: number;
  timestamp: string;
}

export interface Overview {
  players: { total: number; by_team: Record<TeamName, number>; by_status: Record<string, number> };
  sessions: { total: number; by_status: Record<string, number>; active: number; active_ids: number[] };
  matches: {
    finished: number;
    radiant_wins: number;
    dire_wins: number;
    no_winner: number;
    avg_duration_seconds: number | null;
    avg_total_kills: number | null;
  };
  last_match: {
    id: number;
    name: string;
    status: string;
    winner: TeamName | null;
    win_condition: string | null;
    duration_seconds: number | null;
    radiant_score: number;
    dire_score: number;
    finished_at: string | null;
  } | null;
  errors: number;
  events_total: number;
}

export interface PlayerAggregate {
  player_id: number;
  player_name: string;
  team: TeamName;
  role: string;
  matches: number;
  wins: number;
  win_rate: number;
  avg_kills: number | null;
  avg_deaths: number | null;
  avg_assists: number | null;
  kda: number;
  avg_gpm: number | null;
  avg_xpm: number | null;
  avg_net_worth: number | null;
  avg_last_hits: number | null;
  avg_hero_damage: number | null;
  avg_tower_damage: number | null;
}

export interface TeamAggregate {
  team: TeamName;
  matches: number;
  wins: number;
  win_rate: number | null;
  avg_kills: number | null;
  avg_deaths: number | null;
  avg_net_worth: number | null;
  avg_gpm: number | null;
  avg_xpm: number | null;
  avg_tower_damage: number | null;
  avg_hero_damage: number | null;
}

export interface SessionAggregate {
  session_id: number;
  name: string;
  scenario: string;
  winner: TeamName | null;
  duration_minutes: number;
  radiant_kills: number;
  dire_kills: number;
  radiant_net_worth: number;
  dire_net_worth: number;
  radiant_tower_damage: number;
  dire_tower_damage: number;
  kills: number;
  deaths: number;
  assists: number;
  avg_gpm: number | null;
  avg_xpm: number | null;
}

export interface SessionStatistics {
  session_id: number;
  status: SessionStatus;
  source: "live" | "stored" | "none";
  game_time: number | null;
  winner: TeamName | null;
  players: PlayerStatsRow[];
  teams: Record<TeamName, Record<string, number>>;
  timeline: Record<string, number>[];
}

export interface RuntimeSettings {
  default_speed: number;
  max_game_seconds: number;
  snapshot_interval: number;
  tick_seconds: number;
  ws_publish_hz: number;
  ui_refresh_seconds: number;
  log_level: string;
  db_log_level: string;
  max_concurrent_sessions: number;
  persist_ability_events: boolean;
}

export interface SettingsResponse {
  runtime: RuntimeSettings;
  backend: { version: string; host: string; port: number; cors_origins: string[]; api_rate_limit_per_minute: number; log_dir: string };
  database: { url: string; dialect: string; path?: string; size_bytes?: number };
}

export interface Health {
  status: string;
  version: string;
  database: string;
  active_sessions: number;
  websocket_clients: number;
  uptime_seconds: number;
}
