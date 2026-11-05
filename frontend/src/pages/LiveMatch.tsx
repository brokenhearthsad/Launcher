import { Coins, Crown, Flag, Skull, Swords, Zap } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { BotActionMsg, GameEventMsg, HeroState, LiveSnapshot, SessionDetail, TeamName } from "../api/types";
import { MiniMap } from "../components/MiniMap";
import { Bar, Card, Empty, ErrorBanner, PageHeader, Spinner, StatusBadge, TeamBadge, cx } from "../components/ui";
import { useLiveEvent } from "../hooks/LiveEvents";
import { useItemName } from "../hooks/MetaContext";
import { useAsync } from "../hooks/useAsync";
import { formatGameTime, formatNumber, titleCase } from "../lib/format";
import { SessionActions } from "./MatchControl";

const TIERS = ["t1", "t2", "t3"];

export function describeEvent(e: GameEventMsg, name: (id: number | null | undefined) => string): string {
  const d = e.data as Record<string, unknown>;
  switch (e.type) {
    case "hero_killed": return `${d.killer_name ?? "?"} killed ${d.victim_name}${(d.assists as number[])?.length ? ` (+${(d.assists as number[]).length} assists)` : ""}`;
    case "first_blood": return `First blood by ${name(e.player_id)}`;
    case "tower_destroyed": return `${titleCase(String(d.team))} ${String(d.lane)} ${String(d.tier).toUpperCase()} destroyed${e.player_id ? ` by ${name(e.player_id)}` : ""}`;
    case "roshan_killed": return `Roshan slain by ${titleCase(String(d.team))}; aegis → ${name(d.aegis as number)}`;
    case "roshan_spawned": return "Roshan has respawned";
    case "aegis_used": return `${name(e.player_id)} revived with the Aegis`;
    case "level_up": return `${name(e.player_id)} reached level ${d.level}`;
    case "item_purchased": return `${name(e.player_id)} bought ${d.item}`;
    case "item_sold": return `${name(e.player_id)} sold ${d.item}`;
    case "teleport": return `${name(e.player_id)} teleported`;
    case "game_start": return `Simulation started (seed ${d.seed})`;
    case "game_end": return `Match ended — ${d.winner ? `${titleCase(String(d.winner))} victory` : "no winner"} (${titleCase(String(d.condition))})`;
    default: return e.type;
  }
}

const EVENT_ICON: Record<string, JSX.Element> = {
  hero_killed: <Skull className="h-3.5 w-3.5 text-red-400" />,
  first_blood: <Skull className="h-3.5 w-3.5 text-red-500" />,
  tower_destroyed: <Flag className="h-3.5 w-3.5 text-amber-400" />,
  roshan_killed: <Crown className="h-3.5 w-3.5 text-purple-400" />,
  item_purchased: <Coins className="h-3.5 w-3.5 text-yellow-300" />,
  level_up: <Zap className="h-3.5 w-3.5 text-sky-300" />,
};

