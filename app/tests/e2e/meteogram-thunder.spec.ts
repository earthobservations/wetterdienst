import type { Page } from '@playwright/test'
import { expect, test } from '@playwright/test'
import { run10382Values } from '../helpers/mosmix-run'
import { mockBackend } from './accessibility/mock-backend'

// The thunderstorm band of the forecast (GH-4090): a thin panel under the precipitation with a bar for each hour of a probability of
// 10 % or more, its legend under the chart, its probability in the readout and in the table. The run is 10382 of 2026-11-17 03 UTC (real:
// its own hourly probability is 1 % at most, which draws no band), with a thunderstorm put into the evening of the 18th where `STORM`
// says; the page's clock is 05:30 at Berlin on the 17th. The API is answered by the mock backend.

const NOW = new Date('2026-11-17T04:30:00Z')
const FUCHSIA = '#a21caf'
// the hours after the issue (03 UTC on the 17th) that are given a probability: 17:00 to 21:00 UTC on the 18th
const STORM: Record<number, number> = { 38: 12, 39: 35, 40: 70, 41: 25 }
const ISSUE = Date.parse('2026-11-17T03:00:00Z')

test.use({ locale: 'en-US', timezoneId: 'Europe/Berlin' })

function thunderValues(storm: boolean) {
  return Array.from({ length: 247 }, (_, i) => i + 1).map(hour => ({
    station_id: '10382',
    resolution: 'hourly' as const,
    dataset: 'large' as const,
    parameter: 'probability_thunder_last_1h',
    timestamp: new Date(ISSUE + hour * 3_600_000).toISOString().replace('.000Z', '+00:00'),
    value: storm ? (STORM[hour] ?? 1) : 1,
    quality_flags: null,
  }))
}

async function open(page: Page, baseURL: string, path: string, storm = true) {
  await page.clock.setFixedTime(NOW)
  const backend = await mockBackend(page, baseURL, {
    values: (url) => {
      if ((url.searchParams.get('parameters') ?? '').startsWith('hourly/snow'))
        return { values: [] }
      return { values: [...run10382Values({ stationId: url.searchParams.get('stations') ?? '10384' }), ...thunderValues(storm)] }
    },
  }, NOW)
  await page.goto(path)
  return backend
}

const svg = (page: Page) => page.locator('.mg-canvas svg').first()
const legend = (page: Page) => page.getByTestId('meteogram-thunder-legend')
const bars = (page: Page) => svg(page).locator(`path[fill="${FUCHSIA}"]`)

test('draws the hours of a risk as bars in a panel under the precipitation, with its legend under the chart', async ({ page, baseURL }) => {
  const backend = await open(page, baseURL!, '/meteogram?station=10384&view=chart')
  await expect(page.locator('.mg-canvas[data-drawn="true"]')).toBeVisible({ timeout: 60_000 })
  // the hours of 12, 35, 70 and 25 %: four bars, higher with the probability and darker with its class
  await expect(bars(page)).toHaveCount(4)
  const heights = await bars(page).evaluateAll(paths => paths.map(path => path.getBoundingClientRect().height))
  expect(heights[2]!).toBeGreaterThan(heights[1]!)
  expect(heights[1]!).toBeGreaterThan(heights[0]!)
  const opacities = await bars(page).evaluateAll(paths => paths.map(path => Number(path.getAttribute('fill-opacity') ?? 1)))
  expect(opacities[2]!).toBeGreaterThan(opacities[1]!)
  expect(opacities[1]!).toBeGreaterThan(opacities[0]!)
  // the axis names the panel, and the legend what its bars are
  await expect(svg(page).locator('text', { hasText: /^Thunder$/ })).toHaveCount(1)
  await expect(legend(page)).toBeVisible()
  await expect(legend(page)).toContainText('Hours from 10% on are drawn')
  expect(backend.unanswered).toEqual([])
})

test('says the probability of an hour in the readout, by the keys, in words with its unit', async ({ page, baseURL }) => {
  const backend = await open(page, baseURL!, '/meteogram?station=10384&view=chart')
  await expect(page.locator('.mg-canvas[data-drawn="true"]')).toBeVisible({ timeout: 60_000 })
  const stage = page.locator('.mg-stage')
  await stage.focus()
  // the first key lands on the first hour (05:00 at Berlin on the 17th), Page Down is a day, Shift six hours: 20:00 on the 18th is 39 hours on
  await page.keyboard.press('ArrowRight')
  await page.keyboard.press('PageDown')
  await page.keyboard.press('Shift+ArrowRight')
  await page.keyboard.press('Shift+ArrowRight')
  for (let i = 0; i < 3; i++)
    await page.keyboard.press('ArrowRight')
  const readout = page.getByTestId('meteogram-readout')
  await expect(readout).toContainText('20:00')
  await expect(readout).toContainText('Thunderstorm probability (1 h)')
  await expect(readout).toContainText('70%')
  await expect(page.getByTestId('meteogram-announce')).toContainText('Thunderstorm probability (1 h): 70%')
  expect(backend.unanswered).toEqual([])
})

test('has a column of the probability in the table, and the likeliest hour in the description of the chart', async ({ page, baseURL }) => {
  const backend = await open(page, baseURL!, '/meteogram?station=10384&view=table')
  const table = page.getByRole('table')
  await expect(table).toBeVisible({ timeout: 60_000 })
  await expect(table.getByRole('columnheader', { name: /Thunderstorm probability \(1 h\)/ })).toHaveCount(1)
  // the column of the probability holds the 70 of the likeliest hour, once
  const headers = await table.getByRole('columnheader').allTextContents()
  const column = headers.findIndex(header => header.includes('Thunderstorm probability'))
  expect(column).toBeGreaterThan(0)
  const values = await table.getByRole('row').evaluateAll((rows, index) => rows.map(row => row.children[index]?.textContent?.trim()), column)
  expect(values.filter(value => value === '70')).toHaveLength(1)
  expect(backend.unanswered).toEqual([])
})

test('draws no panel and no legend where no hour reaches 10 %: the chart is as it was', async ({ page, baseURL }) => {
  const backend = await open(page, baseURL!, '/meteogram?station=10384&view=chart', false)
  await expect(page.locator('.mg-canvas[data-drawn="true"]')).toBeVisible({ timeout: 60_000 })
  await expect(bars(page)).toHaveCount(0)
  await expect(svg(page).locator('text', { hasText: /^Thunder$/ })).toHaveCount(0)
  await expect(legend(page)).toHaveCount(0)
  expect(backend.unanswered).toEqual([])
})

test('goes with the precipitation\'s switch', async ({ page, baseURL }) => {
  const backend = await open(page, baseURL!, '/meteogram?station=10384&view=chart')
  await expect(page.locator('.mg-canvas[data-drawn="true"]')).toBeVisible({ timeout: 60_000 })
  await expect(bars(page)).toHaveCount(4)
  await page.locator('button[data-panel="precip"]').click()
  await expect(bars(page)).toHaveCount(0)
  await expect(legend(page)).toHaveCount(0)
  await page.locator('button[data-panel="precip"]').click()
  await expect(bars(page)).toHaveCount(4)
  expect(backend.unanswered).toEqual([])
})
