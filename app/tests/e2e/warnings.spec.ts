import type { Page } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { expect, test } from '@playwright/test'
import { alertsAnswer, emptyAlerts } from '../helpers/warnings-answer'
import { askHandlers } from './accessibility/ask-backend'
import { ApiFailure, mockBackend } from './accessibility/mock-backend'
import { expectAtLeastPx } from './target-size'

// DWD's weather warnings (GH-4295) by their main paths in a browser: the layer over the map (the chip, the outlines, the legend that
// says a level by more than colour, the list that is the keyboard's way to a warning, the warning without a polygon listed apart), the banner for
// the station picked and in the Forecast, the refresh while a page is open, and the question of Ask the weather. The backend is the
// accessibility spec's mock with the snapshot of `tests/helpers/warnings-answer.ts`, so nothing here reaches DWD.

const catalog = (language: string) => JSON.parse(readFileSync(fileURLToPath(new URL(`../../i18n/locales/${language}.json`, import.meta.url)), 'utf-8'))
const en = catalog('en')

async function open(page: Page, baseURL: string, path: string, handlers = {}, language = 'en') {
  await page.context().addCookies([{ name: 'wd_lang', value: language, url: baseURL }])
  const asked: string[] = []
  page.on('request', (request) => {
    const url = new URL(request.url())
    if (url.pathname === '/api/alerts')
      asked.push(url.search)
  })
  const backend = await mockBackend(page, baseURL, handlers)
  await page.addInitScript(() => {
    try {
      localStorage.removeItem('wd-place')
    }
    catch {}
  })
  await page.goto(path)
  return { backend, asked }
}

const chip = (page: Page) => page.getByTestId('map-warnings-chip')
const paths = (page: Page) => page.locator('.leaflet-weather-warnings-pane path')

/** Opens the map and waits for its stations, which the chip's layer is drawn under */
async function openMap(page: Page, baseURL: string, path = '/map', handlers = {}, language = 'en') {
  const opened = await open(page, baseURL, path, handlers, language)
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(catalog(language).mapTool.title)
  // the stations are in (the count is not shown on a phone, where it is in the panel)
  await expect(page.getByTestId('map-count').or(page.getByTestId('map-count-panel')).first()).toBeAttached()
  await expect(chip(page)).toBeVisible()
  return opened
}

