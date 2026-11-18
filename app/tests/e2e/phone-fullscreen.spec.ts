import type { Page } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { expect, test } from '@playwright/test'
import { mockBackend } from './accessibility/mock-backend'
import { expectAtLeastPx } from './target-size'

// The narrow layout of the app and the map's full screen (GH-4227), in Chromium: the content runs edge to edge where the
// tab bar stands, the map fills the window between the bars, the "About" of a tool is an ⓘ beside its title, and the map has a
// full-screen button (the browser's API where it has one, the app covering the page where it has not). The backend is
// the accessibility spec's mock; the tiles are a placeholder.

const en = JSON.parse(readFileSync(fileURLToPath(new URL('../../i18n/locales/en.json', import.meta.url)), 'utf-8'))

async function open(page: Page, baseURL: string, path: string, size: { width: number, height: number }, title = en.mapTool.title) {
  await page.setViewportSize(size)
  await page.context().addCookies([{ name: 'wd_lang', value: 'en', url: baseURL }])
  const backend = await mockBackend(page, baseURL)
  await page.goto(path)
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(title)
  await expect(page.getByTestId('map-fullscreen')).toBeAttached()
  await expect(page.getByTestId('map-screen').locator('.leaflet-container')).toBeVisible()
  return backend
}

const noHorizontalScroll = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1)

/** A browser with no Fullscreen API for an element, as iPhone Safari: the app's own full screen */
async function withoutFullscreenApi(page: Page) {
  await page.addInitScript(() => {
    Object.defineProperty(document, 'fullscreenEnabled', { value: false, configurable: true })
    Object.defineProperty(document, 'webkitFullscreenEnabled', { value: false, configurable: true })
  })
}

/** The zoom the map is at, from the tiles it asks for */
async function zoomOf(page: Page) {
  return page.evaluate(() => {
    const zooms = [...document.querySelectorAll<HTMLImageElement>('.station-map-tiles img.leaflet-tile')]
      .map(tile => Number(/\/(\d+)\/\d+\/\d+\.png/.exec(tile.src)?.[1]))
      .filter(zoom => !Number.isNaN(zoom))
    return zooms.length ? Math.max(...zooms) : null
  })
}

for (const width of [390, 320]) {
  test.describe(`the map on a phone, ${width} px wide`, () => {
    test(`fills the window between the bars, edge to edge, with its panel as wide as the window`, async ({ page, baseURL }) => {
      await open(page, baseURL!, '/map?station=10384', { width, height: 800 })
      const stage = (await page.getByTestId('map-stage').boundingBox())!
      const tabbar = (await page.locator('.app-tabbar').boundingBox())!
      const panel = (await page.getByTestId('map-panel').boundingBox())!
      // the map runs from edge to edge and down to the tab bar (the page is at its top)
      expect(stage.x).toBeCloseTo(0, 0)
      expect(stage.width).toBeCloseTo(width, 0)
      expect(stage.y + stage.height).toBeCloseTo(tabbar.y, 0)
      expect(stage.height).toBeGreaterThan(400)
      // the sheet under it is as wide as the window too, and none of its cards is inside a margin
      expect(panel.x).toBeCloseTo(0, 0)
      expect(panel.width).toBeCloseTo(width, 0)
      const card = (await page.getByTestId('map-card-forecast').boundingBox())!
      expect(card.x).toBeCloseTo(0, 0)
      expect(card.width).toBeCloseTo(width, 0)
      expect(await page.locator('.station-map').evaluate(element => getComputedStyle(element).borderTopLeftRadius)).toBe('0px')
      expect(await noHorizontalScroll(page)).toBe(true)
    })

    test('has the full-screen button with the zoom buttons, in the window, at 40 px, and clear of the layers button', async ({ page, baseURL }) => {
      await open(page, baseURL!, '/map', { width, height: 800 })
      const button = page.getByTestId('map-fullscreen')
      await expect(button).toHaveAccessibleName(en.mapTool.fullscreenEnter)
      await expect(button).toHaveAttribute('aria-pressed', 'false')
      const box = (await button.boundingBox())!
      const zoomIn = (await page.locator('.leaflet-control-zoom-in').boundingBox())!
      expectAtLeastPx(box.width, 40)
      expectAtLeastPx(box.height, 40)
      expect(box.x + box.width).toBeLessThanOrEqual(width)
      // in the same bar as the zoom buttons: right above them, in the same column
      expect(box.x).toBeCloseTo(zoomIn.x, 0)
      expect(box.y + box.height).toBeLessThanOrEqual(zoomIn.y + 1)
      const layers = (await page.getByTestId('map-layers-button').boundingBox())!
      expect(box.y).toBeGreaterThan(layers.y + layers.height)
    })
  })
}

