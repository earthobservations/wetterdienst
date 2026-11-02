import type { Page } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { expect, test } from '@playwright/test'
import { mockBackend } from './accessibility/mock-backend'

// The shell of the app (GH-3518): the header with the four tools and the reference, the search, the tab bar and the
// menu sheet of the narrow layout, the skip link, and the one frame every page sits in. The backend is the
// accessibility spec's mock, so nothing here reaches a provider.

const en = JSON.parse(readFileSync(fileURLToPath(new URL('../../i18n/locales/en.json', import.meta.url)), 'utf-8'))
const de = JSON.parse(readFileSync(fileURLToPath(new URL('../../i18n/locales/de.json', import.meta.url)), 'utf-8'))

async function open(page: Page, baseURL: string, path: string, language = 'en') {
  await page.context().addCookies([{ name: 'wd_lang', value: language, url: baseURL }])
  await mockBackend(page, baseURL)
  await page.goto(path)
  await expect(page.locator('html')).toHaveAttribute('lang', language)
  await expect(page.getByRole('heading', { level: 1 }).first()).toBeVisible()
}

test.describe('the wide header', () => {
  test.use({ viewport: { width: 1280, height: 800 } })

  test('names the tools as tabs and marks the one of the page', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/stripes')
    const nav = page.getByRole('navigation', { name: en.shell.mainNav })
    for (const key of ['meteogram', 'explorer', 'stripes', 'history'])
      await expect(nav.getByRole('link', { name: en.nav[key], exact: true })).toBeVisible()
    await expect(nav.getByRole('link', { name: en.nav.stripes, exact: true })).toHaveAttribute('aria-current', 'page')
    await expect(nav.locator('[aria-current="page"]')).toHaveCount(1)
    // the tab bar of the narrow layout is not there at this width
    await expect(page.getByRole('navigation')).toHaveCount(1)
  })

  test('opens the reference as a disclosure that Escape closes, giving the focus back', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/')
    const trigger = page.getByRole('button', { name: en.shell.reference, exact: true })
    await expect(trigger).toHaveAttribute('aria-expanded', 'false')
    await trigger.focus()
    await page.keyboard.press('Enter')
    await expect(trigger).toHaveAttribute('aria-expanded', 'true')
    const panel = page.locator(`[id="${await trigger.getAttribute('aria-controls')}"]`)
    await expect(panel.getByRole('link')).toHaveCount(3)
    // Tab walks into it, in the order it shows
    await page.keyboard.press('Tab')
    await expect(panel.getByRole('link').first()).toBeFocused()
    await page.keyboard.press('Escape')
    await expect(panel).toBeHidden()
    await expect(trigger).toBeFocused()
  })

  test('keeps the reference open on a click on its padding, which Escape then closes', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/')
    const trigger = page.getByRole('button', { name: en.shell.reference, exact: true })
    await trigger.click()
    const panel = page.locator(`[id="${await trigger.getAttribute('aria-controls')}"]`)
    const box = await panel.boundingBox()
    // the padding of the panel, at the middle of its left edge: no link, so the focus goes nowhere
    await page.mouse.click(box!.x + 4, box!.y + box!.height / 2)
    await expect(trigger).toHaveAttribute('aria-expanded', 'true')
    await page.keyboard.press('Escape')
    await expect(trigger).toHaveAttribute('aria-expanded', 'false')
  })

  test('leaves the reference to its own Escape where a dialog of the search is open over it', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/')
    const trigger = page.getByRole('button', { name: en.shell.reference, exact: true })
    await trigger.click()
    const box = await page.locator(`[id="${await trigger.getAttribute('aria-controls')}"]`).boundingBox()
    await page.mouse.click(box!.x + 4, box!.y + box!.height / 2)
    await page.keyboard.press('Control+k')
    const dialog = page.getByRole('dialog', { name: en.shell.search })
    await expect(dialog).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(dialog).toBeHidden()
    // one Escape closed one layer
    await expect(trigger).toHaveAttribute('aria-expanded', 'true')
  })

  test('closes the reference on the link of the page that is shown', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/glossary')
    const trigger = page.getByRole('button', { name: en.shell.reference, exact: true })
    await trigger.click()
    await page.locator(`[id="${await trigger.getAttribute('aria-controls')}"]`).getByRole('link', { name: en.nav.glossary }).click()
    await expect(trigger).toHaveAttribute('aria-expanded', 'false')
  })

  test('closes the reference when the focus leaves it, and on a click elsewhere', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/')
    const trigger = page.getByRole('button', { name: en.shell.reference, exact: true })
    await trigger.click()
    await expect(trigger).toHaveAttribute('aria-expanded', 'true')
    await page.getByRole('heading', { level: 1 }).click()
    await expect(trigger).toHaveAttribute('aria-expanded', 'false')

    await trigger.click()
    for (let stop = 0; stop < 4; stop++)
      await page.keyboard.press('Tab')
    await expect(trigger).toHaveAttribute('aria-expanded', 'false')
  })

  test('goes to the glossary through the reference, which marks the page', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/')
    await page.getByRole('button', { name: en.shell.reference, exact: true }).click()
    await page.getByRole('banner').getByRole('link', { name: new RegExp(`^${en.nav.glossary}`) }).click()
    await expect(page).toHaveURL(/\/glossary$/)
    await expect(page.getByRole('heading', { level: 1 })).toHaveText(en.glossary.title)
    // the trigger is shown as the section one is in; the link in it is the page
    await page.getByRole('button', { name: en.shell.reference, exact: true }).click()
    await expect(page.getByRole('banner').getByRole('link', { name: new RegExp(`^${en.nav.glossary}`) })).toHaveAttribute('aria-current', 'page')
  })
})

