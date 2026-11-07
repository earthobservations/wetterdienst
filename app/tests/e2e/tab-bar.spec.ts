import type { Locator, Page } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { expect, test } from '@playwright/test'
import { mockBackend } from './accessibility/mock-backend'

// The choice of the four tools in the phone's tab bar (GH-3846) and the Menu's mark on the pages of its sheet
// (GH-3851), in a browser: the list with its line and the preview of the bar, drag by the handle with the mouse (and,
// in Chromium, by touch), the arrow buttons that do what dragging does (WCAG 2.5.7, 2.1.1) with their status and
// their focus, that the choice is kept across a reload, that a storage that fails or holds nonsense leaves the app
// working with the default, and that the Menu is marked on every page that is in its sheet. At 390 and 320 px, light
// and dark. The backend is the accessibility spec's mock, so nothing here reaches a provider.

const LOCALES = ['cs', 'da', 'de-hh', 'de', 'en', 'es', 'fr', 'it', 'lb', 'nl', 'pl']
const messages = Object.fromEntries(LOCALES.map(code => [code, JSON.parse(readFileSync(fileURLToPath(new URL(`../../i18n/locales/${code}.json`, import.meta.url)), 'utf-8'))]))
const en = messages.en

const DEFAULT_ORDER = ['forecast', 'explorer', 'stripes', 'history', 'map']
const WITH_MAP = ['map', 'forecast', 'explorer', 'stripes', 'history']
const NAMES: Record<string, string> = { forecast: en.nav.meteogram, explorer: en.nav.explorer, stripes: en.nav.stripes, history: en.nav.history, map: en.nav.map }

type Mode = 'light' | 'dark'

interface Options {
  language?: string
  mode?: Mode
  /** What `wd_settings` holds before the page starts, when it is not the default */
  settings?: unknown
  /** A localStorage that throws, as a browser does with its storage blocked */
  blockedStorage?: boolean
}

async function open(page: Page, baseURL: string, path: string, options: Options = {}) {
  const { language = 'en', mode = 'light', settings, blockedStorage } = options
  await page.context().addCookies([{ name: 'wd_lang', value: language, url: baseURL }])
  await page.addInitScript(({ mode, settings, blockedStorage }) => {
    if (blockedStorage) {
      const refuse = () => {
        throw new DOMException('The operation is insecure.', 'SecurityError')
      }
      Object.defineProperty(window, 'localStorage', { configurable: true, get: refuse })
      return
    }
    // an init script runs on every load: the first one writes the state, a reload keeps what the page has stored since
    if (!sessionStorage.getItem('e2e-seeded')) {
      sessionStorage.setItem('e2e-seeded', '1')
      localStorage.setItem('nuxt-color-mode', mode)
      if (settings !== undefined)
        localStorage.setItem('wd_settings', typeof settings === 'string' ? settings : JSON.stringify(settings))
    }
  }, { mode, settings, blockedStorage })
  await mockBackend(page, baseURL)
  await page.goto(path)
  await expect(page.locator('html')).toHaveAttribute('lang', language)
  // the first page of a dev server's run is compiled on request
  await expect(page.getByRole('heading', { level: 1 }).first()).toBeVisible({ timeout: 20_000 })
}

/** A settings blob of the current version with the order of the bar given */
function settingsWith(tabBar: unknown) {
  return {
    version: 1,
    friendlyLabels: true,
    convertUnits: true,
    units: {},
    stripes: { showTitle: true, showYears: true, showSource: true, showDataAvailability: true, showTimeseries: false, showTrendline: false },
    tabBar,
  }
}

const bar = (page: Page) => page.locator('.app-tabbar')
const barTexts = (page: Page) => bar(page).locator('li').allInnerTexts()
const menuTab = (page: Page) => bar(page).getByRole('button', { name: en.header.menu, exact: true })
const chooser = (page: Page) => page.getByTestId('bar-chooser')
const row = (page: Page, tool: string) => chooser(page).locator(`li[data-row][data-tool="${tool}"]`)
const handle = (page: Page, tool: string) => row(page, tool).getByTestId('bar-handle')
const move = (page: Page, tool: string, dir: 'up' | 'down') => row(page, tool).locator(`button[data-dir="${dir}"]`)
const previewTexts = (page: Page) => chooser(page).getByTestId('bar-preview').locator('[data-preview-tool]').allInnerTexts()
const status = (page: Page) => chooser(page).getByTestId('bar-status')
const stored = (page: Page) => page.evaluate(() => JSON.parse(localStorage.getItem('wd_settings') ?? 'null')?.tabBar ?? null)
const names = (order: string[]) => order.map(tool => NAMES[tool]!)

