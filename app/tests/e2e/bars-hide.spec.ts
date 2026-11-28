import type { Page } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { expect, test } from '@playwright/test'
import { mockBackend } from './accessibility/mock-backend'
import { expectAtLeastPx } from './target-size'

// The bars of the phone hide on scroll and the top bar is slimmer (GH-4226), in Chromium: scrolling down slides the top bar up
// and the tab bar down, scrolling up or the top brings them back, a focus in either brings both back, the map page keeps them,
// and a desktop and a tablet are as they were. The backend is the accessibility spec's mock.

const en = JSON.parse(readFileSync(fileURLToPath(new URL('../../i18n/locales/en.json', import.meta.url)), 'utf-8'))

/** A page long enough to scroll on a phone, whatever it holds */
const LONG_PAGE = '/about'

async function open(page: Page, baseURL: string, path: string, size: { width: number, height: number }, options: { reducedMotion?: boolean, untouched?: boolean } = {}) {
  await page.setViewportSize(size)
  if (options.reducedMotion)
    await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.context().addCookies([{ name: 'wd_lang', value: 'en', url: baseURL }])
  await mockBackend(page, baseURL)
  await page.goto(path)
  await expect(page.getByRole('heading', { level: 1 }).first()).toBeVisible({ timeout: 20_000 })
  // the shell is hydrated when the attribute-driven rules can be set: the search button answers a click
  await expect(page.getByRole('button', { name: en.shell.search })).toBeEnabled()
  if (options.untouched)
    return
  // the reader's first input: a page keeps its bars until one, and after it every scroll counts, a script's `scrollTo` here as well
  await page.mouse.move(200, 400)
  await page.mouse.wheel(0, 1)
}

const header = (page: Page) => page.locator('.app-header')
const tabbar = (page: Page) => page.locator('.app-tabbar')
const attribute = (page: Page) => page.locator('html').getAttribute('data-bars')
const scrollTo = (page: Page, y: number) => page.evaluate(top => window.scrollTo({ top, behavior: 'instant' }), y)

/** Waits until a bar has finished sliding (its box stops moving) and answers where it is */
async function settled(page: Page, bar: 'header' | 'tabbar') {
  const locator = bar === 'header' ? header(page) : tabbar(page)
  let last = Number.NaN
  await expect.poll(async () => {
    const box = (await locator.boundingBox())!
    const same = box.y === last
    last = box.y
    return same
  }, { timeout: 3000 }).toBe(true)
  return (await locator.boundingBox())!
}

async function expectShown(page: Page, size: { width: number, height: number }) {
  await expect.poll(() => attribute(page)).toBeNull()
  const top = await settled(page, 'header')
  const foot = await settled(page, 'tabbar')
  expect(top.y).toBeCloseTo(0, 0)
  expect(foot.y + foot.height).toBeCloseTo(size.height, 0)
}

async function expectHidden(page: Page, size: { width: number, height: number }) {
  await expect.poll(() => attribute(page)).toBe('hidden')
  const top = await settled(page, 'header')
  const foot = await settled(page, 'tabbar')
  // the top bar is over the window's top edge and the tab bar under its foot: nothing of either is in view
  expect(top.y + top.height).toBeLessThanOrEqual(0.5)
  expect(foot.y).toBeGreaterThanOrEqual(size.height - 0.5)
}

const PHONE = { width: 390, height: 800 }

