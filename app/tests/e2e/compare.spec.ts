import type { Page } from '@playwright/test'
import type { CompareAsked } from './accessibility/compare-backend'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { expect, test } from '@playwright/test'
import { compareHandlers } from './accessibility/compare-backend'
import { ApiFailure, mockBackend } from './accessibility/mock-backend'
import { expectAtLeastPx } from './target-size'

// The Compare tool (GH-4296): two stations over a period, or one station over two periods, for one parameter of DWD's observations, in
// one chart and one table with B minus A. The backend is the mock of the accessibility spec with the comparison's data, so nothing here
// reaches a provider.

const en = JSON.parse(readFileSync(fileURLToPath(new URL('../../i18n/locales/en.json', import.meta.url)), 'utf-8'))
const de = JSON.parse(readFileSync(fileURLToPath(new URL('../../i18n/locales/de.json', import.meta.url)), 'utf-8'))

const STATIONS_LINK = '/compare?compare=stations&resolution=daily&parameter=temperature_air_mean_2m&stations=00011,00044&startDate=2026-03-01&endDate=2026-03-31'
const PERIODS_LINK = '/compare?compare=periods&resolution=daily&parameter=temperature_air_mean_2m&stations=00011&periodA=2025-03-01/2025-03-31&periodB=2026-03-01/2026-03-31'

async function open(page: Page, baseURL: string, path: string, language = 'en') {
  const asked: CompareAsked[] = []
  await page.context().addCookies([{ name: 'wd_lang', value: language, url: baseURL }])
  const backend = await mockBackend(page, baseURL, compareHandlers(asked))
  await page.goto(path)
  // the dev server compiles the page on its first visit
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible({ timeout: 30_000 })
  return { asked, backend }
}

const table = (page: Page) => page.getByTestId('compare-table')
const rows = (page: Page) => page.getByTestId('compare-row')

