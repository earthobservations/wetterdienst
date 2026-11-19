import type { Page, Route } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { expect, test } from '@playwright/test'
import { defaultHandlers, mockBackend } from './accessibility/mock-backend'

// DESIGN PREVIEW for GH-4078, the second round (a commit of its own, removed again in the next one): the screenshots of the changes after
// the review, taken with a mocked API so that the layer renders without the live backend. The stations are the real ones of GHCN daily over
// central Europe (2,438 of them), the stripes the real ones of Hamburg-Fuhlsbüttel and of New York (Central Park), both read from the live
// backend on 2026-11-19.
// Run: A11Y=1 npx playwright test -c <a webkit config> tests/e2e/ghcn-preview-4078.spec.ts

const OUT = fileURLToPath(new URL('./preview-4078/', import.meta.url))
const read = (name: string) => JSON.parse(readFileSync(fileURLToPath(new URL(`./fixtures/${name}`, import.meta.url)), 'utf-8'))

// [id, name, latitude, longitude, elevation, first year, last year, WMO number]
const ROWS: Array<[string, string, number, number, number | null, number | null, number | null, string | null]> = read('ghcn-europe-preview-4078.json')
const STATIONS = ROWS.map(([station_id, name, latitude, longitude, elevation, from, to, wmo_id]) => ({
  resolution: 'daily',
  dataset: 'data',
  station_id,
  name,
  region: null,
  latitude,
  longitude,
  elevation,
  wmo_id,
  start_timestamp: from ? `${from}-01-01T00:00:00.000000+00:00` : null,
  end_timestamp: to ? `${to}-12-31T00:00:00.000000+00:00` : null,
}))
const HAMBURG_STRIPES = read('ghcn-hamburg-stripes-preview-4078.json')
const NEW_YORK_STRIPES = read('ghcn-newyork-stripes-preview-4078.json')
const HAMBURG = STATIONS.find(station => station.station_id === 'GM000010147')!
const NEW_YORK = NEW_YORK_STRIPES.series.station
STATIONS.push(NEW_YORK)

function backend() {
  const defaults = defaultHandlers()
  return {
    'stations': (url: URL, route: Route) => {
      if (url.searchParams.get('network') === 'mosmix') {
        const answer = defaults.stations!(url, route) as { stations: Array<{ station_id: string }> }
        // the forecast point of Hamburg carries its WMO number, as the backend's does: it is the same station
        return { stations: answer.stations.map(station => station.station_id === '10147' ? { ...station, wmo_id: '10147' } : station) }
      }
      if (url.searchParams.get('network') !== 'ghcn')
        return defaults.stations!(url, route)
      const wanted = url.searchParams.get('stations')?.split(',')
      if (wanted)
        return { stations: STATIONS.filter(station => wanted.includes(station.station_id)) }
      const [left, bottom, right, top] = ['left', 'bottom', 'right', 'top'].map(name => Number(url.searchParams.get(name))) as [number, number, number, number]
      return { stations: STATIONS.filter(station => station.longitude >= left && station.longitude <= right && station.latitude >= bottom && station.latitude <= top) }
    },
    'stripes/stations': () => ({ stations: [HAMBURG, NEW_YORK] }),
    'stripes/values': (url: URL, route: Route) => {
      if (url.searchParams.get('provider') !== 'noaa')
        return defaults['stripes/values']!(url, route)
      return url.searchParams.get('station') === NEW_YORK.station_id ? NEW_YORK_STRIPES : HAMBURG_STRIPES
    },
  }
}

async function open(page: Page, baseURL: string, path: string) {
  await page.context().addCookies([{ name: 'wd_lang', value: 'en', url: baseURL }])
  await mockBackend(page, baseURL, backend())
  // the map's tiles are OpenStreetMap's own, for the pictures
  await page.route(url => url.hostname.endsWith('tile.openstreetmap.org'), route => route.continue())
  await page.goto(path)
}

async function settle(page: Page) {
  // the dev server's own overlay (Nuxt DevTools) is no part of the picture
  await page.addStyleTag({ content: '#nuxt-devtools-container, [id^="nuxt-devtools"], .nuxt-devtools-vframe { display: none !important }' })
  await page.waitForTimeout(2500)
}

