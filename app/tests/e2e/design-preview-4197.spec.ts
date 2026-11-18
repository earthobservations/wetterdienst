import type { Page } from '@playwright/test'
import { expect, test } from '@playwright/test'
import { defaultHandlers, isSnowRequest, mockBackend } from './accessibility/mock-backend'

// DESIGN PREVIEW for GH-4197, removed again in the next commit: a forecast whose cloud cover and snow chance come in the fraction
// unit `-` (0 to 1), so that the cloud and snow-chance panels' axes are [0, 1] with the middle gridline at 0.5. Screenshots go to
// `PREVIEW_DIR`, named after `PREVIEW_LABEL` (before / after), by the scheme and the width.

const DIR = process.env.PREVIEW_DIR ?? '/tmp'
const LABEL = process.env.PREVIEW_LABEL ?? 'after'
const NOW = new Date('2026-11-17T04:30:00Z')
const CLOUD = ['cloud_cover_total', 'cloud_cover_below_2km', 'cloud_cover_between_2km_and_7km', 'cloud_cover_above_7km']

test.use({ locale: 'en-US', timezoneId: 'Europe/Berlin' })

async function open(page: Page, baseURL: string) {
  await page.clock.setFixedTime(NOW)
  const defaults = defaultHandlers(NOW)
  await mockBackend(page, baseURL, {
    values: (url, route) => {
      const answer = defaults.values!(url, route) as { values: any[], metadata?: { parameters: { name: string, unit: string }[] } }
      if (isSnowRequest(url)) {
        // the chance as a fraction: 0.85 for 85 %
        return {
          values: answer.values.map(v => v.parameter.startsWith('probability_') ? { ...v, value: v.value / 100 } : v),
          metadata: { parameters: answer.metadata!.parameters.map(p => p.name.startsWith('probability_') ? { ...p, unit: '-' } : p) },
        }
      }
      return { values: answer.values, metadata: { parameters: CLOUD.map(name => ({ name, unit: '-' })) } }
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
