import type { Page } from '@playwright/test'
import type { Handlers } from './accessibility/mock-backend'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { expect, test } from '@playwright/test'
import { ApiFailure, defaultHandlers, mockBackend } from './accessibility/mock-backend'

// Text that does not fit in the languages whose words run long (GH-2610): German, Dutch, Polish,
// Luxembourgish, Czech, Low German, Italian and French (the last two scrolled sideways on the stripes and history
// pages, GH-3845). A string longer than its button, tab or table header either pushes the
// page sideways or spills out of its box, and that shows nowhere except in a browser, in the
// language that is too long. No screenshots: an element is an offender when its content is wider
// than it is (`scrollWidth > clientWidth`) and it does not scroll or truncate on purpose, and a
// page is when it scrolls sideways.
//
// The pages need no data to lay out their chrome, so this reads the home, explorer, stripes,
// meteogram, history, glossary, providers, settings, API, about, support, impressum and datenschutz pages as they come.
//
// Each page is loaded once and measured at every width.

const LONG_LANGUAGES = ['de', 'nl', 'lb', 'cs', 'pl', 'de-hh', 'it', 'fr'] as const
const PAGES = ['/', '/explorer', '/stripes', '/meteogram', '/history', '/map', '/glossary', '/providers', '/providers/dwd', '/settings', '/api', '/about', '/support', '/impressum', '/datenschutz']
// every language the app has, and the pages that failed at a phone's width (GH-3845, GH-3858)
const ALL_LANGUAGES = ['en', 'de', 'de-hh', 'fr', 'es', 'it', 'nl', 'pl', 'cs', 'da', 'lb'] as const
const OTHER_LANGUAGES = ALL_LANGUAGES.filter(language => !(LONG_LANGUAGES as readonly string[]).includes(language))
const REFLOW_PAGES = ['/stripes', '/history', '/settings']
const VIEWPORTS = [
  { name: 'desktop', width: 1280, height: 800 },
  // the narrowest window with the tools in the header (64 rem), where their names are tightest (GH-3518)
  { name: 'small desktop', width: 1024, height: 768 },
  { name: 'phone', width: 320, height: 844 },
]

/** The controls and headers a long label can overflow. */
const SELECTOR = 'button, [role="tab"], [role="option"], [role="menuitem"], th, label, h1, h2, h3, nav, nav a'

/** What overflows its box on the page as it is now, and the page itself when it scrolls sideways. */
function offendersOf(page: Page) {
  return page.evaluate((selector) => {
    const found: string[] = []
    const describe = (el: Element) => {
      const text = (el.textContent ?? '').trim().replace(/\s+/g, ' ').slice(0, 60)
      return `<${el.tagName.toLowerCase()}> "${text}" (${el.scrollWidth}px of ${el.clientWidth}px)`
    }
    for (const el of document.querySelectorAll(selector)) {
      const style = getComputedStyle(el)
      if (el.clientWidth === 0 || style.display === 'inline' || style.visibility === 'hidden')
        continue
      if (['auto', 'scroll'].includes(style.overflowX) || style.textOverflow === 'ellipsis')
        continue
      // a heading for a screen reader only (`sr-only`) is a box of one pixel by design, and shows nothing
      if (style.position === 'absolute' && el.clientWidth <= 1 && (style.clipPath === 'inset(50%)' || style.clip === 'rect(0px, 0px, 0px, 0px)'))
        continue
      if (el.scrollWidth > el.clientWidth + 1)
        found.push(describe(el))
    }
    const root = document.documentElement
    if (root.scrollWidth > root.clientWidth + 1)
      found.push(`the page scrolls sideways (${root.scrollWidth}px of ${root.clientWidth}px)`)
    return found
  }, SELECTOR)
}

