import { RefreshCw } from "lucide-react";
import { useState } from "react";
import { api } from "../api/client";
import { Button, Card, Empty, ErrorBanner, PageHeader, Pagination, Select, Spinner, Table, TextInput, cx } from "../components/ui";
import { useLiveEvent } from "../hooks/LiveEvents";
import { useAsync } from "../hooks/useAsync";
import { useUiSettings } from "../hooks/UiSettings";
import { formatDate } from "../lib/format";

const LEVEL_STYLE: Record<string, string> = {
  DEBUG: "text-gray-400", INFO: "text-sky-300", WARNING: "text-amber-300", ERROR: "text-red-400", CRITICAL: "text-red-500 font-bold",
};

export default function Logs() {
  const { refreshMs } = useUiSettings();
  const [page, setPage] = useState(1);
  const [level, setLevel] = useState("");
  const [component, setComponent] = useState("");
  const [search, setSearch] = useState("");
  const [auto, setAuto] = useState(true);
  const levels = level === "WARNING+" ? ["WARNING", "ERROR", "CRITICAL"] : level ? [level] : undefined;
  const logs = useAsync(() => api.logs({ page, page_size: 50, level: levels, component: component || undefined, search: search || undefined }),
    [page, level, component, search], auto ? refreshMs : undefined);
  const components = useAsync(api.logComponents, []);
  const [systemErrors, setSystemErrors] = useState<string[]>([]);
  useLiveEvent(["system_error"], (m) => setSystemErrors((prev) => [String((m.data as { message: string }).message), ...prev].slice(0, 5)));

  return (
    <div>
      <PageHeader title="Логи" subtitle="Структурированные логи Launcher в SQLite (дублируются в backend/logs/app.jsonl)."
        actions={<Button onClick={() => void logs.reload()}><RefreshCw className="h-4 w-4" />Обновить</Button>} />
      {systemErrors.map((e, i) => <div key={i} className="mb-2"><ErrorBanner error={{ message: `Системная ошибка: ${e}` }} /></div>)}
      <Card title="Фильтры">
        <div className="grid items-end gap-3 md:grid-cols-4">
          <Select label="Уровень" value={level} onChange={(v) => { setLevel(v); setPage(1); }} testId="log-level"
            options={[{ value: "", label: "Все уровни" }, { value: "WARNING+", label: "Предупреждения и ошибки" },
              ...["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"].map((l) => ({ value: l, label: l }))]} />
          <Select label="Компонент" value={component} onChange={(v) => { setComponent(v); setPage(1); }} testId="log-component"
            options={[{ value: "", label: "Все компоненты" }, ...(components.data ?? []).map((c) => ({ value: c, label: c }))]} />
          <TextInput label="Поиск по тексту" value={search} onChange={(v) => { setSearch(v); setPage(1); }} placeholder="текст…" testId="log-search" />
          <label className="flex items-center gap-2 pb-2 text-sm text-gray-300">
            <input type="checkbox" checked={auto} onChange={(e) => setAuto(e.target.checked)} className="accent-amber-500" />
            Автообновление каждые {refreshMs / 1000} с
          </label>
        </div>
      </Card>
      <Card title="Записи" className="mt-6">
        <ErrorBanner error={logs.error} />
        {!logs.data ? <Spinner /> : logs.data.items.length === 0 ? <Empty>Нет записей, подходящих под фильтры.</Empty> : (
          <>
            <Table head={["Время", "Уровень", "Компонент", "Сообщение"]} testId="logs-table">
              {logs.data.items.map((l) => (
                <tr key={l.id}>
                  <td className="whitespace-nowrap px-3 py-1.5 font-mono text-xs text-gray-400">{formatDate(l.timestamp)}</td>
                  <td className={cx("px-3 py-1.5 font-mono text-xs", LEVEL_STYLE[l.level])}>{l.level}</td>
                  <td className="px-3 py-1.5 text-xs">{l.component}</td>
                  <td className="px-3 py-1.5 font-mono text-xs">{l.message}</td>
                </tr>
              ))}
            </Table>
            <Pagination page={page} pageSize={50} total={logs.data.total} onPage={setPage} />
          </>
        )}
      </Card>
    </div>
  );
}
