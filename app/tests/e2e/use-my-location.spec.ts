import type { Page } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { expect, test } from '@playwright/test'
import { defaultHandlers, mockBackend } from './accessibility/mock-backend'

// "Use my location" (GH-3651), in a browser with a position: the forecast's station picker and the map. Playwright's
// `geolocation` and `permissions` context options are the browser's own answer to the Geolocation API; the backend is
// the accessibility spec's mock, with the `stations` request ranked by the position as the real one ranks it, so that
// nothing reaches a provider. The position is 53.5412 N, 10.1987 E, which the app rounds to 53.54, 10.2 before it
// goes anywhere.

const en = JSON.parse(readFileSync(fileURLToPath(new URL('../../i18n/locales/en.json', import.meta.url)), 'utf-8'))

/** What the `stations` request was given, in order, so that a test says what was sent and when */
const asked: Array<Record<string, string>> = []

/** The mock's `stations`, ranked by the distance to `latitude` and `longitude` where the request has them, as the REST API does */
function ranked() {
  const list = defaultHandlers().stations!
  return {
    stations: async (url: URL, route: Parameters<typeof list>[1]) => {
      asked.push(Object.fromEntries(url.searchParams))
      const answer = await list(url, route) as { stations: Array<{ latitude: number, longitude: number }> }
      const latitude = Number(url.searchParams.get('latitude'))
      const longitude = Number(url.searchParams.get('longitude'))
      if (!url.searchParams.get('rank'))
        return answer
      const distance = (station: { latitude: number, longitude: number }) => (station.latitude - latitude) ** 2 + (station.longitude - longitude) ** 2
      return { stations: [...answer.stations].sort((a, b) => distance(a) - distance(b)).slice(0, Number(url.searchParams.get('rank'))) }
    },
  }
}

async function open(page: Page, baseURL: string, path: string, title: string) {
  asked.length = 0
  await page.context().addCookies([{ name: 'wd_lang', value: 'en', url: baseURL }])
  await mockBackend(page, baseURL, ranked())
  await page.goto(path)
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(title)
}

test.describe('with the position allowed', () => {
  test.use({ viewport: { width: 1440, height: 900 }, geolocation: { latitude: 53.5412, longitude: 10.1987 }, permissions: ['geolocation'] })

  test('the forecast picks the nearest station, tells how far it is, and sent only the rounded position, on the press', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/meteogram', en.meteogram.title)
    // nothing is asked of the browser or of the backend by a page that is only opened
    expect(asked.filter(query => query.latitude)).toEqual([])
    await expect(page.getByText(en.location.note)).toBeVisible()

    const button = page.getByRole('button', { name: en.location.button })
    // the forecast of the station found is then asked for
    const forecast = page.waitForRequest(request => request.url().includes('/api/values') && request.url().includes('stations=10147'))
    await button.click()

    const chip = page.getByTestId('station-picker-chips').getByRole('button', { name: /HAMBURG-FUHLSBUETTEL/ })
    await expect(chip).toBeVisible()
    await expect(page.getByTestId('use-my-location-status')).toHaveText(/^Nearest station: HAMBURG-FUHLSBUETTEL \(10147\), \d+(\.\d)? km from your position\.$/)
    // the one request that carries the position: rounded to two decimals, ranked by one, to the app's own backend
    const located = asked.filter(query => query.latitude)
    expect(located).toHaveLength(1)
    expect(located[0]).toMatchObject({ provider: 'dwd', network: 'mosmix', latitude: '53.54', longitude: '10.2', rank: '1' })
    // and the position is in no address
    expect(page.url()).not.toMatch(/53\.5|10\.19|latitude|lat=/)
    await forecast
  })

  test('the map centres on the position, marks it, and picks the nearest station as a place of its own', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/map', en.mapTool.title)
    await expect(page.getByTestId('map-count')).toBeVisible()
    const map = page.getByRole('application', { name: /^Station map/ })
    await expect(map.locator('canvas').first()).toBeAttached()
    // the map opens on the whole of Germany, with no mark of a position
    await expect(map.locator('path[fill-opacity="0.55"]')).toHaveCount(0)

    await page.getByRole('button', { name: en.location.button }).click()

    await expect(page.getByTestId('map-station-name')).toHaveText('HAMBURG-FUHLSBUETTEL')
    await expect(page.getByTestId('map-place')).toHaveText(/Your position, \d+(\.\d)? km from this station$/)
    // the mark: a ring round a dot, apart from the station's own
    await expect(map.locator('path[fill-opacity="0.55"]')).toHaveCount(1)
    // the map has moved in, to a zoom where the neighbourhood is seen
    await expect.poll(async () => page.evaluate(() => {
      const zooms = [...document.querySelectorAll<HTMLImageElement>('.station-map-tiles img.leaflet-tile')]
        .map(tile => Number(/\/(\d+)\/\d+\/\d+\.png/.exec(tile.src)?.[1]))
        .filter(zoom => !Number.isNaN(zoom))
      return zooms.length ? Math.max(...zooms) : 0
    })).toBeGreaterThanOrEqual(9)
    // the station is in the address, and the position is not
    await expect(page).toHaveURL(/station=10147/)
    expect(page.url()).not.toMatch(/lat=|lon=|53\.54/)
  })
})

test.describe('with the position refused', () => {
  // no permission granted: the browser answers the Geolocation API with a refusal
  test.use({ viewport: { width: 1440, height: 900 }, permissions: [] })

  test('the picker says how to allow it in an alert, and the search stays the way in', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/meteogram', en.meteogram.title)
    await page.getByRole('button', { name: en.location.button }).click()

    const alert = page.getByTestId('use-my-location-problem')
    await expect(alert).toHaveAttribute('role', 'alert')
    await expect(alert).toHaveText(en.location.denied)
    expect(asked.filter(query => query.latitude)).toEqual([])
    // nothing is picked, and the search of stations is still there
    await expect(page.getByTestId('station-picker-chips')).toHaveCount(0)
    await expect(page.getByRole('button', { name: en.location.button })).toBeEnabled()
    await expect(page.getByRole('button', { name: en.common.stationSearch })).toBeVisible()
  })
})
