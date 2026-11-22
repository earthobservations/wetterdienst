import type { Handlers } from './accessibility/mock-backend'
import type { Locale, Mode, Variant } from './accessibility/scan'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { expect, test } from '@playwright/test'
import { exampleScan } from '../helpers/storm-cells-answer'
import { askHandlers } from './accessibility/ask-backend'
import { compareHandlers } from './accessibility/compare-backend'
import { scanHover, scanKeyboard } from './accessibility/interact'
import { ApiFailure, mockBackend } from './accessibility/mock-backend'
import { compareToBaseline, readBaseline, RECORDING, scan, variantKey } from './accessibility/scan'

// Accessibility, measured: every page, in light and dark and in two languages, scanned with axe
// against WCAG 2.2 level AA, and again in the states a first paint does not show -- a map with
// stations, a chart, a menu, an error. See ../../ACCESSIBILITY.md.
//
// The violations the app has today are in `accessibility/baseline.json`. A scan that finds a rule
// broken outside it fails, so the app cannot get worse; a scan that no longer finds one in it
// fails too, so that whoever fixes a violation takes its entry out and the baseline only shrinks.
//
// Nothing here reaches a provider, or the backend: `mockBackend` answers every `/api/*` request in
// the browser, and every other host with a transparent pixel or a refusal.
//
// The baseline is of the production build, which is what CI serves and what `pnpm test:a11y` builds
// (it sets CI=true): the dev server adds its own overlay.

const MODES: Mode[] = ['light', 'dark']
const LOCALES: Locale[] = ['en', 'de']
const VARIANTS: Variant[] = MODES.flatMap(mode => LOCALES.map(locale => ({ mode, locale })))

// the states are scanned in two variants that between them hold both modes and both languages:
// the pages' first paint takes all four, as it is cheap and where a contrast or a label differs
const STATE_VARIANTS = new Set(['light/en', 'dark/de'])

const catalogs: Record<Locale, unknown> = {
  en: JSON.parse(readFileSync(fileURLToPath(new URL('../../i18n/locales/en.json', import.meta.url)), 'utf-8')),
  de: JSON.parse(readFileSync(fileURLToPath(new URL('../../i18n/locales/de.json', import.meta.url)), 'utf-8')),
}

/** The text the app shows for `key` in `locale`, so a state is driven by the label a reader sees */
function message(locale: Locale, key: string): string {
  const text = key.split('.').reduce<unknown>((node, part) => (node as Record<string, unknown> | undefined)?.[part], catalogs[locale])
  if (typeof text !== 'string')
    throw new TypeError(`no message ${key} in ${locale}`)
  return text
}

type Page = import('@playwright/test').Page

interface Target {
  page: string
  path: string
  /** Waits for what the page is for to be on screen, where its heading is not enough */
  ready?: (page: Page, locale: Locale) => Promise<void>
}

/** The radar, with the reader's position given by a press of "Use my location" and marked on its map (GH-4287) */
async function showPosition(page: Page, locale: Locale, position: { latitude: number, longitude: number }) {
  await page.context().grantPermissions(['geolocation'])
  await page.context().setGeolocation(position)
  await expect(page.getByTestId('radar-newest')).toBeVisible()
  await expect(page.getByTestId('radar-cells-item').first()).toBeVisible()
  await page.getByRole('button', { name: message(locale, 'location.button') }).click()
  await expect(page.getByRole('img', { name: message(locale, 'radar.positionMarker') })).toHaveCount(1)
}

// every page of the app, as it is first shown
const PAGES: Target[] = [
  { page: 'index', path: '/' },
  { page: 'explorer', path: '/explorer' },
  { page: 'stripes', path: '/stripes' },
  { page: 'meteogram', path: '/meteogram' },
  { page: 'history', path: '/history' },
  {
    // the map tool (GH-3650): its chips, its map and its panel with the list of the stations
    page: 'map',
    path: '/map',
    // the list of stations is the panel's, at every width (the count over the map is not there on a phone)
    ready: async (page) => { await expect(page.getByTestId('map-list')).toBeVisible() },
  },
  {
    // the radar tool (GH-3788): the map with the radar over it, its player and legend, and the panel
    page: 'radar',
    path: '/radar',
    ready: async (page) => { await expect(page.getByTestId('radar-newest')).toBeVisible() },
  },
  {
    // the compare tool (GH-4296): the form, and the placeholder where the result will be
    page: 'compare',
    path: '/compare',
    ready: async (page, locale) => { await expect(page.getByRole('heading', { level: 1, name: message(locale, 'compare.title') })).toBeVisible() },
  },
  {
    page: 'widget',
    path: '/widget',
    // the widget has no heading: it says which parameter it lacks
    ready: (page, locale) => expect(page.getByText(message(locale, 'widget.noStation').split('{param}')[0]!.trim())).toBeVisible(),
  },
  {
    page: 'glossary',
    path: '/glossary',
    ready: async (page) => { await expect(page.getByText('Mean air temperature at 2 m height.').first()).toBeVisible() },
  },
  {
    page: 'measurement',
    path: '/measurement',
    ready: async (page, locale) => { await expect(page.getByRole('heading', { level: 1, name: message(locale, 'measurement.title') })).toBeVisible() },
  },
  {
    page: 'methods',
    path: '/methods',
    ready: async (page, locale) => { await expect(page.getByRole('heading', { level: 1, name: message(locale, 'methods.title') })).toBeVisible() },
  },
  {
    page: 'providers',
    path: '/providers',
    ready: async (page) => { await expect(page.getByRole('heading', { name: 'German Weather Service' })).toBeVisible() },
  },
  {
    page: 'provider',
    path: '/providers/dwd',
    ready: async (page) => { await expect(page.getByText('Source: Deutscher Wetterdienst')).toBeVisible() },
  },
  { page: 'api', path: '/api' },
  { page: 'settings', path: '/settings' },
  { page: 'about', path: '/about' },
  { page: 'support', path: '/support' },
  { page: 'impressum', path: '/impressum' },
  { page: 'datenschutz', path: '/datenschutz' },
]

interface State {
  page: string
  state: string
  path: string
  /** The answers of the backend that differ from the usual ones */
  handlers?: Handlers
  viewport?: { width: number, height: number }
  /** Brings the page to the state, from where `path` left it */
  reach: (page: Page, locale: Locale) => Promise<void>
  /** An open menu, popover or dialog that holds the focus: the keyboard scan walks on from there, not from the top of the page */
  keepFocus?: boolean
}

const EXPLORER = '/explorer?provider=dwd&network=observation&resolution=daily&dataset=climate_summary&parameters=temperature_air_max_2m,temperature_air_mean_2m&mode=station'
const EXPLORER_WITH_STATION = `${EXPLORER}&stations=00011`

/** The compare tool with a comparison a link names (GH-4296): two stations over a month, and one station over two months of two years */
const COMPARE_STATIONS = '/compare?compare=stations&resolution=daily&parameter=temperature_air_mean_2m&stations=00011,00044&startDate=2026-03-01&endDate=2026-03-31'
const COMPARE_PERIODS = '/compare?compare=periods&resolution=daily&parameter=temperature_air_mean_2m&stations=00011&periodA=2025-03-01/2025-03-31&periodB=2026-03-01/2026-03-31'

/** The explorer's chart (ECharts, drawn as SVG): its SVG is in the canvas once it has */
const explorerChart = (page: Page) => page.locator('.xc-canvas[data-drawn="true"] svg').first()
/** The stripes' chart (ECharts, drawn as SVG): its SVG is in the canvas once it has */
const stripesChart = (page: Page) => page.locator('.sc-canvas[data-drawn="true"] svg').first()

/** The forecast's chart (ECharts): its SVG is in the container once it has */
const forecastChart = (page: Page) => page.locator('.mg-canvas svg').first()

/** A map with markers: Leaflet puts one icon, or a cluster, in the page for each */
async function mapWithStations(page: Page) {
  await expect(page.locator('.leaflet-marker-icon').first()).toBeVisible()
}

/** The one station with climate stripes that the map tool's states have within reach of Berlin (the mock's are in the south and west) */
const STRIPES_NEAR_BERLIN: Handlers = {
  'stripes/stations': () => ({
    stations: [{ station_id: '00131', name: 'Angermünde', region: 'Brandenburg', latitude: 53.0301, longitude: 13.9951, start_timestamp: '1950-01-01T00:00:00+00:00', end_timestamp: `${new Date().getUTCFullYear() - 1}-12-31T00:00:00+00:00` }],
  }),
}

