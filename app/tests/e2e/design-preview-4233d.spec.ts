import { mkdirSync } from 'node:fs'
import { expect, test } from '@playwright/test'
import { mockBackend } from './accessibility/mock-backend'

// DESIGN PREVIEW (GH-4233, the switch on a phone), removed again in the next commit: the switch of the four views in German, light,
// at 320 and 390 px.

const OUT = 'design-preview/4233d'

for (const width of [320, 390]) {
  test(`the switch, German, ${width} px`, async ({ page, baseURL, context }) => {
    mkdirSync(OUT, { recursive: true })
    await context.addCookies([{ name: 'wd_lang', value: 'de', url: baseURL! }])
    await page.setViewportSize({ width, height: 844 })
    await mockBackend(page, baseURL!)
    await page.goto('/stripes?kind=temperature&station=00011&variant=bars_scale')
    await page.getByRole('button', { name: 'Anzeigen', exact: true }).click()
    await expect(page.locator('.sc-canvas[data-drawn="true"] svg').first()).toBeVisible()
    await page.evaluate(() => document.fonts.ready)
    await page.waitForTimeout(500)
    await page.locator('.sc-controls').evaluate(element => element.scrollIntoView({ block: 'center' }))
    await page.waitForTimeout(200)
    await page.locator('.sc-controls').screenshot({ path: `${OUT}/switch-de-light-${width}.png` })
    const card = page.locator('[data-slot="root"]').filter({ has: page.locator('.sc-controls') }).last()
    await card.evaluate((element) => {
      window.scrollTo(0, element.getBoundingClientRect().top + window.scrollY - 72)
    })
    await page.waitForTimeout(200)
    await page.screenshot({ path: `${OUT}/card-de-light-${width}.png` })
  })
}