test.describe('the map on a phone on its side', () => {
  test('stays in the window (the bars scroll away) and goes full screen with its sheet in view', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/map?station=10384', { width: 844, height: 390 })
    const stage = (await page.getByTestId('map-stage').boundingBox())!
    expect(stage.width).toBeCloseTo(844, 0)
    expect(stage.height).toBeLessThanOrEqual(390)
    expect(await noHorizontalScroll(page)).toBe(true)
    await page.getByTestId('map-fullscreen').click()
    const screen = (await page.getByTestId('map-screen').boundingBox())!
    expect(screen).toMatchObject({ x: 0, y: 0 })
    expect(screen.width).toBeCloseTo(844, 0)
    expect(screen.height).toBeCloseTo(390, 0)
    // the map keeps room above the sheet, the sheet is in the window
    const map = (await page.locator('.station-map').boundingBox())!
    const sheet = (await page.getByTestId('map-sheet').boundingBox())!
    expect(map.height).toBeGreaterThan(200)
    expect(sheet.y + sheet.height).toBeLessThanOrEqual(390 + 1)
    await expect(page.getByTestId('map-fullscreen')).toBeInViewport()
  })
})

test.describe('the full screen of the map, by the browser', () => {
  test('is entered and left by the button and by Escape, with the focus in the map and then back on the button', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/map', { width: 390, height: 800 })
    const button = page.getByTestId('map-fullscreen')
    await button.click()
    await expect.poll(() => page.evaluate(() => document.fullscreenElement?.getAttribute('data-testid'))).toBe('map-screen')
    // the label says what pressing does, and the button is pressed
    await expect(button).toHaveAccessibleName(en.mapTool.fullscreenExit)
    await expect(button).toHaveAttribute('aria-pressed', 'true')
    // the focus is in the map, which a key then pans
    await expect.poll(() => page.evaluate(() => document.activeElement?.classList.contains('station-map'))).toBe(true)
    // the map has the whole screen above the sheet: Leaflet was told
    const canvas = (await page.locator('.map-canvas').boundingBox())!
    const leaflet = (await page.locator('.leaflet-container').boundingBox())!
    expect(leaflet.width).toBeCloseTo(canvas.width, 0)
    expect(leaflet.height).toBeCloseTo(canvas.height, 0)
    expect(await page.locator('.leaflet-tile-container img').first().isVisible()).toBe(true)

    await page.keyboard.press('Escape')
    await expect.poll(() => page.evaluate(() => document.fullscreenElement === null)).toBe(true)
    await expect(button).toHaveAccessibleName(en.mapTool.fullscreenEnter)
    await expect(button).toHaveAttribute('aria-pressed', 'false')
    await expect(button).toBeFocused()
    // and by the button
    await button.click()
    await expect.poll(() => page.evaluate(() => document.fullscreenElement !== null)).toBe(true)
    await button.click()
    await expect.poll(() => page.evaluate(() => document.fullscreenElement === null)).toBe(true)
    await expect(button).toBeFocused()
    const after = (await page.locator('.leaflet-container').boundingBox())!
    expect(after.width).toBeCloseTo(390, 0)
  })

  test('keeps the view, the layer and the station picked through entering and leaving', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/map?station=10384', { width: 390, height: 800 })
    await expect.poll(() => zoomOf(page)).toBe(8)
    // the layer chosen: the measuring stations
    await page.getByTestId('map-layers-button').click()
    await page.getByTestId('map-layers-panel').getByRole('radio', { name: en.mapTool.layerMeasured, exact: true }).check()
    await page.keyboard.press('Escape')
    await expect(page.getByTestId('map-layers-panel')).toBeHidden()
    // and a zoom
    await page.locator('.leaflet-control-zoom-in').click()
    await expect.poll(() => zoomOf(page)).toBe(9)
    const url = page.url()
    const mapBefore = await page.locator('.leaflet-container').elementHandle()

    await page.getByTestId('map-fullscreen').click()
    await expect.poll(() => page.evaluate(() => document.fullscreenElement !== null)).toBe(true)
    // the sheet names the station, and it is the same map (not a new one)
    await expect(page.getByTestId('map-sheet-name')).toBeVisible()
    expect(await mapBefore!.evaluate(element => element.isConnected)).toBe(true)
    await expect.poll(() => zoomOf(page)).toBe(9)
    await page.keyboard.press('Escape')
    await expect.poll(() => page.evaluate(() => document.fullscreenElement === null)).toBe(true)

    await expect.poll(() => zoomOf(page)).toBe(9)
    expect(page.url()).toBe(url)
    await page.getByTestId('map-layers-button').click()
    await expect(page.getByTestId('map-layers-panel').getByRole('radio', { name: en.mapTool.layerMeasured, exact: true })).toBeChecked()
  })

  test('is on a wide screen too, where the panel is beside the map and stays as it was', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/map', { width: 1440, height: 900 })
    const panelBefore = (await page.getByTestId('map-panel').boundingBox())!
    const stageBefore = (await page.getByTestId('map-stage').boundingBox())!
    await page.getByTestId('map-fullscreen').click()
    await expect.poll(() => page.evaluate(() => document.fullscreenElement !== null)).toBe(true)
    await page.keyboard.press('Escape')
    await expect.poll(() => page.evaluate(() => document.fullscreenElement === null)).toBe(true)
    // the same sizes and columns (the window has been scrolled by the press on the button: the page is as tall as it was)
    const [panelAfter, stageAfter] = [(await page.getByTestId('map-panel').boundingBox())!, (await page.getByTestId('map-stage').boundingBox())!]
    expect([panelAfter.x, panelAfter.width, panelAfter.height]).toEqual([panelBefore.x, panelBefore.width, panelBefore.height])
    expect([stageAfter.x, stageAfter.width, stageAfter.height]).toEqual([stageBefore.x, stageBefore.width, stageBefore.height])
    // the page has not changed on a wide screen: the panel is beside the map
    expect(panelBefore.x + panelBefore.width).toBeLessThanOrEqual(stageBefore.x)
  })

  test('falls back to the app\'s own full screen where the browser refuses the request', async ({ page, baseURL }) => {
    await page.addInitScript(() => {
      Element.prototype.requestFullscreen = () => Promise.reject(new TypeError('Permissions check failed'))
    })
    await open(page, baseURL!, '/map', { width: 390, height: 800 })
    await page.getByTestId('map-fullscreen').click()
    await expect(page.getByTestId('map-screen')).toHaveAttribute('data-fullscreen', 'app')
    await expect(page.getByTestId('map-fullscreen')).toHaveAttribute('aria-pressed', 'true')
  })
})

