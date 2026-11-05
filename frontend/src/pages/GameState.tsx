import { FileCog, RotateCcw, ShieldCheck, Trash2, Upload } from "lucide-react";
import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import type { GsiConfig } from "../api/types";
import { Bar, Button, Card, ConfirmDialog, Empty, ErrorBanner, Modal, PageHeader, Spinner, Table, TeamBadge, cx } from "../components/ui";
import { fmt, formatDuration, NO_DATA } from "../components/metrics";
import { gameClock, GsiBadge, liveStatus, prettyId } from "../components/gsi";
import { useLiveEvent } from "../hooks/LiveEvents";
import { useAsync } from "../hooks/useAsync";
import { useMonitoring } from "../hooks/Monitoring";
import { useUiSettings } from "../hooks/UiSettings";
import { formatDate } from "../lib/format";
import { Flag } from "./SteamDota";

const ACTION_TEXT: Record<string, string> = {
  create: "Будет создан новый файл конфигурации.",
  update: "Файл Launcher будет обновлён (старая версия сохранится в резервной копии).",
  replace_foreign: "Файл с таким именем создан не Launcher. Он будет заменён, а исходный сохранён в резервной копии.",
  none: "Конфигурация уже установлена и актуальна — изменений нет.",
};
const RESULT: Record<string, string> = { win: "Победа", loss: "Поражение", ended: "Завершён", left: "Выход из матча", in_progress: "Идёт",
  interrupted: "Прерван (Launcher был остановлен)" };

function useNow(): number {
  const [now, setNow] = useState(Date.now() / 1000);
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now() / 1000), 1000);
    return () => window.clearInterval(id);
  }, []);
  return now;
}

function V({ v }: { v: string | number | null | undefined }) {
  return v === null || v === undefined || v === "" ? <span className="text-gray-500">{NO_DATA}</span> : <>{v}</>;
}

