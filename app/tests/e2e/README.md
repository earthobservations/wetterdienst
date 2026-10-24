# E2E Testing Guide

This directory contains end-to-end (E2E) tests using Playwright that test the app with a real backend.

## Browsers

**Playwright comes with its own browsers** - no system browser installation needed!

Currently configured to use **Firefox**. You can easily switch or test multiple browsers:

```typescript
// playwright.config.ts
projects: [
  { name: 'firefox', use: { ...devices['Desktop Firefox'] } }, // ✅ Current
  // { name: 'chromium', use: { ...devices['Desktop Chrome'] } },   // Alternative
  // { name: 'webkit', use: { ...devices['Desktop Safari'] } },     // Alternative
]
```

### Installing Browsers

```bash
# Install Firefox (current default)
npx playwright install firefox

# Or install all browsers
npx playwright install

# Or install specific browsers
npx playwright install chromium webkit
```

**Browsers are downloaded once** (~90MB each) and stored in `~/Library/Caches/ms-playwright/`

## Health Checks

The E2E test suite includes automatic health checks that verify:
- ✅ Backend API is running and accessible (via `/health` endpoint)
- ✅ App dev server is running

If the backend is not available, you'll see a clear error message:

```
❌ BACKEND HEALTH CHECK FAILED!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
The Wetterdienst backend is not running or not accessible.
Expected backend at: http://localhost:7890
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 To start the backend:

   Option 1 - Using Docker (Recommended):
   $ cd .. && docker compose --profile backend up -d

   Option 2 - Local Python:
   $ cd .. && pip install -e .
   $ wetterdienst restapi --listen 0.0.0.0:7890
```

## Prerequisites

### Backend Server
The E2E tests require the Wetterdienst backend API to be running. You have two options:

#### Option 1: Using Docker Compose (Recommended)
```bash
# From the project root
docker compose --profile backend up -d
```

The backend will be available at `http://localhost:7890`

#### Option 2: Local Python Installation
```bash
# From the project root
pip install -e .
wetterdienst restapi --listen 0.0.0.0:7890
```

### App Server
The Playwright config is set to automatically start the app dev server on `http://localhost:4000`

## Running E2E Tests

### Run all E2E tests (headless)
```bash
npm run test:e2e
```

### Run with UI mode (interactive)
```bash
npm run test:e2e:ui
```

### Run in headed mode (see browser)
```bash
npm run test:e2e:headed
```

### Debug mode (step through tests)
```bash
npm run test:e2e:debug
```

### Run specific test file
```bash
npx playwright test api.spec.ts
```

### Run tests in specific browser
```bash
npx playwright test --project=firefox
npx playwright test --project=chromium  # If chromium is enabled in config
```

### Run tests on multiple browsers
Enable multiple projects in `playwright.config.ts`, then:
```bash
npx playwright test  # Runs on all configured browsers
```

## Test Structure

```
tests/e2e/
├── global-setup.ts       # Health checks for backend/app
├── api.spec.ts           # API endpoint tests
├── pages.spec.ts         # Page navigation and UI tests
├── integration.spec.ts   # Full user flow tests
└── accessibility.spec.ts # axe scans of every page, on request (A11Y=1; mocked backend)
```

## Test Categories

### API Tests (`api.spec.ts`)
- Tests backend API endpoints directly
- Verifies data structure and response codes
- Tests: coverage, stations, values, stripes endpoints

### Page Tests (`pages.spec.ts`)
- Tests page rendering and navigation
- Verifies UI elements are present
- Tests all main pages: home, api, explorer, stripes, support, impressum, datenschutz

### Integration Tests (`integration.spec.ts`)
- Tests complete user workflows
- Verifies app-backend integration
- Tests data loading and API calls

### Accessibility Tests (`accessibility.spec.ts`)
- **On request only**: `playwright.config.ts` ignores it unless `A11Y=1`, so `pnpm test:e2e` and the
  App E2E workflow do not run it. Run it with `pnpm test:a11y`, from the Actions tab ("App
  accessibility"), or by putting the `a11y` label on a pull request
- Scans every page with axe (WCAG 2.2 AA), in light and dark mode and in two languages, and in the
  states a first paint does not show (map, chart, menu, error)
- Answers every `/api/*` request itself, so it reaches neither the backend nor a provider
- Fails on a violation outside `accessibility/baseline.json`; see [ACCESSIBILITY.md](../../ACCESSIBILITY.md)

## Environment Variables

You can override the URLs for testing:

```bash
# Override app URL
BASE_URL=http://localhost:4000 npm run test:e2e

# Override backend URL
BACKEND_URL=http://localhost:7890 npm run test:e2e

# Override both
BASE_URL=http://localhost:4000 BACKEND_URL=http://localhost:7890 npm run test:e2e
```

**Note:** The health check will verify the backend is accessible before running any tests.
## CI/CD

For continuous integration, ensure both backend and app are running:

```bash
# Start backend
docker compose --profile backend up -d

# Run E2E tests
npm run test:e2e

# Cleanup
docker compose --profile backend down
```

## Debugging Failed Tests

1. **Check backend is running:**
   ```bash
   curl http://localhost:7890/api/coverage
   ```

2. **Run test with UI:**
   ```bash
   npm run test:e2e:ui
   ```

3. **View test report:**
   ```bash
   npx playwright show-report
   ```

4. **Take screenshots on failure:**
   Tests automatically capture screenshots on failure in `test-results/`

## Writing New Tests

Example test structure:

```typescript
import { expect, test } from '@playwright/test'

test.describe('Feature Name', () => {
  test('should do something', async ({ page }) => {
    await page.goto('/some-page')
    await expect(page.getByText('Expected Text')).toBeVisible()
  })
})
```

See [Playwright Documentation](https://playwright.dev/docs/intro) for more details.
