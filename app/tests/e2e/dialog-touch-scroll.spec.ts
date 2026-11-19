import type { CDPSession, Locator, Page } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { expect, test } from '@playwright/test'
import { askHandlers } from './accessibility/ask-backend'
import { mockBackend, STATIONS } from './accessibility/mock-backend'

// A finger on an open dialog (GH-3761): the search of the header and the place dialog of "Ask the weather" are modals
// over a page that scrolls, and a touch drag in them must move their own list and nothing behind them -- not by
// chaining on to the page once the list is at its end, and not from a drag on the backdrop. Run on a phone
// (Pixel 7, touch, mobile) in Chromium, the `chromium-touch` project of playwright.config.ts: the drag is a gesture
// of the browser's input (CDP `Input.dispatchTouchEvent`), which is what a finger is, and
// which a wheel event or `scrollTo` is not. The page behind is scrolled down once the dialog is open, since a page at
// the top that does not move proves nothing about a lock. Chromium holds the page still by the `overflow: hidden` the
// dialog library sets on the body, so the same drags are made once more with that lock taken off: a contract for the
// dialog's own CSS (`touch-action` on the overlay, `overscroll-behavior` on the content and the body) in a browser that
// ignores the body's lock. It is not a reproduction of the report, which is iOS Safari with the on-screen keyboard up
// and which this cannot run. What the report turned out to be is a gap in reka-ui's iOS `touchmove` guard, which steps
// aside for every move that has an overflowing ancestor, also one that is at its top or its end (the search's list
// just opened); the last two tests hold the app's guard on the move (`useModalDialogHold`) to that, with moves that a
// script makes. The backend is the accessibility spec's mock, so nothing here reaches a provider.

const en = JSON.parse(readFileSync(fileURLToPath(new URL('../../i18n/locales/en.json', import.meta.url)), 'utf-8'))

/** How far the page behind is scrolled while the dialog is open */
const PAGE_OFFSET = 240

async function home(page: Page, baseURL: string) {
  await page.context().addCookies([{ name: 'wd_lang', value: 'en', url: baseURL }])
  // the place dialog lists the stations of a name: eight, so that its list is the one that overflows
  const handlers = askHandlers()
  const stations = Array.from({ length: 8 }, (_, index) => ({ ...STATIONS[index % STATIONS.length]!, station_id: `9000${index}`, name: `Teststation ${index + 1}` }))
  handlers.stations = (url, route) => url.searchParams.has('name') && url.searchParams.get('network') === 'observation'
    ? { stations }
    : askHandlers().stations!(url, route)
  const backend = await mockBackend(page, baseURL, handlers)
  await page.addInitScript(() => {
    try {
      localStorage.removeItem('wd-place')
    }
    catch {}
  })
  await page.goto('/')
  await expect(page.getByTestId('ask')).toBeVisible()
  return backend
}

/**
 * The page behind, scrolled by `PAGE_OFFSET` once the dialog is open (a click on its button scrolls the page back to
 * the button, and a script can still scroll under a lock), and the proof that it can scroll at all: a short page
 * would pass any lock
 */
async function scrollPage(page: Page) {
  await page.evaluate(offset => window.scrollTo(0, offset), PAGE_OFFSET)
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(PAGE_OFFSET)
  const room = await page.evaluate(() => document.documentElement.scrollHeight - window.innerHeight)
  expect(room, 'the page behind has room to scroll').toBeGreaterThan(PAGE_OFFSET + 200)
}

const scrollY = (page: Page) => page.evaluate(() => window.scrollY)
const scrollTop = (box: Locator) => box.evaluate(element => element.scrollTop)

/**
 * A finger dragged from (x, y) by `distance` pixels (negative: upwards, so that what is under it scrolls down), as touch
 * events of the browser's input (CDP `Input.dispatchTouchEvent`): a start, a move every 16 ms and an end after a stop, so
 * that it is a drag and not a fling. Not `Input.synthesizeScrollGesture` with source touch, which moved the list on
 * macOS and not in CI's headless Chromium on Linux (the likely reason: there the gesture is injected through the
 * platform's window, which a headless one does not have; these events go to the page's input directly)
 */
async function drag(cdp: CDPSession, x: number, y: number, distance: number) {
  const steps = Math.max(1, Math.ceil(Math.abs(distance) / 20))
  const point = (step: number) => [{ x, y: y + (distance * step) / steps, id: 1 }]
  await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: point(0) })
  for (let step = 1; step <= steps; step++) {
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: point(step) })
    await new Promise(resolve => setTimeout(resolve, 16))
  }
  await new Promise(resolve => setTimeout(resolve, 120))
  await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] })
}

