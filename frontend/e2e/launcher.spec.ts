import { expect, test } from "@playwright/test";

test("dashboard is served by FastAPI and shows launcher status", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Обзор" })).toBeVisible();
  await expect(page.getByText("Работает")).toBeVisible();
  await expect(page.getByTestId("ws-status")).toHaveAttribute("data-state", "open");
  await expect(page.getByTestId("components")).toContainText("frontend/dist");
});

test("client-side routes survive a reload (SPA fallback)", async ({ page }) => {
  await page.goto("/logs");
  await expect(page.getByRole("heading", { name: "Логи" })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { name: "Логи" })).toBeVisible();
  await expect(page.getByTestId("logs-table")).toContainText("Launcher");
});

test("settings persist", async ({ page }) => {
  await page.goto("/settings");
  const input = page.getByTestId("ui-refresh");
  const target = (await input.inputValue()) === "7" ? "5" : "7";
  await input.fill(target);
  await page.getByTestId("save-settings").click();
  await expect(page.getByRole("status")).toContainText("сохранены");
  await page.reload();
  await expect(page.getByTestId("ui-refresh")).toHaveValue(target);
});

test("system page shows live metrics or explicit 'Нет данных'", async ({ page }) => {
  await page.goto("/system");
  await expect(page.getByRole("heading", { name: "Система" })).toBeVisible();
  await expect(page.getByTestId("meter-CPU")).toContainText("%");
  await expect(page.getByTestId("disks-table")).toBeVisible();
  // CPU temperature without LibreHardwareMonitor is never invented
  await expect(page.getByTestId("cpu-temp")).toHaveText(/Нет данных|°C/);
});

test("Steam and Dota 2 page reports installation state", async ({ page }) => {
  await page.goto("/steam");
  await expect(page.getByTestId("steam-info")).toBeVisible();
  await expect(page.getByTestId("dota-info")).toBeVisible();
  await expect(page.getByText("Launcher не запускает и не закрывает игры").first()).toBeVisible();
});

test("ten slots: rename persists and appears in history", async ({ page }) => {
  await page.goto("/slots");
  await expect(page.locator("[data-testid^=slot-status-]")).toHaveCount(10);
  const name = `E2E ${Date.now() % 100000}`;
  await page.getByLabel("Изменить слот 4").click();
  await page.getByTestId("slot-name").fill(name);
  await page.getByTestId("slot-save").click();
  await expect(page.getByTestId("slot-4")).toContainText(name);
  await page.reload();
  await expect(page.getByTestId("slot-4")).toContainText(name);
  await page.getByLabel("История слота 4").click();
  await expect(page.getByTestId("slot-history")).toContainText(name);
});
