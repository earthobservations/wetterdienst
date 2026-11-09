import type { Page } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { expect, test } from '@playwright/test'
import { ApiFailure, mockBackend } from './accessibility/mock-backend'

// The map tool (GH-3650), by its main path in a browser: open the map, pick a place, read what the panel shows of it
// and follow its links; the layers; the search of the header opening the map on a station; and the phone's navigation
// with the map in the Menu. The backend is the accessibility spec's mock, so nothing here reaches a provider, and
// the map's tiles are answered with a pixel.

const en = JSON.parse(readFileSync(fileURLToPath(new URL('../../i18n/locales/en.json', import.meta.url)), 'utf-8'))

/** The one station with climate stripes that these tests have within reach of Berlin */
const STRIPES_NEAR = {
  'stripes/stations': () => ({
    stations: [{ station_id: '00131', name: 'Angermünde', region: 'Brandenburg', latitude: 53.0301, longitude: 13.9951, start_timestamp: '1950-01-01T00:00:00+00:00', end_timestamp: `${new Date().getUTCFullYear() - 1}-12-31T00:00:00+00:00` }],
  }),
}

async function open(page: Page, baseURL: string, path = '/map', handlers = {}, title = en.mapTool.title) {
  await page.context().addCookies([{ name: 'wd_lang', value: 'en', url: baseURL }])
  const backend = await mockBackend(page, baseURL, handlers)
  await page.goto(path)
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(title)
  return backend
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

/**
 * Where a position is on the map at its opening view (the centre of Germany at zoom 6), in pixels from the middle of
 * the map: Web Mercator, 256 px tiles
 */
function offsetAtOpening(latitude: number, longitude: number) {
  const scale = 256 * 2 ** 6
  const mercator = (degrees: number) => Math.log(Math.tan(Math.PI / 4 + degrees * Math.PI / 360))
  return {
    x: (longitude - 10.4) * scale / 360,
    y: -(mercator(latitude) - mercator(51.2)) * scale / (2 * Math.PI),
  }
}

/** The middle of the map: at its opening view no station of the mock is within 100 km of it */
async function clickMapCentre(page: Page) {
  const map = page.getByRole('application', { name: /^Station map/ })
  await expect(map).toBeVisible()
  await expect(page.getByTestId('map-count')).toBeVisible()
  // the dots are drawn on canvas tiles, which come after the count
  await expect(map.locator('canvas').first()).toBeAttached()
  const box = (await map.boundingBox())!
  await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2)
}

