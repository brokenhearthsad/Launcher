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