test.describe('the bars of a phone, 390 px wide', () => {
  test('the top bar is 44 px with a smaller logo and name, and two named 44 px icon buttons', async ({ page, baseURL }) => {
    await open(page, baseURL!, LONG_PAGE, PHONE)
    const bar = (await header(page).boundingBox())!
    // 44 px of bar and the hairline under it (the wider layouts' is 64 px)
    expect(bar.height).toBeGreaterThanOrEqual(44)
    expect(bar.height).toBeLessThanOrEqual(46)
    const logo = (await header(page).locator('img').boundingBox())!
    expect(logo.height).toBeCloseTo(28, 0)
    const search = page.getByRole('button', { name: en.shell.search })
    const settings = page.getByRole('button', { name: en.common.settings })
    for (const button of [search, settings]) {
      const box = (await button.boundingBox())!
      expectAtLeastPx(box.width, 44)
      expectAtLeastPx(box.height, 44)
      expect(box.y).toBeGreaterThanOrEqual(bar.y - 0.5)
      expect(box.y + box.height).toBeLessThanOrEqual(bar.y + bar.height + 0.5)
    }
    // the name is written out beside the logo and is the link's name
    await expect(header(page).getByRole('link', { name: 'Wetterdienst' })).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1)).toBe(true)
  })

  test('hides on scrolling down, comes back on scrolling up, and at the top', async ({ page, baseURL }) => {
    await open(page, baseURL!, LONG_PAGE, PHONE)
    expect(await page.evaluate(() => document.documentElement.scrollHeight)).toBeGreaterThan(1500)
    await expectShown(page, PHONE)

    await scrollTo(page, 400)
    await expectHidden(page, PHONE)

    // up by a little more than the threshold
    await scrollTo(page, 380)
    await expectShown(page, PHONE)

    await scrollTo(page, 700)
    await expectHidden(page, PHONE)
    // the top is enough: one jump, no gradual way back
    await scrollTo(page, 0)
    await expectShown(page, PHONE)
  })

  test('the real wheel hides and shows the bars, not only a script\'s scroll', async ({ page, baseURL }) => {
    await open(page, baseURL!, LONG_PAGE, PHONE)
    await page.mouse.move(200, 400)
    await page.mouse.wheel(0, 500)
    await expectHidden(page, PHONE)
    await page.mouse.wheel(0, -100)
    await expectShown(page, PHONE)
  })

  test('a touch drag of a finger hides the bars going up the screen and shows them going down it', async ({ page, baseURL }) => {
    await open(page, baseURL!, LONG_PAGE, PHONE, { untouched: true })
    // a finger as Chromium's input makes it (CDP touch events), which the page sees as touchstart, touchmove and touchend
    const client = await page.context().newCDPSession(page)
    await client.send('Emulation.setTouchEmulationEnabled', { enabled: true, maxTouchPoints: 1 })
    async function drag(fromY: number, toY: number) {
      const steps = 12
      await client.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x: 200, y: fromY }] })
      for (let step = 1; step <= steps; step++)
        await client.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x: 200, y: fromY + (toY - fromY) * step / steps }] })
      await client.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] })
    }
    // the finger goes up the screen: the page goes down
    await drag(700, 150)
    await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(300)
    await expectHidden(page, PHONE)
    // the finger goes down the screen: the page goes up
    await drag(200, 500)
    await expectShown(page, PHONE)
  })

  test('a page that arrives scrolled to an anchor keeps the bars until the reader\'s first touch, wheel, key or press, and not after it', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/settings#bar', PHONE, { untouched: true })
    await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(200)
    await page.waitForTimeout(300)
    expect(await attribute(page)).toBeNull()
    await scrollTo(page, 900)
    await page.waitForTimeout(300)
    expect(await attribute(page)).toBeNull()
    // the first input of the reader, then the scroll that follows it
    await page.mouse.move(200, 400)
    await page.mouse.wheel(0, 300)
    await expectHidden(page, PHONE)
    // and a script's scroll counts from then on: the gate is one-shot for the page
    await scrollTo(page, (await page.evaluate(() => window.scrollY)) - 60)
    await expectShown(page, PHONE)
  })

  test('a small scroll, a tremble and the first pixels of the page change nothing', async ({ page, baseURL }) => {
    await open(page, baseURL!, LONG_PAGE, PHONE)
    // the first 48 px: the bars stay, however fast
    await scrollTo(page, 40)
    await page.waitForTimeout(300)
    expect(await attribute(page)).toBeNull()
    await scrollTo(page, 200)
    await expectHidden(page, PHONE)
    // a few pixels back and forth (a finger's tremble, a rubber band) is no turn
    for (const y of [204, 198, 203, 199, 205, 201])
      await scrollTo(page, y)
    await page.waitForTimeout(300)
    expect(await attribute(page)).toBe('hidden')
    // and the same from the other side: bars in view, a few pixels down
    await scrollTo(page, 150)
    await expectShown(page, PHONE)
    for (const y of [154, 148, 153, 149])
      await scrollTo(page, y)
    await page.waitForTimeout(300)
    expect(await attribute(page)).toBeNull()
  })

  test('slides: nothing of the page moves, and the page is as long with the bars hidden as shown', async ({ page, baseURL }) => {
    await open(page, baseURL!, LONG_PAGE, PHONE)
    const before = await page.evaluate(() => ({ height: document.documentElement.scrollHeight, main: document.querySelector('main')!.getBoundingClientRect().height }))
    await scrollTo(page, 600)
    await expectHidden(page, PHONE)
    const after = await page.evaluate(() => ({ height: document.documentElement.scrollHeight, main: document.querySelector('main')!.getBoundingClientRect().height }))
    expect(after).toEqual(before)
    // a transform, not a size: both bars have the size they had
    expect((await header(page).boundingBox())!.height).toBeGreaterThanOrEqual(44)
    expect((await tabbar(page).boundingBox())!.height).toBeGreaterThanOrEqual(68)
  })

  test('is animated, and not for a reader who asks for no motion', async ({ page, baseURL }) => {
    await open(page, baseURL!, LONG_PAGE, PHONE)
    // each element that moves with the bars transitions its own property (the compositor runs the bars' transform); the root and
    // the page under it transition nothing, so that a frame of the slide restyles those elements and not every element of the page
    const transition = (selector: string) => page.locator(selector).first().evaluate((element) => {
      const style = getComputedStyle(element)
      return { property: style.transitionProperty, duration: style.transitionDuration }
    })
    const root = () => page.evaluate(() => {
      const style = getComputedStyle(document.documentElement)
      return { property: style.transitionProperty, duration: style.transitionDuration }
    })
    const shown = { property: 'transform, top, bottom', duration: '0.2s, 0.2s, 0.2s' }
    for (const selector of ['.app-header', '.app-tabbar'])
      expect(await transition(selector)).toEqual(shown)
    expect(await root()).toEqual({ property: 'all', duration: '0s' })
    await scrollTo(page, 500)
    await expectHidden(page, PHONE)
    expect(await transition('.app-header')).toEqual({ property: 'transform, top, bottom', duration: '0.16s' })
    expect(await root()).toEqual({ property: 'all', duration: '0s' })
  })

  test('with prefers-reduced-motion the bars are away at once, with no transition', async ({ page, baseURL }) => {
    await open(page, baseURL!, LONG_PAGE, PHONE, { reducedMotion: true })
    // nothing is transitioned (the app's own rule for the setting sets the duration of everything else to 0.01 ms)
    const property = () => page.locator('.app-header').evaluate(element => getComputedStyle(element).transitionProperty)
    expect(await property()).toBe('none')
    expect(await tabbar(page).evaluate(element => getComputedStyle(element).transitionProperty)).toBe('none')
    await scrollTo(page, 500)
    await expect.poll(() => attribute(page)).toBe('hidden')
    // no waiting for it to settle: one frame
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))))
    const top = (await header(page).boundingBox())!
    expect(top.y + top.height).toBeLessThanOrEqual(0.5)
    expect(await property()).toBe('none')
    await scrollTo(page, 480)
    await expect.poll(() => attribute(page)).toBeNull()
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))))
    expect((await header(page).boundingBox())!.y).toBeCloseTo(0, 0)
  })

  test('a focus in either bar brings both back, and the landmarks are there while they are away', async ({ page, baseURL }) => {
    await open(page, baseURL!, LONG_PAGE, PHONE)
    const landmarks = async () => ({
      banner: await page.getByRole('banner').count(),
      navigation: await page.getByRole('navigation', { name: en.shell.mainNav }).count(),
    })
    const shown = await landmarks()
    expect(shown.banner).toBe(1)
    expect(shown.navigation).toBeGreaterThanOrEqual(1)

    await scrollTo(page, 500)
    await expectHidden(page, PHONE)
    // the bars are still in the page: the same landmarks, in the tree
    expect(await landmarks()).toEqual(shown)

    // by a key: the Tab that reaches the tab bar from the page after it, as Shift+Tab does
    await page.locator('.app-tabbar a').first().focus()
    await expectShown(page, PHONE)

    // (the focus is on the page again: a focus that stays in a bar holds the bars, the next tests)
    await page.locator('main').focus()
    await scrollTo(page, 900)
    await expectHidden(page, PHONE)
    await page.getByRole('button', { name: en.shell.search }).focus()
    await expectShown(page, PHONE)
    await page.locator('main').focus()

    // and the keyboard itself: from the page, Shift+Tab goes up to the bars
    await scrollTo(page, 1300)
    await expectHidden(page, PHONE)
    await page.locator('main').focus()
    await page.keyboard.press('Shift+Tab')
    await expectShown(page, PHONE)
    await expect(page.locator('.app-tabbar a, .app-tabbar button').last()).toBeFocused()
  })

  test('the skip link is not in a bar: it has the top of the window to itself while the bars are away, and takes the focus to the page', async ({ page, baseURL }) => {
    await open(page, baseURL!, LONG_PAGE, PHONE)
    await scrollTo(page, 500)
    await expectHidden(page, PHONE)
    const skip = page.getByRole('link', { name: en.shell.skipToContent })
    await skip.focus()
    await expect(skip).toBeFocused()
    const link = (await skip.boundingBox())!
    expect(link.y).toBeGreaterThanOrEqual(0)
    expect(link.y + link.height).toBeLessThanOrEqual(PHONE.height)
    // it is not a bar: the bars stay where they were
    expect(await attribute(page)).toBe('hidden')
    await page.keyboard.press('Enter')
    await expect(page.locator('main')).toBeFocused()
  })

  test('the search opens over the bar, stays open on a scroll, closes with Escape and gives the focus back', async ({ page, baseURL }) => {
    await open(page, baseURL!, LONG_PAGE, PHONE)
    const search = page.getByRole('button', { name: en.shell.search })
    await search.click()
    const dialog = page.getByRole('dialog', { name: en.shell.search })
    await expect(dialog).toBeVisible()
    // a bar of its own at the top of the window, over the top bar, as wide as the window (once it has stopped opening)
    await expect.poll(async () => {
      const box = (await dialog.boundingBox())!
      return [Math.round(box.x), Math.round(box.y), Math.round(box.width)]
    }).toEqual([0, 0, PHONE.width])
    await expect(page.getByRole('combobox', { name: en.shell.search })).toBeFocused()
    expect(await attribute(page)).toBeNull()

    await page.keyboard.press('Escape')
    await expect(dialog).toBeHidden()
    await expect(search).toBeFocused()
  })

  test('does not hide while the focus is in a bar: the search button after Escape is not scrolled out of view', async ({ page, baseURL }) => {
    await open(page, baseURL!, LONG_PAGE, PHONE)
    const search = page.getByRole('button', { name: en.shell.search })
    await search.click()
    await expect(page.getByRole('dialog', { name: en.shell.search })).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(search).toBeFocused()
    await page.mouse.move(200, 400)
    await page.mouse.wheel(0, 600)
    await page.waitForTimeout(400)
    expect(await attribute(page)).toBeNull()
    await expect(search).toBeInViewport()
    // the focus goes to the page: the next scroll down hides them
    await page.locator('main').focus()
    await page.mouse.wheel(0, 200)
    await expectHidden(page, PHONE)
  })

  test('does not hide while a popover is open', async ({ page, baseURL }) => {
    await open(page, baseURL!, LONG_PAGE, PHONE)
    await page.getByRole('button', { name: en.common.settings }).click()
    await expect(page.getByText(en.settings.theme, { exact: true })).toBeVisible()
    await scrollTo(page, 600)
    await page.waitForTimeout(400)
    expect(await attribute(page)).toBeNull()
    expect((await header(page).boundingBox())!.y).toBeCloseTo(0, 0)
  })

  test('does not hide while the Menu sheet is open, and works again once it is closed', async ({ page, baseURL }) => {
    await open(page, baseURL!, LONG_PAGE, PHONE)
    await tabbar(page).getByRole('button', { name: en.header.menu, exact: true }).click()
    await expect(page.getByRole('dialog', { name: en.header.menu })).toBeVisible()
    await scrollTo(page, 600)
    await page.waitForTimeout(300)
    expect(await attribute(page)).toBeNull()
    // closed by a press of the pointer: the focus is handed back to the tab, which a pointer's press does not make a focus that shows
    await page.getByRole('dialog', { name: en.header.menu }).getByRole('button', { name: en.common.close }).click()
    await expect(page.getByRole('dialog', { name: en.header.menu })).toBeHidden()
    await scrollTo(page, 900)
    await expectHidden(page, PHONE)
  })

  test('a control of a bar that a pointer has pressed does not hold the bars: a tapped tab stays focused on Android', async ({ page, baseURL }) => {
    await open(page, baseURL!, LONG_PAGE, PHONE)
    await tabbar(page).getByRole('button', { name: en.header.menu, exact: true }).click()
    await page.getByRole('dialog', { name: en.header.menu }).getByRole('button', { name: en.common.close }).click()
    await expect(tabbar(page).getByRole('button', { name: en.header.menu, exact: true })).toBeFocused()
    await page.mouse.move(200, 400)
    await page.mouse.wheel(0, 600)
    await expectHidden(page, PHONE)
  })

  test('on another page the bars are back', async ({ page, baseURL }) => {
    await open(page, baseURL!, LONG_PAGE, PHONE)
    await scrollTo(page, 500)
    await expectHidden(page, PHONE)
    await page.locator('.app-tabbar a').first().evaluate(link => (link as HTMLAnchorElement).click())
    await expectShown(page, PHONE)
  })

  test('the settings page\'s sticky bar preview follows the top bar as it hides and returns', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/settings', PHONE)
    const preview = page.locator('.bar-sticky')
    const bar = (await header(page).boundingBox())!
    const chooserTop = await preview.evaluate(element => element.getBoundingClientRect().top + window.scrollY)
    // down into the chooser, where the preview sticks
    await scrollTo(page, chooserTop + 300)
    await expectHidden(page, PHONE)
    // the top bar is away: the preview sticks to the window's top edge
    await expect.poll(async () => Math.round((await preview.boundingBox())!.y)).toBe(0)
    await scrollTo(page, chooserTop + 250)
    await expectShown(page, PHONE)
    // the top bar is back: the preview stands under it
    await expect.poll(async () => Math.round((await preview.boundingBox())!.y)).toBe(Math.round(bar.height))
    await scrollTo(page, chooserTop + 400)
    await expectHidden(page, PHONE)
    await expect.poll(async () => Math.round((await preview.boundingBox())!.y)).toBe(0)
  })

  test('the map page keeps both bars in view, and its map fills the window between them', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/map', PHONE)
    await expect(page.getByTestId('map-screen').locator('.leaflet-container')).toBeVisible()
    await scrollTo(page, 600)
    await page.waitForTimeout(400)
    expect(await attribute(page)).toBeNull()
    await scrollTo(page, 0)
    await expectShown(page, PHONE)
    const stage = (await page.getByTestId('map-stage').boundingBox())!
    const top = (await header(page).boundingBox())!
    const foot = (await tabbar(page).boundingBox())!
    expect(stage.y).toBeGreaterThanOrEqual(top.y + top.height - 0.5)
    expect(stage.y + stage.height).toBeCloseTo(foot.y, 0)
  })

  test('a window as low as a phone on its side has bars that scroll with the page, and no hiding', async ({ page, baseURL }) => {
    await open(page, baseURL!, LONG_PAGE, { width: 560, height: 300 })
    await scrollTo(page, 600)
    await page.waitForTimeout(400)
    expect(await attribute(page)).toBeNull()
    expect(await header(page).evaluate(element => getComputedStyle(element).position)).toBe('static')
  })
})