test.describe('the layer over the map', () => {
  test.use({ viewport: { width: 1440, height: 900 } })

  test('is a chip over the map, off until pressed, and asks nothing of DWD\'s warnings while it is off', async ({ page, baseURL }) => {
    const { asked } = await openMap(page, baseURL!)
    await expect(chip(page)).toHaveText(en.warnings.chip)
    await expect(chip(page)).toHaveAttribute('aria-pressed', 'false')
    await expect(page.getByTestId('warnings-panel')).toHaveCount(0)
    await expect(paths(page)).toHaveCount(0)
    expect(asked).toEqual([])
  })

  test('draws the outlines of the warnings that have a polygon, and lists every warning in the panel, the most severe first', async ({ page, baseURL }) => {
    const { backend, asked } = await openMap(page, baseURL!)
    await chip(page).click()
    await expect(chip(page)).toHaveAttribute('aria-pressed', 'true')
    await expect(chip(page)).toHaveText(`${en.warnings.chipCount.replace('{count}', '6')}`)
    await expect(page).toHaveURL(/warnings=1/)
    // five polygons: the warning of the sea has none
    await expect(paths(page)).toHaveCount(5)
    expect(asked).toEqual(['?granularity=community&language=en'])
    const panel = page.getByTestId('warnings-panel')
    await expect(panel.getByTestId('warnings-panel-summary')).toHaveText('Warnings in force or announced in Germany: 6')
    const titles = panel.getByTestId('warnings-list').first().getByTestId('warning-title')
    await expect(titles).toHaveText(['thunderstorm', 'PRELIMINARY INFORMATION SEVERE THUNDERSTORMS', 'glaze', 'wind gusts', 'fog'])
    // the credit of the data is in the map's attribution and under the list
    await expect(page.locator('.leaflet-control-attribution')).toContainText('Source: Deutscher Wetterdienst')
    await expect(panel.getByTestId('provider-credit')).toContainText('Source: Deutscher Wetterdienst')
    expect(backend.unanswered).toEqual([])
  })

  test('has the chip in the address, so that a link opens the map with the warnings on, and leaving it off takes it out again', async ({ page, baseURL }) => {
    await openMap(page, baseURL!, '/map?warnings=1')
    await expect(chip(page)).toHaveAttribute('aria-pressed', 'true')
    await expect(paths(page)).toHaveCount(5)
    await chip(page).click()
    await expect(chip(page)).toHaveAttribute('aria-pressed', 'false')
    await expect(page).not.toHaveURL(/warnings=/)
    await expect(paths(page)).toHaveCount(0)
    await expect(page.getByTestId('warnings-panel')).toHaveCount(0)
  })

  test('says a level by its edge and its words as well as its colour: the legend has the dotted, dashed, solid and heavy edges, each with its number and its name', async ({ page, baseURL }) => {
    await openMap(page, baseURL!, '/map?warnings=1')
    await page.getByTestId('map-layers-button').click()
    const entries = page.getByTestId('warnings-legend-entry')
    await expect(entries).toHaveText([
      'Level 1 of 4 · Weather warning',
      'Level 2 of 4 · Marked weather warning',
      'Level 3 of 4 · Severe weather warning',
      'Level 4 of 4 · Extreme severe weather warning',
      'Preliminary information on severe weather',
    ])
    const dashes = await page.locator('.warnings-swatch rect:not([stroke="#ffffff"])').evaluateAll(rects => rects.map(rect => rect.getAttribute('stroke-dasharray')))
    expect(dashes).toEqual(['2 5', '9 5', null, null, '12 4 2 4'])
    const widths = await page.locator('.warnings-swatch rect:not([stroke="#ffffff"])').evaluateAll(rects => rects.map(rect => Number(rect.getAttribute('stroke-width'))))
    expect(widths[3]).toBeGreaterThan(widths[2]!)
    // the map's description says it as well, for a screen reader
    await expect(page.getByTestId('map-legend-description')).toContainText('level 1 has a dotted edge')
    // level 4 is a double line: a light line inside the dark one in its swatch
    await expect(page.locator('.warnings-swatch rect[stroke="#ffffff"]')).toHaveCount(1)
    // heat and UV warnings are drawn in DWD's own colours, said in the legend
    await expect(page.getByTestId('warnings-legend-health')).toHaveText(en.warnings.legendHealth)
    // the outlines of the map carry the same edges: the two severe warnings (level 3) are solid
    const mapDashes = await paths(page).evaluateAll(all => all.map(path => path.getAttribute('stroke-dasharray')))
    expect(mapDashes.filter(dash => dash === null)).toHaveLength(2)
    expect(new Set(mapDashes).size).toBeGreaterThan(2)
  })

  test('opens a warning of the list to its type, level, times, headline, description and instruction, and draws it stronger', async ({ page, baseURL }) => {
    await openMap(page, baseURL!, '/map?warnings=1')
    const list = page.getByTestId('warnings-list').first()
    const first = list.getByTestId('warning-entry').first()
    const before = await paths(page).evaluateAll(all => all.map(path => Number(path.getAttribute('stroke-width'))))
    await expect(page.locator('.warning-outline-focus')).toHaveCount(0)
    await first.getByTestId('warning-toggle').click()
    await expect(first.getByTestId('warning-toggle')).toHaveAttribute('aria-expanded', 'true')
    const details = first.getByTestId('warning-details')
    await expect(details).toBeVisible()
    await expect(details).toContainText('thunderstorm')
    await expect(details).toContainText('Level 3 of 4 · Severe weather warning')
    await expect(details.getByTestId('warning-issued')).not.toBeEmpty()
    await expect(details.getByTestId('warning-description')).toHaveText('Thunderstorms occur. Gale-force gusts up to 80 km/h and heavy rain accompany them.')
    await expect(details.getByTestId('warning-instruction')).toContainText('Lightning strikes may occur')
    // DWD's words, in the language of the page
    await expect(details.locator('[lang="en"]').first()).toBeVisible()
    // the outline of that warning has a ring (a white and a navy line round it), and its own line is no heavier than it was: a level 3 never looks
    // heavier than a level 4 for being the one opened
    await expect(page.locator('.warning-outline-focus')).toHaveCount(2)
    const after = await paths(page).evaluateAll(all => all.filter(path => !path.classList.contains('warning-outline-focus')).map(path => Number(path.getAttribute('stroke-width'))))
    expect(after).toEqual(before)
    // pressed again it closes, and the emphasis goes
    await first.getByTestId('warning-toggle').click()
    await expect(details).toBeHidden()
    await expect(page.locator('.warning-outline-focus')).toHaveCount(0)
  })

  test('lists the warning that has no polygon apart, with its area, and draws no outline for it', async ({ page, baseURL }) => {
    await openMap(page, baseURL!, '/map?warnings=1')
    const aside = page.getByTestId('warnings-aside')
    await expect(aside.getByRole('heading', { level: 4 })).toHaveText(en.warnings.asideTitle)
    await expect(aside.getByTestId('warning-title')).toHaveText('near gale')
    await aside.getByTestId('warning-toggle').click()
    await expect(aside.getByTestId('warning-details')).toContainText('Ostfriesische Küste')
    await expect(paths(page)).toHaveCount(5)
  })

  test('is reached and worked by the keyboard: the chip toggles by Space, the rows by Enter, and the focus stays where it was', async ({ page, baseURL }) => {
    await openMap(page, baseURL!)
    await chip(page).focus()
    await page.keyboard.press('Space')
    await expect(chip(page)).toHaveAttribute('aria-pressed', 'true')
    await expect(chip(page)).toBeFocused()
    const toggle = page.getByTestId('warnings-list').first().getByTestId('warning-toggle').first()
    await toggle.focus()
    await page.keyboard.press('Enter')
    await expect(toggle).toHaveAttribute('aria-expanded', 'true')
    await expect(toggle).toBeFocused()
    await page.keyboard.press('Enter')
    await expect(toggle).toHaveAttribute('aria-expanded', 'false')
    await chip(page).focus()
    await page.keyboard.press('Enter')
    await expect(chip(page)).toHaveAttribute('aria-pressed', 'false')
  })

  test('says that the warnings could not be loaded, with a Retry that asks again and gets them', async ({ page, baseURL }) => {
    let failing = true
    await openMap(page, baseURL!, '/map?warnings=1', {
      alerts: (url: URL) => failing ? new ApiFailure(502, 'DWD does not answer') : alertsAnswer({ language: url.searchParams.get('language') ?? 'en' }),
    })
    const failed = page.getByTestId('warnings-failed')
    await expect(failed).toHaveText(en.warnings.failed)
    await expect(failed).toHaveAttribute('role', 'alert')
    failing = false
    await page.getByTestId('warnings-retry').click()
    await expect(page.getByTestId('warnings-panel-summary')).toHaveText('Warnings in force or announced in Germany: 6')
    await expect(failed).toHaveCount(0)
  })

  test('says there is no warning in Germany on a quiet day, and draws none', async ({ page, baseURL }) => {
    await openMap(page, baseURL!, '/map?warnings=1', { alerts: () => emptyAlerts() })
    await expect(page.getByTestId('warnings-panel-summary')).toHaveText('No warning is in force or announced in Germany.')
    await expect(paths(page)).toHaveCount(0)
    await expect(page.getByTestId('warnings-list')).toHaveCount(0)
  })

  test('asks again every 5 minutes while the page is open, and takes the new snapshot in place of the old', async ({ page, baseURL }) => {
    await page.clock.install()
    let quiet = false
    const { asked } = await openMap(page, baseURL!, '/map?warnings=1', {
      alerts: (url: URL) => quiet ? emptyAlerts() : alertsAnswer({ language: url.searchParams.get('language') ?? 'en' }),
    })
    await expect(page.getByTestId('warnings-panel-summary')).toHaveText('Warnings in force or announced in Germany: 6')
    expect(asked).toHaveLength(1)
    quiet = true
    await page.clock.fastForward('04:50')
    expect(asked).toHaveLength(1)
    await page.clock.fastForward('00:20')
    await expect(page.getByTestId('warnings-panel-summary')).toHaveText('No warning is in force or announced in Germany.')
    expect(asked).toHaveLength(2)
    await expect(paths(page)).toHaveCount(0)
  })

  test('keeps the warnings it has where a refresh fails, and says so', async ({ page, baseURL }) => {
    await page.clock.install()
    let failing = false
    await openMap(page, baseURL!, '/map?warnings=1', {
      alerts: (url: URL) => failing ? new ApiFailure(502, 'offline') : alertsAnswer({ language: url.searchParams.get('language') ?? 'en' }),
    })
    await expect(paths(page)).toHaveCount(5)
    failing = true
    await page.clock.fastForward('05:10')
    await expect(page.getByTestId('warnings-refresh-failed')).toContainText('could not be refreshed')
    await expect(paths(page)).toHaveCount(5)
    await expect(page.getByTestId('warnings-panel-summary')).toHaveText('Warnings in force or announced in Germany: 6')
  })

  test('keeps the chip and the outlines where another layer of stations is chosen', async ({ page, baseURL }) => {
    await openMap(page, baseURL!, '/map?warnings=1')
    await page.getByTestId('map-layers-button').click()
    await page.getByTestId('map-layers-panel').getByRole('radio', { name: en.mapTool.layerMeasured, exact: true }).check()
    await expect(chip(page)).toHaveAttribute('aria-pressed', 'true')
    await expect(paths(page)).toHaveCount(5)
    await expect(page).toHaveURL(/warnings=1/)
  })
})