/** Scrolls the list to where all of it is clear of the header, the sticky preview and the tab bar */
async function showList(page: Page) {
  await chooser(page).getByTestId('bar-group-bar').scrollIntoViewIfNeeded()
  await page.evaluate(() => {
    const top = document.querySelector('[data-testid="bar-group-bar"]')!.getBoundingClientRect().top
    window.scrollBy(0, top - 200)
  })
  await page.waitForTimeout(100)
}

/** The middle of an element, in the window */
async function middle(locator: Locator) {
  const box = (await locator.boundingBox())!
  return { x: box.x + box.width / 2, y: box.y + box.height / 2 }
}

/** Presses on the handle of `tool`, moves to the middle of `target`'s row and, with `drop`, lets go */
async function drag(page: Page, tool: string, target: string, { drop = true, below = 0 }: { drop?: boolean, below?: number } = {}) {
  const from = await middle(handle(page, tool))
  const to = await middle(row(page, target))
  await page.mouse.move(from.x, from.y)
  await page.mouse.down()
  await page.mouse.move(to.x, to.y + below, { steps: 12 })
  if (drop)
    await page.mouse.up()
}

/**
 * Walks the focus over the buttons of the list and the Reset button by Tab, and back by Shift+Tab: in the order of the
 * list, each one in the window and with nothing standing over it (sampled at the middle and the corners), which is what
 * the preview that stays under the header would be, for a button that was scrolled to from below
 */
async function walkFocus(page: Page) {
  const look = () => page.evaluate(() => {
    const el = document.activeElement as HTMLElement
    const box = el.getBoundingClientRect()
    const points = [[0.5, 0.5], [0.1, 0.1], [0.9, 0.1], [0.1, 0.9], [0.9, 0.9]].map(([x, y]) => document.elementFromPoint(box.left + box.width * x!, box.top + box.height * y!))
    return {
      label: el.getAttribute('aria-label') ?? el.textContent!.trim(),
      visible: box.top >= 0 && box.bottom <= window.innerHeight,
      obscured: points.filter(point => point !== el && !el.contains(point)).length,
    }
  })
  const walk = async (key: 'Tab' | 'Shift+Tab', stops: number) => {
    const labels: string[] = []
    for (let stop = 0; stop < stops; stop++) {
      const state = await look()
      labels.push(state.label)
      expect(state.visible, state.label).toBe(true)
      expect(state.obscured, `${state.label} is covered (${key})`).toBe(0)
      if (stop < stops - 1)
        await page.keyboard.press(key)
    }
    return labels
  }
  const forward = [...DEFAULT_ORDER.flatMap(tool => [`Move ${NAMES[tool]} up`, `Move ${NAMES[tool]} down`]), en.settings.bar.reset]
  await move(page, 'forecast', 'up').focus()
  expect(await walk('Tab', forward.length)).toEqual(forward)
  // one stop past the list, and back: Reset is then scrolled to from below, which is where the preview would cover it
  await page.keyboard.press('Tab')
  await page.keyboard.press('Shift+Tab')
  expect(await walk('Shift+Tab', forward.length)).toEqual([...forward].reverse())
}

const SIZES = [
  { width: 390, height: 844 },
  { width: 320, height: 640 },
]