const swipeUp = (cdp: CDPSession, x: number, y: number, up: number) => drag(cdp, x, y, -up)
const swipeDown = (cdp: CDPSession, x: number, y: number, down: number) => drag(cdp, x, y, down)

async function centre(box: Locator) {
  const rect = (await box.boundingBox())!
  return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2, rect }
}

/** A point of the backdrop: above the dialog, where there is room for one, else below it */
async function backdropPoint(page: Page, dialog: Locator) {
  const rect = (await dialog.boundingBox())!
  const height = page.viewportSize()!.height
  const x = page.viewportSize()!.width / 2
  return rect.y > height - rect.y - rect.height ? { x, y: rect.y / 2 } : { x, y: rect.y + rect.height + (height - rect.y - rect.height) / 2 }
}

/** The parts of the search's dialog that do not scroll: the field and the line under the list */
const palette = (dialog: Locator) => [dialog.getByRole('combobox'), dialog.getByRole('status')]

/**
 * What a finger does on an open dialog, from the list to the backdrop. `list` is what scrolls in the dialog, `still` the
 * parts that do not, where a drag moves nothing. `unlocked` takes off the lock the library sets on the body, as for a
 * browser that does not honour it for touch: then only what the dialog does itself holds the page.
 */
async function holds(page: Page, dialog: Locator, list: Locator, options: { still?: Locator[], unlocked?: boolean } = {}) {
  const { still = [], unlocked = false } = options
  const cdp = await page.context().newCDPSession(page)
  if (unlocked)
    await page.evaluate(() => document.body.style.setProperty('overflow', 'visible'))
  // the list is longer than the box it is in, or there is nothing to scroll
  await expect.poll(() => list.evaluate(element => element.scrollHeight - element.clientHeight)).toBeGreaterThan(100)
  const { x, y, rect } = await centre(list)
  // the dialog is inside the window and the list is inside the dialog
  const viewport = page.viewportSize()!
  expect(rect.y).toBeGreaterThanOrEqual(0)
  expect(rect.y + rect.height).toBeLessThanOrEqual(viewport.height)
  const dialogBox = (await dialog.boundingBox())!
  expect(dialogBox.y + dialogBox.height).toBeLessThanOrEqual(viewport.height)

  // a drag in the list moves the list ...
  await swipeUp(cdp, x, y, 150)
  await expect.poll(() => scrollTop(list)).toBeGreaterThan(40)
  expect(await scrollY(page), 'the page does not move with the list').toBe(PAGE_OFFSET)

  // ... to its end, and a drag past the end does not go on to the page
  for (let drag = 0; drag < 6; drag++)
    await swipeUp(cdp, x, y, 400)
  await expect.poll(() => list.evaluate(element => Math.ceil(element.scrollTop + element.clientHeight) >= element.scrollHeight)).toBe(true)
  await swipeUp(cdp, x, y, 300)
  expect(await scrollY(page), 'a drag past the end of the list does not chain to the page').toBe(PAGE_OFFSET)
  // and the same upwards, past the top
  for (let drag = 0; drag < 8; drag++)
    await swipeDown(cdp, x, y, 400)
  await expect.poll(() => scrollTop(list)).toBe(0)
  await swipeDown(cdp, x, y, 300)
  expect(await scrollY(page), 'a drag past the top of the list does not chain to the page').toBe(PAGE_OFFSET)

  // a drag on the parts that do not scroll: the field and the line under the list. Each way is looked at on its own: one
  // way after the other would bring a page that had moved back to where it was
  for (const box of still) {
    const at = await centre(box)
    await swipeUp(cdp, at.x, at.y, 200)
    expect(await scrollY(page), 'a drag up on a part of the dialog that does not scroll does not scroll the page').toBe(PAGE_OFFSET)
    await swipeDown(cdp, at.x, at.y, 200)
    expect(await scrollY(page), 'a drag down on a part of the dialog that does not scroll does not scroll the page').toBe(PAGE_OFFSET)
  }
  // a drag on the backdrop, both ways, does not move the page, and the dialog is still there
  const point = await backdropPoint(page, dialog)
  await swipeUp(cdp, point.x, point.y, 200)
  expect(await scrollY(page), 'a drag up on the backdrop does not scroll the page').toBe(PAGE_OFFSET)
  await swipeDown(cdp, point.x, point.y, 200)
  expect(await scrollY(page), 'a drag down on the backdrop does not scroll the page').toBe(PAGE_OFFSET)
  await expect(dialog).toBeVisible()
  // nothing of the document scrolls either (the window is not the only thing that can)
  expect(await page.evaluate(() => [document.documentElement.scrollTop, document.body.scrollTop])).toEqual([PAGE_OFFSET, 0])
}

