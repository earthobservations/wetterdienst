import { expect, test } from '@playwright/test'
import { run10382Values } from '../helpers/mosmix-run'
import { mockBackend } from './accessibility/mock-backend'

// MOSMIX-L's hourly amount is 0.0 late in a run while its 6 and 12 hour totals still carry rain (GH-4175): the forecast shows days 6 to
// 10 from the totals, in the chart (blocks of 6 and 12 hours and where they begin), the compact view and the map's day rows. The run is
// 10382 of 2026-11-17 03 UTC, real; the page's clock is 05:30 at Berlin on the 17th. The API is answered by the mock backend.

const NOW = new Date('2026-11-17T04:30:00Z')

test.use({ locale: 'en-US', timezoneId: 'Europe/Berlin' })

async function open(page: import('@playwright/test').Page, baseURL: string, path: string) {
  await page.clock.setFixedTime(NOW)
  const backend = await mockBackend(page, baseURL, {
    values: (url) => {
      if ((url.searchParams.get('parameters') ?? '').startsWith('hourly/snow'))
        return { values: [] }
      return { values: run10382Values({ stationId: url.searchParams.get('stations') ?? '10384' }) }
    },
  }, NOW)
  await page.goto(path)
  return backend
}

test('shows the rain of the late days in the compact view, marked as made of 12 hour totals', async ({ page, baseURL }) => {
  const backend = await open(page, baseURL!, '/meteogram?station=10384&view=compact')
  const days = page.getByTestId('compact-days')
  await expect(days).toBeVisible({ timeout: 60_000 })
  const cards = days.locator('> div')
  await expect(cards).toHaveCount(11)
  // Tuesday 24th to Thursday 26th: DWD's totals, where the hourly amount is 0.0
  for (const [index, amount] of [[7, '0.5'], [8, '1.2'], [9, '1.1']] as const)
    await expect(cards.nth(index).getByTestId('day-precip')).toContainText(`≈${amount} mm`)
  // and the first days are the hourly amounts, with no mark
  await expect(cards.nth(1).getByTestId('day-precip')).toContainText('6.8 mm')
  await expect(cards.nth(1).getByTestId('day-precip')).not.toContainText('≈')
  // the first day starts after its midnight, the last ends with the run
  await expect(cards.first().getByTestId('partial-day')).toHaveText('partial, 19 h')
  await expect(cards.last().getByTestId('partial-day')).toHaveText('partial, 12 h')
  expect(backend.unanswered).toEqual([])
})

test('shows the rain of the late days in the map\'s day rows', async ({ page, baseURL }) => {
  const backend = await open(page, baseURL!, '/map?station=10384')
  const rows = page.getByTestId('day-rows').first().getByRole('listitem')
  await expect(rows).toHaveCount(11, { timeout: 60_000 })
  await expect(rows.nth(8).getByTestId('row-precip')).toContainText('≈1.2 mm')
  await expect(rows.nth(1).getByTestId('row-precip')).toContainText('6.8 mm')
  expect(backend.unanswered).toEqual([])
})

test('draws the precipitation of the chart as hours, then 6 hour and 12 hour blocks, and says where they begin', async ({ page, baseURL }) => {
  const backend = await open(page, baseURL!, '/meteogram?station=10384&view=chart')
  await expect(page.locator('.mg-canvas[data-drawn="true"]')).toBeVisible({ timeout: 60_000 })
  // the whole run in the window: zoomed out as far as the chart goes
  const zoomOut = page.getByRole('button', { name: 'Zoom out' })
  for (let i = 0; i < 8 && await zoomOut.isEnabled(); i++)
    await zoomOut.click()
  // the labels of the changes are text of the chart's SVG, beside a dashed line in the precipitation panel
  const texts = page.locator('.mg-canvas svg text')
  await expect(texts.filter({ hasText: /^6 h totals$/ })).toHaveCount(1)
  await expect(texts.filter({ hasText: /^12 h totals$/ })).toHaveCount(1)
  // and the rain of a 6 hour block is a rectangle six hours wide: more of them than of the hourly ones are wider than a pixel or two
  const widths = await page.locator('.mg-canvas svg path[fill="#3b82f6"]').evaluateAll(paths => paths.map(path => path.getBoundingClientRect().width))
  expect(widths.length).toBeGreaterThan(20)
  expect(Math.max(...widths)).toBeGreaterThan(5 * Math.min(...widths.filter(width => width > 0)))
  expect(backend.unanswered).toEqual([])
})
