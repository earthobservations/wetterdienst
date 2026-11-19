import { mkdirSync } from 'node:fs'
import { expect, test } from '@playwright/test'
import { mockBackend } from './accessibility/mock-backend'

// DESIGN PREVIEW (GH-4233, the note above the table dropped), removed again in the next commit: the table view at 390 and 1280 px and the
// About text opened at 1280 px, light, against the mock backend.

const OUT = 'design-preview/4233c'
const PATH = '/stripes?kind=temperature&station=00011'

test.beforeEach(async ({ page, baseURL }) => {
  mkdirSync(OUT, { recursive: true })
  await mockBackend(page, baseURL!)
})

for (const size of [{ name: 'phone', width: 390, height: 844 }, { name: 'desktop', width: 1280, height: 900 }] as const) {
  test(`the table view, ${size.name}`, async ({ page }) => {
    await page.setViewportSize({ width: size.width, height: size.height })
    await page.goto(`${PATH}&variant=table`)
    await page.getByRole('button', { name: 'Show', exact: true }).click()
    await expect(page.locator('table')).toBeVisible()
    await page.evaluate(() => document.fonts.ready)
    await page.waitForTimeout(500)
    const card = page.locator('[data-slot="root"]').filter({ has: page.locator('.sc-controls') }).last()
    await card.evaluate((element) => {
      window.scrollTo(0, element.getBoundingClientRect().top + window.scrollY - (window.innerWidth < 640 ? 72 : 80))
    })
    await page.waitForTimeout(200)
    await page.screenshot({ path: `${OUT}/table-light-${size.name}.png` })
  })
}

test('the About text opened, desktop', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 1000 })
  await page.goto(PATH)
  await page.getByRole('button', { name: 'About climate stripes' }).first().click()
  await expect(page.getByTestId('stripes-about-columns')).toBeVisible()
  await page.evaluate(() => document.fonts.ready)
  await page.waitForTimeout(400)
  await page.screenshot({ path: `${OUT}/about-light-desktop.png` })
})