LONG_LANGUAGES.forEach((language) => {
  test.describe(`${language}`, () => {
    for (const path of PAGES) {
      test(`${path} fits at ${VIEWPORTS.map(viewport => `${viewport.width}px`).join(' and ')}`, async ({ page, context, baseURL }) => {
        await context.addCookies([{ name: 'wd_lang', value: language, url: baseURL! }])
        await page.setViewportSize({ width: VIEWPORTS[0]!.width, height: VIEWPORTS[0]!.height })
        await page.goto(path)
        await page.waitForLoadState('load')
        // the app is client-rendered: the navigation is there once the first heading is
        await expect(page.locator('h1, h2').first()).toBeVisible({ timeout: 30_000 })
        // and what the pages build from the backend's answers (the selects, the station lists)
        // once the requests are through; the dev server's reload socket never lets the network
        // go idle, so the wait is bounded and the page measured as it is
        await page.waitForLoadState('networkidle', { timeout: 10_000 }).catch(() => {})

        for (const viewport of VIEWPORTS) {
          await page.setViewportSize({ width: viewport.width, height: viewport.height })
          // the layout settles after a resize on the next frame
          await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))))
          expect(await offendersOf(page), `${path} in ${language} on a ${viewport.name} (${viewport.width}px)`).toEqual([])
          // the pages that failed at a phone's width (GH-3845, GH-3858) are held to the box that clips as well
          if (viewport.width === 320 && REFLOW_PAGES.includes(path))
            expect(await reflowOffendersOf(page, path), `${path} in ${language} on a ${viewport.name} (${viewport.width}px)`).toEqual([])
        }
      })
    }
  })
})

// The pages of the tools and the settings in every language the app has, at 320 px (WCAG 1.4.10 Reflow, GH-3845,
// GH-3858). `offendersOf` sees what is wider than its own box and the page that scrolls; a card that clips its
// content (the unit selects of the settings, which ran past it in most languages) scrolls nothing and is no box
// that is wider than itself, so `protrudingOf` holds every element inside the box that clips it and inside the
// window, and `cutOf` a text that ends in an ellipsis where it is not meant to (a theme button's name).
// The long languages are measured on every page in the loop above, these pages included; the languages that are not
// among them are here, and the long ones that were tightest on the settings page at a phone's 390 px.
/** What passes the right edge of the window, or of the box that clips it, outside a box that scrolls on purpose. */
function protrudingOf(page: Page) {
  return page.evaluate(() => {
    const found: string[] = []
    const window_ = document.documentElement.clientWidth
    for (const el of document.querySelectorAll('body *')) {
      const box = el.getBoundingClientRect()
      const style = getComputedStyle(el)
      if (box.width === 0 || style.visibility === 'hidden' || style.position === 'fixed')
        continue
      // a heading for a screen reader only (`sr-only`) is a box of one pixel by design, and shows nothing
      if (style.position === 'absolute' && el.clientWidth <= 1 && (style.clipPath === 'inset(50%)' || style.clip === 'rect(0px, 0px, 0px, 0px)'))
        continue
      let limit = window_
      let stops = false
      for (let ancestor = el.parentElement; ancestor && ancestor !== document.documentElement; ancestor = ancestor.parentElement) {
        const ancestorStyle = getComputedStyle(ancestor)
        // a box that scrolls sideways, or truncates on purpose; `overflow-y` alone makes `overflow-x` compute to auto
        // too, and such a box that does not scroll clips like a hidden one
        if ((['auto', 'scroll'].includes(ancestorStyle.overflowX) && ancestor.scrollWidth > ancestor.clientWidth) || ancestorStyle.textOverflow === 'ellipsis') {
          stops = true
          break
        }
        if (['hidden', 'clip', 'auto', 'scroll'].includes(ancestorStyle.overflowX))
          limit = Math.min(limit, ancestor.getBoundingClientRect().right)
      }
      if (!stops && box.right > limit + 1) {
        const text = (el.textContent ?? '').trim().replace(/\s+/g, ' ').slice(0, 40)
        found.push(`<${el.tagName.toLowerCase()}> "${text}" (right edge ${Math.round(box.right)}px, limit ${Math.round(limit)}px)`)
      }
    }
    return found
  })
}

/** The texts that end in an ellipsis: on the settings page every name is read in full. */
function cutOf(page: Page) {
  return page.evaluate(() => [...document.querySelectorAll('body *')]
    .filter(el => getComputedStyle(el).textOverflow === 'ellipsis' && el.scrollWidth > el.clientWidth + 1)
    .map(el => `<${el.tagName.toLowerCase()}> "${(el.textContent ?? '').trim().replace(/\s+/g, ' ').slice(0, 40)}" (${el.scrollWidth}px of ${el.clientWidth}px)`))
}

