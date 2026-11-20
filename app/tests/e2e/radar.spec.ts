import type { Page } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { expect, test } from '@playwright/test'
import { exampleScan } from '../helpers/storm-cells-answer'
import { ApiFailure, defaultHandlers, mockBackend } from './accessibility/mock-backend'
import { expectAtLeastPx } from './target-size'

// The Radar tool (GH-3788), by its main path in a browser: the radar over the map, the loop that starts by itself and is paused by its
// button, the slider by the keys, the frames loaded a few at a time, a frame that fails dropped from the loop, the thunderstorm cells on
// top with their list, the tool in the navigation and the phone. The backend is the accessibility spec's mock, which answers the list of
// the frames and an image for each, so nothing here reaches DWD, and the map's tiles are answered with a pixel.

const en = JSON.parse(readFileSync(fileURLToPath(new URL('../../i18n/locales/en.json', import.meta.url)), 'utf-8'))

async function open(page: Page, baseURL: string, handlers = {}, path = '/radar', title = en.radar.title) {
  await page.context().addCookies([{ name: 'wd_lang', value: 'en', url: baseURL }])
  const backend = await mockBackend(page, baseURL, handlers)
  await page.goto(path)
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(title)
  return backend
}

/** The time the player shows, which changes as the loop plays */
const timeOf = (page: Page) => page.getByTestId('radar-time')
/** The frames of the loop are in hand: the status of the loading is gone, and the loop has its length */
async function loaded(page: Page, frames = 49) {
  await expect(page.getByTestId('radar-slider')).toHaveAttribute('max', String(frames - 1))
  await expect(page.getByTestId('radar-newest')).toBeVisible()
  await expect(page.getByTestId('radar-frames-loading')).toHaveCount(0)
}