// a drag takes its time (a step every 16 ms), and a runner of CI is slow
test.setTimeout(90_000)

test.describe('the dialogs on a phone', () => {
  test('the search scrolls its own list and leaves the page behind alone', async ({ page, baseURL }) => {
    await home(page, baseURL!)
    await page.getByRole('button', { name: en.shell.search }).click()
    const dialog = page.getByRole('dialog', { name: en.shell.search })
    await expect(dialog).toBeVisible()
    await scrollPage(page)
    await expect(dialog.getByRole('combobox', { name: en.shell.search })).toBeFocused()
    await holds(page, dialog, dialog.getByRole('listbox', { name: en.shell.results }), { still: palette(dialog) })
  })

  test.describe('where the body is not held by overflow: hidden', () => {
    test('the search still moves only its own list', async ({ page, baseURL }) => {
      await home(page, baseURL!)
      await page.getByRole('button', { name: en.shell.search }).click()
      const dialog = page.getByRole('dialog', { name: en.shell.search })
      await expect(dialog).toBeVisible()
      await scrollPage(page)
      await holds(page, dialog, dialog.getByRole('listbox', { name: en.shell.results }), { unlocked: true, still: palette(dialog) })
    })
  })

  test.describe('on a short window, a phone on its side', () => {
    test.use({ viewport: { width: 851, height: 330 } })

    test('the search keeps the list inside the window and scrolls it', async ({ page, baseURL }) => {
      await home(page, baseURL!)
      await page.getByRole('button', { name: en.shell.search }).click()
      const dialog = page.getByRole('dialog', { name: en.shell.search })
      await expect(dialog).toBeVisible()
      await scrollPage(page)
      await holds(page, dialog, dialog.getByRole('listbox', { name: en.shell.results }), { still: palette(dialog) })
    })
  })

  test('the place dialog of Ask the weather scrolls its own list and leaves the page behind alone', async ({ page, baseURL }) => {
    await home(page, baseURL!)
    // short enough that eight places are more than the dialog holds
    await page.setViewportSize({ width: 412, height: 520 })
    await page.getByTestId('place-button').click()
    const dialog = page.getByRole('dialog', { name: en.ask.placeDialogTitle })
    await expect(dialog).toBeVisible()
    await scrollPage(page)
    await dialog.getByRole('combobox').fill('Test')
    await expect(dialog.getByRole('option')).toHaveCount(8)
    await holds(page, dialog, dialog.getByRole('listbox', { name: en.shell.results }), { still: palette(dialog) })
  })

  for (const unlocked of [false, true]) {
    test(`the menu sheet of the tab bar scrolls its own list and leaves the page behind alone${unlocked ? ', with no help of the body\'s overflow' : ''}`, async ({ page, baseURL }) => {
      await home(page, baseURL!)
      // short enough that the sheet's links are more than it holds
      await page.setViewportSize({ width: 412, height: 520 })
      await page.getByRole('button', { name: en.header.menu, exact: true }).click()
      const dialog = page.getByRole('dialog', { name: en.header.menu })
      await expect(dialog).toBeVisible()
      await scrollPage(page)
      await holds(page, dialog, dialog.locator('[data-slot="body"]'), { unlocked, still: [dialog.locator('[data-slot="header"]')] })
    })
  }
})

/**
 * A one-finger move as touch events that a script makes (`new TouchEvent`), not the browser's input: a start at the
 * middle of `target` and a move of `dy` pixels, and whether the page cancelled the move (`defaultPrevented`). What a
 * list does with a real finger is the drags above; this is the decision of the app's guard on the move (`useModalDialogHold`),
 * for the cases a finger of a test cannot be placed in: a list at its top or its end where the move would otherwise go
 * on to the page.
 */
