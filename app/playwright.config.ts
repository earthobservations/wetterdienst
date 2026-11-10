import process from 'node:process'
import { defineConfig, devices } from '@playwright/test'

// the port the app is served on; the default is the app's own, E2E_PORT lets a run beside a dev server use another
const PORT = process.env.E2E_PORT || '4000'

// the specs that print pages to a PDF (the sizes of the charts' text; the icons and labels of a print without
// background graphics): they run in Chromium, the others in Firefox
const PDF_SPEC = /(chart-print|print-backgrounds)\.spec\.ts$/

// the spec of the dialogs on a phone: a touch drag as touch events of Chromium's input (CDP `Input.dispatchTouchEvent`),
// which only Chromium can be told to make, so it runs in a Chromium of its own, as a Pixel 7
const TOUCH_SPECS = /dialog-touch-scroll\.spec\.ts$/

// The accessibility scan (393 tests, most of them a page load and a scan: about 20 minutes on three workers, several
// times that on one) runs on request, not with the rest: `pnpm test:a11y`, or the "App accessibility" workflow (see ACCESSIBILITY.md).
// A project's own `testIgnore` replaces the top-level one, so every project carries this list.
const A11Y_IGNORE = process.env.A11Y === '1' ? [] : ['**/accessibility.spec.ts']

export default defineConfig({
  testDir: './tests/e2e',
  testIgnore: A11Y_IGNORE,
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

  projects: process.env.E2E_BROWSER === 'chrome'
    // for a machine where Playwright's Firefox does not start: the system's Chrome (its layout
    // differs from Firefox's, so the accessibility baseline is only of Firefox on Linux); it runs the
    // print spec as well
    ? [
        { name: 'chrome', use: { ...devices['Desktop Chrome'], channel: 'chrome' }, testIgnore: [...A11Y_IGNORE, TOUCH_SPECS] },
        { name: 'chromium-touch', use: { ...devices['Pixel 7'], channel: 'chrome' }, testMatch: TOUCH_SPECS, testIgnore: A11Y_IGNORE },
      ]
    : [
        { name: 'firefox', use: { ...devices['Desktop Firefox'] }, testIgnore: [...A11Y_IGNORE, PDF_SPEC, TOUCH_SPECS] },
        // the print spec measures a PDF, and `page.pdf` is Chromium's alone
        { name: 'chromium', use: { ...devices['Desktop Chrome'] }, testMatch: PDF_SPEC, testIgnore: A11Y_IGNORE },
        // the dialogs on a phone, by touch
        { name: 'chromium-touch', use: { ...devices['Pixel 7'] }, testMatch: TOUCH_SPECS, testIgnore: A11Y_IGNORE },
        // Uncomment to test in multiple browsers:
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