function InstallPanel() {
  const cfg = useAsync(api.gsiConfig, []);
  const [preview, setPreview] = useState(false);
  const [agreed, setAgreed] = useState(false);
  const [confirmRemove, setConfirmRemove] = useState(false);
  const [restoreName, setRestoreName] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const run = async (fn: () => Promise<{ check: GsiConfig }>, ok: (r: never) => string) => {
    setBusy(true);
    setError(null);
    try {
      const r = await fn();
      cfg.setData(r.check);
      setMessage(ok(r as never));
    } catch (e) {
      setError(e as ApiError);
      void cfg.reload();
    } finally {
      setBusy(false);
      setPreview(false);
      setAgreed(false);
    }
  };

  const c = cfg.data;
  return (
    <Card title="Конфигурация GSI" icon={<FileCog className="h-4 w-4" />}
      actions={<Button variant="ghost" onClick={() => void cfg.reload()} data-testid="gsi-check"><ShieldCheck className="h-4 w-4" />Проверить конфигурацию</Button>}>
      <ErrorBanner error={error ?? cfg.error} />
      {message && <p role="status" className="mb-3 text-sm text-emerald-300">{message}</p>}
      {!c ? <Spinner /> : !c.available ? <Empty>{c.error}</Empty> : (
        <>
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm" data-testid="gsi-config">
            <dt className="text-gray-400">Состояние</dt>
            <dd>{c.installed && c.up_to_date ? <Flag ok yes="установлена и актуальна" no="" /> : c.installed ? "установлена (требует обновления)" :
              c.exists && !c.managed ? <span className="text-amber-300">файл с таким именем создан не Launcher</span> : <Flag ok={false} yes="" no="не установлена" />}</dd>
            <dt className="text-gray-400">Файл</dt><dd className="truncate font-mono text-xs" title={c.file}>{c.file}</dd>
            <dt className="text-gray-400">Адрес приёма</dt><dd className="font-mono text-xs">{c.expected_uri}</dd>
            <dt className="text-gray-400">Другие GSI-файлы</dt><dd className="text-xs">{c.other_configs?.length ? `${c.other_configs.join(", ")} — не изменяются` : "нет"}</dd>
            <dt className="text-gray-400">Параметр запуска</dt>
            <dd className="text-xs" data-testid="launch-option">{c.launch_option.found === true ? <Flag ok yes="-gamestateintegration найден" no="" /> :
              c.launch_option.found === false ? <span className="text-amber-300">не найден: Steam → Dota 2 → Свойства → Параметры запуска → добавьте <code>-gamestateintegration</code></span> :
              <span className="text-gray-500">{NO_DATA} (настройки Steam не найдены)</span>}</dd>
          </dl>
          <div className="mt-4 flex flex-wrap gap-2">
            <Button variant="primary" onClick={() => setPreview(true)} disabled={!c.plan || c.plan.action === "none"} data-testid="gsi-install">
              <Upload className="h-4 w-4" />Установить GSI</Button>
            <Button variant="danger" onClick={() => setConfirmRemove(true)} disabled={!c.exists || !c.managed} data-testid="gsi-uninstall">
              <Trash2 className="h-4 w-4" />Удалить конфигурацию Launcher</Button>
          </div>
          <p className="mt-2 text-xs text-gray-500">После установки перезапустите Dota 2 — она читает конфигурацию при старте. Launcher ничего не отправляет в игру.</p>
          {c.backups.length > 0 && (
            <div className="mt-4">
              <div className="mb-1 text-xs uppercase tracking-wide text-gray-400">Резервные копии</div>
              <Table head={["Файл", "Создан", "Источник", ""]} testId="gsi-backups">
                {c.backups.map((b) => (
                  <tr key={b.name}><td className="px-3 py-1.5 font-mono text-xs">{b.name}</td><td className="px-3 py-1.5 text-xs">{formatDate(b.created)}</td>
                    <td className="px-3 py-1.5 text-xs">{b.managed ? "Launcher" : "другой"}</td>
                    <td className="px-3 py-1.5"><Button variant="ghost" onClick={() => setRestoreName(b.name)} aria-label={`Восстановить ${b.name}`}><RotateCcw className="h-4 w-4" />Восстановить</Button></td></tr>
                ))}
              </Table>
            </div>
          )}
        </>
      )}
      {c?.plan && preview && (
        <Modal open wide title="Установка конфигурации GSI — проверьте изменения" onClose={() => setPreview(false)} footer={<>
          <Button onClick={() => setPreview(false)}>Отмена</Button>
          <Button variant="primary" disabled={!agreed} loading={busy} data-testid="gsi-confirm"
            onClick={() => run(() => api.gsiInstall(c.plan!.plan_id), (r: { backup: string | null }) => r.backup ? `Конфигурация установлена. Резервная копия: ${r.backup}` : "Конфигурация установлена.")}>
            Подтвердить и установить</Button>
        </>}>
          <div className="space-y-3 text-sm" data-testid="gsi-preview">
            <p>{ACTION_TEXT[c.plan.action]}</p>
            <ul className="list-disc pl-5 text-xs text-gray-400">
              <li>Файл: <span className="font-mono">{c.file}</span></li>
              {c.plan.creates_directory && <li>Будет создана папка <span className="font-mono">gamestate_integration</span>.</li>}
              <li>{c.plan.backup_before_change ? "Существующий файл будет скопирован в резервные копии перед изменением." : "Существующего файла нет — копия не нужна."}</li>
              <li>Другие файлы и настройки Dota 2 и Steam не изменяются. Токен показан частично.</li>
            </ul>
            <div className="grid gap-3 md:grid-cols-2">
              <div><div className="mb-1 text-xs text-gray-400">Сейчас</div>
                <pre className="max-h-72 overflow-auto rounded bg-gray-950 p-2 text-[11px]">{c.plan.current_content ?? "(файла нет)"}</pre></div>
              <div><div className="mb-1 text-xs text-gray-400">После установки</div>
                <pre className="max-h-72 overflow-auto rounded bg-gray-950 p-2 text-[11px] text-emerald-200">{c.plan.new_content}</pre></div>
            </div>
            <label className="flex items-center gap-2"><input type="checkbox" checked={agreed} onChange={(e) => setAgreed(e.target.checked)}
              className="accent-amber-500" data-testid="gsi-agree" />Я проверил изменения и подтверждаю установку</label>
          </div>
        </Modal>
      )}
      <ConfirmDialog open={confirmRemove} danger title="Удалить конфигурацию Launcher?" confirmLabel="Удалить"
        message="Будет удалён только файл gamestate_integration_launcher.cfg. Перед удалением создаётся резервная копия."
        onCancel={() => setConfirmRemove(false)}
        onConfirm={() => { setConfirmRemove(false); void run(api.gsiUninstall, (r: { backup: string }) => `Конфигурация удалена. Копия: ${r.backup}`); }} />
      <ConfirmDialog open={restoreName !== null} title="Восстановить резервную копию?" confirmLabel="Восстановить"
        message={<>Файл будет заменён содержимым <span className="font-mono">{restoreName}</span>. Текущий файл сначала будет сохранён в копию.</>}
        onCancel={() => setRestoreName(null)}
        onConfirm={() => { const n = restoreName!; setRestoreName(null); void run(() => api.gsiRestore(n), () => `Восстановлено из ${n}`); }} />
    </Card>
  );
}