async function moveIsCancelled(target: Locator, dy: number, fingers = 1) {
  return target.evaluate((element, { dy, fingers }) => {
    const rect = element.getBoundingClientRect()
    const x = rect.left + rect.width / 2
    const y = rect.top + rect.height / 2
    const touch = (id: number, offset: number) => new Touch({ identifier: id, target: element, clientX: x + id * 20, clientY: y + offset })
    const at = (offset: number) => Array.from({ length: fingers }, (_, id) => touch(id, offset))
    const init = { bubbles: true, cancelable: true, composed: true }
    element.dispatchEvent(new TouchEvent('touchstart', { ...init, touches: at(0), targetTouches: at(0), changedTouches: at(0) }))
    const move = new TouchEvent('touchmove', { ...init, touches: at(dy), targetTouches: at(dy), changedTouches: at(dy) })
    element.dispatchEvent(move)
    return move.defaultPrevented
  }, { dy, fingers })
}

// the guard is iOS's, as reka-ui's own (`isIOS` of the user agent): these run as an iPhone's Safari, the touch and the size
// of the Pixel 7 of the project, since Chromium can be given the user agent and the events a script makes
const IPHONE = 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1'

test.describe('the guard on a move at the edge of a list (GH-3761)', () => {
  test.use({ userAgent: IPHONE })

  test('the search\'s list lets a move scroll it, and cancels one at its top and at its end, as the dialog is just opened', async ({ page, baseURL }) => {
    await home(page, baseURL!)
    await page.getByRole('button', { name: en.shell.search }).click()
    const dialog = page.getByRole('dialog', { name: en.shell.search })
    await expect(dialog).toBeVisible()
    const list = dialog.getByRole('listbox', { name: en.shell.results })
    await expect.poll(() => list.evaluate(element => element.scrollHeight - element.clientHeight)).toBeGreaterThan(100)
    const option = list.getByRole('option').first()
    await expect.poll(() => scrollTop(list)).toBe(0)

    // at its top: a finger going up (the list scrolls down) is the list's, a finger going down has nothing above to bring
    expect(await moveIsCancelled(option, -30), 'up, at the top: the list scrolls').toBe(false)
    expect(await moveIsCancelled(option, 30), 'down, at the top: it would go on to the page').toBe(true)
    // a pinch is the browser's, whatever the edge
    expect(await moveIsCancelled(option, 30, 2), 'two fingers: left alone').toBe(false)

    // at its end the other way round
    await list.evaluate(element => element.scrollTo(0, element.scrollHeight))
    await expect.poll(() => list.evaluate(element => Math.ceil(element.scrollTop + element.clientHeight) >= element.scrollHeight)).toBe(true)
    expect(await moveIsCancelled(option, -30), 'up, at the end: it would go on to the page').toBe(true)
    expect(await moveIsCancelled(option, 30), 'down, at the end: the list scrolls back').toBe(false)

    // the parts that do not scroll, whichever way
    for (const part of palette(dialog)) {
      expect(await moveIsCancelled(part, -30)).toBe(true)
      expect(await moveIsCancelled(part, 30)).toBe(true)
    }
  })

  test('is held by the place dialog and the menu sheet as by the search, at the top of their lists', async ({ page, baseURL }) => {
    await home(page, baseURL!)
    // short enough that the places and the sheet's links are more than the dialogs hold
    await page.setViewportSize({ width: 412, height: 520 })
    await page.getByTestId('place-button').click()
    const place = page.getByRole('dialog', { name: en.ask.placeDialogTitle })
    await expect(place).toBeVisible()
    await place.getByRole('combobox').fill('Test')
    const option = place.getByRole('option').first()
    await expect(place.getByRole('option')).toHaveCount(8)
    expect(await moveIsCancelled(option, -30), 'up: the list scrolls').toBe(false)
    expect(await moveIsCancelled(option, 30), 'down at the top: not on to the page').toBe(true)
    await page.keyboard.press('Escape')
    await expect(place).toBeHidden()

    await page.getByRole('button', { name: en.header.menu, exact: true }).click()
    const sheet = page.getByRole('dialog', { name: en.header.menu })
    await expect(sheet).toBeVisible()
    const body = sheet.locator('[data-slot="body"]')
    await expect.poll(() => body.evaluate(element => element.scrollHeight - element.clientHeight)).toBeGreaterThan(100)
    const link = body.getByRole('link').first()
    expect(await moveIsCancelled(link, -30), 'up: the sheet scrolls').toBe(false)
    expect(await moveIsCancelled(link, 30), 'down at the top: not on to the page').toBe(true)
  })

  test('is not held by the settings popover, which is no modal and is not the guard\'s', async ({ page, baseURL }) => {
    await home(page, baseURL!)
    await page.getByRole('button', { name: en.common.settings }).click()
    const popover = page.getByRole('dialog').first()
    await expect(popover).toBeVisible()
    expect(await moveIsCancelled(popover, 30)).toBe(false)
    expect(await moveIsCancelled(popover, -30)).toBe(false)
  })

  test.describe('on a browser that is not iOS', () => {
    test.use({ userAgent: 'Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36' })

    test('the search is left to overscroll-behavior: the guard is not held', async ({ page, baseURL }) => {
      await home(page, baseURL!)
      await page.getByRole('button', { name: en.shell.search }).click()
      const dialog = page.getByRole('dialog', { name: en.shell.search })
      await expect(dialog).toBeVisible()
      const option = dialog.getByRole('listbox', { name: en.shell.results }).getByRole('option').first()
      expect(await moveIsCancelled(option, 30), 'down at the top').toBe(false)
      expect(await moveIsCancelled(palette(dialog)[0]!, 30), 'on the field').toBe(false)
    })
  })

  test('leaves a pan of a zoomed-in page alone', async ({ page, baseURL }) => {
    await home(page, baseURL!)
    await page.getByRole('button', { name: en.shell.search }).click()
    const dialog = page.getByRole('dialog', { name: en.shell.search })
    await expect(dialog).toBeVisible()
    const option = dialog.getByRole('listbox', { name: en.shell.results }).getByRole('option').first()
    // a page that is zoomed in reports a visual viewport scale above 1 (the emulation cannot pinch)
    await page.evaluate(() => Object.defineProperty(window, 'visualViewport', { value: { scale: 2 }, configurable: true }))
    expect(await moveIsCancelled(option, 30)).toBe(false)
  })

  test('a move on the page with no dialog open is the page\'s own', async ({ page, baseURL }) => {
    await home(page, baseURL!)
    expect(await moveIsCancelled(page.getByTestId('ask'), -30)).toBe(false)
    expect(await moveIsCancelled(page.getByTestId('ask'), 30)).toBe(false)
  })
})

