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
    // and only the button is shown at first: the box and its note come after a press (GH-4011)
    await expect(page.getByText(en.location.note)).toHaveCount(0)
    await expect(page.getByRole('checkbox')).toHaveCount(0)

    const button = page.getByRole('button', { name: en.location.button })
    // the forecast of the station found is then asked for
    const forecast = page.waitForRequest(request => request.url().includes('/api/values') && request.url().includes('stations=10147'))
    await button.click()

    const chip = page.getByTestId('station-picker-chips').getByRole('button', { name: /HAMBURG-FUHLSBUETTEL/ })
    await expect(chip).toBeVisible()
    await expect(page.getByTestId('use-my-location-status')).toHaveText(/^Nearest station: HAMBURG-FUHLSBUETTEL \(10147\), \d+(\.\d)? km from your position\.$/)
    // a position is in hand and nothing is stored: the box, unticked, and the note, which the button is described by
    await expect(page.getByRole('checkbox', { name: en.location.remember })).not.toBeChecked()
    await expect(page.getByText(en.location.note)).toBeVisible()
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

test.describe('the stored position', () => {
  test.use({ viewport: { width: 1440, height: 900 }, geolocation: { latitude: 53.5412, longitude: 10.1987 }, permissions: ['geolocation'] })

  const stored = (page: Page) => page.evaluate(() => localStorage.getItem('wd-location'))

  test('is told by a control beside the button, kept over a reload, and forgotten with the keyboard, which puts the focus back on the button (GH-4010, GH-4011)', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/meteogram', en.meteogram.title)
    const button = page.getByTestId('use-my-location-button')
    const box = page.getByRole('checkbox', { name: en.location.remember })
    const chip = page.getByRole('button', { name: en.location.storedLabel })

    // press, tick: the control takes the box's and the note's place, and the focus
    await button.click()
    await box.click()
    await expect(chip).toBeVisible()
    await expect(chip).toHaveText(en.location.stored)
    await expect(chip).toBeFocused()
    await expect(box).toHaveCount(0)
    await expect(page.getByText(en.location.note)).toHaveCount(0)
    expect(JSON.parse((await stored(page))!)).toEqual({ latitude: 53.54, longitude: 10.2 })

    // a later visit shows it at once, with no box, no note and nothing asked of the browser or the backend
    asked.length = 0
    await page.reload()
    await expect(page.getByRole('heading', { level: 1 })).toHaveText(en.meteogram.title)
    await expect(chip).toBeVisible()
    await expect(box).toHaveCount(0)
    await expect(page.getByText(en.location.note)).toHaveCount(0)
    expect(asked.filter(query => query.latitude)).toEqual([])

    // the keyboard opens it to the position and the way to forget it, and Escape closes it again with the focus on it
    await chip.focus()
    await page.keyboard.press('Enter')
    await expect(chip).toHaveAttribute('aria-expanded', 'true')
    await expect(page.getByTestId('use-my-location-remembered')).toContainText('53.54, 10.2')
    // from "Forget" as well as from the control: the details close and the focus is on the control, not lost with them
    await page.keyboard.press('Tab')
    await expect(page.getByRole('button', { name: en.location.forget })).toBeFocused()
    await page.keyboard.press('Escape')
    await expect(page.getByTestId('use-my-location-remembered')).toHaveCount(0)
    await expect(chip).toBeFocused()

    // opened again (a disclosure: the focus stays on the control), the next Tab is "Forget", which follows it in the tab
    // order, and the one after it goes on to the next control of the page, not out of it or round in a loop
    await page.keyboard.press('Enter')
    const forget = page.getByRole('button', { name: en.location.forget })
    await expect(chip).toBeFocused()
    await page.keyboard.press('Tab')
    await expect(forget).toBeFocused()
    await page.keyboard.press('Tab')
    await expect.poll(() => page.evaluate(() => {
      const active = document.activeElement
      return active !== null && active !== document.body && !active.closest('[data-testid="use-my-location-remembered"]') && active.getAttribute('data-testid') !== 'use-my-location-stored'
    })).toBe(true)
    await page.keyboard.press('Shift+Tab')
    await expect(forget).toBeFocused()
    await page.keyboard.press('Enter')
    await expect(chip).toHaveCount(0)
    await expect(button).toBeFocused()
    expect(await stored(page)).toBeNull()
    await expect(box).toHaveCount(0)

    // press, tick again: stored again, and the control is back (GH-4010: it stored nothing)
    await button.click()
    await box.click()
    await expect(chip).toBeVisible()
    expect(JSON.parse((await stored(page))!)).toEqual({ latitude: 53.54, longitude: 10.2 })
  })
})