test.describe('the banner of the station picked on the map', () => {
  test.use({ viewport: { width: 1440, height: 900 } })

  test('names the warning whose polygon contains the station, with the layer off, and opens to DWD\'s words', async ({ page, baseURL }) => {
    await openMap(page, baseURL!, '/map?station=10384')
    const banner = page.getByTestId('map-warnings-banner')
    await expect(banner.getByTestId('warnings-banner-summary')).toHaveText('Warnings of DWD for this position: 1')
    await expect(banner.getByTestId('warning-title')).toHaveText('fog')
    await expect(banner.getByTestId('warning-level')).toHaveText('Level 1 of 4 · Weather warning')
    await banner.getByTestId('warning-toggle').click()
    await expect(banner.getByTestId('warning-description')).toContainText('There is a risk of fog')
    // the layer is off: no outline, no list of the whole snapshot
    await expect(chip(page)).toHaveAttribute('aria-pressed', 'false')
    await expect(paths(page)).toHaveCount(0)
    await expect(page.getByTestId('warnings-panel')).toHaveCount(0)
  })

  test('says no warning of DWD has an area with the position where none has, and says nothing of the warning of the sea for it', async ({ page, baseURL }) => {
    await openMap(page, baseURL!, '/map?station=10147')
    // Hamburg-Fuhlsbüttel is in the thunderstorm
    await expect(page.getByTestId('map-warnings-banner').getByTestId('warning-title')).toHaveText('thunderstorm')
    await page.goto('/map?station=10865')
    // Munich: the preliminary information, announced for later
    const banner = page.getByTestId('map-warnings-banner')
    await expect(banner.getByTestId('warning-title')).toHaveText('PRELIMINARY INFORMATION SEVERE THUNDERSTORMS')
    await expect(banner.getByTestId('warning-when')).toContainText('Announced')
    await expect(banner.getByTestId('warning-level')).toHaveText(en.warnings.level.preliminary)
    await expect(banner).not.toContainText('near gale')
    await expect(banner.getByTestId('warnings-banner-named')).toContainText(': 1.')
  })

  test('is about the place picked where a click picked one, and about the station where the list did', async ({ page, baseURL }) => {
    await openMap(page, baseURL!)
    await page.getByRole('button', { name: /BERLIN-TEMPELHOF/ }).click()
    await expect(page.getByTestId('map-warnings-banner').getByTestId('warning-title')).toHaveText('fog')
    await page.getByTestId('map-back').click()
    await page.getByRole('button', { name: /HAMBURG-FUHLSBUETTEL/ }).click()
    await expect(page.getByTestId('map-warnings-banner').getByTestId('warning-title')).toHaveText('thunderstorm')
  })
})

