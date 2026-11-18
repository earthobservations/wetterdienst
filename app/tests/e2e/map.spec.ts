import type { Page } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { expect, test } from '@playwright/test'
import { emptyScan, exampleScan, stormCellsAnswer } from '../helpers/storm-cells-answer'
import { ApiFailure, mockBackend } from './accessibility/mock-backend'
import { expectAtLeastPx } from './target-size'

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

/** Opens the panel of the layers button (GH-4209), which holds the layers and the grouping, where it is not open */
async function openLayers(page: Page) {
  const button = page.getByTestId('map-layers-button')
  if ((await button.getAttribute('aria-expanded')) !== 'true')
    await button.click()
  await expect(page.getByTestId('map-layers-panel')).toBeVisible()
}

/** The radio of a layer in the panel (the panel is opened first) */
async function layerRadio(page: Page, name: string) {
  await openLayers(page)
  return page.getByTestId('map-layers-panel').getByRole('radio', { name, exact: true })
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
    // the layers are behind one button over the map, which names them in its panel
    await expect(page.getByTestId('map-layers-button')).toHaveAccessibleName(en.mapTool.layersButton)
    await expect(page.getByTestId('map-layers-button')).toHaveAttribute('aria-expanded', 'false')
    await expect(await layerRadio(page, en.mapTool.layerForecast)).toBeChecked()
    await expect(await layerRadio(page, en.mapTool.layerMeasured)).not.toBeChecked()
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

  test('shows the measuring stations of a resolution and a dataset when the layer is chosen in the panel of the layers button', async ({ page, baseURL }) => {
    await open(page, baseURL!)
    await (await layerRadio(page, en.mapTool.layerMeasured)).click()
    await expect(await layerRadio(page, en.mapTool.layerMeasured)).toBeChecked()
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
    // and the panel says why it is not the nearest: Artern is, and stopped in 2018 (GH-3875)
    const why = page.getByTestId('map-why')
    await expect(why).toContainText(/The nearest station that still reports\. Closer: Artern, \d+ km, until 2018\./)
    // the nearer one is offered, by keyboard too: its record can still matter for the history and the stripes
    await page.getByTestId('map-pick-closer').focus()
    await page.keyboard.press('Enter')
    await expect(page.getByTestId('map-station-name')).toHaveText('Artern')
    await expect(page.getByTestId('map-station-name')).toBeFocused()
    await expect(page.getByTestId('map-why')).toHaveCount(0)
    await expect(page.getByTestId('map-place')).toContainText('A point on the map')
  })

  test('draws the stations that have stopped as hollow dots, tells them in a legend, and shows neither on the forecast layer (only the groups, at this zoom)', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/map?layer=measured')
    await expect(page.getByTestId('map-count')).toBeVisible()
    await expect.poll(() => zoomOf(page)).toBe(6)
    const legend = page.getByTestId('map-legend')
    await expect(legend).toBeVisible()
    await expect(legend.getByRole('listitem')).toHaveText([en.mapTool.legendReporting, en.mapTool.legendStopped, `12 ${en.mapTool.legendGroupShare}`])
    const map = page.getByRole('application', { name: /^Station map/ })
    const box = (await map.boundingBox())!
    const centre = (latitude: number, longitude: number) => {
      const at = offsetAtOpening(latitude, longitude)
      return { x: box.x + box.width / 2 + at.x, y: box.y + box.height / 2 + at.y }
    }
    // the middle of a dot, by the pixel the canvas has there: the blue of a station that reports, the light of the
    // halo in the ring of one that has stopped (a difference of fill, not of colour alone)
    const pixel = ({ x, y }: { x: number, y: number }) => page.evaluate(({ x, y }) => {
      for (const canvas of document.querySelectorAll<HTMLCanvasElement>('.leaflet-layer canvas')) {
        const rect = canvas.getBoundingClientRect()
        if (x < rect.left || x >= rect.right || y < rect.top || y >= rect.bottom)
          continue
        const ratio = canvas.width / rect.width
        const data = canvas.getContext('2d')!.getImageData(Math.round((x - rect.left) * ratio), Math.round((y - rect.top) * ratio), 1, 1).data
        if (data[3]! > 0)
          return [data[0], data[1], data[2]]
      }
      return null
    }, { x, y })
    // the stations are dots where they are not grouped (the groups of the opening zoom hold the near ones): Neuhaus am Rennweg reports, Artern stopped in 2018
    await groupBy(page, false)
    await expect.poll(() => pixel(centre(50.5063, 11.1283))).toEqual([0x23, 0x58, 0xA8])
    await expect.poll(async () => (await pixel(centre(51.3745, 11.2915)))?.every(channel => channel! >= 220)).toBe(true)
    await groupBy(page, true)

    // the legend is on the map and takes the click, which is no pick of the place under it
    await legend.scrollIntoViewIfNeeded()
    const hit = await legend.evaluate((element) => {
      const rect = element.getBoundingClientRect()
      return Boolean(document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2)?.closest('.map-legend'))
    })
    expect(hit).toBe(true)
    // and its two dots are told apart by their fill, in forced colours too
    await page.emulateMedia({ forcedColors: 'active' })
    expect(await legend.evaluate(element => getComputedStyle(element).forcedColorAdjust)).toBe('none')
    await (await layerRadio(page, en.mapTool.layerForecast)).click()
    // the forecast's points have no status, so the legend has no dots to tell apart: the groups only, at this zoom
    await expect(page.getByTestId('map-legend').getByRole('listitem')).toHaveText([`12 ${en.mapTool.legendGroup}`])
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

  test('lets a click through the empty space of the status row to the map', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/map?layer=measured')
    await expect(page.getByTestId('map-count')).toBeVisible()
    // the map's code is loaded apart from the page: it is there when its container is
    await expect(page.locator('.station-map.leaflet-container')).toBeVisible()
    const hit = await page.evaluate(() => {
      const row = document.querySelector('.map-chips-row')!.getBoundingClientRect()
      // the row's own empty space, past the count
      const at = document.elementFromPoint(row.right - 70, row.top + row.height / 2)
      return { onRow: Boolean(at?.closest('.map-chips')), inMap: Boolean(at?.closest('.leaflet-container')) }
    })
    expect(hit).toEqual({ onRow: false, inMap: true })
    // and the layer can still be chosen
    await (await layerRadio(page, en.mapTool.layerForecast)).click()
    await expect(await layerRadio(page, en.mapTool.layerForecast)).toBeChecked()
  })
})