/** The map is drawn: on a phone the count is in the panel and not on the map, so the dots' canvas is what is waited for */
async function mapIsDrawn(page: Page) {
  await expect(page.locator('.station-map canvas').first()).toBeAttached()
  await expect(page.getByTestId('map-count-panel').or(page.getByTestId('map-count')).first()).toBeAttached()
}

/** Drags the map by a number of pixels, as a finger or a mouse does */
async function drag(page: Page, dx: number, dy: number) {
  const box = (await page.locator('.station-map').boundingBox())!
  const from = { x: box.x + box.width / 2, y: box.y + box.height / 2 }
  await page.mouse.move(from.x, from.y)
  await page.mouse.down()
  await page.mouse.move(from.x + dx / 2, from.y + dy / 2, { steps: 8 })
  await page.mouse.move(from.x + dx, from.y + dy, { steps: 8 })
  // held a moment before it lets go, so that the map does not glide on
  await page.waitForTimeout(250)
  await page.mouse.up()
}

const SIZES = [
  { name: 'desktop', viewport: { width: 1280, height: 1000 } },
  { name: 'phone', viewport: { width: 390, height: 844 } },
]

for (const size of SIZES) {
  test.describe(`${size.name} ${size.viewport.width}`, () => {
    test.use({ viewport: size.viewport, deviceScaleFactor: 2 })

    test('the stripes of a station of another country: its country in the title, the note in the saved image', async ({ page, baseURL }) => {
      await open(page, baseURL!, '/stripes?kind=temperature&provider=noaa&network=ghcn&station=USW00094728')
      await page.getByRole('button', { name: 'Show' }).click()
      await expect(page.getByTestId('stripes-method')).toBeVisible()
      await settle(page)
      await page.screenshot({ path: `${OUT}${size.name}-1-stripes-country.png`, fullPage: true })
      if (size.name === 'desktop') {
        // the saved image: its title names the country, and one line says how the temperature was made
        await page.getByRole('button', { name: 'Download image' }).click()
        const download = page.waitForEvent('download')
        await page.getByRole('menuitem', { name: /PNG/ }).click()
        await (await download).saveAs(`${OUT}saved-image-new-york.png`)
      }
    })

    test('a pick kept across layers: the forecast layer, the map moved away, then the GHCN layer', async ({ page, baseURL }) => {
      await open(page, baseURL!, '/map?station=10147')
      await expect(page.getByTestId('map-station-name')).toHaveText('HAMBURG-FUHLSBUETTEL')
      await mapIsDrawn(page)
      await page.waitForTimeout(1500)
      // the map moved to the east: the place picked is off the screen
      await drag(page, size.name === 'desktop' ? -380 : -200, 0)
      await page.waitForTimeout(600)
      await settle(page)
      await page.screenshot({ path: `${OUT}${size.name}-2-keep-before.png` })
      await page.getByTestId('map-layers-button').click()
      await page.getByTestId('map-layers-panel').getByRole('radio', { name: 'NOAA GHCN daily', exact: true }).click()
      await page.getByTestId('map-layers-button').click()
      await expect(page.getByTestId('map-station-name')).toHaveText('HAMBURG FUHLSBUETTEL')
      await settle(page)
      await page.screenshot({ path: `${OUT}${size.name}-3-keep-after.png` })
    })

    test('the hint to zoom in, at the cap of 200 square degrees: just under it the stations load, one step out they do not', async ({ page, baseURL }) => {
      await open(page, baseURL!, '/map?layer=ghcn')
      await mapIsDrawn(page)
      await settle(page)
      await page.screenshot({ path: `${OUT}${size.name}-4-under-the-cap.png` })
      await page.getByRole('button', { name: 'Zoom out' }).click()
      await expect(page.getByTestId('map-zoom-hint')).toBeVisible()
      await settle(page)
      await page.screenshot({ path: `${OUT}${size.name}-5-over-the-cap.png` })
    })
  })
}