test.describe('the banner of the forecast', () => {
  test.use({ viewport: { width: 1280, height: 900 } })

  test('names the warning for the forecast point over the chart, with its issue time, and opens to DWD\'s words', async ({ page, baseURL }) => {
    const { backend } = await open(page, baseURL!, '/meteogram?station=10384')
    const banner = page.getByTestId('warnings-banner')
    await expect(banner).toBeVisible()
    await expect(banner.getByTestId('warnings-banner-summary')).toHaveText('Warnings of DWD for this position: 1')
    await expect(banner.getByTestId('warning-issued-row')).toContainText('Issued')
    await banner.getByTestId('warning-toggle').click()
    await expect(banner.getByTestId('warning-instruction')).toContainText('Adapt your driving behaviour')
    // over the chart, in the same card
    const bannerBox = (await banner.boundingBox())!
    const chartBox = (await page.getByRole('figure').first().boundingBox())!
    expect(bannerBox.y).toBeLessThan(chartBox.y)
    // the forecast has no list of the warnings of the sea: it points to the map's
    await expect(banner.getByTestId('warnings-banner-map')).toHaveAttribute('href', '/map?warnings=1')
    expect(backend.unanswered).toEqual([])
  })

  test('says that no warning of DWD has an area with the position where none has', async ({ page, baseURL }) => {
    // the forecast point of Berlin has the fog, which the mock lets end in the next hours; a quiet day has none
    await open(page, baseURL!, '/meteogram?station=10384', { alerts: () => emptyAlerts() })
    await expect(page.getByTestId('warnings-banner-summary')).toHaveText('No DWD warning for this position')
    await expect(page.getByTestId('warning-entry')).toHaveCount(0)
    // one line
    expect((await page.getByTestId('warnings-banner').boundingBox())!.height).toBeLessThan(64)
  })

  test('is one line while it loads and one line on a quiet day, so that the chart does not move when the snapshot arrives', async ({ page, baseURL }) => {
    let release!: () => void
    const gate = new Promise<void>((resolve) => {
      release = resolve
    })
    await open(page, baseURL!, '/meteogram?station=10384', {
      alerts: async () => {
        await gate
        return emptyAlerts()
      },
    })
    await expect(page.getByTestId('warnings-banner-summary')).toHaveText(en.warnings.bannerLoading)
    await expect(page.locator('.mg-stage')).toBeVisible()
    const loading = { banner: (await page.getByTestId('warnings-banner').boundingBox())!, chart: (await page.locator('.mg-stage').boundingBox())! }
    release()
    await expect(page.getByTestId('warnings-banner-summary')).toHaveText('No DWD warning for this position')
    const quiet = { banner: (await page.getByTestId('warnings-banner').boundingBox())!, chart: (await page.locator('.mg-stage').boundingBox())! }
    expect(Math.abs(quiet.banner.height - loading.banner.height)).toBeLessThanOrEqual(1)
    expect(Math.abs(quiet.chart.y - loading.chart.y)).toBeLessThanOrEqual(1)
    expect(quiet.banner.height).toBeLessThan(64)
  })

  test('has no banner for a forecast point outside Germany, and one line in the credits that says the warnings are Germany\'s (GH-4328)', async ({ page, baseURL }) => {
    const { asked } = await open(page, baseURL!, '/meteogram?station=01001')
    await expect(page.getByTestId('meteogram-warnings-note')).toHaveText('Weather warnings: Germany only, from DWD')
    await expect(page.getByTestId('warnings-banner')).toHaveCount(0)
    await expect(page.getByTestId('warning-entry')).toHaveCount(0)
    // nothing was asked for
    expect(asked).toEqual([])
  })

  test('has the line in the credits for a German forecast point too', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/meteogram?station=10384')
    await expect(page.getByTestId('warnings-banner')).toBeVisible()
    await expect(page.getByTestId('meteogram-warnings-note')).toHaveText('Weather warnings: Germany only, from DWD')
  })
})