test.describe('the bars of a narrow phone, 320 px wide', () => {
  test('the top bar holds the logo, the name and both buttons, and the page does not scroll sideways', async ({ page, baseURL }) => {
    await open(page, baseURL!, LONG_PAGE, { width: 320, height: 640 })
    const bar = (await header(page).boundingBox())!
    const search = (await page.getByRole('button', { name: en.shell.search }).boundingBox())!
    const settings = (await page.getByRole('button', { name: en.common.settings }).boundingBox())!
    expect(search.x + search.width).toBeLessThanOrEqual(settings.x + 0.5)
    expect(settings.x + settings.width).toBeLessThanOrEqual(320)
    expect(bar.width).toBeCloseTo(320, 0)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1)).toBe(true)
    await scrollTo(page, 500)
    await expectHidden(page, { width: 320, height: 640 })
  })

  test('the map page fills the window between the bars', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/map', { width: 320, height: 640 })
    await expect(page.getByTestId('map-screen').locator('.leaflet-container')).toBeVisible()
    // the reader's first input (`open`) is a wheel of one pixel, which scrolls the page by it where the page is taller than the window
    // (the map's panel is under it): the stage is measured at the top, as the 390 px test measures it
    await scrollTo(page, 0)
    const stage = (await page.getByTestId('map-stage').boundingBox())!
    const foot = (await tabbar(page).boundingBox())!
    expect(stage.y + stage.height).toBeCloseTo(foot.y, 0)
  })

  // GH-4514: the title's height is measured, and a title that is not a whole number of pixels high (a font, a zoom, a line
  // height) must not leave the stage short of the bar by what rounding it up takes away
  for (const extra of [0.2, 0.5, 0.8]) {
    test(`the map page ends at the tab bar under a title ${extra} px past a whole pixel`, async ({ page, baseURL }) => {
      await open(page, baseURL!, '/map', { width: 320, height: 640 })
      await expect(page.getByTestId('map-screen').locator('.leaflet-container')).toBeVisible()
      await page.addStyleTag({ content: `.page-header { padding-bottom: calc(${extra}px + 0.5rem) !important; }` })
      await scrollTo(page, 0)
      const head = page.locator('.page-header')
      // the title's height has to be one that is not whole, or this tests nothing
      await expect.poll(async () => (await head.boundingBox())!.height % 1).toBeGreaterThan(0.01)
      const foot = (await tabbar(page).boundingBox())!
      await expect.poll(async () => {
        const stage = (await page.getByTestId('map-stage').boundingBox())!
        return Math.abs(stage.y + stage.height - foot.y)
      }).toBeLessThan(0.1)
    })
  }
})

