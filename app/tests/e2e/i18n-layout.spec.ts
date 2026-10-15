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

const LONG_LANGUAGES = ['de', 'nl', 'lb', 'cs'] as const
const PAGES = ['/', '/explorer', '/stripes', '/meteogram', '/history', '/glossary', '/settings', '/api', '/about', '/support', '/impressum']
const VIEWPORTS = [
  { name: 'desktop', width: 1280, height: 800 },
  { name: 'phone', width: 320, height: 844 },
]

/** The controls and headers a long label can overflow. */
const SELECTOR = 'button, [role="tab"], [role="option"], [role="menuitem"], th, label, h1, h2, h3'

for (const language of LONG_LANGUAGES) {
  for (const viewport of VIEWPORTS) {
    test.describe(`${language} on a ${viewport.name}`, () => {
      test.use({ viewport: { width: viewport.width, height: viewport.height } })

      for (const path of PAGES) {
        test(`${path} fits`, async ({ page, context, baseURL }) => {
          await context.addCookies([{ name: 'wd_lang', value: language, url: baseURL! }])
          await page.goto(path)
          await page.waitForLoadState('load')
          // the app is client-rendered: the navigation is there once the first heading is
          await expect(page.locator('h1, h2').first()).toBeVisible({ timeout: 30_000 })
          // and what the pages build from the backend's answers (the selects, the station lists)
          // once the requests are through; the dev server's reload socket never lets the network
          // go idle, so the wait is bounded and the page measured as it is
          await page.waitForLoadState('networkidle', { timeout: 10_000 }).catch(() => {})

          const offenders = await page.evaluate((selector) => {
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

          expect(offenders, `${path} in ${language} at ${viewport.width}px`).toEqual([])
        })
      }
    })
  }
}