for (const size of SIZES) {
  for (const mode of ['light', 'dark'] as const) {
    test.describe(`the chooser at ${size.width} px, ${mode}`, () => {
      test.use({ viewport: size })

      test('lists the tools above and below the line, with a preview of the bar, and no sideways scroll', async ({ page, baseURL }) => {
        await open(page, baseURL!, '/settings', { mode })
        await expect(page.locator('html')).toHaveClass(mode === 'dark' ? /dark/ : /^((?!dark).)*$/)
        await expect(chooser(page).locator('h3')).toHaveText([en.settings.bar.inBar, en.settings.bar.inMenu])
        await expect(chooser(page).getByTestId('bar-group-bar').locator('li')).toHaveCount(4)
        await expect(chooser(page).getByTestId('bar-group-menu').locator('li')).toHaveCount(1)
        expect(await previewTexts(page)).toEqual(names(DEFAULT_ORDER.slice(0, 4)))
        await expect(chooser(page).getByTestId('bar-preview')).toHaveAttribute('aria-label', `Preview of the bar: ${names(DEFAULT_ORDER.slice(0, 4)).join(', ')}, Menu`)
        // the line is drawn between the two lists
        const line = await chooser(page).getByTestId('bar-group-menu').evaluate(node => getComputedStyle(node).borderTopStyle)
        expect(line).toBe('dashed')
        expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(0)
        // no part of the card reaches past the window
        const overflow = await chooser(page).evaluate((node) => {
          const width = document.documentElement.clientWidth
          return [...node.querySelectorAll('*')].filter(el => el.getBoundingClientRect().right > width + 1).map(el => el.className)
        })
        expect(overflow).toEqual([])
      })

      test('has a handle and two buttons on every row that are larger than 24 px (2.5.8), with a name for each button', async ({ page, baseURL }) => {
        await open(page, baseURL!, '/settings', { mode })
        const targets = await chooser(page).evaluate(node => [...node.querySelectorAll('[data-testid="bar-handle"], button.bar-move')].map((el) => {
          const box = el.getBoundingClientRect()
          return { kind: el.getAttribute('data-testid') ?? 'button', width: box.width, height: box.height, label: el.getAttribute('aria-label') }
        }))
        expect(targets).toHaveLength(15)
        for (const target of targets) {
          expect(target.width, JSON.stringify(target)).toBeGreaterThanOrEqual(24)
          expect(target.height, JSON.stringify(target)).toBeGreaterThanOrEqual(24)
        }
        // the app's own measure is 40 px, which is room for a thumb
        for (const target of targets.filter(item => item.kind === 'button')) {
          expect(target.width).toBeGreaterThanOrEqual(40)
          expect(target.height).toBeGreaterThanOrEqual(40)
          expect(target.label).toMatch(/^Move .+ (up|down)$/)
        }
        // the handle is for the pointer only: no stop, nothing read out
        await expect(chooser(page).getByTestId('bar-handle').first()).toHaveAttribute('aria-hidden', 'true')
      })

      test('moves a tool by dragging its handle: the preview follows the pointer, the move is made on the drop and kept after a reload', async ({ page, baseURL }) => {
        await open(page, baseURL!, '/settings', { mode })
        await showList(page)
        await drag(page, 'map', 'explorer', { drop: false })
        // while the pointer is down: the list stays, the row it lands on is marked, the preview is the bar after the drop
        expect(await previewTexts(page)).toEqual(names(['forecast', 'map', 'explorer', 'stripes']))
        await expect(row(page, 'map')).toHaveAttribute('data-dragging', '')
        await expect(row(page, 'explorer')).toHaveAttribute('data-drop', 'before')
        await expect(chooser(page).getByTestId('bar-preview-menu')).toHaveText(`Only in the Menu: ${en.nav.history}`)
        // the preview is in view while the list is dragged
        await expect(chooser(page).getByTestId('bar-preview')).toBeInViewport({ ratio: 1 })
        expect(await barTexts(page)).toEqual([...names(DEFAULT_ORDER.slice(0, 4)), en.header.menu])
        await page.mouse.up()
        await expect(status(page)).toHaveText(`${en.nav.map} is now in the bar, at place 2 of 4. ${en.nav.history} is now only in the Menu.`)
        expect(await stored(page)).toEqual(['forecast', 'map', 'explorer', 'stripes', 'history'])
        // the bar at the foot of the window is the one the preview showed
        expect(await barTexts(page)).toEqual([...names(['forecast', 'map', 'explorer', 'stripes']), en.header.menu])
        await expect(row(page, 'history')).toBeVisible()
        await expect(chooser(page).getByTestId('bar-group-menu').locator('li')).toHaveCount(1)
        // kept across a load
        await page.reload()
        await expect(chooser(page)).toBeVisible()
        expect(await barTexts(page)).toEqual([...names(['forecast', 'map', 'explorer', 'stripes']), en.header.menu])
        expect(await previewTexts(page)).toEqual(names(['forecast', 'map', 'explorer', 'stripes']))
        expect(await stored(page)).toEqual(['forecast', 'map', 'explorer', 'stripes', 'history'])
      })

      test('moves a tool out of the bar by dragging it below the line, and cancels a drag on Escape', async ({ page, baseURL }) => {
        await open(page, baseURL!, '/settings', { mode })
        await showList(page)
        await drag(page, 'forecast', 'map', { drop: false, below: 10 })
        expect(await previewTexts(page)).toEqual(names(['explorer', 'stripes', 'history', 'map']))
        await expect(row(page, 'map')).toHaveAttribute('data-drop', 'after')
        await page.keyboard.press('Escape')
        await page.mouse.up()
        await expect(chooser(page).locator('[data-dragging]')).toHaveCount(0)
        expect(await previewTexts(page)).toEqual(names(DEFAULT_ORDER.slice(0, 4)))
        expect(await stored(page)).toEqual(DEFAULT_ORDER)
        // the same drag, let go
        await drag(page, 'forecast', 'map', { below: 10 })
        expect(await stored(page)).toEqual(['explorer', 'stripes', 'history', 'map', 'forecast'])
        expect(await barTexts(page)).toEqual([...names(['explorer', 'stripes', 'history', 'map']), en.header.menu])
        await expect(status(page)).toHaveText(`${en.nav.meteogram} is now only in the Menu. ${en.nav.map} is now in the bar, at place 4 of 4.`)
      })

      test('does everything dragging does by the arrow buttons, with the keyboard, and says what moved', async ({ page, baseURL }) => {
        await open(page, baseURL!, '/settings', { mode })
        await move(page, 'map', 'up').focus()
        await page.keyboard.press('Enter')
        await expect(status(page)).toHaveText(`${en.nav.map} is now in the bar, at place 4 of 4. ${en.nav.history} is now only in the Menu.`)
        // the focus is on the same button, in the row where the tool now is
        await expect(move(page, 'map', 'up')).toBeFocused()
        expect(await barTexts(page)).toEqual([...names(['forecast', 'explorer', 'stripes', 'map']), en.header.menu])
        await page.keyboard.press('Space')
        await expect(status(page)).toHaveText(`${en.nav.map} moved to place 3 of 4 in the bar.`)
        await expect(move(page, 'map', 'up')).toBeFocused()
        await page.keyboard.press('Enter')
        await page.keyboard.press('Enter')
        await expect(move(page, 'map', 'up')).toBeFocused()
        expect(await stored(page)).toEqual(['map', 'forecast', 'explorer', 'stripes', 'history'])
        // at the top of the list the button stays where it is and does nothing
        await expect(move(page, 'map', 'up')).toHaveAttribute('aria-disabled', 'true')
        await page.keyboard.press('Enter')
        expect(await stored(page)).toEqual(['map', 'forecast', 'explorer', 'stripes', 'history'])
        // and back out of the bar, by "down", across the line
        await move(page, 'map', 'down').focus()
        for (let press = 0; press < 4; press++)
          await page.keyboard.press('Enter')
        await expect(status(page)).toHaveText(`${en.nav.map} is now only in the Menu. ${en.nav.history} is now in the bar, at place 4 of 4.`)
        await expect(move(page, 'map', 'down')).toBeFocused()
        expect(await stored(page)).toEqual(['forecast', 'explorer', 'stripes', 'history', 'map'])
        expect(await barTexts(page)).toEqual([...names(DEFAULT_ORDER.slice(0, 4)), en.header.menu])
      })

      test('reaches each button and Reset by Tab in the order of the list, and by Shift+Tab back, and none is hidden under the preview or the bars when it is focused', async ({ page, baseURL }) => {
        await open(page, baseURL!, '/settings', { mode })
        await walkFocus(page)
      })

      test('puts the default back by "Reset the bar", and says so', async ({ page, baseURL }) => {
        await open(page, baseURL!, '/settings', { mode, settings: settingsWith(WITH_MAP) })
        expect(await barTexts(page)).toEqual([...names(WITH_MAP.slice(0, 4)), en.header.menu])
        await chooser(page).getByTestId('bar-reset').click()
        await expect(status(page)).toHaveText(`The bar is back to its default: ${names(DEFAULT_ORDER.slice(0, 4)).join(', ')}.`)
        expect(await barTexts(page)).toEqual([...names(DEFAULT_ORDER.slice(0, 4)), en.header.menu])
        expect(await stored(page)).toEqual(DEFAULT_ORDER)
      })
    })
  }
}