test.describe('the map tool on a wide screen', () => {
  test.use({ viewport: { width: 1440, height: 900 } })

  test('is the fifth tool of the header, with its violet tile, and marks itself as the page one is on', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/map')
    const nav = page.getByRole('navigation', { name: en.shell.mainNav })
    const links = nav.getByRole('link')
    await expect(links.filter({ hasText: en.nav.map })).toHaveAttribute('aria-current', 'page')
    expect(await nav.locator('ul > li').allInnerTexts()).toEqual([en.nav.meteogram, en.nav.explorer, en.nav.stripes, en.nav.history, en.nav.map])
    await expect(page.locator('.page-header .tile-map')).toBeVisible()
  })

  test('shows the forecast stations, the panel beside the map and the chips over it', async ({ page, baseURL }) => {
    const backend = await open(page, baseURL!)
    await expect(page.getByTestId('map-count')).toHaveText('Stations shown: 4')
    const panel = page.getByTestId('map-panel')
    const stage = page.getByTestId('map-stage')
    const [panelBox, stageBox] = [await panel.boundingBox(), await stage.boundingBox()]
    // the panel is on the left of the map, the two side by side
    expect(panelBox!.x + panelBox!.width).toBeLessThanOrEqual(stageBox!.x)
    expect(Math.abs(panelBox!.y - stageBox!.y)).toBeLessThan(2)
    await expect(page.getByRole('button', { name: en.mapTool.layerForecast })).toHaveAttribute('aria-pressed', 'true')
    await expect(page.getByRole('button', { name: en.mapTool.layerMeasured })).toHaveAttribute('aria-pressed', 'false')
    // the stations near the centre, by name
    await expect(panel.getByRole('button', { name: /BERLIN-TEMPELHOF/ })).toBeVisible()
    expect(backend.unanswered).toEqual([])
  })

  test('picks a place by a click on the map, shows what there is at it, and leads into the explorer and the history, filled in', async ({ page, baseURL }) => {
    const backend = await open(page, baseURL!, '/map?station=10384', STRIPES_NEAR)
    // the map has moved to Berlin-Tempelhof (zoom 8): back to the list, then a click some way beside its dot
    await expect.poll(() => zoomOf(page)).toBe(8)
    await page.getByTestId('map-back').click()
    const box = (await page.getByRole('application', { name: /^Station map/ }).boundingBox())!
    await page.mouse.click(box.x + box.width / 2 + 40, box.y + box.height / 2 + 25)
    const panel = page.getByTestId('map-panel')
    await expect(panel.getByRole('heading', { level: 2 })).toHaveText('BERLIN-TEMPELHOF')
    await expect(page.getByTestId('map-place')).toContainText('from this station')
    await expect(page).toHaveURL(/\/map\?station=10384&lat=/)

    // the forecast, as day rows, of the station the place is nearest to, which the card says is some way from the place
    const forecast = page.getByTestId('map-card-forecast')
    await expect(forecast.getByTestId('day-rows').getByRole('listitem').first()).toBeVisible()
    await expect(forecast).toContainText(/BERLIN-TEMPELHOF, \d+ km away/)
    await expect(forecast.getByRole('link', { name: en.mapTool.openForecast })).toHaveAttribute('href', '/meteogram?station=10384')

    // the stripes are at the nearest station that has them, which the card names with its distance
    const stripes = page.getByTestId('map-card-stripes')
    await expect(stripes).toContainText(/Angermünde, \d+ km away/)
    await expect(stripes.getByRole('link', { name: en.mapTool.openStripes })).toHaveAttribute('href', '/stripes?kind=temperature&station=00131')
    // the measurements are at the nearest station that still reports within 100 km (the mock's has no end), not at
    // Artern, which stopped in 2018 and is farther
    const measured = page.getByTestId('map-card-measured')
    await expect(measured).toContainText(/Angermünde, \d+ km away/)
    await expect(measured).toContainText('since 1991')
    const explorer = measured.getByRole('link', { name: en.mapTool.openExplorer })
    await expect(explorer).toHaveAttribute('href', /stations=00131/)
    await expect(measured.getByRole('link', { name: en.mapTool.openHistory })).toHaveAttribute('href', /stations=00131/)

    // the explorer opens with the station chosen
    await explorer.click()
    await expect(page).toHaveURL(/\/explorer\?.*stations=00131/)
    await expect(page.getByText('Angermünde').first()).toBeVisible()
    expect(backend.unanswered).toEqual([])
  })

  test('picks no station for a click with none within 100 km, and says so', async ({ page, baseURL }) => {
    await open(page, baseURL!)
    await clickMapCentre(page)
    await expect(page.getByTestId('map-none-near')).toHaveText('No station within 100 km of that point.')
    await expect(page.getByTestId('map-station-name')).toHaveCount(0)
    await expect(page).toHaveURL(/\/map$/)
  })

  test('shows the climate stripes of a station that has them', async ({ page, baseURL }) => {
    // Donaueschingen measures and has stripes: the layer of the measurements shows its own station
    await open(page, baseURL!, '/map?layer=measured&station=00011')
    const stripes = page.getByTestId('map-card-stripes')
    await expect(stripes.getByRole('img', { name: /^Climate stripes of Donaueschingen/ })).toBeVisible()
    await expect(stripes.getByRole('link', { name: en.mapTool.openStripes })).toHaveAttribute('href', '/stripes?kind=temperature&station=00011')
    await expect(stripes.locator('figcaption')).toContainText('From 1955 to 2024.')
  })

  test('shows the measuring stations of a resolution and a dataset when the chip is pressed', async ({ page, baseURL }) => {
    await open(page, baseURL!)
    await page.getByRole('button', { name: en.mapTool.layerMeasured }).click()
    await expect(page.getByRole('button', { name: en.mapTool.layerMeasured })).toHaveAttribute('aria-pressed', 'true')
    await expect(page.getByTestId('map-count')).toHaveText('Stations shown: 12')
    await expect(page).toHaveURL(/\/map\?layer=measured$/)
    await expect(page.getByTestId('map-resolution')).toBeVisible()
    await expect(page.getByTestId('map-dataset')).toBeVisible()
    await expect(page.getByTestId('map-panel').getByRole('button', { name: /Neuhaus am Rennweg|Aue|Arkona/ }).first()).toBeVisible()
  })

  test('tells a failing station list in the page and loads it again on Retry', async ({ page, baseURL }) => {
    let failing = true
    await open(page, baseURL!, '/map', {
      stations: (url: URL) => {
        if (failing && url.searchParams.get('network') === 'mosmix')
          return new ApiFailure(500, 'The forecast stations are not available')
        return { stations: [{ station_id: '10384', name: 'BERLIN-TEMPELHOF', region: null, latitude: 52.47, longitude: 13.4, elevation: 49 }] }
      },
    })
    const failure = page.getByTestId('map-failure')
    await expect(failure).toContainText(en.mapTool.stationsFailed)
    await expect(failure).toContainText('The forecast stations are not available')
    failing = false
    await failure.getByRole('button', { name: en.common.retry }).click()
    await expect(page.getByTestId('map-count')).toHaveText('Stations shown: 1')
    await expect(failure).toHaveCount(0)
  })

  test('is opened on a station by the header\'s search (Ctrl+K), which lists the map among the tools', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/', {}, 'Wetterdienst')
    await page.keyboard.press('Control+K')
    const dialog = page.getByRole('dialog')
    const input = dialog.getByRole('combobox')
    await expect(dialog.getByRole('option', { name: new RegExp(`^${en.nav.map}`) })).toBeVisible()
    await input.fill('hamburg')
    const option = dialog.getByRole('option', { name: /Show station 10147 on the map/ })
    await expect(option).toBeVisible()
    await option.click()
    await expect(page).toHaveURL(/\/map\?station=10147/)
    await expect(page.getByTestId('map-panel').getByRole('heading', { level: 2 })).toHaveText('HAMBURG-FUHLSBUETTEL')
    await expect(page.getByTestId('map-announcement')).toHaveText('HAMBURG-FUHLSBUETTEL chosen')
  })

  test('is used by the keyboard alone: the list, the focus on the station, Back, and the centre of the map', async ({ page, baseURL }) => {
    await open(page, baseURL!)
    const panel = page.getByTestId('map-panel')
    const item = panel.getByRole('button', { name: /MUENCHEN-STADT/ })
    await item.focus()
    await page.keyboard.press('Enter')
    const heading = panel.getByRole('heading', { level: 2 })
    await expect(heading).toHaveText('MUENCHEN-STADT')
    await expect(heading).toBeFocused()
    await page.getByTestId('map-back').focus()
    await page.keyboard.press('Enter')
    await expect(panel.getByRole('button', { name: /MUENCHEN-STADT/ })).toBeFocused()
  })

  test('is used by the keyboard alone: the arrow keys move the map and the panel picks the place at its centre', async ({ page, baseURL }) => {
    // opened on Munich, the map is at zoom 8 with it at the middle; back to the list, as a reader of the keys would
    await open(page, baseURL!, '/map?station=10865')
    await expect.poll(() => zoomOf(page)).toBe(8)
    const panel = page.getByTestId('map-panel')
    await page.getByTestId('map-back').click()
    const map = page.getByRole('application', { name: /^Station map/ })
    await map.focus()
    for (let press = 0; press < 3; press++)
      await page.keyboard.press('ArrowRight')
    // the map pans with an animation, and tells the page where it is when that has ended
    await page.waitForTimeout(800)
    await panel.getByTestId('map-pick-centre').focus()
    await page.keyboard.press('Enter')
    // the place at the centre, now beside Munich, is picked, and the focus goes to the name of the station nearest to it
    const heading = panel.getByRole('heading', { level: 2 })
    await expect(heading).toHaveText('MUENCHEN-STADT')
    await expect(heading).toBeFocused()
    await expect(page.getByTestId('map-place')).toBeVisible()
    await expect(page).toHaveURL(/lat=/)
  })
})

