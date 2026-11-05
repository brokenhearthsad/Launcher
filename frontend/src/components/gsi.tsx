import type { GsiState, GsiStatus } from "../api/types";
import { cx } from "./ui";

export const GSI_STATUS: Record<GsiStatus | "fresh", { label: string; tone: string; dot: string }> = {
  waiting: { label: "Ожидание GSI", tone: "text-gray-300", dot: "bg-gray-500" },
  live: { label: "Данные поступают", tone: "text-emerald-300", dot: "bg-emerald-400" },
  fresh: { label: "Данные поступают", tone: "text-emerald-300", dot: "bg-emerald-400" },
  delayed: { label: "Задержка данных", tone: "text-amber-300", dot: "bg-amber-400" },
  stale: { label: "Нет данных (GSI молчит)", tone: "text-red-300", dot: "bg-red-500" },
};

const FRESH_SECONDS = 5;

/** Status as seen *now*: the server value is refined with the age since the last update. */
export function liveStatus(g: GsiState | null, nowSec: number): { status: GsiStatus; age: number | null } {
  if (!g || g.last_update === null) return { status: "waiting", age: null };
  const age = Math.max(0, nowSec - g.last_update);
  if (g.status === "stale" || age > g.stale_after_seconds) return { status: "stale", age };
  return { status: age <= FRESH_SECONDS ? "live" : "delayed", age };
}

export function GsiBadge({ status, testId }: { status: GsiStatus; testId?: string }) {
  const s = GSI_STATUS[status];
  return (
    <span data-testid={testId} data-status={status} className={cx("inline-flex items-center gap-2 text-sm font-medium", s.tone)}>
      <span className={cx("h-2 w-2 rounded-full", s.dot, status === "live" && "animate-pulse")} />{s.label}
    </span>
  );
}

export function gameClock(seconds: number | null | undefined): string | null {
  if (seconds === null || seconds === undefined) return null;
  const neg = seconds < 0;
  const s = Math.abs(Math.floor(seconds));
  return `${neg ? "-" : ""}${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

export function prettyId(internal: string | null): string {
  if (!internal) return "—";
  return internal.replace(/^item_/, "").replace(/_/g, " ");
}