test.describe('the search', () => {
  test.use({ viewport: { width: 1280, height: 800 } })

  test('opens by Ctrl+K, finds a page by its name and goes there', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/')
    await page.keyboard.press('Control+k')
    const dialog = page.getByRole('dialog', { name: en.shell.search })
    await expect(dialog).toBeVisible()
    await page.keyboard.type('glossary')
    await expect(dialog.getByRole('option').first()).toContainText(en.nav.glossary)
    await page.keyboard.press('Enter')
    await expect(page).toHaveURL(/\/glossary$/)
    await expect(dialog).toBeHidden()
  })

  test('opens by ⌘K as well, on any system, and the same keys close it', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/')
    const dialog = page.getByRole('dialog', { name: en.shell.search })
    await page.keyboard.press('Meta+k')
    await expect(dialog).toBeVisible()
    await expect(dialog.getByRole('combobox', { name: en.shell.search })).toBeFocused()
    await page.keyboard.press('Meta+k')
    await expect(dialog).toBeHidden()
  })

  test('finds a provider by its short name', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/')
    await page.getByRole('button', { name: en.shell.search }).click()
    const dialog = page.getByRole('dialog', { name: en.shell.search })
    await page.keyboard.type('DWD')
    await dialog.getByRole('option', { name: /DWD/ }).first().click()
    await expect(page).toHaveURL(/\/providers\/dwd$/)
  })

  test('says so where nothing matches, and Escape gives the focus back to its button', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/')
    const button = page.getByRole('button', { name: en.shell.search })
    await button.focus()
    await page.keyboard.press('Enter')
    await page.keyboard.type('zzzzqqqq')
    await expect(page.getByText(en.shell.searchEmpty)).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(page.getByRole('dialog')).toBeHidden()
    await expect(button).toBeFocused()
  })

  test('switches the theme', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/')
    await page.keyboard.press('Control+k')
    await page.keyboard.type(en.settings.themeDark)
    await page.getByRole('option', { name: en.settings.themeDark }).first().click()
    await expect(page.locator('html')).toHaveClass(/dark/)
  })

  // the WAI-ARIA combobox pattern, by keys alone: the field keeps the focus and names the active option, the arrow keys
  // move it, Tab stays in the dialog, Enter takes the option, Escape closes and gives the focus back
  test('is operated by keys alone: a combobox with a listbox, in a dialog that keeps the focus', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/')
    const button = page.getByRole('button', { name: en.shell.search })
    await button.focus()
    await page.keyboard.press('Enter')
    const dialog = page.getByRole('dialog', { name: en.shell.search })
    const field = dialog.getByRole('combobox', { name: en.shell.search })
    await expect(field).toBeFocused()
    await expect(field).toHaveAttribute('aria-expanded', 'true')
    const list = dialog.getByRole('listbox', { name: en.shell.results })
    await expect(field).toHaveAttribute('aria-controls', (await list.getAttribute('id'))!)

    // the arrow keys move the active option, which is the one the field names and the only one selected
    const activeName = () => page.evaluate(() => {
      const id = document.activeElement?.getAttribute('aria-activedescendant')
      return id ? document.getElementById(id)?.textContent?.trim() ?? null : null
    })
    const first = await activeName()
    await page.keyboard.press('ArrowDown')
    await expect.poll(activeName).not.toBe(first)
    await expect(list.locator('[role="option"][aria-selected="true"]')).toHaveCount(1)
    await page.keyboard.press('ArrowUp')
    await expect.poll(activeName).toBe(first)

    // Tab and Shift+Tab never leave the dialog
    for (const key of ['Tab', 'Shift+Tab']) {
      for (let stop = 0; stop < 6; stop++) {
        await page.keyboard.press(key)
        expect(await dialog.evaluate(node => node.contains(document.activeElement))).toBe(true)
      }
    }

    // Escape closes it, and the focus is back on the button that opened it
    await page.keyboard.press('Escape')
    await expect(dialog).toBeHidden()
    await expect(button).toBeFocused()
  })

  test('finds the forecast of a station by its name, and the forecast shows it', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/')
    await page.keyboard.press('Control+k')
    const dialog = page.getByRole('dialog', { name: en.shell.search })
    await page.keyboard.type('berlin')
    const station = dialog.getByRole('option', { name: /BERLIN-TEMPELHOF/ })
    await expect(station).toBeVisible()
    // the station is the first of its group, after the tools: walked to by keys, taken by Enter
    for (let step = 0; step < 10 && await station.getAttribute('aria-selected') !== 'true'; step++)
      await page.keyboard.press('ArrowDown')
    await expect(station).toHaveAttribute('aria-selected', 'true')
    await page.keyboard.press('Enter')
    await expect(page).toHaveURL(/\/meteogram\?station=10384/)
    await expect(page.getByText('BERLIN-TEMPELHOF').first()).toBeVisible()
  })
})