// The groups of stations at the outer zooms (GH-4079): forty forecast points within a few kilometres of Hamburg, which are
// under three pixels apart at the opening zoom, and Berlin's, which is alone
function dense(latitude: number, longitude: number) {
  return Array.from({ length: 40 }, (_, index) => ({
    station_id: `G${String(index).padStart(2, '0')}`,
    name: `GROUP POINT ${index}`,
    region: null,
    latitude: latitude + (index % 8) * 0.003,
    longitude: longitude + Math.floor(index / 8) * 0.004,
    elevation: 10,
    start_timestamp: null,
    end_timestamp: null,
  }))
}
const DENSE = dense(53.6, 9.99)
const BERLIN_ALONE = { station_id: '10384', name: 'BERLIN-TEMPELHOF', region: null, latitude: 52.47, longitude: 13.4, elevation: 49, start_timestamp: null, end_timestamp: null }
const GROUPED = { stations: () => ({ stations: [...DENSE, BERLIN_ALONE] }) }

/** The colour of the pixel a canvas of the map has at a point of the window (null where it has none) */
async function canvasPixel(page: Page, x: number, y: number) {
  return page.evaluate(({ x, y }) => {
    for (const canvas of document.querySelectorAll<HTMLCanvasElement>('.leaflet-layer canvas')) {
      const rect = canvas.getBoundingClientRect()
      if (x < rect.left || x >= rect.right || y < rect.top || y >= rect.bottom)
        continue
      const ratio = canvas.width / rect.width
      const data = canvas.getContext('2d')!.getImageData(Math.round((x - rect.left) * ratio), Math.round((y - rect.top) * ratio), 1, 1).data
      if (data[3]! > 0)
        return [data[0], data[1], data[2]]
    }
    return null
  }, { x, y })
}

/** The grouping switch, in the panel of the layers button (GH-4209), which is opened first */
async function groupingSwitch(page: Page) {
  await openLayers(page)
  return page.getByTestId('map-grouping')
}

/** Turns the grouping on or off with the pointer, and closes the panel again: a press on the map while it is open only closes it, and picks no place */
async function groupBy(page: Page, on: boolean) {
  const control = await groupingSwitch(page)
  await control.click()
  await expect(control).toHaveAttribute('aria-checked', String(on))
  await page.keyboard.press('Escape')
  await expect(page.getByTestId('map-layers-panel')).toBeHidden()
}

