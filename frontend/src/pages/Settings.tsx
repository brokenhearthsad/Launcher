import { Database, Save, Server, SlidersHorizontal } from "lucide-react";
import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import type { RuntimeSettings } from "../api/types";
import { Button, Card, ConfirmDialog, ErrorBanner, PageHeader, Select, Spinner, TextInput, Toggle } from "../components/ui";
import { useAsync } from "../hooks/useAsync";
import { useUiSettings } from "../hooks/UiSettings";
import { formatBytes } from "../lib/format";

const LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR"].map((l) => ({ value: l, label: l }));

export default function SettingsPage() {
  const settings = useAsync(api.settings, []);
  const ui = useUiSettings();
  const [draft, setDraft] = useState<RuntimeSettings | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [purgeDays, setPurgeDays] = useState("7");
  const [confirmPurge, setConfirmPurge] = useState(false);

  useEffect(() => {
    if (settings.data) setDraft(settings.data.runtime);
  }, [settings.data]);

  const num = (k: keyof RuntimeSettings) => (v: string) => draft && setDraft({ ...draft, [k]: Number(v) });

  const save = async () => {
    if (!draft) return;
    setSaving(true);
    setError(null);
    try {
      await api.updateSettings(draft);
      await settings.reload();
      await ui.reload();
      setMessage("Settings saved. Log levels apply immediately; simulator settings apply to new sessions.");
    } catch (e) {
      setError(e as ApiError);
    } finally {
      setSaving(false);
    }
  };

  const action = async (fn: () => Promise<string>) => {
    setError(null);
    try {
      setMessage(await fn());
      await settings.reload();
    } catch (e) {
      setError(e as ApiError);
    }
  };

  if (!settings.data || !draft) return <div><PageHeader title="Settings" /><ErrorBanner error={settings.error} /><Spinner /></div>;
  const s = settings.data;
  return (
    <div>
      <PageHeader title="Settings" subtitle="Runtime configuration stored in the local database." actions={
        <Button variant="primary" loading={saving} onClick={save} data-testid="save-settings"><Save className="h-4 w-4" />Save settings</Button>} />
      <ErrorBanner error={error} />
      {message && <p role="status" className="mb-4 text-sm text-emerald-300">{message}</p>}
      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Backend" icon={<Server className="h-4 w-4" />}>
          <dl className="grid grid-cols-2 gap-2 text-sm">
            <dt className="text-gray-400">Version</dt><dd>{s.backend.version}</dd>
            <dt className="text-gray-400">Address</dt><dd className="font-mono">http://{s.backend.host}:{s.backend.port}</dd>
            <dt className="text-gray-400">API docs</dt><dd><a className="text-accent underline" href={`http://${s.backend.host}:${s.backend.port}/docs`} target="_blank" rel="noreferrer">/docs</a></dd>
            <dt className="text-gray-400">Rate limit</dt><dd>{s.backend.api_rate_limit_per_minute} req/min</dd>
            <dt className="text-gray-400">Log directory</dt><dd className="truncate font-mono text-xs">{s.backend.log_dir}</dd>
          </dl>
          <div className="mt-4">
            <TextInput label="Max concurrent sessions" type="number" min={1} max={8} value={draft.max_concurrent_sessions} onChange={num("max_concurrent_sessions")} />
          </div>
          <p className="mt-2 text-xs text-gray-500">Host, port and CORS are set in backend/.env (restart required).</p>
        </Card>
        <Card title="Simulator" icon={<SlidersHorizontal className="h-4 w-4" />}>
          <div className="grid grid-cols-2 gap-3">
            <TextInput label="Default speed (game s / real s)" type="number" min={1} max={1000} value={draft.default_speed} onChange={num("default_speed")} testId="default-speed" />
            <TextInput label="Default time limit (s)" type="number" min={300} max={7200} value={draft.max_game_seconds} onChange={num("max_game_seconds")} />
            <TextInput label="Tick (game seconds)" type="number" min={0.25} max={1} value={draft.tick_seconds} onChange={num("tick_seconds")} />
            <TextInput label="Snapshot interval (s)" type="number" min={10} max={600} value={draft.snapshot_interval} onChange={num("snapshot_interval")} />
          </div>
          <div className="mt-3">
            <Toggle label="Store ability-cast and item-use events" checked={draft.persist_ability_events}
              onChange={(v) => setDraft({ ...draft, persist_ability_events: v })} />
          </div>
        </Card>
        <Card title="Interface updates">
          <div className="grid grid-cols-2 gap-3">
            <TextInput label="WebSocket publish rate (Hz)" type="number" min={0.5} max={20} value={draft.ws_publish_hz} onChange={num("ws_publish_hz")} />
            <TextInput label="Page refresh interval (s)" type="number" min={1} max={120} value={draft.ui_refresh_seconds} onChange={num("ui_refresh_seconds")} />
          </div>
          <p className="mt-2 text-xs text-gray-500">Live views use WebSocket pushes; the refresh interval applies to polling pages such as the dashboard and logs.</p>
        </Card>
        <Card title="Logging">
          <div className="grid grid-cols-2 gap-3">
            <Select label="Application log level" value={draft.log_level} onChange={(v) => setDraft({ ...draft, log_level: v })} options={LEVELS} testId="log-level-setting" />
            <Select label="Database log level" value={draft.db_log_level} onChange={(v) => setDraft({ ...draft, db_log_level: v })} options={LEVELS} />
          </div>
        </Card>
        <Card title="Database" icon={<Database className="h-4 w-4" />} className="lg:col-span-2">
          <dl className="grid grid-cols-2 gap-2 text-sm md:grid-cols-4">
            <dt className="text-gray-400">Engine</dt><dd>{s.database.dialect}</dd>
            <dt className="text-gray-400">Size</dt><dd>{formatBytes(s.database.size_bytes)}</dd>
            <dt className="text-gray-400">File</dt><dd className="col-span-3 truncate font-mono text-xs md:col-span-3">{s.database.path ?? s.database.url}</dd>
          </dl>
          <div className="mt-4 flex flex-wrap items-end gap-3">
            <Button onClick={() => action(async () => { const r = await api.vacuum(); return `Vacuum done: ${formatBytes(r.size_before)} → ${formatBytes(r.size_after)}`; })}>Vacuum database</Button>
            <div className="w-40"><TextInput label="Purge logs older than (days)" type="number" min={0} value={purgeDays} onChange={setPurgeDays} /></div>
            <Button variant="danger" onClick={() => setConfirmPurge(true)}>Purge logs</Button>
          </div>
        </Card>
      </div>
      <ConfirmDialog open={confirmPurge} danger title="Purge logs" confirmLabel="Purge"
        message={`Delete all log entries older than ${purgeDays} day(s)?`} onCancel={() => setConfirmPurge(false)}
        onConfirm={() => { setConfirmPurge(false); void action(async () => `Deleted ${(await api.purgeLogs(Number(purgeDays))).deleted} log entries.`); }} />
    </div>
  );
}