test.describe('every language, at 320 px', () => {
  test.use({ viewport: { width: 320, height: 640 } })

  for (const code of LOCALES) {
    test(`${code}: the chooser, its status and the preview fit, and the strings are all there`, async ({ page, baseURL }) => {
      await open(page, baseURL!, '/settings', { language: code })
      const bar = messages[code].settings.bar
      expect(Object.keys(bar).sort()).toEqual(Object.keys(en.settings.bar).sort())
      await expect(chooser(page).locator('h3')).toHaveText([bar.inBar, bar.inMenu])
      // nothing of the chooser reaches past the window (the page's own units and Reset button are not the chooser's: the
      // Spanish "Restablecer valores predeterminados" makes the page wider than 320 px, which this test is not about)
      const beyond = await chooser(page).evaluate((node) => {
        const width = document.documentElement.clientWidth
        return [...node.querySelectorAll('*')].filter(el => el.getBoundingClientRect().right > width + 1).map(el => el.className)
      })
      expect(beyond).toEqual([])
      // a long name takes two lines in its row and stays inside it
      const out = await chooser(page).evaluate(node => [...node.querySelectorAll('li[data-row]')].filter((li) => {
        const box = li.getBoundingClientRect()
        return [...li.querySelectorAll('*')].some(el => el.getBoundingClientRect().right > box.right + 1)
      }).length)
      expect(out).toBe(0)
      // the first move is said in the language of the page
      await move(page, 'map', 'up').click()
      await expect(status(page)).not.toHaveText('')
      await expect(status(page)).not.toContainText('settings.bar')
      await expect(status(page)).toContainText(messages[code].nav.map)
    })
  }
})

