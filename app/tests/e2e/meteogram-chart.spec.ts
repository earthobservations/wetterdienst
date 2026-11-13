import type { Page } from '@playwright/test'
import { expect, test } from '@playwright/test'
import { mockBackend } from './accessibility/mock-backend'

// The forecast chart (GH-4059): Apache ECharts, drawn as SVG at a fixed height for each panel and a fixed width for each
// hour, with its axes in view while it scrolls sideways, a linked zoom, a readout that meets WCAG 1.4.13 and keys for all
// of it. The API is answered by the mock backend (three days of hourly MOSMIX values), so the spec needs nothing but the app.

const PAGE = '/meteogram?station=10384'
// the chart in a window a phone has, where the compact day cards are what opens
const PAGE_CHART = '/meteogram?station=10384&view=chart'
const WIDGET = '/widget?station=10384'

const svg = (page: Page) => page.locator('.mg-canvas svg').first()
const figure = (page: Page) => page.getByRole('figure').first()
const scroller = (page: Page) => page.getByTestId('meteogram-scroller')
const readout = (page: Page) => page.getByTestId('meteogram-readout')
const announced = (page: Page) => page.getByTestId('meteogram-announce')

async function open(page: Page, baseURL: string, path = PAGE, size?: { width: number, height: number }) {
  if (size)
    await page.setViewportSize(size)
  const backend = await mockBackend(page, baseURL)
  await page.goto(path)
  await expect(svg(page)).toBeVisible()
  // drawn: the day names are in it
  await expect(svg(page).locator('text').first()).toBeVisible()
  return backend
}

/** The texts of the chart that are a time of day, as the hours of its axis */
const hourLabels = (page: Page) => svg(page).locator('text').filter({ hasText: /^\d{2}[:.]\d{2}$/ })

/** The distance in px between two hour labels of the axis next to each other: the width of the hours between them */
async function labelSpacing(page: Page) {
  const boxes = await hourLabels(page).evaluateAll(texts => texts.map((text) => {
    const box = text.getBoundingClientRect()
    return { x: box.left + box.width / 2, label: text.textContent! }
  }))
  expect(boxes.length).toBeGreaterThan(1)
  return boxes[1]!.x - boxes[0]!.x
}

for (const [name, path] of [['the forecast page', PAGE], ['the widget', WIDGET]] as const) {
  test(`${name} draws its panels, its wind barbs and its weather symbols at first paint`, async ({ page, baseURL }) => {
    const backend = await open(page, baseURL!, path)
    // the weather symbols of Yr, drawn into the header, and the strokes of the lines and barbs
    await expect(svg(page).locator('image').first()).toBeAttached()
    expect(await svg(page).locator('image').count()).toBeGreaterThan(5)
    expect(await svg(page).locator('path').count()).toBeGreaterThan(100)
    expect(await svg(page).locator('text').allTextContents()).toEqual(expect.arrayContaining([expect.stringMatching(/^[A-Z][a-z]{2} \d{2}\/\d{2}$/)]))
    // every request the page made was one the mock answers, so a missing barb is not a missing answer
    expect(backend.unanswered).toEqual([])
  })

  test(`${name} does not load Plotly`, async ({ page, baseURL }) => {
    const requested: string[] = []
    page.on('request', request => requested.push(request.url()))
    await open(page, baseURL!, path)
    await page.waitForLoadState('networkidle')
    // the library and its locales: `utils/plotly-locale.ts` is the app's own small module, which asks for them only when a Plotly chart is drawn
    expect(requested.filter(url => /plotly\.js/i.test(url))).toEqual([])
    expect(await page.locator('.js-plotly-plot').count()).toBe(0)
    expect(await page.evaluate(() => 'Plotly' in window)).toBe(false)
  })
}

