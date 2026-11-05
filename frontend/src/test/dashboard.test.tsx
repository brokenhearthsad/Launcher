import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import Dashboard, { formatUptime } from "../pages/Dashboard";
import { routes } from "./fixtures";
import { mockFetch, renderWithProviders } from "./utils";

describe("Dashboard", () => {
  it("shows launcher status and own resource usage", async () => {
    mockFetch(routes());
    renderWithProviders(<Dashboard />);
    expect(await screen.findByText("Работает")).toBeInTheDocument();
    expect(await screen.findByText("55.1 МБ")).toBeInTheDocument();
    expect(screen.getByText("0.12 %")).toBeInTheDocument();
    expect(await screen.findByText("backups/match_lab-pre-0002.db")).toBeInTheDocument();
    expect(screen.getByText("Предупреждений нет.")).toBeInTheDocument();
  });

  it("lists recent warnings", async () => {
    mockFetch(routes([[/GET \/api\/logs\?/, { items: [{ id: 1, level: "WARNING", component: "db", message: "disk slow", timestamp: "2026-01-01T00:00:00Z" }], total: 1, page: 1, page_size: 5 }]]));
    renderWithProviders(<Dashboard />);
    expect(await screen.findByText("disk slow")).toBeInTheDocument();
  });

  it("shows an error banner when the backend is down", async () => {
    mockFetch([]);
    renderWithProviders(<Dashboard />);
    expect((await screen.findAllByRole("alert"))[0]).toHaveTextContent("no mock");
  });

  it("formats uptime", () => {
    expect(formatUptime(42)).toBe("42 с");
    expect(formatUptime(125)).toBe("2 мин 5 с");
    expect(formatUptime(3725)).toBe("1 ч 2 мин");
  });
});