// The page behind a modal dialog on iOS (GH-3761): fixed where it stands while a modal is open, its offset given back
// on close, and the dialog laid out by the visual viewport. The user agent is an iPhone's (the lock is iOS's, as
// reka-ui's guard); the visual viewport is a script's, since Chromium's does not shrink for a keyboard that is not there.
test.describe('the page behind a modal dialog, held on iOS (GH-3761)', () => {
  test.use({ userAgent: IPHONE })

  const openSearch = (page: Page) => page.getByRole('button', { name: en.shell.search }).evaluate(button => (button as HTMLElement).click())
  const bodyStyle = (page: Page) => page.evaluate(() => ({
    position: document.body.style.position,
    top: document.body.style.top,
    overscroll: [document.documentElement, document.body].map(element => element.style.getPropertyValue('overscroll-behavior')),
    locked: document.documentElement.hasAttribute('data-dialog-viewport'),
  }))

  test('fixes the body at the scroll offset while the search is open, and gives the offset back, exactly, on close', async ({ page, baseURL }) => {
    await home(page, baseURL!)
    await scrollPage(page)
    // the header stands where it stood, and so does the page under the dialog
    const headerTop = await page.locator('.app-header').evaluate(element => element.getBoundingClientRect().top)
    const mainTop = await page.locator('.app-main').evaluate(element => element.getBoundingClientRect().top)

    await openSearch(page)
    const dialog = page.getByRole('dialog', { name: en.shell.search })
    await expect(dialog).toBeVisible()
    expect(await bodyStyle(page)).toEqual({ position: 'fixed', top: `-${PAGE_OFFSET}px`, overscroll: ['none', 'none'], locked: true })
    expect(await page.evaluate(() => document.documentElement.scrollTop), 'nothing is left to scroll').toBe(0)
    expect(await page.evaluate(() => window.scrollY), 'and the page is at its offset for whoever asks').toBe(PAGE_OFFSET)
    expect(await page.locator('.app-header').evaluate(element => element.getBoundingClientRect().top), 'the sticky header does not jump').toBe(headerTop)
    expect(await page.locator('.app-main').evaluate(element => element.getBoundingClientRect().top), 'the page does not jump').toBe(mainTop)

    await page.keyboard.press('Escape')
    await expect(dialog).toBeHidden()
    await expect.poll(() => bodyStyle(page)).toEqual({ position: '', top: '', overscroll: ['', ''], locked: false })
    expect(await page.evaluate(() => window.scrollY)).toBe(PAGE_OFFSET)
    expect(await page.locator('.app-main').evaluate(element => element.getBoundingClientRect().top)).toBe(mainTop)
  })

  test('holds the page for the place dialog and the menu sheet too, one after the other, and restores the offset each time', async ({ page, baseURL }) => {
    await home(page, baseURL!)
    await page.setViewportSize({ width: 412, height: 520 })
    await scrollPage(page)

    await page.getByTestId('place-button').evaluate(button => (button as HTMLElement).click())
    const place = page.getByRole('dialog', { name: en.ask.placeDialogTitle })
    await expect(place).toBeVisible()
    expect((await bodyStyle(page)).position).toBe('fixed')
    await page.keyboard.press('Escape')
    await expect(place).toBeHidden()
    await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(PAGE_OFFSET)

    await page.getByRole('button', { name: en.header.menu, exact: true }).evaluate(button => (button as HTMLElement).click())
    const sheet = page.getByRole('dialog', { name: en.header.menu })
    await expect(sheet).toBeVisible()
    expect(await bodyStyle(page)).toMatchObject({ position: 'fixed', top: `-${PAGE_OFFSET}px` })
    await page.keyboard.press('Escape')
    await expect(sheet).toBeHidden()
    await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(PAGE_OFFSET)
    expect((await bodyStyle(page)).position).toBe('')
  })

  test('a step of the history with the search open: the page that is left keeps its place, the one that is arrived at is not moved to it', async ({ page, baseURL }) => {
    await home(page, baseURL!)
    // by the router's links, so that it keeps the positions: the home page, About, the home page again
    await page.locator('a[href="/about"]').first().evaluate(link => (link as HTMLElement).click())
    await expect(page).toHaveURL(/\/about$/)
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
    const offsetOfAbout = 300
    expect(await page.evaluate(() => document.documentElement.scrollHeight - window.innerHeight), 'About has room to scroll').toBeGreaterThan(offsetOfAbout + 100)
    await page.evaluate(offset => window.scrollTo(0, offset), offsetOfAbout)
    await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(offsetOfAbout)

    await page.locator('.brand').click()
    await expect(page.getByTestId('ask')).toBeVisible()
    const offsetOfHome = 2000
    await page.evaluate(offset => window.scrollTo(0, offset), offsetOfHome)
    await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(offsetOfHome)

    await openSearch(page)
    const dialog = page.getByRole('dialog', { name: en.shell.search })
    await expect(dialog).toBeVisible()
    expect((await bodyStyle(page)).position).toBe('fixed')
    // what the router reads of the page it leaves while the body is fixed
    expect(await page.evaluate(() => window.scrollY), 'the page is still at its offset as far as the router can tell').toBe(offsetOfHome)

    // the back swipe: the dialog goes with the route and the page that is arrived at is not put where the other one was
    await page.goBack()
    await expect(page).toHaveURL(/\/about$/)
    await expect(dialog).toBeHidden()
    await expect.poll(() => bodyStyle(page)).toEqual({ position: '', top: '', overscroll: ['', ''], locked: false })
    expect(await page.evaluate(() => window.scrollY), 'About is not moved to the offset of the home page').toBeLessThanOrEqual(offsetOfAbout)

    // and forward again: the home page is where it was left, 2000 (the router saved it as that, not as 0)
    await page.goForward()
    await expect(page.getByTestId('ask')).toBeVisible()
    await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(offsetOfHome)
  })

  test('lets go of the page at once on close, and of the dialog\'s layout by the visual viewport when it has left', async ({ page, baseURL }) => {
    await home(page, baseURL!)
    await scrollPage(page)
    await openSearch(page)
    const dialog = page.getByRole('dialog', { name: en.shell.search })
    await expect(dialog).toBeVisible()
    await expect(dialog.getByRole('combobox')).toBeFocused()
    expect((await bodyStyle(page)).locked).toBe(true)

    await page.keyboard.press('Escape')
    // on its way out (reka-ui keeps it for the length of the animation): the page is in the flow, at its offset, the field
    // has let go of the focus (the keyboard drops), and the dialog is still laid out by the visual viewport
    const leaving = await page.evaluate(() => ({
      dialog: !!document.querySelector('[role="dialog"]'),
      position: document.body.style.position,
      scrollY: window.scrollY,
      layout: document.documentElement.hasAttribute('data-dialog-viewport'),
      fieldFocused: document.activeElement?.getAttribute('role') === 'combobox',
    }))
    expect(leaving.dialog, 'the dialog is still there').toBe(true)
    expect(leaving.position).toBe('')
    expect(leaving.scrollY).toBe(PAGE_OFFSET)
    expect(leaving.layout, 'and still laid out by the visual viewport').toBe(true)
    expect(leaving.fieldFocused, 'the field has let go of the focus').toBe(false)

    await expect(dialog).toBeHidden()
    await expect.poll(() => bodyStyle(page)).toEqual({ position: '', top: '', overscroll: ['', ''], locked: false })
    expect(await page.evaluate(() => window.scrollY)).toBe(PAGE_OFFSET)
  })

  test('does not hold the settings popover, which is no modal', async ({ page, baseURL }) => {
    await home(page, baseURL!)
    await scrollPage(page)
    await page.getByRole('button', { name: en.common.settings }).evaluate(button => (button as HTMLElement).click())
    await expect(page.getByRole('dialog').first()).toBeVisible()
    expect((await bodyStyle(page)).position).toBe('')
  })

  test.describe('on a browser that is not iOS', () => {
    test.use({ userAgent: 'Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36' })

    test('leaves the body to reka-ui\'s overflow', async ({ page, baseURL }) => {
      await home(page, baseURL!)
      await scrollPage(page)
      await openSearch(page)
      await expect(page.getByRole('dialog', { name: en.shell.search })).toBeVisible()
      expect(await bodyStyle(page)).toEqual({ position: '', top: '', overscroll: ['', ''], locked: false })
      expect(await page.evaluate(() => window.scrollY)).toBe(PAGE_OFFSET)
    })
  })

  for (const [name, size] of [['below sm', { width: 412, height: 839 }], ['from sm', { width: 820, height: 1000 }]] as const) {
    test.describe(`the dialog in the visual viewport, ${name}`, () => {
      test.use({ viewport: size })

      test('stays inside what is on the screen as the keyboard shrinks and pans it, the list\'s last entry above it', async ({ page, baseURL }) => {
        // a visual viewport of the test's, which the page reads as it would Safari's
        await page.addInitScript((height) => {
          class Viewport extends EventTarget {
            height = height
            offsetTop = 0
            scale = 1
          }
          Object.defineProperty(window, 'visualViewport', { value: new Viewport(), configurable: true })
        }, size.height)
        await home(page, baseURL!)
        await openSearch(page)
        const dialog = page.getByRole('dialog', { name: en.shell.search })
        await expect(dialog).toBeVisible()
        const list = dialog.getByRole('listbox', { name: en.shell.results })

        // the keyboard: 330 px of the screen left, panned 200 px down
        await page.evaluate(() => {
          const viewport = window.visualViewport as unknown as { height: number, offsetTop: number } & EventTarget
          viewport.height = 330
          viewport.offsetTop = 200
          viewport.dispatchEvent(new Event('resize'))
        })
        await expect.poll(async () => {
          const box = (await dialog.boundingBox())!
          return box.y + box.height <= 200 + 330 + 1 && box.y >= 200 - 1
        }, { message: 'the dialog is inside the visual viewport' }).toBe(true)
        await expect(dialog.getByRole('combobox')).toBeInViewport()

        // the list still scrolls, and its last entry can be brought above the keyboard
        await expect.poll(() => list.evaluate(element => element.scrollHeight - element.clientHeight)).toBeGreaterThan(50)
        await list.evaluate(element => element.scrollTo(0, element.scrollHeight))
        const last = list.getByRole('option').last()
        const box = (await last.boundingBox())!
        expect(box.y + box.height).toBeLessThanOrEqual(200 + 330 + 1)
        expect(box.y).toBeGreaterThanOrEqual(200)

        // and without the keyboard it is as it was
        await page.evaluate((height) => {
          const viewport = window.visualViewport as unknown as { height: number, offsetTop: number } & EventTarget
          viewport.height = height
          viewport.offsetTop = 0
          viewport.dispatchEvent(new Event('resize'))
        }, size.height)
        await expect.poll(async () => (await dialog.boundingBox())!.height).toBeGreaterThan(400)
      })
    })
  }
})
