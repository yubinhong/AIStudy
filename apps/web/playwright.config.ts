import { defineConfig, devices } from "@playwright/test";

const apiPort = Number(process.env.STUDY_E2E_API_PORT ?? "18080");
const webPort = Number(process.env.STUDY_E2E_WEB_PORT ?? "13000");

if (!Number.isInteger(apiPort) || !Number.isInteger(webPort)) {
  throw new Error("STUDY_E2E_API_PORT and STUDY_E2E_WEB_PORT must be integers");
}

const apiUrl = `http://127.0.0.1:${apiPort}`;
const webUrl = `http://127.0.0.1:${webPort}`;

export default defineConfig({
  testDir: "./e2e",
  testMatch: "**/*.e2e.ts",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 120_000,
  expect: { timeout: 10_000 },
  reporter: "line",
  outputDir: "test-results",
  use: {
    baseURL: webUrl,
    screenshot: "off",
    trace: "off",
    video: "off",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: [
    {
      name: "api",
      command: `../../services/api/.venv/bin/uvicorn study_api.main:app --app-dir ../../services/api/src --host 127.0.0.1 --port ${apiPort}`,
      url: `${apiUrl}/healthz`,
      timeout: 120_000,
      reuseExistingServer: false,
      stdout: "ignore",
      stderr: "pipe",
      env: {
        ...process.env,
        STUDY_API_AUTH_REPOSITORY: "memory",
        STUDY_API_CURRICULUM_REPOSITORY: "memory",
        STUDY_API_IMAGE_ANALYSIS_REPOSITORY: "memory",
        STUDY_API_LEARNING_REPOSITORY: "memory",
        STUDY_API_OCR_QUEUE: "memory",
        STUDY_API_OCR_RESULTS: "memory",
        STUDY_API_PROFILE_REPOSITORY: "memory",
        STUDY_COOKIE_SECURE: "false",
        STUDY_ENGLISH_LIVE_ENABLED: "false",
        STUDY_ENGLISH_LIVE_PROVIDER: "disabled",
      },
    },
    {
      name: "web",
      command: `pnpm exec next dev --hostname 127.0.0.1 --port ${webPort}`,
      url: `${webUrl}/healthz`,
      timeout: 120_000,
      reuseExistingServer: false,
      stdout: "ignore",
      stderr: "pipe",
      env: {
        ...process.env,
        NEXT_TELEMETRY_DISABLED: "1",
        STUDY_API_URL: apiUrl,
      },
    },
  ],
});