test.describe('the map tool: groups of stations at the outer zooms', () => {
  test.use({ viewport: { width: 1440, height: 900 } })

  test('draws the stations that lie close together as one disc with their number, which a click zooms in on, and picks no place', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/map', GROUPED)
    await expect(page.getByTestId('map-count')).toHaveText('Stations shown: 41')
    await expect.poll(() => zoomOf(page)).toBe(6)
    const map = page.getByRole('application', { name: /^Station map/ })
    const box = (await map.boundingBox())!
    const at = offsetAtOpening(53.62, 10.0)
    const centre = { x: box.x + box.width / 2 + at.x, y: box.y + box.height / 2 + at.y }
    // the disc of the group: the dot's blue, beside the number, which is the middle of it (a group of forty is 16 px in radius)
    await expect.poll(() => canvasPixel(page, centre.x - 11, centre.y)).toEqual([0x23, 0x58, 0xA8])
    // and the legend says what a number is, which is on the map for the forecast layer as well
    await expect(page.getByTestId('map-legend').getByRole('listitem')).toHaveText([`12 ${en.mapTool.legendGroup}`])
    // the map has the stations in the count, as before: the groups are what is drawn, not what is listed
    await expect(page.getByTestId('map-panel').getByRole('button', { name: /GROUP POINT/ }).first()).toBeVisible()

    await page.mouse.click(centre.x, centre.y)
    await expect(page.getByTestId('map-announcement')).toHaveText('Zoomed in on a group. Stations in it: 40')
    // the stations are a few kilometres apart: the map goes in as far as the zoom they are separated from (10)
    await expect.poll(() => zoomOf(page)).toBe(10)
    // no place is picked by the click on a group, and no group is left: the stations are dots
    await expect(page.getByTestId('map-station-name')).toHaveCount(0)
    await expect(page).toHaveURL(/\/map$/)
    await expect(page.getByTestId('map-legend')).toHaveCount(0)
  })

  test('has the layers button in the top right corner of the map, clear of the zoom buttons and the legend, and the credit of OpenStreetMap at the very bottom under the zoom buttons (GH-4209)', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/map', GROUPED)
    await expect(page.getByTestId('map-count')).toBeVisible()
    await expect(page.getByTestId('map-legend')).toBeVisible()
    // the map's code is loaded apart from the page
    await expect(page.locator('.leaflet-control-attribution')).toBeVisible()
    await expect(page.locator('.leaflet-control-zoom')).toBeVisible()
    const rects = await page.evaluate(() => {
      const rect = (selector: string) => {
        const box = document.querySelector(selector)!.getBoundingClientRect()
        return { top: box.top, bottom: box.bottom, left: box.left, right: box.right }
      }
      return { stage: rect('.map-stage'), button: rect('[data-testid="map-layers-button"]'), zoom: rect('.leaflet-control-zoom'), credit: rect('.leaflet-control-attribution'), legend: rect('.map-legend') }
    })
    // the top right: near the corner
    expect(rects.stage.right - rects.button.right).toBeLessThan(20)
    expect(rects.button.top - rects.stage.top).toBeLessThan(20)
    // clear of the zoom buttons (bottom right) and of the legend (bottom left)
    expect(rects.button.bottom).toBeLessThan(rects.zoom.top)
    expect(rects.button.bottom).toBeLessThan(rects.legend.top)
    // the credit is under the zoom buttons, at the foot of the map, and the buttons above it
    expect(rects.credit.top).toBeGreaterThanOrEqual(rects.zoom.bottom - 1)
    expect(rects.stage.bottom - rects.credit.bottom).toBeLessThan(12)
    // and it says whose map it is
    await expect(page.locator('.leaflet-control-attribution')).toContainText('OpenStreetMap')
  })

  test('closes the open panel with a press on the map and does no more: no zoom on a group under it, no pick of a place, and the next click does both (GH-4209)', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/map', GROUPED)
    await expect(page.getByTestId('map-count')).toBeVisible()
    await expect.poll(() => zoomOf(page)).toBe(6)
    const box = (await page.getByRole('application', { name: /^Station map/ }).boundingBox())!
    const group = offsetAtOpening(53.62, 10.0)
    const berlin = offsetAtOpening(52.47, 13.4)
    const press = (at: { x: number, y: number }) => page.mouse.click(box.x + box.width / 2 + at.x, box.y + box.height / 2 + at.y)
    // on a group's disc
    await openLayers(page)
    await press(group)
    await expect(page.getByTestId('map-layers-panel')).toBeHidden()
    await page.waitForTimeout(600)
    expect(await zoomOf(page)).toBe(6)
    await expect(page.getByTestId('map-announcement')).not.toContainText('Zoomed')
    // on a station that is alone, a press that is held longer than any window of time would be
    await openLayers(page)
    await page.mouse.move(box.x + box.width / 2 + berlin.x, box.y + box.height / 2 + berlin.y)
    await page.mouse.down()
    await page.waitForTimeout(900)
    await page.mouse.up()
    await expect(page.getByTestId('map-layers-panel')).toBeHidden()
    await page.waitForTimeout(300)
    await expect(page.getByTestId('map-station-name')).toHaveCount(0)
    // the next click is the map's own again
    await press(berlin)
    await expect(page.getByTestId('map-station-name')).toHaveText('BERLIN-TEMPELHOF')
    await press(group)
    await expect(page.getByTestId('map-announcement')).toHaveText('Zoomed in on a group. Stations in it: 40')
  })

  test('centres the map on the group that was clicked, though its stations are not spread evenly round the disc (GH-4209)', async ({ page, baseURL }) => {
    // twenty stations in a town and one far to the north east: the disc is drawn at the mean, near the town, and the middle of the
    // box of the stations (which the map was centred on) is 30 km from it
    const town = Array.from({ length: 20 }, (_, index) => ({ station_id: `L${index}`, name: `LOPSIDED ${index}`, region: null, latitude: 52.0 + (index % 5) * 0.01, longitude: 10.4 + Math.floor(index / 5) * 0.01, elevation: 10, start_timestamp: null, end_timestamp: null }))
    const far = { station_id: 'LFAR', name: 'LOPSIDED FAR', region: null, latitude: 52.8, longitude: 11.6, elevation: 10, start_timestamp: null, end_timestamp: null }
    await open(page, baseURL!, '/map', { stations: () => ({ stations: [...town, far] }) })
    await expect(page.getByTestId('map-count')).toHaveText('Stations shown: 21')
    await expect.poll(() => zoomOf(page)).toBe(6)
    const map = page.getByRole('application', { name: /^Station map/ })
    const box = (await map.boundingBox())!
    // the disc, where it is drawn: the mean of the stations
    const mean = { latitude: (20 * 52.02 + 52.8) / 21, longitude: (20 * 10.415 + 11.6) / 21 }
    const at = offsetAtOpening(mean.latitude, mean.longitude)
    await expect.poll(() => canvasPixel(page, box.x + box.width / 2 + at.x - 9, box.y + box.height / 2 + at.y)).toEqual([0x23, 0x58, 0xA8])
    await page.mouse.click(box.x + box.width / 2 + at.x - 9, box.y + box.height / 2 + at.y)
    await expect(page.getByTestId('map-announcement')).toHaveText('Zoomed in on a group. Stations in it: 21')
    // the disc is now in the middle of the map: the group is one disc again, or a few dots, and the middle of the map is on the mean
    await expect.poll(() => zoomOf(page)).toBeGreaterThan(6)
    const middle = { x: box.x + box.width / 2, y: box.y + box.height / 2 }
    await expect.poll(() => canvasPixel(page, middle.x - 9, middle.y)).toEqual([0x23, 0x58, 0xA8])
  })

  test('leaves a station that is alone a dot at the outer zoom, picked by a click on it as before', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/map', GROUPED)
    await expect(page.getByTestId('map-count')).toBeVisible()
    await expect.poll(() => zoomOf(page)).toBe(6)
    const box = (await page.getByRole('application', { name: /^Station map/ }).boundingBox())!
    const at = offsetAtOpening(52.47, 13.4)
    await expect.poll(() => canvasPixel(page, box.x + box.width / 2 + at.x, box.y + box.height / 2 + at.y)).toEqual([0x23, 0x58, 0xA8])
    await page.mouse.click(box.x + box.width / 2 + at.x, box.y + box.height / 2 + at.y)
    await expect(page.getByTestId('map-station-name')).toHaveText('BERLIN-TEMPELHOF')
    expect(await zoomOf(page)).toBe(6)
  })

  test('draws a place that has stations that report and stations that have stopped as one group, a ring filled for the share that reports, and says it on a click', async ({ page, baseURL }) => {
    // forty stations on one place, half of them reporting: the first twenty, the others stopped in 2010
    const running = new Date(Date.now() - 2 * 86_400_000).toISOString().replace(/T.*$/, 'T00:00:00+00:00')
    const mixed = dense(53.6, 9.99).map((entry, index) => ({ ...entry, start_timestamp: '1990-01-01T00:00:00+00:00', end_timestamp: index < 20 ? running : '2010-12-31T00:00:00+00:00' }))
    await open(page, baseURL!, '/map?layer=measured', { stations: () => ({ stations: [...mixed, BERLIN_ALONE] }) })
    await expect(page.getByTestId('map-count')).toHaveText('Stations shown: 41')
    await expect.poll(() => zoomOf(page)).toBe(6)
    const box = (await page.getByRole('application', { name: /^Station map/ }).boundingBox())!
    const at = offsetAtOpening(53.611, 9.998)
    const centre = { x: box.x + box.width / 2 + at.x, y: box.y + box.height / 2 + at.y }
    // a group of forty is 16 px in radius; its band, 5 px wide, is 12.25 px from the middle. Half report: the band is filled from
    // the top clockwise, so the right of it is the dot's blue and the left of it the light of the hollow ring
    await expect.poll(() => canvasPixel(page, centre.x + 12.25, centre.y)).toEqual([0x23, 0x58, 0xA8])
    const left = await canvasPixel(page, centre.x - 12.25, centre.y)
    expect(left!.every(channel => channel >= 220), 'the band is hollow where the stations have stopped').toBe(true)
    // the middle of the disc is light, for the number
    // and the legend says what the filled part of the ring is
    await expect(page.getByTestId('map-legend').getByRole('listitem').last()).toHaveText(`12 ${en.mapTool.legendGroupShare}`)

    // one group for the place, whatever the status: a click zooms in on all forty
    await page.mouse.click(centre.x, centre.y)
    await expect(page.getByTestId('map-announcement')).toHaveText('Zoomed in on a group. Stations in it: 40, of them reporting: 20')
    await expect.poll(() => zoomOf(page)).toBe(10)
  })

  test('is turned off by the switch, which draws every station as a dot at the zoom of the opening', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/map', GROUPED)
    await expect(page.getByTestId('map-count')).toBeVisible()
    // on or off, on by default, and named
    await expect(await groupingSwitch(page)).toHaveAttribute('aria-checked', 'true')
    await expect(page.getByTestId('map-layers-panel').getByText(en.mapTool.groupStations)).toBeVisible()
    await expect(page.getByTestId('map-legend')).toBeVisible()
    await groupBy(page, false)
    await expect(page.getByTestId('map-legend')).toHaveCount(0)
    // a click on the place is a pick of a station, not a zoom
    const box = (await page.getByRole('application', { name: /^Station map/ }).boundingBox())!
    const at = offsetAtOpening(53.62, 10.0)
    await page.mouse.click(box.x + box.width / 2 + at.x, box.y + box.height / 2 + at.y)
    await expect(page.getByTestId('map-station-name')).toHaveText(/GROUP POINT/)
    expect(await zoomOf(page)).toBe(6)
  })

  test('keeps grouping to a close zoom: the legend of the groups is there at zoom 9 and gone at 10, where every station is its own dot', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/map', GROUPED)
    await expect(page.getByTestId('map-count')).toBeVisible()
    // one zoom at a time: Leaflet takes no press while it animates the one before
    for (const zoom of [7, 8, 9]) {
      await page.getByRole('button', { name: en.mapTool.zoomIn }).click()
      await expect.poll(() => zoomOf(page)).toBe(zoom)
      await page.waitForTimeout(500)
    }
    await expect(page.getByTestId('map-legend')).toBeVisible()
    await page.getByRole('button', { name: en.mapTool.zoomIn }).click()
    await expect.poll(() => zoomOf(page)).toBe(10)
    await expect(page.getByTestId('map-legend')).toHaveCount(0)
  })

  test('keeps the station picked in view above the group it is in, and a click on its disc is still on that station', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/map?station=G05', GROUPED)
    // the map has moved to the station, at zoom 8, where the forty are still one group
    await expect.poll(() => zoomOf(page)).toBe(8)
    await expect(page.getByTestId('map-legend')).toBeVisible()
    const disc = page.locator('.leaflet-station-marks-pane path[fill="#ffc93c"]')
    await expect(disc).toBeVisible()
    // the disc is over the group: the pane of the marks is above the one the group is drawn in
    const order = await page.evaluate(() => {
      const z = (selector: string) => Number(getComputedStyle(document.querySelector(selector)!).zIndex)
      return { marks: z('.leaflet-station-marks-pane'), groups: z('.leaflet-overlay-pane') }
    })
    expect(order.marks).toBeGreaterThan(order.groups)
    const box = (await disc.boundingBox())!
    await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2)
    await page.waitForTimeout(500)
    // not a zoom, and not another station: the pick stays
    expect(await zoomOf(page)).toBe(8)
    await expect(page.getByTestId('map-station-name')).toHaveText('GROUP POINT 5')
  })

  test('is reached by the keyboard as the rest of the map is: the groups are no stops of Tab, and the plus key and the buttons zoom in on them', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/map', GROUPED)
    await expect(page.getByTestId('map-count')).toBeVisible()
    await expect.poll(() => zoomOf(page)).toBe(6)
    // the map and its two zoom buttons are what the keyboard finds in it, however many stations there are
    const stops = await page.evaluate(() => [...document.querySelectorAll<HTMLElement>('.station-map [tabindex], .station-map a, .station-map button')].map(element => element.getAttribute('aria-label') ?? element.className))
    expect(stops.filter(stop => /marker|cluster|group/i.test(stop))).toEqual([])
    const map = page.getByRole('application', { name: /^Station map/ })
    await map.focus()
    for (const zoom of [7, 8, 9, 10]) {
      await page.keyboard.press('+')
      await expect.poll(() => zoomOf(page)).toBe(zoom)
      // Leaflet takes no press while it animates the one before
      await page.waitForTimeout(500)
    }
    // at the zoom every station is its own dot from there are no groups to explain
    await expect(page.getByTestId('map-legend')).toHaveCount(0)
    // and the grouping is a switch that a keyboard sets, in the panel of the layers button, which Escape closes and gives the focus back from
    const button = page.getByTestId('map-layers-button')
    await button.focus()
    await page.keyboard.press('Enter')
    await expect(page.getByTestId('map-layers-panel')).toBeVisible()
    const control = page.getByTestId('map-grouping')
    await control.focus()
    await page.keyboard.press('Space')
    await expect(control).toHaveAttribute('aria-checked', 'false')
    await page.keyboard.press('Escape')
    await expect(page.getByTestId('map-layers-panel')).toBeHidden()
    await expect(button).toBeFocused()
    await expect(button).toHaveAttribute('aria-expanded', 'false')
  })

  test('is always on for a layer of more than 10,000 stations, which the switch does not turn off, and says why', async ({ page, baseURL }) => {
    const many = Array.from({ length: 10_001 }, (_, index) => ({
      station_id: `W${index}`,
      name: `WORLD ${index}`,
      region: null,
      latitude: -50 + (index % 100) * 1.2,
      longitude: -170 + Math.floor(index / 100) * 3.4,
      elevation: null,
      start_timestamp: null,
      end_timestamp: null,
    }))
    await open(page, baseURL!, '/map', { stations: () => ({ stations: many }) })
    await expect(page.getByTestId('map-count')).toBeVisible()
    const control = await groupingSwitch(page)
    const note = page.getByTestId('map-grouping-note')
    await expect(note).toHaveText(en.mapTool.groupingCompulsory.replace('{shown}', '10,000'))
    await expect(control).toHaveAttribute('aria-describedby', 'map-grouping-note')
    // on, and disabled: it cannot be turned off
    await expect(control).toHaveAttribute('aria-checked', 'true')
    await expect(control).toBeDisabled()
    await expect(page.getByTestId('map-legend')).toBeVisible()
  })
})

