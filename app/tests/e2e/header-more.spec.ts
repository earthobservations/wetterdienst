import type { Page } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { expect, test } from '@playwright/test'
import { rowWidth } from '../../app/utils/header-fit'
import { mockBackend } from './accessibility/mock-backend'

// The tool tabs of the wide header that do not fit go into a "More" menu (GH-4500): measured in the browser in every language at every step of the
// header's width, so that the row never overflows, every tool is one click away, and the menu holds exactly the tabs that do not fit.

const LANGUAGES = ['en', 'de', 'de-hh', 'fr', 'es', 'it', 'nl', 'pl', 'cs', 'da', 'lb'] as const
const WIDTHS = [1024, 1280, 1440]
/** The tools in the order of the header, by their link */
const ORDER = ['/meteogram', '/explorer', '/stripes', '/radar', '/history', '/map', '/kostra']

const messages = (code: string) => JSON.parse(readFileSync(fileURLToPath(new URL(`../../i18n/locales/${code}.json`, import.meta.url)), 'utf-8'))

async function open(page: Page, baseURL: string, language: string, path = '/') {
  await page.context().addCookies([{ name: 'wd_lang', value: language, url: baseURL }])
  await mockBackend(page, baseURL)
  await page.goto(path)
  await expect(page.locator('html')).toHaveAttribute('lang', language)
  await expect(page.getByRole('heading', { level: 1 }).first()).toBeVisible()
  await expect(page.locator('nav.app-nav')).not.toHaveClass(/app-nav-pending/)
}

/** What the header measures its row from, and what it shows: the natural widths of the tabs, and the tabs in the row and in the menu */
function readHeader(page: Page) {
  return page.evaluate(() => {
    const nav = document.querySelector<HTMLElement>('nav.app-nav')!
    const layer = document.querySelector<HTMLElement>('.nav-measure')!
    const list = layer.querySelector<HTMLElement>('[data-measure="list"]')!
    const row = layer.querySelector<HTMLElement>('[data-measure="row"]')!
    const width = (el: Element) => el.getBoundingClientRect().width
    const tabs = [...nav.querySelectorAll<HTMLAnchorElement>('ul > li > a.nav-tab')].map(link => link.getAttribute('href')!)
    return {
      room: width(nav),
      navOverflows: nav.scrollWidth - nav.clientWidth,
      pageOverflows: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      natural: [...layer.querySelectorAll('[data-measure="tab"]')].map(width),
      gap: Number.parseFloat(getComputedStyle(list).columnGap) || 0,
      fixed: width(row) - width(list),
      more: width(layer.querySelector('[data-measure="more"]')!),
      tabs,
      hasMore: Boolean(nav.querySelector('[data-testid="nav-more-button"]')),
      // the row's own content, from the first tab to the end of the reference, and the room of the right-hand buttons beside it
      contentRight: Math.max(...[...nav.querySelectorAll('ul > li, button.nav-tab')].map(el => el.getBoundingClientRect().right)),
      navRight: nav.getBoundingClientRect().right,
      actionsLeft: nav.parentElement!.lastElementChild!.getBoundingClientRect().left,
    }
  })
}

for (const language of LANGUAGES) {
  test.describe(`the header's tabs in ${language}`, () => {
    for (const width of WIDTHS) {
      test(`fit the row at ${width}px, and the More menu holds exactly the tabs that do not`, async ({ page, baseURL }) => {
        await page.setViewportSize({ width, height: 800 })
        await open(page, baseURL!, language)
        const header = await readHeader(page)

        // every tool is one click away: the tabs of the row and the items of the menu are the seven, in the order of the header
        let inMenu: string[] = []
        if (header.hasMore) {
          await page.getByTestId('nav-more-button').click()
          inMenu = await page.getByTestId('nav-more-panel').locator('a').evaluateAll(links => links.map(link => link.getAttribute('href')!))
          await page.keyboard.press('Escape')
        }
        expect([...header.tabs, ...inMenu], `${language} at ${width}px`).toEqual(ORDER)

        // nothing overflows: not the row, not the page, and the row ends before the buttons of the right
        expect(header.navOverflows, 'the row').toBeLessThanOrEqual(1)
        expect(header.pageOverflows, 'the page').toBeLessThanOrEqual(0)
        expect(header.contentRight, 'the row ends before the search').toBeLessThanOrEqual(header.actionsLeft + 0.5)

        // the menu holds exactly what does not fit: the row as it is fits the room, and one tab more would not (the button is gone where all seven are in)
        const shown = header.tabs.length
        const widths = { widths: header.natural, gap: header.gap, fixed: header.fixed, more: header.more }
        expect(rowWidth(widths, shown, shown < 7), 'the row as it is fits the room').toBeLessThanOrEqual(header.room + 0.5)
        if (shown < 7) {
          expect(header.hasMore, 'tabs that go have a menu').toBe(true)
          expect(rowWidth(widths, shown + 1, shown + 1 < 7), 'the next tab would not fit').toBeGreaterThan(header.room + 0.5)
        }
        else {
          expect(header.hasMore, 'no menu where every tab fits').toBe(false)
        }
      })
    }
  })
}