/** What `protrudingOf` and, on the settings page, `cutOf` find. */
async function reflowOffendersOf(page: Page, path: string) {
  return [...await protrudingOf(page), ...(path === '/settings' ? await cutOf(page) : [])]
}

async function settle(page: Page) {
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))))
}

for (const language of OTHER_LANGUAGES) {
  for (const path of REFLOW_PAGES) {
    test(`${path} in ${language} does not scroll or clip sideways at 320px`, async ({ page, context, baseURL }) => {
      await context.addCookies([{ name: 'wd_lang', value: language, url: baseURL! }])
      await page.setViewportSize({ width: 320, height: 844 })
      await page.goto(path)
      await expect(page.locator('h1').first()).toBeVisible({ timeout: 30_000 })
      await page.waitForLoadState('networkidle', { timeout: 10_000 }).catch(() => {})
      await settle(page)
      expect(await offendersOf(page), `${path} in ${language} at 320px`).toEqual([])
      expect(await reflowOffendersOf(page, path), `${path} in ${language} at 320px`).toEqual([])
    })
  }
}

// The explorer with a parameter and a station chosen (GH-3985), before and after the values are fetched: its first state,
// which the loops above measure, has no station, no date range, no columns and no table, and these ran past the
// window at 320 px. The backend is the accessibility spec's mock, with 400 rows to fetch (eight pages, so that the
// pager is measured on a page that has a neighbour on both sides), and, for the lead time of the DWD's DMO
// (`dwd/dmo/icon`), a coverage that has that network.
const EXPLORER_WITH_SELECTION = '/explorer?provider=dwd&network=observation&resolution=daily&dataset=climate_summary&parameters=temperature_air_max_2m,temperature_air_mean_2m&mode=station&stations=00011'
const EXPLORER_WITH_LEAD_TIME = '/explorer?provider=dwd&network=dmo&resolution=hourly&dataset=icon&parameters=temperature_air_mean_2m&mode=station&stations=00011'

/** 400 daily values of station 00011, which the page lists fifty to a page */
const MANY_ROWS: Handlers = {
  values: () => ({
    values: Array.from({ length: 400 }, (_, index) => ({
      station_id: '00011',
      resolution: 'daily',
      dataset: 'climate_summary',
      parameter: 'temperature_air_mean_2m',
      timestamp: new Date(Date.UTC(2025, 0, 1 + index)).toISOString().replace('.000Z', '+00:00'),
      value: 10 + (index % 7),
      quality_flags: null,
    })),
  }),
}

/** The mock's coverage with the DMO's `icon` dataset added to its hourly resolution, and the network to the provider list */
function withDmo(): Handlers {
  const defaults = defaultHandlers()
  return {
    ...MANY_ROWS,
    providers: async (url, route) => {
      const answer = structuredClone(await defaults.providers!(url, route)) as { providers: Array<{ provider: string, networks: Array<{ network: string, kind: string }> }> }
      const dwd = answer.providers.find(provider => provider.provider === 'dwd')!
      dwd.networks.push({ ...dwd.networks.find(network => network.network === 'observation')!, network: 'dmo', kind: 'forecast' })
      return answer
    },
    coverage: async (url, route) => {
      const answer = await defaults.coverage!(url, route) as Record<string, any>
      const hourly = answer.hourly
      return { ...answer, hourly: { ...hourly, datasets: { ...hourly.datasets, icon: hourly.datasets.temperature_air } } }
    },
  }
}

/** The name of the Fetch button in `language`, as the app words it */
function fetchLabel(language: string): string {
  const catalog = JSON.parse(readFileSync(fileURLToPath(new URL(`../../i18n/locales/${language}.json`, import.meta.url)), 'utf-8'))
  return catalog.common.fetch
}