test.describe('the stored position and the browser\'s permission (GH-4014)', () => {
  test.use({ viewport: { width: 1440, height: 900 }, geolocation: { latitude: 53.5412, longitude: 10.1987 }, permissions: ['geolocation'] })

  const stored = (page: Page) => page.evaluate(() => localStorage.getItem('wd-location'))

  test('a press that finds the permission withdrawn deletes the stored position and says so; the browser is not asked', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/meteogram', en.meteogram.title)
    const button = page.getByTestId('use-my-location-button')
    const chip = page.getByRole('button', { name: en.location.storedLabel })
    await button.click()
    await page.getByRole('checkbox', { name: en.location.remember }).click()
    await expect(chip).toBeVisible()

    // Playwright's `permissions` cannot withdraw a permission in a running page: the Permissions API answers `denied` from here on
    await page.evaluate(() => {
      navigator.permissions.query = async () => ({ state: 'denied' }) as PermissionStatus
    })
    asked.length = 0
    await button.click()
    await expect(page.getByTestId('use-my-location-withdrawn')).toHaveText(en.location.withdrawn)
    await expect(chip).toHaveCount(0)
    expect(await stored(page)).toBeNull()
    expect(asked.filter(query => query.latitude)).toEqual([])
  })

  test('a stored position whose station is the place of the home page is deleted at load where the permission is `denied`, and the reader is told', async ({ page, baseURL }) => {
    await page.addInitScript(() => {
      localStorage.setItem('wd-location', JSON.stringify({ latitude: 53.6, longitude: 10.05 }))
      localStorage.setItem('wd-place', JSON.stringify({ id: '01975', name: 'Hamburg-Fuhlsbüttel', latitude: 53.63, longitude: 10, region: 'Hamburg', fromPosition: true }))
      navigator.permissions.query = async () => ({ state: 'denied' }) as PermissionStatus
    })
    asked.length = 0
    await page.context().addCookies([{ name: 'wd_lang', value: 'en', url: baseURL! }])
    await mockBackend(page, baseURL!, ranked())
    await page.goto('/?ask=rain')
    await expect(page.getByTestId('use-my-location-withdrawn')).toHaveText(en.location.withdrawn)
    await expect(page.getByRole('button', { name: en.location.storedLabel })).toHaveCount(0)
    expect(await page.evaluate(() => [localStorage.getItem('wd-location'), localStorage.getItem('wd-place')])).toEqual([null, null])
    expect(asked.filter(query => query.latitude === '53.63' || query.stations === '01975')).toEqual([])
  })

  test('a position forgotten in one tab is forgotten in the other open tab', async ({ page, baseURL, context }) => {
    await open(page, baseURL!, '/meteogram', en.meteogram.title)
    await page.getByTestId('use-my-location-button').click()
    await page.getByRole('checkbox', { name: en.location.remember }).click()
    await expect(page.getByRole('button', { name: en.location.storedLabel })).toBeVisible()

    const other = await context.newPage()
    await mockBackend(other, baseURL!, ranked())
    await other.goto('/meteogram')
    await expect(other.getByRole('heading', { level: 1 })).toHaveText(en.meteogram.title)
    const otherChip = other.getByRole('button', { name: en.location.storedLabel })
    await expect(otherChip).toBeVisible()

    await otherChip.click()
    await other.getByRole('button', { name: en.location.forget }).click()
    await expect(otherChip).toHaveCount(0)
    await expect(page.getByRole('button', { name: en.location.storedLabel })).toHaveCount(0)
    expect(await stored(page)).toBeNull()
  })
})

test.describe('the stored position, on the map', () => {
  test.use({ viewport: { width: 1440, height: 900 }, geolocation: { latitude: 53.5412, longitude: 10.1987 }, permissions: ['geolocation'] })

  test('is offered on the station card that the press picked, kept there, and forgotten there, with one copy of the option in the page at a time (GH-4011)', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/map', en.mapTool.title)
    await expect(page.getByTestId('map-count')).toBeVisible()
    const box = page.getByRole('checkbox', { name: en.location.remember })
    const chip = page.getByRole('button', { name: en.location.storedLabel })

    // the list has the button, and the option once a position is found; the station card replaces the list
    await page.getByTestId('use-my-location-button').click()
    await expect(page.getByTestId('map-station-name')).toHaveText('HAMBURG-FUHLSBUETTEL')
    await expect(page.getByTestId('use-my-location-button')).toHaveCount(0)
    await expect(box).toHaveCount(1)
    await expect(box).toBeVisible()
    await expect(page.getByText(en.location.note)).toHaveCount(1)
    expect(await page.evaluate(() => localStorage.getItem('wd-location'))).toBeNull()

    await box.click()
    await expect(chip).toHaveCount(1)
    await expect(chip).toBeFocused()
    await expect(box).toHaveCount(0)
    expect(JSON.parse((await page.evaluate(() => localStorage.getItem('wd-location')))!)).toEqual({ latitude: 53.54, longitude: 10.2 })

    await page.keyboard.press('Enter')
    await page.keyboard.press('Tab')
    await expect(page.getByRole('button', { name: en.location.forget })).toBeFocused()
    await page.keyboard.press('Enter')
    await expect(chip).toHaveCount(0)
    await expect(page.getByTestId('map-station-name')).toBeFocused()
    expect(await page.evaluate(() => localStorage.getItem('wd-location'))).toBeNull()

    // back to the list: the button alone again
    await page.getByTestId('map-back').click()
    await expect(page.getByTestId('use-my-location-button')).toBeVisible()
    await expect(box).toHaveCount(0)
    await expect(chip).toHaveCount(0)
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