test.describe('the radar on a wide screen', () => {
  test.use({ viewport: { width: 1440, height: 900 } })

  test('shows the newest frame of the radar over the map, with the player, the legend and the credit', async ({ page, baseURL }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await open(page, baseURL!, {})
    await loaded(page)
    // the picture is over the map, and is the frame of its run (so that it is cacheable)
    const picture = page.locator('.station-map-radar')
    await expect(picture).toHaveCount(1)
    await expect(picture).toHaveAttribute('src', /\/api\/radar\/frame\?product=rv&time=[^&]+&run=[^&]+/)
    await expect(picture).toHaveAttribute('alt', '')
    // the player stands on the newest frame, which is observed, in words and by its icon
    await expect(page.getByTestId('radar-kind')).toHaveText(en.radar.observed)
    await expect(page.getByTestId('radar-chip')).toContainText(en.radar.observed)
    await expect(page.getByTestId('radar-slider')).toHaveValue('24')
    // the legend has the numbers, not the colours alone
    await expect(page.getByTestId('radar-legend-class')).toHaveCount(7)
    await expect(page.getByTestId('radar-legend')).toContainText('0.1–0.5')
    await expect(page.getByTestId('radar-legend')).toContainText('25+')
    // the credit and the licence, with the note of what wetterdienst did
    await expect(page.getByTestId('radar-credit')).toContainText('Source: Deutscher Wetterdienst')
    await expect(page.getByTestId('radar-credit').getByRole('link', { name: 'Creative Commons Attribution 4.0 International' })).toHaveAttribute('href', 'https://creativecommons.org/licenses/by/4.0/')
    await expect(page.getByTestId('radar-credit').getByTestId('processing-note')).toContainText('Each frame is DWD\'s RV composite')
  })

  test('starts the loop by itself, and the pause button stops it where it is', async ({ page, baseURL }) => {
    await open(page, baseURL!)
    await loaded(page)
    await expect(page.getByTestId('radar-play')).toHaveAccessibleName(en.radar.pause)
    const first = await timeOf(page).textContent()
    await expect.poll(async () => timeOf(page).textContent(), { timeout: 10_000 }).not.toBe(first)
    await page.getByTestId('radar-play').click()
    await expect(page.getByTestId('radar-play')).toHaveAccessibleName(en.radar.play)
    const paused = await timeOf(page).textContent()
    await page.waitForTimeout(1200)
    expect(await timeOf(page).textContent()).toBe(paused)
    // pressed again it goes on
    await page.getByTestId('radar-play').click()
    await expect.poll(async () => timeOf(page).textContent(), { timeout: 10_000 }).not.toBe(paused)
  })

  test('does not start by itself where the system asks for less motion, and the reader can still run it', async ({ page, baseURL }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await open(page, baseURL!)
    await loaded(page)
    const shown = await timeOf(page).textContent()
    await page.waitForTimeout(1500)
    expect(await timeOf(page).textContent()).toBe(shown)
    await expect(page.getByTestId('radar-play')).toHaveAccessibleName(en.radar.play)
    await expect(page.getByTestId('radar-reduced-motion')).toBeVisible()
    await page.getByTestId('radar-play').click()
    await expect.poll(async () => timeOf(page).textContent(), { timeout: 10_000 }).not.toBe(shown)
  })

  test('moves to a forecast frame by the keys of the slider, and marks it as forecast in words and by the dashed chip', async ({ page, baseURL }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await open(page, baseURL!)
    await loaded(page)
    const slider = page.getByTestId('radar-slider')
    await slider.focus()
    // the frame after the newest observed one is the first of the forecast: 5 minutes ahead
    await page.keyboard.press('ArrowRight')
    await expect(page.getByTestId('radar-kind')).toHaveText('Forecast, 5 min ahead')
    await expect(page.getByTestId('radar-kind')).toHaveAttribute('data-kind', 'forecast')
    await expect(page.getByTestId('radar-chip')).toHaveAttribute('data-kind', 'forecast')
    await expect(slider).toHaveAttribute('aria-valuetext', /, forecast, 5 minutes ahead$/)
    // the picture follows, and Home and End go to the ends
    await page.keyboard.press('End')
    await expect(page.getByTestId('radar-kind')).toHaveText('Forecast, 120 min ahead')
    await page.keyboard.press('Home')
    await expect(page.getByTestId('radar-kind')).toHaveText(en.radar.observed)
    await expect(slider).toHaveValue('0')
    // the steps are the way for a pointer that does not drag
    await page.getByTestId('radar-step-forward').click()
    await expect(slider).toHaveValue('1')
    await page.getByTestId('radar-step-back').click()
    await expect(slider).toHaveValue('0')
    await expect(page.getByTestId('radar-step-back')).toBeDisabled()
  })

  test('puts a different picture on the map for each frame', async ({ page, baseURL }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await open(page, baseURL!)
    await loaded(page)
    const picture = page.locator('.station-map-radar')
    const before = await picture.getAttribute('src')
    await page.getByTestId('radar-slider').focus()
    await page.keyboard.press('ArrowLeft')
    await expect.poll(async () => picture.getAttribute('src')).not.toBe(before)
    await expect(picture).toHaveAttribute('src', /time=/)
  })

  test('asks for the frames 5 at a time, never all of them at once', async ({ page, baseURL }) => {
    let inFlight = 0
    let most = 0
    let asked = 0
    const base = defaultHandlers()['radar/frame']!
    await open(page, baseURL!, {
      'radar/frame': async (url: URL, route: unknown) => {
        asked++
        inFlight++
        most = Math.max(most, inFlight)
        // a network takes a moment, so that those that are asked for together are open together
        await new Promise(resolve => setTimeout(resolve, 40))
        inFlight--
        return base(url, route as never)
      },
    })
    await loaded(page)
    expect(asked).toBeGreaterThanOrEqual(49)
    expect(most).toBeLessThanOrEqual(6)
    expect(most).toBeGreaterThan(1)
  })

  test('drops a frame that fails from the loop and says how many were skipped', async ({ page, baseURL }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' })
    const base = defaultHandlers()['radar/frame']!
    await open(page, baseURL!, {
      'radar/frame': (url: URL, route: unknown) => {
        // the third frame of the forecast is a 502 (DWD sent a file the decoder is not written for)
        const lead = Date.parse(url.searchParams.get('time')!) - Date.parse(url.searchParams.get('run')!)
        if (lead === 15 * 60_000)
          return new ApiFailure(502, 'The composite has changed')
        return base(url, route as never)
      },
    })
    await expect(page.getByTestId('radar-slider')).toHaveAttribute('max', '47', { timeout: 20_000 })
    await expect(page.getByTestId('radar-skipped')).toHaveText('Frames that could not be loaded and are skipped: 1')
    // the loop goes on: the picture is on the map
    await expect(page.locator('.station-map-radar')).toHaveCount(1)
  })

  test('says the newest run is old where the backend warns of it, and still shows the loop', async ({ page, baseURL }) => {
    const { radarAnswer } = await import('../helpers/radar-answer')
    await open(page, baseURL!, { 'radar/frames': () => radarAnswer({ warnings: [{ code: 'radar-stale', message: 'old' }] }) })
    await loaded(page)
    await expect(page.getByTestId('radar-stale')).toContainText('more than 20 minutes old')
  })

  test('says it where the radar cannot be loaded, and Retry asks again', async ({ page, baseURL }) => {
    let fail = true
    const answer = defaultHandlers()['radar/frames']!
    await open(page, baseURL!, { 'radar/frames': (url: URL, route: unknown) => fail ? new ApiFailure(502, 'DWD could not be reached') : answer(url, route as never) })
    await expect(page.getByTestId('radar-failed')).toBeVisible()
    fail = false
    await page.getByTestId('radar-retry').click()
    await loaded(page)
    await expect(page.getByTestId('radar-failed')).toHaveCount(0)
  })

  test('has the About text with its sources', async ({ page, baseURL }) => {
    await open(page, baseURL!)
    await page.getByRole('button', { name: en.radar.aboutButton }).click()
    await expect(page.getByText('The forecast is no weather model')).toBeVisible()
    await expect(page.getByTestId('radar-sources')).toContainText('WMO-No. 8')
    await expect(page.getByTestId('radar-sources').getByRole('link')).toHaveAttribute('href', 'https://www.dwd.de/DE/leistungen/radvor/radvor.html')
  })
})