for (const language of ['en', ...LONG_LANGUAGES]) {
  for (const { name, path, handlers } of [
    { name: 'a station chosen', path: EXPLORER_WITH_SELECTION, handlers: MANY_ROWS },
    { name: 'a lead time offered', path: EXPLORER_WITH_LEAD_TIME, handlers: withDmo() },
  ]) {
    test(`/explorer with ${name} in ${language} does not scroll or clip sideways at 320px`, async ({ page, context, baseURL }) => {
      await mockBackend(page, baseURL!, handlers)
      await context.addCookies([{ name: 'wd_lang', value: language, url: baseURL! }])
      await page.setViewportSize({ width: 320, height: 844 })
      await page.goto(path)
      await expect(page.getByText('Donaueschingen').first()).toBeVisible({ timeout: 30_000 })
      if (path === EXPLORER_WITH_LEAD_TIME)
        await expect(page.getByTestId('lead-time')).toBeVisible()
      await page.waitForLoadState('networkidle', { timeout: 10_000 }).catch(() => {})
      await settle(page)
      expect(await offendersOf(page), `/explorer with ${name} in ${language} at 320px`).toEqual([])
      expect(await reflowOffendersOf(page, '/explorer'), `/explorer with ${name} in ${language} at 320px`).toEqual([])

      // and with the values: the options bar (columns, copy, download), the table and its pager, on page 3 of 8
      await page.getByRole('button', { name: fetchLabel(language), exact: true }).click()
      await expect(page.getByRole('table').first()).toBeVisible({ timeout: 30_000 })
      // two pages on: the pager has a neighbour on both sides, which is its widest state
      await page.locator('[data-slot="next"]').click()
      await page.locator('[data-slot="next"]').click()
      await settle(page)
      // the pager has no First and Last buttons below `sm`, and its seven buttons (the edges, the current page, the
      // ellipses and Previous/Next) are one line
      await expect(page.locator('[data-slot="first"]')).toBeHidden()
      expect(await page.locator('[data-slot="next"]').evaluate((next) => {
        const buttons = [...next.parentElement!.parentElement!.querySelectorAll('button')].filter(button => button.getBoundingClientRect().width > 0)
        return new Set(buttons.map(button => Math.round(button.getBoundingClientRect().top))).size
      }), `the pager of /explorer in ${language} at 320px stands in one line`).toBe(1)
      expect(await offendersOf(page), `/explorer with values in ${language} at 320px`).toEqual([])
      expect(await reflowOffendersOf(page, '/explorer'), `/explorer with values in ${language} at 320px`).toEqual([])
    })
  }
}

// The two-column layout (from 72 rem) gives the setup card a column of 368 px inside, where the lead time's row of
// buttons overflows in Polish and is close to the card's width in Czech, French and Luxembourgish: it stacks where it
// does not fit the card (a window-width rule missed this)
for (const language of ['pl', 'cs', 'fr', 'lb']) {
  test(`/explorer at 1152px has the lead time row inside its card in ${language}`, async ({ page, context, baseURL }) => {
    await mockBackend(page, baseURL!, withDmo())
    await context.addCookies([{ name: 'wd_lang', value: language, url: baseURL! }])
    await page.setViewportSize({ width: 1152, height: 900 })
    await page.goto(EXPLORER_WITH_LEAD_TIME)
    const card = page.getByTestId('lead-time')
    await expect(card).toBeVisible({ timeout: 30_000 })
    await settle(page)
    const outside = await card.evaluate((element) => {
      // the card's content box: the body that holds the buttons and the hint
      const limit = element.querySelector('.space-y-3')!.getBoundingClientRect().right
      return [...element.querySelectorAll('.space-y-3 *')].filter(el => el.getBoundingClientRect().right > limit + 1).map(el => `<${el.tagName.toLowerCase()}> "${(el.textContent ?? '').trim().slice(0, 30)}"`)
    })
    expect(outside, `the lead time card in ${language} at 1152px`).toEqual([])
    expect(await offendersOf(page), `/explorer in ${language} at 1152px`).toEqual([])
  })
}

// A phone of 390 px: the theme buttons of the settings share a row, and Polish and Czech names ("Systemowy",
// "Systémový") were cut where the buttons were as wide as each other and no wider than the row allowed
for (const language of ['pl', 'cs']) {
  test(`/settings in ${language} shows the theme buttons in full at 390px`, async ({ page, context, baseURL }) => {
    await context.addCookies([{ name: 'wd_lang', value: language, url: baseURL! }])
    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto('/settings')
    await expect(page.locator('h1').first()).toBeVisible({ timeout: 30_000 })
    await page.waitForLoadState('networkidle', { timeout: 10_000 }).catch(() => {})
    await settle(page)
    expect(await offendersOf(page), `/settings in ${language} at 390px`).toEqual([])
    expect(await reflowOffendersOf(page, '/settings'), `/settings in ${language} at 390px`).toEqual([])
  })
}