export default function GameState() {
  const { gsi, environment } = useMonitoring();
  const { refreshMs } = useUiSettings();
  const polled = useAsync(api.gsiState, [], refreshMs);
  const state = gsi && polled.data ? ((gsi.last_update ?? 0) >= (polled.data.last_update ?? 0) ? gsi : polled.data) : gsi ?? polled.data ?? null;
  const now = useNow();
  const { status, age } = liveStatus(state, now);
  const events = useAsync(() => api.events({ source: "gsi", page_size: 15 }), []);
  const matches = useAsync(() => api.gsiMatches({ page_size: 10 }), []);
  useLiveEvent(["event_created"], (m) => {
    if ((m.data as { source?: string }).source === "gsi") { void events.reload(); void matches.reload(); }
  });
  const s = status === "stale" ? null : state?.snapshot ?? null;
  const dotaRunning = environment?.dota.process.running ?? state?.dota_running ?? null;

  return (
    <div>
      <PageHeader title="Состояние игры" subtitle="Данные Dota 2 Game State Integration. Только чтение: Launcher не управляет игрой и ничего ей не отправляет." />
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4" data-testid="gsi-status-cards">
        <Card title="Подключение GSI"><GsiBadge status={status} testId="gsi-status" />
          <div className="mt-2 text-xs text-gray-500">получено обновлений: {state?.updates ?? 0}{state?.rejected ? ` · отклонено: ${state.rejected}` : ""}</div></Card>
        <Card title="Dota 2"><Flag ok={dotaRunning} yes="Запущена" no="Не запущена" /></Card>
        <Card title="Последнее получение">
          <div className="text-sm" data-testid="gsi-last">{state?.last_update ? new Date(state.last_update * 1000).toLocaleTimeString() : NO_DATA}</div>
          <div className="text-xs text-gray-500">{age !== null ? `${Math.round(age)} с назад` : "данных ещё не было"}</div>
        </Card>
        <Card title="Актуальность">
          <Bar value={age === null ? 0 : Math.max(0, (state?.stale_after_seconds ?? 40) - age)} max={state?.stale_after_seconds ?? 40}
            color={status === "live" ? "bg-emerald-500" : status === "delayed" ? "bg-amber-400" : "bg-red-500"} />
          <div className="mt-1 text-xs text-gray-500" data-testid="gsi-freshness">{status === "waiting" ? "ожидание" : status === "stale" ? "устарели" : status === "delayed" ? "задержка" : "актуальны"}
            {" "}· «нет данных» через {state?.stale_after_seconds ?? 40} с без обновлений</div>
        </Card>
      </div>

      {status === "waiting" && (
        <div className="mt-4 rounded-lg border border-surface-border bg-surface/60 p-3 text-sm text-gray-300">
          Данные от Dota 2 ещё не приходили. Установите конфигурацию ниже, добавьте параметр запуска <code>-gamestateintegration</code> и перезапустите Dota 2.
        </div>
      )}

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Card title="Игра">
          {!s ? <Empty>{NO_DATA}</Empty> : !s.has_map ? (
            <Empty>Игрок не в матче{s.activity ? ` (${s.activity === "menu" ? "главное меню" : s.activity})` : ""}: GSI не передаёт данные карты.</Empty>
          ) : (
            <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm" data-testid="gsi-game">
              <dt className="text-gray-400">Фаза</dt><dd><V v={s.game_state_label} /></dd>
              <dt className="text-gray-400">Игровое время</dt><dd className="font-mono"><V v={gameClock(s.clock_time)} />{s.paused ? " · пауза" : ""}</dd>
              <dt className="text-gray-400">С начала матча</dt><dd className="font-mono"><V v={gameClock(s.game_time)} /></dd>
              <dt className="text-gray-400">Счёт</dt>
              <dd data-testid="gsi-score">{s.radiant_score !== null && s.dire_score !== null
                ? <><span className="text-radiant">{s.radiant_score}</span> : <span className="text-dire">{s.dire_score}</span></> : <V v={null} />}</dd>
              <dt className="text-gray-400">Карта / режим</dt>
              <dd><V v={[s.map_name, s.game_mode, s.custom_game_name].filter(Boolean).join(" · ") || null} />
                {!s.game_mode && <span className="ml-1 text-xs text-gray-500">(название режима GSI не передаёт)</span>}</dd>
              <dt className="text-gray-400">Время суток</dt><dd><V v={s.daytime === null ? null : s.daytime ? "день" : "ночь"} /></dd>
              <dt className="text-gray-400">Матч</dt><dd className="font-mono text-xs"><V v={s.match_id} /></dd>
              {s.win_team && <><dt className="text-gray-400">Победитель</dt><dd><TeamBadge team={s.win_team} /></dd></>}
            </dl>
          )}
        </Card>
        <Card title="Герой">
          {!s || !s.has_hero ? <Empty>{NO_DATA}{s?.has_map ? " — герой ещё не выбран или вы наблюдатель" : ""}</Empty> : (
            <div data-testid="gsi-hero">
              <div className="flex items-baseline justify-between">
                <div><span className="text-lg font-semibold">{s.hero_name}</span><span className="ml-2 font-mono text-xs text-gray-500">{s.hero_internal}</span></div>
                <span className="rounded bg-gray-800 px-2 text-sm">Ур. <V v={s.hero_level} /></span>
              </div>
              <div className="mt-1 text-sm">{s.alive === false ? <span className="text-red-300">Мёртв{s.respawn_seconds ? ` — возрождение через ${s.respawn_seconds} с` : ""}</span>
                : s.alive ? <span className="text-emerald-300">Жив</span> : <V v={null} />} {s.team && <TeamBadge team={s.team} />}</div>
              <div className="mt-3 space-y-2">
                <div><div className="flex justify-between text-xs"><span>Здоровье</span><span data-testid="gsi-hp">{s.health !== null && s.max_health !== null ? `${s.health} / ${s.max_health}` : NO_DATA}</span></div>
                  <Bar value={s.health ?? 0} max={s.max_health ?? 1} color="bg-emerald-500" /></div>
                <div><div className="flex justify-between text-xs"><span>Мана</span><span>{s.mana !== null && s.max_mana !== null ? `${s.mana} / ${s.max_mana}` : NO_DATA}</span></div>
                  <Bar value={s.mana ?? 0} max={s.max_mana ?? 1} color="bg-sky-500" /></div>
              </div>
              <dl className="mt-3 grid grid-cols-4 gap-2 text-center text-sm">
                <div><dt className="text-[11px] text-gray-500">K/D/A</dt><dd className="font-mono">{s.kills ?? "—"}/{s.deaths ?? "—"}/{s.assists ?? "—"}</dd></div>
                <div><dt className="text-[11px] text-gray-500">LH/DN</dt><dd className="font-mono">{s.last_hits ?? "—"}/{s.denies ?? "—"}</dd></div>
                <div><dt className="text-[11px] text-gray-500">Золото</dt><dd>{fmt(s.gold)}</dd></div>
                <div><dt className="text-[11px] text-gray-500">GPM/XPM</dt><dd>{s.gpm ?? "—"}/{s.xpm ?? "—"}</dd></div>
              </dl>
            </div>
          )}
        </Card>
        <Card title="Способности">
          {!s || s.abilities.length === 0 ? <Empty>{NO_DATA}</Empty> : (
            <Table head={["Способность", "Ур.", "Перезарядка", "Готова"]} testId="gsi-abilities">
              {s.abilities.map((a) => (
                <tr key={a.slot}><td className="px-3 py-1.5 text-sm">{prettyId(a.name)}{a.ultimate ? " (ульт.)" : ""}{a.passive ? " · пассивная" : ""}</td>
                  <td className="px-3 py-1.5"><V v={a.level} /></td><td className="px-3 py-1.5">{a.cooldown ? `${a.cooldown} с` : a.cooldown === 0 ? "—" : <V v={null} />}</td>
                  <td className={cx("px-3 py-1.5", a.can_cast ? "text-emerald-300" : "text-gray-500")}>{a.can_cast === null ? NO_DATA : a.can_cast ? "да" : "нет"}</td></tr>
              ))}
            </Table>
          )}
        </Card>
        <Card title="Предметы">
          {!s || s.items.length === 0 ? <Empty>{NO_DATA}</Empty> : (
            <ul className="grid grid-cols-2 gap-2 text-sm" data-testid="gsi-items">
              {s.items.map((i) => (
                <li key={i.slot} className="rounded border border-surface-border px-2 py-1"><span className="text-[11px] text-gray-500">{i.slot}</span><div>{prettyId(i.name)}
                  {i.charges ? <span className="text-xs text-gray-400"> ×{i.charges}</span> : null}{i.cooldown ? <span className="text-xs text-amber-300"> · {i.cooldown} с</span> : null}</div></li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <div className="mt-6"><InstallPanel /></div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Card title="Журнал GSI">
          {!events.data ? <Spinner /> : events.data.items.length === 0 ? <Empty>Событий ещё нет.</Empty> : (
            <Table head={["Время", "Событие"]} testId="gsi-events">
              {events.data.items.map((e) => <tr key={e.id}><td className="whitespace-nowrap px-3 py-1.5 text-xs text-gray-400">{formatDate(e.ts)}</td>
                <td className={cx("px-3 py-1.5 text-sm", e.severity === "warning" && "text-amber-300")}>{e.message}</td></tr>)}
            </Table>
          )}
        </Card>
        <Card title="Матчи (по данным GSI)">
          {!matches.data ? <Spinner /> : matches.data.items.length === 0 ? <Empty>Матчей пока нет.</Empty> : (
            <Table head={["Начало", "Герой", "Итог", "Длит.", "K/D/A"]} testId="gsi-matches">
              {matches.data.items.map((m) => (
                <tr key={m.id}><td className="whitespace-nowrap px-3 py-1.5 text-xs text-gray-400">{formatDate(m.started_at)}</td>
                  <td className="px-3 py-1.5 text-sm"><V v={m.hero_name} /></td><td className="px-3 py-1.5 text-sm">{RESULT[m.result] ?? m.result}</td>
                  <td className="px-3 py-1.5 font-mono text-xs">{m.game_time !== null ? formatDuration(m.game_time) : NO_DATA}</td>
                  <td className="px-3 py-1.5 font-mono text-xs">{m.kills ?? "—"}/{m.deaths ?? "—"}/{m.assists ?? "—"}</td></tr>
              ))}
            </Table>
          )}
        </Card>
      </div>
      <p className="mt-4 text-xs text-gray-500">Набор данных зависит от контекста: в главном меню GSI передаёт только сведения о клиенте, во время выбора героев — без героя,
        в режиме наблюдателя — другие поля. Недоступные значения отмечены «{NO_DATA}».</p>
    </div>
  );
}