test.describe('by touch (Chromium)', () => {
  test.use({ viewport: { width: 390, height: 844 }, hasTouch: true })

  // Playwright can send a finger's events (CDP) only to Chromium; the suite's Firefox project skips this, and
  // E2E_BROWSER=chrome runs it
  test.skip(({ browserName }) => browserName !== 'chromium', 'a finger can be sent only to Chromium')

  test('drags by the handle, which does not scroll the page, and a finger on the rest of a row does scroll it', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/settings')
    await showList(page)
    const client = await page.context().newCDPSession(page)
    const send = (type: 'touchStart' | 'touchMove' | 'touchEnd', point?: { x: number, y: number }) =>
      client.send('Input.dispatchTouchEvent', { type, touchPoints: point ? [{ x: point.x, y: point.y, id: 1 }] : [] })
    const scrollBefore = await page.evaluate(() => window.scrollY)

    // the handle: up from the Map's row to the Explorer's
    const from = await middle(handle(page, 'map'))
    const to = await middle(row(page, 'explorer'))
    await send('touchStart', from)
    for (let step = 1; step <= 10; step++)
      await send('touchMove', { x: from.x, y: from.y + (to.y - from.y) * step / 10 })
    expect(await previewTexts(page)).toEqual(names(['forecast', 'map', 'explorer', 'stripes']))
    expect(await page.evaluate(() => window.scrollY)).toBe(scrollBefore)
    await send('touchEnd')
    expect(await stored(page)).toEqual(['forecast', 'map', 'explorer', 'stripes', 'history'])
    await expect(status(page)).toContainText(`${en.nav.map} is now in the bar, at place 2 of 4`)

    // the name of a tool, off the handle: the finger scrolls, the order stays
    const name = await middle(row(page, 'stripes').locator('span.font-semibold'))
    await send('touchStart', name)
    for (let step = 1; step <= 10; step++)
      await send('touchMove', { x: name.x, y: name.y - 12 * step })
    await send('touchEnd')
    await page.waitForTimeout(300)
    expect(await page.evaluate(() => window.scrollY)).toBeGreaterThan(scrollBefore)
    expect(await stored(page)).toEqual(['forecast', 'map', 'explorer', 'stripes', 'history'])
    await client.detach()
  })
})