test.describe('the shape of the chart', () => {
  // fixed heights for the panels and a fixed width for each hour: what the screen is and how it is held do not change them
  const SIZES = [
    { width: 320, height: 640 },
    { width: 390, height: 844 },
    { width: 844, height: 390 },
    { width: 1280, height: 900 },
  ]

  test('has the height of its panels on every screen, and the hours at the same width where it does not fit', async ({ page, baseURL }) => {
    const seen: { height: number, strip: number }[] = []
    await mockBackend(page, baseURL!)
    for (const size of SIZES) {
      await page.setViewportSize(size)
      await page.goto(PAGE_CHART)
      await expect(svg(page)).toBeVisible()
      await expect(hourLabels(page).first()).toBeVisible()
      seen.push(await page.evaluate(() => ({
        height: Number(document.querySelector('.mg-canvas svg')!.getAttribute('height')),
        // 72 hours at their width, and the room of the axis' labels at the left and the right
        strip: (document.querySelector('.mg-track') as HTMLElement).offsetWidth,
      })))
    }
    expect(new Set(seen.map(entry => entry.height)).size, JSON.stringify(seen)).toBe(1)
    // the same strip on a phone, in landscape and on a desktop's card: the 71 hours between the first and the last stamp at 10 px,
    // and the gutters of the axes (68 px at the left, 84 where a title is broken in two, and 10 at the right)
    expect(new Set(seen.map(entry => entry.strip)).size, JSON.stringify(seen)).toBe(1)
    expect(seen[0]!.strip).toBeGreaterThanOrEqual(71 * 10 + 78)
    expect(seen[0]!.strip).toBeLessThanOrEqual(71 * 10 + 94)
  })

  test('scrolls sideways on a phone, with the axes in view and the later hours a scroll away', async ({ page, baseURL }) => {
    await open(page, baseURL!, PAGE_CHART, { width: 390, height: 844 })
    const strip = scroller(page)
    expect(await strip.evaluate(element => element.scrollWidth > element.clientWidth)).toBe(true)
    // the first label of the first panel's axis, which has to stay where it is
    const axisLabel = svg(page).locator('text').filter({ hasText: /^\d+$/ }).first()
    const before = (await axisLabel.boundingBox())!
    const firstHours = await hourLabels(page).allTextContents()
    const stage = page.locator('.mg-stage')
    const stageBefore = (await stage.boundingBox())!

    await strip.evaluate((element) => {
      element.scrollLeft = 300
    })
    // the window moved: other hours are labelled, and the day names changed with them
    await expect.poll(async () => (await hourLabels(page).allTextContents()).join()).not.toBe(firstHours.join())
    const after = (await axisLabel.boundingBox())!
    expect(Math.round(after.x)).toBe(Math.round(before.x))
    expect(Math.round((await stage.boundingBox())!.x)).toBe(Math.round(stageBefore.x))

    // to the end: the last hour of the forecast is in view
    await strip.evaluate((element) => {
      element.scrollLeft = element.scrollWidth
    })
    await expect.poll(() => strip.evaluate(element => element.scrollLeft + element.clientWidth >= element.scrollWidth - 1)).toBe(true)
    const days = await svg(page).locator('text').allTextContents()
    expect(days.filter(text => /^[A-Z][a-z]{2}/.test(text)).length).toBeGreaterThan(0)
  })

  test('fills the width up to the cap on a wide screen, where the whole forecast fits', async ({ page, baseURL }) => {
    await open(page, baseURL!, WIDGET, { width: 1800, height: 900 })
    // the widget is not capped: 72 hours at 22 px at the widest is 1584 px, which the screen holds
    const strip = scroller(page)
    expect(await strip.evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true)
    expect(await labelSpacing(page)).toBeGreaterThan(40)
  })
})

