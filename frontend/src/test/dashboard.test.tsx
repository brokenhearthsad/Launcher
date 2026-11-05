import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import Dashboard from "../pages/Dashboard";
import { OVERVIEW, SESSION } from "./fixtures";
import { mockFetch, renderWithProviders } from "./utils";

describe("Dashboard", () => {
  it("shows system indicators from the backend", async () => {
    mockFetch([
      [/\/api\/health/, { status: "ok", version: "1.0.0", database: "ok", active_sessions: 1, websocket_clients: 1, uptime_seconds: 3 }],
      [/\/api\/analytics\/overview/, OVERVIEW],
      [/\/api\/analytics\/sessions/, [{ session_id: 1, duration_minutes: 35 }]],
      [/\/api\/sessions/, { items: [SESSION], total: 1, page: 1, page_size: 10 }],
    ]);
    renderWithProviders(<Dashboard />);
    expect(await screen.findByText("Online")).toBeInTheDocument();
    expect(screen.getByText("5 Radiant · 5 Dire")).toBeInTheDocument();
    expect(screen.getByText("35m 00s")).toBeInTheDocument();
    expect(screen.getByText("Last one", { exact: false })).toBeInTheDocument();
    expect(await screen.findByText("Watch live →")).toHaveAttribute("href", "/live/3");
  });

  it("shows an error banner when the backend is down", async () => {
    mockFetch([]);
    renderWithProviders(<Dashboard />);
    expect(await screen.findByRole("alert")).toHaveTextContent("no mock");
  });
});
