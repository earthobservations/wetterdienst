import type { Handlers } from './accessibility/mock-backend'
import type { Locale, Mode, Variant } from './accessibility/scan'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { expect, test } from '@playwright/test'
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

// every page of the app, as it is first shown
const PAGES: Target[] = [
  { page: 'index', path: '/' },
  { page: 'explorer', path: '/explorer' },
  { page: 'stripes', path: '/stripes' },
  { page: 'meteogram', path: '/meteogram' },
  { page: 'history', path: '/history' },
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
  { page: 'api', path: '/api' },
  { page: 'settings', path: '/settings' },
  { page: 'about', path: '/about' },
  { page: 'support', path: '/support' },
  { page: 'impressum', path: '/impressum' },
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
}

const EXPLORER = '/explorer?provider=dwd&network=observation&resolution=daily&dataset=climate_summary&parameters=temperature_air_max_2m,temperature_air_mean_2m&mode=station'
const EXPLORER_WITH_STATION = `${EXPLORER}&stations=00011`

/** The chart Plotly drew: its SVG is in the container once it has */
const plotly = (page: Page) => page.locator('.js-plotly-plot .main-svg').first()

/** A map with markers: Leaflet puts one icon, or a cluster, in the page for each */
async function mapWithStations(page: Page) {
  await expect(page.locator('.leaflet-marker-icon').first()).toBeVisible()
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
      await page.getByRole('button', { name: message(locale, 'stationSelection.chooseOnMap') }).click()
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
      // the view toggle's buttons have an icon and no name (which the scan reports), so the second is the chart
      await page.locator('div.rounded-lg.p-1 > button').nth(1).click()
      await expect(plotly(page)).toBeVisible()
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
      await expect(page.getByText(`${message(locale, 'history.stationIdPrefix')}: 00011`)).toBeVisible()
    },
  },
  {
    page: 'history',
    state: 'backend-lacks-provider',
    path: '/history',
    // the page is restricted to dwd/observation and says so where the backend has no dwd
    handlers: { coverage: () => ({ noaa: { ghcn: { auth: false, configured: false, valid: null, date_required: false } } }) },
    reach: async (page) => {
      await expect(page.getByRole('main').locator('[role="alert"], .text-error').first()).toBeVisible()
    },
  },
  {
    page: 'stripes',
    state: 'station-map',
    path: '/stripes',
    reach: async (page, locale) => {
      await page.getByRole('button', { name: message(locale, 'stripes.chooseOnMap') }).click()
      await mapWithStations(page)
    },
  },
  {
    page: 'stripes',
    state: 'chart-drawn',
    path: '/stripes?kind=temperature&station=00011',
    reach: async (page, locale) => {
      await page.getByRole('button', { name: message(locale, 'common.fetch'), exact: true }).click()
      await expect(plotly(page)).toBeVisible()
    },
  },
  {
    page: 'stripes',
    state: 'download-menu-open',
    path: '/stripes?kind=temperature&station=00011',
    reach: async (page, locale) => {
      await page.getByRole('button', { name: message(locale, 'common.fetch'), exact: true }).click()
      await expect(plotly(page)).toBeVisible()
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
      await expect(plotly(page)).toBeVisible()
    },
  },
  {
    page: 'meteogram',
    state: 'station-menu-open',
    path: '/meteogram',
    reach: async (page, locale) => {
      await page.getByText(message(locale, 'common.stationSearch')).click()
      await expect(page.getByRole('listbox').getByRole('option').first()).toBeVisible()
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
      await expect(plotly(page)).toBeVisible()
    },
  },
  {
    page: 'index',
    state: 'settings-popover-open',
    path: '/',
    reach: async (page, locale) => {
      await page.getByRole('button', { name: message(locale, 'common.settings'), exact: true }).click()
      await expect(page.getByRole('dialog')).toBeVisible()
    },
  },
  {
    page: 'index',
    state: 'mobile-menu-open',
    path: '/',
    viewport: { width: 390, height: 844 },
    reach: async (page, locale) => {
      await page.getByRole('button', { name: message(locale, 'header.menu'), exact: true }).click()
      await expect(page.getByRole('navigation').last()).toBeVisible()
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

// a chart page in a browser on a busy runner takes longer than Playwright's thirty seconds
test.describe.configure({ timeout: 60_000 })

const UNMOCKED = 'the page asked the backend for something the accessibility spec does not mock'

// an entry of a scan the spec no longer makes (a state renamed or dropped, a variant it is not
// scanned in) could never be found fixed, and so would stay in the baseline for ever
test('the baseline lists only scans this spec makes', () => {
  test.skip(RECORDING, 'the baseline is being rewritten')
  const planned = new Set([
    ...PAGES.flatMap(target => VARIANTS.map(variant => `${target.page}/first-paint/${variantKey(variant)}`)),
    ...STATES.flatMap(state => VARIANTS.filter(variant => STATE_VARIANTS.has(variantKey(variant))).map(variant => `${state.page}/${state.state}/${variantKey(variant)}`)),
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
