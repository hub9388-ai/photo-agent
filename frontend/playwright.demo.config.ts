import { defineConfig } from "@playwright/test"

export default defineConfig({
  testDir: "./tests",
  testMatch: "demo.spec.ts",
  outputDir: "../.test_artifacts/frontend-demo",
  reporter: "list",
  workers: 1,
  use: {
    baseURL: "http://127.0.0.1:4175",
    channel: process.env.DEMO_BROWSER_CHANNEL ?? "chrome",
    screenshot: "only-on-failure",
  },
  webServer: {
    command: "node scripts/serve-demo.mjs",
    url: "http://127.0.0.1:4175",
    reuseExistingServer: !process.env.CI,
  },
})