test.describe('the map tool: what a pick moves, and what a click reaches', () => {
  test.use({ viewport: { width: 1440, height: 900 } })

  test('opens at the zoom of the country, and moves to the station of the address, once, at the zoom of a town', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/map')
    await expect(page.getByTestId('map-count')).toBeVisible()
    await expect.poll(() => zoomOf(page)).toBe(6)
    await open(page, baseURL!, '/map?station=10865')
    // the map has moved to Munich: zoom 8 at the least, and its dot is at the middle of the map, where a click on it is that station
    await expect.poll(() => zoomOf(page)).toBe(8)
    const map = page.getByRole('application', { name: /^Station map/ })
    const box = (await map.boundingBox())!
    await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2)
    await expect(page.getByTestId('map-station-name')).toHaveText('MUENCHEN-STADT')
    // a click on the dot is the station itself, with no place apart: the click tolerance is a dot's width, not a distance
    await expect(page.getByTestId('map-place')).toHaveCount(0)
    await expect(page).toHaveURL(/\/map\?station=10865$/)
  })

  test('is not moved by a station that is not there: the map keeps its zoom for the next click', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/map?station=99999')
    await expect(page.getByTestId('map-unknown')).toBeVisible()
    await expect.poll(() => zoomOf(page)).toBe(6)
    // a click on the dot of Berlin-Tempelhof
    const box = (await page.getByRole('application', { name: /^Station map/ }).boundingBox())!
    const at = offsetAtOpening(52.47, 13.4)
    await page.mouse.click(box.x + box.width / 2 + at.x, box.y + box.height / 2 + at.y)
    await expect(page.getByTestId('map-station-name')).toHaveText('BERLIN-TEMPELHOF')
    // the map did not jump to a pick that was never made
    await page.waitForTimeout(600)
    expect(await zoomOf(page)).toBe(6)
  })

  test('picks the station whose dot is clicked, and for a click beside a dot at the opening zoom the one that reports, not the closed dot a circle of twelve pixels would have taken', async ({ page, baseURL }) => {
    // Artern stopped in 2018; Neuhaus am Rennweg, about 97 km from it, reports
    await open(page, baseURL!, '/map?layer=measured')
    await expect(page.getByTestId('map-count')).toBeVisible()
    await expect.poll(() => zoomOf(page)).toBe(6)
    const map = page.getByRole('application', { name: /^Station map/ })
    const box = (await map.boundingBox())!
    const artern = offsetAtOpening(51.3745, 11.2915)
    // a click on the dot of Artern is Artern, closed as it is
    await page.mouse.click(box.x + box.width / 2 + artern.x, box.y + box.height / 2 + artern.y)
    await expect(page.getByTestId('map-station-name')).toHaveText('Artern')
    await page.getByTestId('map-back').click()
    // a click 9 px beside it (the dot has a radius of 2.75 px, and the click reaches 4.75): 14 km from Artern, 85 km from Neuhaus
    const beside = offsetAtOpening(51.25, 11.15)
    expect(Math.hypot(beside.x - artern.x, beside.y - artern.y)).toBeGreaterThan(8)
    await page.mouse.click(box.x + box.width / 2 + beside.x, box.y + box.height / 2 + beside.y)
    await expect(page.getByTestId('map-station-name')).toHaveText('Neuhaus am Rennweg')
    await expect(page.getByTestId('map-place')).toBeVisible()
  })

  test('keeps the pick for a click on the yellow disc of the station picked, which is bigger than its dot, and does not take it to the station that reports', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/map?layer=measured')
    await expect(page.getByTestId('map-count')).toBeVisible()
    await expect.poll(() => zoomOf(page)).toBe(6)
    const box = (await page.getByRole('application', { name: /^Station map/ }).boundingBox())!
    const artern = offsetAtOpening(51.3745, 11.2915)
    // Artern, which stopped in 2018, picked on its dot
    await page.mouse.click(box.x + box.width / 2 + artern.x, box.y + box.height / 2 + artern.y)
    await expect(page.getByTestId('map-station-name')).toHaveText('Artern')
    // 7 px from its centre, which is on the yellow disc (10.5 px with its edge) and beyond the dot (4.75 px): Artern still
    await page.mouse.click(box.x + box.width / 2 + artern.x + 7, box.y + box.height / 2 + artern.y)
    await page.waitForTimeout(400)
    await expect(page.getByTestId('map-station-name')).toHaveText('Artern')
    await expect(page.getByTestId('map-place')).toHaveCount(0)
    // 16 px from it is the map, and the station that reports is Neuhaus am Rennweg
    await page.mouse.click(box.x + box.width / 2 + artern.x - 16, box.y + box.height / 2 + artern.y + 9)
    await expect(page.getByTestId('map-station-name')).toHaveText('Neuhaus am Rennweg')
  })

  test('keeps a place that is clicked on another copy of the world, as the same place on the first', async ({ page, baseURL }) => {
    const dateline = { station_id: '91000', name: 'DATELINE', region: null, latitude: -17.7, longitude: 179.95, elevation: 5, start_timestamp: null, end_timestamp: null }
    await open(page, baseURL!, '/map?station=91000', { stations: () => ({ stations: [dateline] }) })
    await expect.poll(() => zoomOf(page)).toBe(8)
    await expect(page.getByTestId('map-station-name')).toHaveText('DATELINE')
    await page.getByTestId('map-back').click()
    // 60 px east of the station, across the antimeridian: the map says 180.28, which is -179.72
    const box = (await page.getByRole('application', { name: /^Station map/ }).boundingBox())!
    await page.mouse.click(box.x + box.width / 2 + 60, box.y + box.height / 2)
    await expect(page.getByTestId('map-station-name')).toHaveText('DATELINE')
    await expect(page).toHaveURL(/lat=.*&lon=-179\./)
    const longitude = Number(new URL(page.url()).searchParams.get('lon'))
    expect(Math.abs(longitude)).toBeLessThanOrEqual(180)
    await expect(page.getByTestId('map-place')).toBeVisible()
  })

  test('lets a click through the empty space of the chips to the map', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/map?layer=measured')
    await expect(page.getByTestId('map-count')).toBeVisible()
    const hit = await page.evaluate(() => {
      const row = document.querySelector('.map-chips-row')!.getBoundingClientRect()
      // the right end of the row, past its last chip
      const at = document.elementFromPoint(row.right - 12, row.top + row.height / 2)
      return { onRow: Boolean(at?.closest('.map-chips')), inMap: Boolean(at?.closest('.leaflet-container')) }
    })
    expect(hit).toEqual({ onRow: false, inMap: true })
    // and a chip is still a chip
    await page.getByTestId('map-layer-forecast').click()
    await expect(page.getByTestId('map-layer-forecast')).toHaveAttribute('aria-pressed', 'true')
  })
})

