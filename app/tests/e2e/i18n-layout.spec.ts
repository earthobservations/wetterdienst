import type { Page } from '@playwright/test'
import { expect, test } from '@playwright/test'
import { mockBackend } from './accessibility/mock-backend'

// Text that does not fit in the languages whose words run long (GH-2610): German, Dutch, Polish,
// Luxembourgish, Czech and Low German (which had no overflow on any page, with or without the map's). A string longer than its button, tab or table header either pushes the
// page sideways or spills out of its box, and that shows nowhere except in a browser, in the
// language that is too long. No screenshots: an element is an offender when its content is wider
// than it is (`scrollWidth > clientWidth`) and it does not scroll or truncate on purpose, and a
// page is when it scrolls sideways.
//
// The pages need no data to lay out their chrome, so this reads the home, explorer, stripes,
// meteogram, history, glossary, providers, settings, API, about, support, impressum and datenschutz pages as they come.
//
// Each page is loaded once and measured at every width.

const LONG_LANGUAGES = ['de', 'nl', 'lb', 'cs', 'pl', 'de-hh'] as const
const PAGES = ['/', '/explorer', '/stripes', '/meteogram', '/history', '/map', '/glossary', '/providers', '/providers/dwd', '/settings', '/api', '/about', '/support', '/impressum', '/datenschutz']
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
        }
      })
    }
  })
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
      await expect(page.getByRole('radiogroup')).toBeVisible()

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
const ALL_LANGUAGES = ['en', 'de', 'de-hh', 'fr', 'es', 'it', 'nl', 'pl', 'cs', 'da', 'lb'] as const
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
