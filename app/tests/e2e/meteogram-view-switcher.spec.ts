import type { Page } from '@playwright/test'
import { expect, test } from '@playwright/test'
import { mockBackend } from './accessibility/mock-backend'

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
