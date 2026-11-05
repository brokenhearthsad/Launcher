import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { fmt, fmtRate, formatDuration, NO_DATA, Sparkline } from "../components/metrics";
import { MonitoringProvider } from "../hooks/Monitoring";
import Dashboard from "../pages/Dashboard";
import Slots from "../pages/Slots";
import SteamDota from "../pages/SteamDota";
import SystemPage from "../pages/System";
import { ENV, METRICS, routes } from "./fixtures";
import { FakeWebSocket, mockFetch, renderWithProviders } from "./utils";

const withMon = (ui: JSX.Element) => <MonitoringProvider>{ui}</MonitoringProvider>;

describe("metric formatting", () => {
  it("never invents values", () => {
    expect(fmt(null, "%")).toBe(NO_DATA);
    expect(fmt(undefined)).toBe(NO_DATA);
    expect(fmt(42, "%")).toBe("42 %");
    expect(fmtRate(null)).toBe(NO_DATA);
    expect(fmtRate(2048)).toBe("2 МБ/с");
    expect(formatDuration(3725)).toBe("1 ч 2 мин");
  });

  it("sparkline needs real points", () => {
    const { rerender, container } = renderWithProviders(<Sparkline values={[null, 5]} testId="s" />);
    expect(screen.getByTestId("s")).toHaveTextContent("недостаточно точек");
    rerender(<Sparkline values={[1, null, 3, 4]} testId="s" />);
    expect(container.querySelectorAll("polyline")).toHaveLength(2); // gap splits the line
  });
});

describe("System page", () => {
  it("shows real metrics and 'Нет данных' for unavailable sources", async () => {
    mockFetch(routes());
    renderWithProviders(withMon(<SystemPage />));
    const meters = await screen.findByTestId("system-meters");
    expect(within(meters).getByText("13 %")).toBeInTheDocument(); // 12.5 rounded
    expect(within(screen.getByTestId("meter-GPU")).getByText(NO_DATA)).toBeInTheDocument();
    expect(screen.getByTestId("cpu-temp")).toHaveTextContent(NO_DATA);
    expect(screen.getByTestId("gpu-temp")).toHaveTextContent(NO_DATA);
    const disks = screen.getByTestId("disks-table");
    expect(disks).toHaveTextContent("212 ГБ");
    expect(disks).toHaveTextContent(`${NO_DATA} (диск не найден)`);
    expect(screen.getByTestId("net-rx")).toHaveTextContent("2 МБ/с");
    expect(screen.getByTestId("per-core").children).toHaveLength(4);
  });

  it("updates from WebSocket pushes", async () => {
    FakeWebSocket.instances = [];
    mockFetch(routes());
    renderWithProviders(withMon(<SystemPage />));
    await screen.findByTestId("system-meters");
    await waitFor(() => expect(FakeWebSocket.instances.length).toBe(1));
    act(() => FakeWebSocket.instances[0].emit({ type: "metrics_updated", session_id: null,
      data: { ...METRICS, cpu: { ...METRICS.cpu, percent: 77 }, gpu: { available: true, source: "nvml", name: "RTX 3050",
        util_percent: 55, mem_used_mb: 2048, mem_total_mb: 8192, temp_c: 61, power_w: 70 } } }));
    expect(await within(screen.getByTestId("system-meters")).findByText("77 %")).toBeInTheDocument();
    expect(screen.getByTestId("gpu-temp")).toHaveTextContent("61 °C");
  });
});

describe("Steam & Dota page", () => {
  it("shows installation and process state", async () => {
    mockFetch(routes());
    renderWithProviders(withMon(<SteamDota />));
    expect(await screen.findByTestId("steam-info")).toHaveTextContent("реестр Windows");
    expect(screen.getByTestId("steam-info")).toHaveTextContent("выполнен");
    expect(screen.getByTestId("dota-info")).toHaveTextContent("20512345");
    expect(screen.getByTestId("proc-steam.exe")).toHaveTextContent("4321");
    expect(screen.getByTestId("proc-steam.exe")).toHaveTextContent("1 ч 2 мин");
    expect(screen.getByText(/Launcher не запускает и не закрывает игры/)).toBeInTheDocument();
  });

  it("reports missing installations", async () => {
    mockFetch(routes([[/GET \/api\/environment/, { ...ENV, steam: { installed: false, signed_in: null, error: "Steam installation not found",
      process: { running: false } }, dota: { installed: false, process: { running: false } } }]]));
    renderWithProviders(withMon(<SteamDota />));
    expect(await screen.findByText("Не найден")).toBeInTheDocument();
    expect(screen.getByText("Не найдена")).toBeInTheDocument();
  });
});

describe("Slots page", () => {
  it("renders ten slots split into teams", async () => {
    mockFetch(routes());
    renderWithProviders(<Slots />);
    expect(await screen.findByTestId("slot-10")).toBeInTheDocument();
    expect(screen.getByTestId("slots-radiant").children).toHaveLength(5);
    expect(screen.getByTestId("slots-dire").children).toHaveLength(5);
    expect(screen.getByTestId("slot-status-1")).toHaveTextContent("Steam запущен");
    expect(screen.getByTestId("slot-1")).toHaveTextContent("steam PID 4321");
  });

  it("edits name, note and binding", async () => {
    const calls = mockFetch(routes([[/PUT \/api\/slots\/2/, { id: 2 }]]));
    renderWithProviders(<Slots />);
    fireEvent.click(await screen.findByLabelText("Изменить слот 2"));
    fireEvent.change(screen.getByTestId("slot-name"), { target: { value: "Тест" } });
    fireEvent.change(screen.getByTestId("slot-note"), { target: { value: "заметка" } });
    fireEvent.click(screen.getByTestId("slot-bind"));
    fireEvent.click(screen.getByTestId("slot-save"));
    await waitFor(() => expect(calls.some((c) => c.init?.method === "PUT")).toBe(true));
    expect(JSON.parse(String(calls.find((c) => c.init?.method === "PUT")!.init!.body)))
      .toEqual({ name: "Тест", note: "заметка", binding: "local_client" });
  });

  it("shows the server's reason when a second slot is bound", async () => {
    mockFetch(routes([[/PUT \/api\/slots\/3/, new Response(JSON.stringify({ error: { code: "conflict",
      message: "локальный клиент уже привязан к слоту «Slot 1» (#1)" } }), { status: 409 })]]));
    renderWithProviders(<Slots />);
    fireEvent.click(await screen.findByLabelText("Изменить слот 3"));
    fireEvent.click(screen.getByTestId("slot-bind"));
    fireEvent.click(screen.getByTestId("slot-save"));
    expect(await screen.findByRole("alert")).toHaveTextContent("уже привязан");
  });
});

describe("Overview", () => {
  it("summarises machine, Steam/Dota and the bound slot", async () => {
    mockFetch(routes());
    renderWithProviders(withMon(<Dashboard />));
    expect(await within(await screen.findByTestId("overview-machine")).findByText("13 %")).toBeInTheDocument();
    const env = await screen.findByTestId("overview-env");
    await waitFor(() => expect(env).toHaveTextContent("запущен"));
    expect(env).toHaveTextContent("остановлена");
    expect(await screen.findByText(/Слот «Slot 1»: Steam запущен/)).toBeInTheDocument();
  });
});