test.describe('the skip link', () => {
  test('is the first stop, and takes the focus past the header to the page', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/glossary')
    await page.keyboard.press('Tab')
    const skip = page.getByRole('link', { name: en.shell.skipToContent })
    await expect(skip).toBeFocused()
    await expect(skip).toBeInViewport()
    await page.keyboard.press('Enter')
    await expect(page.locator('main#content')).toBeFocused()
    // the next stop is the page's own first control, not the header's
    await page.keyboard.press('Tab')
    expect(await page.evaluate(() => !!document.activeElement?.closest('main'))).toBe(true)
  })
})

test.describe('the narrow layout', () => {
  test.use({ viewport: { width: 390, height: 844 } })

  test('puts the tools in a tab bar at the foot of the window, the current one marked', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/meteogram')
    const bar = page.getByRole('navigation', { name: en.shell.mainNav })
    await expect(bar).toBeVisible()
    const box = await bar.boundingBox()
    expect(box!.y + box!.height).toBeGreaterThan(844 - 2)
    await expect(bar.getByRole('link', { name: en.nav.meteogram })).toHaveAttribute('aria-current', 'page')
    // the page keeps the bar's height free at its foot, so its last line is not under the bar
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight))
    const last = page.getByRole('link', { name: en.footer.licenses })
    const linkBox = await last.boundingBox()
    expect(linkBox!.y + linkBox!.height).toBeLessThanOrEqual(box!.y)
  })

  test('opens the rest in a sheet that closes on a choice', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/')
    await page.getByRole('button', { name: en.header.menu, exact: true }).click()
    const sheet = page.getByRole('dialog', { name: en.header.menu })
    await expect(sheet).toBeVisible()
    await sheet.getByRole('link', { name: en.nav.providers }).click()
    await expect(page).toHaveURL(/\/providers$/)
    await expect(sheet).toBeHidden()
  })

  test('closes the sheet on the link of the page that is shown', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/glossary')
    await page.getByRole('button', { name: en.header.menu, exact: true }).click()
    const sheet = page.getByRole('dialog', { name: en.header.menu })
    await sheet.getByRole('link', { name: en.nav.glossary }).click()
    await expect(sheet).toBeHidden()
  })

  test('lets a German tab name break onto two lines rather than out of its tab', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/', 'de')
    const tab = page.getByRole('navigation', { name: de.shell.mainNav }).getByRole('link', { name: de.nav.stripes })
    const fits = await tab.evaluate(el => el.scrollWidth <= el.clientWidth + 1)
    expect(fits).toBe(true)
  })
})

