import { fireEvent, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AppRoutes } from "../App";
import { Layout, NAV } from "../components/Layout";
import { META, OVERVIEW, SESSION, players } from "./fixtures";
import { mockFetch, renderWithProviders } from "./utils";

function routes() {
  mockFetch([
    [/GET \/api\/meta/, META], [/GET \/api\/players/, players()], [/GET \/api\/health/, { status: "ok", version: "1", database: "ok" }],
    [/GET \/api\/analytics\/overview/, OVERVIEW], [/GET \/api\/analytics\/(players|sessions)/, []],
    [/GET \/api\/analytics\/teams/, []], [/GET \/api\/sessions\/3$/, { ...SESSION, participants: [], live: null }],
    [/GET \/api\/sessions/, { items: [SESSION], total: 1, page: 1, page_size: 10 }],
    [/GET \/api\/matches\/history/, { items: [], total: 0, page: 1, page_size: 15 }],
    [/GET \/api\/logs\/components/, ["session"]], [/GET \/api\/logs/, { items: [], total: 0, page: 1, page_size: 50 }],
    [/GET \/api\/settings/, { runtime: { default_speed: 20, max_game_seconds: 3600, snapshot_interval: 60, tick_seconds: 0.5, ws_publish_hz: 4, ui_refresh_seconds: 5, log_level: "INFO", db_log_level: "INFO", max_concurrent_sessions: 2, persist_ability_events: true }, backend: { version: "1", host: "127.0.0.1", port: 8000, cors_origins: [], api_rate_limit_per_minute: 240, log_dir: "logs" }, database: { url: "sqlite://", dialect: "sqlite", size_bytes: 1000 } }],
  ]);
}

describe("navigation", () => {
  it("has a link for every page", () => {
    routes();
    renderWithProviders(<Layout><AppRoutes /></Layout>);
    const nav = screen.getByRole("navigation", { name: "Main navigation" });
    for (const item of NAV) expect(nav).toHaveTextContent(item.label);
  });

  it.each([
    ["Players", "Players"], ["Bot Configuration", "Bot Configuration"], ["Match Control", "Match Control"],
    ["Live Match", "Live Match"], ["Analytics", "Analytics"], ["Match History", "Match History"], ["Logs", "Logs"], ["Settings", "Settings"],
  ])("navigates to %s", async (link, heading) => {
    routes();
    renderWithProviders(<Layout><AppRoutes /></Layout>);
    fireEvent.click(screen.getByRole("link", { name: link }));
    expect(await screen.findByRole("heading", { level: 1, name: heading })).toBeInTheDocument();
  });

  it("shows the websocket connection state", async () => {
    routes();
    renderWithProviders(<Layout><AppRoutes /></Layout>);
    expect(await screen.findByText("Live connection")).toBeInTheDocument();
  });
});