test.describe('the Menu, on a phone', () => {
  test.use({ viewport: { width: 390, height: 844 } })

  test('has a link to the chooser that opens the settings at it, with the focus on its heading, and the Menu marked', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/')
    await menuTab(page).click()
    const sheet = page.getByRole('dialog', { name: en.header.menu })
    await sheet.getByRole('link', { name: en.settings.bar.title }).click()
    await expect(page).toHaveURL(/\/settings#bar$/)
    await expect(sheet).toBeHidden()
    await expect(page.getByRole('heading', { level: 2, name: en.settings.bar.title })).toBeFocused()
    await expect(menuTab(page)).toHaveAttribute('aria-current', 'true')
    await expect(chooser(page)).toBeInViewport()
  })

  test('scrolls to the chooser, with the focus on its heading, where the address `/settings#bar` is opened afresh', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/settings#bar')
    await expect(page.getByRole('heading', { level: 2, name: en.settings.bar.title })).toBeFocused()
    await expect(page.getByRole('heading', { level: 2, name: en.settings.bar.title })).toBeInViewport()
    // clear of the header that stands over the top of the page
    const heading = (await page.getByRole('heading', { level: 2, name: en.settings.bar.title }).boundingBox())!
    const header = (await page.getByRole('banner').boundingBox())!
    expect(heading.y).toBeGreaterThanOrEqual(header.y + header.height)
  })

  test('is reached from the settings page as well: the chooser is a card of it', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/settings')
    await expect(page.getByRole('heading', { level: 2, name: en.settings.bar.title })).toBeVisible()
    await expect(menuTab(page)).toHaveAttribute('aria-current', 'true')
  })

  // the pages the sheet reaches, the ones it does not, and the tools the bar holds
  const ROUTES: Array<[string, string | null | undefined]> = [
    ['/', undefined],
    ['/impressum', undefined],
    ['/datenschutz', undefined],
    ['/meteogram', 'forecast'],
    ['/explorer', 'explorer'],
    ['/stripes', 'stripes'],
    ['/history', 'history'],
    ['/map', null],
    ['/providers', null],
    ['/glossary', null],
    ['/api', null],
    ['/about', null],
    ['/support', null],
    ['/settings', null],
  ]

  for (const [route, tab] of ROUTES) {
    test(`marks ${tab === null ? 'the Menu' : tab ? `the ${tab} tab` : 'nothing'} on ${route}`, async ({ page, baseURL }) => {
      await open(page, baseURL!, route)
      await expect(bar(page).locator('[aria-current]')).toHaveCount(tab === undefined ? 0 : 1)
      if (tab === null)
        await expect(menuTab(page)).toHaveAttribute('aria-current', 'true')
      else if (tab)
        await expect(bar(page).getByRole('link', { name: NAMES[tab]!, exact: true })).toHaveAttribute('aria-current', 'page')
    })
  }

  test('follows the route through the sheet, a tab and Back, with no page load', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/')
    await expect(bar(page).locator('[aria-current]')).toHaveCount(0)
    const goBySheet = async (name: string, url: RegExp) => {
      await menuTab(page).click()
      await page.getByRole('dialog', { name: en.header.menu }).getByRole('link', { name, exact: true }).click()
      await expect(page).toHaveURL(url)
    }
    await goBySheet(en.nav.glossary, /\/glossary$/)
    await expect(menuTab(page)).toHaveAttribute('aria-current', 'true')
    await goBySheet(en.nav.map, /\/map$/)
    await expect(menuTab(page)).toHaveAttribute('aria-current', 'true')
    await bar(page).getByRole('link', { name: en.nav.history, exact: true }).click()
    await expect(page).toHaveURL(/\/history/)
    await expect(menuTab(page)).not.toHaveAttribute('aria-current', 'true')
    await expect(bar(page).getByRole('link', { name: en.nav.history, exact: true })).toHaveAttribute('aria-current', 'page')
    await goBySheet(en.footer.about, /\/about$/)
    await expect(menuTab(page)).toHaveAttribute('aria-current', 'true')
    await goBySheet(en.nav.home, /\/$/)
    await expect(bar(page).locator('[aria-current]')).toHaveCount(0)
    await page.goBack()
    await expect(page).toHaveURL(/\/about$/)
    await expect(menuTab(page)).toHaveAttribute('aria-current', 'true')
    await page.goBack()
    await expect(page).toHaveURL(/\/history/)
    await expect(menuTab(page)).not.toHaveAttribute('aria-current', 'true')
    await expect(bar(page).locator('[aria-current="page"]')).toHaveCount(1)
  })

  test('marks the tab of a tool the reader moved into the bar, and the Menu on the one it left out', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/map', { settings: settingsWith(WITH_MAP) })
    expect(await barTexts(page)).toEqual([...names(WITH_MAP.slice(0, 4)), en.header.menu])
    await expect(bar(page).getByRole('link', { name: en.nav.map, exact: true })).toHaveAttribute('aria-current', 'page')
    await expect(menuTab(page)).not.toHaveAttribute('aria-current')
    await expect(bar(page).getByRole('link', { name: en.nav.history })).toHaveCount(0)
    // History is in the sheet now, and its page is the Menu's
    await menuTab(page).click()
    await page.getByRole('dialog', { name: en.header.menu }).getByRole('link', { name: en.nav.history, exact: true }).click()
    await expect(page).toHaveURL(/\/history/)
    await expect(menuTab(page)).toHaveAttribute('aria-current', 'true')
    await expect(bar(page).locator('[aria-current="page"]')).toHaveCount(0)
  })

  test('follows a choice made on the settings page at once, on the page itself', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/settings')
    await expect(menuTab(page)).toHaveAttribute('aria-current', 'true')
    await move(page, 'map', 'up').click()
    // History left the bar for the Menu: its tab is gone, and the pages of the sheet go on marking the Menu
    expect(await barTexts(page)).toEqual([...names(['forecast', 'explorer', 'stripes', 'map']), en.header.menu])
    await menuTab(page).click()
    await page.getByRole('dialog', { name: en.header.menu }).getByRole('link', { name: en.nav.history, exact: true }).click()
    await expect(page).toHaveURL(/\/history/)
    await expect(menuTab(page)).toHaveAttribute('aria-current', 'true')
    // the choice stays after the navigation, and a page of a tool in the bar marks its tab
    await bar(page).getByRole('link', { name: en.nav.map, exact: true }).click()
    await expect(page).toHaveURL(/\/map$/)
    await expect(bar(page).getByRole('link', { name: en.nav.map, exact: true })).toHaveAttribute('aria-current', 'page')
    await expect(menuTab(page)).not.toHaveAttribute('aria-current')
  })
})