const STATES: State[] = [
  {
    page: 'explorer',
    state: 'selection-restored',
    path: EXPLORER_WITH_STATION,
    reach: async (page) => {
      await expect(page.getByText('Donaueschingen').first()).toBeVisible()
    },
  },
  {
    page: 'explorer',
    state: 'station-menu-open',
    keepFocus: true,
    path: EXPLORER,
    reach: async (page, locale) => {
      await page.getByText(message(locale, 'common.stationSearch')).click()
      await expect(page.getByRole('listbox').getByRole('option').first()).toBeVisible()
    },
  },
  {
    page: 'explorer',
    state: 'station-map',
    path: EXPLORER,
    reach: async (page, locale) => {
      await page.getByRole('radio', { name: message(locale, 'stationSelection.modeMap') }).click()
      await mapWithStations(page)
    },
  },
  {
    page: 'explorer',
    state: 'values-table',
    path: EXPLORER_WITH_STATION,
    reach: async (page, locale) => {
      await page.getByRole('button', { name: message(locale, 'common.fetch'), exact: true }).click()
      await expect(page.getByRole('table').first()).toBeVisible()
    },
  },
  {
    page: 'explorer',
    state: 'values-chart',
    path: EXPLORER_WITH_STATION,
    reach: async (page, locale) => {
      await page.getByRole('button', { name: message(locale, 'common.fetch'), exact: true }).click()
      await expect(page.getByRole('table').first()).toBeVisible()
      await page.getByRole('button', { name: message(locale, 'dataViewer.viewChart'), exact: true }).click()
      await expect(explorerChart(page)).toBeVisible()
    },
  },
  {
    page: 'explorer',
    state: 'values-error',
    path: EXPLORER_WITH_STATION,
    // a 4xx, which the app asks again for no more than a 5xx: the notice is up at once
    handlers: { values: () => new ApiFailure(422, 'The source does not carry these parameters for this station.') },
    reach: async (page, locale) => {
      await page.getByRole('button', { name: message(locale, 'common.fetch'), exact: true }).click()
      await expect(page.getByText(message(locale, 'dataViewer.fetchError')).first()).toBeVisible()
      // the notice in the table's place and the toast the error raises: both are the state, and the
      // toast comes a moment after
      const toast = page.locator('[data-slot="title"]', { hasText: message(locale, 'dataViewer.fetchErrorToastTitle') })
      await expect(toast).toBeVisible()
      // the toast closes after five seconds, which a slow scan could outlast: the pointer on it holds it open
      await toast.hover()
    },
  },
  {
    page: 'explorer',
    state: 'values-limit-refused',
    path: EXPLORER_WITH_STATION,
    // the problem of a limit, as the backend answers it: the page words its numbers itself (GH-3457)
    handlers: {
      values: () => new ApiFailure(400, 'This request would return about 614,866 rows, more than the 500,000 this server sends as one answer.', {
        type: 'urn:wetterdienst:problem:limit-exceeded',
        title: 'Bad Request',
        status: 400,
        limit: 'rows',
        maximum: 500_000,
        requested: 614_866,
      }),
    },
    reach: async (page, locale) => {
      await page.getByRole('button', { name: message(locale, 'common.fetch'), exact: true }).click()
      const notice = page.getByTestId('limit-notice')
      await expect(notice).toBeVisible()
      await expect(notice.getByRole('alert')).toBeVisible()
      await expect(page.getByTestId('limit-apply')).toBeVisible()
      await expect(page.getByTestId('limit-download')).toBeVisible()
      // a refusal raises no toast: it is a state of the table, not a failure
      await expect(page.locator('[data-slot="title"]', { hasText: message(locale, 'dataViewer.fetchErrorToastTitle') })).toHaveCount(0)
    },
  },
  {
    page: 'explorer',
    state: 'values-limit-refused-narrow',
    path: EXPLORER_WITH_STATION,
    viewport: { width: 320, height: 844 },
    handlers: {
      values: () => new ApiFailure(400, 'English', {
        type: 'urn:wetterdienst:problem:limit-exceeded',
        title: 'Bad Request',
        status: 400,
        limit: 'rows',
        maximum: 500_000,
        requested: 614_866,
      }),
    },
    reach: async (page, locale) => {
      await page.getByRole('button', { name: message(locale, 'common.fetch'), exact: true }).click()
      await expect(page.getByTestId('limit-apply')).toBeVisible()
      // the notice's text and buttons wrap, and none reaches past the screen (1.4.10): the page itself
      // is wider at 320 px where a station is chosen, which is the explorer's own and no concern of the notice
      const past = await page.evaluate(() => {
        const width = document.documentElement.clientWidth
        const notice = document.querySelector('[data-testid="limit-notice"]')!
        return [...notice.querySelectorAll('*')].filter(el => el.getBoundingClientRect().right > width + 1).map(el => el.tagName)
      })
      expect(past).toEqual([])
    },
  },
  {
    page: 'explorer',
    state: 'default-range-note',
    // twelve stations of hourly data from the 1960s on are millions of rows: the page starts a window that fits
    path: '/explorer?provider=dwd&network=observation&resolution=hourly&dataset=temperature_air&parameters=temperature_air_mean_2m,humidity&mode=station'
      + '&stations=00011,00044,00071,00073,00091,00096,00102,00125,00131,00183,00198,00205',
    reach: async (page) => {
      await expect(page.getByTestId('default-range-note')).not.toBeEmpty()
      await expect(page.getByTestId('clear-date-range')).toBeVisible()
    },
  },
  {
    page: 'history',
    state: 'histories-shown',
    path: '/history',
    reach: async (page, locale) => {
      await page.getByLabel(message(locale, 'parameterSelection.resolutionLabel')).click()
      await page.getByRole('option').first().click()
      await page.getByLabel(message(locale, 'parameterSelection.datasetLabel')).click()
      await page.getByRole('option').first().click()
      await page.getByText(message(locale, 'common.stationSearch')).click()
      await page.getByRole('option').first().click()
      // the station picker is a popover; its selection is made once it is closed
      await page.keyboard.press('Escape')
      await page.getByRole('button', { name: message(locale, 'common.fetch'), exact: true }).click()
      // the station's history itself, not the station picker that names it too
      await expect(page.getByText(`${message(locale, 'history.stationIdPrefix')}${message(locale, 'common.colon')} 00011`)).toBeVisible()
      // the choosing above scrolled the page to where the toggle of the station picker is half under the sticky header, which
      // axe reads as a target too small to press (target-size: "partially obscured"); the page as it is opened is at its top
      await page.evaluate(() => window.scrollTo(0, 0))
    },
  },
  {
    page: 'history',
    state: 'backend-lacks-provider',
    path: '/history',
    // the page is restricted to dwd/observation and says so where the backend has no dwd
    handlers: {
      providers: () => ({
        metadata: {
          api_version: '1',
          schema_version: '1',
          retrieved_at: '2026-10-17T10:00:00.000000+00:00',
          counts: { providers: 1, networks: 1, parameters: 8 },
          warnings: [],
        },
        providers: [{
          provider: 'noaa',
          name_short: 'NOAA',
          name_local: 'National Oceanic and Atmospheric Administration',
          name_english: 'National Oceanic and Atmospheric Administration',
          country: 'United States Of America',
          country_code: 'US',
          license: null,
          attribution: null,
          networks: [{
            network: 'ghcn',
            kind: 'observation',
            extent: { scope: 'global', continents: [], bbox: [-180, -90, 180, 90] },
            url: 'https://noaa-ghcn-pds.s3.amazonaws.com/csv.gz/by_station/',
            copyright: '© NOAA',
            auth: false,
            configured: true,
            date_required: false,
            parameters: 8,
          }],
        }],
      }),
    },
    reach: async (page) => {
      await expect(page.getByRole('main').locator('[role="alert"], .text-error').first()).toBeVisible()
    },
  },
  {
    page: 'stripes',
    state: 'station-map',
    path: '/stripes',
    reach: async (page, locale) => {
      await page.getByRole('radio', { name: message(locale, 'stationSelection.modeMap') }).click()
      await mapWithStations(page)
    },
  },
  {
    page: 'stripes',
    state: 'chart-drawn',
    path: '/stripes?kind=temperature&station=00011',
    reach: async (page, locale) => {
      await page.getByRole('button', { name: message(locale, 'common.fetch'), exact: true }).click()
      await expect(stripesChart(page)).toBeVisible()
    },
  },
  {
    page: 'stripes',
    state: 'download-menu-open',
    keepFocus: true,
    path: '/stripes?kind=temperature&station=00011',
    reach: async (page, locale) => {
      await page.getByRole('button', { name: message(locale, 'common.fetch'), exact: true }).click()
      await expect(stripesChart(page)).toBeVisible()
      await page.getByRole('button', { name: message(locale, 'stripes.downloadImage') }).click()
      await expect(page.getByRole('menuitem').first()).toBeVisible()
    },
  },
  {
    page: 'stripes',
    state: 'fetch-error',
    path: '/stripes?kind=temperature&station=00011',
    handlers: { 'stripes/values': () => new ApiFailure(422, 'This station has no complete years.') },
    reach: async (page, locale) => {
      await page.getByRole('button', { name: message(locale, 'common.fetch'), exact: true }).click()
      await expect(page.getByText('This station has no complete years.').first()).toBeVisible()
    },
  },
  {
    page: 'meteogram',
    state: 'chart-drawn',
    path: '/meteogram?station=01001',
    reach: async (page) => {
      await expect(forecastChart(page)).toBeVisible()
    },
  },
  {
    // the readout the keys open, with the focus on the chart (the ring is drawn, the readout lies over the panels)
    page: 'meteogram',
    state: 'readout-shown',
    keepFocus: true,
    path: '/meteogram?station=01001',
    reach: async (page) => {
      await expect(forecastChart(page)).toBeVisible()
      await page.getByRole('figure').focus()
      await page.keyboard.press('ArrowRight')
      await expect(page.getByTestId('meteogram-readout')).toBeVisible()
    },
  },
  {
    // a phone's window, which opens on the day cards: the chart is asked for, and the strip scrolls under its axes
    page: 'meteogram',
    state: 'chart-phone',
    path: '/meteogram?station=01001&view=chart',
    viewport: { width: 390, height: 844 },
    reach: async (page) => {
      await expect(forecastChart(page)).toBeVisible()
      await page.getByTestId('meteogram-scroller').evaluate((element) => {
        element.scrollLeft = 200
      })
    },
  },
  {
    page: 'stripes',
    state: 'table-shown',
    path: '/stripes?kind=temperature&station=00011',
    reach: async (page, locale) => {
      await page.getByRole('button', { name: message(locale, 'common.fetch'), exact: true }).click()
      await expect(stripesChart(page)).toBeVisible()
      // the table is a view of the stripes' switch (GH-4233)
      await page.getByRole('radio', { name: message(locale, 'stripes.variant.table'), exact: true }).click()
      await expect(page.getByRole('table')).toBeVisible()
    },
  },
  {
    page: 'meteogram',
    state: 'table-shown',
    path: '/meteogram?station=01001',
    reach: async (page, locale) => {
      await expect(forecastChart(page)).toBeVisible()
      await page.getByRole('radio', { name: message(locale, 'meteogram.chart.viewTable'), exact: true }).click()
      await expect(page.getByRole('table')).toBeVisible()
    },
  },
  {
    page: 'meteogram',
    state: 'table-view-linked',
    path: '/meteogram?station=01001&view=table',
    reach: async (page) => {
      await expect(page.getByRole('table')).toBeVisible()
    },
  },
  {
    page: 'widget',
    state: 'table-shown',
    path: '/widget?station=01001',
    reach: async (page, locale) => {
      await expect(forecastChart(page)).toBeVisible()
      await page.getByRole('button', { name: message(locale, 'dataViewer.viewTable'), exact: true }).click()
      await expect(page.getByRole('table')).toBeVisible()
    },
  },
  {
    page: 'meteogram',
    state: 'compact-view',
    path: '/meteogram?station=01001&compact=true',
    // the day cards, which are not controls and still change their colours under the pointer
    reach: async (page, locale) => {
      await expect(page.getByText(message(locale, 'meteogram.chart.today')).first()).toBeVisible()
    },
  },
  {
    page: 'meteogram',
    state: 'station-menu-open',
    keepFocus: true,
    path: '/meteogram',
    reach: async (page, locale) => {
      await page.getByText(message(locale, 'common.stationSearch')).click()
      await expect(page.getByRole('listbox').getByRole('option').first()).toBeVisible()
    },
  },
  {
    page: 'meteogram',
    state: 'station-map',
    path: '/meteogram',
    reach: async (page, locale) => {
      await page.getByRole('radio', { name: message(locale, 'stationSelection.modeMap') }).click()
      await mapWithStations(page)
    },
  },
  {
    page: 'meteogram',
    state: 'forecast-error',
    path: '/meteogram?station=01001',
    handlers: { values: () => new ApiFailure(422, 'No forecast is issued for this station.') },
    reach: async (page) => {
      await expect(page.getByText(/No forecast is issued for this station\./).first()).toBeVisible()
    },
  },
  {
    page: 'widget',
    state: 'chart-drawn',
    path: '/widget?station=01001',
    reach: async (page) => {
      await expect(forecastChart(page)).toBeVisible()
    },
  },
  {
    page: 'index',
    state: 'settings-popover-open',
    keepFocus: true,
    path: '/',
    reach: async (page, locale) => {
      await page.getByRole('button', { name: message(locale, 'common.settings'), exact: true }).click()
      await expect(page.getByRole('dialog')).toBeVisible()
    },
  },
  {
    page: 'index',
    state: 'mobile-menu-open',
    keepFocus: true,
    path: '/',
    viewport: { width: 390, height: 844 },
    reach: async (page, locale) => {
      await page.getByRole('button', { name: message(locale, 'header.menu'), exact: true }).click()
      await expect(page.getByRole('navigation').last()).toBeVisible()
    },
  },
  {
    // the reference of the wide header, a disclosure of links (GH-3518)
    page: 'index',
    state: 'reference-open',
    path: '/',
    reach: async (page, locale) => {
      await page.getByRole('button', { name: message(locale, 'shell.reference'), exact: true }).click()
      await expect(page.getByRole('link', { name: new RegExp(message(locale, 'nav.glossary')) }).first()).toBeVisible()
    },
  },
  {
    // the search of the header, a dialog with a list of every place (GH-3518)
    page: 'index',
    state: 'search-open',
    keepFocus: true,
    path: '/',
    reach: async (page, locale) => {
      await page.getByRole('button', { name: message(locale, 'shell.search') }).click()
      await expect(page.getByRole('dialog')).toBeVisible()
      await expect(page.getByRole('option').first()).toBeVisible()
    },
  },
  {
    // the search with a query typed: the pages and providers it matches, and the forecast stations the backend found
    page: 'index',
    state: 'search-results',
    keepFocus: true,
    path: '/',
    reach: async (page, locale) => {
      // the shortcut is the app's: it listens once the page has been drawn
      await expect(page.getByRole('heading', { level: 1 }).first()).toBeVisible()
      await page.keyboard.press('Control+k')
      await expect(page.getByRole('combobox', { name: message(locale, 'shell.search') })).toBeFocused()
      await page.keyboard.type('ber')
      // the station of the forecast's points, in the group of its network (GH-3790)
      await expect(page.getByRole('option', { name: /BERLIN-TEMPELHOF/ }).first()).toBeVisible()
      await page.keyboard.press('ArrowDown')
    },
  },
  {
    // stations of three networks found by name (GH-3790): a group for each of the forecast's points, DWD's measuring stations and NOAA GHCN daily,
    // each result with its provider and network, and the last option of the group that has more than it shows, which leads to the map's search
    page: 'index',
    state: 'search-stations',
    keepFocus: true,
    path: '/',
    reach: async (page, locale) => {
      await expect(page.getByRole('heading', { level: 1 }).first()).toBeVisible()
      // DWD's measuring stations are a list of the search that a reader turns on (the setting is kept in the browser)
      await page.evaluate(() => localStorage.setItem('wd_settings', JSON.stringify({ version: 2, searchStations: { forecast: true, measured: true, ghcn: true } })))
      await page.reload()
      // the shortcut is the app's: it listens once the page has been drawn
      await expect(page.getByRole('heading', { level: 1 }).first()).toBeVisible()
      await page.keyboard.press('Control+k')
      await expect(page.getByRole('combobox', { name: message(locale, 'shell.search') })).toBeFocused()
      await page.keyboard.type('hamburg')
      await expect(page.getByRole('group', { name: message(locale, 'shell.stationsGhcn'), exact: true })).toBeVisible()
      await expect(page.getByRole('group', { name: message(locale, 'shell.stationsMeasured'), exact: true })).toBeVisible()
      await expect(page.getByRole('group', { name: message(locale, 'shell.stationsForecast'), exact: true })).toBeVisible()
      await page.keyboard.press('ArrowDown')
    },
  },
  {
    // a WMO number typed in (GH-3790): the stations of the lists that have it, and the option that asks every network for it; run, the stations
    // of four networks in a group of their own, one of them leading to the Explorer
    page: 'index',
    state: 'search-station-ids',
    keepFocus: true,
    path: '/',
    reach: async (page, locale) => {
      await expect(page.getByRole('heading', { level: 1 }).first()).toBeVisible()
      await page.keyboard.press('Control+k')
      await expect(page.getByRole('combobox', { name: message(locale, 'shell.search') })).toBeFocused()
      await page.keyboard.type('10381')
      const option = page.getByRole('option', { name: message(locale, 'shell.searchAllNetworks').replace('{id}', '10381') })
      await expect(option).toBeVisible()
      await page.keyboard.press('Enter')
      await expect(page.getByRole('group', { name: message(locale, 'shell.stationsWithId').replace('{id}', '10381'), exact: true })).toBeVisible()
      await expect(page.getByRole('option', { name: /AEMET/ })).toBeVisible()
    },
  },
  {
    // the search with words of the app typed (GH-3790): the groups of the entries, the glossary, the settings and the questions, each with its
    // few results and the option that leads on; "temp" is in a word of every language (the glossary is found by the English names as well)
    page: 'index',
    state: 'search-words',
    keepFocus: true,
    path: '/',
    reach: async (page, locale) => {
      await expect(page.getByRole('heading', { level: 1 }).first()).toBeVisible()
      await page.keyboard.press('Control+k')
      await expect(page.getByRole('combobox', { name: message(locale, 'shell.search') })).toBeFocused()
      await page.keyboard.type('temp')
      await expect(page.getByRole('group', { name: message(locale, 'glossary.title'), exact: true })).toBeVisible()
      await expect(page.getByRole('group', { name: message(locale, 'measurement.title'), exact: true })).toBeVisible()
      await page.keyboard.press('ArrowDown')
    },
  },
  {
    // a position typed into the search: a place that leads to the map, before every other group (GH-3790)
    page: 'index',
    state: 'search-place',
    keepFocus: true,
    path: '/',
    reach: async (page, locale) => {
      await expect(page.getByRole('heading', { level: 1 }).first()).toBeVisible()
      await page.keyboard.press('Control+k')
      await expect(page.getByRole('combobox', { name: message(locale, 'shell.search') })).toBeFocused()
      await page.keyboard.type('52.52, 13.40')
      await expect(page.getByRole('option', { name: /52\.5200, 13\.4000/ })).toBeVisible()
    },
  },
  {
    // the compare tool with two stations compared (GH-4296): the chart with both series, the summary, the table with its difference column, the credit
    page: 'compare',
    state: 'stations-result',
    path: COMPARE_STATIONS,
    handlers: compareHandlers(),
    reach: async (page) => {
      await expect(page.getByTestId('compare-table')).toBeVisible()
      await expect(explorerChart(page)).toBeVisible()
    },
  },
  {
    // two periods of one station, aligned by their place in the period, and the note that says so
    page: 'compare',
    state: 'periods-result',
    path: COMPARE_PERIODS,
    handlers: compareHandlers(),
    reach: async (page) => {
      await expect(page.getByTestId('compare-table')).toBeVisible()
      await expect(explorerChart(page)).toBeVisible()
    },
  },
  {
    // the two sides are not the same kind of number: the tool says so and has no table
    page: 'compare',
    state: 'refused',
    path: COMPARE_PERIODS,
    handlers: {
      ...compareHandlers(),
      values: (url) => {
        const later = (url.searchParams.get('timestamp') ?? '').startsWith('2026')
        return { metadata: { parameters: [{ resolution: 'daily', dataset: 'climate_summary', name: 'temperature_air_mean_2m', name_original: 'tmk', description: null, quantity: 'temperature', unit: later ? 'K' : '°C', aggregation: 'mean', timestamp_position: 'start' }] }, values: [] }
      },
    },
    reach: async (page) => {
      await expect(page.getByTestId('compare-refused')).toBeVisible()
    },
  },
  {
    // on a phone: the form, then the result, in one column
    page: 'compare',
    state: 'phone-result',
    path: COMPARE_STATIONS,
    viewport: { width: 390, height: 844 },
    handlers: compareHandlers(),
    reach: async (page) => {
      await expect(page.getByTestId('compare-table')).toBeVisible()
      await expect(explorerChart(page)).toBeVisible()
    },
  },
  {
    // the two new questions of Ask the weather (GH-4296): the answer with its chart and the link into the Compare tool
    page: 'index',
    state: 'ask-monthrain',
    path: '/?ask=monthrain',
    handlers: askHandlers(),
    reach: async (page) => {
      await expect(page.getByTestId('answer-verdict')).toBeVisible()
    },
  },
  {
    page: 'index',
    state: 'ask-nearby',
    path: '/?ask=nearby',
    handlers: askHandlers(),
    reach: async (page) => {
      await expect(page.getByTestId('answer-verdict')).toBeVisible()
    },
  },
  {
    // Ask the weather (GH-3518): a question open, with its verdict, its bars and the links into the tools
    page: 'index',
    state: 'ask-answer-open',
    path: '/?ask=rain',
    handlers: askHandlers(),
    reach: async (page) => {
      await expect(page.getByTestId('answer-verdict')).toBeVisible()
    },
  },
  {
    // the summer question: bars that hang from a line, the one asked about marked, the table of values opened
    page: 'index',
    state: 'ask-summer-values',
    path: '/?ask=summer',
    handlers: askHandlers(),
    reach: async (page, locale) => {
      await expect(page.getByTestId('answer-verdict')).toBeVisible()
      await page.getByText(message(locale, 'ask.showValues'), { exact: true }).click()
      await expect(page.getByRole('table')).toBeVisible()
    },
  },
  {
    // the explanation under an answer (GH-3764): "How was this worked out?" opened, with the marks of what is wetterdienst's own, the sources and the links
    page: 'index',
    state: 'ask-explanation-open',
    path: '/?ask=summer',
    handlers: askHandlers(),
    reach: async (page) => {
      await expect(page.getByTestId('answer-verdict')).toBeVisible()
      await page.getByTestId('explanation-button').click()
      await expect(page.getByTestId('explanation-rules')).toBeVisible()
    },
  },
  {
    // the season question with its choices (GH-3764, step 2a): the season and the normal as labelled selects, a winter against 1961-1990, the
    // disclosure opened so that what it says of the choice is scanned too
    page: 'index',
    state: 'ask-season-choices',
    path: '/?ask=season&season=winter&ref=1961-1990',
    handlers: askHandlers(),
    reach: async (page, locale) => {
      await expect(page.getByTestId('answer-verdict')).toBeVisible()
      await expect(page.getByRole('combobox', { name: message(locale, 'ask.season.seasonLabel') })).toBeVisible()
      await expect(page.getByRole('combobox', { name: message(locale, 'ask.season.refLabel') })).toBeVisible()
      await page.getByTestId('explanation-button').click()
      await expect(page.getByTestId('explanation-rules')).toBeVisible()
    },
  },
  {
    // the same on a phone, at a station that has too few winters of 1961-1990: the normal is offered disabled with the reason, and the answer says why there is none
    page: 'index',
    state: 'ask-season-disabled-phone',
    path: '/?ask=season&season=winter&ref=1961-1990&place=00183',
    viewport: { width: 390, height: 844 },
    handlers: askHandlers(),
    reach: async (page, locale) => {
      await expect(page.getByTestId('place-button')).toContainText('Arkona')
      await expect(page.getByRole('combobox', { name: message(locale, 'ask.season.refLabel') }).locator('option').first()).toBeDisabled()
      await expect(page.getByTestId('answer')).toContainText('16')
    },
  },
  {
    // a season the station has too little of is greyed out with the reason in its text, and the line under the choices says why (a link that names it)
    page: 'index',
    state: 'ask-season-greyed-season',
    path: '/?ask=season&season=winter&place=00205',
    handlers: askHandlers(),
    reach: async (page, locale) => {
      await expect(page.getByTestId('place-button')).toContainText('Aue')
      await expect(page.getByRole('combobox', { name: message(locale, 'ask.season.seasonLabel') }).locator('option[disabled]')).toHaveCount(1)
      await expect(page.getByTestId('choice-note')).not.toHaveText('')
      await expect(page.getByTestId('answer-verdict')).toBeVisible()
    },
  },
  {
    // the day question with its measure (GH-3764, step 2b): the measure and the day as labelled controls, a sunny-or-dull day, the disclosure opened
    // so that the rules of the measure, their sources and the marks of what is wetterdienst's own are scanned too
    page: 'index',
    state: 'ask-day-choices',
    path: '/?ask=day&measure=sun&day=2025-12-26',
    handlers: askHandlers(),
    reach: async (page, locale) => {
      await expect(page.getByTestId('answer-verdict')).toBeVisible()
      await expect(page.getByRole('combobox', { name: message(locale, 'ask.day.measureLabel') })).toBeVisible()
      await page.getByTestId('explanation-button').click()
      await expect(page.getByTestId('explanation-rules')).toBeVisible()
    },
  },
  {
    // the temperature of a day: bars that hang from a line (a frost day has negative minima around it), with the classes the day counts as
    page: 'index',
    state: 'ask-day-temperature',
    path: '/?ask=day&measure=temperature&day=2025-12-26',
    handlers: askHandlers(),
    reach: async (page, locale) => {
      await expect(page.getByTestId('answer-verdict')).toBeVisible()
      await expect(page.getByRole('combobox', { name: message(locale, 'ask.day.measureLabel') })).toBeVisible()
      await page.getByText(message(locale, 'ask.showValues'), { exact: true }).click()
      await expect(page.getByRole('table')).toBeVisible()
    },
  },
  {
    // a phone, at a station that has no snow reading: the snow measure is offered disabled with the reason in its option, and the line under the choices says why
    page: 'index',
    state: 'ask-day-greyed-phone',
    path: '/?ask=day&day=2025-12-26&place=00183',
    viewport: { width: 390, height: 844 },
    handlers: askHandlers(),
    reach: async (page, locale) => {
      await expect(page.getByTestId('place-button')).toContainText('Arkona')
      await expect(page.getByRole('combobox', { name: message(locale, 'ask.day.measureLabel') }).locator('option[disabled]')).toHaveCount(1)
      await expect(page.getByTestId('choice-note')).not.toHaveText('')
      await expect(page.getByTestId('answer-verdict')).toBeVisible()
    },
  },
  {
    // the search of a place of the questions, with a name typed
    page: 'index',
    state: 'ask-place-open',
    keepFocus: true,
    path: '/',
    handlers: askHandlers(),
    reach: async (page) => {
      await page.getByTestId('place-button').click()
      await page.getByRole('combobox').fill('ar')
      await expect(page.getByRole('option').first()).toBeVisible()
    },
  },
  {
    // the tab bar of the narrow layout, on a tool's page
    page: 'stripes',
    state: 'tab-bar',
    path: '/stripes',
    viewport: { width: 390, height: 844 },
    reach: async (page, locale) => {
      await expect(page.getByRole('navigation').getByRole('link', { name: message(locale, 'nav.stripes') })).toHaveAttribute('aria-current', 'page')
    },
  },
  {
    // a place picked on the map tool: the forecast's day rows, the stripes and the links to the measurements (GH-3650)
    page: 'map',
    state: 'station-picked',
    path: '/map?station=10384&lat=52.9&lon=13.0',
    handlers: STRIPES_NEAR_BERLIN,
    reach: async (page) => {
      await expect(page.getByTestId('map-card-forecast').getByTestId('day-rows')).toBeVisible()
      await expect(page.getByTestId('map-card-stripes').getByRole('img')).toBeVisible()
      await expect(page.getByTestId('map-card-measured').getByRole('link').first()).toBeVisible()
    },
  },
  {
    // the layer of the measurements, with the choices of its resolution and dataset, in the panel of the layers button (GH-4209)
    page: 'map',
    state: 'measured-layer',
    path: '/map?layer=measured',
    reach: async (page) => {
      await expect(page.getByTestId('map-count')).toBeVisible()
      await page.getByTestId('map-layers-button').click()
      await expect(page.getByTestId('map-grouping')).toBeVisible()
      await expect(page.getByTestId('map-resolution')).toBeVisible()
      await expect(page.getByTestId('map-dataset')).toBeVisible()
    },
  },
  {
    // the stations that could not be loaded
    page: 'map',
    state: 'stations-failed',
    path: '/map',
    handlers: { stations: () => new ApiFailure(500, 'The forecast stations are not available') },
    reach: async (page) => {
      await expect(page.getByTestId('map-failure')).toBeVisible()
    },
  },
  {
    // on a phone: the map first and the panel under it as a sheet, with a station picked
    page: 'map',
    state: 'phone-station-picked',
    path: '/map?station=10384&lat=52.9&lon=13.0',
    handlers: STRIPES_NEAR_BERLIN,
    viewport: { width: 390, height: 844 },
    reach: async (page) => {
      await expect(page.getByTestId('map-card-forecast').getByTestId('day-rows')).toBeVisible()
      await expect(page.getByTestId('map-card-stripes').getByRole('img')).toBeVisible()
      await expect(page.getByTestId('map-card-measured').getByRole('link').first()).toBeVisible()
    },
  },
  {
    // on a phone, the map full screen (GH-4227): the browser's own where it has the API, the app covering the page where it has
    // not; either way the map, its buttons and the sheet that stands in for the panel are all there is of the page
    page: 'map',
    state: 'phone-fullscreen',
    path: '/map?station=10384&lat=52.9&lon=13.0',
    viewport: { width: 390, height: 844 },
    reach: async (page) => {
      await expect(page.getByTestId('map-fullscreen')).toBeVisible()
      await page.getByTestId('map-fullscreen').click()
      await expect(page.getByTestId('map-sheet')).toBeVisible()
      await expect(page.getByTestId('map-sheet-name')).toBeVisible()
    },
  },
  {
    // the radar with the thunderstorm cells drawn and listed, the loop paused on a frame of the forecast (GH-3788)
    page: 'radar',
    state: 'cells-forecast-frame',
    path: '/radar',
    handlers: { 'storm-cells': () => exampleScan() },
    reach: async (page) => {
      await expect(page.getByTestId('radar-newest')).toBeVisible()
      await expect(page.getByTestId('radar-cells-item').first()).toBeVisible()
      await page.getByTestId('radar-slider').focus()
      await page.keyboard.press('End')
      await expect(page.getByTestId('radar-kind')).toHaveAttribute('data-kind', 'forecast')
    },
  },
  {
    // on a phone: the map first, then the player and the legend, then the panel (GH-3788)
    page: 'radar',
    state: 'phone-radar',
    path: '/radar',
    viewport: { width: 390, height: 844 },
    handlers: { 'storm-cells': () => exampleScan() },
    reach: async (page) => {
      await expect(page.getByTestId('radar-newest')).toBeVisible()
      await expect(page.getByTestId('radar-cells-item').first()).toBeVisible()
    },
  },
  {
    // the radar with the reader's own position marked over the picture and the cells, centred on (GH-4287): the marker, its name, the status and the button that hides it
    page: 'radar',
    state: 'position-shown',
    path: '/radar',
    handlers: { 'storm-cells': () => exampleScan() },
    reach: async (page, locale) => {
      await showPosition(page, locale, { latitude: 51.34, longitude: 12.37 })
      await expect(page.getByTestId('radar-position-toggle')).toBeVisible()
    },
  },
  {
    // the same on a phone, where the map is over the panel and comes into view
    page: 'radar',
    state: 'phone-position-shown',
    path: '/radar',
    viewport: { width: 390, height: 844 },
    handlers: { 'storm-cells': () => exampleScan() },
    reach: async (page, locale) => {
      await showPosition(page, locale, { latitude: 51.34, longitude: 12.37 })
      await expect(page.getByTestId('radar-position-toggle')).toBeVisible()
    },
  },
  {
    // a position outside the radar's area: told in the status, no marker, the map where it was (GH-4287)
    page: 'radar',
    state: 'position-outside',
    path: '/radar',
    reach: async (page, locale) => {
      await page.context().grantPermissions(['geolocation'])
      await page.context().setGeolocation({ latitude: 40.4168, longitude: -3.7038 })
      await expect(page.getByTestId('radar-newest')).toBeVisible()
      await page.getByRole('button', { name: message(locale, 'location.button') }).click()
      await expect(page.getByTestId('use-my-location-status')).toHaveText(message(locale, 'radar.positionOutside'))
    },
  },
  {
    // on a phone, the "About" of a tool as the ⓘ beside the title, open (GH-4227)
    page: 'explorer',
    state: 'phone-about-open',
    path: '/explorer',
    viewport: { width: 390, height: 844 },
    reach: async (page) => {
      await page.getByTestId('page-info').click()
      await expect(page.locator('.page-about')).toBeVisible()
    },
  },
  {
    // the page scrolled down on a phone, with both bars slid away (GH-4226): what the bars do not draw is not scanned as drawn, and
    // the page under where they were is clear of them
    page: 'about',
    state: 'phone-bars-hidden',
    path: '/about',
    viewport: { width: 390, height: 844 },
    reach: async (page, locale) => {
      await expect(page.getByRole('heading', { level: 1 }).first()).toBeVisible()
      await expect(page.getByRole('button', { name: message(locale, 'shell.search') })).toBeEnabled()
      // the reader's first input, then their scroll: the bars hide for no other
      await page.mouse.move(200, 400)
      await page.mouse.wheel(0, 1)
      await page.evaluate(() => window.scrollTo({ top: 600, behavior: 'instant' }))
      await expect(page.locator('html')).toHaveAttribute('data-bars', 'hidden')
      // the slide is over
      await expect.poll(async () => (await page.locator('.app-header').boundingBox())!.y).toBeLessThanOrEqual(-44)
    },
  },
  {
    // the search on a phone (GH-4226): a bar at the top of the window, over the top bar, with its results under it
    page: 'index',
    state: 'phone-search-open',
    keepFocus: true,
    path: '/',
    viewport: { width: 390, height: 844 },
    reach: async (page, locale) => {
      await page.getByRole('button', { name: message(locale, 'shell.search') }).click()
      await expect(page.getByRole('dialog')).toBeVisible()
      await expect(page.getByRole('option').first()).toBeVisible()
      // it has stopped opening
      await expect.poll(async () => Math.round((await page.getByRole('dialog').boundingBox())!.x)).toBe(0)
    },
  },
  {
    // the search on a phone with words of the app typed (GH-3790): the groups under the bar at the top, on the narrow layout
    page: 'index',
    state: 'phone-search-words',
    keepFocus: true,
    path: '/',
    viewport: { width: 390, height: 844 },
    reach: async (page, locale) => {
      await page.getByRole('button', { name: message(locale, 'shell.search') }).click()
      await expect(page.getByRole('dialog')).toBeVisible()
      await page.keyboard.type('temp')
      await expect(page.getByRole('group', { name: message(locale, 'glossary.title'), exact: true })).toBeVisible()
      await expect.poll(async () => Math.round((await page.getByRole('dialog').boundingBox())!.x)).toBe(0)
    },
  },
  {
    // the stations found by name on a phone (GH-3790): the groups of the three networks under the bar at the top
    page: 'index',
    state: 'phone-search-stations',
    keepFocus: true,
    path: '/',
    viewport: { width: 390, height: 844 },
    reach: async (page, locale) => {
      // DWD's measuring stations are a list of the search that a reader turns on (the setting is kept in the browser)
      await page.evaluate(() => localStorage.setItem('wd_settings', JSON.stringify({ version: 2, searchStations: { forecast: true, measured: true, ghcn: true } })))
      await page.reload()
      // the shortcut is the app's: it listens once the page has been drawn
      await expect(page.getByRole('heading', { level: 1 }).first()).toBeVisible()
      await page.getByRole('button', { name: message(locale, 'shell.search') }).click()
      await expect(page.getByRole('dialog')).toBeVisible()
      await page.keyboard.type('hamburg')
      await expect(page.getByRole('group', { name: message(locale, 'shell.stationsGhcn'), exact: true })).toBeVisible()
      await expect.poll(async () => Math.round((await page.getByRole('dialog').boundingBox())!.x)).toBe(0)
    },
  },
  {
    // the lists of stations the search looks in by name (GH-3790): a group of three checkboxes under a heading the search leads to; DWD's measuring
    // stations turned on, which is a change from the defaults (the forecast's points and GHCN daily on)
    page: 'settings',
    state: 'search-stations-setting',
    path: '/settings#settings-search-stations',
    reach: async (page, locale) => {
      await expect(page.locator('#settings-search-stations')).toBeFocused()
      await page.getByRole('checkbox', { name: message(locale, 'mapTool.layerMeasured') }).click()
      await expect(page.getByRole('checkbox', { name: message(locale, 'mapTool.layerMeasured') })).toBeChecked()
    },
  },
  {
    // the chooser of the phone bar's four tools (GH-3846): the preview, the two lists with their line, the handles and
    // the arrow buttons, at a phone's width and at 320 px, with the choice changed so that the list is not the default
    page: 'settings',
    state: 'phone-bar-chooser',
    path: '/settings#bar',
    viewport: { width: 390, height: 844 },
    reach: async (page) => {
      await expect(page.getByTestId('bar-chooser')).toBeVisible()
      await page.getByTestId('bar-chooser').locator('li[data-tool="map"] button[data-dir="up"]').click()
      await expect(page.getByTestId('bar-status')).not.toHaveText('')
    },
  },
  {
    page: 'settings',
    state: 'phone-bar-chooser-narrow',
    path: '/settings#bar',
    viewport: { width: 320, height: 844 },
    reach: async (page) => {
      await expect(page.getByTestId('bar-chooser')).toBeVisible()
    },
  },
]