test.describe('by keyboard', () => {
  test('steps the crosshair through the hours and reads them out, one tab stop for the whole chart', async ({ page, baseURL }) => {
    await open(page, baseURL!)
    await figure(page).focus()
    await expect(figure(page)).toBeFocused()
    await expect(readout(page)).toHaveCount(0)

    await page.keyboard.press('ArrowRight')
    await expect(readout(page)).toBeVisible()
    const first = (await announced(page).textContent())!.trim()
    expect(first).toMatch(/\d{2}[:.]\d{2}/)
    expect(first).toContain('Temperature')
    await page.keyboard.press('ArrowRight')
    await expect.poll(async () => (await announced(page).textContent())!.trim()).not.toBe(first)
    await page.keyboard.press('Shift+ArrowRight')
    await page.keyboard.press('PageDown')
    await page.keyboard.press('End')
    await expect(readout(page)).toBeVisible()
    await page.keyboard.press('Home')
    await expect(readout(page)).toBeVisible()

    // the whole chart is one stop: Tab leaves it, and Shift+Tab comes back to it
    await page.keyboard.press('Tab')
    await expect(figure(page)).not.toBeFocused()
    await page.keyboard.press('Shift+Tab')
    await expect(figure(page)).toBeFocused()
  })

  test('zooms with + and -, and goes back with 0', async ({ page, baseURL }) => {
    await open(page, baseURL!, PAGE, { width: 1280, height: 900 })
    await figure(page).focus()
    const initial = await labelSpacing(page)
    await page.keyboard.press('+')
    await expect.poll(() => labelSpacing(page)).toBeGreaterThan(initial)
    const zoomed = await labelSpacing(page)
    await page.keyboard.press('+')
    await expect.poll(() => labelSpacing(page)).toBeGreaterThanOrEqual(zoomed)
    await page.keyboard.press('-')
    await page.keyboard.press('-')
    await page.keyboard.press('0')
    await expect.poll(() => labelSpacing(page)).toBe(initial)
  })

  test('has buttons for the zoom, the scroll and the reset, named by what they do', async ({ page, baseURL }) => {
    await open(page, baseURL!, PAGE, { width: 1280, height: 900 })
    const group = page.getByRole('group', { name: 'Zoom and scroll the chart' })
    for (const name of ['Earlier hours', 'Later hours', 'Zoom out', 'Zoom in', 'Reset zoom'])
      await expect(group.getByRole('button', { name })).toBeVisible()
    const initial = await labelSpacing(page)
    await group.getByRole('button', { name: 'Zoom in' }).click()
    await expect.poll(() => labelSpacing(page)).toBeGreaterThan(initial)
    await group.getByRole('button', { name: 'Reset zoom' }).click()
    await expect.poll(() => labelSpacing(page)).toBe(initial)
    const first = await hourLabels(page).allTextContents()
    await group.getByRole('button', { name: 'Later hours' }).click()
    await expect.poll(async () => (await hourLabels(page).allTextContents()).join()).not.toBe(first.join())
  })
})

