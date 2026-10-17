import process from 'node:process'
import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './tests/e2e',
  // The accessibility scan (84 page loads, ten minutes and more) runs on request, not with the rest:
  // `pnpm test:a11y`, or the "App accessibility" workflow (see ACCESSIBILITY.md)
  testIgnore: process.env.A11Y === '1' ? undefined : '**/accessibility.spec.ts',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',

  // Global setup for health checks
  globalSetup: './tests/e2e/global-setup.ts',

  use: {
    baseURL: process.env.BASE_URL || 'http://localhost:4000',
    trace: 'on-first-retry',
  },

  projects: [
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
    },
    // Uncomment to test in multiple browsers:
    // {
    //   name: 'chromium',
    //   use: { ...devices['Desktop Chrome'] },
    // },
    // {
    //   name: 'webkit',
    //   use: { ...devices['Desktop Safari'] },
    // },
  ],

  webServer: {
    // In CI, test against the real production build (catches bundling/build
    // regressions the dev server would never surface); locally, keep the fast
    // dev-server iteration loop.
    command: process.env.CI ? 'npm run build && npm run preview -- --port 4000' : 'npm run dev',
    url: 'http://localhost:4000',
    reuseExistingServer: !process.env.CI,
    // read by nuxt.config.ts at build and start: the rate limiter is off for the suite's own server
    env: { WD_E2E: '1' },
    timeout: process.env.CI ? 300 * 1000 : 120 * 1000,
  },
})
