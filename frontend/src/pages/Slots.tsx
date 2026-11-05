import { History, Link2, Link2Off, Pencil } from "lucide-react";
import { useState } from "react";
import { api, ApiError } from "../api/client";
import type { Slot } from "../api/types";
import { Button, Card, Empty, ErrorBanner, Modal, PageHeader, Pagination, Spinner, Table, TeamBadge, TextInput, cx } from "../components/ui";
import { useLiveEvent } from "../hooks/LiveEvents";
import { useAsync } from "../hooks/useAsync";
import { formatDate } from "../lib/format";

const STATUS_STYLE: Record<string, string> = {
  unbound: "bg-gray-800 text-gray-400 border-gray-700",
  steam_not_installed: "bg-red-900/50 text-red-300 border-red-800",
  steam_stopped: "bg-gray-800 text-gray-300 border-gray-600",
  steam_running: "bg-sky-900/60 text-sky-300 border-sky-700",
  dota_running: "bg-emerald-900/60 text-emerald-300 border-emerald-700",
};

function SlotCard({ s, onEdit, onHistory }: { s: Slot; onEdit: () => void; onHistory: () => void }) {
  return (
    <div data-testid={`slot-${s.id}`} className={cx("rounded-xl border bg-surface/80 p-4", s.team === "radiant" ? "border-radiant-dark/60" : "border-dire-dark/60")}>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="text-[11px] uppercase text-gray-500">Слот {s.id}</div>
          <div className="truncate font-semibold">{s.name}</div>
        </div>
        <TeamBadge team={s.team} />
      </div>
      <div className="mt-2"><span className={cx("rounded-full border px-2 py-0.5 text-xs", STATUS_STYLE[s.status])} data-testid={`slot-status-${s.id}`}>{s.status_label}</span></div>
      <div className="mt-2 flex items-center gap-1 text-xs text-gray-400">
        {s.binding === "local_client" ? <><Link2 className="h-3.5 w-3.5 text-accent" />наблюдает локальный клиент</> : <><Link2Off className="h-3.5 w-3.5" />без привязки</>}
      </div>
      {s.observed && (s.observed.steam_pid || s.observed.dota_pid) && (
        <div className="mt-1 font-mono text-[11px] text-gray-500">steam PID {s.observed.steam_pid ?? "—"} · dota PID {s.observed.dota_pid ?? "—"}</div>
      )}
      {s.note && <p className="mt-2 line-clamp-2 text-xs text-gray-400">{s.note}</p>}
      <div className="mt-3 flex justify-end gap-1">
        <Button variant="ghost" onClick={onHistory} aria-label={`История слота ${s.id}`}><History className="h-4 w-4" /></Button>
        <Button variant="ghost" onClick={onEdit} aria-label={`Изменить слот ${s.id}`}><Pencil className="h-4 w-4" /></Button>
      </div>
    </div>
  );
}

function SlotEditor({ slot, onClose, onSaved }: { slot: Slot; onClose: () => void; onSaved: () => void }) {
  const [name, setName] = useState(slot.name);
  const [note, setNote] = useState(slot.note);
  const [bound, setBound] = useState(slot.binding === "local_client");
  const [error, setError] = useState<ApiError | null>(null);
  const [saving, setSaving] = useState(false);
  const save = async () => {
    setSaving(true);
    try {
      await api.updateSlot(slot.id, { name, note, binding: bound ? "local_client" : "none" });
      onSaved();
    } catch (e) {
      setError(e as ApiError);
    } finally {
      setSaving(false);
    }
  };
  return (
    <Modal open title={`Слот ${slot.id}`} onClose={onClose} footer={<>
      <Button onClick={onClose}>Отмена</Button>
      <Button variant="primary" onClick={save} loading={saving} disabled={!name.trim()} data-testid="slot-save">Сохранить</Button>
    </>}>
      <div className="space-y-3">
        <ErrorBanner error={error} />
        <TextInput label="Название" value={name} onChange={setName} testId="slot-name" />
        <label className="block space-y-1 text-xs text-gray-300">
          <span>Заметка</span>
          <textarea value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} rows={3} data-testid="slot-note"
            className="w-full rounded-lg border border-surface-border bg-gray-900 px-2 py-2 text-sm text-gray-100 focus:border-accent focus:outline-none" />
        </label>
        <label className="flex items-start gap-2 text-sm text-gray-300">
          <input type="checkbox" checked={bound} onChange={(e) => setBound(e.target.checked)} className="mt-1 accent-amber-500" data-testid="slot-bind" />
          <span>Наблюдать локальный клиент Steam / Dota 2 этого ПК
            <span className="block text-xs text-gray-500">Только один слот может быть привязан: на одном компьютере работает один клиент Steam. Launcher ничего не запускает и не выполняет вход.</span></span>
        </label>
      </div>
    </Modal>
  );
}

function SlotHistory({ slot, onClose }: { slot: Slot; onClose: () => void }) {
  const [page, setPage] = useState(1);
  const h = useAsync(() => api.slotHistory(slot.id, { page, page_size: 15 }), [slot.id, page]);
  return (
    <Modal open wide title={`История: ${slot.name}`} onClose={onClose}>
      {!h.data ? <Spinner /> : h.data.items.length === 0 ? <Empty>Событий пока нет.</Empty> : (
        <>
          <Table head={["Время", "Событие"]} testId="slot-history">
            {h.data.items.map((e) => <tr key={e.id}><td className="whitespace-nowrap px-3 py-1.5 text-xs text-gray-400">{formatDate(e.ts)}</td><td className="px-3 py-1.5 text-sm">{e.message}</td></tr>)}
          </Table>
          <Pagination page={page} pageSize={15} total={h.data.total} onPage={setPage} />
        </>
      )}
    </Modal>
  );
}

export default function Slots() {
  const slots = useAsync(api.slots, []);
  const [editing, setEditing] = useState<Slot | null>(null);
  const [history, setHistory] = useState<Slot | null>(null);
  useLiveEvent(["slot_updated", "environment_updated"], () => void slots.reload());
  const team = (t: "radiant" | "dire") => (slots.data ?? []).filter((s) => s.team === t);
  return (
    <div>
      <PageHeader title="10 слотов" subtitle="Логические слоты для учёта тестовых окружений. Это не 10 аккаунтов Steam и не 10 клиентов Dota 2." />
      <ErrorBanner error={slots.error} onRetry={slots.reload} />
      {!slots.data && <Spinner />}
      <div className="grid gap-6 xl:grid-cols-2">
        {(["radiant", "dire"] as const).map((t) => (
          <Card key={t} title={<span className={t === "radiant" ? "text-radiant" : "text-dire"}>{t === "radiant" ? "Radiant · слоты 1–5" : "Dire · слоты 6–10"}</span>}>
            <div className="grid gap-4 sm:grid-cols-2" data-testid={`slots-${t}`}>
              {team(t).map((s) => <SlotCard key={s.id} s={s} onEdit={() => setEditing(s)} onHistory={() => setHistory(s)} />)}
            </div>
          </Card>
        ))}
      </div>
      {editing && <SlotEditor slot={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); void slots.reload(); }} />}
      {history && <SlotHistory slot={history} onClose={() => setHistory(null)} />}
    </div>
  );
}
