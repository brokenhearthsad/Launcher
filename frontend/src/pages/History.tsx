import { Eye } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { HistoryItem } from "../api/types";
import { Button, Card, Empty, ErrorBanner, Modal, PageHeader, Pagination, Select, Spinner, StatusBadge, Table, TeamBadge } from "../components/ui";
import { useLiveEvent } from "../hooks/LiveEvents";
import { useHeroName } from "../hooks/MetaContext";
import { useAsync } from "../hooks/useAsync";
import { formatDate, formatGameTime, formatNumber, titleCase } from "../lib/format";

function Details({ item, onClose }: { item: HistoryItem; onClose: () => void }) {
  const heroName = useHeroName();
  const stats = useAsync(() => api.statistics(item.id), [item.id]);
  const [evPage, setEvPage] = useState(1);
  const [evType, setEvType] = useState("");
  const events = useAsync(() => api.events(item.id, { page: evPage, page_size: 25, event_type: evType || undefined }), [item.id, evPage, evType]);
  return (
    <Modal open wide title={`Session #${item.id} — ${item.name}`} onClose={onClose}>
      <div className="mb-4 flex flex-wrap gap-4 text-sm text-gray-300">
        <StatusBadge status={item.status} />
        <span>Winner: {item.winner ? <TeamBadge team={item.winner} /> : "—"}</span>
        <span>{titleCase(item.win_condition ?? "")}</span>
        <span>Duration {formatGameTime(item.duration_seconds)}</span>
        <span>Seed {item.seed}</span>
        <Link className="text-accent underline" to={`/live/${item.id}`}>Open in Live view</Link>
      </div>
      <ErrorBanner error={stats.error} />
      {!stats.data ? <Spinner /> : stats.data.players.length === 0 ? <Empty>No statistics were recorded.</Empty> : (
        <Table head={["Player", "Team", "Hero", "Lvl", "K/D/A", "LH/DN", "GPM", "XPM", "Net worth", "Hero dmg", "Tower dmg", "Items"]} testId="details-table">
          {stats.data.players.map((p) => (
            <tr key={p.player_id}>
              <td className="px-3 py-1.5">{p.player_name}</td><td className="px-3 py-1.5"><TeamBadge team={p.team} /></td>
              <td className="px-3 py-1.5">{heroName(p.hero)}</td><td className="px-3 py-1.5">{p.level}</td>
              <td className="px-3 py-1.5 font-mono">{p.kills}/{p.deaths}/{p.assists}</td><td className="px-3 py-1.5 font-mono">{p.last_hits}/{p.denies}</td>
              <td className="px-3 py-1.5">{formatNumber(p.gpm)}</td><td className="px-3 py-1.5">{formatNumber(p.xpm)}</td>
              <td className="px-3 py-1.5">{formatNumber(p.net_worth)}</td><td className="px-3 py-1.5">{formatNumber(p.hero_damage)}</td>
              <td className="px-3 py-1.5">{formatNumber(p.tower_damage)}</td><td className="px-3 py-1.5 text-xs text-gray-400">{p.items.join(", ")}</td>
            </tr>
          ))}
        </Table>
      )}
      <div className="mt-6">
        <div className="mb-2 flex items-center justify-between">
          <h4 className="text-sm font-semibold text-gray-300">Events</h4>
          <div className="w-48"><Select value={evType} onChange={(v) => { setEvType(v); setEvPage(1); }}
            options={[{ value: "", label: "All types" }, ...["hero_killed", "tower_destroyed", "item_purchased", "level_up", "roshan_killed", "ability_cast", "game_end"].map((t) => ({ value: t, label: titleCase(t) }))]} /></div>
        </div>
        {events.data && (
          <>
            <Table head={["Time", "Type", "Player", "Data"]}>
              {events.data.items.map((e) => (
                <tr key={e.id}><td className="px-3 py-1 font-mono text-xs">{formatGameTime(e.game_time)}</td><td className="px-3 py-1 text-xs">{titleCase(e.event_type)}</td>
                  <td className="px-3 py-1 text-xs">{e.player_id ?? "—"}</td><td className="truncate px-3 py-1 font-mono text-[11px] text-gray-400">{JSON.stringify(e.event_data)}</td></tr>
              ))}
            </Table>
            <Pagination page={evPage} pageSize={25} total={events.data.total} onPage={setEvPage} />
          </>
        )}
      </div>
    </Modal>
  );
}

export default function History() {
  const [page, setPage] = useState(1);
  const [winner, setWinner] = useState("");
  const [status, setStatus] = useState("");
  const history = useAsync(() => api.history({ page, page_size: 15, winner: winner || undefined, status: status || undefined }), [page, winner, status]);
  const [open, setOpen] = useState<HistoryItem | null>(null);
  useLiveEvent(["session_finished"], () => void history.reload());

  return (
    <div>
      <PageHeader title="Match History" subtitle="Completed, stopped and failed sessions stored in SQLite." />
      <Card title="Sessions" actions={
        <div className="flex gap-2">
          <div className="w-40"><Select value={winner} onChange={(v) => { setWinner(v); setPage(1); }} testId="history-winner"
            options={[{ value: "", label: "Any winner" }, { value: "radiant", label: "Radiant" }, { value: "dire", label: "Dire" }, { value: "none", label: "No winner" }]} /></div>
          <div className="w-40"><Select value={status} onChange={(v) => { setStatus(v); setPage(1); }}
            options={[{ value: "", label: "Any status" }, { value: "finished", label: "Finished" }, { value: "stopped", label: "Stopped" }, { value: "error", label: "Error" }]} /></div>
        </div>
      }>
        <ErrorBanner error={history.error} onRetry={history.reload} />
        {!history.data ? <Spinner /> : history.data.items.length === 0 ? <Empty>No completed sessions yet.</Empty> : (
          <>
            <Table head={["ID", "Date", "Name", "Status", "Winner", "Score", "Duration", "Events", ""]} testId="history-table">
              {history.data.items.map((h) => (
                <tr key={h.id}>
                  <td className="px-3 py-2 font-mono">#{h.id}</td>
                  <td className="px-3 py-2 text-xs text-gray-400">{formatDate(h.finished_at ?? h.created_at)}</td>
                  <td className="px-3 py-2">{h.name}</td>
                  <td className="px-3 py-2"><StatusBadge status={h.status} /></td>
                  <td className="px-3 py-2"><TeamBadge team={h.winner} /></td>
                  <td className="px-3 py-2 font-mono"><span className="text-radiant">{h.radiant_score}</span>:<span className="text-dire">{h.dire_score}</span></td>
                  <td className="px-3 py-2 font-mono">{formatGameTime(h.duration_seconds)}</td>
                  <td className="px-3 py-2">{formatNumber(h.events_count)}</td>
                  <td className="px-3 py-2"><Button variant="ghost" onClick={() => setOpen(h)} aria-label={`Details for session ${h.id}`}><Eye className="h-4 w-4" />Details</Button></td>
                </tr>
              ))}
            </Table>
            <Pagination page={page} pageSize={15} total={history.data.total} onPage={setPage} />
          </>
        )}
      </Card>
      {open && <Details item={open} onClose={() => setOpen(null)} />}
    </div>
  );
}
