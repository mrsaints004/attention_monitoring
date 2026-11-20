import { defineConfig } from "@playwright/test";
import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { tmpdir } from "node:os";

const python = process.env.ATTENTION_BACKEND_PYTHON ||
  (existsSync(resolve("../backend/venv/bin/python")) ? resolve("../backend/venv/bin/python") : "python");
const installedChrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const browserPath = process.env.ATTENTION_BROWSER_PATH || (existsSync(installedChrome) ? installedChrome : undefined);
const frontendPort = Number(process.env.ATTENTION_E2E_PORT || 3017);
const frontendURL = `http://localhost:${frontendPort}`;
export default defineConfig({
  testDir: "./e2e", timeout: 45000, workers: 1, fullyParallel: false,
  reporter: "list", outputDir: "test-results",
  use: { baseURL: frontendURL, trace: "retain-on-failure", screenshot: "only-on-failure",
    launchOptions: browserPath ? {executablePath: browserPath} : {} },
  webServer: [
    { command: `"${python}" -m uvicorn app.main:app --host 127.0.0.1 --port 8000`,
      cwd: "../backend", url: "http://127.0.0.1:8000/api/ready", reuseExistingServer: false,
      env: { DATABASE_URL: `sqlite+aiosqlite:///${resolve(tmpdir(), `attention-e2e-${process.pid}.sqlite`)}`,
        APP_ENV: "development", AUTH_SECRET: "local-integration-test-signing-secret-only",
        CORS_ORIGINS: JSON.stringify([frontendURL]) } },
    { command: `npm run start -- --hostname 127.0.0.1 --port ${frontendPort}`,
      url: frontendURL, reuseExistingServer: false },
  ],
});