// The station picker's toggle and its map at a phone's 320 px, in the languages whose words run long (GH-3877): the toggle
// "List | Map", the map with its control beside the zoom buttons and the chips of the picked stations, none of which
// may push the page sideways or reach past its card. The mode is the one the picker remembers, set before the page loads.
const PICKER_PAGES = [
  '/explorer?provider=dwd&network=observation&resolution=daily&dataset=climate_summary&parameters=temperature_air_max_2m,temperature_air_mean_2m&mode=station&stations=00011',
  '/stripes?kind=temperature&station=00011',
  '/meteogram?station=01001',
]

LONG_LANGUAGES.forEach((language) => {
  for (const path of PICKER_PAGES) {
    test(`the station picker's map and toggle on ${path.split('?')[0]} in ${language} fit at 320px`, async ({ page, context, baseURL }) => {
      await mockBackend(page, baseURL!)
      await context.addCookies([{ name: 'wd_lang', value: language, url: baseURL! }])
      await page.addInitScript(() => localStorage.setItem('wd-station-picker', JSON.stringify({ explorer: 'map', stripes: 'map', forecast: 'map' })))
      await page.setViewportSize({ width: 320, height: 844 })
      await page.goto(path)
      await expect(page.locator('.leaflet-container')).toBeVisible({ timeout: 30_000 })
      await expect(page.locator('[data-testid="map-center"]')).toBeVisible()
      await expect(page.locator('[data-station-chip]').first()).toBeVisible()
      await settle(page)
      // The picker itself, not the page around it (the explorer's date range and result table have their own 320 px,
      // GH-3845): nothing of it overflows its box or reaches past the window. The map's tiles reach past its box by design.
      const offenders = await page.evaluate(() => {
        const root = document.querySelector('[data-testid="station-picker"]')!
        const found: string[] = []
        const window_ = document.documentElement.clientWidth
        for (const el of [root, ...root.querySelectorAll('*')]) {
          if (el.closest('.leaflet-container') || el.clientWidth === 0)
            continue
          const box = el.getBoundingClientRect()
          const name = `<${el.tagName.toLowerCase()}> "${(el.textContent ?? '').trim().replace(/\s+/g, ' ').slice(0, 40)}"`
          if (box.right > window_ + 1 || box.left < -1)
            found.push(`${name} reaches past the window (${Math.round(box.left)} to ${Math.round(box.right)}px)`)
          if (el.scrollWidth > el.clientWidth + 1 && getComputedStyle(el).display !== 'inline')
            found.push(`${name} is wider than its box (${el.scrollWidth}px of ${el.clientWidth}px)`)
        }
        return found
      })
      expect(offenders, `${path} in ${language} at 320px`).toEqual([])
    })
  }
})

// The forecast in each of its views, with the view control and, in the table, its header: the control's
// labels and the table's headers are the longest texts on the page. The backend is the accessibility
// spec's, answered in the browser.
const METEOGRAM_VIEWS = [
  { view: 'chart', ready: '.js-plotly-plot .main-svg' },
  { view: 'compact', ready: '[role="radio"][aria-checked="true"]' },
  { view: 'table', ready: 'table' },
] as const

LONG_LANGUAGES.forEach((language) => {
  for (const { view, ready } of METEOGRAM_VIEWS) {
    test(`the forecast's ${view} view in ${language} fits at ${VIEWPORTS.map(viewport => `${viewport.width}px`).join(' and ')}`, async ({ page, context, baseURL }) => {
      await mockBackend(page, baseURL!)
      await context.addCookies([{ name: 'wd_lang', value: language, url: baseURL! }])
      await page.setViewportSize({ width: VIEWPORTS[0]!.width, height: VIEWPORTS[0]!.height })
      await page.goto(`/meteogram?station=01001&view=${view}`)
      await expect(page.locator(ready).first()).toBeVisible({ timeout: 30_000 })
      // the toggle of the station picker above the forecast's views, and the views'
      await expect(page.getByRole('radiogroup')).toHaveCount(2)

      for (const viewport of VIEWPORTS) {
        await page.setViewportSize({ width: viewport.width, height: viewport.height })
        await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))))
        expect(await offendersOf(page), `the ${view} view in ${language} on a ${viewport.name} (${viewport.width}px)`).toEqual([])
      }
    })
  }
})

