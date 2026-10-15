import type { Page } from '@playwright/test'
import { expect, test } from '@playwright/test'

// Text that does not fit in the languages whose words run long (GH-2610): German, Dutch,
// Luxembourgish and Czech. A string longer than its button, tab or table header either pushes the
// page sideways or spills out of its box, and that shows nowhere except in a browser, in the
// language that is too long. No screenshots: an element is an offender when its content is wider
// than it is (`scrollWidth > clientWidth`) and it does not scroll or truncate on purpose, and a
// page is when it scrolls sideways.
//
// The pages need no data to lay out their chrome, so this reads the home, explorer, stripes,
// meteogram, history, glossary, settings, API, about, support and impressum pages as they come.
//
// The app server rate-limits by client address (nuxt-security: 150 requests per 5 minutes, and its
// own /api proxy counts), which the rest of the suite stays well under and 44 page loads of this one
// would not: the tests after it got "429 Too Many Requests" pages. So each language loads its pages
// as a client of its own (`x-forwarded-for`, which the limiter reads), and each page is loaded once
// and measured at both widths.

const LONG_LANGUAGES = ['de', 'nl', 'lb', 'cs'] as const
const PAGES = ['/', '/explorer', '/stripes', '/meteogram', '/history', '/glossary', '/settings', '/api', '/about', '/support', '/impressum']
const VIEWPORTS = [
  { name: 'desktop', width: 1280, height: 800 },
  { name: 'phone', width: 320, height: 844 },
]

/** The controls and headers a long label can overflow. */
const SELECTOR = 'button, [role="tab"], [role="option"], [role="menuitem"], th, label, h1, h2, h3'

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
      if (el.scrollWidth > el.clientWidth + 1)
        found.push(describe(el))
    }
    const root = document.documentElement
    if (root.scrollWidth > root.clientWidth + 1)
      found.push(`the page scrolls sideways (${root.scrollWidth}px of ${root.clientWidth}px)`)
    return found
  }, SELECTOR)
}

LONG_LANGUAGES.forEach((language, index) => {
  test.describe(`${language}`, () => {
    // 203.0.113.0/24 is documentation address space (RFC 5737)
    test.use({ extraHTTPHeaders: { 'x-forwarded-for': `203.0.113.${index + 10}` } })

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