test.describe('the readout (WCAG 1.4.13)', () => {
  // over a panel of the chart, in the middle of the plot
  async function overPlot(page: Page, fraction = 0.3) {
    const box = (await page.locator('.mg-stage').boundingBox())!
    return { x: box.x + 68 + (box.width - 78) * fraction, y: box.y + box.height * 0.6 }
  }

  test('appears under the pointer, can be moved onto, and stays while the pointer is over it', async ({ page, baseURL }) => {
    await open(page, baseURL!, PAGE, { width: 1280, height: 900 })
    const point = await overPlot(page)
    await page.mouse.move(point.x, point.y)
    await expect(readout(page)).toBeVisible()
    const box = (await readout(page).boundingBox())!
    // level with the pointer, so that moving onto it is one step
    expect(box.y).toBeLessThanOrEqual(point.y)
    expect(box.y + box.height).toBeGreaterThanOrEqual(point.y)
    await page.mouse.move(box.x + box.width / 2, point.y, { steps: 8 })
    await expect(readout(page)).toBeVisible()
    // the pointer is over it and it is the same hour
    const hour = await readout(page).locator('.font-semibold').textContent()
    await page.mouse.move(box.x + box.width / 2 + 2, point.y)
    expect(await readout(page).locator('.font-semibold').textContent()).toBe(hour)
    // and it goes where the pointer leaves the chart
    await page.mouse.move(5, 5)
    await expect(readout(page)).toHaveCount(0)
  })

  test('is dismissed by Escape under the pointer, stays dismissed while it rests, and comes back where it moves on', async ({ page, baseURL }) => {
    await open(page, baseURL!, PAGE, { width: 1280, height: 900 })
    const point = await overPlot(page)
    await page.mouse.move(point.x, point.y)
    await expect(readout(page)).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(readout(page)).toHaveCount(0)
    await page.waitForTimeout(500)
    await expect(readout(page)).toHaveCount(0)
    await page.mouse.move(point.x + 25, point.y)
    await expect(readout(page)).toBeVisible()
  })

  test('is dismissed by Escape with the focus on the chart, which keeps the focus, and is closed by its button', async ({ page, baseURL }) => {
    await open(page, baseURL!)
    await figure(page).focus()
    await page.keyboard.press('ArrowRight')
    await expect(readout(page)).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(readout(page)).toHaveCount(0)
    await expect(figure(page)).toBeFocused()
    await page.keyboard.press('ArrowRight')
    await readout(page).getByRole('button', { name: 'Close the values' }).click()
    await expect(readout(page)).toHaveCount(0)
  })

  test('closes a dialog with Escape, which it does not take', async ({ page, baseURL }) => {
    await open(page, baseURL!)
    await figure(page).focus()
    await page.keyboard.press('ArrowRight')
    await expect(readout(page)).toBeVisible()
    await page.getByLabel('Settings', { exact: true }).click()
    await expect(page.getByRole('dialog')).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(page.getByRole('dialog')).toHaveCount(0)
  })
})

test.describe('the zoom', () => {
  test('is linked: a box dragged on a panel zooms them all, and the reset goes back', async ({ page, baseURL }) => {
    await open(page, baseURL!, PAGE, { width: 1280, height: 900 })
    const initial = await labelSpacing(page)
    const box = (await page.locator('.mg-stage').boundingBox())!
    const y = box.y + 200
    await page.mouse.move(box.x + 120, y)
    await page.mouse.down()
    await page.mouse.move(box.x + 260, y, { steps: 6 })
    // the selection is drawn while it is dragged
    await expect(page.locator('.mg-selection')).toBeVisible()
    await page.mouse.up()
    await expect.poll(() => labelSpacing(page)).toBeGreaterThan(initial * 2)
    // a double click goes back
    await page.locator('.mg-stage').dblclick({ position: { x: 300, y: 300 } })
    await expect.poll(() => labelSpacing(page)).toBe(initial)
  })
})

test.describe('the colours', () => {
  test('are the dark ones, symbols included, in dark mode, and the page\'s own in light', async ({ page, baseURL, context }) => {
    await context.addInitScript(() => localStorage.setItem('nuxt-color-mode', 'dark'))
    await open(page, baseURL!)
    await expect(page.locator('.mg-canvas')).toHaveAttribute('data-chart-scheme', 'dark')
    expect(await svg(page).locator('image').first().getAttribute('href')).toContain('/yr-symbols/darkmode/')
  })

  test('are the light ones in light mode', async ({ page, baseURL, context }) => {
    await context.addInitScript(() => localStorage.setItem('nuxt-color-mode', 'light'))
    await open(page, baseURL!)
    await expect(page.locator('.mg-canvas')).toHaveAttribute('data-chart-scheme', 'light')
    expect(await svg(page).locator('image').first().getAttribute('href')).toContain('/yr-symbols/lightmode/')
  })

  test('credit the symbols to Yr under CC BY 4.0, with links', async ({ page, baseURL }) => {
    await open(page, baseURL!)
    const credit = page.getByTestId('meteogram-credit')
    await expect(credit).toContainText('Weather symbols by Yr')
    await expect(credit.getByRole('link', { name: 'CC BY 4.0' })).toHaveAttribute('href', 'https://creativecommons.org/licenses/by/4.0/')
    await expect(credit.getByRole('link', { name: 'Yr' })).toHaveAttribute('href', 'https://github.com/nrkno/yr-weather-symbols')
  })
})