// The header with five tools (GH-3650) in every language the app has: Italian and French were the tightest, at 1024 and
// 1280 px (the settings button ended at 1033 and 1310 px with the fifth tab), where the header holds the search too.
// The page is measured as it first comes, with the typeface not yet there, which is the narrower of its two faces' margins.
test.describe('the header', () => {
  for (const language of ALL_LANGUAGES) {
    test(`holds the five tools, the reference, the search and the settings in ${language} at 1024 and 1280 px`, async ({ page, context, baseURL }) => {
      await context.addCookies([{ name: 'wd_lang', value: language, url: baseURL! }])
      await mockBackend(page, baseURL!)
      await page.goto('/history')
      await expect(page.locator('header .nav-tab').first()).toBeVisible({ timeout: 30_000 })
      for (const width of [1024, 1280]) {
        await page.setViewportSize({ width, height: 800 })
        await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))))
        const sizes = await page.evaluate(() => {
          const header = document.querySelector('header.app-header')!
          const last = [...header.querySelectorAll('button, a')].pop()!
          return { header: header.scrollWidth - header.clientWidth, page: document.documentElement.scrollWidth - document.documentElement.clientWidth, right: last.getBoundingClientRect().right, window: window.innerWidth }
        })
        expect(sizes.header, `the header in ${language} at ${width} px`).toBeLessThanOrEqual(0)
        expect(sizes.page, `the page in ${language} at ${width} px`).toBeLessThanOrEqual(0)
        expect(sizes.right, `the last control of the header in ${language} at ${width} px`).toBeLessThanOrEqual(sizes.window)
      }
    })
  }
})

// "Use my location" with a position stored (GH-4011): the "Stored" control stands beside the button, at once for a
// position that an earlier visit kept, and opens to the position and "Forget my position". The button and the control
// run side by side, so in the languages whose words run long they must wrap, not push the page sideways or spill out of
// the window at 320 px. The control is on the pages that have the button: Ask the weather, the map and the forecast's picker.
const POSITION_STORED = ['/', '/map', '/meteogram']

for (const language of ['en', ...LONG_LANGUAGES]) {
  for (const path of POSITION_STORED) {
    test(`${path} in ${language} with a position stored, closed and open, fits at 320px`, async ({ page, context, baseURL }) => {
      await mockBackend(page, baseURL!, {})
      await context.addCookies([{ name: 'wd_lang', value: language, url: baseURL! }])
      await context.addInitScript(() => localStorage.setItem('wd-location', JSON.stringify({ latitude: 53.54, longitude: 10.2 })))
      await page.setViewportSize({ width: 320, height: 844 })
      await page.goto(path)
      const chip = page.getByTestId('use-my-location-stored')
      await expect(chip).toBeVisible({ timeout: 30_000 })
      await page.waitForLoadState('networkidle', { timeout: 10_000 }).catch(() => {})
      await settle(page)

      const inWindow = async (testId: string) => page.getByTestId(testId).evaluate((el) => {
        const box = el.getBoundingClientRect()
        return box.left >= -1 && box.right <= document.documentElement.clientWidth + 1
      })
      expect(await offendersOf(page), `${path} in ${language} at 320px, closed`).toEqual([])
      expect(await inWindow('use-my-location-button'), `the button of ${path} in ${language}`).toBe(true)
      expect(await inWindow('use-my-location-stored'), `the control of ${path} in ${language}`).toBe(true)

      await chip.click()
      await expect(page.getByTestId('use-my-location-remembered')).toBeVisible()
      await settle(page)
      expect(await offendersOf(page), `${path} in ${language} at 320px, open`).toEqual([])
      expect(await inWindow('use-my-location-remembered'), `the popover of ${path} in ${language}`).toBe(true)
      expect(await inWindow('use-my-location-forget'), `Forget of ${path} in ${language}`).toBe(true)
    })
  }
}

