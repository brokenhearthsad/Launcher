import { Database, Power, Save, Server, Radio } from "lucide-react";
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
  const [confirmStop, setConfirmStop] = useState(false);
  const [stopped, setStopped] = useState(false);

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
      setMessage("Настройки сохранены. Уровни логов применяются сразу.");
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

  const stop = async () => {
    setConfirmStop(false);
    try {
      await api.shutdown();
      setStopped(true);
    } catch (e) {
      setError(e as ApiError);
    }
  };

  if (stopped) {
    return (
      <div>
        <PageHeader title="Launcher остановлен" />
        <p className="text-sm text-gray-300" role="status">Сервер корректно завершил работу. Вкладку можно закрыть. Для повторного запуска используйте start.bat.</p>
      </div>
    );
  }
  if (!settings.data || !draft) return <div><PageHeader title="Настройки" /><ErrorBanner error={settings.error} /><Spinner /></div>;
  const s = settings.data;
  return (
    <div>
      <PageHeader title="Настройки" subtitle="Параметры хранятся в локальной базе данных." actions={
        <Button variant="primary" loading={saving} onClick={save} data-testid="save-settings"><Save className="h-4 w-4" />Сохранить</Button>} />
      <ErrorBanner error={error} />
      {message && <p role="status" className="mb-4 text-sm text-emerald-300">{message}</p>}
      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Сервер" icon={<Server className="h-4 w-4" />}>
          <dl className="grid grid-cols-2 gap-2 text-sm">
            <dt className="text-gray-400">Версия</dt><dd>{s.backend.version}</dd>
            <dt className="text-gray-400">Адрес</dt><dd className="font-mono">http://localhost:{s.backend.port}</dd>
            <dt className="text-gray-400">Документация API</dt><dd><a className="text-accent underline" href="/docs" target="_blank" rel="noreferrer">/docs</a></dd>
            <dt className="text-gray-400">Лимит запросов</dt><dd>{s.backend.api_rate_limit_per_minute} в минуту</dd>
            <dt className="text-gray-400">Пониженный приоритет Launcher</dt><dd>{s.backend.lower_own_priority ? "включён" : "выключен"}</dd>
            <dt className="text-gray-400">Папка логов</dt><dd className="truncate font-mono text-xs" title={s.backend.log_dir}>{s.backend.log_dir}</dd>
          </dl>
          <p className="mt-3 text-xs text-gray-500">Адрес, порт и приоритет задаются в backend\.env (нужен перезапуск). Приоритеты других программ Launcher не меняет.</p>
          <div className="mt-4">
            <Button variant="danger" onClick={() => setConfirmStop(true)} data-testid="shutdown"><Power className="h-4 w-4" />Остановить Launcher</Button>
          </div>
        </Card>
        <Card title="Обновление интерфейса" icon={<Radio className="h-4 w-4" />}>
          <div className="grid grid-cols-2 gap-3">
            <TextInput label="Частота WebSocket (раз в секунду)" type="number" min={0.5} max={20} value={draft.ws_publish_hz} onChange={num("ws_publish_hz")} />
            <TextInput label="Интервал обновления страниц (с)" type="number" min={1} max={120} value={draft.ui_refresh_seconds} onChange={num("ui_refresh_seconds")} testId="ui-refresh" />
          </div>
          <p className="mt-2 text-xs text-gray-500">Чем больше интервал, тем меньше обращений к серверу. Опрос приостанавливается, когда вкладка скрыта.</p>
        </Card>
        <Card title="Мониторинг" className="lg:col-span-2">
          <div className="grid gap-3 md:grid-cols-4">
            <TextInput label="Интервал, страница открыта (с)" type="number" min={1} max={30} value={draft.monitor_active_interval} onChange={num("monitor_active_interval")} testId="active-interval" />
            <TextInput label="Интервал, страница закрыта (с)" type="number" min={5} max={300} value={draft.monitor_idle_interval} onChange={num("monitor_idle_interval")} />
            <TextInput label="Проверка процессов (с)" type="number" min={2} max={120} value={draft.process_scan_interval} onChange={num("process_scan_interval")} />
            <TextInput label="Хранить историю (дней)" type="number" min={1} max={365} value={draft.metrics_retention_days} onChange={num("metrics_retention_days")} />
          </div>
          <div className="mt-4 grid items-end gap-3 md:grid-cols-[auto_1fr]">
            <Toggle label="Температура CPU из LibreHardwareMonitor" checked={draft.lhm_enabled} onChange={(v) => setDraft({ ...draft, lhm_enabled: v })} />
            <TextInput label="Адрес LibreHardwareMonitor (только этот ПК)" value={draft.lhm_url} onChange={(v) => setDraft({ ...draft, lhm_url: v })} testId="lhm-url" />
          </div>
          <p className="mt-2 text-xs text-gray-500">LibreHardwareMonitor нужно запустить отдельно: Options → Remote Web Server → Run (порт 8085). Без него температура CPU показывается как «Нет данных».</p>
        </Card>
        <Card title="Логирование">
          <div className="grid grid-cols-2 gap-3">
            <Select label="Уровень логов приложения" value={draft.log_level} onChange={(v) => setDraft({ ...draft, log_level: v })} options={LEVELS} testId="log-level-setting" />
            <Select label="Уровень логов в базе данных" value={draft.db_log_level} onChange={(v) => setDraft({ ...draft, db_log_level: v })} options={LEVELS} />
          </div>
        </Card>
        <Card title="База данных" icon={<Database className="h-4 w-4" />}>
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
            <dt className="text-gray-400">Тип</dt><dd>{s.database.dialect}</dd>
            <dt className="text-gray-400">Размер</dt><dd>{formatBytes(s.database.size_bytes)}</dd>
            <dt className="text-gray-400">Файл</dt><dd className="truncate font-mono text-xs" title={s.database.path}>{s.database.path ?? s.database.url}</dd>
            <dt className="text-gray-400">Резервные копии</dt><dd className="truncate font-mono text-xs" title={s.database.backup_dir}>{s.database.backup_dir}</dd>
            <dt className="text-gray-400">Последняя копия</dt><dd className="truncate font-mono text-xs">{s.database.last_backup ?? "при этом запуске не создавалась"}</dd>
          </dl>
          <div className="mt-4 flex flex-wrap items-end gap-3">
            <Button onClick={() => action(async () => { const r = await api.vacuum(); return `Сжатие выполнено: ${formatBytes(r.size_before)} → ${formatBytes(r.size_after)}`; })}>Сжать базу (VACUUM)</Button>
            <div className="w-44"><TextInput label="Удалить логи старше (дней)" type="number" min={0} value={purgeDays} onChange={setPurgeDays} /></div>
            <Button variant="danger" onClick={() => setConfirmPurge(true)}>Удалить логи</Button>
          </div>
        </Card>
      </div>
      <ConfirmDialog open={confirmPurge} danger title="Удаление логов" confirmLabel="Удалить"
        message={`Удалить все записи логов старше ${purgeDays} дн.?`} onCancel={() => setConfirmPurge(false)}
        onConfirm={() => { setConfirmPurge(false); void action(async () => `Удалено записей: ${(await api.purgeLogs(Number(purgeDays))).deleted}`); }} />
      <ConfirmDialog open={confirmStop} danger title="Остановить Launcher?" confirmLabel="Остановить"
        message="Сервер корректно завершит работу. Снова запустить можно через start.bat." onCancel={() => setConfirmStop(false)} onConfirm={stop} />
    </div>
  );
}