/** Opens `path` and waits until the app, in this variant, has taken the page up */
async function open(page: Page, path: string, variant: Variant) {
  await page.goto(path)
  await expect(page.locator('html')).toHaveAttribute('lang', variant.locale)
  // a scan in the wrong colours would record a baseline of the wrong page
  if (variant.mode === 'dark')
    await expect(page.locator('html')).toHaveClass(/dark/)
  else
    await expect(page.locator('html')).not.toHaveClass(/dark/)
}

const baseline = readBaseline()

// beyond what axe finds in a page at rest: the colours under a pointer (hover) and the focus on its way
// through the page (keyboard: indicator, hidden behind content, order), see accessibility/interact.ts
const INTERACTIONS = ['hover', 'keyboard'] as const
const interact = { hover: scanHover, keyboard: scanKeyboard }

// a chart page in a browser on a busy runner takes longer than Playwright's thirty seconds, and a scan
// that hovers every link or walks the tab order of a page is a hundred scans of an element
test.describe.configure({ timeout: 180_000 })

const UNMOCKED = 'the page asked the backend for something the accessibility spec does not mock'

// an entry of a scan the spec no longer makes (a state renamed or dropped, a variant it is not
// scanned in) could never be found fixed, and so would stay in the baseline for ever
test('the baseline lists only scans this spec makes', () => {
  test.skip(RECORDING, 'the baseline is being rewritten')
  const inStateVariants = VARIANTS.filter(variant => STATE_VARIANTS.has(variantKey(variant)))
  const planned = new Set([
    ...PAGES.flatMap(target => VARIANTS.map(variant => `${target.page}/first-paint/${variantKey(variant)}`)),
    ...STATES.flatMap(state => inStateVariants.map(variant => `${state.page}/${state.state}/${variantKey(variant)}`)),
    // the pointer and keyboard scans, of the first paint of each page and of each state
    ...INTERACTIONS.flatMap(kind => [
      ...PAGES.flatMap(target => inStateVariants.map(variant => `${target.page}/first-paint-${kind}/${variantKey(variant)}`)),
      ...STATES.flatMap(state => inStateVariants.map(variant => `${state.page}/${state.state}-${kind}/${variantKey(variant)}`)),
    ]),
  ])
  const unplanned = baseline.entries.flatMap(entry => entry.variants.map(variant => `${entry.page}/${entry.state}/${variant}`)).filter(key => !planned.has(key))
  expect(unplanned, 'baseline entries for scans the spec does not make -- remove them from tests/e2e/accessibility/baseline.json').toEqual([])
})

