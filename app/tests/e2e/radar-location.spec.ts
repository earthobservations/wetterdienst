import type { Page } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { expect, test } from '@playwright/test'
import { exampleScan } from '../helpers/storm-cells-answer'
import { mockBackend } from './accessibility/mock-backend'

// The reader's own position on the Radar tool (GH-4287), in a browser with a position: the map tool's "Use my location", asked only on a
// press, the marker over the radar and the cells, the map centred on it, the way to hide it, a position outside the radar, a remembered
// position, and that no request of the backend carries a coordinate (the radar is the same for everyone). Playwright's `geolocation` and
// `permissions` context options are the browser's own answer to the Geolocation API; the backend is the accessibility spec's mock, and the
// map's tiles are answered with a pixel. The position is 53.5412 N, 10.1987 E (Hamburg), which the app rounds to 53.54, 10.2.

const en = JSON.parse(readFileSync(fileURLToPath(new URL('../../i18n/locales/en.json', import.meta.url)), 'utf-8'))

/** The requests the app made to its own origin that carry a question (the page, `/api/*`: a document, a fetch or an XHR, not a script or a style): what the backend and the app's server were told */
const toOrigin: string[] = []

async function open(page: Page, baseURL: string, handlers = {}) {
  toOrigin.length = 0
  await page.context().addCookies([{ name: 'wd_lang', value: 'en', url: baseURL }])
  await mockBackend(page, baseURL, handlers)
  page.on('request', (request) => {
    if (request.url().startsWith(baseURL) && ['document', 'fetch', 'xhr'].includes(request.resourceType()))
      toOrigin.push(`${request.method()} ${request.url()} ${request.postData() ?? ''}`)
  })
  await page.goto('/radar')
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(en.radar.title)
  await expect(page.getByTestId('radar-newest')).toBeVisible()
}

/** The highest zoom of the map's tiles: where the map is */
function zoomOf(page: Page) {
  return page.evaluate(() => Math.max(...[...document.querySelectorAll<HTMLImageElement>('.station-map-tiles img.leaflet-tile')]
    .map(tile => Number(/\/(\d+)\/\d+\/\d+\.png/.exec(tile.src)?.[1]))
    .filter(zoom => !Number.isNaN(zoom))))
}

/** The marker of the position: the ring that is named, as a screen reader meets it */
const marker = (page: Page) => page.getByRole('img', { name: en.radar.positionMarker })

const press = (page: Page) => page.getByRole('button', { name: en.location.button })

