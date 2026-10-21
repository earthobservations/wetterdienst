import type { Page } from '@playwright/test'
import { expect, test } from '@playwright/test'
import { mockBackend } from './accessibility/mock-backend'

// The wind barbs of the meteogram are drawn on a canvas laid over the chart (GH-3240): they are there once the
// chart is, not only after the window has been resized. The API is answered by the mock backend (a MOSMIX
// forecast with wind speed and direction), so that the spec needs nothing but the app.

/** How many pixels of the barb canvas have been drawn on, or null while there is no canvas or it has no size */
async function drawnPixels(page: Page): Promise<number | null> {
  return page.evaluate(() => {
    const canvas = document.querySelector<HTMLCanvasElement>('.js-plotly-plot .meteogram-overlay-canvas')
    if (!canvas || canvas.width === 0 || canvas.height === 0)
      return null
    const data = canvas.getContext('2d')!.getImageData(0, 0, canvas.width, canvas.height).data
    let drawn = 0
    for (let i = 3; i < data.length; i += 4) {
      if (data[i]! > 0)
        drawn++
    }
    return drawn
  })
}

for (const [name, path] of [
  ['the forecast page', '/meteogram?station=10384'],
  ['the widget', '/widget?station=10384'],
] as const) {
  test(`${name} has its wind barbs at first paint, without a resize`, async ({ page, baseURL }) => {
    const backend = await mockBackend(page, baseURL!)
    await page.goto(path)
    // the chart is drawn, which is when the barbs are due
    await expect(page.locator('.js-plotly-plot .main-svg').first()).toBeVisible()

    // polled until they are there: a barb canvas that stays empty is the failure
    await expect.poll(() => drawnPixels(page), { message: 'pixels of wind barbs on the overlay canvas' }).toBeGreaterThan(100)
    // every request the page made was one the mock answers, so a missing barb is not a missing answer
    expect(backend.unanswered).toEqual([])
  })
}
