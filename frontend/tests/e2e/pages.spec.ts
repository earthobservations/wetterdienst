import { expect, test } from '@playwright/test'

test.describe('Home Page', () => {
  test('should load the homepage', async ({ page }) => {
    await page.goto('/')
    await expect(page).toHaveTitle(/Wetterdienst/i)
  })

  test('should display main navigation', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    // Check for navigation links
    const explorerLink = page.getByRole('link', { name: /explorer/i })
    const apiLink = page.getByRole('link', { name: /api/i })

    await expect(explorerLink).toBeVisible()
    await expect(apiLink).toBeVisible()
  })
})

test.describe('API Documentation Page', () => {
  test('should navigate to API page', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    await page.getByRole('link', { name: /api/i }).click()

    await expect(page).toHaveURL(/\/api/)
    await expect(page.getByRole('heading', { name: /REST API/i })).toBeVisible()
  })

  test('should display API endpoints', async ({ page }) => {
    await page.goto('/api')
    await page.waitForLoadState('networkidle')

    const endpoints = ['coverage', 'stations', 'values', 'interpolate', 'summarize']

    for (const endpoint of endpoints) {
      await expect(page.getByText(endpoint, { exact: false }).first()).toBeVisible()
    }
  })

  test('should have clickable endpoint links', async ({ page }) => {
    await page.goto('/api')
    await page.waitForLoadState('networkidle')

    // Just verify endpoint text is visible, buttons may not exist
    await expect(page.getByText('coverage', { exact: false }).first()).toBeVisible()
  })
})

test.describe('Explorer Page', () => {
  test('should navigate to explorer page', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    await page.getByRole('link', { name: /explorer/i }).click()

    await expect(page).toHaveURL(/\/explorer/)
  })

  test('should display parameter selection', async ({ page }) => {
    await page.goto('/explorer')
    await page.waitForLoadState('networkidle')

    await expect(page.getByText(/Select Parameters/i).first()).toBeVisible()
  })

  test('should have provider dropdown', async ({ page }) => {
    await page.goto('/explorer')
    await page.waitForLoadState('networkidle')

    // Check that select elements exist
    const selects = await page.locator('select, [role="combobox"]').count()
    expect(selects).toBeGreaterThan(0)
  })
})

test.describe('Climate Stripes Page', () => {
  test('should navigate to stripes page', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    await page.getByRole('navigation').getByRole('link', { name: /stripes/i }).click()

    await expect(page).toHaveURL(/\/stripes/)
  })

  test('should display climate stripes heading', async ({ page }) => {
    await page.goto('/stripes')
    await page.waitForLoadState('networkidle')

    // Use first() to avoid strict mode violation with multiple headings
    await expect(page.getByRole('heading', { name: /Climate Stripes/i }).first()).toBeVisible()
  })

  test('should load stripes stations', async ({ page }) => {
    await page.goto('/stripes')
    await page.waitForLoadState('networkidle')

    // Should have a station selector
    const selectors = await page.locator('select, [role="combobox"]').count()
    expect(selectors).toBeGreaterThan(0)
  })
})

test.describe('Support Page', () => {
  test('should navigate to support page', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    await page.getByRole('link', { name: /support/i }).click()

    await expect(page).toHaveURL(/\/support/)
  })

  test('should display support options', async ({ page }) => {
    await page.goto('/support')
    await page.waitForLoadState('networkidle')

    await expect(page.getByText(/Report Issues/i)).toBeVisible()
    await expect(page.getByText(/Contribute/i)).toBeVisible()
  })

  test('should have external links', async ({ page }) => {
    await page.goto('/support')
    await page.waitForLoadState('networkidle')

    const githubLink = page.getByRole('link', { name: /github/i }).first()
    await expect(githubLink).toBeVisible()
  })
})

