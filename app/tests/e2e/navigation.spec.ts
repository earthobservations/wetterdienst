import type { Page } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { expect, test } from '@playwright/test'
import { REFERENCE } from '../../app/utils/sections'
import { mockBackend } from './accessibility/mock-backend'

// The shell of the app (GH-3518): the header with the six tools and the reference, the search, the tab bar and the
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
    for (const key of ['meteogram', 'explorer', 'stripes', 'history', 'map'])
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
    await expect(panel.getByRole('link')).toHaveCount(REFERENCE.length)
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
    // the trigger, then each link of the reference, then the next thing on the page
    for (let stop = 0; stop < REFERENCE.length + 1; stop++)
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
    // the provider, not the first page that names DWD in its description (the Radar does, GH-3788): its name starts with it
    await dialog.getByRole('option', { name: /^DWD\b/ }).first().click()
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

  // the stations (GH-3790): matched by the app's own server on the lists it keeps, which the mock backend stands in for with the real matching
  test('finds stations of the forecast, of DWD and of GHCN daily by name, each in a group with its provider and network, and opens the map on one', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/')
    await page.keyboard.press('Control+k')
    const dialog = page.getByRole('dialog', { name: en.shell.search })
    await expect(dialog.getByRole('combobox', { name: en.shell.search })).toBeFocused()
    await page.keyboard.type('hamburg')
    const forecast = dialog.getByRole('group', { name: en.shell.stationsForecast, exact: true })
    const measured = dialog.getByRole('group', { name: en.shell.stationsMeasured, exact: true })
    const ghcn = dialog.getByRole('group', { name: en.shell.stationsGhcn, exact: true })
    await expect(forecast).toBeVisible()
    await expect(measured).toBeVisible()
    await expect(ghcn).toBeVisible()
    // each result names its provider and network
    await expect(forecast.getByRole('option').first()).toContainText('DWD · MOSMIX forecast · 10147')
    await expect(measured.getByRole('option').first()).toContainText('DWD · measurements · 01975')
    await expect(ghcn.getByRole('option').first()).toContainText('NOAA · GHCN daily · GM000010147')
    // the stations come first, and the first is the active option: Enter opens the map on it
    await expect(dialog.getByRole('option').first()).toHaveAttribute('aria-selected', 'true')
    await expect(dialog.getByRole('option').first()).toContainText('HAMBURG-FUHLSBUETTEL')
    await page.keyboard.press('Enter')
    await expect(page).toHaveURL(/\/map\?station=10147/)
    await expect(page.getByTestId('map-station-name')).toContainText('HAMBURG-FUHLSBUETTEL')
  })

  test('leads a station of GHCN daily to the map on its layer, and the "more" of a network to the map\'s own search', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/')
    await page.keyboard.press('Control+k')
    const dialog = page.getByRole('dialog', { name: en.shell.search })
    await expect(dialog.getByRole('combobox', { name: en.shell.search })).toBeFocused()
    await page.keyboard.type('hamburg')
    const ghcn = dialog.getByRole('group', { name: en.shell.stationsGhcn, exact: true })
    await expect(ghcn).toBeVisible()
    await ghcn.getByRole('option').first().click()
    await expect(page).toHaveURL(/\/map\?layer=ghcn&station=GM000010147/)
    await expect(page.getByTestId('map-station-name')).toContainText('HAMBURG FUHLSBUETTEL')
    await expect(dialog).toBeHidden()
    // three stations of the network and a last option for the rest, which opens the map's own search of the layer on what was typed
    await page.keyboard.press('Control+k')
    await expect(dialog.getByRole('combobox', { name: en.shell.search })).toBeFocused()
    await page.keyboard.type('hamburg')
    await expect(ghcn.getByRole('option')).toHaveCount(4)
    await ghcn.getByRole('option').last().click()
    // the text starts the map's own search, and the address the page then writes is the map's state, which has no text of a search in it
    await expect(page.locator('#map-search')).toHaveValue('hamburg')
    await expect(page).toHaveURL(/\/map\?layer=ghcn/)
    await expect(page.getByTestId('map-list').getByRole('listitem').first()).toContainText('HAMBURG')
  })

  test('offers the search of every network for a WMO number, and lists the stations that carry it after Enter', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/')
    await page.keyboard.press('Control+k')
    const dialog = page.getByRole('dialog', { name: en.shell.search })
    await expect(dialog.getByRole('combobox', { name: en.shell.search })).toBeFocused()
    await page.keyboard.type('10147')
    // the stations of the lists that have the number are first; the option that asks every network follows them
    const option = dialog.getByRole('option', { name: /Search all networks for 10147/ })
    await expect(option).toBeVisible()
    await expect(dialog.getByRole('option').first()).not.toContainText('Search all networks')
    await option.click()
    // the dialog stays open, and the stations of every network that carries the number are a group of their own
    await expect(dialog).toBeVisible()
    const group = dialog.getByRole('group', { name: 'Stations with 10147', exact: true })
    await expect(group.getByRole('option')).toHaveCount(4)
    await expect(group.getByRole('option').first()).toHaveAttribute('aria-selected', 'true')
    await expect(group.getByRole('option').nth(3)).toContainText('AEMET · observation · SN99999 · opens the Explorer')
    // a network the map shows leads to it, any other to the Explorer with the network and the station chosen
    await group.getByRole('option').nth(3).click()
    await expect(page).toHaveURL(/\/explorer\?provider=aemet&network=observation&resolution=hourly&dataset=temperature_air&mode=station&stations=SN99999/)
  })

  test('takes four letters for a word, and offers the search of every network for them only where nothing else answers', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/')
    await page.keyboard.press('Control+k')
    const dialog = page.getByRole('dialog', { name: en.shell.search })
    await expect(dialog.getByRole('combobox', { name: en.shell.search })).toBeFocused()
    await page.keyboard.type('Dark')
    await expect(dialog.getByRole('option', { name: en.settings.themeDark })).toBeVisible()
    await expect(dialog.getByRole('option', { name: /Search all networks/ })).toHaveCount(0)
    await dialog.getByRole('combobox').fill('EDDH')
    await expect(dialog.getByRole('option', { name: /Search all networks for EDDH/ })).toBeVisible()
  })
})

