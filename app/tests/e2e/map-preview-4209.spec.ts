import { mkdirSync } from 'node:fs'
import process from 'node:process'
import { expect, test } from '@playwright/test'
import { mockBackend } from './accessibility/mock-backend'

// DESIGN PREVIEW of GH-4209 (to be removed again): the map page, light and dark, desktop and phone. PHASE=before|after.

const PHASE = process.env.PHASE ?? 'after'
const OUT = `design-preview/4209`

function dense(prefix: string, latitude: number, longitude: number, count: number) {
  return Array.from({ length: count }, (_, index) => ({
    station_id: `${prefix}${String(index).padStart(2, '0')}`,
    name: `${prefix} POINT ${index}`,
    region: null,
    latitude: latitude + (index % 8) * 0.01,
    longitude: longitude + Math.floor(index / 8) * 0.012,
    elevation: 10,
    start_timestamp: null,
    end_timestamp: null,
  }))
}
const BERLIN = { station_id: '10384', name: 'BERLIN-TEMPELHOF', region: null, latitude: 52.47, longitude: 13.4, elevation: 49, start_timestamp: null, end_timestamp: null }
const STATIONS = { stations: () => ({ stations: [...dense('H', 53.6, 9.99, 40), ...dense('M', 48.1, 11.5, 24), ...dense('K', 50.9, 6.9, 12), BERLIN] }) }

const SHOTS = [
  { mode: 'light', device: 'desktop', viewport: { width: 1280, height: 800 } },
  { mode: 'dark', device: 'desktop', viewport: { width: 1280, height: 800 } },
  { mode: 'light', device: 'phone', viewport: { width: 390, height: 844 } },
  { mode: 'dark', device: 'phone', viewport: { width: 390, height: 844 } },
] as const

for (const shot of SHOTS) {
  test.describe(`${PHASE} ${shot.mode} ${shot.device}`, () => {
    test.use({ viewport: shot.viewport, locale: 'en-US' })
    test.setTimeout(180_000)

    test('the map', async ({ page, context, baseURL }) => {
      mkdirSync(OUT, { recursive: true })
      await context.addCookies([{ name: 'wd_lang', value: 'en', url: baseURL! }])
      await context.addInitScript((mode) => {
        localStorage.setItem('nuxt-color-mode', mode)
      }, shot.mode)
      await mockBackend(page, baseURL!, STATIONS)
      await page.goto('/map')
      await expect(page.getByRole('heading', { level: 1 })).toBeVisible({ timeout: 90_000 })
      await expect(page.locator('html')).toHaveClass(shot.mode === 'dark' ? /dark/ : /^((?!dark).)*$/)
      const map = page.getByRole('application', { name: /^Station map/ })
      await expect(map.locator('canvas').first()).toBeAttached()
      await expect(page.locator('.map-legend')).toBeVisible()
      await page.waitForTimeout(1200)
      await page.getByTestId('map-stage').scrollIntoViewIfNeeded()
      await page.waitForTimeout(300)
      await page.screenshot({ path: `${OUT}/${PHASE}-${shot.mode}-${shot.device}.png`, fullPage: false })
      if (PHASE === 'after' && shot.device === 'phone') {
        await page.getByTestId('map-layers-button').click()
        await expect(page.getByTestId('map-layers-panel')).toBeVisible()
        await page.waitForTimeout(500)
        await page.screenshot({ path: `${OUT}/${PHASE}-${shot.mode}-phone-panel.png`, fullPage: false })
      }
    })
  })
}
