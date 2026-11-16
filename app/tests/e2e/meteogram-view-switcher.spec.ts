import type { Page } from '@playwright/test'
import { expect, test } from '@playwright/test'
import { mockBackend } from './accessibility/mock-backend'
import { alternatingRainValues } from './meteogram-days-fixture'

// The forecast's view switcher (Chart / Compact / Table) keeps its place (GH-4124): it is clicked again and again to compare
// the views, so it must not move under the pointer when the view changes, which it did when the pan/zoom buttons (chart view)
// and the panels and horizon (every view but the compact) came and went around it. The API is answered by the mock backend, so
// the spec needs nothing but the app.

const PAGE = '/meteogram?station=10384&view=chart'
const VIEWS = ['Chart', 'Compact', 'Table'] as const
// a wide desktop, the width of the maintainer's report, and a phone (where the toolbar is stacked)
const WIDTHS = [1280, 900, 390]

const switcher = (page: Page) => page.getByRole('radiogroup', { name: 'View' })
const zoomGroup = (page: Page) => page.getByRole('group', { name: /zoom/i })

/** Where the switcher is on the page (not in the window: a click may scroll it), as the browser lays it out */
async function placeOf(page: Page) {
  const place = await switcher(page).evaluate((element) => {
    const box = element.getBoundingClientRect()
    return { x: box.left + window.scrollX, y: box.top + window.scrollY, width: box.width, height: box.height }
  })
  return place
}

type Place = Awaited<ReturnType<typeof placeOf>>

// Tailwind's `md`, where the toolbar leaves the stacked layout
const MD = 768

/**
 * The same place, to less than a pixel. The chosen option is set in a heavier weight, which makes the switcher a little
 * wider (by 0.5 px in English, up to 1.5 px in Polish and Czech) on the side that is free: from `md` up the switcher is
 * pinned to the right edge of the toolbar, so its right edge is what stays (x + width); below it, where it starts at the
 * left edge, its x. The top (y) and the height are the same at every width.
 */
function expectSamePlace(place: Place, chart: Place, view: string, width: number) {
  const edge = (p: Place) => (width >= MD ? p.x + p.width : p.x)
  const where = `the switcher in the ${view} view: ${JSON.stringify(place)} against the chart view's ${JSON.stringify(chart)}`
  expect(Math.abs(edge(place) - edge(chart)), `${width >= MD ? 'right edge' : 'x'} of ${where}`).toBeLessThan(1)
  expect(Math.abs(place.y - chart.y), `y of ${where}`).toBeLessThan(1)
  expect(Math.abs(place.height - chart.height), `height of ${where}`).toBeLessThan(1)
}

for (const width of WIDTHS) {
  test(`keeps the view switcher where it is when the view changes, at ${width} px`, async ({ page, baseURL }) => {
    const backend = await mockBackend(page, baseURL!)
    await page.setViewportSize({ width, height: 900 })
    await page.goto(PAGE)
    await expect(page.locator('.mg-canvas[data-drawn="true"]')).toBeVisible({ timeout: 60_000 })
    await expect(switcher(page).getByRole('radio', { name: 'Chart' })).toBeChecked()
    // the pan and zoom buttons are what the chart view adds to the toolbar: the thing that pushed the switcher away
    await expect(zoomGroup(page)).toBeVisible()

    const chart = await placeOf(page)
    const seen = new Set<string>(['Chart'])

    // the way a reader uses it: one click after the other, at the same point of the page
    for (const view of ['Compact', 'Table', 'Chart', 'Compact', 'Chart', 'Table'] as const) {
      await switcher(page).getByRole('radio', { name: view }).click()
      await expect(switcher(page).getByRole('radio', { name: view })).toBeChecked()
      // the toolbar of the view is there: the zoom buttons are the chart's alone
      await expect(zoomGroup(page)).toHaveCount(view === 'Chart' ? 1 : 0)
      seen.add(view)
      expectSamePlace(await placeOf(page), chart, view, width)
    }
    expect([...seen].sort()).toEqual([...VIEWS].sort())

    // and it is in the toolbar's first row: the top of the card, at the corner on a wide screen
    const card = await page.evaluate(() => {
      const group = document.querySelector('[role="radiogroup"][aria-label="View"]')!
      const box = group.closest('.grid')!.getBoundingClientRect()
      return { top: box.top + window.scrollY, right: box.right + window.scrollX }
    })
    expect(chart.y - card.top, 'the switcher sits in the first row of the toolbar').toBeLessThan(20)
    if (width >= MD)
      expect(card.right - (chart.x + chart.width), 'the switcher sits at the right edge of the toolbar').toBeLessThan(20)
    expect(backend.unanswered).toEqual([])
  })
}

// The panels and the horizon ("Bereiche", 24h / 3d / 7d / Alles) keep their place as well (GH-4138). They were centred over the
// toolbar's two rows, so that they moved up when the second row, the pan/zoom buttons of the chart view, was not there (the
// table view). They are pinned to the first row, beside the switcher. The compact view has no panels to place.

const panelToggle = (page: Page) => page.locator('[data-panel="temp"]')
const horizonButton = (page: Page) => page.getByRole('button', { name: '24h', exact: true })

/** Where the panels' first toggle and the horizon's first button are, on the page */
async function panelsPlaceOf(page: Page) {
  const at = (locator: ReturnType<Page['locator']>) => locator.evaluate((element) => {
    const box = element.getBoundingClientRect()
    return { x: box.left + window.scrollX, y: box.top + window.scrollY, width: box.width, height: box.height }
  })
  return { panels: await at(panelToggle(page)), horizon: await at(horizonButton(page)) }
}

