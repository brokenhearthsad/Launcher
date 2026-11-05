import { Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { api, ApiError } from "../api/client";
import type { Player, PlayerCreate, TeamName } from "../api/types";
import {
  Bar, Button, Card, ConfirmDialog, ErrorBanner, Modal, PageHeader, Select, Spinner, StatusBadge, TextInput, cx,
} from "../components/ui";
import { useLiveEvent } from "../hooks/LiveEvents";
import { useHeroName, useMeta } from "../hooks/MetaContext";
import { useAsync } from "../hooks/useAsync";
import { titleCase } from "../lib/format";

const LOCKED = ["running", "paused"];

export function PlayerCard({ p, onEdit }: { p: Player; onEdit: () => void }) {
  const heroName = useHeroName();
  const color = p.team === "radiant" ? "bg-radiant" : "bg-dire";
  return (
    <div data-testid={`player-card-${p.id}`}
      className={cx("rounded-xl border bg-surface/80 p-4 transition hover:border-gray-500",
        p.team === "radiant" ? "border-radiant-dark/60" : "border-dire-dark/60")}>
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="font-semibold">{p.name}</div>
          <div className="text-sm text-gray-400">{heroName(p.hero)} · {titleCase(p.role)}</div>
        </div>
        <StatusBadge status={p.status} />
      </div>
      <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-[11px] text-gray-400">
        {([["Aggression", p.aggression], ["Farming", p.farming_priority], ["Coordination", p.team_coordination],
          ["Risk", p.risk_tolerance], ["Objectives", p.objective_priority]] as const).map(([l, v]) => (
          <div key={l}>
            <div className="flex justify-between"><span>{l}</span><span>{Math.round(v * 100)}</span></div>
            <Bar value={v} max={1} color={color} />
          </div>
        ))}
        <div>
          <div>Difficulty</div>
          <div className="font-medium text-gray-200">{titleCase(p.bot_difficulty)}</div>
        </div>
      </div>
      <div className="mt-3 flex justify-end">
        <Button variant="ghost" onClick={onEdit} aria-label={`Edit ${p.name}`}><Pencil className="h-4 w-4" /> Edit</Button>
      </div>
    </div>
  );
}

type Draft = PlayerCreate & { id?: number };

function blank(team: TeamName): Draft {
  return {
    name: "", team, slot: 1, role: "carry", hero: "juggernaut", bot_difficulty: "hard", status: "ready",
    aggression: 0.5, farming_priority: 0.5, team_coordination: 0.5, risk_tolerance: 0.5, objective_priority: 0.5,
  };
}

export function PlayerEditor({ draft, onClose, onSaved }: { draft: Draft; onClose: () => void; onSaved: () => void }) {
  const meta = useMeta();
  const [d, setD] = useState<Draft>(draft);
  const [error, setError] = useState<ApiError | null>(null);
  const [saving, setSaving] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const locked = LOCKED.includes(d.status);
  const set = <K extends keyof Draft>(k: K, v: Draft[K]) => setD({ ...d, [k]: v });

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      const { id, created_at: _c, updated_at: _u, ...body } = d as Draft & { created_at?: string; updated_at?: string };
      void _c; void _u;
      if (id) {
        const patch: Record<string, unknown> = { ...body };
        if (locked) for (const k of ["team", "role", "hero", "slot", "status"]) delete patch[k];
        await api.updatePlayer(id, patch);
      } else {
        await api.createPlayer(body);
      }
      onSaved();
    } catch (e) {
      setError(e as ApiError);
    } finally {
      setSaving(false);
    }
  };

  const remove = async () => {
    if (!d.id) return;
    try {
      await api.deletePlayer(d.id);
      onSaved();
    } catch (e) {
      setError(e as ApiError);
      setConfirmDelete(false);
    }
  };

  return (
    <Modal open title={d.id ? `Edit ${draft.name}` : "Add participant"} onClose={onClose} footer={
      <>
        {d.id && <Button variant="danger" className="mr-auto" disabled={locked} onClick={() => setConfirmDelete(true)}><Trash2 className="h-4 w-4" />Delete</Button>}
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="primary" loading={saving} onClick={save} disabled={!d.name.trim()}>Save</Button>
      </>
    }>
      <div className="space-y-3">
        <ErrorBanner error={error} />
        {locked && <p className="text-xs text-amber-300">This participant is in an active session: team, role, hero and status are locked until it ends.</p>}
        <TextInput label="Name" value={d.name} onChange={(v) => set("name", v)} testId="player-name" />
        <div className="grid grid-cols-2 gap-3">
          <Select label="Team" value={d.team} disabled={locked} onChange={(v) => set("team", v as TeamName)}
            options={[{ value: "radiant", label: "Radiant" }, { value: "dire", label: "Dire" }]} />
          <Select label="Role" value={d.role} disabled={locked} onChange={(v) => set("role", v)} testId="player-role"
            options={(meta?.roles ?? [d.role]).map((r) => ({ value: r, label: titleCase(r) }))} />
          <Select label="Hero" value={d.hero} disabled={locked} onChange={(v) => set("hero", v)} testId="player-hero"
            options={(meta?.heroes ?? []).map((h) => ({ value: h.key, label: `${h.name} (${h.roles.map(titleCase).join(", ")})` }))} />
          <Select label="Difficulty" value={d.bot_difficulty} onChange={(v) => set("bot_difficulty", v)} testId="player-difficulty"
            options={(meta?.difficulties ?? [d.bot_difficulty]).map((x) => ({ value: x, label: titleCase(x) }))} />
          <Select label="Status" value={locked ? d.status : d.status === "offline" ? "offline" : "ready"} disabled={locked}
            onChange={(v) => set("status", v as Draft["status"])}
            options={locked ? [{ value: d.status, label: titleCase(d.status) }] : [{ value: "ready", label: "Ready" }, { value: "offline", label: "Offline" }]} />
          <TextInput label="Slot (1-5)" type="number" min={1} max={5} value={d.slot} onChange={(v) => set("slot", Math.max(1, Math.min(5, Number(v) || 1)))} />
        </div>
        <p className="text-xs text-gray-500">AI behaviour parameters are configured on the Bot Configuration page.</p>
      </div>
      <ConfirmDialog open={confirmDelete} danger title="Delete participant" confirmLabel="Delete"
        message={`Delete ${d.name}? Their past statistics are removed too.`} onCancel={() => setConfirmDelete(false)} onConfirm={remove} />
    </Modal>
  );
}

