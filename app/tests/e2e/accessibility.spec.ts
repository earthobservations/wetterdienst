import type { Handlers } from './accessibility/mock-backend'
import type { Locale, Mode, Variant } from './accessibility/scan'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { expect, test } from '@playwright/test'
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
      await page.getByRole('button', { name: message(locale, 'dataViewer.viewChart'), exact: true }).click()
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
    handlers: {
      coverage: () => ({
        noaa: {
          ghcn: {
            name_short: 'NOAA',
            country: 'United States Of America',
            kind: 'observation',
            url: 'https://noaa-ghcn-pds.s3.amazonaws.com/csv.gz/by_station/',
            auth: false,
            configured: false,
            date_required: false,
          },
        },
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
    keepFocus: true,
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
    page: 'stripes',
    state: 'table-shown',
    path: '/stripes?kind=temperature&station=00011',
    reach: async (page, locale) => {
      await page.getByRole('button', { name: message(locale, 'common.fetch'), exact: true }).click()
      await expect(plotly(page)).toBeVisible()
      await page.getByRole('button', { name: message(locale, 'dataViewer.viewTable'), exact: true }).click()
      await expect(page.getByRole('table')).toBeVisible()
    },
  },
  {
    page: 'meteogram',
    state: 'table-shown',
    path: '/meteogram?station=01001',
    reach: async (page, locale) => {
      await expect(plotly(page)).toBeVisible()
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
    keepFocus: true,
    path: '/',
    reach: async (page, locale) => {
      await page.getByRole('button', { name: message(locale, 'common.settings'), exact: true }).click()
      await expect(page.getByRole('dialog')).toBeVisible()
    },
  },
  {
    // the map's panel for a station: its forecast as day cards, and the links to its measurements and history
    page: 'index',
    state: 'station-panel',
    path: '/?station=10384',
    reach: async (page, locale) => {
      await expect(page.getByRole('heading', { level: 2, name: 'BERLIN-TEMPELHOF' })).toBeVisible()
      await expect(page.getByText(message(locale, 'meteogram.chart.today')).first()).toBeVisible()
      // the map's stations are dots on canvas tiles, not markers
      await expect(page.locator('.atlas-map canvas').first()).toBeVisible()
    },
  },
  {
    // the search of the header: a dialog with a combobox over the list of the pages, the settings and the stations
    page: 'index',
    state: 'search-open',
    keepFocus: true,
    path: '/',
    reach: async (page, locale) => {
      await page.getByRole('button', { name: message(locale, 'palette.open'), exact: true }).click()
      await expect(page.getByRole('combobox')).toBeFocused()
      // a query that finds a page and a station, so both groups are scanned
      await page.keyboard.type('ber')
      await expect(page.getByRole('listbox').getByRole('option', { name: /BERLIN-TEMPELHOF/ })).toBeVisible()
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
    const chosen = page.getByRole('button', { name: /Donaueschingen/ })
    await expect(chosen).toBeVisible()
    await expect(chosen).toBeFocused()
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
    await expect(plotly(page)).toBeVisible()

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

  // The map of the home page has no marker a keyboard reaches: its stations are chosen from the panel's list,
  // and a place from the centre of the map, which the arrow keys move (WCAG 2.1.1)
  test('a station of the map is chosen from its list by keys, and Back gives the focus to it again', async ({ page, baseURL }) => {
    await mockBackend(page, baseURL!)
    await open(page, '/', variant)
    const first = page.locator('.atlas-list-item').first()
    await expect(first).toBeVisible()
    const id = (await first.getAttribute('data-station-id'))!
    const name = (await first.locator('span span').first().textContent())!.trim()
    await first.focus()
    await page.keyboard.press('Enter')

    // the focus is on the station's name, which is announced as chosen
    await expect(page.getByRole('heading', { level: 2, name })).toBeFocused()
    await expect(page.locator('.atlas-panel [aria-live="polite"]')).toContainText(name)
    // and the panel has its forecast
    await expect(page.getByText(message('en', 'meteogram.chart.today')).first()).toBeVisible()

    await page.getByRole('button', { name: message('en', 'atlas.back') }).focus()
    await page.keyboard.press('Enter')
    await expect(page.locator(`[data-station-id="${id}"]`)).toBeFocused()
  })

  test('the place at the centre of the map is chosen by keys, after the arrow keys have moved the map', async ({ page, baseURL }) => {
    await mockBackend(page, baseURL!)
    await open(page, '/', variant)
    await expect(page.locator('.atlas-list-item').first()).toBeVisible()
    // the map moves by the arrow keys while it has the focus
    const map = page.locator('.atlas-map')
    await map.focus()
    const centre = () => page.evaluate(() => new URL(location.href).searchParams.toString())
    for (let step = 0; step < 6; step++)
      await page.keyboard.press('ArrowUp')
    await expect(map).toBeFocused()
    await page.getByRole('button', { name: message('en', 'atlas.pickCentre') }).focus()
    await page.keyboard.press('Enter')
    // the station nearest to the centre is chosen, with the focus on its name, and the address says which
    await expect(page.getByRole('heading', { level: 2 }).first()).toBeFocused()
    await expect.poll(centre).toMatch(/station=/)
    await expect(page.getByRole('button', { name: message('en', 'atlas.back') })).toBeVisible()
  })

  // The search of the header (WCAG 2.1.1, 2.1.2, 2.4.3, 4.1.2): the combobox pattern in a dialog
  test('the search opens by Ctrl+K, moves through its options by the arrow keys and opens a page by Enter', async ({ page, baseURL }) => {
    await mockBackend(page, baseURL!)
    await open(page, '/about', variant)
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
    await page.keyboard.press('Control+k')

    const dialog = page.getByRole('dialog')
    await expect(dialog).toBeVisible()
    await expect(dialog).toHaveAccessibleName(message('en', 'palette.title'))
    const combobox = page.getByRole('combobox')
    await expect(combobox).toBeFocused()
    const listbox = page.getByRole('listbox')
    await expect(combobox).toHaveAttribute('aria-controls', (await listbox.getAttribute('id'))!)
    await expect(combobox).toHaveAttribute('aria-expanded', 'true')

    // the active option is the one the field names, and the arrow keys move it while the focus stays in the field
    const activeOption = async () => {
      const id = await combobox.getAttribute('aria-activedescendant')
      return id ? page.locator(`[id="${id}"]`) : null
    }
    await expect((await activeOption())!).toHaveAttribute('aria-selected', 'true')
    const first = await combobox.getAttribute('aria-activedescendant')
    await page.keyboard.press('ArrowDown')
    await expect(combobox).not.toHaveAttribute('aria-activedescendant', first!)
    await expect(combobox).toBeFocused()

    await page.keyboard.type('glossary')
    await expect((await activeOption())!).toContainText(message('en', 'nav.glossary'))
    await page.keyboard.press('Enter')
    await expect(page).toHaveURL(/\/glossary$/)
    await expect(dialog).toBeHidden()
  })

  test('the search keeps the focus, closes by Escape and gives the focus back to its button', async ({ page, baseURL }) => {
    await mockBackend(page, baseURL!)
    await open(page, '/glossary', variant)
    // by label, not by role: while the dialog is open the page behind it is hidden from the accessibility tree
    const button = page.locator(`button[aria-label="${message('en', 'palette.open')}"]`)
    await button.focus()
    await page.keyboard.press('Enter')
    const dialog = page.getByRole('dialog')
    await expect(dialog).toBeVisible()
    await expect(button).toHaveAttribute('aria-expanded', 'true')
    for (let stop = 0; stop < 6; stop++) {
      await page.keyboard.press('Tab')
      expect(await dialog.evaluate(node => node.contains(document.activeElement))).toBe(true)
    }
    await page.keyboard.press('Escape')
    await expect(dialog).toBeHidden()
    await expect(button).toBeFocused()
  })

  test('the search finds a station and opens it on the map', async ({ page, baseURL }) => {
    await mockBackend(page, baseURL!)
    await open(page, '/glossary', variant)
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
    await page.keyboard.press('Control+k')
    await expect(page.getByRole('combobox')).toBeFocused()
    await page.keyboard.type('fuhlsbuettel')
    const option = page.getByRole('option', { name: /HAMBURG-FUHLSBUETTEL/ })
    await expect(option).toBeVisible()
    // the station is the only result: it is the active option
    await expect(option).toHaveAttribute('aria-selected', 'true')
    await page.keyboard.press('Enter')
    await expect(page).toHaveURL(/\/\?station=10147$/)
    await expect(page.getByRole('heading', { level: 2, name: 'HAMBURG-FUHLSBUETTEL' })).toBeVisible()
    await expect(page.locator('.atlas-panel [aria-live="polite"]')).toContainText('HAMBURG-FUHLSBUETTEL')
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

// Plotly's modebar (zoom, pan, reset) is the keyboard's way to move around a chart (WCAG 2.1.1). Its buttons
// are native buttons in the Plotly the app ships; this holds them to being so on an upgrade.
test.describe('chart controls by keyboard', () => {
  test.describe.configure({ timeout: 60_000 })
  const variant: Variant = { mode: 'light', locale: 'en' }

  test.beforeEach(async ({ context, baseURL }) => {
    await context.addCookies([{ name: 'wd_lang', value: 'en', url: baseURL! }])
  })

  test('the modebar of the stripes is reached by Tab, named, and operated by Enter and Space', async ({ page, baseURL }) => {
    await mockBackend(page, baseURL!)
    await open(page, '/stripes?kind=temperature&station=00011', variant)
    await page.getByRole('button', { name: message('en', 'common.fetch'), exact: true }).click()
    await expect(plotly(page)).toBeVisible()

    const buttons = page.locator('.js-plotly-plot .modebar-btn')
    const count = await buttons.count()
    expect(count).toBeGreaterThan(3)
    // every one is a control in the tab order with a name of its own
    const names = await buttons.evaluateAll(nodes => nodes.map(node => ({
      role: node.getAttribute('role') ?? node.tagName.toLowerCase(),
      tabindex: (node as HTMLElement).tabIndex,
      name: node.getAttribute('aria-label'),
    })))
    for (const button of names) {
      expect(['button', 'a']).toContain(button.role)
      expect(button.tabindex).toBeGreaterThanOrEqual(0)
      expect(button.name).toBeTruthy()
    }
    expect(new Set(names.map(button => button.name)).size).toBe(count)

    // Tab walks through the modebar, button by button in order, and on to the download menu after the chart
    const focusedName = () => page.evaluate(() => document.activeElement?.closest('.modebar') ? document.activeElement.getAttribute('aria-label') : null)
    await buttons.first().focus()
    const reached = [await focusedName()]
    for (let stop = 1; stop < count; stop++) {
      await page.keyboard.press('Tab')
      reached.push(await focusedName())
    }
    expect(reached).toEqual(names.map(button => button.name))
    // and on to the table of the values, below the chart
    await page.keyboard.press('Tab')
    await expect(page.getByRole('button', { name: message('en', 'dataViewer.viewTable'), exact: true })).toBeFocused()

    // "Pan" is a toggle: Enter turns it on, and the button says so by its class
    const pan = page.locator('.js-plotly-plot .modebar-btn[data-attr="dragmode"][data-val="pan"]')
    await pan.focus()
    await page.keyboard.press('Enter')
    await expect(pan).toHaveClass(/active/)
    // Reset axes by Space leaves the chart drawn
    await page.locator('.js-plotly-plot .modebar-btn[data-attr="zoom"][data-val="reset"]').focus()
    await page.keyboard.press('Space')
    await expect(plotly(page)).toBeVisible()
  })

  test('the modebar of the explorer\'s chart is in the tab order and named', async ({ page, baseURL }) => {
    await mockBackend(page, baseURL!)
    await open(page, EXPLORER_WITH_STATION, variant)
    await page.getByRole('button', { name: message('en', 'common.fetch'), exact: true }).click()
    await expect(page.getByRole('table').first()).toBeVisible()
    await page.getByRole('button', { name: message('en', 'dataViewer.viewChart'), exact: true }).click()
    await expect(plotly(page)).toBeVisible()

    // the buttons; the Plotly logo is a link, which its icon names
    const buttons = page.locator('.js-plotly-plot .modebar-btn:not(.modebar-btn--logo)')
    expect(await buttons.count()).toBeGreaterThan(3)
    const unreachable = await buttons.evaluateAll(nodes => nodes
      .filter(node => (node as HTMLElement).tabIndex < 0 || !node.getAttribute('aria-label'))
      .map(node => node.getAttribute('data-title') ?? node.outerHTML.slice(0, 80)))
    expect(unreachable, 'modebar buttons outside the tab order or without a name').toEqual([])
    // the first is reached by Tab, and takes the focus
    await buttons.first().focus()
    await expect(buttons.first()).toBeFocused()
  })

  // what the stripes and the forecast draw, in a table a keyboard and a screen reader read (WCAG 1.1.1, 1.3.1)
  for (const { page: name, path, ready } of [
    { page: 'stripes', path: '/stripes?kind=temperature&station=00011', ready: async (page: Page) => {
      await page.getByRole('button', { name: message('en', 'common.fetch'), exact: true }).click()
      await expect(plotly(page)).toBeVisible()
    } },
    { page: 'meteogram', path: '/meteogram?station=01001', ready: async (page: Page) => {
      await expect(plotly(page)).toBeVisible()
    } },
  ]) {
    test(`the chart of the ${name} page has its values as a table, opened and read by keys`, async ({ page, baseURL }) => {
      await mockBackend(page, baseURL!)
      await open(page, path, variant)
      await ready(page)

      // the chart is described by a sentence that exists, and the table is not in the page before it is asked for
      const figure = page.getByRole('figure')
      await expect(figure).toHaveAttribute('aria-describedby', /\S/)
      const described = (await figure.getAttribute('aria-describedby'))!
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

  // Plotly's hover label comes with the pointer and goes with it; Escape takes it away without moving the
  // pointer, until the pointer moves on (WCAG 1.4.13). Hoverable it cannot be, see utils/chart-hover.ts.
  test('the hover label of the forecast chart is dismissed by Escape, until the pointer moves', async ({ page, baseURL }) => {
    await mockBackend(page, baseURL!)
    await open(page, '/meteogram?station=01001', variant)
    await expect(plotly(page)).toBeVisible()

    // the chart lies below the fold of the window
    await page.locator('.js-plotly-plot').scrollIntoViewIfNeeded()
    const box = (await page.locator('.js-plotly-plot .main-svg').first().boundingBox())!
    const x = box.x + box.width / 2
    const y = box.y + box.height / 4
    const label = page.locator('.js-plotly-plot .hoverlayer')
    await page.mouse.move(x - 20, y)
    await page.mouse.move(x, y, { steps: 4 })
    await expect(label).toContainText(/\S/)
    await expect(label.locator('text').first()).toBeVisible()

    // focus is nowhere near the chart: the pointer is what Escape is about
    await page.keyboard.press('Escape')
    await expect(page.locator('.js-plotly-plot')).toHaveAttribute('data-hover-dismissed', 'true')
    await expect(label).toBeHidden()
    // it stays away while the pointer rests
    await page.waitForTimeout(500)
    await expect(label).toBeHidden()

    // a new move is a new hover
    await page.mouse.move(x + 40, y, { steps: 4 })
    await expect(page.locator('.js-plotly-plot')).not.toHaveAttribute('data-hover-dismissed', /.*/)
    await expect(label.locator('text').first()).toBeVisible()
  })

  test('the names of the modebar buttons on hover are dismissed by Escape too', async ({ page, baseURL }) => {
    await mockBackend(page, baseURL!)
    await open(page, '/stripes?kind=temperature&station=00011', variant)
    await page.getByRole('button', { name: message('en', 'common.fetch'), exact: true }).click()
    await expect(plotly(page)).toBeVisible()

    const button = page.locator('.js-plotly-plot .modebar-btn[data-attr="zoom"][data-val="reset"]')
    const nameShown = () => button.evaluate(node => getComputedStyle(node, '::after').display)
    await expect(button).toBeVisible()
    await button.hover()
    await expect.poll(nameShown).toBe('block')
    await page.keyboard.press('Escape')
    await expect.poll(nameShown).toBe('none')
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
    await page.getByRole('navigation').first().getByRole('link', { name: message('en', 'nav.glossary') }).click()
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
          .filter(node => !node.closest('.overflow-x-auto, .overflow-auto, .overflow-hidden, .leaflet-container, .js-plotly-plot, [style*="overflow"]'))
          .slice(0, 5)
          .map(node => `${node.tagName.toLowerCase()}.${[...node.classList].slice(0, 3).join('.')} (${Math.round(node.getBoundingClientRect().right)} px)`)
        return { scrolls: document.documentElement.scrollWidth - width, wide }
      })
      expect(overflow.scrolls, `the page is wider than its window; wide: ${overflow.wide.join(', ')}`).toBeLessThanOrEqual(1)
    })
  }
})