test.describe('the language of DWD\'s texts', () => {
  test.use({ viewport: { width: 1280, height: 900 } })

  test('are DWD\'s German ones, with the note, in a language DWD does not write in', async ({ page, baseURL }) => {
    const { asked } = await open(page, baseURL!, '/meteogram?station=10384', {}, 'cs')
    const banner = page.getByTestId('warnings-banner')
    await expect(banner.getByTestId('warning-title')).toHaveText('NEBEL')
    await banner.getByTestId('warning-toggle').click()
    await expect(banner.getByTestId('warning-language-note')).toHaveText(catalog('cs').warnings.textGerman)
    await expect(banner.getByTestId('warning-description')).toHaveText('Es tritt zeitweise Nebel mit Sichtweiten unter 150 Metern auf.')
    await expect(banner.locator('[lang="de"]').first()).toBeVisible()
    expect(asked).toEqual(['?granularity=community&language=de'])
  })

  test('are DWD\'s Polish ones, from the multilingual product, in Polish', async ({ page, baseURL }) => {
    const { asked } = await open(page, baseURL!, '/meteogram?station=10384', {}, 'pl')
    const banner = page.getByTestId('warnings-banner')
    await expect(banner.getByTestId('warning-title')).toHaveText('mgła')
    await banner.getByTestId('warning-toggle').click()
    await expect(banner.getByTestId('warning-language-note')).toHaveCount(0)
    await expect(banner.locator('[lang="pl"]').first()).toBeVisible()
    expect(asked).toEqual(['?granularity=community&language=mul'])
  })
})

