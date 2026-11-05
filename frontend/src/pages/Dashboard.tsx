import { AlertTriangle, Clock, Cpu, Database, HardDrive, MemoryStick, Server } from "lucide-react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { Card, Empty, ErrorBanner, PageHeader, Spinner, StatCard, Table, cx } from "../components/ui";
import { useLive } from "../hooks/LiveEvents";
import { useAsync } from "../hooks/useAsync";
import { useUiSettings } from "../hooks/UiSettings";
import { formatDate } from "../lib/format";

// Targets agreed for the Launcher itself (see PROJECT_AUDIT.md).
const RAM_TARGET_MB = 150;
const CPU_TARGET = 1;

export function formatUptime(seconds: number): string {
  const s = Math.floor(seconds);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  return h ? `${h} ч ${m} мин` : m ? `${m} мин ${s % 60} с` : `${s} с`;
}

export default function Dashboard() {
  const { refreshMs } = useUiSettings();
  const { state: wsState } = useLive();
  const health = useAsync(api.health, [], refreshMs);
  const proc = useAsync(api.process, [], refreshMs);
  const settings = useAsync(api.settings, []);
  const problems = useAsync(() => api.logs({ level: ["WARNING", "ERROR", "CRITICAL"], page_size: 5 }), [], refreshMs);

  const h = health.data;
  const p = proc.data;
  return (
    <div>
      <PageHeader title="Обзор" subtitle="Состояние Launcher. Мониторинг Steam, Dota 2 и ресурсов ПК добавляется на следующих этапах." />
      <ErrorBanner error={health.error ?? proc.error} onRetry={() => { void health.reload(); void proc.reload(); }} />
      {!h && health.loading && <Spinner />}
      {h && (
        <div className="mt-4 grid grid-cols-2 gap-4 lg:grid-cols-4" data-testid="dashboard-stats">
          <StatCard label="Launcher" value={h.status === "ok" ? "Работает" : "Проблема"} tone={h.status === "ok" ? "radiant" : "danger"}
            hint={`v${h.version} · БД: ${h.database === "ok" ? "OK" : "недоступна"}`} icon={<Server className="h-4 w-4" />} />
          <StatCard label="ОЗУ процесса" value={p ? `${p.private_mb} МБ` : "—"} tone={p && p.private_mb > RAM_TARGET_MB ? "danger" : "default"}
            hint={`цель < ${RAM_TARGET_MB} МБ · RSS ${p?.rss_mb ?? "—"} МБ`} icon={<MemoryStick className="h-4 w-4" />} />
          <StatCard label="CPU процесса" value={p ? `${p.cpu_percent.toFixed(2)} %` : "—"} tone={p && p.cpu_percent > CPU_TARGET ? "accent" : "default"}
            hint={`цель < ${CPU_TARGET} % · потоков ${p?.threads ?? "—"}`} icon={<Cpu className="h-4 w-4" />} />
          <StatCard label="Время работы" value={formatUptime(h.uptime_seconds)} icon={<Clock className="h-4 w-4" />}
            hint={`дочерних процессов: ${p?.child_processes ?? "—"}`} />
        </div>
      )}
      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Card title="Компоненты" icon={<HardDrive className="h-4 w-4" />}>
          <ul className="space-y-2 text-sm" data-testid="components">
            <Row label="Сервер (FastAPI, один процесс Python)" ok={h?.status === "ok"} value={h ? `PID ${p?.pid ?? "—"} · Python ${p?.python ?? "—"}` : "—"} />
            <Row label="База данных SQLite" ok={h?.database === "ok"} value={settings.data?.database.path ?? "—"} />
            <Row label="Интерфейс (production-сборка)" ok={h?.frontend_built} value={h?.frontend_built ? "frontend/dist" : "не собран"} />
            <Row label="Канал обновлений (WebSocket)" ok={wsState === "open"} value={wsState === "open" ? "подключён" : "переподключение"} />
            <Row label="Резервная копия перед миграцией" ok={!!settings.data?.database.last_backup}
              value={settings.data?.database.last_backup ?? "не требовалась при этом запуске"} neutral={!settings.data?.database.last_backup} />
          </ul>
        </Card>
        <Card title="Последние предупреждения и ошибки" icon={<AlertTriangle className="h-4 w-4" />}
          actions={<Link className="text-xs text-accent hover:underline" to="/logs">все логи →</Link>}>
          {!problems.data ? <Spinner /> : problems.data.items.length === 0 ? <Empty>Предупреждений нет.</Empty> : (
            <Table head={["Время", "Уровень", "Компонент", "Сообщение"]}>
              {problems.data.items.map((l) => (
                <tr key={l.id}>
                  <td className="whitespace-nowrap px-3 py-1.5 text-xs text-gray-400">{formatDate(l.timestamp)}</td>
                  <td className={cx("px-3 py-1.5 font-mono text-xs", l.level === "WARNING" ? "text-amber-300" : "text-red-400")}>{l.level}</td>
                  <td className="px-3 py-1.5 text-xs">{l.component}</td>
                  <td className="px-3 py-1.5 font-mono text-xs">{l.message}</td>
                </tr>
              ))}
            </Table>
          )}
        </Card>
      </div>
      <p className="mt-6 flex items-center gap-2 text-xs text-gray-500"><Database className="h-3.5 w-3.5" />
        Показатели обновляются каждые {refreshMs / 1000} с (меняется в настройках). Launcher не изменяет приоритеты других программ.</p>
    </div>
  );
}

function Row({ label, ok, value, neutral }: { label: string; ok: boolean | undefined; value: string; neutral?: boolean }) {
  return (
    <li className="flex items-start justify-between gap-3">
      <span className="flex items-center gap-2">
        <span className={cx("h-2 w-2 shrink-0 rounded-full", neutral ? "bg-gray-500" : ok ? "bg-emerald-400" : "bg-red-500")} />
        {label}
      </span>
      <span className="truncate text-right font-mono text-xs text-gray-400" title={value}>{value}</span>
    </li>
  );
}
