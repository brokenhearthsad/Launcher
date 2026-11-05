import { RotateCcw, Save, Wand2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api, ApiError } from "../api/client";
import type { AIParams, Player } from "../api/types";
import { Button, Card, ErrorBanner, PageHeader, Select, Slider, Spinner, StatusBadge, TeamBadge, Toggle } from "../components/ui";
import { useHeroName, useMeta } from "../hooks/MetaContext";
import { useAsync } from "../hooks/useAsync";
import { titleCase } from "../lib/format";

const PARAMS: { key: keyof Omit<AIParams, "bot_difficulty">; label: string; hint: string }[] = [
  { key: "aggression", label: "Aggression", hint: "Weight of combat actions; willingness to start fights." },
  { key: "farming_priority", label: "Farming Priority", hint: "Weight of last hits, wave clearing and jungle." },
  { key: "team_coordination", label: "Team Coordination", hint: "How strongly team directives (push/defend/group) are followed." },
  { key: "risk_tolerance", label: "Risk Tolerance", hint: "Lower values retreat earlier and avoid tower dives." },
  { key: "objective_priority", label: "Objective Priority", hint: "Weight of attacking/defending towers and Roshan." },
];

const PRESETS: Record<string, Omit<AIParams, "bot_difficulty">> = {
  Balanced: { aggression: 0.5, farming_priority: 0.5, team_coordination: 0.5, risk_tolerance: 0.5, objective_priority: 0.5 },
  Aggressive: { aggression: 0.85, farming_priority: 0.4, team_coordination: 0.6, risk_tolerance: 0.75, objective_priority: 0.6 },
  Farmer: { aggression: 0.3, farming_priority: 0.95, team_coordination: 0.35, risk_tolerance: 0.35, objective_priority: 0.4 },
  "Team player": { aggression: 0.55, farming_priority: 0.35, team_coordination: 0.95, risk_tolerance: 0.5, objective_priority: 0.75 },
};

function pick(p: Player): AIParams {
  return {
    bot_difficulty: p.bot_difficulty, aggression: p.aggression, farming_priority: p.farming_priority,
    team_coordination: p.team_coordination, risk_tolerance: p.risk_tolerance, objective_priority: p.objective_priority,
  };
}

export default function BotConfig() {
  const meta = useMeta();
  const heroName = useHeroName();
  const players = useAsync(() => api.players(), []);
  const [selected, setSelected] = useState<number | null>(null);
  const [draft, setDraft] = useState<AIParams | null>(null);
  const [applyToTeam, setApplyToTeam] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [saved, setSaved] = useState<string | null>(null);

  const player = useMemo(() => players.data?.find((p) => p.id === selected) ?? null, [players.data, selected]);
  useEffect(() => {
    if (!selected && players.data?.length) setSelected(players.data[0].id);
  }, [players.data, selected]);
  useEffect(() => {
    if (player) setDraft(pick(player));
  }, [player]);

  const dirty = player && draft && JSON.stringify(pick(player)) !== JSON.stringify(draft);

  const save = async () => {
    if (!player || !draft) return;
    setSaving(true);
    setError(null);
    try {
      const targets = applyToTeam ? (players.data ?? []).filter((p) => p.team === player.team) : [player];
      for (const t of targets) await api.updatePlayer(t.id, draft);
      setSaved(`Saved for ${targets.map((t) => t.name).join(", ")}. Takes effect from the next session start.`);
      await players.reload();
    } catch (e) {
      setError(e as ApiError);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      <PageHeader title="Bot Configuration" subtitle="Per-bot utility-AI weights. Values are snapshotted into each session when it starts." />
      <ErrorBanner error={players.error ?? error} />
      {!players.data && <Spinner />}
      {players.data && (
        <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
          <Card title="Participants">
            <ul className="space-y-1" data-testid="bot-list">
              {players.data.map((p) => (
                <li key={p.id}>
                  <button type="button" onClick={() => { setSelected(p.id); setSaved(null); }}
                    className={`flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm ${selected === p.id ? "bg-accent/15 text-accent" : "hover:bg-surface-raised"}`}>
                    <span><span className="font-medium">{p.name}</span><span className="block text-xs text-gray-500">{heroName(p.hero)} · {titleCase(p.role)}</span></span>
                    <TeamBadge team={p.team} />
                  </button>
                </li>
              ))}
            </ul>
          </Card>
          {player && draft && (
            <Card title={`${player.name} — ${heroName(player.hero)}`} actions={<StatusBadge status={player.status} />}>
              <div className="grid gap-6 md:grid-cols-2">
                <div className="space-y-5">
                  <Select label="AI Difficulty" testId="difficulty-select" value={draft.bot_difficulty}
                    onChange={(v) => setDraft({ ...draft, bot_difficulty: v })}
                    options={(meta?.difficulties ?? ["easy", "medium", "hard", "expert"]).map((d) => ({ value: d, label: titleCase(d) }))} />
                  <p className="text-xs text-gray-500">Difficulty controls reaction time, decision noise, last-hit accuracy and how reliably abilities are used.</p>
                  {PARAMS.map((p) => (
                    <Slider key={p.key} label={p.label} hint={p.hint} value={draft[p.key]}
                      onChange={(v) => setDraft({ ...draft, [p.key]: v })} />
                  ))}
                </div>
                <div className="space-y-4">
                  <div>
                    <div className="mb-2 text-xs uppercase tracking-wide text-gray-400">Presets</div>
                    <div className="flex flex-wrap gap-2">
                      {Object.entries(PRESETS).map(([name, v]) => (
                        <Button key={name} variant="ghost" onClick={() => setDraft({ ...draft, ...v })}><Wand2 className="h-4 w-4" />{name}</Button>
                      ))}
                    </div>
                  </div>
                  <Toggle label={`Apply to whole ${player.team} team`} checked={applyToTeam} onChange={setApplyToTeam} />
                  <div className="flex gap-2">
                    <Button variant="primary" loading={saving} disabled={!dirty && !applyToTeam} onClick={save}><Save className="h-4 w-4" />Save</Button>
                    <Button disabled={!dirty} onClick={() => setDraft(pick(player))}><RotateCcw className="h-4 w-4" />Reset</Button>
                  </div>
                  {saved && <p className="text-sm text-emerald-300" role="status">{saved}</p>}
                </div>
              </div>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
