import type { Page } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { expect, test } from '@playwright/test'
import { mockBackend } from './accessibility/mock-backend'

// The Heavy-rainfall tool (GH-4500), by its main path in a browser: the point of the link, the table of 22 durations by 9 return periods,
// the curves, the cell outlined on the map, a click on the map that chooses a point, the words for a point outside DWD's grid, depth and
// intensity, a phone and the dark page. The backend is the accessibility spec's mock, which answers `/api/kostra` for a point in the box
// of DWD's grid and with its 400 for one outside it, so nothing here reaches DWD, and the map's tiles are answered with a pixel.

const en = JSON.parse(readFileSync(fileURLToPath(new URL('../../i18n/locales/en.json', import.meta.url)), 'utf-8'))

const ZINNWALD = '/kostra?lat=50.7313&lon=13.7516'

async function open(page: Page, baseURL: string, path = ZINNWALD) {
  await page.context().addCookies([{ name: 'wd_lang', value: 'en', url: baseURL }])
  await mockBackend(page, baseURL)
  await page.goto(path)
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(en.kostra.title)
}

/** The page does not scroll sideways: the table scrolls in its box, the page never does (WCAG 1.4.10) */
const scrollsSideways = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth > 0)

test.describe('the heavy rainfall on a wide screen', () => {
  test.use({ viewport: { width: 1280, height: 900 } })

  test('shows the table of the point of the link: 22 durations by 9 return periods, the depth with DWD\'s uncertainty under it', async ({ page, baseURL }) => {
    await open(page, baseURL!)
    const table = page.getByTestId('kostra-table')
    await expect(table).toBeVisible()
    await expect(table.locator('tbody tr')).toHaveCount(22)
    await expect(table.locator('thead th[data-years]')).toHaveCount(9)
    await expect(table.locator('tbody tr').first().locator('th')).toHaveText('5 min')
    await expect(table.locator('tbody tr').last().locator('th')).toHaveText('7 d')
    await expect(table.locator('tr[data-minutes="60"] td[data-years="100"] .kostra-uncertainty')).toContainText('±12 %')
    await expect(page.getByTestId('kostra-cell')).toContainText('DWD grid cell 144197')
    await expect(page.getByTestId('kostra-estimate')).toHaveText(/not measurements at the point/)
    await expect(page.getByTestId('kostra-credit')).toContainText('Source: Deutscher Wetterdienst')
  })

  test('draws nine curves with a legend, and reads the values of a duration by the keys', async ({ page, baseURL }) => {
    await open(page, baseURL!)
    const chart = page.getByTestId('kostra-chart')
    await expect(chart.locator('[data-drawn="true"] svg')).toBeVisible()
    await expect(page.locator('.kostra-legend-item')).toHaveText(['1', '2', '3', '5', '10', '20', '30', '50', '100'])
    // the axis is labelled in min, h and d
    const axis = await chart.locator('svg text').allTextContents()
    for (const label of ['5 min', '15 min', '1 h', '6 h', '1 d', '7 d'])
      expect(axis).toContain(label)
    await page.getByTestId('kostra-stage').focus()
    await page.keyboard.press('Home')
    await expect(page.getByTestId('kostra-readout-title')).toHaveText('5 min')
    await page.keyboard.press('ArrowRight')
    await expect(page.getByTestId('kostra-readout-title')).toHaveText('10 min')
    await page.keyboard.press('Escape')
    await expect(page.getByTestId('kostra-readout')).toHaveCount(0)
  })

  test('outlines the 5 km cell on the map and marks the point', async ({ page, baseURL }) => {
    await open(page, baseURL!)
    await expect(page.getByTestId('kostra-table')).toBeVisible()
    await expect(page.getByRole('img', { name: en.kostra.pointMarker })).toHaveCount(1)
    // the cell is one polygon of the map's own pane
    await expect(page.locator('.leaflet-station-marks-pane path').first()).toBeVisible()
  })

  test('switches between the depth and the intensity, which change the table and the chart and keep the uncertainty', async ({ page, baseURL }) => {
    await open(page, baseURL!)
    const cell = page.locator('tr[data-minutes="60"] td[data-years="100"]')
    const depth = await cell.locator('.kostra-value').textContent()
    await page.getByRole('radio', { name: /^Intensity/ }).click()
    await expect(cell.locator('.kostra-value')).not.toHaveText(depth!)
    await expect(cell.locator('.kostra-uncertainty')).toContainText('±12 %')
    await expect(page.locator('.kostra-corner-unit')).toHaveText('l/(s·ha)')
    await page.getByRole('radio', { name: /^Depth/ }).click()
    await expect(cell.locator('.kostra-value')).toHaveText(depth!)
  })

  test('takes a click on the map as the point: it is in the link, and the table is that of its cell', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/kostra')
    await expect(page.getByTestId('tool-placeholder')).toBeVisible()
    const map = page.getByRole('application', { name: en.kostra.mapLabel })
    await expect(map).toBeVisible()
    await map.click({ position: { x: 200, y: 120 } })
    await expect(page).toHaveURL(/\/kostra\?lat=[\d.]+&lon=[\d.]+$/)
    await expect(page.getByTestId('kostra-table')).toBeVisible()
    await expect(page.getByTestId('kostra-point')).toContainText(en.kostra.pointLabel)
  })

  test('says in words that a point outside the grid has no values: a note, no alert', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/kostra?lat=40&lon=3')
    const note = page.getByTestId('kostra-outside')
    await expect(note).toContainText('There is no design rainfall for this point')
    await expect(page.getByRole('alert')).toHaveCount(0)
    await expect(page.getByTestId('kostra-table')).toHaveCount(0)
    // and a click inside the grid leaves it
    await page.getByRole('application', { name: en.kostra.mapLabel }).click({ position: { x: 200, y: 120 } })
    await expect(page.getByTestId('kostra-table')).toBeVisible()
  })

  test('is in the dark page too: the table and the curves are drawn in the colours of the night', async ({ page, baseURL }) => {
    await page.emulateMedia({ colorScheme: 'dark' })
    await page.addInitScript(() => localStorage.setItem('nuxt-color-mode', 'dark'))
    await open(page, baseURL!)
    await expect(page.locator('html')).toHaveClass(/dark/)
    await expect(page.getByTestId('kostra-chart').locator('[data-chart-scheme="dark"]')).toBeVisible()
    await expect(page.getByTestId('kostra-table')).toBeVisible()
  })
})