test.describe('the thunderstorm cells on top of the radar', () => {
  test.use({ viewport: { width: 1440, height: 900 } })

  test('are drawn on the map and listed with where they are, and a press on a cell centres the map on it', async ({ page, baseURL }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await open(page, baseURL!, { 'storm-cells': () => exampleScan() })
    await expect(page.getByTestId('radar-cells-summary')).toHaveText('Thunderstorm cells in the latest scan: 4')
    // a mark for each cell, and an outline, none of them a stop of the keyboard
    await expect(page.locator('.storm-cell-mark')).toHaveCount(4)
    await expect(page.locator('.station-map path.leaflet-interactive')).toHaveCount(0)
    await expect(page.locator('.storm-cell-mark svg').first()).toHaveAttribute('aria-hidden', 'true')
    // the list: the most severe first, each with its position, its severity in words and its calculated motion
    const first = page.getByTestId('radar-cells-item').first()
    await expect(first).toContainText('Cell 12')
    await expect(first).toContainText('Severity 3 (extreme)')
    await expect(first).toContainText('direction calculated')
    await expect(first.getByTestId('radar-cells-location')).toHaveText('Position 51.30, 12.40')
    // the credit of the radar and the cells is one line of the map's credit, with no product codes
    await expect(page.locator('.leaflet-control-attribution')).toContainText('Source: Deutscher Wetterdienst')
    const zoomOf = () => page.evaluate(() => Math.max(...[...document.querySelectorAll<HTMLImageElement>('.station-map-tiles img.leaflet-tile')].map(tile => Number(/\/(\d+)\/\d+\/\d+\.png/.exec(tile.src)?.[1])).filter(zoom => !Number.isNaN(zoom))))
    const before = await zoomOf()
    await first.getByRole('button').click()
    await expect(page.getByTestId('radar-panel-announcement')).toHaveText('Map centred on cell 12')
    await expect.poll(zoomOf).toBeGreaterThan(before)
  })

  test('fade out on a frame of the forecast, with a note in the panel, and come back on the frame they are for; the map keeps its Leaflet classes (M1/c)', async ({ page, baseURL }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await open(page, baseURL!, { 'storm-cells': () => exampleScan() })
    await expect(page.locator('.storm-cell-mark')).toHaveCount(4)
    const mark = page.locator('.storm-cell-mark').first()
    await expect(mark).toBeVisible()
    await expect(page.getByTestId('radar-cells-faded')).toHaveCount(0)
    await page.getByTestId('radar-slider').focus()
    await page.keyboard.press('End')
    await expect(page.getByTestId('radar-cells-faded')).toBeVisible()
    await expect(page.getByTestId('radar-cells-faded')).toContainText('within 15 minutes')
    await expect(page.locator('.station-map')).toHaveClass(/leaflet-container/)
    await expect(page.locator('.station-map')).toHaveClass(/station-map-cells-faded/)
    // faded out: the panes of the cells have no opacity (Playwright counts an element of opacity 0 as visible)
    await expect(page.locator('.leaflet-storm-cell-marks-pane')).toHaveCSS('opacity', '0')
    await expect(page.locator('.leaflet-storm-cells-pane')).toHaveCSS('opacity', '0')
    // the list stays, and the credit of the cells leaves the map's (DWD's line is the radar's)
    await expect(page.getByTestId('radar-cells-item')).toHaveCount(4)
    // the newest observed frame is within 15 minutes of the scan again; the oldest of the loop is not
    await page.getByTestId('radar-slider').fill('24')
    await expect(page.getByTestId('radar-cells-faded')).toHaveCount(0)
    await expect(page.locator('.leaflet-storm-cell-marks-pane')).toHaveCSS('opacity', '1')
    await page.keyboard.press('Home')
    await expect(page.getByTestId('radar-cells-faded')).toBeVisible()
  })

  test('are off with the switch, which is a switch: nothing is drawn and the list is gone', async ({ page, baseURL }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await open(page, baseURL!, { 'storm-cells': () => exampleScan() })
    await expect(page.locator('.storm-cell-mark')).toHaveCount(4)
    const control = page.getByRole('switch', { name: en.radar.cellsSwitch })
    await expect(control).toBeChecked()
    await control.click()
    await expect(page.locator('.storm-cell-mark')).toHaveCount(0)
    await expect(page.getByTestId('radar-cells-list')).toHaveCount(0)
    await control.click()
    await expect(page.locator('.storm-cell-mark')).toHaveCount(4)
  })

  test('say so where the scan is empty, which is the usual one', async ({ page, baseURL }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await open(page, baseURL!)
    await expect(page.getByTestId('radar-cells-summary')).toHaveText('No thunderstorm cells in the latest scan')
    await expect(page.locator('.storm-cell-mark')).toHaveCount(0)
  })
})

