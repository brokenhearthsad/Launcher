import { AlertTriangle, Loader2, X } from "lucide-react";
import { useEffect, type ButtonHTMLAttributes, type ReactNode } from "react";
import { titleCase } from "../lib/format";

export function cx(...c: (string | false | null | undefined)[]) {
  return c.filter(Boolean).join(" ");
}

export function Card({ title, actions, children, className, icon }: {
  title?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string; icon?: ReactNode;
}) {
  return (
    <section className={cx("rounded-xl border border-surface-border bg-surface/80 shadow-lg shadow-black/20", className)}>
      {(title || actions) && (
        <header className="flex items-center justify-between gap-2 border-b border-surface-border px-4 py-3">
          <h2 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-gray-300">
            {icon}
            {title}
          </h2>
          <div className="flex items-center gap-2">{actions}</div>
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}

export function StatCard({ label, value, hint, icon, tone = "default" }: {
  label: string; value: ReactNode; hint?: ReactNode; icon?: ReactNode;
  tone?: "default" | "radiant" | "dire" | "accent" | "danger";
}) {
  const tones = {
    default: "text-gray-100", radiant: "text-radiant", dire: "text-dire", accent: "text-accent", danger: "text-red-400",
  };
  return (
    <div className="rounded-xl border border-surface-border bg-surface/80 p-4">
      <div className="flex items-center justify-between text-xs uppercase tracking-wide text-gray-400">
        <span>{label}</span>
        {icon}
      </div>
      <div className={cx("mt-2 text-2xl font-bold", tones[tone])}>{value}</div>
      {hint && <div className="mt-1 text-xs text-gray-500">{hint}</div>}
    </div>
  );
}

type Variant = "primary" | "secondary" | "danger" | "ghost" | "success";

export function Button({ variant = "secondary", loading, className, children, ...rest }:
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; loading?: boolean }) {
  const styles: Record<Variant, string> = {
    primary: "bg-accent text-gray-950 hover:bg-amber-400",
    secondary: "bg-surface-raised text-gray-100 border border-surface-border hover:bg-gray-700",
    danger: "bg-red-600 text-white hover:bg-red-500",
    success: "bg-emerald-600 text-white hover:bg-emerald-500",
    ghost: "text-gray-300 hover:bg-surface-raised",
  };
  return (
    <button
      type="button"
      className={cx(
        "inline-flex items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition",
        "disabled:cursor-not-allowed disabled:opacity-50",
        styles[variant], className,
      )}
      disabled={loading || rest.disabled}
      {...rest}
    >
      {loading && <Loader2 className="h-4 w-4 animate-spin" />}
      {children}
    </button>
  );
}

const STATUS_STYLES: Record<string, string> = {
  ready: "bg-emerald-900/60 text-emerald-300 border-emerald-700",
  running: "bg-sky-900/60 text-sky-300 border-sky-700",
  paused: "bg-amber-900/60 text-amber-300 border-amber-700",
  error: "bg-red-900/60 text-red-300 border-red-700",
  finished: "bg-violet-900/60 text-violet-300 border-violet-700",
  offline: "bg-gray-800 text-gray-400 border-gray-700",
  created: "bg-gray-800 text-gray-300 border-gray-600",
  stopped: "bg-orange-900/60 text-orange-300 border-orange-700",
};

export function StatusBadge({ status }: { status: string }) {
  return (
    <span data-testid="status-badge" className={cx("inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium",
      STATUS_STYLES[status] ?? STATUS_STYLES.offline)}>
      <span className={cx("h-1.5 w-1.5 rounded-full", status === "running" ? "animate-pulse bg-sky-300" : "bg-current")} />
      {titleCase(status)}
    </span>
  );
}

export function TeamBadge({ team }: { team: string | null | undefined }) {
  if (!team) return <span className="text-gray-500">—</span>;
  return (
    <span className={cx("rounded px-2 py-0.5 text-xs font-semibold uppercase",
      team === "radiant" ? "bg-radiant-soft text-radiant" : "bg-dire-soft text-dire")}>
      {team}
    </span>
  );
}

export function Slider({ label, value, onChange, min = 0, max = 1, step = 0.05, hint, disabled }: {
  label: string; value: number; onChange: (v: number) => void; min?: number; max?: number; step?: number;
  hint?: string; disabled?: boolean;
}) {
  const id = `slider-${label.replace(/\s+/g, "-").toLowerCase()}`;
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs">
        <label htmlFor={id} className="text-gray-300">{label}</label>
        <span className="font-mono text-accent">{Math.round(value * 100)}%</span>
      </div>
      <input
        id={id} type="range" min={min} max={max} step={step} value={value} disabled={disabled}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full accent-amber-500"
      />
      {hint && <p className="text-[11px] text-gray-500">{hint}</p>}
    </div>
  );
}

export function Select({ label, value, onChange, options, disabled, testId }: {
  label?: string; value: string; onChange: (v: string) => void;
  options: { value: string; label: string; disabled?: boolean }[]; disabled?: boolean; testId?: string;
}) {
  return (
    <label className="block space-y-1 text-xs text-gray-300">
      {label && <span>{label}</span>}
      <select
        data-testid={testId} value={value} disabled={disabled} onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-lg border border-surface-border bg-gray-900 px-2 py-2 text-sm text-gray-100 focus:border-accent focus:outline-none disabled:opacity-50"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value} disabled={o.disabled}>{o.label}</option>
        ))}
      </select>
    </label>
  );
}