test.describe('the position on the radar, allowed', () => {
  test.use({ viewport: { width: 1440, height: 900 }, geolocation: { latitude: 53.5412, longitude: 10.1987 }, permissions: ['geolocation'] })

  test('is asked only on a press, marked over the radar and the cells, centred on, and sent to no request', async ({ page, baseURL }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await open(page, baseURL!, { 'storm-cells': () => exampleScan() })
    await expect(page.locator('.storm-cell-mark')).toHaveCount(4)
    // opened, nothing is marked, nothing is stored, and the button is there
    await expect(marker(page)).toHaveCount(0)
    await expect(page.getByTestId('radar-position-toggle')).toHaveCount(0)
    await expect(page.getByRole('checkbox')).toHaveCount(0)
    const before = await zoomOf(page)
    expect(before).toBeLessThan(9)

    await press(page).click()

    // the marker has a name, and the result is said in a status
    await expect(marker(page)).toHaveCount(1)
    await expect(page.getByTestId('use-my-location-status')).toHaveText(en.radar.positionShown)
    // the map has moved in, to a zoom where the surroundings are seen
    await expect.poll(() => zoomOf(page)).toBeGreaterThanOrEqual(9)
    // the marker is over the picture and over the cells: its pane is above theirs
    const order = await page.evaluate(() => {
      const z = (selector: string) => Number(getComputedStyle(document.querySelector(selector)!).zIndex)
      return { marks: z('.leaflet-station-marks-pane'), radar: z('.leaflet-radar-pane'), cells: z('.leaflet-storm-cells-pane'), cellMarks: z('.leaflet-storm-cell-marks-pane') }
    })
    expect(order.marks).toBeGreaterThan(order.radar)
    expect(order.marks).toBeGreaterThan(order.cells)
    expect(order.marks).toBeGreaterThan(order.cellMarks)
    // the marker is drawn: it has a size on the page
    const box = (await page.locator('.leaflet-station-marks-pane path').first().boundingBox())!
    expect(box.width).toBeGreaterThanOrEqual(20)
    // the loop, the player and the legend are as they were
    await expect(page.getByTestId('radar-slider')).toHaveAttribute('max', '48')
    await expect(page.getByTestId('radar-legend-class')).toHaveCount(7)
    await expect(page.locator('.station-map-radar')).toHaveCount(1)

    // the backend and the app's server were told nothing of it: no coordinate, in no address and no body
    expect(toOrigin.filter(request => /latitude|longitude|lat=|lon=|53\.5|10\.19|10\.2\b/.test(request))).toEqual([])
    expect(toOrigin.some(request => request.includes('/api/radar/frames'))).toBe(true)
    expect(page.url()).not.toMatch(/53\.5|10\.19|latitude|lat=/)
  })

  test('can be hidden and shown again, which does not move the map and is announced by the button\'s name', async ({ page, baseURL }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await open(page, baseURL!)
    await press(page).click()
    await expect(marker(page)).toHaveCount(1)
    await expect.poll(() => zoomOf(page)).toBeGreaterThanOrEqual(9)
    const zoom = await zoomOf(page)

    await page.getByRole('button', { name: en.radar.positionHide }).click()
    await expect(marker(page)).toHaveCount(0)
    await expect(page.getByTestId('use-my-location-status')).toHaveText(en.radar.positionHidden)
    await expect(page.getByRole('button', { name: en.radar.positionShow })).toBeVisible()

    await page.getByRole('button', { name: en.radar.positionShow }).click()
    await expect(marker(page)).toHaveCount(1)
    await expect(page.getByTestId('use-my-location-status')).toHaveText(en.radar.positionShown)
    expect(await zoomOf(page)).toBe(zoom)

    // a press while it is hidden shows it again
    await page.getByRole('button', { name: en.radar.positionHide }).click()
    await press(page).click()
    await expect(marker(page)).toHaveCount(1)
  })

  test('works with the keyboard alone: the button, the tick that remembers, and the control that hides the marker', async ({ page, baseURL }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await open(page, baseURL!)
    await press(page).focus()
    await page.keyboard.press('Enter')
    await expect(marker(page)).toHaveCount(1)
    // the box that remembers is the next stop, then the control that hides the marker
    await page.keyboard.press('Tab')
    await expect(page.getByRole('checkbox', { name: en.location.remember })).toBeFocused()
    await expect(page.getByTestId('use-my-location-note')).toContainText(en.location.noteRadar)
    await page.keyboard.press('Tab')
    await expect(page.getByTestId('use-my-location-privacy')).toBeFocused()
    await page.keyboard.press('Tab')
    await expect(page.getByRole('button', { name: en.radar.positionHide })).toBeFocused()
    await page.keyboard.press('Enter')
    await expect(marker(page)).toHaveCount(0)
    await expect(page.getByRole('button', { name: en.radar.positionShow })).toBeFocused()
  })

  test('is kept only with the tick, forgotten with "Forget", and shown on a later press without asking the browser again', async ({ page, baseURL }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' })
    // how often the browser is asked for a position
    await page.addInitScript(() => {
      const asks = { count: 0 }
      ;(window as unknown as { __asks: typeof asks }).__asks = asks
      const real = navigator.geolocation.getCurrentPosition.bind(navigator.geolocation)
      navigator.geolocation.getCurrentPosition = (...args) => {
        asks.count++
        return real(...args)
      }
    })
    const asked = () => page.evaluate(() => (window as unknown as { __asks: { count: number } }).__asks.count)
    await open(page, baseURL!)
    await press(page).click()
    await expect(marker(page)).toHaveCount(1)
    expect(await asked()).toBe(1)
    // not ticked: nothing is stored
    expect(await page.evaluate(() => localStorage.getItem('wd-location'))).toBeNull()
    await page.getByRole('checkbox', { name: en.location.remember }).click()
    expect(JSON.parse((await page.evaluate(() => localStorage.getItem('wd-location')))!)).toEqual({ latitude: 53.54, longitude: 10.2 })

    // a later visit: nothing is marked until a press, and the press does not ask the browser
    await page.reload()
    await expect(page.getByTestId('radar-newest')).toBeVisible()
    await expect(marker(page)).toHaveCount(0)
    await expect(page.getByRole('button', { name: en.location.storedLabel })).toBeVisible()
    await press(page).click()
    await expect(marker(page)).toHaveCount(1)
    expect(await asked()).toBe(0)

    // "Forget" takes the marker with the position, and the focus goes back to the button
    await page.getByRole('button', { name: en.location.storedLabel }).click()
    await page.getByRole('button', { name: en.location.forget }).click()
    await expect(marker(page)).toHaveCount(0)
    await expect(page.getByTestId('radar-position-toggle')).toHaveCount(0)
    await expect(press(page)).toBeFocused()
    expect(await page.evaluate(() => localStorage.getItem('wd-location'))).toBeNull()
  })

  test('outside the radar is told, and the map stays on the data: no marker, no move', async ({ page, baseURL, context }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' })
    // Madrid: far outside the box of the images
    await context.setGeolocation({ latitude: 40.4168, longitude: -3.7038 })
    await open(page, baseURL!)
    const before = await zoomOf(page)
    await press(page).click()
    await expect(page.getByTestId('use-my-location-status')).toHaveText(en.radar.positionOutside)
    await expect(marker(page)).toHaveCount(0)
    await expect(page.getByTestId('radar-position-toggle')).toHaveCount(0)
    await page.waitForTimeout(500)
    expect(await zoomOf(page)).toBe(before)
    expect(toOrigin.filter(request => /latitude|longitude|lat=|lon=|40\.4|3\.7/.test(request))).toEqual([])
  })
})