test.describe('the Radar in the navigation', () => {
  test.describe('on a wide screen', () => {
    test.use({ viewport: { width: 1440, height: 900 } })

    test('is a tab of the header, the fourth of six tools, and marked while one is on its page', async ({ page, baseURL }) => {
      await page.emulateMedia({ reducedMotion: 'reduce' })
      await open(page, baseURL!)
      const nav = page.getByRole('navigation', { name: en.shell.mainNav })
      await expect(nav.getByRole('link', { name: en.nav.radar })).toHaveAttribute('aria-current', 'page')
      await expect(nav.locator('a.nav-tab')).toHaveCount(6)
    })

    test('is found from the home page, which has a tile for it', async ({ page, baseURL }) => {
      await open(page, baseURL!, {}, '/', 'Wetterdienst')
      await page.locator('.home-tasks a[href="/radar"]').click()
      await expect(page).toHaveURL(/\/radar$/)
    })
  })

  test.describe('on a phone', () => {
    test.use({ viewport: { width: 390, height: 844 }, hasTouch: true })

    test('has the Radar in the default bar, in History\'s place, and History and the Map in the Menu\'s sheet; the Radar\'s tab is marked on its page and the Menu is not', async ({ page, baseURL }) => {
      await page.emulateMedia({ reducedMotion: 'reduce' })
      await open(page, baseURL!)
      const bar = page.getByRole('navigation').last()
      await expect(bar.getByRole('link', { name: en.nav.radar })).toHaveAttribute('aria-current', 'page')
      await expect(bar.getByRole('link', { name: en.nav.history })).toHaveCount(0)
      await expect(page.getByRole('button', { name: en.header.menu })).not.toHaveAttribute('aria-current', 'true')
      await page.getByRole('button', { name: en.header.menu }).click()
      const sheet = page.getByRole('dialog')
      await expect(sheet.getByRole('link', { name: new RegExp(`^${en.nav.history}`) })).toBeVisible()
      await expect(sheet.getByRole('link', { name: new RegExp(`^${en.nav.map}`) })).toBeVisible()
    })

    test('does not scroll sideways at 390 px, has its player in the window under the map with buttons of 44 px, and the panel after it', async ({ page, baseURL }) => {
      await page.emulateMedia({ reducedMotion: 'reduce' })
      await open(page, baseURL!)
      await loaded(page)
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
      for (const id of ['radar-play', 'radar-step-back', 'radar-step-forward']) {
        const box = (await page.getByTestId(id).boundingBox())!
        expectAtLeastPx(box.width, 44, id)
        expectAtLeastPx(box.height, 44, id)
      }
      // the slider's thumb is as large as a target, 24 px and more
      expectAtLeastPx((await page.getByTestId('radar-slider').boundingBox())!.height, 24, 'the slider')
      // the order on the page is the one of the window: the map, the player, the legend, then the panel
      const top = async (id: string) => (await page.getByTestId(id).boundingBox())!.y
      expect(await top('radar-stage')).toBeLessThan(await top('radar-panel'))
      expect(await top('radar-player')).toBeLessThan(await top('radar-legend'))
      expect(await top('radar-legend')).toBeLessThan(await top('radar-panel'))
    })

    test('does not scroll sideways at 320 px in any language, with the player and the legend whole', async ({ page, baseURL }) => {
      await page.setViewportSize({ width: 320, height: 700 })
      await page.emulateMedia({ reducedMotion: 'reduce' })
      for (const language of ['de', 'fr', 'pl', 'cs', 'lb', 'de-hh', 'nl', 'da', 'es', 'it']) {
        await page.context().addCookies([{ name: 'wd_lang', value: language, url: baseURL! }])
        await mockBackend(page, baseURL!, {})
        await page.goto('/radar')
        await expect(page.getByTestId('radar-newest')).toBeVisible()
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), language).toBe(true)
        const overflowing = await page.evaluate(() => [...document.querySelectorAll('[data-testid="radar-player"] *, [data-testid="radar-legend"] *')]
          .filter(element => element.getBoundingClientRect().right > window.innerWidth + 1)
          .length)
        expect(overflowing, language).toBe(0)
        await page.unrouteAll({ behavior: 'ignoreErrors' })
      }
    })
  })
})
