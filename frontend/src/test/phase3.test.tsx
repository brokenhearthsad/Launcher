import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { gameClock, liveStatus } from "../components/gsi";
import { NO_DATA } from "../components/metrics";
import { MonitoringProvider } from "../hooks/Monitoring";
import Dashboard from "../pages/Dashboard";
import GameState from "../pages/GameState";
import { GSI_CONFIG, gsiState, routes } from "./fixtures";
import { FakeWebSocket, mockFetch, renderWithProviders } from "./utils";

const page = () => <MonitoringProvider><GameState /></MonitoringProvider>;

describe("GSI helpers", () => {
  it("derives freshness from the age of the last update", () => {
    const now = 1000;
    expect(liveStatus(null, now).status).toBe("waiting");
    const g = gsiState({ last_update: now - 2 }) as never;
    expect(liveStatus(g, now)).toEqual({ status: "live", age: 2 });
    expect(liveStatus(gsiState({ last_update: now - 20 }) as never, now).status).toBe("delayed");
    expect(liveStatus(gsiState({ last_update: now - 41 }) as never, now).status).toBe("stale");
    expect(liveStatus(gsiState({ status: "stale", last_update: now - 1 }) as never, now).status).toBe("stale");
  });

  it("formats the game clock including negative pre-horn time", () => {
    expect(gameClock(664)).toBe("11:04");
    expect(gameClock(-75)).toBe("-1:15");
    expect(gameClock(null)).toBeNull();
  });
});

describe("Game state page", () => {
  it("waits for GSI without inventing data", async () => {
    mockFetch(routes());
    renderWithProviders(page());
    expect(await screen.findByTestId("gsi-status")).toHaveAttribute("data-status", "waiting");
    expect(screen.getByText(/Данные от Dota 2 ещё не приходили/)).toBeInTheDocument();
    expect(screen.getByTestId("gsi-last")).toHaveTextContent(NO_DATA);
  });

  it("shows live game, hero and score; missing mana is 'Нет данных'", async () => {
    mockFetch(routes([[/GET \/api\/gsi\/state/, gsiState()]]));
    renderWithProviders(page());
    expect(await screen.findByTestId("gsi-game")).toHaveTextContent("Игра идёт");
    expect(screen.getByTestId("gsi-game")).toHaveTextContent("11:04");
    expect(screen.getByTestId("gsi-score")).toHaveTextContent("7 : 4");
    expect(screen.getByTestId("gsi-game")).toHaveTextContent("название режима GSI не передаёт");
    const hero = screen.getByTestId("gsi-hero");
    expect(hero).toHaveTextContent("Anti-Mage");
    expect(screen.getByTestId("gsi-hp")).toHaveTextContent("812 / 1210");
    expect(hero).toHaveTextContent(`Мана${NO_DATA}`);
    expect(screen.getByTestId("gsi-abilities")).toHaveTextContent("antimage blink");
    expect(screen.getByTestId("gsi-items")).toHaveTextContent("power treads");
    expect(screen.getByTestId("gsi-status")).toHaveAttribute("data-status", "live");
  });

  it("hides data when stale", async () => {
    mockFetch(routes([[/GET \/api\/gsi\/state/, gsiState({ status: "stale", freshness: "stale", last_update: Date.now() / 1000 - 120 })]]));
    renderWithProviders(page());
    expect(await screen.findByTestId("gsi-status")).toHaveAttribute("data-status", "stale");
    expect(screen.queryByTestId("gsi-hero")).toBeNull();
    expect(screen.getByTestId("gsi-freshness")).toHaveTextContent("устарели");
  });

  it("updates from gsi_updated pushes", async () => {
    FakeWebSocket.instances = [];
    mockFetch(routes());
    renderWithProviders(page());
    await screen.findByTestId("gsi-status");
    await waitFor(() => expect(FakeWebSocket.instances.length).toBe(1));
    act(() => FakeWebSocket.instances[0].emit({ type: "gsi_updated", session_id: null, data: gsiState() }));
    expect(await screen.findByTestId("gsi-hero")).toHaveTextContent("Anti-Mage");
  });
});

describe("GSI installer", () => {
  it("shows the plan and installs only after explicit agreement", async () => {
    const calls = mockFetch(routes([[/POST \/api\/gsi\/install/, { changed: true, backup: null, check: { ...GSI_CONFIG, installed: true, up_to_date: true,
      exists: true, managed: true, plan: { ...GSI_CONFIG.plan, action: "none" } } }]]));
    renderWithProviders(page());
    expect(await screen.findByTestId("launch-option")).toHaveTextContent("-gamestateintegration");
    expect(screen.getByTestId("gsi-config")).toHaveTextContent("gamestate_integration_obs.cfg — не изменяются");
    expect(screen.getByTestId("gsi-uninstall")).toBeDisabled();
    fireEvent.click(screen.getByTestId("gsi-install"));
    const preview = screen.getByTestId("gsi-preview");
    expect(preview).toHaveTextContent("Будет создан новый файл");
    expect(within(preview).getByText(/••••••••abcd/)).toBeInTheDocument();
    expect(screen.getByTestId("gsi-confirm")).toBeDisabled();
    expect(calls.some((c) => c.url.includes("/install"))).toBe(false);
    fireEvent.click(screen.getByTestId("gsi-agree"));
    fireEvent.click(screen.getByTestId("gsi-confirm"));
    expect(await screen.findByRole("status")).toHaveTextContent("Конфигурация установлена");
    const call = calls.find((c) => c.url.includes("/install"))!;
    expect(JSON.parse(String(call.init!.body))).toEqual({ plan_id: "a".repeat(128), confirm: true });
    expect((call.init!.headers as Record<string, string>)["X-Launcher-Request"]).toBe("1");
    expect(screen.getByTestId("gsi-config")).toHaveTextContent("установлена и актуальна");
  });

  it("restores a backup after confirmation", async () => {
    const calls = mockFetch(routes([[/POST \/api\/gsi\/restore/, { restored: "x", backup: null, check: GSI_CONFIG }]]));
    renderWithProviders(page());
    fireEvent.click(await screen.findByLabelText("Восстановить 20261105-120000-before_install.cfg"));
    expect(calls.some((c) => c.url.includes("/restore"))).toBe(false);
    fireEvent.click(screen.getByRole("button", { name: "Восстановить" }));
    await waitFor(() => expect(calls.some((c) => c.url.includes("/restore"))).toBe(true));
    expect(JSON.parse(String(calls.find((c) => c.url.includes("/restore"))!.init!.body)))
      .toEqual({ name: "20261105-120000-before_install.cfg", confirm: true });
  });

  it("explains when Dota 2 is not found", async () => {
    mockFetch(routes([[/GET \/api\/gsi\/config/, { ...GSI_CONFIG, available: false, error: "Dota 2 не найдена", plan: null }]]));
    renderWithProviders(page());
    expect(await screen.findByText("Dota 2 не найдена")).toBeInTheDocument();
  });
});

describe("Overview game card", () => {
  it("shows a compact game summary", async () => {
    mockFetch(routes([[/GET \/api\/gsi\/state/, gsiState()]]));
    renderWithProviders(<MonitoringProvider><Dashboard /></MonitoringProvider>);
    const card = await screen.findByTestId("overview-game");
    await waitFor(() => expect(card).toHaveTextContent("Anti-Mage, ур. 11"));
    expect(card).toHaveTextContent("Игра идёт");
    expect(card).toHaveTextContent("7:4");
  });
});