test.describe('the More menu', () => {
  test.use({ viewport: { width: 1024, height: 800 } })

  test('is a disclosure as the reference is: a button that says it is open, Escape closes it with the focus on the button, a link in it goes to its tool', async ({ page, baseURL }) => {
    await open(page, baseURL!, 'it')
    const button = page.getByTestId('nav-more-button')
    await expect(button).toBeVisible()
    await expect(button).toHaveText(messages('it').shell.more)
    await expect(button).toHaveAttribute('aria-expanded', 'false')
    await button.focus()
    await page.keyboard.press('Enter')
    await expect(button).toHaveAttribute('aria-expanded', 'true')
    const panel = page.getByTestId('nav-more-panel')
    await expect(panel).toBeVisible()
    // Tab walks into it, in the order it shows
    await page.keyboard.press('Tab')
    await expect(panel.getByRole('link').first()).toBeFocused()
    await page.keyboard.press('Escape')
    await expect(panel).toBeHidden()
    await expect(button).toBeFocused()
    // a click outside closes it too
    await button.click()
    await expect(panel).toBeVisible()
    await page.mouse.click(5, 400)
    await expect(panel).toBeHidden()
    // and a link goes to its tool and closes it
    await button.click()
    await panel.getByRole('link', { name: new RegExp(messages('it').nav.kostra) }).click()
    await expect(page).toHaveURL(/\/kostra$/)
    await expect(panel).toBeHidden()
  })

  test('marks its button as the tab of the page is marked where the page is a tool in it, and says which in its panel', async ({ page, baseURL }) => {
    await open(page, baseURL!, 'it', '/kostra')
    const button = page.getByTestId('nav-more-button')
    await expect(button).toHaveAttribute('data-current', 'true')
    // the same bar under it as under a tab's: the tab's marking is drawn on `data-current` too
    const bar = await button.evaluate(el => getComputedStyle(el, '::after').content)
    expect(bar).not.toBe('none')
    await button.click()
    await expect(page.getByTestId('nav-more-panel').locator('a[href="/kostra"]')).toHaveAttribute('aria-current', 'page')
    // and a tool whose tab is in the row does not mark it
    await page.keyboard.press('Escape')
    await page.goto('/explorer')
    await expect(page.getByTestId('nav-more-button')).not.toHaveAttribute('data-current', 'true')
  })

  test('is measured again where the window is resized: the tabs that are in the row change with the width, and no step of it overflows', async ({ page, baseURL }) => {
    await page.setViewportSize({ width: 1440, height: 800 })
    await open(page, baseURL!, 'fr')
    const count = async () => (await readHeader(page)).tabs.length
    const wide = await count()
    // the tiles are left out of the tabs below 80 rem and the search's word below 90 rem, so the room is another and the tabs are narrower: more of them are in the row
    await page.setViewportSize({ width: 1024, height: 800 })
    await expect.poll(count).not.toBe(wide)
    const narrow = await readHeader(page)
    expect(narrow.navOverflows).toBeLessThanOrEqual(1)
    expect(narrow.contentRight).toBeLessThanOrEqual(narrow.actionsLeft + 0.5)
    await page.setViewportSize({ width: 1440, height: 800 })
    await expect.poll(count).toBe(wide)
    const back = await readHeader(page)
    expect(back.navOverflows).toBeLessThanOrEqual(1)
    expect(back.contentRight).toBeLessThanOrEqual(back.actionsLeft + 0.5)
  })

  test('is measured again where the reader changes the order of the tools: the tools at the end of the list are the ones in it', async ({ page, baseURL }) => {
    await page.addInitScript(() => localStorage.setItem('wd_settings', JSON.stringify({ version: 2, tabBar: ['kostra', 'map', 'history', 'radar', 'stripes', 'explorer', 'forecast'] })))
    await open(page, baseURL!, 'it')
    const header = await readHeader(page)
    expect(header.tabs[0]).toBe('/kostra')
    expect(header.hasMore).toBe(true)
    await page.getByTestId('nav-more-button').click()
    const inMenu = await page.getByTestId('nav-more-panel').locator('a').evaluateAll(links => links.map(link => link.getAttribute('href')!))
    expect([...header.tabs, ...inMenu]).toEqual(['/kostra', '/map', '/history', '/radar', '/stripes', '/explorer', '/meteogram'])
  })

  test('does not jump on load: the row is not seen until it is measured, and what is seen is never a row that changes', async ({ page, baseURL }) => {
    await page.addInitScript(() => {
      const frames: Array<[string, number, boolean]> = []
      ;(window as any).__headerFrames = frames
      const tick = () => {
        const nav = document.querySelector('nav.app-nav')
        if (nav)
          frames.push([getComputedStyle(nav).visibility, nav.querySelectorAll('ul a').length, Boolean(nav.querySelector('[data-testid="nav-more-button"]'))])
        requestAnimationFrame(tick)
      }
      requestAnimationFrame(tick)
    })
    await open(page, baseURL!, 'it')
    await page.waitForTimeout(500)
    const frames: Array<[string, number, boolean]> = await page.evaluate(() => (window as any).__headerFrames)
    const seen = frames.filter(([visibility]) => visibility === 'visible')
    expect(seen.length).toBeGreaterThan(0)
    expect(new Set(seen.map(([, links, more]) => `${links}/${more}`)).size, 'every frame in which the row is seen shows the same tabs').toBe(1)
  })
})