test.describe('the map tool on a phone: groups of stations', () => {
  test.use({ viewport: { width: 390, height: 844 }, hasTouch: true })

  test('are drawn and tapped as on a wide screen, with the layers button the only control over the map and no sideways scroll', async ({ page, baseURL }) => {
    // the group is near the middle of the map, which is what a phone shows of it under the chips
    await open(page, baseURL!, '/map', { stations: () => ({ stations: [...dense(51.3, 10.4), BERLIN_ALONE] }) })
    await expect(page.getByTestId('map-layers-button')).toBeVisible()
    await expect.poll(() => zoomOf(page)).toBe(6)
    const sideways = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
    expect(sideways).toBe(0)
    const box = (await page.getByRole('application', { name: /^Station map/ }).boundingBox())!
    const at = offsetAtOpening(51.31, 10.41)
    await page.touchscreen.tap(box.x + box.width / 2 + at.x, box.y + box.height / 2 + at.y)
    await expect.poll(() => zoomOf(page)).toBe(10)
    await expect(page.getByTestId('map-station-name')).toHaveCount(0)
  })
})

// A station carried across layers by its WMO number (GH-4077): the forecast point of Hamburg and the measuring station
// that is the same station (the same number, 0.8 km apart), and a measuring station with no number that is nearer to the point
const CARRIED_FORECAST = [
  { station_id: '10147', name: 'HAMBURG-FUHLSBUETTEL', region: null, latitude: 53.63, longitude: 10.0, elevation: 11, wmo_id: '10147', start_timestamp: null, end_timestamp: null },
]
const RUNNING_END = new Date(Date.now() - 2 * 86_400_000).toISOString().replace(/T.*$/, 'T00:00:00+00:00')
const CARRIED_MEASURED = [
  { station_id: '01975', name: 'Hamburg-Fuhlsbüttel', region: 'Hamburg', latitude: 53.6332, longitude: 9.9881, elevation: 11, wmo_id: '10147', start_timestamp: '1891-01-01T00:00:00+00:00', end_timestamp: RUNNING_END },
  { station_id: '00999', name: 'Hamburg-Nahe', region: 'Hamburg', latitude: 53.6295, longitude: 10.0003, elevation: 10, wmo_id: null, start_timestamp: '1990-01-01T00:00:00+00:00', end_timestamp: RUNNING_END },
]
const CARRIED = { stations: (url: URL) => ({ stations: url.searchParams.get('network') === 'mosmix' ? CARRIED_FORECAST : CARRIED_MEASURED }) }