test.describe('a tool on a phone', () => {
  test.use({ viewport: { width: 390, height: 844 } })

  // the result column of the workbench is no wider than the page: the forecast's row of day cards scrolls in its own
  // box, and a chart or a table in theirs (WCAG 1.4.10)
  for (const path of ['/meteogram?station=01001&compact=true', '/meteogram?station=01001', '/stripes?kind=temperature&station=00011']) {
    test(`does not scroll sideways: ${path}`, async ({ page, baseURL }) => {
      await open(page, baseURL!, path)
      await page.waitForLoadState('networkidle').catch(() => {})
      await page.waitForTimeout(500)
      expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(0)
    })
  }
})

test.describe('a low window', () => {
  // a desktop window at 400 % zoom, or a phone on its side: the bars stop being fixed (WCAG 1.4.10)
  test.use({ viewport: { width: 320, height: 256 } })

  test('scrolls the header and the tab bar away with the page', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/glossary')
    await page.evaluate(() => window.scrollTo(0, 600))
    const header = await page.getByRole('banner').boundingBox()
    expect(header!.y + header!.height).toBeLessThanOrEqual(0)
    await expect(page.getByRole('navigation', { name: en.shell.mainNav })).not.toBeInViewport()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true)
  })
})

test.describe('the frame', () => {
  test.use({ viewport: { width: 1440, height: 900 } })

  test('puts the title of every page on one line with the logo', async ({ page, baseURL }) => {
    test.setTimeout(120_000)
    const lefts: Record<string, number> = {}
    for (const path of ['/', '/meteogram', '/explorer', '/stripes', '/history', '/providers', '/glossary', '/api', '/settings', '/about', '/support', '/impressum', '/datenschutz']) {
      await open(page, baseURL!, path)
      const logo = await page.getByRole('banner').getByRole('link', { name: 'Wetterdienst' }).locator('img').boundingBox()
      const title = page.getByRole('heading', { level: 1 })
      // the title stands after the page's tile where it has one: the frame is the tile's or the title's left edge
      const tile = page.locator('.page-header .tile').first()
      const left = await tile.count() ? (await tile.boundingBox())!.x : (await title.boundingBox())!.x
      lefts[path] = Math.round(left - logo!.x)
    }
    // the logo's link is padded by 6 px, which its negative margin takes back
    expect(new Set(Object.values(lefts)), JSON.stringify(lefts)).toEqual(new Set([0]))
  })
})

test.describe('print', () => {
  test('leaves out the header, the tab bar and the footer', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/glossary')
    await page.emulateMedia({ media: 'print' })
    await expect(page.getByRole('banner')).toBeHidden()
    await expect(page.getByRole('contentinfo')).toBeHidden()
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  })
})

test.describe('the typefaces', () => {
  test('are the app\'s own files, asked for before the app has run', async ({ page, request, baseURL }) => {
    const html = await (await request.get('/')).text()
    const preload = /<link[^>]+rel="preload"[^>]+href="(\/_typefaces\/[^"]+\.woff2)"/.exec(html)?.[1]
      ?? /<link[^>]+href="(\/_typefaces\/[^"]+\.woff2)"[^>]+rel="preload"/.exec(html)?.[1]
    expect(preload).toBeDefined()
    const font = await request.get(preload!)
    expect(font.status()).toBe(200)

    await open(page, baseURL!, '/')
    // the page's text is set in it once it has come (a check of the face, which the page asks for itself)
    await expect.poll(() => page.evaluate(() => document.fonts.check('16px "Atkinson Hyperlegible Next"')), { timeout: 10_000 }).toBe(true)
  })
})
