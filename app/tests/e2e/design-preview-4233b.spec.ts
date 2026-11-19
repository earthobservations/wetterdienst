import type { StripesValuesResponse } from '#shared/types/api'
import { mkdirSync } from 'node:fs'
import { expect, test } from '@playwright/test'
import { recordOf, stripesAnswer } from '../helpers/stripes-answer'
import { defaultHandlers, mockBackend } from './accessibility/mock-backend'

// DESIGN PREVIEW (GH-4233, review fixes), removed again in the next commit: the short line where only the spread falls back to the
// station's whole record (a station from 1976), and the About text opened, light, 390 and 1280 px.

const OUT = 'design-preview/4233b'
const SIZES = [{ name: 'phone', width: 390, height: 844 }, { name: 'desktop', width: 1280, height: 900 }] as const

for (const size of SIZES) {
  test.describe(size.name, () => {
    test.beforeEach(async ({ page, baseURL }) => {
      mkdirSync(OUT, { recursive: true })
      await page.setViewportSize({ width: size.width, height: size.height })
      const base = defaultHandlers()['stripes/values']!
      await mockBackend(page, baseURL!, {
        // a station that begins in 1976: 25 years in 1971 to 2000 (the mean needs 20), 25 in 1901 to 2000 (the spread needs 30)
        'stripes/values': async (url, route) => {
          const answer = await base(url, route) as StripesValuesResponse
          return { ...answer, ...stripesAnswer(recordOf(1976, 2024, year => 7.5 + (year - 1976) * 0.03 + 0.8 * Math.sin((year - 1976) / 3))) }
        },
      })
    })

    async function show(page: import('@playwright/test').Page, variant: string) {
      await page.goto(`/stripes?kind=temperature&station=00011&variant=${variant}`)
      await page.getByRole('button', { name: 'Show', exact: true }).click()
      await expect(page.getByTestId('stripes-reference')).toBeVisible()
      await page.evaluate(() => document.fonts.ready)
      await page.waitForTimeout(500)
    }

    test('the line where only the spread falls back', async ({ page }) => {
      await show(page, 'stripes')
      await expect(page.getByTestId('stripes-reference')).toHaveText('Relative to the mean of 1976–2000 (spread from the whole record, 1976–2024)')
      const card = page.locator('[data-slot="root"]').filter({ has: page.locator('.sc-controls') }).last()
      await card.evaluate((element) => {
        window.scrollTo(0, element.getBoundingClientRect().top + window.scrollY - (window.innerWidth < 640 ? 72 : 80))
      })
      await page.waitForTimeout(200)
      await page.screenshot({ path: `${OUT}/spread-fallback-light-${size.name}.png` })
    })

    test('the About text opened', async ({ page }) => {
      await show(page, 'stripes')
      await page.getByRole('button', { name: 'About climate stripes' }).first().click()
      await expect(page.getByTestId('stripes-about-method')).toContainText('its mean or its spread is taken from its whole record instead')
      await page.evaluate(() => window.scrollTo(0, 0))
      await page.screenshot({ path: `${OUT}/about-light-${size.name}.png`, fullPage: size.name === 'phone' })
    })
  })
}