test.describe('a storage that is wrong, blocked or full of nonsense', () => {
  test.use({ viewport: { width: 390, height: 844 } })

  const WRONG: Array<[string, unknown, string[]]> = [
    ['a tool that does not exist', settingsWith(['radar', 'map', 'forecast', 'explorer', 'stripes']), ['map', 'forecast', 'explorer', 'stripes']],
    ['too few tools', settingsWith(['history']), ['history', 'forecast', 'explorer', 'stripes']],
    ['too many', settingsWith([...WITH_MAP, 'radar', 'weather']), WITH_MAP.slice(0, 4)],
    ['a tool twice', settingsWith(['map', 'map', 'map', 'map']), ['map', 'forecast', 'explorer', 'stripes']],
    ['no list', settingsWith('map'), DEFAULT_ORDER.slice(0, 4)],
    ['a list of numbers', settingsWith([1, 2, 3, 4]), DEFAULT_ORDER.slice(0, 4)],
    ['an empty list', settingsWith([]), DEFAULT_ORDER.slice(0, 4)],
    ['a null', settingsWith(null), DEFAULT_ORDER.slice(0, 4)],
    ['settings of an earlier version, with no choice', { version: 1, friendlyLabels: false, convertUnits: true }, DEFAULT_ORDER.slice(0, 4)],
    ['text that is no JSON', '{not json', DEFAULT_ORDER.slice(0, 4)],
    ['a string for the whole of it', '"forecast"', DEFAULT_ORDER.slice(0, 4)],
  ]

  for (const [name, settings, bar4] of WRONG) {
    test(`shows a valid bar of four tools for ${name}, with no error`, async ({ page, baseURL }) => {
      const errors: string[] = []
      page.on('pageerror', error => errors.push(error.message))
      await open(page, baseURL!, '/settings', { settings })
      expect(await barTexts(page)).toEqual([...names(bar4), en.header.menu])
      expect(await previewTexts(page)).toEqual(names(bar4))
      await expect(chooser(page).locator('li[data-row]')).toHaveCount(5)
      // and the first move starts from it
      await move(page, bar4[1]!, 'up').click()
      expect(await barTexts(page)).toHaveLength(5)
      expect(errors).toEqual([])
    })
  }

  test('works with the browser\'s storage blocked: the default bar, the chooser in use for the visit, no error', async ({ page, baseURL }) => {
    const errors: string[] = []
    page.on('pageerror', error => errors.push(error.message))
    await open(page, baseURL!, '/settings', { blockedStorage: true })
    expect(await barTexts(page)).toEqual([...names(DEFAULT_ORDER.slice(0, 4)), en.header.menu])
    expect(await previewTexts(page)).toEqual(names(DEFAULT_ORDER.slice(0, 4)))
    // the choice holds for as long as the page does, and no longer
    await move(page, 'map', 'up').click()
    expect(await barTexts(page)).toEqual([...names(['forecast', 'explorer', 'stripes', 'map']), en.header.menu])
    await drag(page, 'history', 'forecast')
    expect(await barTexts(page)).toEqual([...names(['history', 'forecast', 'explorer', 'stripes']), en.header.menu])
    // the pages of the sheet are still marked, and a page of the app still opens
    await menuTab(page).click()
    await page.getByRole('dialog', { name: en.header.menu }).getByRole('link', { name: en.nav.glossary, exact: true }).click()
    await expect(page).toHaveURL(/\/glossary$/)
    await expect(menuTab(page)).toHaveAttribute('aria-current', 'true')
    expect(await barTexts(page)).toEqual([...names(['history', 'forecast', 'explorer', 'stripes']), en.header.menu])
    expect(errors).toEqual([])
  })
})

test.describe('every page, with the browser\'s storage blocked', () => {
  test.use({ viewport: { width: 390, height: 844 } })

  // measured on main with localStorage throwing: `/` and `/meteogram` opened, the pages that read the settings did not
  for (const route of ['/', '/meteogram', '/explorer', '/stripes', '/history', '/map', '/glossary', '/providers', '/api', '/about', '/support', '/settings']) {
    test(`opens ${route}, with the bar and no error`, async ({ page, baseURL }) => {
      const errors: string[] = []
      page.on('pageerror', error => errors.push(error.message))
      await open(page, baseURL!, route, { blockedStorage: true })
      await expect(bar(page)).toBeVisible()
      expect(await barTexts(page)).toEqual([...names(DEFAULT_ORDER.slice(0, 4)), en.header.menu])
      expect(errors).toEqual([])
    })
  }
})

test.describe('the wide header', () => {
  test.use({ viewport: { width: 1280, height: 800 } })

  test('shows all five tools whatever the bar holds, and the chooser is still on the settings page', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/settings', { settings: settingsWith(WITH_MAP) })
    const header = page.getByRole('banner').getByRole('navigation', { name: en.shell.mainNav })
    await expect(header.getByRole('link')).toHaveText(['meteogram', 'explorer', 'stripes', 'history', 'map'].map(key => en.nav[key]))
    await expect(bar(page)).toBeHidden()
    await expect(chooser(page)).toBeVisible()
  })
})

test.describe('a low phone, 320 x 568', () => {
  test.use({ viewport: { width: 320, height: 568 } })

  test('keeps the focus of every button and of Reset clear of the preview, forwards and back', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/settings')
    await walkFocus(page)
  })
})

