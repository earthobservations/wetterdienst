import type { Page } from '@playwright/test'
import { expect, test } from '@playwright/test'
import { defaultHandlers, isSnowRequest, mockBackend } from './accessibility/mock-backend'

// DESIGN PREVIEW for GH-4212, removed again in the next commit: a forecast whose pressure comes in kPa, between 101.1 and 101.7 (the
// axis is then 100.9 to 101.9, the range of the issue, whose middle tick is 101.5). Screenshots of the pressure panel go to
// `PREVIEW_DIR`, named after `PREVIEW_LABEL` (before / after), by the scheme and the width.

const DIR = process.env.PREVIEW_DIR ?? '/tmp'
const LABEL = process.env.PREVIEW_LABEL ?? 'after'
const NOW = new Date('2026-11-17T04:30:00Z')

test.use({ locale: 'en-US', timezoneId: 'Europe/Berlin' })

async function open(page: Page, baseURL: string) {
  await page.clock.setFixedTime(NOW)
  const defaults = defaultHandlers(NOW)
  await mockBackend(page, baseURL, {
    values: (url, route) => {
      const answer = defaults.values!(url, route) as { values: any[], metadata?: { parameters: { name: string, unit: string }[] } }
      if (isSnowRequest(url))
        return answer
      const pressure = answer.values.filter(v => v.parameter === 'pressure_air_sea_level' && v.value !== null).map(v => v.value as number)
      const low = Math.min(...pressure)
      const high = Math.max(...pressure)
      return {
        values: answer.values.map(v => v.parameter === 'pressure_air_sea_level' && v.value !== null ? { ...v, value: Math.round((101.1 + (v.value - low) / (high - low) * 0.6) * 100) / 100 } : v),
        metadata: { parameters: [{ name: 'pressure_air_sea_level', unit: 'kPa' }] },
      }
    },
  }, NOW)
  await page.goto('/meteogram?station=Z914&view=chart')
  await expect(page.locator('.mg-canvas[data-drawn="true"]')).toBeVisible({ timeout: 60_000 })
}

for (const scheme of ['light', 'dark'] as const) {
  for (const [name, size] of [['desktop', { width: 1280, height: 900 }], ['phone', { width: 390, height: 1500 }]] as const) {
    test(`${LABEL} ${scheme} ${name}`, async ({ page, baseURL }) => {
      await page.emulateMedia({ colorScheme: scheme })
      await page.setViewportSize(size)
      await open(page, baseURL!)
      await page.waitForTimeout(2500)
      await page.getByRole('figure').first().screenshot({ path: `${DIR}/${LABEL}-${scheme}-${name}.png` })
    })
  }
}