// and on the map's station card, where the position's result is shown (GH-4011): the box and its note after a press, and
// the "Stored" control, closed and open, once the box is ticked
for (const language of ['en', ...LONG_LANGUAGES]) {
  test(`/map station card with the option to keep the position, then the Stored control, in ${language}, fits at 320px`, async ({ page, context, baseURL }) => {
    await mockBackend(page, baseURL!, {})
    await context.addCookies([{ name: 'wd_lang', value: language, url: baseURL! }])
    await context.grantPermissions(['geolocation'])
    await context.setGeolocation({ latitude: 53.5412, longitude: 10.1987 })
    await page.setViewportSize({ width: 320, height: 844 })
    await page.goto('/map')
    const press = page.getByTestId('use-my-location-button')
    await expect(press).toBeVisible({ timeout: 30_000 })
    await page.waitForLoadState('networkidle', { timeout: 10_000 }).catch(() => {})
    await press.click()
    const box = page.getByTestId('use-my-location-remember')
    await expect(box).toBeVisible({ timeout: 30_000 })
    await settle(page)
    expect(await offendersOf(page), `the card with the option in ${language} at 320px`).toEqual([])

    await box.click()
    const chip = page.getByTestId('use-my-location-stored')
    await expect(chip).toBeVisible()
    await chip.click()
    await expect(page.getByTestId('use-my-location-remembered')).toBeVisible()
    await settle(page)
    expect(await offendersOf(page), `the card with the Stored control open in ${language} at 320px`).toEqual([])
    const inside = await page.getByTestId('use-my-location-remembered').evaluate((el) => {
      const rect = el.getBoundingClientRect()
      return rect.left >= -1 && rect.right <= document.documentElement.clientWidth + 1
    })
    expect(inside, `the details on the card in ${language}`).toBe(true)
  })
}

// The banner of a provider the page is configured for but the backend does not offer (GH-4037): it is shown too when the
// list of providers cannot be read at all (an unreachable backend). It was `w-full` with a margin of 24 px on both sides,
// so it ran 24 px past the card's content at every width, 8 px past the window at 320 px. It stands where the fields
// stand: the same left and right edge as the first select, inside the window, at a phone's, a tablet's and a desktop's width.
function restrictionTitle(language: string): string {
  const catalog = JSON.parse(readFileSync(fileURLToPath(new URL(`../../i18n/locales/${language}.json`, import.meta.url)), 'utf-8'))
  return catalog.parameterSelection.providerRestrictionUnavailable.replace('{provider}', 'dwd')
}

for (const language of ['en', ...LONG_LANGUAGES]) {
  test(`/history with the backend's providers unreadable shows the banner of its provider within the fields' edges in ${language}`, async ({ page, context, baseURL }) => {
    const unreachable = () => new ApiFailure(503, 'Service Unavailable')
    await mockBackend(page, baseURL!, { providers: unreachable, coverage: unreachable })
    await context.addCookies([{ name: 'wd_lang', value: language, url: baseURL! }])
    await page.setViewportSize({ width: 320, height: 844 })
    await page.goto('/history')
    const title = page.getByText(restrictionTitle(language), { exact: true })
    await expect(title).toBeVisible({ timeout: 60_000 })
    for (const width of [320, 640, 1280]) {
      await page.setViewportSize({ width, height: 844 })
      await settle(page)
      const edges = await title.evaluate((el) => {
        const alert = el.closest('[data-slot="root"]')!.getBoundingClientRect()
        const field = document.querySelector('button[role="combobox"]')!.getBoundingClientRect()
        return { alertLeft: alert.left, alertRight: alert.right, fieldLeft: field.left, fieldRight: field.right, window: document.documentElement.clientWidth }
      })
      const where = `the banner of /history in ${language} at ${width}px`
      expect(Math.abs(edges.alertLeft - edges.fieldLeft), `${where}: left edge against the fields'`).toBeLessThanOrEqual(1)
      expect(Math.abs(edges.alertRight - edges.fieldRight), `${where}: right edge against the fields'`).toBeLessThanOrEqual(1)
      expect(edges.alertRight, `${where}: inside the window`).toBeLessThanOrEqual(edges.window)
      if (width === 320)
        expect(await offendersOf(page), where).toEqual([])
    }
  })
}
