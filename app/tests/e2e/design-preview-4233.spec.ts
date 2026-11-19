import type { Page } from '@playwright/test'
import { mkdirSync } from 'node:fs'
import { expect, test } from '@playwright/test'
import { mockBackend } from './accessibility/mock-backend'

// DESIGN PREVIEW (GH-4233), removed again in the next commit: the screenshots of the stripes page's four views, the switch, the
// download menu of the table view and the About fold-out, light and dark, 390 and 1280 px, against the mock backend.

const OUT = 'design-preview/4233'
const PATH = '/stripes?kind=temperature&station=00011'
const SCHEMES = ['light', 'dark'] as const
const SIZES = [{ name: 'phone', width: 390, height: 844 }, { name: 'desktop', width: 1280, height: 900 }] as const

const card = (page: Page) => page.locator('[data-slot="root"]').filter({ has: page.locator('.sc-controls') }).last()

for (const scheme of SCHEMES) {
  for (const size of SIZES) {
    test.describe(`${scheme} ${size.name}`, () => {
      test.beforeEach(async ({ page, context, baseURL }) => {
        mkdirSync(OUT, { recursive: true })
        await context.addInitScript(mode => localStorage.setItem('nuxt-color-mode', mode), scheme)
        await page.setViewportSize({ width: size.width, height: size.height })
        await mockBackend(page, baseURL!)
      })

      async function show(page: Page, variant: string) {
        await page.goto(`${PATH}&variant=${variant}`)
        await page.getByRole('button', { name: 'Show', exact: true }).click()
        await expect(page.locator(variant === 'table' ? 'table' : '.sc-canvas[data-drawn="true"] svg').first()).toBeVisible()
        // the fonts and the chart's last layout
        await page.evaluate(() => document.fonts.ready)
        await page.waitForTimeout(400)
      }

      for (const variant of ['stripes', 'bars', 'bars_scale', 'table']) {
        test(`the ${variant} view`, async ({ page }) => {
          await show(page, variant)
          // the card's head at the top of the window, under the bar: what a reader sees
          await card(page).evaluate((element) => {
            window.scrollTo(0, element.getBoundingClientRect().top + window.scrollY - (window.innerWidth < 640 ? 72 : 80))
          })
          await page.waitForTimeout(200)
          await page.screenshot({ path: `${OUT}/${variant}-${scheme}-${size.name}.png` })
        })
      }

      test('the switch', async ({ page }) => {
        await show(page, 'table')
        await page.locator('.sc-controls').evaluate(element => element.scrollIntoView({ block: 'center' }))
        await page.waitForTimeout(200)
        await page.locator('.sc-controls').screenshot({ path: `${OUT}/switch-${scheme}-${size.name}.png` })
      })

      test('the download menu of the table view', async ({ page }) => {
        await show(page, 'table')
        await page.getByRole('button', { name: 'Download table' }).evaluate(element => element.scrollIntoView({ block: 'center' }))
        await page.getByRole('button', { name: 'Download table' }).click()
        await expect(page.getByRole('menuitem', { name: 'Download as CSV' })).toBeVisible()
        // the menu's fade-in
        await page.waitForTimeout(600)
        await page.screenshot({ path: `${OUT}/csv-menu-${scheme}-${size.name}.png` })
      })

      test('the About text opened', async ({ page }) => {
        await show(page, 'stripes')
        await page.getByRole('button', { name: 'About climate stripes' }).first().click()
        await expect(page.getByTestId('stripes-about-method')).toBeVisible()
        await page.evaluate(() => window.scrollTo(0, 0))
        await page.screenshot({ path: `${OUT}/about-${scheme}-${size.name}.png`, fullPage: size.name === 'phone' })
      })
    })
  }
}
