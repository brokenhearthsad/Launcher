import { Download } from "lucide-react";
import { useMemo, useState } from "react";
import {
  Bar as RBar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { api } from "../api/client";
import { Card, Empty, ErrorBanner, PageHeader, Select, Spinner, Table, TeamBadge, Toggle } from "../components/ui";
import { useAsync } from "../hooks/useAsync";
import { formatNumber, pct, titleCase } from "../lib/format";

const AXIS = { stroke: "#9ca3af", fontSize: 10, interval: 0 as const };
const TIP = { contentStyle: { background: "#111827", border: "1px solid #273248", fontSize: 12 } };
const GRID = <CartesianGrid strokeDasharray="3 3" stroke="#273248" />;

function ChartCard({ title, children, empty }: { title: string; children: React.ReactElement; empty: boolean }) {
  return (
    <Card title={title}>
      {empty ? <Empty>No data for the selected filters.</Empty> : <div className="h-64"><ResponsiveContainer>{children}</ResponsiveContainer></div>}
    </Card>
  );
}

export default function Analytics() {
  const [team, setTeam] = useState("");
  const [playerId, setPlayerId] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [scenario, setScenario] = useState("");
  const [includeStopped, setIncludeStopped] = useState(false);
  const q = { team: team || undefined, player_id: playerId || undefined, session_id: sessionId ? [Number(sessionId)] : undefined,
    scenario: scenario || undefined, include_stopped: includeStopped || undefined };
  const key = JSON.stringify(q);

  const players = useAsync(() => api.players(), []);
  const history = useAsync(() => api.history({ page_size: 100 }), []);
  const perPlayer = useAsync(() => api.analyticsPlayers(q), [key]);
  const perTeam = useAsync(() => api.analyticsTeams({ session_id: q.session_id, scenario: q.scenario, include_stopped: q.include_stopped }), [key]);
  const perSession = useAsync(() => api.analyticsSessions(q), [key]);
  const timeline = useAsync(() => (sessionId ? api.statistics(Number(sessionId)) : Promise.resolve(null)), [sessionId]);

  const playerRows = useMemo(() => (perPlayer.data ?? []).map((p) => ({
    name: p.player_name, team: p.team, GPM: p.avg_gpm, XPM: p.avg_xpm, "Net worth": p.avg_net_worth,
    Kills: p.avg_kills, Deaths: p.avg_deaths, Assists: p.avg_assists, "Tower damage": p.avg_tower_damage,
  })), [perPlayer.data]);
  const sessionRows = (perSession.data ?? []).map((s) => ({ name: `#${s.session_id}`, Minutes: s.duration_minutes,
    "Radiant kills": s.radiant_kills, "Dire kills": s.dire_kills }));
  const timelineRows = (timeline.data?.timeline ?? []) as Record<string, number>[];

  return (
    <div>
      <PageHeader title="Analytics" subtitle="Aggregated from stored session statistics. Only completed matches are included unless enabled below."
        actions={<>
          <a className="inline-flex items-center gap-2 rounded-lg border border-surface-border bg-surface-raised px-3 py-2 text-sm hover:bg-gray-700" href={api.exportUrl("csv", q)} download><Download className="h-4 w-4" />CSV</a>
          <a className="inline-flex items-center gap-2 rounded-lg border border-surface-border bg-surface-raised px-3 py-2 text-sm hover:bg-gray-700" href={api.exportUrl("json", q)} download><Download className="h-4 w-4" />JSON</a>
        </>} />
      <Card title="Filters">
        <div className="grid items-end gap-3 md:grid-cols-5">
          <Select label="Team" value={team} onChange={setTeam} testId="filter-team"
            options={[{ value: "", label: "Both teams" }, { value: "radiant", label: "Radiant" }, { value: "dire", label: "Dire" }]} />
          <Select label="Participant" value={playerId} onChange={setPlayerId} testId="filter-player"
            options={[{ value: "", label: "All participants" }, ...(players.data ?? []).map((p) => ({ value: String(p.id), label: p.name }))]} />
          <Select label="Session" value={sessionId} onChange={setSessionId} testId="filter-session"
            options={[{ value: "", label: "All sessions" }, ...(history.data?.items ?? []).map((s) => ({ value: String(s.id), label: `#${s.id} ${s.name} (${s.status})` }))]} />
          <Select label="Scenario" value={scenario} onChange={setScenario}
            options={[{ value: "", label: "All scenarios" }, ...["balanced", "radiant_advantage", "dire_advantage", "aggressive", "defensive"].map((s) => ({ value: s, label: titleCase(s) }))]} />
          <Toggle label="Include stopped" checked={includeStopped} onChange={setIncludeStopped} />
        </div>
      </Card>
      <ErrorBanner error={perPlayer.error ?? perTeam.error ?? perSession.error} />
      {perPlayer.loading && !perPlayer.data && <Spinner />}

      <Card title="Team comparison" className="mt-6">
        <Table head={["Team", "Matches", "Wins", "Win rate", "Avg kills", "Avg deaths", "Avg net worth", "Avg GPM", "Avg XPM", "Avg tower dmg"]} testId="team-table">
          {(perTeam.data ?? []).map((t) => (
            <tr key={t.team}>
              <td className="px-3 py-2"><TeamBadge team={t.team} /></td>
              <td className="px-3 py-2">{t.matches}</td><td className="px-3 py-2">{t.wins}</td><td className="px-3 py-2">{pct(t.win_rate)}</td>
              <td className="px-3 py-2">{formatNumber(t.avg_kills, 1)}</td><td className="px-3 py-2">{formatNumber(t.avg_deaths, 1)}</td>
              <td className="px-3 py-2">{formatNumber(t.avg_net_worth)}</td><td className="px-3 py-2">{formatNumber(t.avg_gpm)}</td>
              <td className="px-3 py-2">{formatNumber(t.avg_xpm)}</td><td className="px-3 py-2">{formatNumber(t.avg_tower_damage)}</td>
            </tr>
          ))}
        </Table>
      </Card>

      <div className="mt-6 grid gap-6 xl:grid-cols-2">
        <ChartCard title="GPM / XPM per participant" empty={playerRows.length === 0}>
          <BarChart data={playerRows} maxBarSize={48}>{GRID}<XAxis dataKey="name" {...AXIS} /><YAxis {...AXIS} /><Tooltip {...TIP} /><Legend />
            <RBar dataKey="GPM" fill="#f59e0b" /><RBar dataKey="XPM" fill="#38bdf8" /></BarChart>
        </ChartCard>
        <ChartCard title="Average net worth" empty={playerRows.length === 0}>
          <BarChart data={playerRows} maxBarSize={48}>{GRID}<XAxis dataKey="name" {...AXIS} /><YAxis {...AXIS} /><Tooltip {...TIP} />
            <RBar dataKey="Net worth" fill="#a78bfa" /></BarChart>
        </ChartCard>
        <ChartCard title="Kills / Deaths / Assists (average)" empty={playerRows.length === 0}>
          <BarChart data={playerRows} maxBarSize={48}>{GRID}<XAxis dataKey="name" {...AXIS} /><YAxis {...AXIS} /><Tooltip {...TIP} /><Legend />
            <RBar dataKey="Kills" fill="#4ade80" /><RBar dataKey="Deaths" fill="#f87171" /><RBar dataKey="Assists" fill="#60a5fa" /></BarChart>
        </ChartCard>
        <ChartCard title="Tower damage (average)" empty={playerRows.length === 0}>
          <BarChart data={playerRows} maxBarSize={48}>{GRID}<XAxis dataKey="name" {...AXIS} /><YAxis {...AXIS} /><Tooltip {...TIP} />
            <RBar dataKey="Tower damage" fill="#fb923c" /></BarChart>
        </ChartCard>
        <ChartCard title="Match duration (minutes) and kills" empty={sessionRows.length === 0}>
          <BarChart data={sessionRows} maxBarSize={48}>{GRID}<XAxis dataKey="name" {...AXIS} /><YAxis {...AXIS} /><Tooltip {...TIP} /><Legend />
            <RBar dataKey="Minutes" fill="#f59e0b" /><RBar dataKey="Radiant kills" fill="#4ade80" /><RBar dataKey="Dire kills" fill="#f87171" /></BarChart>
        </ChartCard>
        <ChartCard title={sessionId ? `Net worth dynamics — session #${sessionId}` : "Net worth dynamics (select a session)"} empty={timelineRows.length === 0}>
          <LineChart data={timelineRows}>{GRID}<XAxis dataKey="minute" {...AXIS} unit="m" /><YAxis {...AXIS} /><Tooltip {...TIP} /><Legend />
            <Line dataKey="radiant_net_worth" name="Radiant" stroke="#4ade80" dot={false} />
            <Line dataKey="dire_net_worth" name="Dire" stroke="#f87171" dot={false} />
            <Line dataKey="net_worth_diff" name="Radiant lead" stroke="#f59e0b" dot={false} strokeDasharray="4 2" /></LineChart>
        </ChartCard>
      </div>

      <Card title="Participant comparison" className="mt-6">
        {(perPlayer.data ?? []).length === 0 ? <Empty>No completed matches match the filters.</Empty> : (
          <Table head={["Participant", "Team", "Role", "Matches", "Win rate", "K/D/A", "KDA", "GPM", "XPM", "LH", "Hero dmg", "Tower dmg"]} testId="player-table">
            {(perPlayer.data ?? []).map((p) => (
              <tr key={p.player_id}>
                <td className="px-3 py-2 font-medium">{p.player_name}</td><td className="px-3 py-2"><TeamBadge team={p.team} /></td>
                <td className="px-3 py-2">{titleCase(p.role)}</td><td className="px-3 py-2">{p.matches}</td><td className="px-3 py-2">{pct(p.win_rate)}</td>
                <td className="px-3 py-2 font-mono">{formatNumber(p.avg_kills, 1)}/{formatNumber(p.avg_deaths, 1)}/{formatNumber(p.avg_assists, 1)}</td>
                <td className="px-3 py-2">{p.kda}</td><td className="px-3 py-2">{formatNumber(p.avg_gpm)}</td><td className="px-3 py-2">{formatNumber(p.avg_xpm)}</td>
                <td className="px-3 py-2">{formatNumber(p.avg_last_hits)}</td><td className="px-3 py-2">{formatNumber(p.avg_hero_damage)}</td>
                <td className="px-3 py-2">{formatNumber(p.avg_tower_damage)}</td>
              </tr>
            ))}
          </Table>
        )}
      </Card>
    </div>
  );
}
