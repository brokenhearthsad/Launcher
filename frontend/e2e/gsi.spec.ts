// GSI end-to-end against a FAKE Dota 2 folder and SYNTHETIC payloads (no real game is involved).
import { expect, test } from "@playwright/test";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));

const CFG = join(HERE, ".tmp", "Steam", "steamapps", "common", "dota 2 beta", "game", "dota", "cfg",
  "gamestate_integration", "gamestate_integration_launcher.cfg");
const FIXTURES = join(HERE, "..", "..", "backend", "tests", "fixtures", "gsi");

test.skip(!!process.env.E2E_NO_SERVERS, "needs the fake Dota 2 folder created by global-setup");

test("install GSI with confirmation, receive data, then remove the config", async ({ page, request }) => {
  await page.goto("/game");
  await expect(page.getByTestId("gsi-config")).toContainText("не установлена");

  await page.getByTestId("gsi-install").click();
  await expect(page.getByTestId("gsi-preview")).toContainText("Будет создан новый файл");
  await expect(page.getByTestId("gsi-confirm")).toBeDisabled();
  expect(existsSync(CFG)).toBe(false);
  await page.getByTestId("gsi-agree").check();
  await page.getByTestId("gsi-confirm").click();
  await expect(page.getByTestId("gsi-config")).toContainText("установлена и актуальна");
  expect(existsSync(CFG)).toBe(true);

  // Simulate Dota 2 posting to the configured URI with the token from the installed file.
  const token = readFileSync(CFG, "utf8").match(/"token"\s+"([^"]+)"/)![1];
  for (const f of ["menu", "hero_selection", "playing"]) {
    const body = JSON.parse(readFileSync(join(FIXTURES, `${f}.json`), "utf8"));
    body.auth.token = token;
    expect((await request.post("/gsi", { data: body })).ok()).toBe(true);
  }
  expect((await request.post("/gsi", { data: { auth: { token: "wrong" } } })).status()).toBe(401);

  await expect(page.getByTestId("gsi-status")).toHaveAttribute("data-status", "live");
  await expect(page.getByTestId("gsi-hero")).toContainText("Anti-Mage");
  await expect(page.getByTestId("gsi-score")).toContainText("7 : 4");
  await expect(page.getByTestId("gsi-events")).toContainText("Началась игра");

  await page.goto("/");
  await expect(page.getByTestId("overview-game")).toContainText("Anti-Mage, ур. 11");

  await page.goto("/game");
  await page.getByTestId("gsi-uninstall").click();
  await page.getByRole("button", { name: "Удалить", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Конфигурация удалена");
  expect(existsSync(CFG)).toBe(false);
  await expect(page.getByTestId("gsi-backups")).toContainText("before_uninstall");
});