test.describe('the full screen of the map, by the app (a browser with no Fullscreen API for an element)', () => {
  test.beforeEach(async ({ page }) => {
    await withoutFullscreenApi(page)
  })

  test('covers the app\'s bars, makes the page behind it inert, and keeps the focus in the map', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/map?station=10384', { width: 390, height: 800 })
    const button = page.getByTestId('map-fullscreen')
    await button.click()
    const screen = page.getByTestId('map-screen')
    await expect(screen).toHaveAttribute('data-fullscreen', 'app')
    expect(await page.evaluate(() => document.fullscreenElement)).toBeNull()
    // fixed, over the whole window and over the header and the tab bar
    expect(await screen.evaluate(element => getComputedStyle(element).position)).toBe('fixed')
    expect(await screen.boundingBox()).toMatchObject({ x: 0, y: 0, width: 390, height: 800 })
    for (const [x, y] of [[20, 20], [195, 780]]) {
      expect(await page.evaluate(([px, py]) => !!document.elementFromPoint(px!, py!)?.closest('.map-screen'), [x, y])).toBe(true)
    }
    // the page under it is inert: the header, the tab bar, the panel and the footer are out of reach
    for (const selector of ['.app-header', '.app-tabbar', '[data-testid=map-panel]', '.app-footer']) {
      expect(await page.locator(selector).first().evaluate(element => !!element.closest('[inert]')), selector).toBe(true)
    }
    expect(await page.evaluate(() => getComputedStyle(document.documentElement).overflow)).toBe('hidden')
    // the focus is in the map, and Tab goes through the screen's controls and out of the document, never to the page behind it
    await expect.poll(() => page.evaluate(() => document.activeElement?.classList.contains('station-map'))).toBe(true)
    for (let i = 0; i < 12; i++) {
      await page.keyboard.press('Tab')
      expect(await page.evaluate(() => document.activeElement === document.body || !!document.activeElement?.closest('.map-screen')), `tab ${i}`).toBe(true)
    }
    await page.getByTestId('map-fullscreen').focus()
    // the map is told its size
    const canvas = (await page.locator('.map-canvas').boundingBox())!
    const leaflet = (await page.locator('.leaflet-container').boundingBox())!
    expect(leaflet.height).toBeCloseTo(canvas.height, 0)

    // Escape leaves, the page is whole again and the focus is on the button
    await page.keyboard.press('Escape')
    await expect(screen).toHaveAttribute('data-fullscreen', 'off')
    await expect(button).toBeFocused()
    await expect(button).toHaveAccessibleName(en.mapTool.fullscreenEnter)
    expect(await page.locator('[inert]').count()).toBe(0)
    expect(await page.evaluate(() => getComputedStyle(document.documentElement).overflow)).toBe('visible')
    expect(await screen.evaluate(element => getComputedStyle(element).position)).toBe('relative')
  })

  test('closes the layers panel with Escape first, and leaves with the next', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/map', { width: 390, height: 800 })
    await page.getByTestId('map-fullscreen').click()
    await page.getByTestId('map-layers-button').click()
    await expect(page.getByTestId('map-layers-panel')).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(page.getByTestId('map-layers-panel')).toBeHidden()
    await expect(page.getByTestId('map-screen')).toHaveAttribute('data-fullscreen', 'app')
    await page.keyboard.press('Escape')
    await expect(page.getByTestId('map-screen')).toHaveAttribute('data-fullscreen', 'off')
  })

  test('has a sheet for the station: its name, the centre of the map as a place, and the way back to the details', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/map', { width: 390, height: 800 })
    await page.getByTestId('map-fullscreen').click()
    const sheet = page.getByTestId('map-sheet')
    await expect(sheet).toBeVisible()
    await expect(sheet).toContainText('Stations shown')
    await expect(page.getByTestId('map-sheet-details')).toHaveCount(0)
    // the keyboard's way to a place: the middle of the map; a map with no station near says so
    await page.getByTestId('map-sheet-pick-centre').click()
    await expect(sheet).toContainText('No station within 100 km')
    await expect(page.getByTestId('map-sheet-pick-centre')).toBeFocused()

    // a station picked by the address
    await page.getByTestId('map-fullscreen').click()
    await page.goto('/map?station=10384')
    await expect(page.getByTestId('map-fullscreen')).toBeAttached()
    await page.getByTestId('map-fullscreen').click()
    await expect(page.getByTestId('map-sheet-name')).toHaveText('BERLIN-TEMPELHOF')
    // "Show details" leaves the full screen and puts the focus on the panel's heading, which is in view
    await page.getByTestId('map-sheet-details').click()
    await expect(page.getByTestId('map-screen')).toHaveAttribute('data-fullscreen', 'off')
    await expect(page.getByTestId('map-station-name')).toBeFocused()
    await expect(page.getByTestId('map-station-name')).toBeInViewport()
  })

  test('a click on the button is no pick of a place on the map', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/map', { width: 390, height: 800 })
    await page.getByTestId('map-fullscreen').click()
    await expect(page.getByTestId('map-sheet')).not.toContainText('No station within')
  })
})