test.describe('on a desktop', () => {
  test.use({ viewport: { width: 1280, height: 900 } })

  test('is a tool of the header, and a link opens the comparison two stations make', async ({ page, baseURL }) => {
    const { asked } = await open(page, baseURL!, '/stripes')
    await page.getByRole('navigation', { name: en.shell.mainNav }).getByRole('link', { name: en.nav.compare, exact: true }).click()
    await expect(page).toHaveURL(/\/compare/)
    await expect(page.getByRole('heading', { level: 1, name: en.compare.title })).toBeVisible()
    await expect(page.getByTestId('tool-placeholder')).toHaveAttribute('data-tool', 'compare')
    // a tool that has not been asked has asked nothing
    expect(asked.filter(entry => entry.path === 'values')).toEqual([])

    await page.goto(STATIONS_LINK)
    await expect(table(page)).toBeVisible()
    // 31 days of March, one row each, and the unit in the header of the difference
    await expect(rows(page)).toHaveCount(31)
    await expect(table(page).getByRole('columnheader', { name: 'B − A (°C)' })).toBeVisible()
    expect(asked.filter(entry => entry.path === 'values').at(-1)!.query).toMatchObject({ stations: '00011,00044', timestamp: '2026-03-01/2026-03-31', parameters: 'daily/climate_summary/temperature_air_mean_2m' })
  })

  test('has a difference that is B minus A for every day, and none for a day a side lacks', async ({ page, baseURL }) => {
    await open(page, baseURL!, STATIONS_LINK)
    await expect(rows(page)).toHaveCount(31)
    // the mock's stations are 4 degrees apart: Großenkneten (B, 12 °C level) minus Donaueschingen (A, 8 °C level)
    const day = async (index: number) => (await rows(page).nth(index).locator('th, td').allInnerTexts()).map(text => text.trim())
    const first = await day(0)
    expect(first.slice(0, 3)).toEqual(['1', '2026-03-01', '2026-03-01'])
    expect(first[5]).toBe('+4')
    // the 5th of every month Großenkneten has a null: no difference, and not a zero or a minus
    const fifth = await day(4)
    expect(fifth[4]).toBe('')
    expect(fifth[5]).toBe('')
    await expect(page.getByTestId('compare-summary')).toContainText('30 of 31 days compared')
    await expect(page.getByTestId('compare-mean')).toContainText('B − A = +4 °C')
  })

  test('draws one chart with both series, B dashed with square markers, and the table is its alternative', async ({ page, baseURL }) => {
    await open(page, baseURL!, STATIONS_LINK)
    const figure = page.getByRole('figure', { name: /Chart of Mean air temperature/ })
    await expect(figure).toBeVisible()
    await expect(figure).toHaveAccessibleName(/A, Donaueschingen \(Landeplatz\) \(00011\), and B, Großenkneten \(00044\)/)
    // the legend names both sides, and the sentence that describes the chart says the table holds every value
    const legend = page.locator('.xc-legend button')
    await expect(legend).toHaveCount(2)
    await expect(legend.nth(0)).toHaveAccessibleName(/A · Donaueschingen/)
    await expect(legend.nth(1)).toHaveAccessibleName(/B · Großenkneten/)
    await expect(page.getByTestId('compare-chart-note')).toContainText('The table below holds every value of the chart.')
    await expect(page.getByTestId('compare-chart-note')).toContainText('Aligned by calendar date')
    // the lines differ by more than the colour: a dashed line and another marker
    const svg = figure.locator('svg').first()
    await expect(svg).toBeVisible()
    expect(await svg.locator('path[stroke-dasharray]').count(), 'a dashed line for B').toBeGreaterThan(0)
  })

  test('opens two periods of one station by their place in the period: day 1 of A against day 1 of B', async ({ page, baseURL }) => {
    const { asked } = await open(page, baseURL!, PERIODS_LINK)
    await expect(rows(page)).toHaveCount(31)
    const first = (await rows(page).first().locator('th, td').allInnerTexts()).map(text => text.trim())
    // the mock's year is 1.5 °C warmer for each year: B is 1.5 °C above A on the same day of the year, the dates are the periods' own
    expect(first.slice(0, 3)).toEqual(['1', '2025-03-01', '2026-03-01'])
    await expect(page.getByTestId('compare-chart-note')).toContainText('Aligned by day of the period: day 1 of A with day 1 of B')
    // two requests, one for each period, of the one station
    expect(asked.filter(entry => entry.path === 'values').map(entry => [entry.query.stations, entry.query.timestamp]).sort()).toEqual([['00011', '2025-03-01/2025-03-31'], ['00011', '2026-03-01/2026-03-31']])
    await expect(page.getByTestId('compare-mean')).toContainText('B − A = +')
  })

  test('says what is subtracted for totals: a day\'s rain is a total, so the difference is of two totals', async ({ page, baseURL }) => {
    await open(page, baseURL!, STATIONS_LINK.replace('temperature_air_mean_2m', 'precipitation_amount'))
    await expect(table(page)).toBeVisible()
    await expect(page.getByTestId('compare-sum')).toContainText('In total, A is')
    await expect(page.getByTestId('compare-difference-note')).toContainText('totals (or counts)')
  })

  test('credits the provider for both sides, with the note of what was done to the data, and writes both into the files', async ({ page, baseURL }) => {
    await open(page, baseURL!, STATIONS_LINK)
    await expect(table(page)).toBeVisible()
    const credit = page.getByTestId('compare-credit')
    await expect(credit).toContainText(en.compare.creditBoth)
    await expect(credit).toContainText('Source: Deutscher Wetterdienst')
    await expect(credit.getByTestId('processing-note')).toBeVisible()
    // a download holds both sides and the difference, and the credit before the header
    await page.getByTestId('compare-download').click()
    const download = page.waitForEvent('download')
    await page.getByRole('menuitem', { name: 'CSV' }).click()
    const file = await download
    expect(file.suggestedFilename()).toBe('compare.csv')
    const text = readFileSync((await file.path())!, 'utf-8')
    const lines = text.split('\n')
    expect(lines[0]).toContain('temperature_air_mean_2m (°C), daily, difference = B - A')
    expect(lines.some(line => line.startsWith('# Source: Deutscher Wetterdienst'))).toBe(true)
    expect(lines.some(line => line.startsWith('# Side A: Donaueschingen (Landeplatz) (00011). Side B: Großenkneten (00044).'))).toBe(true)
    expect(lines.find(line => line.startsWith('step,'))).toBe('step,date_a,date_b,value_a,value_b,difference')
    expect(lines.find(line => line.startsWith('1,2026-03-01,2026-03-01,'))).toMatch(/,\+?4$/)
    // the JSON too
    await page.getByTestId('compare-download').click()
    const jsonDownload = page.waitForEvent('download')
    await page.getByRole('menuitem', { name: 'JSON' }).click()
    const json = JSON.parse(readFileSync((await (await jsonDownload).path())!, 'utf-8'))
    expect(json.metadata.provider.attribution).toBe('Source: Deutscher Wetterdienst')
    expect(json.metadata.compare.sides.a.name).toBe('Donaueschingen (Landeplatz) (00011)')
    expect(json.values).toHaveLength(31)
    expect(json.values[0].difference).toBe(4)
  })

  test('writes the comparison into the address as it is chosen: a link opens it again', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/compare')
    await expect(page).toHaveURL(/compare=stations/)
    await expect(page.getByTestId('compare-parameter')).toBeVisible()
    // the pickers are labelled by the side they pick
    await expect(page.getByText('Station A', { exact: true })).toBeVisible()
    await expect(page.getByText('Station B', { exact: true })).toBeVisible()
    await page.getByTestId('compare-by-periods').click()
    await expect(page).toHaveURL(/compare=periods/)
    await expect(page.getByTestId('compare-by-periods')).toHaveAttribute('aria-pressed', 'true')
    await expect(page.getByRole('group', { name: en.compare.periodA }).getByLabel(en.compare.start)).toBeVisible()
    await expect(page.getByRole('group', { name: en.compare.periodB }).getByLabel(en.compare.end)).toBeVisible()
    await expect(page.getByRole('group', { name: en.compare.periodA })).toBeVisible()
    await expect(page.getByRole('group', { name: en.compare.periodB })).toBeVisible()
    // both periods start filled: the last complete month, and the same one a year before
    const query = new URL(page.url()).searchParams
    expect(query.get('periodB')).toMatch(/^\d{4}-\d{2}-01\/\d{4}-\d{2}-\d{2}$/)
    expect(query.get('periodA')!.slice(0, 4)).toBe(String(Number(query.get('periodB')!.slice(0, 4)) - 1))
  })

  test('is reached by keys alone: the form is in the order of the page, Show is a button, the table scrolls by keys', async ({ page, baseURL }) => {
    await open(page, baseURL!, STATIONS_LINK)
    await expect(table(page)).toBeVisible()
    const region = page.getByRole('region', { name: en.compare.tableTitle })
    await region.focus()
    await expect(region).toBeFocused()
    // the region holds more rows than its height shows, so it is a scroll region that keys reach
    expect(await region.evaluate(element => element.scrollHeight - element.clientHeight)).toBeGreaterThan(0)
    await page.keyboard.press('PageDown')
    await expect.poll(() => region.evaluate(element => element.scrollTop)).toBeGreaterThan(0)
    // the toggle of what is compared is two buttons, the chosen one pressed
    await page.getByTestId('compare-by-stations').focus()
    await page.keyboard.press('Tab')
    await expect(page.getByTestId('compare-by-periods')).toBeFocused()
    await page.keyboard.press('Enter')
    await expect(page.getByTestId('compare-by-periods')).toHaveAttribute('aria-pressed', 'true')
  })

  test('refuses a link\'s two sides that are not the same kind of number, with the reason and no table', async ({ page, baseURL }) => {
    await mockBackend(page, baseURL!, {
      ...compareHandlers(),
      values: (url) => {
        // the second period answers in Kelvin
        const march2026 = (url.searchParams.get('timestamp') ?? '').startsWith('2026')
        const rows = [{ station_id: '00011', resolution: 'daily', dataset: 'climate_summary', parameter: 'temperature_air_mean_2m', timestamp: `${march2026 ? 2026 : 2025}-03-01T00:00:00+00:00`, value: 280, quality_flags: null }]
        return { metadata: { parameters: [{ resolution: 'daily', dataset: 'climate_summary', name: 'temperature_air_mean_2m', name_original: 'tmk', description: null, quantity: 'temperature', unit: march2026 ? 'K' : '°C', aggregation: 'mean', timestamp_position: 'start' }] }, values: rows }
      },
    })
    await page.goto(PERIODS_LINK)
    await expect(page.getByTestId('compare-refused')).toContainText('not the same kind of number (another unit), so no difference is calculated')
    await expect(table(page)).toHaveCount(0)
  })

  test('says it where the backend fails, and asks again on Show', async ({ page, baseURL }) => {
    let fail = true
    const handlers = compareHandlers()
    await mockBackend(page, baseURL!, {
      ...handlers,
      values: (url, route) => {
        if (fail)
          return new ApiFailure(502, 'The provider could not be reached')
        return handlers.values!(url, route)
      },
    })
    await page.goto(STATIONS_LINK)
    await expect(page.getByRole('alert').filter({ hasText: 'The provider could not be reached' })).toBeVisible()
    fail = false
    await page.getByTestId('compare-fetch').click()
    await expect(table(page)).toBeVisible()
  })

  test('has controls that are 24 px or more (WCAG 2.5.8) and no page that scrolls sideways', async ({ page, baseURL }) => {
    await open(page, baseURL!, STATIONS_LINK)
    await expect(table(page)).toBeVisible()
    for (const target of [page.getByTestId('compare-fetch'), page.getByTestId('compare-by-stations'), page.getByTestId('compare-by-periods')]) {
      const box = (await target.boundingBox())!
      expectAtLeastPx(box.width, 24)
      expectAtLeastPx(box.height, 24)
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(0)
  })

  test('is in German with its own words, the numbers as German writes them', async ({ page, baseURL }) => {
    await open(page, baseURL!, STATIONS_LINK, 'de')
    await expect(page.getByRole('heading', { level: 1, name: de.compare.title })).toBeVisible()
    await expect(table(page)).toBeVisible()
    await expect(table(page).getByRole('columnheader', { name: 'B − A (°C)' })).toBeVisible()
    await expect(page.getByTestId('compare-mean')).toContainText('B − A = +4 °C')
    await expect(page.getByTestId('compare-chart-note')).toContainText(de.compare.alignDaysStations)
    // the decimal comma
    const first = (await rows(page).first().locator('td').allInnerTexts()).join(' ')
    expect(first).toMatch(/\d,\d/)
  })
})

test.describe('on a phone', () => {
  test.use({ viewport: { width: 390, height: 844 } })

  test('is in the Menu\'s sheet of the tab bar, and holds the form and the result in one column', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/')
    await page.getByRole('button', { name: en.header.menu }).click()
    await page.getByRole('dialog').getByRole('link', { name: new RegExp(`^${en.nav.compare}`) }).click()
    await expect(page).toHaveURL(/\/compare/)
    await expect(page.getByRole('heading', { level: 1, name: en.compare.title })).toBeVisible()
    await page.goto(STATIONS_LINK)
    await expect(table(page)).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(0)
  })
})
