import { defineConfig, devices } from "@playwright/test";
import path from "node:path";

const backendPort = 8011;
const frontendPort = 5181;
const e2eDataDir = path.resolve(".tmp/e2e-data");
const quotedDataDir = JSON.stringify(e2eDataDir);

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 45_000,
  expect: {
    timeout: 10_000,
  },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: `http://127.0.0.1:${frontendPort}`,
    screenshot: "only-on-failure",
    trace: "on-first-retry",
    ...devices["Desktop Chrome"],
  },
  webServer: [
    {
      command: [
        `rm -rf ${quotedDataDir}`,
        `mkdir -p ${quotedDataDir}`,
        [
          `TRADEMINER_E2E_DATA_DIR=${quotedDataDir}`,
          "PYTHONPATH=src",
          "python -m uvicorn e2e_server:app",
          "--app-dir tests",
          "--host 127.0.0.1",
          `--port ${backendPort}`,
        ].join(" "),
      ].join(" && "),
      url: `http://127.0.0.1:${backendPort}/api/system/status`,
      reuseExistingServer: false,
      timeout: 20_000,
    },
    {
      command: [
        `TRADEMINER_API_BASE_URL=http://127.0.0.1:${backendPort}`,
        "npm run web:dev --",
        "--host 127.0.0.1",
        `--port ${frontendPort}`,
      ].join(" "),
      url: `http://127.0.0.1:${frontendPort}`,
      reuseExistingServer: false,
      timeout: 20_000,
    },
  ],
});