/** Fails on a rule broken outside the baseline, or in it and no longer broken, unless the baseline is being recorded */
function holdToBaseline(result: Awaited<ReturnType<typeof scan>>) {
  if (RECORDING)
    return
  const { fresh, stale } = compareToBaseline(result, baseline)
  const where = `${result.page} / ${result.state} / ${result.variant}`
  const describe = (rule: string) => `${rule} (${result.found[rule]!.impact}, ${result.found[rule]!.nodes} elements, e.g. ${result.found[rule]!.targets.slice(0, 2).join(' | ')})`
  expect(fresh.map(describe), `${where}: rules broken that the baseline does not list -- fix them, or if they are known, add them to tests/e2e/accessibility/baseline.json`).toEqual([])
  expect(stale, `${where}: rules in the baseline that are no longer broken -- remove them from tests/e2e/accessibility/baseline.json`).toEqual([])
}

for (const variant of VARIANTS) {
  test.describe(`accessibility ${variantKey(variant)}`, () => {
    test.use({ locale: variant.locale === 'en' ? 'en-US' : 'de-DE' })

    test.beforeEach(async ({ context, baseURL }) => {
      // the app's own choice of language, which `detectBrowserLanguage` keeps in this cookie
      await context.addCookies([{ name: 'wd_lang', value: variant.locale, url: baseURL! }])
      // and the colour mode as the settings page keeps it: `colorScheme` is no way to ask for it, as the
      // app follows the system by default and Playwright's Firefox answers `light` to `prefers-color-scheme` whatever it is given
      await context.addInitScript((mode) => {
        localStorage.setItem('nuxt-color-mode', mode)
      }, variant.mode)
    })

    for (const target of PAGES) {
      test(`${target.page}: first paint`, async ({ page, baseURL }) => {
        const backend = await mockBackend(page, baseURL!)
        await open(page, target.path, variant)
        if (target.ready)
          await target.ready(page, variant.locale)
        else
          await expect(page.getByRole('heading', { level: 1 }).first()).toBeVisible()

        const result = await scan(page, backend, { page: target.page, state: 'first-paint', variant })
        expect(backend.unanswered, UNMOCKED).toEqual([])
        holdToBaseline(result)
      })
    }

    if (!STATE_VARIANTS.has(variantKey(variant)))
      return

    for (const kind of INTERACTIONS) {
      for (const target of PAGES) {
        test(`${target.page}: first paint (${kind})`, async ({ page, baseURL }) => {
          const backend = await mockBackend(page, baseURL!)
          await open(page, target.path, variant)
          if (target.ready)
            await target.ready(page, variant.locale)
          else
            await expect(page.getByRole('heading', { level: 1 }).first()).toBeVisible()

          const result = await interact[kind](page, backend, { page: target.page, state: `first-paint-${kind}`, variant })
          holdToBaseline(result)
        })
      }

      for (const state of STATES) {
        test(`${state.page}: ${state.state} (${kind})`, async ({ page, baseURL }) => {
          if (state.viewport)
            await page.setViewportSize(state.viewport)
          const backend = await mockBackend(page, baseURL!, state.handlers)
          await open(page, state.path, variant)
          await state.reach(page, variant.locale)

          const result = await interact[kind](page, backend, { page: state.page, state: `${state.state}-${kind}`, variant }, { keepFocus: state.keepFocus })
          holdToBaseline(result)
        })
      }
    }

    for (const state of STATES) {
      test(`${state.page}: ${state.state}`, async ({ page, baseURL }) => {
        if (state.viewport)
          await page.setViewportSize(state.viewport)
        const backend = await mockBackend(page, baseURL!, state.handlers)
        await open(page, state.path, variant)
        await state.reach(page, variant.locale)

        const result = await scan(page, backend, { page: state.page, state: state.state, variant })
        expect(backend.unanswered, UNMOCKED).toEqual([])
        holdToBaseline(result)
      })
    }
  })
}