test.describe('the map tool at 320 px', () => {
  test.use({ viewport: { width: 320, height: 700 } })

  // the longer languages: a link of a card that did not wrap pushed the page sideways (Open the measurements in the Explorer)
  for (const language of ['en', 'de', 'de-hh', 'lb', 'nl', 'pl', 'cs', 'it', 'fr']) {
    test(`does not scroll sideways with a station picked, in ${language}`, async ({ page, baseURL }) => {
      await page.context().addCookies([{ name: 'wd_lang', value: language, url: baseURL! }])
      await mockBackend(page, baseURL!, STRIPES_NEAR)
      await page.goto('/map?station=10384&lat=52.9&lon=13.0')
      await expect(page.getByTestId('map-card-measured').getByRole('link').first()).toBeVisible()
      await expect(page.getByTestId('map-card-forecast').getByTestId('day-rows')).toBeVisible()
      const sizes = await page.evaluate(() => ({ page: document.documentElement.scrollWidth - document.documentElement.clientWidth, links: [...document.querySelectorAll('.map-card a')].filter(link => link.getBoundingClientRect().right > document.documentElement.clientWidth).length }))
      expect(sizes).toEqual({ page: 0, links: 0 })
    })
  }

  test('leaves most of the map to the map on the measurements layer, where the chips take the most', async ({ page, baseURL }) => {
    await page.context().addCookies([{ name: 'wd_lang', value: 'nl', url: baseURL! }])
    await mockBackend(page, baseURL!)
    await page.goto('/map?layer=measured')
    await expect(page.getByTestId('map-resolution')).toBeVisible()
    const [chips, stage] = await Promise.all([page.locator('.map-chips').boundingBox(), page.getByTestId('map-stage').boundingBox()])
    expect(chips!.height / stage!.height).toBeLessThan(0.4)
    expect(chips!.x + chips!.width).toBeLessThanOrEqual(320)
    // the count is in the panel, not over the map
    await expect(page.getByTestId('map-count')).toBeHidden()
    await expect(page.getByTestId('map-count-panel')).toBeVisible()
  })
})