test.describe('the position on the radar, refused', () => {
  test.use({ viewport: { width: 1440, height: 900 }, permissions: [] })

  test('is told in an alert, and nothing is marked', async ({ page, baseURL }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await open(page, baseURL!)
    await page.evaluate(() => {
      navigator.permissions.query = async () => ({ state: 'denied' }) as PermissionStatus
    })
    await press(page).click()
    await expect(page.getByRole('alert').filter({ hasText: en.location.denied })).toBeVisible()
    await expect(marker(page)).toHaveCount(0)
  })
})

test.describe('the position on the radar, on a phone', () => {
  test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, geolocation: { latitude: 53.5412, longitude: 10.1987 }, permissions: ['geolocation'] })

  test('brings the map into view over the panel, and does not scroll sideways', async ({ page, baseURL }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await open(page, baseURL!)
    // the panel is under the map: scrolled to its button
    await press(page).scrollIntoViewIfNeeded()
    expect(await page.evaluate(() => window.scrollY)).toBeGreaterThan(0)
    await press(page).click()
    await expect(marker(page)).toHaveCount(1)
    await expect.poll(() => page.evaluate(() => {
      const top = document.querySelector('[data-testid="radar-stage"]')!.getBoundingClientRect().top
      return top >= -2 && top < 120
    })).toBe(true)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
    expect(await zoomOf(page)).toBeGreaterThanOrEqual(9)
  })
})