test.describe('the map tool: the station picked across layers', () => {
  test.use({ viewport: { width: 1440, height: 900 } })

  test('is the same station in the other layer by its WMO number, though a nearer station has none, and says so', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/map?station=10147', CARRIED)
    const panel = page.getByTestId('map-panel')
    await expect(panel.getByRole('heading', { level: 2 })).toHaveText('HAMBURG-FUHLSBUETTEL')
    await expect(page.getByTestId('map-same-station')).toHaveCount(0)

    await (await layerRadio(page, en.mapTool.layerMeasured)).click()
    await expect(panel.getByRole('heading', { level: 2 })).toHaveText('Hamburg-Fuhlsbüttel')
    await expect(page.getByTestId('map-same-station')).toHaveText('The same station, by its WMO number 10147.')
    await expect(page.getByTestId('map-announcement')).toHaveText('Hamburg-Fuhlsbüttel chosen. The same station, by its WMO number 10147.')
    await expect(page).toHaveURL(/\/map\?layer=measured&station=01975$/)
    // the forecast card is the same station too, by the number, not "some way away"
    await expect(page.getByTestId('map-card-same-forecast')).toContainText('HAMBURG-FUHLSBUETTEL')

    // and back
    await (await layerRadio(page, en.mapTool.layerForecast)).click()
    await expect(panel.getByRole('heading', { level: 2 })).toHaveText('HAMBURG-FUHLSBUETTEL')
    await expect(page.getByTestId('map-same-station')).toBeVisible()
    await expect(page).toHaveURL(/\/map\?station=10147$/)
  })

  test('is carried by the keyboard alone: the layers button opened with Enter, the layer chosen with Space', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/map?station=10147', CARRIED)
    const panel = page.getByTestId('map-panel')
    await expect(panel.getByRole('heading', { level: 2 })).toHaveText('HAMBURG-FUHLSBUETTEL')
    await page.getByTestId('map-layers-button').focus()
    await page.keyboard.press('Enter')
    await expect(page.getByTestId('map-layers-panel')).toBeVisible()
    await page.getByTestId('map-layers-panel').getByRole('radio', { name: en.mapTool.layerMeasured, exact: true }).focus()
    await page.keyboard.press('Space')
    await expect(panel.getByRole('heading', { level: 2 })).toHaveText('Hamburg-Fuhlsbüttel')
    await expect(page.getByTestId('map-same-station')).toBeVisible()
  })

  test('is the station for the place where it has no WMO number: the nearer station, and nothing said of the same', async ({ page, baseURL }) => {
    const unnumbered = { stations: (url: URL) => ({ stations: url.searchParams.get('network') === 'mosmix' ? CARRIED_FORECAST.map(entry => ({ ...entry, wmo_id: null })) : CARRIED_MEASURED }) }
    await open(page, baseURL!, '/map?station=10147', unnumbered)
    await expect(page.getByTestId('map-panel').getByRole('heading', { level: 2 })).toHaveText('HAMBURG-FUHLSBUETTEL')
    await (await layerRadio(page, en.mapTool.layerMeasured)).click()
    await expect(page.getByTestId('map-panel').getByRole('heading', { level: 2 })).toHaveText('Hamburg-Nahe')
    await expect(page.getByTestId('map-same-station')).toHaveCount(0)
  })
})

