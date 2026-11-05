import { CircleCheck, CircleX, RefreshCw } from "lucide-react";
import { useState, type ReactNode } from "react";
import { api, ApiError } from "../api/client";
import type { ProcessState } from "../api/types";
import { Button, Card, Empty, ErrorBanner, PageHeader, Spinner, Table, cx } from "../components/ui";
import { fmt, formatDuration, NO_DATA } from "../components/metrics";
import { useLiveEvent } from "../hooks/LiveEvents";
import { useAsync } from "../hooks/useAsync";
import { useMonitoring } from "../hooks/Monitoring";
import { formatDate } from "../lib/format";

const STATE_LABELS: Record<string, string> = {
  fully_installed: "установлена", update_required: "требуется обновление", update_running: "обновляется",
  downloading: "загрузка", validating: "проверка файлов", files_missing: "нет файлов", update_paused: "обновление на паузе",
};

export function Flag({ ok, yes, no }: { ok: boolean | null | undefined; yes: string; no: string }) {
  if (ok === null || ok === undefined) return <span className="text-gray-500">{NO_DATA}</span>;
  return (
    <span className={cx("inline-flex items-center gap-1", ok ? "text-emerald-300" : "text-gray-400")}>
      {ok ? <CircleCheck className="h-4 w-4" /> : <CircleX className="h-4 w-4" />}{ok ? yes : no}
    </span>
  );
}

function ProcessCard({ title, p }: { title: string; p: ProcessState }) {
  return (
    <Card title={title}>
      <div className="mb-3"><Flag ok={p.running} yes="Запущен" no="Остановлен" /></div>
      {p.running ? (
        <dl className="grid grid-cols-2 gap-2 text-sm" data-testid={`proc-${title}`}>
          <dt className="text-gray-400">PID</dt><dd className="font-mono">{p.pid}</dd>
          <dt className="text-gray-400">Время работы</dt><dd>{formatDuration(p.uptime_seconds)}</dd>
          <dt className="text-gray-400">Запущен</dt><dd>{p.started_at ? new Date(p.started_at * 1000).toLocaleString() : NO_DATA}</dd>
          <dt className="text-gray-400">ОЗУ</dt><dd>{fmt(p.rss_mb, "МБ")}</dd>
          <dt className="text-gray-400">CPU</dt><dd>{fmt(p.cpu_percent, "%", 1)}</dd>
        </dl>
      ) : <p className="text-sm text-gray-500">Процесс не найден. Launcher не запускает и не закрывает игры.</p>}
    </Card>
  );
}

function Row({ k, v }: { k: string; v: ReactNode }) {
  return <><dt className="text-gray-400">{k}</dt><dd className="truncate" title={typeof v === "string" ? v : undefined}>{v}</dd></>;
}

export default function SteamDota() {
  const { environment: env, setEnvironment, error } = useMonitoring();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<ApiError | null>(null);
  const events = useAsync(() => api.events({ page_size: 20 }), []);
  useLiveEvent(["event_created"], () => void events.reload());

  const refresh = async () => {
    setBusy(true);
    try {
      setEnvironment(await api.refreshEnvironment());
      setErr(null);
    } catch (e) {
      setErr(e as ApiError);
    } finally {
      setBusy(false);
    }
  };

  if (!env) return <div><PageHeader title="Steam и Dota 2" /><ErrorBanner error={error} />{!error && <Spinner />}</div>;
  const { steam, dota } = env;
  return (
    <div>
      <PageHeader title="Steam и Dota 2" subtitle="Только наблюдение: файлы Steam, реестр (путь и признак входа) и список процессов."
        actions={<Button onClick={refresh} loading={busy}><RefreshCw className="h-4 w-4" />Проверить сейчас</Button>} />
      <ErrorBanner error={err ?? error} />
      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Steam">
          <div className="mb-3"><Flag ok={steam.installed} yes="Установлен" no="Не найден" /></div>
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm" data-testid="steam-info">
            <Row k="Папка" v={steam.path ?? NO_DATA} />
            <Row k="Источник" v={steam.source === "registry" ? "реестр Windows" : steam.source === "config" ? "backend\\.env" : steam.source === "default" ? "стандартная папка" : NO_DATA} />
            <Row k="Вход в аккаунт" v={<Flag ok={steam.signed_in} yes="выполнен" no="не выполнен" />} />
            <Row k="Библиотеки" v={steam.libraries?.length ? steam.libraries.join("; ") : NO_DATA} />
          </dl>
          {steam.error && <p className="mt-2 text-xs text-amber-300">{steam.error}</p>}
        </Card>
        <Card title="Dota 2">
          <div className="mb-3"><Flag ok={dota.installed} yes="Установлена" no="Не найдена" /></div>
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm" data-testid="dota-info">
            <Row k="Папка" v={dota.path ?? NO_DATA} />
            <Row k="dota2.exe" v={dota.installed ? <Flag ok={dota.exe_exists} yes="найден" no="не найден" /> : NO_DATA} />
            <Row k="Состояние" v={dota.state?.length ? dota.state.map((s) => STATE_LABELS[s] ?? s).join(", ") : NO_DATA} />
            <Row k="Сборка" v={dota.buildid ?? NO_DATA} />
            <Row k="Размер" v={fmt(dota.size_gb, "ГБ", 1)} />
            <Row k="Обновлена" v={dota.last_updated ? formatDate(dota.last_updated) : NO_DATA} />
          </dl>
          {dota.error && <p className="mt-2 text-xs text-amber-300">{dota.error}</p>}
        </Card>
        <ProcessCard title="steam.exe" p={steam.process} />
        <ProcessCard title="dota2.exe" p={dota.process} />
      </div>
      <Card title="События" className="mt-6">
        {!events.data ? <Spinner /> : events.data.items.length === 0 ? <Empty>Событий пока нет: здесь появятся запуски и остановки Steam и Dota 2.</Empty> : (
          <Table head={["Время", "Источник", "Событие"]} testId="events-table">
            {events.data.items.map((e) => (
              <tr key={e.id}><td className="whitespace-nowrap px-3 py-1.5 text-xs text-gray-400">{formatDate(e.ts)}</td>
                <td className="px-3 py-1.5 text-xs">{e.source}</td><td className="px-3 py-1.5 text-sm">{e.message}</td></tr>
            ))}
          </Table>
        )}
      </Card>
      <p className="mt-4 text-xs text-gray-500">Последняя проверка: {env.checked_at ? new Date(env.checked_at * 1000).toLocaleTimeString() : NO_DATA} ·
        реестр Windows: {env.registry_available ? "доступен" : "недоступен"}</p>
    </div>
  );
}
