import { expect, test } from '@playwright/test'
import { mockBackend } from './accessibility/mock-backend'

// The "About" panel of a tool (GH-3872). On a wide window it opens right-aligned under its button, at the measure
// of text, so that the two read as one control; it used to open at the left edge of the page, with the button at the
// right end of the row, about 750 px away at 2,450 px. At a phone's width the header stacks and the panel is the full
// width under the title.

const PAGES = ['/explorer', '/meteogram', '/stripes', '/history', '/map']
const WIDE = [1280, 1920, 2450]
// the measure of text (--measure, 46 rem) and the rounding of a layout
const MEASURE_PX = 46 * 16
const TOLERANCE = 3

async function openAbout(page: import('@playwright/test').Page, baseURL: string, path: string) {
  await mockBackend(page, baseURL)
  await page.goto(path)
  const button = page.locator('.page-header button[aria-expanded]').first()
  await expect(button).toBeVisible({ timeout: 20_000 })
  await expect(button).toHaveAttribute('aria-expanded', 'false')
  await button.click()
  const panel = page.locator('.page-about')
  await expect(panel).toBeVisible()
  const boxes = async () => {
    const [b, p, h, title] = await Promise.all([
      button.boundingBox(),
      panel.boundingBox(),
      page.locator('.page-header').boundingBox(),
      page.locator('.page-title').boundingBox(),
    ])
    return { button: b!, panel: p!, header: h!, title: title! }
  }
  return { button, panel, boxes }
}

for (const path of PAGES) {
  for (const width of WIDE) {
    test(`${path} at ${width}px: the About panel's right edge is the button's, at the measure`, async ({ page, baseURL }) => {
      await page.setViewportSize({ width, height: 900 })
      const { button, panel, boxes } = await openAbout(page, baseURL!, path)
      const { button: b, panel: p, header, title } = await boxes()
      expect(Math.abs((p.x + p.width) - (b.x + b.width)), 'right edges').toBeLessThanOrEqual(TOLERANCE)
      // not at the page's left edge, where the title stands
      expect(p.x, 'left edge').toBeGreaterThan(title.x + 100)
      expect(p.width).toBeLessThanOrEqual(MEASURE_PX + TOLERANCE)
      // inside the header's row, below the button
      expect(p.x + p.width).toBeLessThanOrEqual(header.x + header.width + TOLERANCE)
      expect(p.y).toBeGreaterThanOrEqual(b.y + b.height)
      // the button still names its panel
      await expect(button).toHaveAttribute('aria-expanded', 'true')
      const id = await panel.getAttribute('id')
      expect(id).toBeTruthy()
      await expect(button).toHaveAttribute('aria-controls', id!)
    })
  }

  test(`${path} at 390px: the About panel is the full width under the title`, async ({ page, baseURL }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    const { button, panel, boxes } = await openAbout(page, baseURL!, path)
    const { panel: p, header, title } = await boxes()
    expect(Math.abs(p.x - header.x), 'left edge').toBeLessThanOrEqual(TOLERANCE)
    expect(Math.abs(p.width - header.width), 'width').toBeLessThanOrEqual(TOLERANCE)
    expect(p.y).toBeGreaterThan(title.y + title.height)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1)).toBe(true)
    await expect(button).toHaveAttribute('aria-controls', (await panel.getAttribute('id'))!)
  })
}