// The panel of the layers button has the layers and a switch with a label, which must fit the window's width in every language at 320 px
test.describe('the layers panel at 320 px', () => {
  test.use({ viewport: { width: 320, height: 700 } })

  for (const language of ['en', 'de', 'de-hh', 'fr', 'es', 'it', 'nl', 'pl', 'cs', 'da', 'lb']) {
    test(`fits the window's width, whole, in ${language}`, async ({ page, baseURL }) => {
      await page.context().addCookies([{ name: 'wd_lang', value: language, url: baseURL! }])
      await mockBackend(page, baseURL!, GROUPED)
      await page.goto('/map')
      await expect(page.getByTestId('map-count')).toBeAttached()
      const button = page.getByTestId('map-layers-button')
      await expect(button).toBeVisible()
      await button.click()
      await expect(page.getByTestId('map-grouping')).toBeVisible()
      const place = await page.evaluate(() => {
        const panel = document.querySelector('[data-testid="map-layers-panel"]')!.getBoundingClientRect()
        const cut = [...document.querySelectorAll<HTMLElement>('[data-testid="map-layers-panel"] label')].filter(label => label.scrollWidth > label.clientWidth + 1).map(label => label.textContent)
        return { left: panel.left, right: panel.right, width: window.innerWidth, cut, sideways: document.documentElement.scrollWidth - document.documentElement.clientWidth }
      })
      // 1 px: what the browser measures, not what the CSS says
      expect(place.right, 'the panel ends where the window does or before').toBeLessThanOrEqual(place.width + 1)
      expect(place.left).toBeGreaterThanOrEqual(-1)
      expect(place.cut, 'each label is whole').toEqual([])
      expect(place.sideways, 'the page does not scroll sideways').toBe(0)
    })
  }
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

  test('leaves the map to the map on the measurements layer: one button of 44 px over it, and the choices of the source in its panel', async ({ page, baseURL }) => {
    await page.context().addCookies([{ name: 'wd_lang', value: 'nl', url: baseURL! }])
    await mockBackend(page, baseURL!)
    await page.goto('/map?layer=measured')
    const button = page.getByTestId('map-layers-button')
    await expect(button).toBeVisible()
    const [box, stage] = await Promise.all([button.boundingBox(), page.getByTestId('map-stage').boundingBox()])
    expectAtLeastPx(box!.width, 44, 'the layers button is wide')
    expectAtLeastPx(box!.height, 44, 'the layers button is high')
    expect(box!.x + box!.width).toBeLessThanOrEqual(stage!.x + stage!.width)
    expect(box!.height / stage!.height).toBeLessThan(0.15)
    // the source is not on the map: it is in the panel
    await expect(page.getByTestId('map-resolution')).toBeHidden()
    await button.click()
    await expect(page.getByTestId('map-resolution')).toBeVisible()
    await expect(page.getByTestId('map-dataset')).toBeVisible()
    const select = (await page.getByTestId('map-resolution').boundingBox())!
    expect(select.x + select.width).toBeLessThanOrEqual(320)
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
    // the keyboard meets the layers button, the map and the panel in the order the window shows them
    const order = await page.evaluate(() => [...document.querySelectorAll('[data-testid="map-layers-button"], [role="application"], [data-testid="map-panel"] input')].map(element => element.getAttribute('data-testid') ?? element.getAttribute('role') ?? 'search'))
    expect(order).toEqual(['map-layers-button', 'application', 'search'])
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
    await (await layerRadio(page, en.mapTool.layerMeasured)).click()
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

// The legend and the credit of OpenStreetMap are both at the map's foot, the legend on the left and the credit on the right, and
// on a narrow map the credit is wider than the right half: they must not lie over each other (GH-4209)
for (const width of [320, 390]) {
  test.describe(`the legend and the credit at ${width} px`, () => {
    test.use({ viewport: { width, height: 800 } })

    for (const language of ['en', 'de', 'de-hh', 'fr', 'es', 'it', 'nl', 'pl', 'cs', 'da', 'lb']) {
      for (const path of ['/map', '/map?layer=measured']) {
        test(`are apart in ${language}, ${path === '/map' ? 'the forecast' : 'the measurements'}`, async ({ page, baseURL }) => {
          await page.context().addCookies([{ name: 'wd_lang', value: language, url: baseURL! }])
          await mockBackend(page, baseURL!, GROUPED)
          await page.goto(path)
          await expect(page.getByTestId('map-legend')).toBeVisible()
          await expect(page.locator('.leaflet-control-attribution')).toBeVisible()
          const rects = await page.evaluate(() => {
            const rect = (selector: string) => {
              const box = document.querySelector(selector)!.getBoundingClientRect()
              return { top: box.top, bottom: box.bottom, left: box.left, right: box.right }
            }
            return { legend: rect('.map-legend'), credit: rect('.leaflet-control-attribution'), zoom: rect('.leaflet-control-zoom') }
          })
          const apart = (a: { top: number, bottom: number, left: number, right: number }, b: typeof a) => a.bottom <= b.top || b.bottom <= a.top || a.right <= b.left || b.right <= a.left
          expect(apart(rects.legend, rects.credit), 'the legend is clear of the credit').toBe(true)
          expect(apart(rects.legend, rects.zoom), 'the legend is clear of the zoom buttons').toBe(true)
        })
      }
    }
  })
}

// The thunderstorm cells of DWD's radar (GH-4208): a switch in the layers panel that draws the cells of the latest scan over the
// stations, lists them in the panel, and says so where the scan has none. The mock serves a scan with cells and an empty one.
test.describe('the thunderstorm cells', () => {
  test.use({ viewport: { width: 1440, height: 900 } })

  const WITH_CELLS = { 'storm-cells': () => exampleScan() }
  const NO_CELLS = { 'storm-cells': () => emptyScan() }
  /** The scan of a page whose clock is set to 2026-11-17 22:21 UTC (a scan is out of date after 20 minutes of that clock) */
  const SCAN_OF_THE_CLOCK = '2026-11-17T22:15:00.000000+00:00'

  /** Counts the requests for the scan of the cells, and answers each from `scan` */
  function counting(scan: () => unknown) {
    const asked: Array<Record<string, string>> = []
    return {
      asked,
      handlers: {
        'storm-cells': (url: URL) => {
          asked.push(Object.fromEntries(url.searchParams))
          return scan()
        },
      },
    }
  }

  test('are a switch beside the layers, off at the opening, and nothing is asked for or drawn while it is', async ({ page, baseURL }) => {
    const cells = counting(exampleScan)
    const backend = await open(page, baseURL!, '/map', cells.handlers)
    await expect(page.getByTestId('map-count')).toBeVisible()
    await openLayers(page)
    const control = page.getByRole('switch', { name: en.mapTool.layerCells })
    await expect(control).toBeVisible()
    await expect(control).not.toBeChecked()
    // the layers stay the stations' (two radios), the cells are no third
    await expect(page.getByTestId('map-layers-panel').getByRole('radio')).toHaveCount(2)
    await expect(page.getByTestId('map-cells')).toHaveCount(0)
    await expect(page.locator('.leaflet-storm-cells-pane path')).toHaveCount(0)
    expect(cells.asked).toEqual([])
    expect(backend.unanswered).toEqual([])
  })

  test('draw the outline, the severity and the calculated motion of each cell of a scan over the stations, and list them in words', async ({ page, baseURL }) => {
    const cells = counting(exampleScan)
    const backend = await open(page, baseURL!, '/map', cells.handlers)
    await expect(page.getByTestId('map-count')).toHaveText('Stations shown: 4')
    await openLayers(page)
    await page.getByRole('switch', { name: en.mapTool.layerCells }).click()
    await expect(page).toHaveURL(/\/map\?cells=1$/)
    expect(cells.asked).toEqual([{ track: 'false' }])
    // an outline for each of the four cells, and a mark at the centre of each with the number of its severity
    await expect(page.locator('.leaflet-storm-cells-pane path')).toHaveCount(4)
    const marks = page.locator('.leaflet-storm-cell-marks-pane .storm-cell-mark')
    await expect(marks).toHaveCount(4)
    expect(await marks.locator('text').allTextContents()).toEqual(expect.arrayContaining(['0', '1', '2', '3']))
    // every mark has an arrow: the four cells move
    await expect(page.locator('.leaflet-storm-cell-marks-pane .storm-cell-mark-moving')).toHaveCount(4)
    // the marks are no stop of the keyboard, no button and no text for a screen reader
    await expect(page.locator('.leaflet-storm-cell-marks-pane [tabindex], .leaflet-storm-cell-marks-pane [role="button"]')).toHaveCount(0)
    await expect(marks.first().locator('svg')).toHaveAttribute('aria-hidden', 'true')
    // the stations are still there, the map has not moved from Germany, and DWD is credited on the map
    await expect.poll(() => zoomOf(page)).toBe(6)
    await expect(page.getByTestId('map-count')).toHaveText('Stations shown: 4')
    await expect(page.locator('.leaflet-control-attribution')).toContainText('Source: Deutscher Wetterdienst (KONRAD3D)')
    // with the licence as a link to its terms, on the map as in the panel
    await expect(page.locator('.leaflet-control-attribution').getByRole('link', { name: 'CC-BY-4.0' })).toHaveAttribute('href', 'https://creativecommons.org/licenses/by/4.0/')
    await expect(page.getByRole('application', { name: /^Station map/ })).toHaveAccessibleName(`${en.mapTool.mapLabelCells.replace('{layer}', en.mapTool.layerForecast)}`)

    // the same cells in the panel, where the map is not needed to read them: severity in words and numbers, the motion as calculated
    const panel = page.getByTestId('map-cells')
    await expect(panel.getByRole('heading', { level: 2 })).toHaveText(en.mapTool.layerCells)
    await expect(panel.getByTestId('map-cells-summary')).toHaveText('Thunderstorm cells in the latest scan: 4')
    const list = panel.getByRole('list', { name: en.mapTool.cellsListLabel })
    await expect(list.getByRole('listitem')).toHaveCount(4)
    await expect(list.getByRole('listitem').first()).toContainText('Cell 12')
    await expect(list.getByRole('listitem').first()).toContainText('Severity 3 (extreme)')
    await expect(list.getByRole('listitem').first()).toContainText('Moves east at 31 km/h (direction calculated)')
    await expect(panel.getByTestId('map-cells-scan')).toContainText('UTC')
    // each cell is told where it is, and is a button that centres the map on it
    await expect(list.getByRole('listitem').first()).toContainText('Position 51.30, 12.40')
    await expect(list.getByRole('button').first()).toHaveAccessibleDescription(en.mapTool.cellsCentreHint)
    // the credit of the data where the layer is shown: DWD, the product and the licence's terms
    const credit = panel.getByTestId('map-cells-credit')
    await expect(credit).toContainText('KONRAD3D radar product of the German Weather Service (DWD)')
    await expect(credit).toContainText('Source: Deutscher Wetterdienst')
    await expect(credit.getByRole('link', { name: /Creative Commons Attribution 4\.0/ })).toHaveAttribute('href', 'https://creativecommons.org/licenses/by/4.0/')
    // the legend says what the marks are
    const legend = page.getByTestId('map-legend')
    await expect(legend).toContainText(en.mapTool.cellsLegendMark)
    await expect(legend).toContainText(en.mapTool.cellsLegendArrow)
    expect(backend.unanswered).toEqual([])
  })

  test('say that the latest scan has none, and when it was, for an empty scan, which is the usual one', async ({ page, baseURL }) => {
    const backend = await open(page, baseURL!, '/map?cells=1', NO_CELLS)
    const panel = page.getByTestId('map-cells')
    await expect(panel.getByTestId('map-cells-summary')).toHaveText(en.mapTool.cellsNone)
    await expect(panel.getByTestId('map-cells-scan')).toContainText('UTC')
    await expect(panel.getByRole('list')).toHaveCount(0)
    await expect(page.locator('.leaflet-storm-cells-pane path')).toHaveCount(0)
    await expect(page.locator('.storm-cell-mark')).toHaveCount(0)
    // DWD is credited where the cells would be, an empty scan included
    await expect(panel.getByTestId('map-cells-credit')).toContainText('Source: Deutscher Wetterdienst')
    expect(backend.unanswered).toEqual([])
  })

  test('are an overlay of the measurements as well, and the address keeps both', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/map?layer=measured&cells=1', WITH_CELLS)
    await expect(page.getByTestId('map-count')).toHaveText('Stations shown: 12')
    await expect(page.locator('.leaflet-storm-cells-pane path')).toHaveCount(4)
    await expect(page.getByTestId('map-cells').getByRole('listitem')).toHaveCount(4)
    await openLayers(page)
    await expect(page.getByRole('switch', { name: en.mapTool.layerCells })).toBeChecked()
    await page.getByRole('switch', { name: en.mapTool.layerCells }).click()
    await expect(page.locator('.leaflet-storm-cells-pane path')).toHaveCount(0)
    await expect(page.getByTestId('map-cells')).toHaveCount(0)
    await expect(page).toHaveURL(/\/map\?layer=measured$/)
  })

  test('are switched on and off by the keyboard alone, and their list is in the tab order of the panel', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/map', WITH_CELLS)
    await expect(page.getByTestId('map-count')).toBeVisible()
    await page.getByTestId('map-layers-button').focus()
    await page.keyboard.press('Enter')
    const control = page.getByRole('switch', { name: en.mapTool.layerCells })
    await control.focus()
    await expect(control).toBeFocused()
    await page.keyboard.press('Space')
    await expect(control).toBeChecked()
    await expect(page.locator('.leaflet-storm-cells-pane path')).toHaveCount(4)
    // Escape closes the panel and gives the button its focus back
    await page.keyboard.press('Escape')
    await expect(page.getByTestId('map-layers-button')).toBeFocused()
    await expect(page.getByTestId('map-cells').getByRole('listitem')).toHaveCount(4)
  })

  test('ask for the scan again every 5 minutes while they are shown, and not once they are switched off', async ({ page, baseURL }) => {
    await page.clock.install({ time: new Date('2026-11-17T22:21:00Z') })
    const cells = counting(() => emptyScan(SCAN_OF_THE_CLOCK))
    await open(page, baseURL!, '/map?cells=1', cells.handlers)
    await expect(page.getByTestId('map-cells-summary')).toBeVisible()
    expect(cells.asked).toHaveLength(1)
    await page.clock.fastForward(4 * 60_000)
    await page.waitForTimeout(300)
    expect(cells.asked).toHaveLength(1)
    await page.clock.fastForward(61_000)
    await expect.poll(() => cells.asked.length).toBe(2)
    // switched off: no timer is left to ask
    await openLayers(page)
    await page.getByRole('switch', { name: en.mapTool.layerCells }).click()
    await page.clock.fastForward(20 * 60_000)
    await page.waitForTimeout(300)
    expect(cells.asked).toHaveLength(2)
  })

  test('are not asked for while the tab is in the background, and are as it comes back to a scan that is due', async ({ page, baseURL }) => {
    await page.clock.install({ time: new Date('2026-11-17T22:21:00Z') })
    const cells = counting(() => emptyScan(SCAN_OF_THE_CLOCK))
    await open(page, baseURL!, '/map?cells=1', cells.handlers)
    await expect(page.getByTestId('map-cells-summary')).toBeVisible()
    const visibility = (state: 'hidden' | 'visible') => page.evaluate((next) => {
      Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => next })
      document.dispatchEvent(new Event('visibilitychange'))
    }, state)
    await visibility('hidden')
    await page.clock.fastForward(30 * 60_000)
    await page.waitForTimeout(300)
    expect(cells.asked).toHaveLength(1)
    await visibility('visible')
    await expect.poll(() => cells.asked.length).toBe(2)
  })

  test('tell a scan that could not be loaded, and load it on Retry', async ({ page, baseURL }) => {
    let failing = true
    await open(page, baseURL!, '/map?cells=1', {
      'storm-cells': () => failing ? new ApiFailure(502, 'DWD did not answer') : exampleScan(),
    })
    const failed = page.getByTestId('map-cells-failed')
    await expect(failed).toHaveText(en.mapTool.cellsFailed)
    failing = false
    await page.getByTestId('map-cells-retry').click()
    await expect(page.getByTestId('map-cells').getByRole('listitem')).toHaveCount(4)
  })

  test('are told from the place picked, and a press on a cell centres the map on it, said in the status, with the focus on its row', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/map?cells=1&station=10384', WITH_CELLS)
    const panel = page.getByTestId('map-cells')
    await expect(panel.getByRole('listitem')).toHaveCount(4)
    // from Berlin-Tempelhof: the distance and the point of the compass
    await expect(panel.getByTestId('map-cells-location').first()).toHaveText(/^[\d,]+ km from the picked place, to the (south|west|north|east)/)
    await expect.poll(() => zoomOf(page)).toBe(8)
    // the cell 7, over Frankfurt, is the second: a press centres the map on it at a zoom that fits it (a town, 10 at most)
    const row = panel.getByRole('button').nth(1)
    await row.focus()
    await page.keyboard.press('Enter')
    await expect(page.getByTestId('map-announcement')).toHaveText('Map centred on cell 7')
    await expect(row).toBeFocused()
    await expect.poll(() => zoomOf(page)).toBeGreaterThanOrEqual(9)
    // the cell's outline is now over the middle of the map
    const map = (await page.getByRole('application', { name: /^Station map/ }).boundingBox())!
    await expect.poll(async () => {
      // the paths are in the order of the list: the second is the cell 7
      const box = (await page.locator('.leaflet-storm-cells-pane path').nth(1).boundingBox())
      return box ? Math.round(Math.abs(box.x + box.width / 2 - (map.x + map.width / 2))) : 9999
    }, { timeout: 5000 }).toBeLessThan(300)
  })

  test('take the cells of a scan that is out of date off the map, keep the list and say so', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/map?cells=1', { 'storm-cells': () => exampleScan(new Date(Date.now() - 3 * 3_600_000).toISOString().replace('Z', '000+00:00')) })
    await expect(page.getByTestId('map-cells').getByRole('listitem')).toHaveCount(4)
    await expect(page.getByTestId('map-cells-outdated')).toContainText('is out of date (over 20 minutes old)')
    await expect(page.locator('.leaflet-storm-cells-pane path')).toHaveCount(0)
    await expect(page.locator('.storm-cell-mark')).toHaveCount(0)
  })

  test('tell a stale scan, which makes an empty one no all-clear', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/map?cells=1', {
      'storm-cells': () => stormCellsAnswer([], { warnings: [{ code: 'scan-stale', message: 'old' }] }),
    })
    await expect(page.getByTestId('map-cells-stale')).toContainText('more than 20 minutes old')
  })
})