test.describe('the map tool on a phone', () => {
  test.use({ viewport: { width: 390, height: 844 } })

  test('has the map first and the panel under it as a sheet', async ({ page, baseURL }) => {
    await open(page, baseURL!)
    const stage = await page.getByTestId('map-stage').boundingBox()
    const panel = await page.getByTestId('map-panel').boundingBox()
    expect(stage!.y + stage!.height).toBeGreaterThan(panel!.y - 12)
    expect(panel!.y).toBeGreaterThan(stage!.y)
    expect(Math.abs(stage!.x - panel!.x)).toBeLessThan(2)
    // the keyboard meets the chips, the map and the panel in the order the window shows them
    const order = await page.evaluate(() => [...document.querySelectorAll('[data-testid="map-layer-forecast"], [role="application"], [data-testid="map-panel"] input')].map(element => element.getAttribute('data-testid') ?? element.getAttribute('role') ?? 'search'))
    expect(order).toEqual(['map-layer-forecast', 'application', 'search'])
  })

  test('has the four tools it had before the map and the Menu in the bar, the map in the Menu, and the Menu marked on the map', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/map')
    const bar = page.locator('.app-tabbar')
    expect(await bar.locator('li').allInnerTexts()).toEqual([en.nav.meteogram, en.nav.explorer, en.nav.stripes, en.nav.history, en.header.menu])
    await expect(bar.getByRole('link', { name: en.nav.map })).toHaveCount(0)
    // the page is the map's, which has no tab: the Menu's tab is the one marked, for the eye and for a screen reader
    const menu = bar.getByRole('button', { name: en.header.menu })
    await expect(menu).toHaveAttribute('aria-current', 'true')
    await expect(bar.locator('[aria-current="page"]')).toHaveCount(0)
    // and it stays so after a pick that changes the address
    await page.goto('/map?station=10384&lat=52.9&lon=13.0')
    await expect(page.getByTestId('map-station-name')).toBeVisible()
    await expect(menu).toHaveAttribute('aria-current', 'true')
    await page.getByTestId('map-layer-measured').click()
    await expect(page).toHaveURL(/layer=measured/)
    await expect(menu).toHaveAttribute('aria-current', 'true')
  })

  test('marks the Menu while one is on the map, as one goes from page to page by the sheet, a tab and the browser\'s Back', async ({ page, baseURL }) => {
    // the navigations of the app itself, no page load: the mark follows the route
    await open(page, baseURL!, '/', {}, 'Wetterdienst')
    const bar = page.locator('.app-tabbar')
    const menu = bar.getByRole('button', { name: en.header.menu })
    await expect(menu).not.toHaveAttribute('aria-current', 'true')
    await menu.click()
    await page.getByRole('dialog', { name: en.header.menu }).getByRole('link', { name: en.nav.map }).click()
    await expect(page).toHaveURL(/\/map$/)
    await expect(menu).toHaveAttribute('aria-current', 'true')
    await bar.getByRole('link', { name: en.nav.history }).click()
    // the history page writes its default query into the address a moment after it opens (`router.replace`): a Back
    // before that is followed by the page's own navigation to /history, so it is waited for
    await expect(page).toHaveURL(/\/history\?provider=dwd/)
    await expect(menu).not.toHaveAttribute('aria-current', 'true')
    await expect(bar.getByRole('link', { name: en.nav.history })).toHaveAttribute('aria-current', 'page')
    await page.goBack()
    await expect(page).toHaveURL(/\/map$/)
    await expect(menu).toHaveAttribute('aria-current', 'true')
    await expect(bar.locator('[aria-current="page"]')).toHaveCount(0)
  })

  test('is found from the Menu, where the map is a link of the sheet that opens it', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/history', {}, en.history.title)
    const bar = page.locator('.app-tabbar')
    await expect(bar.getByRole('link', { name: en.nav.history })).toHaveAttribute('aria-current', 'page')
    await expect(bar.getByRole('button', { name: en.header.menu })).not.toHaveAttribute('aria-current', 'true')
    await bar.getByRole('button', { name: en.header.menu }).click()
    const sheet = page.getByRole('dialog', { name: en.header.menu })
    await sheet.getByRole('link', { name: en.nav.map }).click()
    await expect(page).toHaveURL(/\/map$/)
    await expect(page.getByTestId('map-panel')).toBeVisible()
  })

  test('is found from the home page, whose fifth card is the map, and from the search, which opens it on a station', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/', {}, 'Wetterdienst')
    await page.locator('.home-tasks').getByRole('link', { name: en.mapTool.title }).click()
    await expect(page).toHaveURL(/\/map$/)
    await page.goto('/')
    await page.getByRole('button', { name: en.shell.search, exact: true }).click()
    const dialog = page.getByRole('dialog')
    await dialog.getByRole('combobox').fill('hamburg')
    await dialog.getByRole('option', { name: /Show station 10147 on the map/ }).click()
    await expect(page).toHaveURL(/\/map\?station=10147/)
    await expect(page.getByTestId('map-station-name')).toHaveText('HAMBURG-FUHLSBUETTEL')
  })

  test('has no page that scrolls sideways, the chips included', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/map?layer=measured&station=00011')
    await expect(page.getByTestId('map-station-name')).toBeVisible()
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
    expect(overflow).toBeLessThanOrEqual(0)
    const chips = await page.locator('.map-chips').boundingBox()
    expect(chips!.x + chips!.width).toBeLessThanOrEqual(390)
  })
})

test.describe('the map tool with a finger', () => {
  test.use({ viewport: { width: 1440, height: 900 }, hasTouch: true })

  test('takes a tap beside a closed dot, in the ring of a finger, for the closed station, where the same click of a mouse is the station that reports', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/map?layer=measured')
    await expect(page.getByTestId('map-count')).toBeVisible()
    test.skip(!(await page.evaluate(() => matchMedia('(pointer: coarse)').matches)), 'this browser does not report a coarse pointer for a touch screen')
    await expect.poll(() => zoomOf(page)).toBe(6)
    const box = (await page.getByRole('application', { name: /^Station map/ }).boundingBox())!
    const artern = offsetAtOpening(51.3745, 11.2915)
    // 9 px beside the dot of Artern (the dot reaches 4.75 px, the ring of a finger 12): Artern, the only dot in the ring
    await page.touchscreen.tap(box.x + box.width / 2 + artern.x - 6, box.y + box.height / 2 + artern.y + 7)
    await expect(page.getByTestId('map-station-name')).toHaveText('Artern')
    await expect(page.getByTestId('map-place')).toBeVisible()
  })
})
