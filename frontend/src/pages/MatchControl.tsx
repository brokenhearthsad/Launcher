import { Pause, Play, Plus, Radio, Square, StepForward } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { MatchSession, Player, SessionCreate, TeamName } from "../api/types";
import {
  Button, Card, ConfirmDialog, Empty, ErrorBanner, PageHeader, Pagination, Select, Spinner, StatusBadge, Table, TextInput,
} from "../components/ui";
import { useLiveEvent } from "../hooks/LiveEvents";
import { useMeta } from "../hooks/MetaContext";
import { useAsync } from "../hooks/useAsync";
import { formatGameTime, titleCase } from "../lib/format";

const SPEEDS = [1, 5, 10, 20, 50, 100, 1000];

interface Row { include: boolean; team: TeamName; hero: string; role: string }

export function SessionActions({ s, onChanged }: { s: MatchSession; onChanged: () => void }) {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [confirmStop, setConfirmStop] = useState(false);
  const run = async (name: string, fn: () => Promise<unknown>) => {
    setBusy(name);
    setError(null);
    try {
      await fn();
      onChanged();
    } catch (e) {
      setError(e as ApiError);
    } finally {
      setBusy(null);
    }
  };
  const active = s.status === "running" || s.status === "paused";
  return (
    <div className="flex flex-wrap items-center gap-2">
      {s.status === "created" && (
        <Button variant="success" loading={busy === "start"} onClick={() => run("start", () => api.startSession(s.id))} aria-label={`Start session ${s.id}`}>
          <Play className="h-4 w-4" />Start
        </Button>
      )}
      {s.status === "running" && (
        <Button loading={busy === "pause"} onClick={() => run("pause", () => api.pauseSession(s.id))} aria-label={`Pause session ${s.id}`}>
          <Pause className="h-4 w-4" />Pause
        </Button>
      )}
      {s.status === "paused" && (
        <Button variant="success" loading={busy === "resume"} onClick={() => run("resume", () => api.resumeSession(s.id))} aria-label={`Resume session ${s.id}`}>
          <StepForward className="h-4 w-4" />Resume
        </Button>
      )}
      {active && (
        <select aria-label={`Speed for session ${s.id}`} value={s.speed}
          onChange={(e) => run("speed", () => api.setSpeed(s.id, Number(e.target.value)))}
          className="rounded-lg border border-surface-border bg-gray-900 px-2 py-2 text-sm">
          {[...new Set([...SPEEDS, s.speed])].sort((a, b) => a - b).map((v) => <option key={v} value={v}>x{v}</option>)}
        </select>
      )}
      {(active || s.status === "created") && (
        <Button variant="danger" loading={busy === "stop"} aria-label={`Stop session ${s.id}`}
          onClick={() => (active ? setConfirmStop(true) : run("stop", () => api.stopSession(s.id)))}>
          <Square className="h-4 w-4" />Stop
        </Button>
      )}
      {active && <Link to={`/live/${s.id}`} className="inline-flex items-center gap-1 text-sm text-accent hover:underline"><Radio className="h-4 w-4" />Live</Link>}
      {error && <span role="alert" className="text-xs text-red-300">{error.message}</span>}
      <ConfirmDialog open={confirmStop} danger title="Stop the active match?" confirmLabel="Stop match"
        message={<>Session #{s.id} will end immediately without a winner. Statistics collected so far are saved and marked as <b>stopped</b>.</>}
        onCancel={() => setConfirmStop(false)}
        onConfirm={() => { setConfirmStop(false); void run("stop", () => api.stopSession(s.id)); }} />
    </div>
  );
}

function CreateSession({ players, onCreated }: { players: Player[]; onCreated: (id: number) => void }) {
  const meta = useMeta();
  const [form, setForm] = useState({ name: "Test session", environment: "mock", scenario: "balanced", game_mode: "standard",
    seed: "", speed: "20", minutes: "60" });
  const [rows, setRows] = useState<Record<number, Row>>({});
  const [error, setError] = useState<ApiError | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setRows(Object.fromEntries(players.map((p) => [p.id, { include: p.status !== "offline", team: p.team, hero: p.hero, role: p.role }])));
  }, [players]);

  const included = players.filter((p) => rows[p.id]?.include);
  const counts = { radiant: included.filter((p) => rows[p.id].team === "radiant").length, dire: included.filter((p) => rows[p.id].team === "dire").length };
  const env = meta?.environments.find((e) => e.name === form.environment);

  const submit = async () => {
    setSaving(true);
    setError(null);
    const body: SessionCreate = {
      name: form.name, environment: form.environment, scenario: form.scenario, game_mode: form.game_mode,
      seed: form.seed ? Number(form.seed) : null, speed: Number(form.speed), max_game_seconds: Number(form.minutes) * 60,
      participants: included.map((p) => ({ player_id: p.id, team: rows[p.id].team, hero: rows[p.id].hero, role: rows[p.id].role })),
    };
    try {
      const s = await api.createSession(body);
      onCreated(s.id);
    } catch (e) {
      setError(e as ApiError);
    } finally {
      setSaving(false);
    }
  };

  const setRow = (id: number, patch: Partial<Row>) => setRows({ ...rows, [id]: { ...rows[id], ...patch } });

  return (
    <Card title="Create test session" icon={<Plus className="h-4 w-4" />}>
      <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-7">
        <TextInput label="Name" value={form.name} onChange={(v) => setForm({ ...form, name: v })} testId="session-name" />
        <Select label="Environment" value={form.environment} onChange={(v) => setForm({ ...form, environment: v })} testId="session-environment"
          options={(meta?.environments ?? [{ name: "mock", title: "Local simulator", available: true }]).map((e) => ({
            value: e.name, label: e.available ? e.title : `${e.title} — unavailable`,
          }))} />
        <Select label="Scenario" value={form.scenario} onChange={(v) => setForm({ ...form, scenario: v })} testId="session-scenario"
          options={(meta?.scenarios ?? ["balanced"]).map((s) => ({ value: s, label: titleCase(s) }))} />
        <Select label="Simulator mode" value={form.game_mode} onChange={(v) => setForm({ ...form, game_mode: v })} testId="session-mode"
          options={(meta?.game_modes ?? ["standard"]).map((s) => ({ value: s, label: titleCase(s) }))} />
        <TextInput label="Seed (empty = random)" type="number" value={form.seed} onChange={(v) => setForm({ ...form, seed: v })} testId="session-seed" />
        <Select label="Speed" value={form.speed} onChange={(v) => setForm({ ...form, speed: v })} testId="session-speed"
          options={SPEEDS.map((s) => ({ value: String(s), label: s === 1 ? "x1 (real time)" : `x${s}` }))} />
        <TextInput label="Time limit (min)" type="number" min={5} max={120} value={form.minutes} onChange={(v) => setForm({ ...form, minutes: v })} />
      </div>
      {env && !env.available && (
        <div className="mt-3 rounded-lg border border-amber-800 bg-amber-950/40 p-3 text-xs text-amber-200">
          <b>{env.title}</b> cannot run matches yet: {env.description}
          <ul className="mt-1 list-disc pl-4">{env.notes.map((n) => <li key={n}>{n}</li>)}</ul>
        </div>
      )}
      <div className="mt-4">
        <div className="mb-2 flex items-center gap-4 text-xs text-gray-400">
          <span>Participants: <b className="text-gray-200">{included.length}/10</b></span>
          <span className={counts.radiant === 5 ? "text-radiant" : "text-amber-300"}>Radiant {counts.radiant}/5</span>
          <span className={counts.dire === 5 ? "text-dire" : "text-amber-300"}>Dire {counts.dire}/5</span>
        </div>
        <Table head={["Use", "Player", "Team", "Hero", "Role", "Status"]} testId="participants-table">
          {players.map((p) => {
            const r = rows[p.id];
            if (!r) return null;
            return (
              <tr key={p.id} className={r.include ? "" : "opacity-50"}>
                <td className="px-3 py-1.5"><input type="checkbox" aria-label={`Include ${p.name}`} checked={r.include} disabled={p.status === "offline"}
                  onChange={(e) => setRow(p.id, { include: e.target.checked })} className="accent-amber-500" /></td>
                <td className="px-3 py-1.5 font-medium">{p.name}</td>
                <td className="px-3 py-1.5">
                  <select aria-label={`Team for ${p.name}`} value={r.team} onChange={(e) => setRow(p.id, { team: e.target.value as TeamName })}
                    className="rounded border border-surface-border bg-gray-900 px-1 py-1 text-sm">
                    <option value="radiant">Radiant</option><option value="dire">Dire</option>
                  </select>
                </td>
                <td className="px-3 py-1.5">
                  <select aria-label={`Hero for ${p.name}`} value={r.hero} onChange={(e) => setRow(p.id, { hero: e.target.value })}
                    className="rounded border border-surface-border bg-gray-900 px-1 py-1 text-sm">
                    {(meta?.heroes ?? [{ key: r.hero, name: r.hero }]).map((h) => <option key={h.key} value={h.key}>{h.name}</option>)}
                  </select>
                </td>
                <td className="px-3 py-1.5">
                  <select aria-label={`Role for ${p.name}`} value={r.role} onChange={(e) => setRow(p.id, { role: e.target.value })}
                    className="rounded border border-surface-border bg-gray-900 px-1 py-1 text-sm">
                    {(meta?.roles ?? [r.role]).map((x) => <option key={x} value={x}>{titleCase(x)}</option>)}
                  </select>
                </td>
                <td className="px-3 py-1.5"><StatusBadge status={p.status} /></td>
              </tr>
            );
          })}
        </Table>
      </div>
      <div className="mt-4 flex items-center gap-3">
        <Button variant="primary" loading={saving} onClick={submit} data-testid="create-session"><Plus className="h-4 w-4" />Create session</Button>
        <ErrorBanner error={error} />
      </div>
    </Card>
  );
}

