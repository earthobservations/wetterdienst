import { mkdirSync } from 'node:fs'
import process from 'node:process'
import { expect, test } from '@playwright/test'
import { defaultHandlers, mockBackend } from './accessibility/mock-backend'

// DESIGN PREVIEW of GH-4193 (to be removed again): the day cards of the compact view, the map panel's rows and the widget, light and
// dark, desktop and phone. PHASE=before|after.

const PHASE = process.env.PHASE ?? 'after'
const OUT = `design-preview/4193`
const NOW = new Date('2026-11-18T08:30:00Z')

// one weather for each day of the forecast: [weather code, cloud cover in %, rain of the hour in mm by the hour of the day]
const DAYS: [number, number, (hour: number) => number][] = [
  [18, 10, () => 0], // wind under a clear sky: the sun with the wind badge
  [19, 30, () => 0], // a funnel cloud: the partly cloudy sky with the tornado badge
  [61, 85, () => 0.25], // drizzly: 0.25 mm every hour, 5.75 mm in all, light rain as the chart draws every hour of it
  [65, 98, hour => (hour >= 12 && hour < 15 ? 5 : 0.4)], // heavy rain: the wettest hours are 5 mm
  [95, 90, () => 0.5], // thunderstorm
  [71, 95, () => 0.5], // snow
  [1, 12, () => 0], // clear
  [3, 55, () => 0], // partly cloudy
  [3, 92, () => 0], // cloudy
  [45, 100, () => 0], // fog
  [33, 60, () => 0], // dust or sand storm: the cloudy-ish sky with the wind badge
  [63, 95, () => 1], // rain
  [18, 90, () => 0], // wind under a cloudy sky
]

function values() {
  const original = defaultHandlers(NOW).values!
  return async (url: URL, route: unknown) => {
    const answer = await original(url, route as never) as { values: Record<string, unknown>[], metadata?: unknown }
    if (url.searchParams.get('network') !== 'mosmix' || !Array.isArray(answer?.values) || (url.searchParams.get('parameters') ?? '').startsWith('hourly/snow'))
      return answer
    const copies = Math.ceil((DAYS.length * 24) / 72) + 1
    const base = answer.values.filter(value => !['weather_significant', 'cloud_cover_total', 'precipitation_amount_significant_weather_last_1h'].includes(value.parameter as string))
    const hours = [...new Set(answer.values.map(value => value.timestamp as string))]
    const all = Array.from({ length: copies }, (_, copy) => base.map(value => ({
      ...value,
      timestamp: new Date(Date.parse(value.timestamp as string) + copy * 72 * 3_600_000).toISOString().replace('.000Z', '+00:00'),
    }))).flat()
    const first = Date.parse(hours[0]!)
    const extra: Record<string, unknown>[] = []
    const station_id = url.searchParams.get('stations') ?? '10384'
    for (let hour = 0; hour < DAYS.length * 24; hour++) {
      const time = new Date(first + hour * 3_600_000)
      const stamp = time.toISOString().replace('.000Z', '+00:00')
      const [code, cover, amount] = DAYS[Math.min(DAYS.length - 1, Math.floor(hour / 24))]!
      const rain = amount(time.getUTCHours())
      const add = (parameter: string, value: number) => extra.push({ station_id, resolution: 'hourly', dataset: 'large', parameter, timestamp: stamp, value, quality_flags: null })
      add('weather_significant', code)
      add('cloud_cover_total', cover / 100)
      add('precipitation_amount_significant_weather_last_1h', rain)
    }
    return { ...answer, values: [...all, ...extra] }
  }
}

const SHOTS = [
  { mode: 'light', device: 'desktop', viewport: { width: 1280, height: 900 } },
  { mode: 'dark', device: 'desktop', viewport: { width: 1280, height: 900 } },
  { mode: 'light', device: 'phone', viewport: { width: 390, height: 844 } },
  { mode: 'dark', device: 'phone', viewport: { width: 390, height: 844 } },
] as const

for (const shot of SHOTS) {
  test.describe(`${PHASE} ${shot.mode} ${shot.device}`, () => {
    test.use({ viewport: shot.viewport, locale: 'en-US', timezoneId: 'Europe/Berlin', deviceScaleFactor: 2 })
    test.setTimeout(180_000)

    test.beforeEach(async ({ page, context, baseURL }) => {
      mkdirSync(OUT, { recursive: true })
      await context.addCookies([{ name: 'wd_lang', value: 'en', url: baseURL! }])
      await context.addInitScript((mode) => {
        localStorage.setItem('nuxt-color-mode', mode)
      }, shot.mode)
      await page.emulateMedia({ reducedMotion: 'reduce' })
      await page.clock.setFixedTime(NOW)
      await mockBackend(page, baseURL!, { values: values() }, NOW)
    })

    test('the compact view', async ({ page }) => {
      await page.goto('/meteogram?station=10384&view=compact')
      const days = page.getByTestId('compact-days')
      await expect(days).toBeVisible({ timeout: 90_000 })
      await expect(page.locator('html')).toHaveClass(shot.mode === 'dark' ? /dark/ : /^((?!dark).)*$/)
      await page.waitForTimeout(800)
      await days.scrollIntoViewIfNeeded()
      await page.screenshot({ path: `${OUT}/${PHASE}-compact-${shot.mode}-${shot.device}.png`, fullPage: false })
    })

    test('the map panel', async ({ page }) => {
      await page.goto('/map?station=10384&lat=52.9&lon=13.0')
      const card = page.getByTestId('map-card-forecast')
      await expect(card.getByTestId('day-rows')).toBeVisible({ timeout: 90_000 })
      await expect(page.locator('html')).toHaveClass(shot.mode === 'dark' ? /dark/ : /^((?!dark).)*$/)
      await page.waitForTimeout(800)
      // the panel's bottom: the last rows and what is under them (the credit, after), as the viewport shows them
      await card.getByTestId('day-rows').getByRole('listitem').nth(2).scrollIntoViewIfNeeded()
      await page.waitForTimeout(300)
      await page.screenshot({ path: `${OUT}/${PHASE}-map-${shot.mode}-${shot.device}.png`, fullPage: false })
      await card.getByRole('link', { name: /forecast/i }).last().scrollIntoViewIfNeeded()
      await page.waitForTimeout(300)
      await page.screenshot({ path: `${OUT}/${PHASE}-mapcredit-${shot.mode}-${shot.device}.png`, fullPage: false })
    })

    // on a wide frame the widget shows the chart: its cards are those of the narrow frame
    test('the widget', async ({ page }) => {
      test.skip(shot.device === 'desktop')
      await page.goto('/widget?station=10384')
      const days = page.getByTestId('compact-days')
      await expect(days).toBeVisible({ timeout: 90_000 })
      await page.waitForTimeout(800)
      await page.screenshot({ path: `${OUT}/${PHASE}-widget-${shot.mode}-${shot.device}.png`, fullPage: false })
    })
  })
}
