import { expect, test } from "@playwright/test";

test("dashboard and navigation load", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
  await expect(page.getByTestId("ws-status")).toHaveAttribute("data-state", "open");
  await page.getByRole("link", { name: "Players" }).click();
  await expect(page.getByTestId("team-radiant").locator("[data-testid^=player-card-]")).toHaveCount(5);
  await expect(page.getByTestId("team-dire").locator("[data-testid^=player-card-]")).toHaveCount(5);
});

test("bot settings persist", async ({ page }) => {
  await page.goto("/bots");
  const slider = page.getByLabel("Aggression");
  await expect(slider).toBeVisible();
  const target = Number(await slider.inputValue()) === 0.85 ? "0.15" : "0.85";
  await slider.fill(target);
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Saved for");
  await page.reload();
  await expect(page.getByLabel("Aggression")).toHaveValue(target);
});

test("create, run, pause, resume and finish a simulated match", async ({ page }) => {
  await page.goto("/match-control");
  await page.getByTestId("session-name").fill("E2E match");
  await page.getByTestId("session-seed").fill("77");
  await page.getByTestId("session-speed").selectOption("50");
  await page.getByTestId("create-session").click();
  const created = page.getByRole("status");
  await expect(created).toContainText("created");
  const id = (await created.textContent())!.match(/#(\d+)/)![1];

  await page.getByLabel(`Start session ${id}`).click();
  await page.getByTestId(`session-row-${id}`).getByRole("link", { name: "Live", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/live/${id}`));
  await expect(page.getByTestId("minimap")).toBeVisible();
  await expect(page.locator("[data-testid^=hero-row-]")).toHaveCount(10);
  await expect(page.getByTestId("event-feed")).toBeVisible({ timeout: 30_000 });

  await page.getByLabel(`Pause session ${id}`).click();
  await expect(page.getByTestId("scoreboard")).toContainText("Paused");
  const t1 = await page.getByTestId("game-time").textContent();
  await page.waitForTimeout(1500);
  expect(await page.getByTestId("game-time").textContent()).toBe(t1);
  await page.getByLabel(`Resume session ${id}`).click();
  await page.getByLabel(`Speed for session ${id}`).selectOption("1000");
  await expect(page.getByTestId("scoreboard")).toContainText("Finished", { timeout: 90_000 });

  await page.getByRole("link", { name: "Match History" }).click();
  await expect(page.getByTestId("history-table")).toContainText("E2E match");
  await page.getByLabel(`Details for session ${id}`).click();
  await expect(page.getByTestId("details-table").locator("tbody tr")).toHaveCount(10);
});
