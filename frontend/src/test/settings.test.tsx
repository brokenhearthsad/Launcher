import { fireEvent, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import SettingsPage from "../pages/Settings";
import { routes } from "./fixtures";
import { mockFetch, renderWithProviders } from "./utils";

describe("Settings", () => {
  it("saves runtime settings", async () => {
    const calls = mockFetch(routes([[/PUT \/api\/settings/, { ws_publish_hz: 4, ui_refresh_seconds: 12, log_level: "INFO", db_log_level: "INFO" }]]));
    renderWithProviders(<SettingsPage />);
    fireEvent.change(await screen.findByTestId("ui-refresh"), { target: { value: "12" } });
    fireEvent.click(screen.getByTestId("save-settings"));
    await waitFor(() => expect(calls.some((c) => c.init?.method === "PUT")).toBe(true));
    const body = JSON.parse(String(calls.find((c) => c.init?.method === "PUT")!.init!.body));
    expect(body.ui_refresh_seconds).toBe(12);
  });

  it("asks for confirmation and sends the guard header on shutdown", async () => {
    const calls = mockFetch(routes([[/POST \/api\/system\/shutdown/, { status: "stopping" }]]));
    renderWithProviders(<SettingsPage />);
    fireEvent.click(await screen.findByTestId("shutdown"));
    expect(calls.some((c) => c.url.includes("shutdown"))).toBe(false);
    fireEvent.click(screen.getByRole("button", { name: "Остановить" }));
    expect(await screen.findByText(/корректно завершил работу/)).toBeInTheDocument();
    const call = calls.find((c) => c.url.includes("shutdown"))!;
    expect((call.init!.headers as Record<string, string>)["X-Launcher-Request"]).toBe("1");
  });
});