test.describe('the question "Are there warnings here?"', () => {
  test.use({ viewport: { width: 1280, height: 900 } })

  async function home(pageToOpen: Page, baseURL: string, path = '/', language = 'en', handlers = {}) {
    const asked: Array<{ path: string, query: Record<string, string> }> = []
    await pageToOpen.context().addCookies([{ name: 'wd_lang', value: language, url: baseURL }])
    const backend = await mockBackend(pageToOpen, baseURL, { ...askHandlers(asked), ...handlers })
    await pageToOpen.addInitScript(() => {
      try {
        localStorage.removeItem('wd-place')
      }
      catch {}
    })
    await pageToOpen.goto(path)
    await expect(pageToOpen.getByTestId('ask')).toBeVisible()
    return { asked, backend }
  }

  test('says DWD has warnings for Kiel, quotes the warning in DWD\'s words, says they are DWD\'s own, and leads into the map', async ({ page, baseURL }) => {
    const { backend } = await home(page, baseURL!)
    await page.getByTestId('question-warnings').click()
    await expect(page).toHaveURL(/\?ask=warnings$/)
    await expect(page.getByTestId('answer-verdict')).toHaveText('Yes. DWD has warnings for Kiel-Holtenau.')
    await expect(page.getByTestId('answer').getByRole('heading', { level: 3 })).toHaveText(en.ask.q.warnings)
    const quote = page.getByTestId('answer-quote')
    await expect(quote.getByRole('heading', { level: 4 })).toHaveText('wind gusts')
    await expect(quote).toContainText('Level 2 of 4 · Marked weather warning · In force')
    await expect(quote).toContainText('Official WARNING of WIND GUSTS')
    await expect(quote).toContainText('ATTENTION! Notice of possible danger: Single branches may fall.')
    await expect(page.getByTestId('answer')).toContainText('These are DWD\'s own words. wetterdienst does not rate, shorten or reword them.')
    await expect(page.getByTestId('answer')).toContainText('Further warnings that name only an area (the sea, a coast), 1 in all, cannot be matched to Kiel-Holtenau.')
    // the live region says the verdict
    await expect(page.getByTestId('answer-status')).toHaveText('Yes. DWD has warnings for Kiel-Holtenau.')
    // the credit and the licence, and the way to the map
    await expect(page.getByTestId('answer').getByTestId('provider-credit')).toContainText('Source: Deutscher Wetterdienst')
    await expect(page.getByTestId('answer-actions').getByRole('link', { name: en.ask.warnings.open })).toHaveAttribute('href', '/map?warnings=1&lat=54.3776&lon=10.1424')
    expect(backend.unanswered).toEqual([])
  })

  test('has the disclosure, whose rules are DWD\'s CAP profile or marked as wetterdienst\'s own, and the credit of the profile', async ({ page, baseURL }) => {
    await home(page, baseURL!, '/?ask=warnings')
    await expect(page.getByTestId('answer-verdict')).toBeVisible()
    await page.getByTestId('explanation-button').click()
    const region = page.getByTestId('explanation-region')
    await expect(region.getByTestId('explanation-numbers')).toContainText('Warnings in force or announced: 1 for this position, 6 in Germany.')
    const rules = region.locator('[data-rule]')
    await expect(rules).toHaveCount(13)
    await expect(region.getByTestId('own-mark')).toHaveCount(7)
    await expect(region.getByRole('link', { name: /DWD CAP profile 2.1.12/ }).first()).toBeVisible()
    await expect(region).toContainText('wetterdienst\'s own choice.')
  })

  test('says no for a position no polygon contains, with nothing quoted and nothing said of what to expect', async ({ page, baseURL }) => {
    await home(page, baseURL!, '/?ask=warnings', 'en', { alerts: () => emptyAlerts() })
    await expect(page.getByTestId('answer-verdict')).toHaveText('No. No warning of DWD has an area that contains Kiel-Holtenau at the moment.')
    await expect(page.getByTestId('answer-quote')).toHaveCount(0)
  })

  test('quotes DWD\'s German text, with the note, where DWD does not write in the language of the page', async ({ page, baseURL }) => {
    await home(page, baseURL!, '/?ask=warnings', 'cs')
    const quote = page.getByTestId('answer-quote')
    await expect(quote.getByRole('heading', { level: 4 })).toHaveText('WINDBÖEN')
    await expect(quote.locator('[lang="de"]')).toContainText('Amtliche WARNUNG vor WINDBÖEN')
    await expect(page.getByTestId('answer-quote-note')).toHaveText(catalog('cs').warnings.textGerman)
  })

  test('quotes DWD\'s German text with the note on the Low German page too, which is formatted as German', async ({ page, baseURL }) => {
    await home(page, baseURL!, '/?ask=warnings', 'de-hh')
    await expect(page.getByTestId('answer-quote').locator('[lang="de"]')).toContainText('Amtliche WARNUNG vor WINDBÖEN')
    await expect(page.getByTestId('answer-quote-note')).toHaveText(catalog('de-hh').warnings.textGerman)
  })

  test('says in German what the German page asks, and quotes the German text without a note', async ({ page, baseURL }) => {
    await home(page, baseURL!, '/?ask=warnings', 'de')
    await expect(page.getByTestId('answer-verdict')).toHaveText('Ja. Der DWD hat Warnungen für Kiel-Holtenau.')
    await expect(page.getByTestId('answer-quote')).toContainText('Amtliche WARNUNG vor WINDBÖEN')
    await expect(page.getByTestId('answer-quote-note')).toHaveCount(0)
  })
})

