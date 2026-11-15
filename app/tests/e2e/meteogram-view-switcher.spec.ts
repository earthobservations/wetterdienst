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

/**
 * The same place: to less than a pixel, since the chosen option is set in a heavier weight, which makes the whole switcher a
 * fraction of a pixel wider (its right edge stays where it is); a move that a reader could see is many times that.
 */
function expectSamePlace(place: Awaited<ReturnType<typeof placeOf>>, chart: Awaited<ReturnType<typeof placeOf>>, view: string) {
  for (const key of ['x', 'y', 'width', 'height'] as const)
    expect(Math.abs(place[key] - chart[key]), `${key} of the switcher in the ${view} view: ${JSON.stringify(place)} against the chart view's ${JSON.stringify(chart)}`).toBeLessThan(1)
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
      expectSamePlace(await placeOf(page), chart, view)
    }
    expect([...seen].sort()).toEqual([...VIEWS].sort())

    // and it is in the toolbar's first row: the top of the card, at the corner on a wide screen
    const card = await page.evaluate(() => {
      const group = document.querySelector('[role="radiogroup"][aria-label="View"]')!
      const box = group.closest('.grid')!.getBoundingClientRect()
      return { top: box.top + window.scrollY, right: box.right + window.scrollX }
    })
    expect(chart.y - card.top, 'the switcher sits in the first row of the toolbar').toBeLessThan(20)
    if (width >= 768)
      expect(card.right - (chart.x + chart.width), 'the switcher sits at the right edge of the toolbar').toBeLessThan(20)
    expect(backend.unanswered).toEqual([])
  })
}