test.describe('the "About" of a tool on a phone', () => {
  for (const [path, title] of [['/explorer', en.explorer.title], ['/meteogram', en.meteogram.title], ['/history', en.history.title], ['/stripes', en.stripes.title]] as const) {
    test(`${path}: is an ⓘ beside the title, which opens the text, and Escape closes it and returns the focus`, async ({ page, baseURL }) => {
      await page.setViewportSize({ width: 390, height: 844 })
      await page.context().addCookies([{ name: 'wd_lang', value: 'en', url: baseURL! }])
      await mockBackend(page, baseURL!)
      await page.goto(path)
      await expect(page.getByRole('heading', { level: 1 })).toHaveText(title)
      const info = page.getByTestId('page-info')
      await expect(info).toBeVisible()
      await expect(info).toHaveAttribute('aria-expanded', 'false')
      const controls = await info.getAttribute('aria-controls')
      expect(controls).toBeTruthy()
      // no labelled button in the row of actions
      await expect(page.locator('.page-header').getByRole('button', { name: /^About/ })).toHaveCount(1)
      const box = (await info.boundingBox())!
      const h1 = (await page.locator('.page-title').boundingBox())!
      expectAtLeastPx(box.width, 44)
      expectAtLeastPx(box.height, 44)
      // beside the title, at its end, on the line of its first row
      expect(box.x).toBeGreaterThanOrEqual(h1.x + 1)
      expect(box.y).toBeLessThan(h1.y + h1.height)
      await expect(page.locator(`#${controls}`)).toBeHidden()

      await info.click()
      await expect(info).toHaveAttribute('aria-expanded', 'true')
      const panel = page.locator(`#${controls}`)
      await expect(panel).toBeVisible()
      // edge to edge
      expect(await panel.boundingBox()).toMatchObject({ x: 0, width: 390 })
      expect(await noHorizontalScroll(page)).toBe(true)
      await page.keyboard.press('Escape')
      await expect(info).toHaveAttribute('aria-expanded', 'false')
      await expect(panel).toBeHidden()
      await expect(info).toBeFocused()
    })
  }

  test('Escape closes it from inside its text too, and the focus is on the ⓘ', async ({ page, baseURL }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await mockBackend(page, baseURL!)
    await page.goto('/explorer')
    const info = page.getByTestId('page-info')
    await info.click()
    await page.locator('.page-about').evaluate((element) => {
      element.setAttribute('tabindex', '-1')
      element.focus()
    })
    await page.keyboard.press('Escape')
    await expect(info).toBeFocused()
  })

  test('is the labelled button of the row of actions from 64 rem, as it was', async ({ page, baseURL }) => {
    await page.setViewportSize({ width: 1280, height: 900 })
    await mockBackend(page, baseURL!)
    await page.goto('/explorer')
    await expect(page.getByTestId('page-info')).toHaveCount(0)
    const button = page.locator('.page-header').getByRole('button', { name: en.explorer.aboutButton })
    await expect(button).toBeVisible()
    await button.click()
    await expect(page.locator('.page-about')).toBeVisible()
  })
})

test.describe('cards on a phone', () => {
  test('run edge to edge, and are cards again from 64 rem', async ({ page, baseURL }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await mockBackend(page, baseURL!)
    await page.goto('/meteogram')
    const card = page.locator('[data-slot="root"].card-bleed').first()
    await expect(card).toBeVisible()
    expect(await card.boundingBox()).toMatchObject({ x: 0, width: 390 })
    expect(await card.evaluate(element => getComputedStyle(element).borderTopLeftRadius)).toBe('0px')
    expect(await noHorizontalScroll(page)).toBe(true)
    await page.setViewportSize({ width: 1280, height: 900 })
    const wide = (await card.boundingBox())!
    expect(wide.x).toBeGreaterThan(8)
    expect(await card.evaluate(element => getComputedStyle(element).borderTopLeftRadius)).not.toBe('0px')
  })
})