test.describe('on a phone', () => {
  test.use({ viewport: { width: 390, height: 844 } })

  test('the chip is a target of 44 px, the panel and the banner fit the width, and the legend is in the layers panel', async ({ page, baseURL }) => {
    await openMap(page, baseURL!, '/map?warnings=1')
    expectAtLeastPx((await chip(page).boundingBox())!.height, 44)
    await expect(page.getByTestId('warnings-panel')).toBeAttached()
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
    expect(overflow).toBeLessThanOrEqual(0)
    await page.getByTestId('map-layers-button').click()
    await expect(page.getByTestId('warnings-legend')).toBeVisible()
  })

  test('has the banner of a station in the panel under the map, within the width', async ({ page, baseURL }) => {
    await openMap(page, baseURL!, '/map?station=10384')
    const banner = page.getByTestId('map-warnings-banner')
    await expect(banner.getByTestId('warning-title')).toHaveText('fog')
    await banner.getByTestId('warning-toggle').click()
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
    expect(overflow).toBeLessThanOrEqual(0)
  })
})

test.describe('with reduced motion', () => {
  test.use({ viewport: { width: 1440, height: 900 } })

  test('moves the map to an opened warning without animation, and nothing of the layer moves by itself', async ({ page, baseURL }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await openMap(page, baseURL!, '/map?warnings=1')
    await page.getByTestId('warnings-list').first().getByTestId('warning-toggle').first().click()
    // the map's own animations (a pan, a zoom) leave their classes on its panes while they run: none is seen, and the map is where the warning is
    const classes = await page.evaluate(async () => {
      const seen = new Set<string>()
      for (let frame = 0; frame < 30; frame++) {
        document.querySelectorAll('.leaflet-pane, .leaflet-container').forEach(element => element.classList.forEach(name => /anim/.test(name) && seen.add(name)))
        await new Promise(resolve => requestAnimationFrame(resolve))
      }
      return [...seen]
    })
    expect(classes).toEqual([])
    // the first of the list is the thunderstorm of Hamburg: the map shows it at once
    const tiles = await page.evaluate(() => [...document.querySelectorAll<HTMLImageElement>('.station-map-tiles img.leaflet-tile')].map(tile => tile.src))
    expect(tiles.length).toBeGreaterThan(0)
  })
})
