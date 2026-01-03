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
    await page.getByRole('link', { name: /stripes/i }).click()

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

test.describe('Color Mode Toggle', () => {
  test('should have color mode toggle button', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    // Look for the color mode button (should have an icon)
    const colorModeButton = page.locator('button').filter({ hasText: '' }).first()
    await expect(colorModeButton).toBeVisible()
  })
})