/** Records, on every frame, whether the row of tabs is seen and which tabs it has (a script of the page, from before its first script) */
async function recordFrames(page: Page) {
  await page.addInitScript(() => {
    const frames: Array<[string, string]> = []
    ;(window as any).__headerFrames = frames
    const tick = () => {
      const nav = document.querySelector('nav.app-nav')
      if (nav)
        frames.push([getComputedStyle(nav).visibility, [...nav.querySelectorAll('ul a, [data-testid="nav-more-button"]')].map(el => el.getAttribute('href') ?? 'more').join(' ')])
      requestAnimationFrame(tick)
    }
    requestAnimationFrame(tick)
  })
}
const framesOf = (page: Page): Promise<Array<[string, string]>> => page.evaluate(() => (window as any).__headerFrames)

test.describe('the tabs where a font comes late', () => {
  // the tabs are as wide as the letters of the face they are set in, and the latin-ext subset of it (cs, pl, lb) is a request of its own: the row is not
  // seen until the faces are in (at most a second), so that what is seen is what stays
  for (const language of ['cs', 'pl', 'lb', 'it'] as const) {
    for (const width of WIDTHS) {
      test(`never changes its tabs once it is seen, in ${language} at ${width}px, with the typefaces 600 ms late`, async ({ page, baseURL }) => {
        await page.setViewportSize({ width, height: 800 })
        await page.route('**/_typefaces/**', async (route) => {
          await new Promise(resolve => setTimeout(resolve, 600))
          await route.continue()
        })
        await recordFrames(page)
        await open(page, baseURL!, language)
        await page.waitForTimeout(1500)
        const seen = (await framesOf(page)).filter(([visibility]) => visibility === 'visible').map(([, tabs]) => tabs)
        expect(seen.length).toBeGreaterThan(0)
        expect([...new Set(seen)], 'every frame in which the row is seen has the same tabs').toHaveLength(1)
        // and they are the tabs the settled row has
        const settled = await readHeader(page)
        expect(seen.at(-1)!.split(' ').filter(item => item !== 'more')).toEqual(settled.tabs)
      })
    }
  }
})

test.describe('the More menu and the focus', () => {
  test.use({ viewport: { width: 1280, height: 800 } })

  test('goes to the tab that takes its place where a resize makes every tab fit while the focus is on the button', async ({ page, baseURL }) => {
    await open(page, baseURL!, 'en')
    const button = page.getByTestId('nav-more-button')
    await expect(button).toBeVisible()
    await button.focus()
    await page.setViewportSize({ width: 1024, height: 800 })
    await expect(button).toHaveCount(0)
    const href = await page.evaluate(() => document.activeElement?.getAttribute('href') ?? null)
    expect(href, 'the focus is on a tab of the row, not on the page').toBe('/kostra')
  })
})

test.describe('the narrow layout', () => {
  test.use({ viewport: { width: 390, height: 844 } })

  test('has no More menu in its header: the tab bar and the Menu are as they were', async ({ page, baseURL }) => {
    await open(page, baseURL!, 'it')
    await expect(page.getByTestId('nav-more-button')).toBeHidden()
    const bar = page.getByRole('navigation', { name: messages('it').shell.mainNav })
    expect(await bar.locator('li').count()).toBe(5)
  })

  test('has no row to measure: the copy of the header\'s tabs is not laid out, and the page does not scroll sideways', async ({ page, baseURL }) => {
    await open(page, baseURL!, 'cs')
    expect(await page.locator('.nav-measure').evaluate(el => getComputedStyle(el).display)).toBe('none')
    expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(0)
  })
})
