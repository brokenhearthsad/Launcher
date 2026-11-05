import { defineConfig } from "@playwright/test";

// End-to-end tests run against a real backend (127.0.0.1:8000) and the Vite dev server.
// Both are started automatically unless E2E_NO_SERVERS=1 (e.g. when start.bat is already running).
const python = process.platform === "win32" ? "..\\backend\\.venv\\Scripts\\python.exe" : "../backend/.venv/bin/python";

export default defineConfig({
  testDir: "./e2e",
  timeout: 120_000,
  fullyParallel: false,
  workers: 1,
  use: {
    baseURL: "http://localhost:5173",
    launchOptions: process.env.PW_CHROMIUM_PATH ? { executablePath: process.env.PW_CHROMIUM_PATH } : undefined,
  },
  webServer: process.env.E2E_NO_SERVERS ? undefined : [
    {
      command: `${python} -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000`,
      cwd: "../backend",
      url: "http://127.0.0.1:8000/api/health",
      reuseExistingServer: true,
      env: { DML_DATABASE_URL: "sqlite:///./data/e2e.db", DML_API_RATE_LIMIT_PER_MINUTE: "100000" },
      timeout: 60_000,
    },
    { command: "npm run dev", url: "http://localhost:5173", reuseExistingServer: true, timeout: 60_000 },
  ],
});
