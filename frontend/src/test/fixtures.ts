import type { Meta, Player } from "../api/types";

export const META: Meta = {
  teams: ["radiant", "dire"], roles: ["carry", "mid", "offlane", "soft_support", "hard_support"],
  difficulties: ["easy", "medium", "hard", "expert"], player_statuses: ["offline", "ready", "running", "paused", "error", "finished"],
  scenarios: ["balanced", "aggressive"], game_modes: ["standard", "turbo"],
  environments: [
    { name: "mock", title: "Local simulator", description: "sim", available: true, is_simulation: true, capabilities: {}, notes: [] },
    { name: "dota_test", title: "Dota 2 test environment (planned)", description: "Not available.", available: false, is_simulation: false, capabilities: {}, notes: ["read-only GSI"] },
  ],
  heroes: [{ key: "axe", name: "Axe", primary: "str", roles: ["offlane"], attack_range: 1, abilities: [] },
    { key: "lina", name: "Lina", primary: "int", roles: ["mid"], attack_range: 4, abilities: [] }],
  items: [],
};

export function players(): Player[] {
  return Array.from({ length: 10 }, (_, i) => ({
    id: i + 1, name: i < 5 ? `Radiant ${i + 1}` : `Dire ${i - 4}`, team: i < 5 ? "radiant" : "dire", slot: (i % 5) + 1,
    role: ["carry", "mid", "offlane", "soft_support", "hard_support"][i % 5], hero: i % 2 ? "lina" : "axe",
    bot_difficulty: "hard", status: "ready", aggression: 0.5, farming_priority: 0.6, team_coordination: 0.7,
    risk_tolerance: 0.4, objective_priority: 0.5, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z",
  }));
}

export const OVERVIEW = {
  players: { total: 10, by_team: { radiant: 5, dire: 5 }, by_status: { ready: 10 } },
  sessions: { total: 3, by_status: { finished: 2, running: 1 }, active: 1, active_ids: [3] },
  matches: { finished: 2, radiant_wins: 1, dire_wins: 1, no_winner: 0, avg_duration_seconds: 2100, avg_total_kills: 50 },
  last_match: { id: 2, name: "Last one", status: "finished", winner: "dire", win_condition: "ancient_destroyed", duration_seconds: 2400, radiant_score: 20, dire_score: 30, finished_at: "2026-01-01T00:00:00Z" },
  errors: 0, events_total: 1000,
};

export const SESSION = {
  id: 3, name: "Running one", status: "running", environment: "mock", map: "lab_map_v1", scenario: "balanced", game_mode: "standard",
  seed: 1, speed: 20, max_game_seconds: 3600, created_at: "2026-01-01T00:00:00Z", started_at: null, finished_at: null, winner: null,
  win_condition: null, duration_seconds: 120, radiant_score: 1, dire_score: 2, events_count: 10, error_message: null,
};