test.describe('the heavy rainfall on a phone', () => {
  test.use({ viewport: { width: 390, height: 844 } })

  test('does not scroll the page sideways: the table scrolls in its own box, which the keyboard reaches', async ({ page, baseURL }) => {
    await open(page, baseURL!)
    await expect(page.getByTestId('kostra-table')).toBeVisible()
    expect(await scrollsSideways(page)).toBe(false)
    const box = page.getByTestId('kostra-table-scroll')
    expect(await box.evaluate(el => el.scrollWidth > el.clientWidth)).toBe(true)
    await box.focus()
    await expect(box).toBeFocused()
    // the durations stay at the left edge while the table is scrolled
    await box.evaluate(el => el.scrollTo({ left: 400 }))
    const first = await page.locator('tbody th.kostra-duration').first().boundingBox()
    const edge = await box.boundingBox()
    expect(Math.abs(first!.x - edge!.x)).toBeLessThan(3)
  })

  test('has the heavy rainfall in the Menu and not in the bar of four', async ({ page, baseURL }) => {
    await open(page, baseURL!)
    const bar = page.getByRole('navigation', { name: en.shell.mainNav })
    expect(await bar.locator('li').allInnerTexts()).toEqual([en.nav.meteogram, en.nav.explorer, en.nav.stripes, en.nav.radar, en.header.menu])
    await page.getByRole('button', { name: en.header.menu, exact: true }).click()
    await expect(page.getByRole('dialog', { name: en.header.menu }).getByRole('link', { name: en.nav.kostra })).toHaveAttribute('aria-current', 'page')
  })

  test('does not scroll sideways for a point outside the grid either', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/kostra?lat=40&lon=3')
    await expect(page.getByTestId('kostra-outside')).toBeVisible()
    expect(await scrollsSideways(page)).toBe(false)
  })
})
