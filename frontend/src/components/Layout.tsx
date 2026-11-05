import {
  Activity, BarChart3, Bot, Cpu, FileText, History, LayoutDashboard, Menu, Radio, Settings, Swords, Users, X,
} from "lucide-react";
import { useState, type ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { useLive } from "../hooks/LiveEvents";
import { cx } from "./ui";

export const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/players", label: "Players", icon: Users },
  { to: "/bots", label: "Bot Configuration", icon: Bot },
  { to: "/match-control", label: "Match Control", icon: Swords },
  { to: "/live", label: "Live Match", icon: Radio },
  { to: "/analytics", label: "Analytics", icon: BarChart3 },
  { to: "/history", label: "Match History", icon: History },
  { to: "/logs", label: "Logs", icon: FileText },
  { to: "/settings", label: "Settings", icon: Settings },
];

function ConnectionIndicator() {
  const { state } = useLive();
  const map = {
    open: ["bg-emerald-400", "Live connection"],
    connecting: ["bg-amber-400 animate-pulse", "Connecting…"],
    closed: ["bg-red-500", "Disconnected — retrying"],
  } as const;
  const [color, text] = map[state];
  return (
    <div data-testid="ws-status" data-state={state} className="flex items-center gap-2 text-xs text-gray-400">
      <span className={cx("h-2 w-2 rounded-full", color)} /> {text}
    </div>
  );
}

export function Layout({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="flex min-h-screen bg-[radial-gradient(ellipse_at_top_left,_#1f2937_0%,_#030712_55%)]">
      <aside className={cx(
        "fixed inset-y-0 left-0 z-40 w-64 transform border-r border-surface-border bg-gray-950/95 backdrop-blur transition md:static md:translate-x-0",
        open ? "translate-x-0" : "-translate-x-full",
      )}>
        <div className="flex items-center gap-3 border-b border-surface-border px-5 py-5">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-dire to-accent">
            <Cpu className="h-5 w-5 text-gray-950" />
          </div>
          <div>
            <div className="font-bold leading-tight">Dota 2 Match Lab</div>
            <div className="text-[11px] uppercase tracking-widest text-gray-500">5v5 bot simulator</div>
          </div>
          <button type="button" className="ml-auto md:hidden" aria-label="Close menu" onClick={() => setOpen(false)}><X className="h-5 w-5" /></button>
        </div>
        <nav className="space-y-1 p-3" aria-label="Main navigation">
          {NAV.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to} to={to} end={to === "/"} onClick={() => setOpen(false)}
              className={({ isActive }) => cx(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition",
                isActive ? "bg-accent/15 text-accent" : "text-gray-300 hover:bg-surface-raised hover:text-white",
              )}
            >
              <Icon className="h-4 w-4" /> {label}
            </NavLink>
          ))}
        </nav>
        <div className="absolute bottom-0 w-full border-t border-surface-border p-4">
          <ConnectionIndicator />
          <p className="mt-2 text-[11px] leading-snug text-gray-600">
            Matches run in the local simulator. They are not real Dota 2 games.
          </p>
        </div>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-3 border-b border-surface-border px-4 py-3 md:hidden">
          <button type="button" aria-label="Open menu" onClick={() => setOpen(true)}><Menu className="h-5 w-5" /></button>
          <span className="font-semibold">Dota 2 Match Lab</span>
          <Activity className="ml-auto h-4 w-4 text-accent" />
        </header>
        <main className="mx-auto w-full max-w-[1500px] flex-1 p-4 md:p-8">{children}</main>
      </div>
    </div>
  );
}
