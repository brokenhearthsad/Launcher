import { Cpu, HardDrive, MemoryStick, MonitorSmartphone, Network, Thermometer } from "lucide-react";
import { api } from "../api/client";
import type { HistoryPoint } from "../api/types";
import { Card, Empty, ErrorBanner, PageHeader, Spinner, Table } from "../components/ui";
import { fmt, fmtRate, Meter, NO_DATA, Sparkline } from "../components/metrics";
import { useAsync } from "../hooks/useAsync";
import { useMonitoring } from "../hooks/Monitoring";

export default function SystemPage() {
  const { metrics: m, series, error } = useMonitoring();
  const history = useAsync(() => api.history(24), [], 60_000);

  if (!m) return <div><PageHeader title="Система" /><ErrorBanner error={error} />{!error && <Spinner />}</div>;
  const gpu = m.gpu;
  const pick = (k: keyof (typeof series)[number]) => series.map((p) => p[k] as number | null);
  return (
    <div>
      <PageHeader title="Система" subtitle={`Обновление каждые ${m.interval_seconds ?? 2} с, пока страница открыта. Недоступные показатели отмечены «${NO_DATA}».`} />
      <ErrorBanner error={error} />
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4" data-testid="system-meters">
        <Meter label="CPU" value={m.cpu.percent} hint={`${m.cpu.logical_cores} потоков · ${fmt(m.cpu.freq_mhz, "МГц")}`} />
        <Meter label="ОЗУ" value={m.memory.percent} hint={`${fmt(m.memory.used_mb / 1024, "ГБ", 1)} из ${fmt(m.memory.total_mb / 1024, "ГБ", 1)}`} />
        <Meter label="GPU" value={gpu.available ? gpu.util_percent : null} hint={gpu.available ? gpu.name : gpu.reason ?? NO_DATA} />
        <Meter label="Видеопамять" value={gpu.available ? gpu.mem_used_mb : null} unit="МБ" max={gpu.mem_total_mb ?? 1}
          hint={gpu.available ? `из ${fmt(gpu.mem_total_mb, "МБ")}` : NO_DATA} />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <Card title="Загрузка CPU" icon={<Cpu className="h-4 w-4" />} className="lg:col-span-2">
          <Sparkline values={pick("cpu")} max={100} testId="cpu-spark" />
          <div className="mt-4 grid grid-cols-6 gap-2 md:grid-cols-12" data-testid="per-core">
            {m.cpu.per_core.map((v, i) => (
              <div key={i} className="text-center">
                <div className="mx-auto h-12 w-3 overflow-hidden rounded bg-gray-800">
                  <div className="w-full bg-sky-500" style={{ height: `${v}%`, marginTop: `${100 - v}%` }} />
                </div>
                <div className="mt-1 text-[10px] text-gray-500">{i + 1}</div>
              </div>
            ))}
          </div>
        </Card>
        <Card title="Температуры" icon={<Thermometer className="h-4 w-4" />}>
          <dl className="space-y-3 text-sm">
            <div className="flex justify-between"><dt className="text-gray-400">CPU</dt>
              <dd className={m.cpu_temp.available ? "font-semibold" : "text-gray-500"} data-testid="cpu-temp">{m.cpu_temp.available ? fmt(m.cpu_temp.temp_c, "°C", 1) : NO_DATA}</dd></div>
            <p className="text-[11px] text-gray-500">{m.cpu_temp.available ? `LibreHardwareMonitor: ${m.cpu_temp.sensor}` : m.cpu_temp.reason}</p>
            <div className="flex justify-between"><dt className="text-gray-400">GPU</dt>
              <dd className={gpu.available && gpu.temp_c != null ? "font-semibold" : "text-gray-500"} data-testid="gpu-temp">{gpu.available ? fmt(gpu.temp_c, "°C") : NO_DATA}</dd></div>
            <div className="flex justify-between"><dt className="text-gray-400">Мощность GPU</dt><dd>{gpu.available ? fmt(gpu.power_w, "Вт", 1) : NO_DATA}</dd></div>
            <div className="flex justify-between"><dt className="text-gray-400">Источник GPU</dt><dd className="text-xs text-gray-400">{gpu.source ?? NO_DATA}</dd></div>
          </dl>
          <div className="mt-3"><Sparkline values={pick("gpu_temp")} max={100} color="#f87171" /></div>
        </Card>
        <Card title="Видеокарта" icon={<MonitorSmartphone className="h-4 w-4" />}>
          {gpu.available ? (
            <>
              <div className="mb-2 text-sm">{gpu.name}</div>
              <div className="text-xs text-gray-500">Загрузка</div><Sparkline values={pick("gpu_util")} max={100} color="#a78bfa" />
              <div className="mt-2 text-xs text-gray-500">Видеопамять, МБ</div><Sparkline values={pick("gpu_mem_mb")} max={gpu.mem_total_mb ?? undefined} color="#38bdf8" />
            </>
          ) : <Empty>{NO_DATA}: {gpu.reason}</Empty>}
        </Card>
        <Card title="Память" icon={<MemoryStick className="h-4 w-4" />}>
          <dl className="grid grid-cols-2 gap-2 text-sm">
            <dt className="text-gray-400">Занято</dt><dd>{fmt(m.memory.used_mb, "МБ")}</dd>
            <dt className="text-gray-400">Свободно</dt><dd>{fmt(m.memory.available_mb, "МБ")}</dd>
            <dt className="text-gray-400">Всего</dt><dd>{fmt(m.memory.total_mb, "МБ")}</dd>
          </dl>
          <div className="mt-3"><Sparkline values={pick("ram_pct")} max={100} color="#4ade80" /></div>
        </Card>
        <Card title="Сеть" icon={<Network className="h-4 w-4" />}>
          <dl className="grid grid-cols-2 gap-2 text-sm">
            <dt className="text-gray-400">Приём</dt><dd data-testid="net-rx">{fmtRate(m.network.rx_kbps)}</dd>
            <dt className="text-gray-400">Отправка</dt><dd>{fmtRate(m.network.tx_kbps)}</dd>
          </dl>
          <div className="mt-3"><Sparkline values={pick("net_rx_kbps")} color="#60a5fa" /></div>
        </Card>
      </div>

      <Card title="Диски" icon={<HardDrive className="h-4 w-4" />} className="mt-6">
        <Table head={["Диск", "Занято", "Свободно", "Всего", "Заполнено"]} testId="disks-table">
          {m.disks.map((d) => (
            <tr key={d.mount}>
              <td className="px-3 py-2 font-mono">{d.mount}</td>
              {d.available ? (
                <>
                  <td className="px-3 py-2">{fmt(d.used_gb, "ГБ", 1)}</td><td className="px-3 py-2">{fmt(d.free_gb, "ГБ", 1)}</td>
                  <td className="px-3 py-2">{fmt(d.total_gb, "ГБ", 1)}</td>
                  <td className="px-3 py-2"><div className="flex items-center gap-2"><div className="h-1.5 w-32 overflow-hidden rounded bg-gray-800">
                    <div className={(d.percent ?? 0) > 90 ? "h-full bg-red-500" : "h-full bg-emerald-500"} style={{ width: `${d.percent}%` }} /></div>{fmt(d.percent, "%")}</div></td>
                </>
              ) : <td colSpan={4} className="px-3 py-2 text-gray-500">{NO_DATA} (диск не найден)</td>}
            </tr>
          ))}
        </Table>
        <p className="mt-3 text-xs text-gray-400">Активность всех дисков: чтение {fmtRate(m.disk_io.read_kbps)}, запись {fmtRate(m.disk_io.write_kbps)}.
          Разбивка активности по буквам дисков без WMI недоступна.</p>
      </Card>

      <Card title="История за 24 часа (средние за минуту)" className="mt-6">
        {!history.data ? <Spinner /> : history.data.points.length < 2 ? <Empty>История накапливается: одна точка в минуту.</Empty> : (
          <HistoryCharts points={history.data.points} />
        )}
      </Card>
    </div>
  );
}

function HistoryCharts({ points }: { points: HistoryPoint[] }) {
  const col = (k: keyof HistoryPoint) => points.map((p) => p[k] as number | null);
  return (
    <div className="grid gap-4 md:grid-cols-3">
      <div><div className="text-xs text-gray-400">CPU, %</div><Sparkline values={col("cpu_avg")} max={100} /></div>
      <div><div className="text-xs text-gray-400">ОЗУ, %</div><Sparkline values={col("ram_pct_avg")} max={100} color="#4ade80" /></div>
      <div><div className="text-xs text-gray-400">GPU, %</div><Sparkline values={col("gpu_util_avg")} max={100} color="#a78bfa" /></div>
      <p className="text-[11px] text-gray-500 md:col-span-3">{points.length} мин · с {new Date(points[0].ts).toLocaleString()}</p>
    </div>
  );
}