function HeroRow({ h, action, selected, onSelect }: { h: HeroState; action?: BotActionMsg; selected: boolean; onSelect: () => void }) {
  const itemName = useItemName();
  return (
    <button type="button" onClick={onSelect} data-testid={`hero-row-${h.player_id}`}
      className={cx("w-full rounded-lg border p-3 text-left transition", selected ? "border-accent" : "border-surface-border hover:border-gray-500",
        !h.alive && "opacity-60")}>
      <div className="flex items-center justify-between gap-2 text-sm">
        <div className="min-w-0">
          <span className="font-semibold">{h.name}</span>
          <span className="ml-2 text-gray-400">{h.hero_name}</span>
          <span className="ml-2 rounded bg-gray-800 px-1.5 text-xs">Lv {h.level}</span>
          {h.has_aegis && <span className="ml-1 text-xs text-yellow-300">Aegis</span>}
        </div>
        <div className="shrink-0 font-mono text-xs">
          <span className="text-emerald-300">{h.kills}</span>/<span className="text-red-300">{h.deaths}</span>/<span className="text-sky-300">{h.assists}</span>
          <span className="ml-2 text-gray-400">{h.last_hits}/{h.denies}</span>
          <span className="ml-2 text-yellow-300">{formatNumber(h.net_worth)}</span>
        </div>
      </div>
      <div className="mt-2 grid grid-cols-2 gap-2">
        <div><Bar value={h.hp} max={h.max_hp} color="bg-emerald-500" /><div className="mt-0.5 text-[10px] text-gray-500">{h.hp}/{h.max_hp} HP</div></div>
        <div><Bar value={h.mana} max={h.max_mana} color="bg-sky-500" /><div className="mt-0.5 text-[10px] text-gray-500">{h.mana}/{h.max_mana} MP</div></div>
      </div>
      <div className="mt-1 flex flex-wrap gap-1">
        {h.items.map((it, i) => <span key={i} className="rounded bg-gray-800 px-1.5 py-0.5 text-[10px] text-gray-300">{itemName(it)}</span>)}
      </div>
      <div className="mt-1 truncate text-[11px] text-gray-500">
        {h.alive ? <>▶ {action ? `${action.action} (${action.source})` : h.action}</> : <span className="text-red-300">Dead — respawn in {h.respawn_in}s</span>}
      </div>
    </button>
  );
}

function ObjectiveProgress({ snap }: { snap: LiveSnapshot }) {
  const lanes = ["top", "mid", "bot"];
  const alive = (team: TeamName, lane: string, tier: string) => snap.towers.find((t) => t.team === team && t.lane === lane && t.tier === tier)?.alive;
  return (
    <div className="space-y-3 text-xs" data-testid="objectives">
      {(["radiant", "dire"] as TeamName[]).map((team) => {
        const all = snap.towers.filter((t) => t.team === team);
        const up = all.filter((t) => t.alive).length;
        const ancient = all.find((t) => t.tier === "ancient");
        return (
          <div key={team}>
            <div className="mb-1 flex justify-between"><TeamBadge team={team} /><span className="text-gray-400">{up}/{all.length} structures · Ancient {ancient ? Math.round((ancient.hp / ancient.max_hp) * 100) : 0}%</span></div>
            <div className="grid grid-cols-3 gap-2">
              {lanes.map((lane) => (
                <div key={lane} className="flex items-center gap-1">
                  <span className="w-7 text-gray-500">{lane}</span>
                  {TIERS.map((tier) => (
                    <span key={tier} title={`${lane} ${tier}`} className={cx("h-3 w-3 rounded-sm", alive(team, lane, tier)
                      ? (team === "radiant" ? "bg-radiant" : "bg-dire") : "bg-gray-800")} />
                  ))}
                </div>
              ))}
            </div>
          </div>
        );
      })}
      <div className="flex justify-between text-gray-400"><span>Roshan</span><span>{snap.roshan.alive ? `alive (${formatNumber(snap.roshan.hp)} HP)` : "dead"} · killed {snap.roshan.kills}×</span></div>
    </div>
  );
}