export default function Players() {
  const players = useAsync(() => api.players(), []);
  const [editing, setEditing] = useState<Draft | null>(null);
  useLiveEvent(["player_updated"], () => void players.reload());

  const team = (t: TeamName) => (players.data ?? []).filter((p) => p.team === t);
  return (
    <div>
      <PageHeader title="Players" subtitle="Ten test participants split into Radiant and Dire. Not linked to any Steam account."
        actions={<Button variant="primary" onClick={() => setEditing(blank("radiant"))}><Plus className="h-4 w-4" />Add participant</Button>} />
      <ErrorBanner error={players.error} onRetry={players.reload} />
      {players.loading && !players.data && <Spinner />}
      <div className="grid gap-6 xl:grid-cols-2">
        {(["radiant", "dire"] as TeamName[]).map((t) => (
          <Card key={t} title={<span className={t === "radiant" ? "text-radiant" : "text-dire"}>{t} ({team(t).length})</span>}>
            <div className="grid gap-4 sm:grid-cols-2" data-testid={`team-${t}`}>
              {team(t).map((p) => <PlayerCard key={p.id} p={p} onEdit={() => setEditing({ ...p })} />)}
            </div>
          </Card>
        ))}
      </div>
      {editing && <PlayerEditor draft={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); void players.reload(); }} />}
    </div>
  );
}