test.describe('the preview of the bar', () => {
  test.use({ viewport: { width: 320, height: 640 } })

  // the names that the bar shows whole (Pronóstico, Explorador, Franjas climáticas) are not broken in the preview: its
  // labels wrap exactly as the bar's, so each is as tall as the one of the same tool in the bar at the foot
  for (const code of ['es', 'fr', 'it', 'pl', 'cs', 'de-hh']) {
    test(`${code}: wraps the names of the tools as the bar does, at 320 px`, async ({ page, baseURL }) => {
      await open(page, baseURL!, '/settings', { language: code })
      const heights = await page.evaluate(() => {
        const measure = (selector: string) => [...document.querySelectorAll<HTMLElement>(selector)].map(label => ({ text: label.textContent!.trim(), height: label.getBoundingClientRect().height, lines: label.getClientRects().length }))
        return { preview: measure('[data-testid="bar-preview"] .tabbar-label'), bar: measure('.app-tabbar .tabbar-label') }
      })
      // the four tools of both, in the same order; the Menu is the last of each
      expect(heights.preview.map(label => label.text)).toEqual(heights.bar.map(label => label.text))
      for (const [index, label] of heights.preview.entries())
        expect(label.height, `${label.text}: the preview's label is ${label.height} px tall, the bar's ${heights.bar[index]!.height}`).toBe(heights.bar[index]!.height)
      // and it is as wide as the window, as the bar is
      const widths = await page.evaluate(() => ({
        preview: document.querySelector('[data-testid="bar-preview"]')!.getBoundingClientRect().width,
        bar: document.querySelector('.app-tabbar')!.getBoundingClientRect().width,
        right: document.querySelector('[data-testid="bar-preview"]')!.getBoundingClientRect().right,
        left: document.querySelector('[data-testid="bar-preview"]')!.getBoundingClientRect().left,
        window: document.documentElement.clientWidth,
      }))
      expect(widths.preview).toBe(widths.bar)
      // (the page itself is wider than the window in es, by its Reset button, which is not the preview)
      expect(widths.left).toBeGreaterThanOrEqual(0)
      expect(widths.right).toBeLessThanOrEqual(widths.window)
    })
  }
})

test.describe('the link to the chooser, in a browser', () => {
  test.use({ viewport: { width: 390, height: 844 } })

  test('takes the focus to the heading from the settings page itself, where only the address changes', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/settings')
    await menuTab(page).click()
    await page.getByRole('dialog', { name: en.header.menu }).getByRole('link', { name: en.settings.bar.title }).click()
    await expect(page).toHaveURL(/\/settings#bar$/)
    await expect(page.getByRole('heading', { level: 2, name: en.settings.bar.title })).toBeFocused()
  })

  test('gives the focus back to the Menu tab where the reader is at the chooser already and nothing changes', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/settings#bar')
    await menuTab(page).click()
    const sheet = page.getByRole('dialog', { name: en.header.menu })
    await sheet.getByRole('link', { name: en.settings.bar.title }).click()
    await expect(sheet).toBeHidden()
    await expect(menuTab(page)).toBeFocused()
  })

  test('leaves the sheet and the focus alone on a Ctrl-click, which opens the link in a tab of its own', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/history')
    await menuTab(page).click()
    const sheet = page.getByRole('dialog', { name: en.header.menu })
    const link = sheet.getByRole('link', { name: en.settings.bar.title })
    await link.focus()
    await link.click({ modifiers: ['Control'] })
    await expect(sheet).toBeVisible()
    await expect(page).toHaveURL(/\/history/)
    expect(await page.evaluate(() => document.activeElement?.tagName)).not.toBe('BODY')
  })
})

test.describe('a scroll while a tool is dragged', () => {
  test.use({ viewport: { width: 390, height: 844 } })

  test('is followed by the preview, which is the drop that the release makes', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/settings')
    await showList(page)
    const from = await middle(handle(page, 'map'))
    const to = await middle(row(page, 'explorer'))
    await page.mouse.move(from.x, from.y)
    await page.mouse.down()
    await page.mouse.move(to.x, to.y, { steps: 10 })
    expect(await previewTexts(page)).toEqual(names(['forecast', 'map', 'explorer', 'stripes']))
    // the wheel turns with the pointer where it is: the rows move, the pointer does not
    await page.mouse.wheel(0, 130)
    await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(100)
    // the scroll may take a moment to arrive; the preview follows it
    await expect.poll(() => previewTexts(page)).not.toEqual(names(['forecast', 'map', 'explorer', 'stripes']))
    await page.waitForTimeout(300)
    const shown = await previewTexts(page)
    await page.mouse.up()
    const stored_ = (await stored(page)) as string[]
    expect(stored_.slice(0, 4).map(tool => NAMES[tool])).toEqual(shown)
  })
})
