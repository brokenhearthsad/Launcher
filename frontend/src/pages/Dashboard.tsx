import { AlertOctagon, Clock, Gamepad2, Radio, Trophy, Users } from "lucide-react";
import { Bar as RBar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { Card, Empty, ErrorBanner, PageHeader, Spinner, StatCard, StatusBadge, TeamBadge } from "../components/ui";
import { useLiveEvent } from "../hooks/LiveEvents";
import { useAsync } from "../hooks/useAsync";
import { useUiSettings } from "../hooks/UiSettings";
import { formatDuration, formatGameTime, titleCase } from "../lib/format";

export default function Dashboard() {
  const { refreshMs } = useUiSettings();
  const health = useAsync(api.health, [], refreshMs);
  const overview = useAsync(api.overview, [], refreshMs);
  const active = useAsync(() => api.sessions({ page_size: 10 }), [], refreshMs);
  const recent = useAsync(() => api.analyticsSessions(), []);
  useLiveEvent(["session_started", "session_finished", "session_paused", "session_resumed", "player_updated"], () => {
    void overview.reload();
    void active.reload();
    void recent.reload();
  });

  const o = overview.data;
  const activeSessions = (active.data?.items ?? []).filter((s) => s.status === "running" || s.status === "paused");
  const durations = (recent.data ?? []).slice(-12).map((s) => ({ name: `#${s.session_id}`, minutes: s.duration_minutes }));

  return (
    <div>
      <PageHeader title="Dashboard" subtitle="System status and key indicators of the test lab." />
      <ErrorBanner error={health.error ?? overview.error} onRetry={() => { void health.reload(); void overview.reload(); }} />
      {!o && overview.loading && <Spinner />}
      {o && (
        <>
          <div className="mt-4 grid grid-cols-2 gap-4 lg:grid-cols-6" data-testid="dashboard-stats">
            <StatCard label="System" value={health.data?.status === "ok" ? "Online" : health.data ? "Degraded" : "—"}
              tone={health.data?.status === "ok" ? "radiant" : "danger"}
              hint={health.data ? `v${health.data.version} · DB ${health.data.database}` : undefined} icon={<Gamepad2 className="h-4 w-4" />} />
            <StatCard label="Participants" value={o.players.total}
              hint={`${o.players.by_team.radiant ?? 0} Radiant · ${o.players.by_team.dire ?? 0} Dire`} icon={<Users className="h-4 w-4" />} />
            <StatCard label="Active sessions" value={o.sessions.active} tone="accent" icon={<Radio className="h-4 w-4" />}
              hint={`${o.sessions.total} sessions total`} />
            <StatCard label="Finished matches" value={o.matches.finished}
              hint={`Radiant ${o.matches.radiant_wins} · Dire ${o.matches.dire_wins}`} icon={<Trophy className="h-4 w-4" />} />
            <StatCard label="Avg duration" value={formatDuration(o.matches.avg_duration_seconds)} icon={<Clock className="h-4 w-4" />}
              hint={o.matches.avg_total_kills !== null ? `${o.matches.avg_total_kills} kills / match` : "no finished matches"} />
            <StatCard label="Errors" value={o.errors} tone={o.errors ? "danger" : "default"} icon={<AlertOctagon className="h-4 w-4" />}
              hint={<Link className="underline" to="/logs">open logs</Link>} />
          </div>

          <div className="mt-6 grid gap-6 lg:grid-cols-3">
            <Card title="Active sessions" className="lg:col-span-2">
              {activeSessions.length === 0 ? (
                <Empty>No session is running. <Link className="text-accent underline" to="/match-control">Create one in Match Control</Link>.</Empty>
              ) : (
                <ul className="divide-y divide-surface-border">
                  {activeSessions.map((s) => (
                    <li key={s.id} className="flex items-center justify-between py-3">
                      <div>
                        <div className="font-medium">#{s.id} {s.name}</div>
                        <div className="text-xs text-gray-500">{titleCase(s.scenario)} · {titleCase(s.game_mode)} · x{s.speed}</div>
                      </div>
                      <div className="flex items-center gap-3">
                        <StatusBadge status={s.status} />
                        <Link to={`/live/${s.id}`} className="text-sm text-accent hover:underline">Watch live →</Link>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
            <Card title="Last match">
              {o.last_match ? (
                <div className="space-y-2 text-sm">
                  <div className="font-medium">#{o.last_match.id} {o.last_match.name}</div>
                  <div className="flex items-center gap-2"><StatusBadge status={o.last_match.status} />
                    {o.last_match.winner ? <><span className="text-gray-400">Winner</span><TeamBadge team={o.last_match.winner} /></> : <span className="text-gray-500">no winner</span>}
                  </div>
                  <div className="text-3xl font-bold">
                    <span className="text-radiant">{o.last_match.radiant_score}</span>
                    <span className="mx-2 text-gray-600">:</span>
                    <span className="text-dire">{o.last_match.dire_score}</span>
                  </div>
                  <div className="text-gray-400">Duration {formatGameTime(o.last_match.duration_seconds)} · {titleCase(o.last_match.win_condition ?? "—")}</div>
                </div>
              ) : <Empty>No matches yet.</Empty>}
            </Card>
          </div>

          <div className="mt-6 grid gap-6 lg:grid-cols-3">
            <Card title="Participant status">
              <ul className="space-y-2 text-sm">
                {Object.entries(o.players.by_status).map(([st, n]) => (
                  <li key={st} className="flex items-center justify-between"><StatusBadge status={st} /><span className="font-mono">{n}</span></li>
                ))}
              </ul>
            </Card>
            <Card title="Recent match durations (min)" className="lg:col-span-2">
              {durations.length === 0 ? <Empty>Finish a match to see durations.</Empty> : (
                <div className="h-56">
                  <ResponsiveContainer>
                    <BarChart data={durations} maxBarSize={56}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#273248" />
                      <XAxis dataKey="name" stroke="#9ca3af" fontSize={12} />
                      <YAxis stroke="#9ca3af" fontSize={12} />
                      <Tooltip contentStyle={{ background: "#111827", border: "1px solid #273248" }} />
                      <RBar dataKey="minutes" fill="#f59e0b" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