for (const size of [{ width: 820, height: 1180 }, { width: 1280, height: 800 }]) {
  test.describe(`${size.width < 1000 ? 'a tablet' : 'a desktop'}, ${size.width} px wide`, () => {
    test('the bars do not hide, and the top bar is the 64 px it was', async ({ page, baseURL }) => {
      await open(page, baseURL!, LONG_PAGE, size)
      const bar = (await header(page).boundingBox())!
      expect(bar.height).toBeCloseTo(64, 0)
      await scrollTo(page, 800)
      await page.waitForTimeout(400)
      expect(await attribute(page)).toBeNull()
      expect((await header(page).boundingBox())!.y).toBeCloseTo(0, 0)
      expect(await header(page).evaluate(element => getComputedStyle(element).transform)).toBe('none')
      if (size.width < 1000) {
        // the tab bar stands to 64 rem
        expect((await tabbar(page).boundingBox())!.y + (await tabbar(page).boundingBox())!.height).toBeCloseTo(size.height, 0)
        expect(await tabbar(page).evaluate(element => getComputedStyle(element).transform)).toBe('none')
      }
      await scrollTo(page, 200)
      expect(await attribute(page)).toBeNull()
    })

    test('the buttons are the size they were', async ({ page, baseURL }) => {
      await open(page, baseURL!, LONG_PAGE, size)
      const box = (await page.getByRole('button', { name: en.common.settings }).boundingBox())!
      expect(box.width).toBeLessThan(40)
    })
  })
}
