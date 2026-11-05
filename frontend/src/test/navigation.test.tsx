import { fireEvent, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AppRoutes } from "../App";
import { Layout, NAV } from "../components/Layout";
import { routes } from "./fixtures";
import { mockFetch, renderWithProviders } from "./utils";

describe("navigation", () => {
  it("lists only implemented pages", () => {
    mockFetch(routes());
    renderWithProviders(<Layout><AppRoutes /></Layout>);
    const nav = screen.getByRole("navigation", { name: "Основная навигация" });
    expect(NAV.map((n) => n.label)).toEqual(["Обзор", "Логи", "Настройки"]);
    for (const item of NAV) expect(nav).toHaveTextContent(item.label);
    expect(nav).not.toHaveTextContent("Players");
  });

  it.each([["Логи", "Логи"], ["Настройки", "Настройки"], ["Обзор", "Обзор"]])("navigates to %s", async (link, heading) => {
    mockFetch(routes());
    renderWithProviders(<Layout><AppRoutes /></Layout>, "/logs");
    fireEvent.click(screen.getByRole("link", { name: link }));
    expect(await screen.findByRole("heading", { level: 1, name: heading })).toBeInTheDocument();
  });

  it("shows the websocket connection state", async () => {
    mockFetch(routes());
    renderWithProviders(<Layout><AppRoutes /></Layout>);
    expect(await screen.findByText("Связь установлена")).toBeInTheDocument();
  });

  it("renders a not-found message for unknown routes", () => {
    mockFetch(routes());
    renderWithProviders(<AppRoutes />, "/players");
    expect(screen.getByText("Страница не найдена.")).toBeInTheDocument();
  });
});