// The words of the app, a position and the questions (GH-3790): the index is built with the app and loaded when the search is opened
test.describe('the search of the words of the app', () => {
  test.use({ viewport: { width: 1280, height: 800 } })

  async function search(page: Page, text: string) {
    await page.keyboard.press('Control+k')
    const dialog = page.getByRole('dialog', { name: en.shell.search })
    await expect(dialog.getByRole('combobox', { name: en.shell.search })).toBeFocused()
    await page.keyboard.type(text)
    return dialog
  }

  test('loads the index of the language when the search opens, not with the page', async ({ page, baseURL }) => {
    // the index is a script of its own: told by what is in it
    const indexes: string[] = []
    page.on('response', async (response) => {
      if (response.request().resourceType() === 'script' && (await response.text().catch(() => '')).includes('"postings"'))
        indexes.push(response.url())
    })
    await open(page, baseURL!, '/')
    await page.waitForLoadState('networkidle')
    expect(indexes).toEqual([])
    await search(page, 'dew point')
    await expect(page.getByRole('option', { name: /Humidity and dew point/ })).toBeVisible()
    // the one of the language of the page, once
    await expect.poll(() => indexes.length).toBe(1)
  })

  test('finds an entry of "How weather is measured" and takes the reader to it, at its anchor', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/')
    const dialog = await search(page, 'dew point')
    const group = dialog.getByRole('group', { name: en.measurement.title, exact: true })
    await expect(group.getByRole('option').first()).toContainText('Humidity and dew point')
    await page.keyboard.press('ArrowDown')
    for (let step = 0; step < 20 && !(await group.getByRole('option').first().getAttribute('aria-selected') === 'true'); step++)
      await page.keyboard.press('ArrowDown')
    await page.keyboard.press('Enter')
    await expect(page).toHaveURL(/\/measurement#humidity$/)
    await expect(page.locator('#humidity-title')).toBeFocused()
  })

  test('finds a word in German, ignoring case', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/', 'de')
    await page.keyboard.press('Control+k')
    await page.keyboard.type('TAUPUNKT')
    await expect(page.getByRole('option', { name: /Luftfeuchte und Taupunkt/ })).toBeVisible()
  })

  test('finds a parameter of the glossary and goes to its entry, which has the focus', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/')
    const dialog = await search(page, 'dew point')
    const group = dialog.getByRole('group', { name: en.glossary.title, exact: true })
    await expect(group.getByRole('option').first()).toContainText('Dew point')
    await group.getByRole('option').first().click()
    await expect(page).toHaveURL(/\/glossary#temperature_dew_point_2m$/)
    await expect(page.locator('[id="temperature_dew_point_2m"]')).toBeFocused()
  })

  test('shows a few results with a last option that opens the page that has them all', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/')
    const dialog = await search(page, 'units')
    const group = dialog.getByRole('group', { name: en.common.settings, exact: true })
    await expect(group.getByRole('option')).toHaveCount(4)
    await group.getByRole('option').last().click()
    await expect(page).toHaveURL(/\/settings$/)
  })

  test('leads a setting to its own control', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/')
    const dialog = await search(page, 'plain-language')
    await dialog.getByRole('option', { name: /Plain-language labels/ }).click()
    await expect(page).toHaveURL(/\/settings#settings-friendly-labels$/)
    await expect(page.locator('#settings-friendly-labels')).toBeFocused()
  })

  test('finds a question of Ask the weather and opens it on the home page', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/settings')
    const dialog = await search(page, 'rain')
    const group = dialog.getByRole('group', { name: en.ask.title, exact: true })
    await group.getByRole('option').first().click()
    await expect(page).toHaveURL(/\/\?ask=rain$/)
    await expect(page.getByTestId('question-rain')).toHaveAttribute('aria-pressed', 'true')
  })

  test('takes coordinates as a place that leads to the map at that point, before everything else', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/')
    const dialog = await search(page, '52°31\'N 13°24\'E')
    const place = dialog.getByRole('group').first()
    await expect(place).toContainText('52.5167, 13.4000')
    await expect(dialog.getByRole('option').first()).toHaveAttribute('aria-selected', 'true')
    await page.keyboard.press('Enter')
    await expect(page).toHaveURL(/\/map\?(?:.*&)?lat=52\.5167&lon=13\.4000/)
    // the map picks the station for the place, as a click would
    await expect(page.getByTestId('map-station-name')).toBeVisible()
  })

  test('says how many results each group has, in the live region', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/')
    const dialog = await search(page, 'dew point')
    await expect(dialog.getByRole('status')).toContainText(new RegExp(`${en.measurement.title}: \\d+`))
    await expect(dialog.getByRole('status')).toContainText(new RegExp(`${en.glossary.title}: \\d+`))
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
    // four tools and the Menu (GH-3650), the Radar in the fourth place (GH-3788); History and the map are in the Menu's sheet
    expect(await bar.locator('li').allInnerTexts()).toEqual([en.nav.meteogram, en.nav.explorer, en.nav.stripes, en.nav.radar, en.header.menu])
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
    for (const path of ['/', '/meteogram', '/explorer', '/stripes', '/history', '/providers', '/glossary', '/measurement', '/methods', '/api', '/settings', '/about', '/support', '/impressum', '/datenschutz']) {
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