export function TextInput({ label, value, onChange, type = "text", min, max, placeholder, testId }: {
  label?: string; value: string | number; onChange: (v: string) => void; type?: string; min?: number; max?: number;
  placeholder?: string; testId?: string;
}) {
  return (
    <label className="block space-y-1 text-xs text-gray-300">
      {label && <span>{label}</span>}
      <input
        data-testid={testId} type={type} value={value} min={min} max={max} placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-lg border border-surface-border bg-gray-900 px-2 py-2 text-sm text-gray-100 focus:border-accent focus:outline-none"
      />
    </label>
  );
}

export function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="flex cursor-pointer items-center justify-between gap-3 text-sm text-gray-300">
      <span>{label}</span>
      <button
        type="button" role="switch" aria-checked={checked} aria-label={label} onClick={() => onChange(!checked)}
        className={cx("relative h-6 w-11 rounded-full transition", checked ? "bg-accent" : "bg-gray-700")}
      >
        <span className={cx("absolute top-0.5 h-5 w-5 rounded-full bg-white transition", checked ? "left-5" : "left-0.5")} />
      </button>
    </label>
  );
}

export function Modal({ open, title, onClose, children, footer, wide }: {
  open: boolean; title: string; onClose: () => void; children: ReactNode; footer?: ReactNode; wide?: boolean;
}) {
  useEffect(() => {
    if (!open) return;
    const h = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" role="dialog" aria-modal="true" aria-label={title}>
      <div className={cx("max-h-[90vh] w-full overflow-y-auto rounded-xl border border-surface-border bg-gray-900 shadow-2xl",
        wide ? "max-w-5xl" : "max-w-lg")}>
        <div className="flex items-center justify-between border-b border-surface-border px-4 py-3">
          <h3 className="font-semibold">{title}</h3>
          <button type="button" aria-label="Close" onClick={onClose} className="text-gray-400 hover:text-white"><X className="h-5 w-5" /></button>
        </div>
        <div className="p-4">{children}</div>
        {footer && <div className="flex justify-end gap-2 border-t border-surface-border px-4 py-3">{footer}</div>}
      </div>
    </div>
  );
}

export function ConfirmDialog({ open, title, message, confirmLabel = "Confirm", onConfirm, onCancel, danger }: {
  open: boolean; title: string; message: ReactNode; confirmLabel?: string; onConfirm: () => void; onCancel: () => void;
  danger?: boolean;
}) {
  return (
    <Modal open={open} title={title} onClose={onCancel} footer={
      <>
        <Button onClick={onCancel}>Cancel</Button>
        <Button variant={danger ? "danger" : "primary"} onClick={onConfirm}>{confirmLabel}</Button>
      </>
    }>
      <div className="text-sm text-gray-300">{message}</div>
    </Modal>
  );
}

export function ErrorBanner({ error, onRetry }: { error: { message: string } | null | undefined; onRetry?: () => void }) {
  if (!error) return null;
  return (
    <div role="alert" className="flex items-center justify-between gap-3 rounded-lg border border-red-800 bg-red-950/60 px-4 py-3 text-sm text-red-200">
      <span className="flex items-center gap-2"><AlertTriangle className="h-4 w-4" />{error.message}</span>
      {onRetry && <Button variant="ghost" onClick={onRetry}>Retry</Button>}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="rounded-lg border border-dashed border-surface-border p-6 text-center text-sm text-gray-500">{children}</div>;
}

export function Spinner({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 p-4 text-sm text-gray-400">
      <Loader2 className="h-4 w-4 animate-spin" /> {label}
    </div>
  );
}

export function Pagination({ page, pageSize, total, onPage }: { page: number; pageSize: number; total: number; onPage: (p: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  return (
    <div className="flex items-center justify-between pt-3 text-xs text-gray-400">
      <span>{total} total · page {page} / {pages}</span>
      <div className="flex gap-2">
        <Button variant="ghost" disabled={page <= 1} onClick={() => onPage(page - 1)}>Previous</Button>
        <Button variant="ghost" disabled={page >= pages} onClick={() => onPage(page + 1)}>Next</Button>
      </div>
    </div>
  );
}

export function Table({ head, children, testId }: { head: ReactNode[]; children: ReactNode; testId?: string }) {
  return (
    <div className="overflow-x-auto">
      <table data-testid={testId} className="w-full text-left text-sm">
        <thead className="border-b border-surface-border text-xs uppercase tracking-wide text-gray-400">
          <tr>{head.map((h, i) => <th key={i} className="px-3 py-2 font-medium">{h}</th>)}</tr>
        </thead>
        <tbody className="divide-y divide-surface-border/60">{children}</tbody>
      </table>
    </div>
  );
}

export function Bar({ value, max, color }: { value: number; max: number; color: string }) {
  const pctv = max > 0 ? Math.max(0, Math.min(100, (value / max) * 100)) : 0;
  return (
    <div className="h-1.5 w-full overflow-hidden rounded bg-gray-800">
      <div className={cx("h-full rounded transition-all", color)} style={{ width: `${pctv}%` }} />
    </div>
  );
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-gray-400">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}