// Keyboard operation of the widgets the scans can only look at (WCAG 2.1.1, 2.1.2, 2.4.3, 4.1.2): the
// station picker, a collapsible, a menu and the narrow layout's menu, each driven by keys alone. The
// keyboard scan (accessibility/interact.ts) walks the tab order; these say what the keys do there.
test.describe('keyboard operation', () => {
  test.describe.configure({ timeout: 30_000 })
  const variant: Variant = { mode: 'light', locale: 'en' }

  test.beforeEach(async ({ context, baseURL }) => {
    await context.addCookies([{ name: 'wd_lang', value: 'en', url: baseURL! }])
  })

  test('the station picker opens, searches, selects and closes by keys', async ({ page, baseURL }) => {
    await mockBackend(page, baseURL!)
    await open(page, EXPLORER, variant)
    // Reka's select menu is a button with a popup, whose name is the placeholder until something is chosen
    const picker = page.getByRole('button', { name: message('en', 'common.stationSearch') })
    await picker.focus()
    await page.keyboard.press('Enter')

    // the list is the one the picker controls, and its options are named
    const listbox = page.getByRole('listbox')
    await expect(listbox).toBeVisible()
    await expect(picker).toHaveAttribute('aria-expanded', 'true')
    await expect(picker).toHaveAttribute('aria-controls', (await listbox.getAttribute('id'))!)
    await expect(listbox.getByRole('option').first()).toHaveAccessibleName(/\S/)

    await page.keyboard.type('Donaueschingen')
    await expect(listbox.getByRole('option')).toHaveCount(1)
    await page.keyboard.press('ArrowDown')
    await page.keyboard.press('Enter')
    await page.keyboard.press('Escape')
    await expect(listbox).toBeHidden()
    // what was chosen is the picker's name now, and the focus is back on it, not lost to the page
    // (its chip, a button to remove it, is named "Remove ...")
    const chosen = page.getByRole('button', { name: /^Donaueschingen/ })
    await expect(chosen).toBeVisible()
    await expect(chosen).toBeFocused()
  })

  test('the station picker\'s toggle is a radio group moved by the arrow keys, and a click moves the focus into the search or the map (GH-3877)', async ({ page, baseURL }) => {
    await mockBackend(page, baseURL!)
    await open(page, EXPLORER, variant)
    const list = page.getByRole('radio', { name: message('en', 'stationSelection.modeList'), exact: true })
    const map = page.getByRole('radio', { name: message('en', 'stationSelection.modeMap'), exact: true })
    const group = page.getByRole('radiogroup', { name: message('en', 'stationSelection.modeLabel') })
    await expect(group).toBeVisible()
    await expect(list).toBeChecked()

    // the arrow keys select and keep the focus on the toggle, to walk along it
    await list.focus()
    await page.keyboard.press('ArrowRight')
    await expect(map).toBeChecked()
    await expect(map).toBeFocused()
    // what the toggle controls is there, and the map is in it
    const controlled = (await map.getAttribute('aria-controls'))!
    await expect(page.locator(`[id="${controlled}"] .leaflet-container`)).toBeVisible()
    await expect(page.locator('.leaflet-marker-icon').first()).toBeVisible()
    await page.keyboard.press('ArrowLeft')
    await expect(list).toBeChecked()
    await expect(page.locator('.leaflet-container')).toHaveCount(0)

    // a click is a decision to use the mode: the focus goes into it
    await map.click()
    await expect(page.locator('.leaflet-container')).toBeFocused()
    await list.click()
    await expect(page.getByRole('button', { name: message('en', 'common.stationSearch') })).toBeFocused()

    // the map stands where the toggle left it, and a pick on it is a chip that stays in the list
    await map.press('Enter')
    await expect(page.locator('.leaflet-container')).toBeFocused()
    await page.locator('img.leaflet-marker-icon').first().dispatchEvent('click')
    const chip = page.locator('[data-station-chip]')
    await expect(chip).toHaveCount(1)
    await list.click()
    await expect(page.locator('[data-station-chip]')).toHaveCount(1)
    // a chip is a button: Enter takes the station out, and the focus does not fall to the page
    await page.locator('[data-station-chip]').focus()
    await page.keyboard.press('Enter')
    await expect(page.locator('[data-station-chip]')).toHaveCount(0)
    await expect(list).toBeFocused()
  })

  test('the station picker\'s mode is remembered for the tool, and the other tools keep their own (GH-3877)', async ({ page, baseURL }) => {
    await mockBackend(page, baseURL!)
    await open(page, '/stripes', variant)
    const map = page.getByRole('radio', { name: message('en', 'stationSelection.modeMap'), exact: true })
    await map.click()
    await expect(page.locator('.leaflet-container')).toBeVisible()

    await page.reload()
    await expect(map).toBeChecked()
    await expect(page.locator('.leaflet-container')).toBeVisible()

    // the explorer's picker has been left on the list
    await open(page, EXPLORER, variant)
    await expect(page.getByRole('radio', { name: message('en', 'stationSelection.modeList'), exact: true })).toBeChecked()
  })

  test('a collapsible opens and closes by Enter and Space, and says so', async ({ page, baseURL }) => {
    await mockBackend(page, baseURL!)
    await open(page, EXPLORER, variant)
    const trigger = page.getByRole('button', { name: message('en', 'explorer.aboutButton') })
    await expect(trigger).toHaveAttribute('aria-expanded', 'false')
    await trigger.focus()
    await page.keyboard.press('Enter')
    await expect(trigger).toHaveAttribute('aria-expanded', 'true')
    // what it controls is there, and not an empty reference (axe: aria-allowed-attr)
    const controlled = (await trigger.getAttribute('aria-controls'))!
    expect(controlled).not.toBe('')
    await expect(page.locator(`[id="${controlled}"]`)).toBeVisible()
    await page.keyboard.press('Space')
    await expect(trigger).toHaveAttribute('aria-expanded', 'false')
  })

  test('a menu opens by Enter, moves by the arrow keys and gives the focus back on Escape', async ({ page, baseURL }) => {
    await mockBackend(page, baseURL!)
    await open(page, '/stripes?kind=temperature&station=00011', variant)
    await page.getByRole('button', { name: message('en', 'common.fetch'), exact: true }).click()
    await expect(stripesChart(page)).toBeVisible()

    const trigger = page.getByRole('button', { name: message('en', 'stripes.downloadImage') })
    await trigger.focus()
    await page.keyboard.press('Enter')
    const items = page.getByRole('menuitem')
    await expect(items.first()).toBeVisible()
    // opened by a key, the menu puts the focus on an item; the arrow keys move it on, each to another
    const focusedItem = () => page.evaluate(() => document.activeElement?.getAttribute('role') === 'menuitem' ? document.activeElement.textContent : null)
    await expect.poll(focusedItem).not.toBeNull()
    const first = await focusedItem()
    await page.keyboard.press('ArrowDown')
    await expect.poll(focusedItem).not.toBe(first)
    await expect.poll(focusedItem).not.toBeNull()
    await page.keyboard.press('Escape')
    await expect(items.first()).toBeHidden()
    await expect(trigger).toBeFocused()
  })

  test('a link of the footer that the Tab key reaches is not under an error toast (2.4.11)', async ({ page, baseURL }) => {
    await mockBackend(page, baseURL!, { values: () => new ApiFailure(422, 'The source does not carry these parameters for this station.') })
    await open(page, EXPLORER_WITH_STATION, variant)
    await page.getByRole('button', { name: message('en', 'common.fetch'), exact: true }).click()
    const toast = page.locator('[data-slot="title"]', { hasText: message('en', 'dataViewer.fetchErrorToastTitle') })
    await expect(toast).toBeVisible()
    // the toast closes after five seconds: the pointer on it holds it open while the keys are pressed
    await toast.hover()

    // the link before the last one, and then the key that goes on to it
    await page.getByRole('link', { name: message('en', 'footer.privacy'), exact: true }).focus()
    await page.keyboard.press('Tab')
    const licences = page.getByRole('link', { name: message('en', 'footer.licenses'), exact: true })
    await expect(licences).toBeFocused()

    // what lies at the middle of the focused link is the link: the page was scrolled clear of the toast
    const hitsLink = () => licences.evaluate((link) => {
      const box = link.getBoundingClientRect()
      const hit = document.elementFromPoint(box.left + box.width / 2, box.top + box.height / 2)
      return hit != null && link.contains(hit)
    })
    await expect.poll(hitsLink).toBe(true)
    const toastBox = (await page.locator('.app-toast-viewport').boundingBox())!
    const linkBox = (await licences.boundingBox())!
    // and clear of the toast altogether, not merely not entirely under it
    expect(linkBox.y + linkBox.height).toBeLessThanOrEqual(toastBox.y)
  })

  test('the menu of the narrow layout is a dialog that keeps the focus, and Escape closes it', async ({ page, baseURL }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await mockBackend(page, baseURL!)
    await open(page, '/', variant)
    // by label, not by role: while the dialog is open the page behind it is hidden from the accessibility tree
    const hamburger = page.locator(`button[aria-label="${message('en', 'header.menu')}"]`)
    await expect(hamburger).toHaveAttribute('aria-expanded', 'false')
    await hamburger.focus()
    await page.keyboard.press('Enter')

    const dialog = page.getByRole('dialog')
    await expect(dialog).toBeVisible()
    await expect(dialog).toHaveAccessibleName(message('en', 'header.menu'))
    await expect(hamburger).toHaveAttribute('aria-expanded', 'true')
    // Tab through more stops than the menu has: the focus never leaves it, forwards or back
    for (const key of ['Tab', 'Shift+Tab']) {
      for (let stop = 0; stop < 25; stop++) {
        await page.keyboard.press(key)
        expect(await dialog.evaluate(node => node.contains(document.activeElement))).toBe(true)
      }
    }
    // a tooltip that is open takes an Escape of its own, as it should; the dialog goes with the next
    for (let attempt = 0; attempt < 3 && await dialog.isVisible(); attempt++) {
      await page.keyboard.press('Escape')
      await page.waitForTimeout(300)
    }
    await expect(dialog).toBeHidden()
    await expect(hamburger).toBeFocused()
  })
})

