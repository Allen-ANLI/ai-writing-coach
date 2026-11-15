import path from "node:path";

import { defineConfig } from "@playwright/test";

/**
 * Isolated E2E stack (never touches the dev environment):
 * - Backend on :8001 against the ai_writing_coach_test database, with a 2s
 *   access-token TTL so expiry/refresh paths are testable, CORS allowing the
 *   E2E frontend origin :3600.
 * - Frontend dev server on :3600 pointed at that backend.
 * The dev servers (:8000 / :3500) keep running untouched.
 */
const backendDir = path.resolve(__dirname, "../backend");
const backendPython = path.join(backendDir, ".venv", "Scripts", "python.exe");

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  reporter: [["list"]],
  globalSetup: "./e2e/global-setup.ts",
  use: {
    baseURL: "http://localhost:3600",
    trace: "retain-on-failure",
    // The Playwright CDN download stalls on this machine, so tests run on the
    // installed Chromium-based Edge. To use the bundled browser instead:
    // `npx playwright install chromium` and remove the channel line.
    channel: "msedge",
  },
  webServer: [
    {
      command: `"${backendPython}" -m uvicorn app.main:app --host 127.0.0.1 --port 8001`,
      cwd: backendDir,
      url: "http://127.0.0.1:8001/api/v1/health",
      reuseExistingServer: false,
      timeout: 60_000,
      env: {
        DATABASE_URL: "postgresql+psycopg://awc:awc_local_dev@127.0.0.1:5432/ai_writing_coach_test",
        ACCESS_TOKEN_TTL_SECONDS: "2",
        CORS_ORIGINS: '["http://localhost:3600"]',
        // The suite registers many users from one IP; production rate limits
        // stay untouched, the isolated E2E backend relaxes them.
        AUTH_RATE_LIMIT_MAX_REQUESTS: "1000",
        // E2E stays deterministic and never spends real API credits.
        LLM_PROVIDER: "mock",
      },
    },
    {
      command: "npx next dev -p 3600",
      url: "http://localhost:3600",
      reuseExistingServer: false,
      timeout: 120_000,
      env: {
        NEXT_PUBLIC_API_BASE_URL: "http://localhost:8001/api/v1",
      },
    },
  ],
});
