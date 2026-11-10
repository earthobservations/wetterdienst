import process from 'node:process'
import { defineConfig, devices } from '@playwright/test'

// the port the app is served on; the default is the app's own, E2E_PORT lets a run beside a dev server use another
const PORT = process.env.E2E_PORT || '4000'

// A touch drag is a gesture of the browser's own compositor, which only Chromium can be told to make (CDP's
// `Input.synthesizeScrollGesture`), so the specs of the dialogs on a phone run in a Chromium of their own: the
// system's Chrome where `E2E_BROWSER=chrome`, else Playwright's Chromium (`npx playwright install chromium`)
const TOUCH_SPECS = '**/dialog-touch-scroll.spec.ts'
// The accessibility scan (393 tests, most of them a page load and a scan: about 20 minutes on three workers, several
// times that on one) runs on request, not with the rest: `pnpm test:a11y`, or the "App accessibility" workflow (see ACCESSIBILITY.md)
const ON_REQUEST = process.env.A11Y === '1' ? [] : ['**/accessibility.spec.ts']

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',

  // Global setup for health checks
  globalSetup: './tests/e2e/global-setup.ts',

  use: {
    baseURL: process.env.BASE_URL || `http://localhost:${PORT}`,
    trace: 'on-first-retry',
  },

  projects: [
    process.env.E2E_BROWSER === 'chrome'
      // for a machine where Playwright's Firefox does not start: the system's Chrome (its layout
      // differs from Firefox's, so the accessibility baseline is only of Firefox on Linux)
      ? { name: 'chrome', use: { ...devices['Desktop Chrome'], channel: 'chrome' }, testIgnore: [...ON_REQUEST, TOUCH_SPECS] }
      : { name: 'firefox', use: { ...devices['Desktop Firefox'] }, testIgnore: [...ON_REQUEST, TOUCH_SPECS] },
    {
      name: 'chromium-touch',
      testMatch: TOUCH_SPECS,
      use: { ...devices['Pixel 7'], ...(process.env.E2E_BROWSER === 'chrome' ? { channel: 'chrome' } : {}) },
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
    command: process.env.CI ? `npm run build && npm run preview -- --port ${PORT}` : `npm run dev -- --port ${PORT}`,
    url: `http://localhost:${PORT}`,
    reuseExistingServer: !process.env.CI,
    // read by nuxt.config.ts at build and start: the rate limiter is off for the suite's own server
    env: { WD_E2E: '1' },
    timeout: process.env.CI ? 300 * 1000 : 120 * 1000,
  },
})