// The toolbars of the charts (zoom, move, reset, the camera) are the keyboard's way to move around a chart (WCAG 2.1.1), which a
// drag, a pinch and the wheel do for a pointer (2.5.7): native buttons in the tab order with names, and the chart itself is one
// tab stop whose keys step through its values. The Explorer's was Plotly's modebar until GH-4096.
test.describe('chart controls by keyboard', () => {
  test.describe.configure({ timeout: 60_000 })
  const variant: Variant = { mode: 'light', locale: 'en' }

  test.beforeEach(async ({ context, baseURL }) => {
    await context.addCookies([{ name: 'wd_lang', value: 'en', url: baseURL! }])
  })

  test('the toolbar of the stripes is reached by Tab, named, and operated by Enter and Space', async ({ page, baseURL }) => {
    await mockBackend(page, baseURL!)
    await open(page, '/stripes?kind=temperature&station=00011', variant)
    await page.getByRole('button', { name: message('en', 'common.fetch'), exact: true }).click()
    await expect(stripesChart(page)).toBeVisible()

    const buttons = page.locator('.sc-toolbar button')
    const count = await buttons.count()
    expect(count).toBe(6)
    // every one is a button in the tab order with a name of its own
    const names = await buttons.evaluateAll(nodes => nodes.map(node => ({
      tabindex: (node as HTMLElement).tabIndex,
      name: node.getAttribute('aria-label'),
    })))
    for (const button of names) {
      expect(button.tabindex).toBeGreaterThanOrEqual(0)
      expect(button.name).toBeTruthy()
    }
    expect(new Set(names.map(button => button.name)).size).toBe(count)
    expect(await page.locator('.sc-toolbar').getAttribute('role')).toBe('group')

    // the whole chart is shown, so there is nothing to zoom out of, to move to or to reset: those are off, and the others are not
    const named = (name: string) => page.locator(`.sc-toolbar button[aria-label="${name}"]`)
    await expect(named(message('en', 'stripes.chart.zoomOut'))).toBeDisabled()
    await expect(named(message('en', 'stripes.chart.resetZoom'))).toBeDisabled()
    // Enter zooms in, which turns reset on; Space resets it
    const zoomIn = named(message('en', 'stripes.chart.zoomIn'))
    await zoomIn.focus()
    await page.keyboard.press('Enter')
    const reset = named(message('en', 'stripes.chart.resetZoom'))
    await expect(reset).toBeEnabled()
    await reset.focus()
    await page.keyboard.press('Space')
    await expect(reset).toBeDisabled()
    await expect(stripesChart(page)).toBeVisible()

    // Tab goes from the toolbar to the chart, which is one stop, and on to the download of the image below it (the table is a view of
    // the switch above, GH-4233)
    await named(message('en', 'stripes.chart.savePng')).focus()
    await page.keyboard.press('Tab')
    await expect(page.locator('.sc-stage')).toBeFocused()
    await page.keyboard.press('Tab')
    await expect(page.getByRole('button', { name: message('en', 'stripes.downloadImage'), exact: true })).toBeFocused()
  })

  // WCAG 2.1.1 and 2.5.7: what the pointer reads from the stripes (the year's value) the keyboard reads too
  test('the stripes\' chart is read by the arrow keys, and zoomed by + - 0, with its values said to a screen reader', async ({ page, baseURL }) => {
    await mockBackend(page, baseURL!)
    await open(page, '/stripes?kind=temperature&station=00011', variant)
    await page.getByRole('button', { name: message('en', 'common.fetch'), exact: true }).click()
    await expect(stripesChart(page)).toBeVisible()

    const stage = page.locator('.sc-stage')
    const readout = page.getByTestId('stripes-readout')
    const announced = page.getByTestId('stripes-announce')
    await stage.focus()
    await expect(readout).toHaveCount(0)
    await page.keyboard.press('ArrowRight')
    await expect(readout).toBeVisible()
    await expect(announced).toHaveText(/^1955: Value: [\d.]+ °C$/)
    await page.keyboard.press('ArrowRight')
    await expect(announced).toHaveText(/^1956: /)
    await page.keyboard.press('PageDown')
    await expect(announced).toHaveText(/^1966: /)
    await page.keyboard.press('End')
    await expect(announced).toHaveText(/^2024: /)
    await page.keyboard.press('Home')
    await expect(announced).toHaveText(/^1955: /)

    const reset = page.locator(`.sc-toolbar button[aria-label="${message('en', 'stripes.chart.resetZoom')}"]`)
    await expect(reset).toBeDisabled()
    await page.keyboard.press('+')
    await expect(reset).toBeEnabled()
    await page.keyboard.press('0')
    await expect(reset).toBeDisabled()
    // the focus stays on the chart, and the page does not scroll for a key it takes
    await expect(stage).toBeFocused()
  })

  // WCAG 1.4.13: the readout comes with the pointer or a key, can be moved onto, stays, and Escape closes it
  test('the readout of the stripes\' chart is hoverable, persistent and dismissed by Escape, until the pointer or a key moves on', async ({ page, baseURL }) => {
    await mockBackend(page, baseURL!)
    await open(page, '/stripes?kind=temperature&station=00011', variant)
    await page.getByRole('button', { name: message('en', 'common.fetch'), exact: true }).click()
    await expect(stripesChart(page)).toBeVisible()
    await page.locator('.sc-stage').scrollIntoViewIfNeeded()

    const stage = (await page.locator('.sc-stage').boundingBox())!
    const readout = page.getByTestId('stripes-readout')
    // the right half of the chart: the readout is docked on the left, away from the crosshair
    const x = stage.x + stage.width * 0.75
    const y = stage.y + stage.height * 0.5
    await page.mouse.move(x - 12, y)
    await page.mouse.move(x, y, { steps: 4 })
    await expect(readout).toBeVisible()
    const shownFor = (await readout.getAttribute('aria-label'))!

    // hoverable: the pointer moves onto it, along the way over the stripes, and it is still there for the same year
    const box = (await readout.boundingBox())!
    await page.mouse.move(box.x + box.width / 2, y, { steps: 20 })
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps: 4 })
    await expect(readout).toBeVisible()
    await expect(readout).toHaveAttribute('aria-label', shownFor)
    // persistent: it stays while the pointer rests
    await page.waitForTimeout(600)
    await expect(readout).toBeVisible()

    // dismissible: Escape, with the pointer where it is and no focus in the chart
    await page.keyboard.press('Escape')
    await expect(readout).toHaveCount(0)
    await page.waitForTimeout(300)
    await expect(readout).toHaveCount(0)

    // a pointer that leaves and comes to another stripe is a new hover
    await page.mouse.move(x, y - stage.height / 2 - 40, { steps: 3 })
    await page.mouse.move(x + 30, y, { steps: 4 })
    await expect(readout).toBeVisible()
  })

  // opens the explorer's chart, which the tests of its toolbar, its keys, its readout and its legend are of
  async function openExplorerChart(page: Page, baseURL: string) {
    await mockBackend(page, baseURL)
    await open(page, EXPLORER_WITH_STATION, variant)
    await page.getByRole('button', { name: message('en', 'common.fetch'), exact: true }).click()
    await expect(page.getByRole('table').first()).toBeVisible()
    await page.getByRole('button', { name: message('en', 'dataViewer.viewChart'), exact: true }).click()
    await expect(explorerChart(page)).toBeVisible()
  }

  /** The window of time the chart shows, in ms: what a zoom changes, which the canvas says */
  const windowOf = async (page: Page) => {
    const [start, end] = (await page.locator('.xc-canvas').first().getAttribute('data-window'))!.split('/').map(Number)
    return { start: start!, end: end!, span: end! - start! }
  }

  test('the toolbar of the explorer\'s chart is in the tab order and named', async ({ page, baseURL }) => {
    await openExplorerChart(page, baseURL!)

    const buttons = page.locator('.xc-toolbar button')
    expect(await buttons.count()).toBe(6)
    const names = await buttons.evaluateAll(nodes => nodes.map(node => ({
      tabindex: (node as HTMLElement).tabIndex,
      name: node.getAttribute('aria-label'),
      native: node.tagName === 'BUTTON',
    })))
    for (const button of names) {
      expect(button.native).toBe(true)
      expect(button.tabindex, `${button.name} is in the tab order`).toBeGreaterThanOrEqual(0)
      expect(button.name).toBeTruthy()
    }
    expect(new Set(names.map(button => button.name)).size, 'every button has a name of its own').toBe(6)
    expect(await page.locator('.xc-toolbar').getAttribute('role')).toBe('group')
    await expect(page.locator('.xc-toolbar')).toHaveAttribute('aria-label', message('en', 'dataViewer.chart.zoomGroup'))
    // the first that is on takes the focus
    await page.getByRole('button', { name: 'Zoom in', exact: true }).focus()
    await expect(page.getByRole('button', { name: 'Zoom in', exact: true })).toBeFocused()
  })

  test('the toolbar of the explorer\'s chart is walked by Tab in order, and operated by Enter and Space', async ({ page, baseURL }) => {
    await openExplorerChart(page, baseURL!)

    const named = (name: string) => page.locator(`.xc-toolbar button[aria-label="${name}"]`)
    const zoomIn = named(message('en', 'dataViewer.chart.zoomIn'))
    const reset = named(message('en', 'dataViewer.chart.resetZoom'))
    // the whole chart is shown, so there is nothing to zoom out of, to move to or to reset: those are off, and the others are not
    await expect(named(message('en', 'dataViewer.chart.zoomOut'))).toBeDisabled()
    await expect(reset).toBeDisabled()
    await expect(named(message('en', 'dataViewer.chart.earlier'))).toBeDisabled()
    await expect(named(message('en', 'dataViewer.chart.later'))).toBeDisabled()

    // Enter zooms in: the window of time of the chart is narrower, which turns reset on
    const whole = await windowOf(page)
    await zoomIn.focus()
    await page.keyboard.press('Enter')
    await expect.poll(async () => (await windowOf(page)).span, { message: 'Enter on Zoom in narrows the window' }).toBeLessThan(whole.span)
    await expect(reset).toBeEnabled()
    const zoomed = await windowOf(page)
    expect(zoomed.start).toBeGreaterThanOrEqual(whole.start)
    expect(zoomed.end).toBeLessThanOrEqual(whole.end)

    // Tab walks through the toolbar, button by button in order, to the first of the legend's
    const focused = () => page.evaluate(() => {
      const element = document.activeElement
      return element?.closest('.xc-toolbar') ? `toolbar: ${element.getAttribute('aria-label')}` : element?.closest('.xc-legend') ? 'legend' : element?.classList.contains('xc-stage') ? 'chart' : null
    })
    const order = (await page.locator('.xc-toolbar button').evaluateAll(nodes => nodes.map(node => node.getAttribute('aria-label')))).map(name => `toolbar: ${name}`)
    await page.locator('.xc-toolbar button').first().focus()
    const reached = [await focused()]
    for (let stop = 1; stop < order.length; stop++) {
      await page.keyboard.press('Tab')
      reached.push(await focused())
    }
    expect(reached).toEqual(order)
    await page.keyboard.press('Tab')
    expect(await focused()).toBe('legend')

    // Later moves the window on; Space on reset puts the whole chart back, which turns reset off again
    await named(message('en', 'dataViewer.chart.later')).focus()
    await page.keyboard.press('Space')
    await expect.poll(async () => (await windowOf(page)).start, { message: 'Space on Later moves the window' }).toBeGreaterThan(zoomed.start)
    await reset.focus()
    await page.keyboard.press('Space')
    await expect.poll(async () => await windowOf(page), { message: 'Space on Reset zoom goes back to the whole chart' }).toEqual(whole)
    await expect(reset).toBeDisabled()
    await expect(explorerChart(page)).toBeVisible()

    // the camera is a button too: Enter on it saves the image
    const saved = page.waitForEvent('download')
    await named(message('en', 'dataViewer.chart.savePng')).focus()
    await page.keyboard.press('Enter')
    expect((await saved).suggestedFilename()).toBe('newplot.png')
  })

  // WCAG 2.1.1 and 2.5.7: what the pointer reads from the chart (the values at a time) the keyboard reads too
  test('the explorer\'s chart is read by the arrow keys, and zoomed by + - 0, with its values said to a screen reader', async ({ page, baseURL }) => {
    await openExplorerChart(page, baseURL!)

    const stage = page.locator('.xc-stage')
    const readout = page.getByTestId('explorer-readout')
    const announced = page.getByTestId('explorer-announce')
    await stage.focus()
    await expect(readout).toHaveCount(0)
    await page.keyboard.press('ArrowRight')
    await expect(readout).toBeVisible()
    await expect(announced).toHaveText(/^Sep 1, 2026: .+: [\d.]+; .+: [\d.]+$/)
    await expect(readout.locator('dd')).toHaveCount(2)
    await page.keyboard.press('ArrowRight')
    await expect(announced).toHaveText(/^Sep 2, 2026: /)
    await page.keyboard.press('Shift+ArrowRight')
    await expect(announced).toHaveText(/^Sep 12, 2026: /)
    await page.keyboard.press('End')
    await expect(announced).toHaveText(/^Sep 30, 2026: /)
    await page.keyboard.press('Home')
    await expect(announced).toHaveText(/^Sep 1, 2026: /)
    // the readout is of the moment the announcement is of
    await expect(readout).toHaveAttribute('aria-label', 'Values at Sep 1, 2026')

    const whole = await windowOf(page)
    const reset = page.locator(`.xc-toolbar button[aria-label="${message('en', 'dataViewer.chart.resetZoom')}"]`)
    await expect(reset).toBeDisabled()
    await page.keyboard.press('+')
    await expect.poll(async () => (await windowOf(page)).span).toBeLessThan(whole.span)
    await expect(reset).toBeEnabled()
    await page.keyboard.press('-')
    await page.keyboard.press('+')
    await page.keyboard.press('0')
    await expect.poll(async () => await windowOf(page), { message: '0 goes back to the whole chart' }).toEqual(whole)
    await expect(reset).toBeDisabled()
    // the focus stays on the chart, and the page does not scroll for a key it takes
    await expect(stage).toBeFocused()
  })

  // WCAG 1.4.13: the readout comes with the pointer or a key, can be moved onto, stays, and Escape closes it
  test('the readout of the explorer\'s chart is hoverable, persistent and dismissed by Escape, until the pointer or a key moves on', async ({ page, baseURL }) => {
    await openExplorerChart(page, baseURL!)
    await page.locator('.xc-stage').scrollIntoViewIfNeeded()

    const stage = (await page.locator('.xc-stage').boundingBox())!
    const readout = page.getByTestId('explorer-readout')
    // the left part of the plot: the readout is docked at the right edge, clear of the crosshair
    const x = stage.x + stage.width * 0.25
    const y = stage.y + stage.height * 0.55
    await page.mouse.move(x - 12, y)
    await page.mouse.move(x, y, { steps: 4 })
    await expect(readout).toBeVisible()
    // the crosshair is in the chart, with a dot (a circle of 5 px, which the browser draws as an arc) on each series
    await expect(page.locator('.xc-canvas svg path[d*="A5 5 "]')).toHaveCount(2)

    // hoverable: the pointer moves onto it, along the way over the plot, and it is still there
    const box = (await readout.boundingBox())!
    await page.mouse.move(box.x + box.width / 2, y, { steps: 25 })
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps: 4 })
    await expect(readout).toBeVisible()
    const shownFor = (await readout.getAttribute('aria-label'))!
    // persistent: it stays, as it is, while the pointer rests on it
    await page.waitForTimeout(600)
    await expect(readout).toBeVisible()
    await expect(readout).toHaveAttribute('aria-label', shownFor)

    // dismissible: Escape, with the pointer where it is and no focus in the chart
    await page.keyboard.press('Escape')
    await expect(readout).toHaveCount(0)
    await page.waitForTimeout(300)
    await expect(readout).toHaveCount(0)

    // a pointer that leaves and comes back to another moment is a new hover
    await page.mouse.move(x, y - stage.height / 2 - 40, { steps: 3 })
    await page.mouse.move(x + 30, y, { steps: 4 })
    await expect(readout).toBeVisible()
    // and it goes where the pointer leaves the chart
    await page.mouse.move(x, y - stage.height / 2 - 40, { steps: 3 })
    await expect(readout).toHaveCount(0)
  })

  test('the readout of the explorer\'s chart gives the focus back to the chart where its Close button goes', async ({ page, baseURL }) => {
    await openExplorerChart(page, baseURL!)
    const stage = page.locator('.xc-stage')
    await stage.focus()
    await page.keyboard.press('ArrowRight')
    const readout = page.getByTestId('explorer-readout')
    await expect(readout).toBeVisible()
    // Tab goes from the chart to the readout's Close button, and Enter on it closes the readout and gives the focus back
    await page.keyboard.press('Tab')
    const close = readout.getByRole('button', { name: message('en', 'dataViewer.chart.readoutClose') })
    await expect(close).toBeFocused()
    await page.keyboard.press('Enter')
    await expect(readout).toHaveCount(0)
    await expect(stage).toBeFocused()
  })

  // the legend is drawn in the chart (and in a saved image) and operated from the buttons over its items
  test('the legend of the explorer\'s chart turns a series off and on by the keyboard, and says which is on', async ({ page, baseURL }) => {
    await openExplorerChart(page, baseURL!)
    const items = page.locator('.xc-legend button')
    expect(await items.count()).toBe(2)
    expect(await items.evaluateAll(nodes => nodes.map(node => node.getAttribute('aria-pressed')))).toEqual(['true', 'true'])
    // the first series' colour, on the mark in the legend and on its line in the plot
    const marks = () => page.locator('.xc-canvas svg').first().evaluate(svg => [...svg.querySelectorAll('[stroke="#3b82f6"], [fill="#3b82f6"]')].length)
    expect(await marks()).toBeGreaterThan(1)

    // Tab from the toolbar reaches the legend, which is before the chart
    await page.locator('.xc-toolbar button[aria-label="Download plot as a PNG"]').focus()
    await page.keyboard.press('Tab')
    await expect(items.first()).toBeFocused()
    await page.keyboard.press('Space')
    await expect(items.first()).toHaveAttribute('aria-pressed', 'false')
    // the series is gone from the plot, and the legend draws the item as off: no more of its colour anywhere in the chart
    await expect.poll(marks).toBe(0)
    // the focus stays on the item
    await expect(items.first()).toBeFocused()
    // and what the keys read leaves it out
    await page.locator('.xc-stage').focus()
    await page.keyboard.press('ArrowRight')
    await expect(page.getByTestId('explorer-readout').locator('dd')).toHaveCount(1)
    await items.first().focus()
    await page.keyboard.press('Enter')
    await expect(items.first()).toHaveAttribute('aria-pressed', 'true')
    await expect.poll(marks).toBeGreaterThan(1)
    // the way on is the next item, and then the chart
    await page.keyboard.press('Tab')
    await expect(items.nth(1)).toBeFocused()
    await page.keyboard.press('Tab')
    await expect(page.locator('.xc-stage')).toBeFocused()
  })

  // "Show as table": what the chart draws is in a table that a keyboard and a screen reader read (WCAG 1.1.1, 1.3.1)
  test('the explorer\'s chart has its values as a table, one toggle away, and the chart comes back', async ({ page, baseURL }) => {
    await openExplorerChart(page, baseURL!)
    const table = page.getByRole('button', { name: message('en', 'dataViewer.viewTable'), exact: true })
    const chart = page.getByRole('button', { name: message('en', 'dataViewer.viewChart'), exact: true })
    await expect(chart).toHaveAttribute('aria-pressed', 'true')
    await expect(page.getByRole('table')).toHaveCount(0)
    await table.focus()
    await page.keyboard.press('Enter')
    await expect(page.getByRole('table').first()).toBeVisible()
    // the values of the station, a page of them
    await expect(page.getByRole('table').first().getByRole('cell', { name: '00011' }).first()).toBeVisible()
    expect(await page.getByRole('table').first().getByRole('row').count()).toBeGreaterThan(40)
    await expect(page.locator('.xc-canvas')).toHaveCount(0)
    await chart.focus()
    await page.keyboard.press('Enter')
    await expect(explorerChart(page)).toBeVisible()
    await expect(page.getByRole('table')).toHaveCount(0)
  })

  // what the widget's forecast draws, in a table a keyboard and a screen reader read (WCAG 1.1.1, 1.3.1)
  for (const { page: name, path, ready } of [
    { page: 'widget', path: '/widget?station=01001', ready: async (page: Page) => {
      await expect(forecastChart(page)).toBeVisible()
    } },
  ]) {
    test(`the chart of the ${name} page has its values as a table, opened and read by keys`, async ({ page, baseURL }) => {
      await mockBackend(page, baseURL!)
      await open(page, path, variant)
      await ready(page)

      // the chart is described by a sentence that exists, and the table is not in the page before it is asked for
      const figure = page.getByRole('figure')
      await expect(figure).toHaveAttribute('aria-describedby', /\S/)
      // the sentence first, and after it the keys the chart answers to (the forecast's and the stripes')
      const described = (await figure.getAttribute('aria-describedby'))!.split(' ')[0]!
      await expect(page.locator(`[id="${described}"]`)).toHaveText(/\S/)
      await expect(page.getByRole('table')).toHaveCount(0)

      const trigger = page.getByRole('button', { name: message('en', 'dataViewer.viewTable'), exact: true })
      await expect(trigger).toHaveAttribute('aria-expanded', 'false')
      await trigger.focus()
      await page.keyboard.press('Enter')
      await expect(trigger).toHaveAttribute('aria-expanded', 'true')
      const table = page.getByRole('table')
      await expect(table).toBeVisible()
      await expect(table.getByRole('rowheader').first()).toHaveText(/\S/)
      expect(await table.getByRole('row').count()).toBeGreaterThan(10)

      // the box that scrolls takes the focus by Tab, so that the keys scroll it
      await page.keyboard.press('Tab')
      const region = page.getByRole('region', { name: await figure.getAttribute('aria-label') ?? '' })
      await expect(region).toBeFocused()
      const before = await region.evaluate(node => node.scrollTop)
      await page.keyboard.press('PageDown')
      await expect.poll(() => region.evaluate(node => node.scrollTop)).toBeGreaterThan(before)

      await trigger.focus()
      await page.keyboard.press('Space')
      await expect(trigger).toHaveAttribute('aria-expanded', 'false')
      await expect(page.getByRole('table')).toHaveCount(0)
    })
  }

  // the stripes' table is a view of its own, the fourth of the switch that the arrow keys move along, as the forecast's is
  // (GH-4233; WCAG 1.1.1, 1.3.1, 2.1.1, 4.1.2)
  test('the stripes page has its values as a view of its own, chosen and read by keys, and the chart\'s summary points at it', async ({ page, baseURL }) => {
    await mockBackend(page, baseURL!)
    await open(page, '/stripes?kind=temperature&station=00011', variant)
    await page.getByRole('button', { name: message('en', 'common.fetch'), exact: true }).click()
    await expect(stripesChart(page)).toBeVisible()

    // the chart is described by a sentence that says where the values are, and there is no table until the view is chosen
    const figure = page.getByRole('figure')
    const described = (await figure.getAttribute('aria-describedby'))!.split(' ')[0]!
    await expect(page.locator(`[id="${described}"]`)).toContainText(message('en', 'stripes.variant.table'))
    await expect(page.getByRole('table')).toHaveCount(0)
    await expect(page.getByRole('button', { name: message('en', 'dataViewer.viewTable'), exact: true })).toHaveCount(0)

    const group = page.getByRole('radiogroup', { name: message('en', 'stripes.variant.label'), exact: true })
    const barsScale = group.getByRole('radio', { name: message('en', 'stripes.variant.barsScale'), exact: true })
    const stripes = group.getByRole('radio', { name: message('en', 'stripes.variant.stripes'), exact: true })
    const tableView = group.getByRole('radio', { name: message('en', 'stripes.variant.table'), exact: true })
    await expect(stripes).toBeChecked()

    // the group is one stop; the arrow keys choose and move the focus, the table last
    await stripes.focus()
    await page.keyboard.press('End')
    await expect(tableView).toBeChecked()
    await expect(tableView).toBeFocused()
    await expect(page).toHaveURL(/[?&]variant=table/)
    await page.keyboard.press('ArrowLeft')
    await expect(barsScale).toBeChecked()
    await page.keyboard.press('ArrowRight')
    await expect(tableView).toBeChecked()

    // the table has no chart over it, a caption, and the headers and rows a screen reader reads
    await expect(page.getByRole('figure')).toHaveCount(0)
    const table = page.getByRole('table')
    await expect(table).toBeVisible()
    await expect(table.locator('caption')).toHaveText(/\S/)
    await expect(table.getByRole('columnheader')).toHaveText([
      message('en', 'stripes.table.year'),
      `${message('en', 'stripes.table.value')} (°C)`,
      `${message('en', 'stripes.table.anomaly')} (°C)`,
      message('en', 'stripes.table.class'),
    ])
    await expect(table.getByRole('rowheader').first()).toHaveText(/\S/)
    expect(await table.getByRole('row').count()).toBeGreaterThan(10)

    // the box that scrolls takes the focus, so that the keys scroll it
    const region = page.getByRole('region', { name: /^Climate stripes \(Temperature\) for / })
    await region.focus()
    await expect(region).toBeFocused()
    const before = await region.evaluate(node => node.scrollTop)
    await page.keyboard.press('PageDown')
    await expect.poll(() => region.evaluate(node => node.scrollTop)).toBeGreaterThan(before)

    // and back to the chart by keys
    await tableView.focus()
    await page.keyboard.press('Home')
    await expect(stripes).toBeChecked()
    await expect(stripesChart(page)).toBeVisible()
    await expect(page.getByRole('table')).toHaveCount(0)
  })

  // the forecast's table is a view of its own, chosen by a radio group that the arrow keys move along
  // (WCAG 1.1.1, 1.3.1, 2.1.1, 4.1.2)
  test('the forecast of the meteogram page has its values as a view of its own, chosen and read by keys', async ({ page, baseURL }) => {
    await mockBackend(page, baseURL!)
    await open(page, '/meteogram?station=01001', variant)
    await expect(forecastChart(page)).toBeVisible()

    // the chart is described by a sentence that exists, and there is no table until the view is chosen
    const figure = page.getByRole('figure')
    const described = (await figure.getAttribute('aria-describedby'))!.split(' ')[0]!
    await expect(page.locator(`[id="${described}"]`)).toHaveText(/\S/)
    await expect(page.getByRole('table')).toHaveCount(0)
    await expect(page.getByRole('button', { name: message('en', 'dataViewer.viewTable'), exact: true })).toHaveCount(0)

    const group = page.getByRole('radiogroup', { name: message('en', 'meteogram.chart.viewLabel'), exact: true })
    const chart = group.getByRole('radio', { name: message('en', 'meteogram.chart.viewChart'), exact: true })
    const compact = group.getByRole('radio', { name: message('en', 'meteogram.chart.viewCompact'), exact: true })
    const tableView = group.getByRole('radio', { name: message('en', 'meteogram.chart.viewTable'), exact: true })
    await expect(chart).toBeChecked()

    // the group is one stop; the arrow keys choose and move the focus
    await chart.focus()
    await page.keyboard.press('ArrowRight')
    await expect(compact).toBeChecked()
    await expect(compact).toBeFocused()
    await page.keyboard.press('ArrowRight')
    await expect(tableView).toBeChecked()
    await expect(tableView).toBeFocused()
    await expect(page).toHaveURL(/[?&]view=table/)

    // the table has no chart over it, and the headers and rows a screen reader reads
    await expect(page.getByRole('figure')).toHaveCount(0)
    const table = page.getByRole('table')
    await expect(table).toBeVisible()
    await expect(table.getByRole('rowheader').first()).toHaveText(/\S/)
    expect(await table.getByRole('row').count()).toBeGreaterThan(10)

    // the box that scrolls takes the focus, so that the keys scroll it
    const region = page.getByRole('region', { name: /^Forecast chart for / })
    await region.focus()
    await expect(region).toBeFocused()
    const before = await region.evaluate(node => node.scrollTop)
    await page.keyboard.press('PageDown')
    await expect.poll(() => region.evaluate(node => node.scrollTop)).toBeGreaterThan(before)

    // and back to the chart by keys
    await tableView.focus()
    await page.keyboard.press('Home')
    await expect(chart).toBeChecked()
    await expect(forecastChart(page)).toBeVisible()
    await expect(page.getByRole('table')).toHaveCount(0)
  })

  // The forecast's readout is an element of the page, not a Plotly label: it is hoverable, dismissible and persistent
  // (WCAG 1.4.13), and the chart is one tab stop that steps through the hours by keys (2.1.1)
  test('the readout of the forecast chart is hoverable, dismissed by Escape, and persistent', async ({ page, baseURL }) => {
    await mockBackend(page, baseURL!)
    await open(page, '/meteogram?station=01001', variant)
    await expect(forecastChart(page)).toBeVisible()

    await page.locator('.mg-stage').scrollIntoViewIfNeeded()
    const box = (await page.locator('.mg-stage').boundingBox())!
    const x = box.x + 71 + (box.width - 81) * 0.3
    const y = box.y + box.height * 0.6
    const readout = page.getByTestId('meteogram-readout')
    await page.mouse.move(x - 20, y)
    await page.mouse.move(x, y, { steps: 4 })
    await expect(readout).toBeVisible()
    await expect(readout).toContainText(/\d{2}[:.]\d{2}/)

    // hoverable: the pointer moves onto it, and it stays
    const over = (await readout.boundingBox())!
    await page.mouse.move(over.x + over.width / 2, y, { steps: 6 })
    await expect(readout).toBeVisible()
    // persistent: it stays while the pointer rests
    await page.waitForTimeout(800)
    await expect(readout).toBeVisible()

    // dismissible: Escape takes it away without moving the pointer, and it stays away while the pointer rests
    await page.keyboard.press('Escape')
    await expect(readout).toHaveCount(0)
    await page.waitForTimeout(500)
    await expect(readout).toHaveCount(0)

    // a new move is a new hover
    await page.mouse.move(x + 60, y, { steps: 4 })
    await expect(readout).toBeVisible()
  })

  test('the forecast chart is one tab stop, steps through the hours by the arrow keys and zooms by +, - and 0', async ({ page, baseURL }) => {
    await mockBackend(page, baseURL!)
    await open(page, '/meteogram?station=01001', variant)
    await expect(forecastChart(page)).toBeVisible()
    const figure = page.getByRole('figure')
    await expect(figure).toHaveAttribute('tabindex', '0')
    await figure.focus()
    await page.keyboard.press('ArrowRight')
    await expect(page.getByTestId('meteogram-readout')).toBeVisible()
    await expect(page.getByTestId('meteogram-announce')).toHaveText(/\S/)
    await page.keyboard.press('+')
    await page.keyboard.press('0')
    await page.keyboard.press('Escape')
    await expect(page.getByTestId('meteogram-readout')).toHaveCount(0)
    await expect(figure).toBeFocused()
  })
})

