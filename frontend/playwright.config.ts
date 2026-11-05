import { defineConfig } from "@playwright/test";
import { resolve } from "node:path";
import { createFakeDota } from "./e2e/fake-dota";

// Fake Dota 2 folder for the GSI test; created before the server starts (test data only).
// The config is re-evaluated in worker processes; the env flag (inherited) keeps this once per run.
if (!process.env.E2E_NO_SERVERS && !process.env.E2E_FAKE_DOTA_READY) {
  createFakeDota();
  process.env.E2E_FAKE_DOTA_READY = "1";
}

// End-to-end tests run against the production setup: `npm run build`, then one
// Python process (`python -m app`) serving UI + API on http://localhost:8000.
// Set E2E_NO_SERVERS=1 to reuse an already running Launcher (e.g. start.bat).
const python = process.platform === "win32" ? ".venv\\Scripts\\python.exe" : ".venv/bin/python";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  workers: 1,
  use: {
    baseURL: "http://localhost:8000",
    launchOptions: process.env.PW_CHROMIUM_PATH ? { executablePath: process.env.PW_CHROMIUM_PATH } : undefined,
  },
  webServer: process.env.E2E_NO_SERVERS ? undefined : {
    command: `${python} -m app`,
    cwd: "../backend",
    url: "http://127.0.0.1:8000/api/health",
    reuseExistingServer: true,
    env: { DML_DATABASE_URL: "sqlite:///./data/e2e.db", DML_API_RATE_LIMIT_PER_MINUTE: "100000",
      DML_STEAM_PATH: resolve("e2e", ".tmp", "Steam") },
    timeout: 60_000,
  },
});
