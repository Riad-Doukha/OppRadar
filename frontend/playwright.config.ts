import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end tests (e2e/).
 *
 *   npm run e2e              public pages (API mocked) — what CI runs
 *   npm run e2e:full         + the signed-in journey against your Supabase project
 *                            (needs the API on :8000 and the root .env; creates and
 *                            deletes a throwaway account)
 *
 * Locally the running dev servers are reused; otherwise `next dev` is started.
 * Uses the installed Chrome when available (no browser download needed).
 */
const CI = Boolean(process.env.CI);
// Installed Chrome locally; the bundled Chromium in CI (PW_CHANNEL overrides, e.g. to run CI mode locally).
const channel = process.env.PW_CHANNEL ?? (CI ? undefined : "chrome");

export default defineConfig({
  testDir: "e2e",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  retries: CI ? 1 : 0,
  reporter: CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: "http://localhost:3000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "public", testMatch: /public\.spec\.ts/, use: { ...devices["Desktop Chrome"], channel } },
    { name: "phone", testMatch: /public\.spec\.ts/, grep: /@phone/, use: { ...devices["Pixel 7"], channel } },
    { name: "journey", testMatch: /journey\.spec\.ts/, use: { ...devices["Desktop Chrome"], channel } },
  ],
  webServer: {
    command: CI ? "npm run build && npx next start -p 3000" : "npx next dev -p 3000",
    url: "http://localhost:3000/login",
    reuseExistingServer: !CI,
    timeout: 300_000,
  },
});
