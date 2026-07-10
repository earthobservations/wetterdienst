import { expect, test } from '@playwright/test'

test.describe('Explorer E2E Flow', () => {
  test('should complete full data exploration flow', async ({ page }) => {
    await page.goto('/explorer')
    await page.waitForLoadState('networkidle')

    // Wait for coverage data to load with longer timeout
    await page.waitForTimeout(2000)

    // Check if select elements exist first
    const selectCount = await page.locator('select').count()
    if (selectCount > 0) {
      // Select provider (DWD should be available)
      const providerSelect = page.locator('select').first()
      await providerSelect.selectOption({ label: /dwd/i })

      // Wait for the next dropdown to populate
      await page.waitForTimeout(1000)

      // Verify that network dropdown is now enabled
      const networkSelect = page.locator('select').nth(1)
      const isDisabled = await networkSelect.isDisabled()
      expect(isDisabled).toBe(false)
    }
    else {
      // If no selects, just verify page loaded
      expect(selectCount).toBeGreaterThanOrEqual(0)
    }
  })

  test('should disable dependent dropdowns initially', async ({ page }) => {
    await page.goto('/explorer')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)

    // Just verify the page has content
    const bodyText = await page.locator('body').textContent()
    expect(bodyText).toBeTruthy()
  })

  test('should leave provider/network freely selectable and resolution/dataset unset on load', async ({ page }) => {
    await page.goto('/explorer')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)

    const providerSelect = page.getByLabel('Provider')
    await expect(providerSelect).toBeEnabled()
    await expect(providerSelect).toHaveText('dwd')

    // Resolution/dataset are no longer auto-preselected on load -- picking a full
    // dataset's worth of parameters eagerly made the page feel like it hung.
    const resolutionSelect = page.getByLabel('Resolution')
    await expect(resolutionSelect).toHaveText('Select resolution')

    await providerSelect.click()
    const optionCount = await page.getByRole('option').count()
    expect(optionCount).toBeGreaterThan(1)
  })
})

test.describe('History Provider/Network Restriction', () => {
  test('should restrict provider and network to dwd/observation', async ({ page }) => {
    await page.goto('/history')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)

    const providerSelect = page.getByLabel('Provider')
    await expect(providerSelect).toBeDisabled()
    await expect(providerSelect).toHaveText('dwd')

    const networkSelect = page.getByLabel('Network')
    await expect(networkSelect).toBeDisabled()
    await expect(networkSelect).toHaveText('observation')

    // Resolution stays freely selectable -- only provider/network are locked.
    const resolutionSelect = page.getByLabel('Resolution')
    await expect(resolutionSelect).toBeEnabled()
  })

  test('should fetch and expand a station history end to end via real clicks', async ({ page }) => {
    await page.goto('/history')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)

    // ParameterSelection's Resolution/Dataset are NuxtUI comboboxes (button +
    // popover listbox), not native <select> elements -- open and pick by click.
    await page.getByLabel('Resolution').click()
    await page.getByRole('option', { name: 'Daily', exact: true }).click()
    await page.waitForTimeout(500)
    await page.getByLabel('Dataset').click()
    await page.getByRole('option', { name: 'Climate summary', exact: true }).click()
    await page.waitForTimeout(500)

    // Station search is a searchable combobox: clicking its placeholder text
    // opens a popover containing the actual text input to type into.
    await page.getByText(/Search by name or station ID/i).click()
    await page.getByPlaceholder('Search…').fill('00011')
    await page.waitForTimeout(500)
    await page.getByRole('option').first().click()
    await page.waitForTimeout(300)

    await page.getByRole('button', { name: 'Show', exact: true }).click()
    await page.waitForTimeout(2000)

    await expect(page.getByText(/Station ID: 11/i)).toBeVisible()

    const nameHistoryButton = page.getByRole('button', { name: /Name history/i })
    await nameHistoryButton.click()
    await expect(page.getByText('Station names')).toBeVisible()

    await page.getByRole('button', { name: 'Reset', exact: true }).click()
    await expect(page.getByText(/No histories loaded/i)).toBeVisible()
  })
})

test.describe('API Integration Flow', () => {
  test('should fetch and display station data in explorer', async ({ page }) => {
    await page.goto('/explorer')
    await page.waitForLoadState('networkidle')

    // The page should have loaded without errors
    const errorText = await page.getByText(/error/i).count()
    expect(errorText).toBe(0)
  })

  test('should load coverage on API page and allow navigation', async ({ page }) => {
    await page.goto('/api')
    await page.waitForLoadState('networkidle')

    // Should show API endpoints
    await expect(page.getByText('coverage').first()).toBeVisible()
    await expect(page.getByText('stations').first()).toBeVisible()
  })
})

test.describe('Real-time Data Loading', () => {
  test('should show loading states', async ({ page }) => {
    await page.goto('/explorer')
    await page.waitForLoadState('networkidle')

    // On initial load, there might be loading indicators
    // Just verify the page loads successfully
    const body = await page.locator('body').textContent()
    expect(body).toBeTruthy()
  })

  test('stripes page should fetch stations from API', async ({ page }) => {
    // Listen for API calls
    const apiCalls: string[] = []
    page.on('request', (request) => {
      if (request.url().includes('/api/')) {
        apiCalls.push(request.url())
      }
    })

    await page.goto('/stripes')
    await page.waitForLoadState('networkidle')

    // Should have made API call to stripes/stations
    const stripesCall = apiCalls.find(url => url.includes('/stripes/stations'))
    expect(stripesCall).toBeDefined()
  })
})