// Page titles (WCAG 2.4.2): axe only asks that a page has one. Every page names itself, in the language
// of the page, and a screen reader is told so when a client-side navigation arrives at it.
test.describe('page titles', () => {
  test.describe.configure({ timeout: 120_000 })
  test.use({ locale: 'en-US' })

  test.beforeEach(async ({ context, baseURL }) => {
    await context.addCookies([{ name: 'wd_lang', value: 'en', url: baseURL! }])
  })

  test('every page has a title of its own', async ({ page, baseURL }) => {
    await mockBackend(page, baseURL!)
    const titles: Record<string, string> = {}
    for (const target of PAGES) {
      await open(page, target.path, { mode: 'light', locale: 'en' })
      if (target.ready)
        await target.ready(page, 'en')
      else
        await expect(page.getByRole('heading', { level: 1 }).first()).toBeVisible()
      titles[target.page] = await page.title()
    }
    expect(Object.values(titles).every(title => title.includes('Wetterdienst')), JSON.stringify(titles)).toBe(true)
    // the same title on two pages tells a reader of the tab strip or of the history nothing
    const duplicates = Object.entries(titles).filter(([, title], index, all) => all.findIndex(([, other]) => other === title) !== index)
    expect(duplicates, 'pages that share a title').toEqual([])
  })

  test('a navigation within the app changes the title and announces the page', async ({ page, baseURL }) => {
    await mockBackend(page, baseURL!)
    await open(page, '/', { mode: 'light', locale: 'en' })
    // the glossary is in the reference of the header, a disclosure (GH-3518)
    await page.getByRole('navigation').first().getByRole('button', { name: message('en', 'shell.reference') }).click()
    await page.getByRole('navigation').first().getByRole('link', { name: new RegExp(`^${message('en', 'nav.glossary')}`) }).click()
    await expect(page).toHaveTitle(`${message('en', 'glossary.title')} - Wetterdienst`)
    await expect(page.locator('.nuxt-route-announcer [aria-live]')).toHaveText(`${message('en', 'glossary.title')} - Wetterdienst`)
  })
})

