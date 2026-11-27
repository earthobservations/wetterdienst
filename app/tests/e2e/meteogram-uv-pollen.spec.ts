import type { Page } from '@playwright/test'
import { expect, test } from '@playwright/test'
import { MOSMIX_DRESDEN, pollenValues } from '../helpers/uv-pollen'
import { defaultHandlers, mockBackend } from './accessibility/mock-backend'

// The "UV & pollen" panel of the forecast (GH-4501), under the chart of a station in Germany. The API is answered by the mock backend (the UV
// places Berlin, Dresden, Hamburg and München, the 27 pollen regions with a spring's load, and a station of the observation network near Dresden,
// which gives it Sachsen and two part-regions), so the spec needs nothing but the app. What it holds is what a component test cannot: the panel in a
// browser, at a phone's width and in the dark, where nothing may make the page scroll sideways (WCAG 1.4.10) and a number must be legible on its
// fill (WCAG 1.4.3).

const DRESDEN = '/meteogram?station=10488&view=chart'
// Jan Mayen, which is outside the box of Germany
const JAN_MAYEN = '/meteogram?station=01001&view=chart'

const panel = (page: Page) => page.getByTestId('uv-pollen-panel')
const chips = (page: Page) => page.getByTestId('pollen-chips').getByRole('button')

/** The mock's answers, with the forecast station of Dresden-Klotzsche added to its list, which a link can name */
function withDresden(extra: Parameters<typeof mockBackend>[2] = {}): NonNullable<Parameters<typeof mockBackend>[2]> {
  const defaults = defaultHandlers()
  return {
    stations: (url, route) => {
      const wanted = url.searchParams.getAll('stations').flatMap(ids => ids.split(','))
      if (url.searchParams.get('network') === 'mosmix' && wanted.includes(MOSMIX_DRESDEN.station_id))
        return { stations: [{ ...MOSMIX_DRESDEN, region: null, start_timestamp: null, end_timestamp: null }] }
      return defaults.stations!(url, route)
    },
    ...extra,
  }
}

async function open(page: Page, baseURL: string, path = DRESDEN, override = withDresden()) {
  const backend = await mockBackend(page, baseURL, override)
  await page.goto(path)
  await expect(page.locator('.mg-canvas svg').first()).toBeVisible()
  return backend
}

/** Whether the page scrolls sideways: its scroll width is more than the window's */
const scrollsSideways = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)

// WCAG 2.x relative luminance, and the contrast ratio of two colours
function channels(color: string) {
  const rgb = /^rgba?\(\s*(\d+)[\s,]+(\d+)[\s,]+(\d+)/.exec(color)!
  return [1, 2, 3].map(i => Number(rgb[i]))
}
function luminance(color: string) {
  const [r, g, b] = channels(color).map(c => c / 255).map(c => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4))
  return 0.2126 * r! + 0.7152 * g! + 0.0722 * b!
}
function contrast(a: string, b: string) {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi! + 0.05) / (lo! + 0.05)
}

test.describe('at a station in Germany', () => {
  test('shows the UV index of the nearest place and the pollen load of the state under the chart', async ({ page, baseURL }) => {
    const backend = await open(page, baseURL!)
    await expect(panel(page)).toBeVisible()
    await expect(page.getByTestId('uv-part').getByRole('heading', { level: 4 })).toHaveText(/^UV index for Dresden \(\d+ km\)$/)
    await expect(page.getByTestId('uv-day')).toHaveCount(3)
    // the class is in words beside the number, never the colour alone
    await expect(page.getByTestId('uv-class')).toHaveText(['Moderate', 'Moderate', 'Very high'])
    await expect(page.getByTestId('pollen-part').getByRole('heading', { level: 4 })).toHaveText('Pollen load for Sachsen')
    await expect(chips(page)).toHaveText(['Tiefland Sachsen', 'Mittelgebirge Sachsen'])
    await expect(chips(page).first()).toHaveAttribute('aria-pressed', 'true')
    await expect(page.getByTestId('pollen-row')).toHaveCount(8)
    // below the chart, not beside it
    const [chart, below] = await Promise.all([page.locator('.mg-canvas').first().boundingBox(), panel(page).boundingBox()])
    expect(below!.y).toBeGreaterThan(chart!.y + chart!.height)
    // every request was one the mock answers
    expect(backend.unanswered).toEqual([])
  })

  test('shows the grid of the part that is chosen, and remembers the choice for the next visit', async ({ page, baseURL }) => {
    await open(page, baseURL!)
    await expect(chips(page)).toHaveCount(2)
    await chips(page).nth(1).click()
    await expect(chips(page).nth(1)).toHaveAttribute('aria-pressed', 'true')
    await expect(chips(page).first()).toHaveAttribute('aria-pressed', 'false')
    await page.reload()
    await expect(chips(page)).toHaveCount(2)
    await expect(chips(page).nth(1)).toHaveAttribute('aria-pressed', 'true')
  })

  test('says in one line that no pollen load is expected, out of season', async ({ page, baseURL }) => {
    const defaults = defaultHandlers()
    await open(page, baseURL!, DRESDEN, withDresden({
      values: (url, route) => url.searchParams.get('network') === 'pollen'
        ? { values: pollenValues(url.searchParams.get('stations')!.split(','), { hazel: [0, 0, 0] }) }
        : defaults.values!(url, route),
    }))
    await expect(page.getByTestId('pollen-out-of-season')).toHaveText('No pollen load is expected for the next three days.')
    await expect(page.getByTestId('pollen-grid')).toHaveCount(0)
    // the UV index is still there
    await expect(page.getByTestId('uv-part')).toBeVisible()
  })

  for (const scheme of ['light', 'dark'] as const) {
    test(`fits a phone's width in the ${scheme} scheme, with no sideways scroll`, async ({ page, baseURL }) => {
      await page.emulateMedia({ colorScheme: scheme })
      await page.setViewportSize({ width: 390, height: 844 })
      await open(page, baseURL!)
      await expect(panel(page)).toBeVisible()
      expect(await scrollsSideways(page)).toBe(false)
      const box = (await panel(page).boundingBox())!
      expect(box.x).toBeGreaterThanOrEqual(0)
      expect(box.x + box.width).toBeLessThanOrEqual(390)
    })

    test(`writes each UV number legibly on its colour in the ${scheme} scheme (4.5:1)`, async ({ page, baseURL }) => {
      await page.emulateMedia({ colorScheme: scheme })
      await open(page, baseURL!)
      const badges = await page.getByTestId('uv-index').evaluateAll(elements => elements.map((element) => {
        const style = getComputedStyle(element)
        return { color: style.color, background: style.backgroundColor }
      }))
      expect(badges).toHaveLength(3)
      for (const badge of badges)
        expect(contrast(badge.color, badge.background), JSON.stringify(badge)).toBeGreaterThanOrEqual(4.5)
    })
  }
})

test.describe('at a station outside Germany', () => {
  test('shows no panel, and asks for none of its data', async ({ page, baseURL }) => {
    const asked: string[] = []
    page.on('request', (request) => {
      const url = new URL(request.url())
      if (url.pathname.startsWith('/api/') && /uvi|pollen/.test(url.search))
        asked.push(url.pathname + url.search)
    })
    const backend = await open(page, baseURL!, JAN_MAYEN)
    await page.waitForTimeout(500)
    await expect(panel(page)).toHaveCount(0)
    expect(asked).toEqual([])
    expect(backend.unanswered).toEqual([])
  })
})