for (const width of WIDTHS) {
  test(`keeps the panels and the horizon where they are when the view changes, at ${width} px`, async ({ page, baseURL }) => {
    const backend = await mockBackend(page, baseURL!)
    await page.setViewportSize({ width, height: 900 })
    await page.goto(PAGE)
    await expect(page.locator('.mg-canvas[data-drawn="true"]')).toBeVisible({ timeout: 60_000 })
    await expect(zoomGroup(page)).toBeVisible()
    const chart = await panelsPlaceOf(page)

    for (const view of ['Table', 'Chart', 'Compact', 'Table', 'Compact', 'Chart', 'Table'] as const) {
      await switcher(page).getByRole('radio', { name: view }).click()
      await expect(switcher(page).getByRole('radio', { name: view })).toBeChecked()
      // the compact cards have no panels to choose, so there is none to place
      await expect(panelToggle(page)).toHaveCount(view === 'Compact' ? 0 : 1)
      if (view === 'Compact')
        continue
      const place = await panelsPlaceOf(page)
      for (const part of ['panels', 'horizon'] as const) {
        const where = `the ${part} in the ${view} view: ${JSON.stringify(place[part])} against the chart view's ${JSON.stringify(chart[part])}`
        expect(Math.abs(place[part].y - chart[part].y), `y of ${where}`).toBeLessThan(1)
        expect(Math.abs(place[part].x - chart[part].x), `x of ${where}`).toBeLessThan(1)
      }
    }

    // from `md` up they are in the first row, level with the switcher: the middle of the panels' buttons is the switcher's middle
    if (width >= MD) {
      const middle = (box: Place) => box.y + box.height / 2
      expect(Math.abs(middle(chart.panels) - middle(await placeOf(page))), 'the panels are level with the switcher').toBeLessThan(1)
    }
    expect(backend.unanswered).toEqual([])
  })
}

// The compact view's day cards (GH-4138): a dry day has no line for the rain, which made its card shorter and, since the strip
// and the card centred their content, pushed its weekday, icon, date and temperatures down. All the cards are as high as the
// tallest and their rows are level. The forecast has rain on every other day, and ends in the middle of a day (a note under the
// rest of that card).
for (const width of [1280, 390]) {
  test(`has day cards of one height with their rows level, dry days and days with rain alike, at ${width} px`, async ({ page, baseURL }) => {
    const backend = await mockBackend(page, baseURL!, { values: alternatingRainValues() })
    // the icons bounce once (4 px) when the page opens, which would put their tops off by the frame the test reads them in
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await page.setViewportSize({ width, height: 900 })
    await page.goto('/meteogram?station=10384&view=compact')
    const cards = page.getByTestId('compact-days').locator(':scope > div')
    await expect(cards.first()).toBeVisible({ timeout: 60_000 })

    const found = await page.getByTestId('compact-days').evaluate(strip => [...strip.children].map((card) => {
      const top = (selector: string) => {
        const element = card.querySelector(selector)
        return element ? Math.round(element.getBoundingClientRect().top * 10) / 10 : null
      }
      const box = card.getBoundingClientRect()
      const rain = card.querySelector('[data-testid="day-precip"]')
      return {
        height: Math.round(box.height * 10) / 10,
        weekday: top('.uppercase'),
        icon: top('svg, .iconify'),
        temperature: top('.shadow-xs'),
        rain: top('[data-testid="day-precip"]'),
        rainHeight: rain ? Math.round(rain.getBoundingClientRect().height * 10) / 10 : 0,
        // a day with rain says so in millimetres, in the visible line and for a screen reader
        dry: !/\d\s*mm/.test(card.textContent ?? ''),
        hiddenFromReaders: rain?.getAttribute('aria-hidden') === 'true',
        rainText: rain?.textContent!.trim() ?? '',
      }
    }))
    // a mix: days with and without rain
    expect(found.length).toBeGreaterThanOrEqual(6)
    expect(found.filter(card => card.dry).length, JSON.stringify(found)).toBeGreaterThanOrEqual(2)
    expect(found.filter(card => !card.dry).length, JSON.stringify(found)).toBeGreaterThanOrEqual(2)
    // a dry day's line for the rain has no text, and is hidden from a screen reader, which would read out an empty line
    for (const card of found.filter(entry => entry.dry)) {
      expect(card.rainText).toBe('')
      expect(card.hiddenFromReaders, 'an empty line for the rain is hidden from a screen reader').toBe(true)
    }

    // the height first: it is what differs, by the line of the rain
    const [first] = found
    for (const [index, card] of found.entries())
      expect(card.height, `height of card ${index} (${card.dry ? 'dry' : 'rain'}) against card 0: ${JSON.stringify(found)}`).toBeCloseTo(first!.height, 0)
    for (const [index, card] of found.entries()) {
      const where = `card ${index} (${card.dry ? 'dry' : 'rain'}): ${JSON.stringify(card)} against card 0: ${JSON.stringify(first)}`
      expect(card.weekday, `weekday of ${where}`).toBeCloseTo(first!.weekday!, 0)
      expect(card.icon, `icon of ${where}`).toBeCloseTo(first!.icon!, 0)
      expect(card.temperature, `temperature of ${where}`).toBeCloseTo(first!.temperature!, 0)
      expect(card.rain ?? Number.NaN, `rain row of ${where}`).toBeCloseTo(first!.rain!, 0)
      expect(card.rainHeight, `height of the rain row of ${where}`).toBeCloseTo(first!.rainHeight, 0)
    }
    expect(backend.unanswered).toEqual([])
  })
}