// Reflow (WCAG 1.4.10): at 320 CSS pixels wide, the width of a phone and of a desktop window at 400 %
// zoom, a page needs no sideways scrolling. A table or a chart may scroll inside its own box; the page may not.
test.describe('reflow at 320 px', () => {
  test.use({ locale: 'en-US', viewport: { width: 320, height: 640 } })

  test.beforeEach(async ({ context, baseURL }) => {
    await context.addCookies([{ name: 'wd_lang', value: 'en', url: baseURL! }])
  })

  for (const target of PAGES) {
    test(`${target.page} does not scroll sideways`, async ({ page, baseURL }) => {
      await mockBackend(page, baseURL!)
      await open(page, target.path, { mode: 'light', locale: 'en' })
      if (target.ready)
        await target.ready(page, 'en')
      else
        await expect(page.getByRole('heading', { level: 1 }).first()).toBeVisible()
      const overflow = await page.evaluate(() => {
        const width = document.documentElement.clientWidth
        const wide = [...document.body.querySelectorAll('*')]
          .filter(node => node.getBoundingClientRect().right > width + 1 && node.getBoundingClientRect().width > 0)
          // what scrolls inside a box of its own does not widen the page
          .filter(node => !node.closest('.overflow-x-auto, .overflow-auto, .overflow-hidden, .leaflet-container, .xc-frame, .mg-scroller, [style*="overflow"]'))
          .slice(0, 5)
          .map(node => `${node.tagName.toLowerCase()}.${[...node.classList].slice(0, 3).join('.')} (${Math.round(node.getBoundingClientRect().right)} px)`)
        return { scrolls: document.documentElement.scrollWidth - width, wide }
      })
      expect(overflow.scrolls, `the page is wider than its window; wide: ${overflow.wide.join(', ')}`).toBeLessThanOrEqual(1)
    })
  }
})