export default function LiveMatch() {
  const params = useParams();
  const navigate = useNavigate();
  const recent = useAsync(() => api.sessions({ page_size: 20 }), []);
  const fallbackId = recent.data?.items.find((s) => s.status === "running" || s.status === "paused")?.id ?? recent.data?.items[0]?.id;
  const sessionId = params.sessionId ? Number(params.sessionId) : fallbackId;

  const [detail, setDetail] = useState<SessionDetail | null>(null);
  const [snap, setSnap] = useState<LiveSnapshot | null>(null);
  const [events, setEvents] = useState<GameEventMsg[]>([]);
  const [actions, setActions] = useState<Record<number, BotActionMsg>>({});
  const [selected, setSelected] = useState<number | null>(null);
  const [error, setError] = useState<Error | null>(null);

  const load = useCallback(async () => {
    if (!sessionId) return;
    try {
      const d = await api.session(sessionId);
      setDetail(d);
      if (d.live) setSnap(d.live);
      else if (!snap || snap.time === 0) setSnap(null);
      setError(null);
    } catch (e) {
      setError(e as Error);
    }
  }, [sessionId]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    setSnap(null);
    setEvents([]);
    setActions({});
    void load();
  }, [load]);

  useLiveEvent(["statistics_updated"], (m) => {
    if (m.session_id === sessionId) setSnap(m.data as LiveSnapshot);
  });
  useLiveEvent(["match_event"], (m) => {
    if (m.session_id !== sessionId) return;
    const evs = (m.data as { events: GameEventMsg[] }).events;
    setEvents((prev) => [...evs.slice().reverse(), ...prev].slice(0, 150));
  });
  useLiveEvent(["bot_action"], (m) => {
    if (m.session_id !== sessionId) return;
    const list = (m.data as { actions: BotActionMsg[] }).actions;
    setActions((prev) => ({ ...prev, ...Object.fromEntries(list.map((a) => [a.player_id, a])) }));
  });
  useLiveEvent(["session_started", "session_paused", "session_resumed", "session_finished"], (m) => {
    if (m.session_id === sessionId) void load();
    else void recent.reload();
  });

  const nameOf = useMemo(() => {
    const map = new Map((snap?.heroes ?? []).map((h) => [h.player_id, h.name]));
    return (id: number | null | undefined) => (id ? map.get(id) ?? `#${id}` : "?");
  }, [snap]);

  const team = (t: TeamName) => (snap?.heroes ?? []).filter((h) => h.team === t);
  const selectedAction = selected ? actions[selected] : undefined;

  return (
    <div>
      <PageHeader title="Live Match" subtitle={snap?.is_simulation !== false ? "Simulated match (local simulator) — real-time updates over WebSocket." : undefined}
        actions={recent.data && recent.data.items.length > 0 && (
          <select aria-label="Select session" value={sessionId ?? ""} onChange={(e) => navigate(`/live/${e.target.value}`)}
            className="rounded-lg border border-surface-border bg-gray-900 px-3 py-2 text-sm">
            {recent.data.items.map((s) => <option key={s.id} value={s.id}>#{s.id} {s.name} ({s.status})</option>)}
          </select>
        )} />
      <ErrorBanner error={error ?? recent.error} />
      {!sessionId && !recent.loading && <Empty>No sessions exist yet. Create one in Match Control.</Empty>}
      {sessionId && !detail && !error && <Spinner />}
      {detail && (
        <>
          <div className="mb-6 flex flex-wrap items-center justify-between gap-4 rounded-xl border border-surface-border bg-surface/80 p-4" data-testid="scoreboard">
            <div className="flex items-center gap-3">
              <StatusBadge status={detail.status} />
              <span className="text-sm text-gray-400">#{detail.id} {detail.name} · {titleCase(detail.scenario)} · seed {detail.seed}</span>
            </div>
            <div className="flex items-center gap-6">
              <span className="text-4xl font-black text-radiant" data-testid="score-radiant">{snap?.score.radiant ?? detail.radiant_score}</span>
              <div className="text-center">
                <div className="font-mono text-2xl" data-testid="game-time">{formatGameTime(snap?.time ?? detail.duration_seconds)}</div>
                <div className="text-[11px] text-gray-500">{snap?.speed ? `x${snap.speed}` : ""}{snap?.paused ? " · paused" : ""}</div>
              </div>
              <span className="text-4xl font-black text-dire" data-testid="score-dire">{snap?.score.dire ?? detail.dire_score}</span>
            </div>
            <SessionActions s={detail} onChanged={load} />
          </div>
          {detail.status === "finished" && (
            <div className="mb-6 rounded-xl border border-violet-700 bg-violet-950/40 p-4 text-sm">
              Match finished: {detail.winner ? <><TeamBadge team={detail.winner} /> victory</> : "no winner"} · {titleCase(detail.win_condition ?? "")} after {formatGameTime(detail.duration_seconds)}.
            </div>
          )}
          {detail.status === "error" && <ErrorBanner error={{ message: detail.error_message ?? "session error" }} />}
          {!snap ? (
            <Empty>{detail.status === "created" ? "Session has not started yet. Press Start." : "No live data for this session. See Match History for stored results."}</Empty>
          ) : (
            <div className="grid gap-6 xl:grid-cols-[1fr_380px_1fr]">
              <Card title={<span className="text-radiant">Radiant · NW {formatNumber(snap.net_worth.radiant)}</span>}>
                <div className="space-y-2">{team("radiant").map((h) => <HeroRow key={h.player_id} h={h} action={actions[h.player_id]} selected={selected === h.player_id} onSelect={() => setSelected(h.player_id)} />)}</div>
              </Card>
              <div className="space-y-6">
                <Card title="Map"><MiniMap snap={snap} highlight={selected} /></Card>
                <Card title="Objectives"><ObjectiveProgress snap={snap} /></Card>
                {snap.directives && (
                  <Card title="Team AI">
                    <ul className="space-y-2 text-xs">
                      {(["radiant", "dire"] as TeamName[]).map((t) => snap.directives && (
                        <li key={t} className="flex items-start gap-2"><TeamBadge team={t} />
                          <span><b className="text-gray-200">{titleCase(snap.directives[t].kind)}</b>{snap.directives[t].target ? ` → ${snap.directives[t].target}` : ""}<span className="block text-gray-500">{snap.directives[t].reason}</span></span>
                        </li>
                      ))}
                    </ul>
                  </Card>
                )}
              </div>
              <Card title={<span className="text-dire">Dire · NW {formatNumber(snap.net_worth.dire)}</span>}>
                <div className="space-y-2">{team("dire").map((h) => <HeroRow key={h.player_id} h={h} action={actions[h.player_id]} selected={selected === h.player_id} onSelect={() => setSelected(h.player_id)} />)}</div>
              </Card>
            </div>
          )}
          {snap && (
            <div className="mt-6 grid gap-6 lg:grid-cols-2">
              <Card title="Recent events" icon={<Swords className="h-4 w-4" />}>
                {events.length === 0 ? <Empty>Waiting for events…</Empty> : (
                  <ul className="max-h-80 space-y-1 overflow-y-auto font-mono text-xs" data-testid="event-feed">
                    {events.map((e, i) => (
                      <li key={i} className="flex items-center gap-2">
                        <span className="w-12 text-gray-500">{formatGameTime(e.time)}</span>
                        {EVENT_ICON[e.type] ?? <span className="h-3.5 w-3.5" />}
                        <span>{describeEvent(e, nameOf)}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
              <Card title={selected ? `Bot decision — ${nameOf(selected)}` : "Bot decisions"}>
                {selectedAction ? (
                  <div className="space-y-1 text-sm">
                    <div><span className="text-gray-400">Action:</span> {selectedAction.action}</div>
                    <div><span className="text-gray-400">Subsystem:</span> {selectedAction.source} · utility {selectedAction.score}</div>
                    <div><span className="text-gray-400">Reason:</span> {selectedAction.reason || "—"}</div>
                    <div><span className="text-gray-400">Accepted:</span> {selectedAction.ok ? "yes" : "no"}</div>
                  </div>
                ) : (
                  <ul className="space-y-1 text-xs">
                    {Object.values(actions).sort((a, b) => a.player_id - b.player_id).map((a) => (
                      <li key={a.player_id} className="flex justify-between gap-2"><span className="text-gray-400">{nameOf(a.player_id)}</span><span className="truncate">{a.action}</span><span className="text-gray-500">{a.source}</span></li>
                    ))}
                    {Object.keys(actions).length === 0 && <Empty>Select a hero to inspect its last decision.</Empty>}
                  </ul>
                )}
              </Card>
            </div>
          )}
        </>
      )}
    </div>
  );
}