test.describe('the thunderstorm cells on a phone', () => {
  test.use({ viewport: { width: 390, height: 844 } })

  test('have their switch, their list under the map and their legend over it, and the page does not scroll sideways', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/map?cells=1', { 'storm-cells': () => exampleScan() })
    await expect(page.locator('.leaflet-storm-cells-pane path')).toHaveCount(4)
    await expect(page.getByTestId('map-cells').getByRole('listitem')).toHaveCount(4)
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
    expect(overflow).toBeLessThanOrEqual(0)
    // the legend is clear of the zoom buttons and of the layers button
    const rects = await page.evaluate(() => {
      const rect = (selector: string) => {
        const box = document.querySelector(selector)!.getBoundingClientRect()
        return { top: box.top, bottom: box.bottom, left: box.left, right: box.right }
      }
      return { legend: rect('.map-legend'), zoom: rect('.leaflet-control-zoom'), layers: rect('.map-layers-button') }
    })
    const apart = (a: { top: number, bottom: number, left: number, right: number }, b: typeof a) => a.bottom <= b.top || b.bottom <= a.top || a.right <= b.left || b.right <= a.left
    expect(apart(rects.legend, rects.zoom), 'the legend is clear of the zoom buttons').toBe(true)
    expect(apart(rects.legend, rects.layers), 'the legend is clear of the layers button').toBe(true)
    await openLayers(page)
    const control = page.getByRole('switch', { name: en.mapTool.layerCells })
    const height = await control.evaluate(element => (element.closest('[data-slot="root"]') as HTMLElement).offsetHeight)
    expectAtLeastPx(height, 44, 'the row of the switch is high')
  })
})

test.describe('the switch of the grouping on a phone', () => {
  test.use({ viewport: { width: 390, height: 844 } })

  test('has a row of 44 px, of which the label is the whole height, so that the row is the target', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/map', GROUPED)
    await expect(page.getByTestId('map-count-panel')).toBeVisible()
    const control = await groupingSwitch(page)
    await expect(control).toBeVisible()
    const heights = await page.evaluate(() => {
      const label = document.querySelector('label[for="map-grouping-switch"]')!
      // the layout's own heights: the panel is scaled while it opens, which `getBoundingClientRect` measures
      return { label: (label as HTMLElement).offsetHeight, row: (label.closest('[data-slot="root"]') as HTMLElement).offsetHeight }
    })
    expectAtLeastPx(heights.label, 44, 'the label is high')
    expectAtLeastPx(heights.row, 44, 'the row is high')
  })
})