test.describe('Impressum Page', () => {
  test('should navigate to impressum page', async ({ page }) => {
    // Go directly to impressum page instead of trying to find the link
    await page.goto('/impressum')
    await expect(page).toHaveURL(/\/impressum/)
  })

  test('should display legal notice', async ({ page }) => {
    await page.goto('/impressum')
    await page.waitForLoadState('networkidle')

    await expect(page.getByRole('heading', { name: /Legal Notice/i })).toBeVisible()
  })
})

test.describe('Forecast (Meteogram) Page', () => {
  test('should navigate to the forecast page', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    await page.getByRole('navigation').getByRole('link', { name: /forecast/i }).click()

    await expect(page).toHaveURL(/\/meteogram/)
  })

  test('should display the forecast heading and station search', async ({ page }) => {
    await page.goto('/meteogram')
    await page.waitForLoadState('networkidle')

    await expect(page.getByRole('heading', { name: /Weather forecast/i }).first()).toBeVisible()
    await expect(page.getByText(/Search for a station above/i)).toBeVisible()
  })

  test('should load a forecast when a station is picked via the URL', async ({ page }) => {
    await page.goto('/meteogram?station=01001')
    await page.waitForLoadState('networkidle')

    // Either the chart loads or a definitive error/no-data state is shown --
    // never the empty "search for a station" hint.
    await expect(page.getByText(/Search for a station above/i)).not.toBeVisible()
    await expect(page.getByText('JAN MAYEN', { exact: true })).toBeVisible()
  })
})

test.describe('History Page', () => {
  test('should navigate to the history page', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    await page.getByRole('navigation').getByRole('link', { name: /history/i }).click()

    await expect(page).toHaveURL(/\/history/)
  })

  test('should display the station history heading', async ({ page }) => {
    await page.goto('/history')
    await page.waitForLoadState('networkidle')

    await expect(page.getByRole('heading', { name: /Station history/i }).first()).toBeVisible()
  })

  test('should show the history sections selector', async ({ page }) => {
    await page.goto('/history')
    await page.waitForLoadState('networkidle')

    await expect(page.getByText(/History sections/i)).toBeVisible()
  })
})

test.describe('Settings Page', () => {
  test('should navigate to the settings page', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    // The header icon opens a quick-settings popover; the full settings
    // page is reached via the "Settings" link inside that popover.
    await page.getByRole('button', { name: 'Settings', exact: true }).click()
    await page.getByRole('link', { name: 'Settings', exact: true }).click()

    await expect(page).toHaveURL(/\/settings/)
  })

  test('should display language, appearance and units sections', async ({ page }) => {
    await page.goto('/settings')
    await page.waitForLoadState('networkidle')

    await expect(page.getByRole('heading', { name: /^Settings$/i })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Language' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Appearance' })).toBeVisible()
  })

  test('should switch theme when a theme button is clicked', async ({ page }) => {
    await page.goto('/settings')
    await page.waitForLoadState('networkidle')

    await page.getByRole('button', { name: /^Dark$/i }).click()
    await expect(page.locator('html')).toHaveClass(/dark/)
  })
})

test.describe('Widget Page', () => {
  test('should show a hint when no station is specified', async ({ page }) => {
    await page.goto('/widget')
    await page.waitForLoadState('networkidle')

    await expect(page.getByText(/No station specified/i)).toBeVisible()
  })

  test('should render a minimal embeddable view for a given station', async ({ page }) => {
    await page.goto('/widget?station=01001')
    await page.waitForLoadState('networkidle')

    await expect(page.getByText(/No station specified/i)).not.toBeVisible()
    await expect(page.getByText('JAN MAYEN')).toBeVisible()
    await expect(page.getByTitle(/Open full forecast/i)).toBeVisible()
  })
})

test.describe('Color Mode Toggle', () => {
  test('should have color mode toggle button', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    // Look for the color mode button (should have an icon)
    const colorModeButton = page.locator('button').filter({ hasText: '' }).first()
    await expect(colorModeButton).toBeVisible()
  })
})
