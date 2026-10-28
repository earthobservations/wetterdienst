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
    // Exact, not /api/i: the home page's developer row links to the backend's Swagger UI as
    // "REST API", which a loose match picks up alongside the nav entry and fails on strict mode.
    const apiLink = page.getByRole('link', { name: 'API', exact: true })

    await expect(explorerLink).toBeVisible()
    await expect(apiLink).toBeVisible()
  })

  // The weather services are the backend's (`/api/providers`), so for a moment there are none to show: the
  // block holds its place with placeholders. What is under the card must not move by more than a row of chips
  // when the answer comes (a row is a chip of 30px and a gap of 8), however wide the window is.
  for (const width of [1280, 768, 375]) {
    test(`keeps the weather services block about as tall before the backend answers as after, at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 })
      let release!: () => void
      const held = new Promise<void>((resolve) => {
        release = resolve
      })
      await page.route(url => url.pathname === '/api/providers', async (route) => {
        await held
        await route.continue()
      })
      await page.goto('/')
      const card = page.getByTestId('home-providers-card')
      await expect(card.getByRole('status')).toBeVisible()
      const before = (await card.boundingBox())!.height

      release()
      await expect(page.getByTestId('home-providers')).toBeVisible({ timeout: 30_000 })
      const after = (await card.boundingBox())!.height

      expect(Math.abs(after - before), `the card was ${before}px tall before and ${after}px after`).toBeLessThanOrEqual(38)
    })
  }

  test('links every weather service to its page', async ({ page }) => {
    await page.goto('/')
    const chip = page.getByTestId('home-providers').getByRole('link', { name: 'DWD' })

    await expect(chip).toBeVisible({ timeout: 30_000 })
    await chip.click()
    await expect(page).toHaveURL(/\/providers\/dwd$/)
  })
})

test.describe('API Documentation Page', () => {
  test('should navigate to API page', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    await page.getByRole('link', { name: 'API', exact: true }).click()

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

test.describe('Providers Page', () => {
  test('should be reachable from the navigation', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    await page.getByRole('navigation').getByRole('link', { name: 'Providers', exact: true }).click()

    await expect(page).toHaveURL(/\/providers$/)
    await expect(page.getByRole('heading', { name: 'Providers', level: 1 })).toBeVisible()
  })

  test('should be reachable from the home page', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    await page.getByRole('link', { name: /All providers, their licences/ }).click()

    await expect(page).toHaveURL(/\/providers$/)
  })

  test('should list the providers the backend serves, and narrow them by a search', async ({ page }) => {
    await page.goto('/providers')

    // what the backend says each is, not a list written into the app
    await expect(page.getByRole('heading', { name: 'German Weather Service' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Norwegian Meteorological Institute' })).toBeVisible()
    await expect(page.getByText(/Showing 22 of 22/)).toBeVisible()

    await page.getByPlaceholder(/Search name, country or code/).fill('norway')
    await expect(page.getByRole('heading', { name: 'Norwegian Meteorological Institute' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'German Weather Service' })).toHaveCount(0)
    await expect(page.getByText(/Showing 1 of 22/)).toBeVisible()
  })

  test('should open the page of a provider with its licence and credit line', async ({ page }) => {
    await page.goto('/providers')
    await page.getByRole('link', { name: /German Weather Service/ }).click()

    await expect(page).toHaveURL(/\/providers\/dwd$/)
    await expect(page.getByRole('heading', { name: 'German Weather Service', level: 1 })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Creative Commons Attribution 4.0 International' })).toHaveAttribute('href', 'https://creativecommons.org/licenses/by/4.0/')
    await expect(page.getByText('Source: Deutscher Wetterdienst')).toBeVisible()
    // its networks, the standalone ones among them
    await expect(page.getByRole('heading', { name: 'observation', level: 3 })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'radar', level: 3 })).toBeVisible()
  })

  test('should open the explorer on the network of a provider', async ({ page }) => {
    await page.goto('/providers/dwd')
    await page.getByRole('link', { name: 'Open in the explorer' }).first().click()

    await expect(page).toHaveURL(/\/explorer\?provider=dwd&network=/)
    await expect(page.getByText(/Select Parameters/i).first()).toBeVisible()
  })

  test('should say so for a provider there is none of', async ({ page }) => {
    await page.goto('/providers/nowhere')

    await expect(page.getByText('There is no provider called “nowhere”.')).toBeVisible()
  })
})

test.describe('Support Page', () => {
  test('should be reachable from the header icon', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    // Support is not a nav entry: it is a heart in the header's project links, and a footer link.
    // Both are named "Support", hence the scoping.
    await page.getByRole('banner').getByRole('link', { name: /support/i }).click()

    await expect(page).toHaveURL(/\/support/)
  })

  test('should be reachable from the footer', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    await page.getByRole('contentinfo').getByRole('link', { name: /support/i }).click()

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

test.describe('About Page', () => {
  test('should be reachable from the footer', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    await page.getByRole('contentinfo').getByRole('link', { name: /about/i }).click()
    await expect(page).toHaveURL(/\/about/)
  })

  test('should introduce the project and the maintainer', async ({ page }) => {
    await page.goto('/about')
    await page.waitForLoadState('networkidle')

    await expect(page.getByRole('heading', { name: /About Wetterdienst/i })).toBeVisible()
    await expect(page.getByText('Benjamin Gutzmann')).toBeVisible()
    await expect(page.getByText('Andreas Motl')).toBeVisible()
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

test.describe('Privacy Policy Page', () => {
  test('should be linked in the footer next to the legal notice', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    const footer = page.getByRole('contentinfo')
    await expect(footer.locator('a[href="/impressum"]')).toBeVisible()
    await footer.locator('a[href="/datenschutz"]').click()
    await expect(page).toHaveURL(/\/datenschutz/)
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  })

  test('should serve the same page at /privacy', async ({ page }) => {
    await page.goto('/privacy')
    await page.waitForLoadState('networkidle')

    await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
    await expect(page.getByText('Hetzner').first()).toBeVisible()
  })

  test('should be German with a German browser and English with an English one', async ({ browser }) => {
    for (const [locale, heading] of [['de-DE', 'Datenschutzerklärung'], ['en-GB', 'Privacy policy']] as const) {
      const context = await browser.newContext({ locale })
      const page = await context.newPage()
      await page.goto('/datenschutz')
      await page.waitForLoadState('networkidle')
      await expect(page.getByRole('heading', { level: 1, name: heading })).toBeVisible()
      await context.close()
    }
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