export default function MatchControl() {
  const navigate = useNavigate();
  const players = useAsync(() => api.players(), []);
  const [page, setPage] = useState(1);
  const sessions = useAsync(() => api.sessions({ page, page_size: 10 }), [page]);
  const [created, setCreated] = useState<number | null>(null);
  useLiveEvent(["session_started", "session_paused", "session_resumed", "session_finished", "session_created"], () => void sessions.reload());
  useLiveEvent(["player_updated"], () => void players.reload());

  return (
    <div>
      <PageHeader title="Match Control" subtitle="Create sessions, assign participants and control the simulator." />
      <ErrorBanner error={players.error ?? sessions.error} />
      {!players.data ? <Spinner /> : (
        <CreateSession players={players.data} onCreated={(id) => { setCreated(id); setPage(1); void sessions.reload(); }} />
      )}
      {created && (
        <p className="mt-3 text-sm text-emerald-300" role="status">
          Session #{created} created. Start it below, then <button type="button" className="underline" onClick={() => navigate(`/live/${created}`)}>open the live view</button>.
        </p>
      )}
      <Card title="Sessions" className="mt-6">
        {!sessions.data ? <Spinner /> : sessions.data.items.length === 0 ? <Empty>No sessions yet.</Empty> : (
          <>
            <Table head={["ID", "Name", "Status", "Scenario", "Mode", "Seed", "Game time", "Score", "Actions"]} testId="sessions-table">
              {sessions.data.items.map((s) => (
                <tr key={s.id} data-testid={`session-row-${s.id}`}>
                  <td className="px-3 py-2 font-mono">#{s.id}</td>
                  <td className="px-3 py-2">{s.name}</td>
                  <td className="px-3 py-2"><StatusBadge status={s.status} /></td>
                  <td className="px-3 py-2">{titleCase(s.scenario)}</td>
                  <td className="px-3 py-2">{titleCase(s.game_mode)}</td>
                  <td className="px-3 py-2 font-mono text-xs">{s.seed}</td>
                  <td className="px-3 py-2 font-mono">{formatGameTime(s.duration_seconds)}</td>
                  <td className="px-3 py-2 font-mono"><span className="text-radiant">{s.radiant_score}</span>:<span className="text-dire">{s.dire_score}</span></td>
                  <td className="px-3 py-2"><SessionActions s={s} onChanged={() => void sessions.reload()} /></td>
                </tr>
              ))}
            </Table>
            <Pagination page={page} pageSize={10} total={sessions.data.total} onPage={setPage} />
          </>
        )}
      </Card>
    </div>
  );
}
