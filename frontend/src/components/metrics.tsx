import type { ReactNode } from "react";
import { cx } from "./ui";

export const NO_DATA = "Нет данных";

/** Format a nullable metric: null / undefined renders "Нет данных", never a made-up number. */
export function fmt(v: number | null | undefined, unit = "", digits = 0): string {
  if (v === null || v === undefined || Number.isNaN(v)) return NO_DATA;
  return `${v.toLocaleString("ru-RU", { maximumFractionDigits: digits, minimumFractionDigits: 0 })}${unit ? ` ${unit}` : ""}`;
}

export function fmtRate(kbps: number | null | undefined): string {
  if (kbps === null || kbps === undefined) return NO_DATA;
  if (kbps >= 1024) return `${(kbps / 1024).toLocaleString("ru-RU", { maximumFractionDigits: 1 })} МБ/с`;
  return `${kbps.toLocaleString("ru-RU", { maximumFractionDigits: 0 })} КБ/с`;
}

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return NO_DATA;
  const s = Math.max(0, Math.floor(seconds));
  const d = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  const m = Math.floor((s % 3600) / 60);
  if (d) return `${d} д ${h} ч`;
  if (h) return `${h} ч ${m} мин`;
  if (m) return `${m} мин ${s % 60} с`;
  return `${s} с`;
}

/** Tiny dependency-free SVG line; gaps where values are missing. */
export function Sparkline({ values, max, color = "#f59e0b", height = 40, testId }: {
  values: (number | null)[]; max?: number; color?: string; height?: number; testId?: string;
}) {
  const real = values.filter((v): v is number => v !== null);
  if (real.length < 2) return <div className="flex items-center text-[11px] text-gray-600" style={{ height }} data-testid={testId}>недостаточно точек</div>;
  const top = max ?? Math.max(1, ...real) * 1.1;
  const w = 100;
  const step = w / Math.max(1, values.length - 1);
  const segments: string[] = [];
  let cur: string[] = [];
  values.forEach((v, i) => {
    if (v === null) {
      if (cur.length) segments.push(cur.join(" "));
      cur = [];
    } else cur.push(`${(i * step).toFixed(2)},${(height - (Math.min(v, top) / top) * (height - 2) - 1).toFixed(2)}`);
  });
  if (cur.length) segments.push(cur.join(" "));
  return (
    <svg viewBox={`0 0 ${w} ${height}`} preserveAspectRatio="none" className="w-full" style={{ height }} data-testid={testId}>
      {segments.map((pts, i) => <polyline key={i} points={pts} fill="none" stroke={color} strokeWidth="1.5" vectorEffect="non-scaling-stroke" />)}
    </svg>
  );
}

export function Meter({ label, value, unit = "%", max = 100, hint, warn = 80, danger = 92, children }: {
  label: string; value: number | null | undefined; unit?: string; max?: number; hint?: ReactNode; warn?: number; danger?: number; children?: ReactNode;
}) {
  const pct = value === null || value === undefined ? null : Math.min(100, (value / max) * 100);
  const color = pct === null ? "bg-gray-700" : pct >= danger ? "bg-red-500" : pct >= warn ? "bg-amber-400" : "bg-emerald-500";
  return (
    <div className="rounded-xl border border-surface-border bg-surface/80 p-4" data-testid={`meter-${label}`}>
      <div className="flex items-baseline justify-between text-xs uppercase tracking-wide text-gray-400"><span>{label}</span></div>
      <div className={cx("mt-1 text-2xl font-bold", value === null || value === undefined ? "text-gray-500 text-lg" : "text-gray-100")}>
        {fmt(value, unit, unit === "%" ? 0 : 0)}
      </div>
      <div className="mt-2 h-1.5 w-full overflow-hidden rounded bg-gray-800"><div className={cx("h-full", color)} style={{ width: `${pct ?? 0}%` }} /></div>
      {hint && <div className="mt-1 text-xs text-gray-500">{hint}</div>}
      {children}
    </div>
  );
}
