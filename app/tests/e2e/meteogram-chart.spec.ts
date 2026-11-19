import type { Locator, Page } from '@playwright/test'
import { expect, test } from '@playwright/test'
import { chartLayout } from '../../app/utils/meteogram-geometry'
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
    // drawn at a size it says, which a print scales the picture by
    const [width, height] = (await svg(page).getAttribute('viewBox'))!.split(' ').slice(2).map(Number)
    expect(width).toBe(Number(await svg(page).getAttribute('width')))
    expect(height).toBe(Number(await svg(page).getAttribute('height')))
    // every request the page made was one the mock answers, so a missing barb is not a missing answer
    expect(backend.unanswered).toEqual([])
  })

  test(`${name} does not load Plotly`, async ({ page, baseURL }) => {
    // the script files are hashed, so what is asked for cannot be told by its name: what is in them can. `plotly-notifier` is the class of
    // Plotly's own notifications, in its code and in no other's
    const plotly: string[] = []
    let scripts = 0
    page.on('response', async (response) => {
      if (!/\.js(?:\?|$)/.test(response.url()))
        return
      scripts++
      if ((await response.text().catch(() => '')).includes('plotly-notifier'))
        plotly.push(response.url())
    })
    await open(page, baseURL!, path)
    await page.waitForLoadState('networkidle')
    expect(scripts, 'the scripts the page was served').toBeGreaterThan(20)
    expect(plotly, 'a script with Plotly in it').toEqual([])
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
    // the same strip on a phone and on a desktop's card: the 71 hours between the first and the last stamp at 10 px,
    // and the gutters of the axes (56 px at the least at the left, 71 with the pressure's labels, and 10 at the right).
    // A phone on its side (844 px) has the chart edge to edge since GH-4227, which is room for the whole of it: the strip is
    // then as wide as the window lets it be, and no narrower than the others
    const [narrow, phone, landscape, desktop] = seen
    expect(new Set([narrow, phone, desktop].map(entry => entry!.strip)).size, JSON.stringify(seen)).toBe(1)
    expect(narrow!.strip).toBeGreaterThanOrEqual(71 * 10 + 66)
    expect(narrow!.strip).toBeLessThanOrEqual(71 * 10 + 94)
    expect(landscape!.strip).toBeGreaterThanOrEqual(narrow!.strip)
    expect(landscape!.strip).toBeLessThanOrEqual(844)
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

  test('scrolls to the very end of a short forecast that is drawn at its widest spacing, and stays there', async ({ page, baseURL }) => {
    // 24 hours at 22 px an hour: the chart is narrower than its column, and so is its scroller
    await open(page, baseURL!, `${PAGE}&horizon=24`, { width: 1280, height: 900 })
    await figure(page).focus()
    for (let i = 0; i < 4; i++)
      await page.keyboard.press('+')
    await page.keyboard.press('End')
    await expect(readout(page)).toBeVisible()
    const strip = scroller(page)
    // the scroller is as wide as the chart, and the end of the strip is the end of the window
    const sizes = await strip.evaluate(element => ({ scroller: element.clientWidth, stage: (element.querySelector('.mg-stage') as HTMLElement).offsetWidth, left: element.scrollLeft, max: element.scrollWidth - element.clientWidth }))
    expect(sizes.scroller).toBe(sizes.stage)
    expect(sizes.left).toBeGreaterThanOrEqual(sizes.max - 1)
    // and the window does not come back from it: the last hour is still the one the crosshair is at
    await page.waitForTimeout(500)
    await expect(readout(page)).toBeVisible()
    expect(await strip.evaluate(element => element.scrollLeft)).toBeGreaterThanOrEqual(sizes.max - 1)
  })

  test('fills the width up to the cap on a wide screen, where the whole forecast fits', async ({ page, baseURL }) => {
    await open(page, baseURL!, WIDGET, { width: 1800, height: 900 })
    // the widget is not capped: 72 hours at 22 px at the widest is 1584 px, which the screen holds
    const strip = scroller(page)
    expect(await strip.evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true)
    expect(await labelSpacing(page)).toBeGreaterThan(40)
  })
})

test.describe('on a phone, in German (the longest labels), with every panel on', () => {
  const WIDTHS = [320, 390]

  test.beforeEach(async ({ context, baseURL }) => {
    await context.addCookies([{ name: 'wd_lang', value: 'de', url: baseURL! }])
  })

  for (const width of WIDTHS) {
    test(`keeps every title of an axis inside the chart, left of the tick labels of its panel and close to them at ${width} px (GH-4132)`, async ({ page, baseURL }) => {
      await open(page, baseURL!, PAGE_CHART, { width, height: 844 })
      const found = await page.evaluate(() => {
        const stage = document.querySelector('.mg-stage')!.getBoundingClientRect()
        const texts = [...document.querySelectorAll<SVGTextElement>('.mg-canvas svg text')].map((text) => {
          const box = text.getBoundingClientRect()
          // ECharts turns a title to read upwards with `transform="matrix(0,-1,1,0,x,y)"` on the text: the turn is read from the
          // matrix that draws it (a quarter turn has the sine at 1, whatever the scale), never from the shape of its box, which
          // a two-letter day name such as "Sa" can have as well (taller than wide in Firefox's font)
          const matrix = text.getScreenCTM()
          const turned = !!matrix && Math.abs(matrix.b) / Math.hypot(matrix.a, matrix.b) > 0.9
          return { text: text.textContent ?? '', left: box.left - stage.left, right: box.right - stage.left, top: box.top, bottom: box.bottom, turned }
        })
        // the titles are the words turned to read upwards; the labels of the axes are numbers
        // (only what is in the gutter counts: the first day name is at the left as well)
        const titles = texts.filter(entry => entry.turned && entry.left < 100)
        const labels = texts.filter(entry => !entry.turned && /^[-\d.,]+$/.test(entry.text) && entry.right < 100)
        return { titles, labels, stage: stage.width, stageTop: stage.top }
      })
      // the panels' grids, where the layout puts them: each has its title and its labels in it
      const rows = chartLayout(['wind', 'precip', 'cloud', 'temp', 'pressure'], true).rows
      const inRow = (row: typeof rows[number], entry: { top: number, bottom: number }) => (entry.top + entry.bottom) / 2 >= found.stageTop + row.top && (entry.top + entry.bottom) / 2 <= found.stageTop + row.top + row.height
      // a title for each of the five panels, of one or two lines
      expect(found.titles.length, JSON.stringify(found.titles)).toBeGreaterThanOrEqual(5)
      expect(found.labels.length).toBeGreaterThanOrEqual(3)
      for (const title of found.titles) {
        // (a pixel to spare: the rotated box is 1 px further left in Firefox than in Chrome)
        expect(title.left, `${title.text} is cut at the left`).toBeGreaterThanOrEqual(1)
        // the labels of its own panel: those in the same grid, of which a panel has two at least
        const row = rows.find(candidate => inRow(candidate, title))
        expect(row, `${title.text} is in no panel: ${JSON.stringify({ title, stageTop: found.stageTop })}`).toBeDefined()
        // a label is its panel's when its middle is in the grid or within half a label below it: the lowest label sits on the grid's
        // bottom line, and Firefox puts its middle a fraction of a px below it (a panel of 0 and 0,5 then had one label). The top needs
        // none: the axis' maximum is not labelled, so no label sits on a grid's top line, where the panel above ends
        const own = found.labels.filter(label => inRow({ ...row!, height: row!.height + 9 }, label))
        expect(own.length, `${title.text} (${row!.id}) has fewer than two labels in its panel: ${JSON.stringify(found.labels)}`).toBeGreaterThanOrEqual(2)
        const middleOf = (entry: { top: number, bottom: number }) => (entry.top + entry.bottom) / 2
        const ownLeft = Math.min(...own.map(entry => entry.left))
        expect(title.right, `${title.text} is under the labels`).toBeLessThanOrEqual(ownLeft + 0.5)
        // and it stands next to them, not at the far left of a gutter made for the widest labels of all: the room between is the 4 px
        // of the layout and what the estimate of the labels' width has over their real width (a few px), where it was 33 px for the wind's
        // (a title of two lines is two texts, with the same middle: the block's right edge is its last line's)
        const blockRight = Math.max(...found.titles.filter(other => Math.abs(middleOf(other) - middleOf(title)) < 2).map(other => other.right))
        expect(ownLeft - blockRight, `${title.text} stands off its labels: ${JSON.stringify({ title, own })}`).toBeLessThanOrEqual(14)
      }
      // the panel with the widest labels (the pressure's thousands separator) has its title at the very left edge
      expect(Math.min(...found.titles.map(title => title.left))).toBeLessThanOrEqual(5)
    })
  }

  for (const width of WIDTHS) {
    for (const view of ['chart', 'compact', 'table']) {
      test(`has a toolbar that stays inside its card at ${width} px in the ${view} view`, async ({ page, baseURL }) => {
        await mockBackend(page, baseURL!)
        await page.setViewportSize({ width, height: 844 })
        await page.goto(`/meteogram?station=10384&view=${view}`)
        await expect(page.getByRole('radiogroup', { name: 'Ansicht' })).toBeVisible()
        const outside = await page.evaluate(() => {
          const card = document.querySelector('[role="radiogroup"]')!.closest('[data-slot="root"]')!.getBoundingClientRect()
          const toolbar = document.querySelector('[role="radiogroup"][aria-label="Ansicht"]')!.parentElement!.parentElement!.parentElement!
          return [...toolbar.querySelectorAll('button, [role="radiogroup"], [role="radio"]')]
            .map((element) => {
              const box = element.getBoundingClientRect()
              return { name: element.getAttribute('aria-label') ?? element.textContent?.trim().slice(0, 20), left: Math.round(box.left - card.left), right: Math.round(box.right - card.right) }
            })
            .filter(entry => entry.left < 0 || entry.right > 0)
        })
        expect(outside, 'controls that stick out of the card').toEqual([])
        expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(0)
      })
    }
  }
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
    // back to the spacing it had, to a fraction of a pixel: a browser's layout of the labels is not exact to the last bit (Firefox: 60.0000 against 59.9992)
    await expect.poll(() => labelSpacing(page)).toBeCloseTo(initial, 0)
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
    // back to the spacing it had, to a fraction of a pixel: a browser's layout of the labels is not exact to the last bit (Firefox: 60.0000 against 59.9992)
    await expect.poll(() => labelSpacing(page)).toBeCloseTo(initial, 0)
    const first = await hourLabels(page).allTextContents()
    await group.getByRole('button', { name: 'Later hours' }).click()
    await expect.poll(async () => (await hourLabels(page).allTextContents()).join()).not.toBe(first.join())
  })
})

// WCAG 2.4.3 (GH-4101): a toolbar button that turns off while it has the focus is off (`aria-disabled`) and keeps the focus; `disabled`
// would drop it to the page, and a keyboard user would start again from the top. Pressed again, it does nothing.
test.describe('a toolbar button that turns off while it has the focus', () => {
  const focusedLabel = (page: Page) => page.evaluate(() => document.activeElement?.getAttribute('aria-label') ?? document.activeElement?.tagName)
  async function pressUntilOff(page: Page, button: Locator, key: string) {
    for (let press = 0; press < 40; press++)
      await page.keyboard.press(key)
    await expect(button).toHaveAttribute('aria-disabled', 'true')
  }

  test('Zoom in keeps the focus at its limit, and does nothing when it is pressed again', async ({ page, baseURL }) => {
    await open(page, baseURL!, PAGE, { width: 1280, height: 900 })
    const group = page.getByRole('group', { name: 'Zoom and scroll the chart' })
    const zoomIn = group.getByRole('button', { name: 'Zoom in' })
    await expect(zoomIn).not.toHaveAttribute('aria-disabled', 'true')
    await zoomIn.focus()
    await pressUntilOff(page, zoomIn, 'Enter')
    await expect(zoomIn).toBeFocused()
    expect(await focusedLabel(page)).toBe('Zoom in')
    // still a button in the tab order, not a disabled one
    expect(await zoomIn.evaluate((button: HTMLButtonElement) => [button.disabled, button.tabIndex])).toEqual([false, 0])
    const atLimit = await labelSpacing(page)
    await page.keyboard.press('Enter')
    await page.keyboard.press('Space')
    await expect(zoomIn).toBeFocused()
    await expect(zoomIn).toHaveAttribute('aria-disabled', 'true')
    expect(await labelSpacing(page)).toBe(atLimit)
  })

  test('Later keeps the focus at the end of the forecast', async ({ page, baseURL }) => {
    await open(page, baseURL!, PAGE, { width: 1280, height: 900 })
    const group = page.getByRole('group', { name: 'Zoom and scroll the chart' })
    await group.getByRole('button', { name: 'Zoom in' }).click()
    const later = group.getByRole('button', { name: 'Later hours' })
    await expect(later).not.toHaveAttribute('aria-disabled', 'true')
    await later.focus()
    await pressUntilOff(page, later, 'Space')
    await expect(later).toBeFocused()
    expect(await focusedLabel(page)).toBe('Later hours')
    // the first hour on screen stays where the end of the forecast put it
    const hours = (await hourLabels(page).allTextContents()).join()
    await page.keyboard.press('Space')
    await page.keyboard.press('Enter')
    await expect(later).toBeFocused()
    expect((await hourLabels(page).allTextContents()).join()).toBe(hours)
  })
})

test.describe('the readout (WCAG 1.4.13)', () => {
  // over a panel of the chart, a third of the way along the plot, at the middle of an hour: the tests that move the pointer by a pixel
  // or two need to stay in the hour, which a fixed x does not do (the gutter and the width of the chart differ by a few px between the
  // engines and the widths of the labels). The middle is found where the hour under the pointer changes, a pixel at a time.
  async function overPlot(page: Page, fraction = 0.3) {
    const box = (await page.locator('.mg-stage').boundingBox())!
    const y = box.y + box.height * 0.6
    const base = box.x + 71 + (box.width - 81) * fraction
    const hourAt = async (x: number) => {
      await page.mouse.move(x, y)
      await expect(readout(page)).toBeVisible()
      // the readout follows the pointer a frame later
      await page.waitForTimeout(40)
      return (await readout(page).locator('.font-semibold').textContent())!
    }
    const hour = await hourAt(base)
    let first = base
    while (base - first < 12 && (await hourAt(first - 1)) === hour)
      first--
    let last = base
    while (last - base < 12 && (await hourAt(last + 1)) === hour)
      last++
    return { x: Math.round((first + last) / 2), y }
  }

  test('appears under the pointer, is docked at the far edge, can be moved onto and holds its hour while the pointer is over it', async ({ page, baseURL }) => {
    await open(page, baseURL!, PAGE, { width: 1280, height: 900 })
    const point = await overPlot(page)
    await page.mouse.move(point.x, point.y)
    await expect(readout(page)).toBeVisible()
    const stage = (await page.locator('.mg-stage').boundingBox())!
    const box = (await readout(page).boundingBox())!
    // the crosshair is in the left of the chart, the readout at its right edge
    expect(box.x + box.width).toBeGreaterThan(stage.x + stage.width - 12)
    expect(box.x).toBeGreaterThan(point.x)
    const hour = await readout(page).locator('.font-semibold').textContent()
    // across to it, by the way a pointer goes, and onto it
    await page.mouse.move(box.x + box.width / 2, box.y + 40, { steps: 25 })
    await expect(readout(page)).toBeVisible()
    const held = await readout(page).locator('.font-semibold').textContent()
    expect(held).not.toBe(hour)
    await page.mouse.move(box.x + box.width / 2 + 4, box.y + 60, { steps: 4 })
    expect(await readout(page).locator('.font-semibold').textContent()).toBe(held)
    // and it goes where the pointer leaves the chart
    await page.mouse.move(5, 5)
    await expect(readout(page)).toHaveCount(0)
  })

  test('does not hold up a pointer that scrubs slowly along the hours: the crosshair follows every step', async ({ page, baseURL }) => {
    await open(page, baseURL!, PAGE, { width: 1280, height: 900 })
    const stage = (await page.locator('.mg-stage').boundingBox())!
    const y = stage.y + stage.height * 0.5
    const start = stage.x + 120
    await page.mouse.move(start, y)
    await expect(readout(page)).toBeVisible()
    const hourAt = async () => (await readout(page).locator('.font-semibold').textContent())!
    const first = await hourAt()
    // a hundred pixels at 4 px a step: ten hours at 10 px an hour
    for (let dx = 4; dx <= 100; dx += 4)
      await page.mouse.move(start + dx, y)
    await expect.poll(hourAt).not.toBe(first)
    const readoutBox = (await readout(page).boundingBox())!
    // the pointer is nowhere near the readout, and the hour is the one under it
    expect(start + 100).toBeLessThan(readoutBox.x)
    await page.mouse.move(start + 112, y)
    const next = await hourAt()
    await page.mouse.move(start + 100, y)
    expect(await hourAt()).not.toBe(next)
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
    // a pixel to the side is the same hour, and no new hover (WCAG 1.4.13)
    await page.mouse.move(point.x + 1, point.y)
    await page.mouse.move(point.x - 1, point.y)
    await page.waitForTimeout(200)
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
    // back to the spacing it had, to a fraction of a pixel: a browser's layout of the labels is not exact to the last bit (Firefox: 60.0000 against 59.9992)
    await expect.poll(() => labelSpacing(page)).toBeCloseTo(initial, 0)
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
    await expect(credit).toContainText('Weather symbols © 2015 Yr/NRK, CC BY 4.0.')
    await expect(credit.getByRole('link', { name: 'CC BY 4.0' })).toHaveAttribute('href', 'https://creativecommons.org/licenses/by/4.0/')
    await expect(credit.getByRole('link', { name: 'Yr' })).toHaveAttribute('href', 'https://github.com/nrkno/yr-weather-symbols')
  })
})

// A chart that prints as an empty box (GH-4080): ECharts lays its SVG out `position: absolute` in a box that has no
// height of its own, so on paper the box was 0 px high with `overflow: hidden` and the panels, bars and tick labels
// were clipped away. The print medium is emulated, which Firefox does as well; the PDF is held in chart-print.spec.ts.
test.describe('on paper', () => {
  test('the chart has a box of its own height, with its y-axis tick labels inside it', async ({ page, baseURL }) => {
    await open(page, baseURL!, PAGE, { width: 1440, height: 1000 })
    await page.emulateMedia({ media: 'print' })
    const layout = await page.evaluate(() => {
      const chart = document.querySelector('.mg-canvas svg')!
      const box = chart.parentElement!.getBoundingClientRect()
      const drawn = chart.getBoundingClientRect()
      // the numbers of the axes: 0, 5, 10, 0.5, 50, and the pressure's 1,010 and 1,015
      const ticks = [...chart.querySelectorAll('text')]
        .filter(text => /^-?\d{1,3}(?:,\d{3})*(?:\.\d+)?$/.test(text.textContent?.trim() ?? ''))
        .map(text => text.getBoundingClientRect())
      return {
        position: getComputedStyle(chart).position,
        boxHeight: box.height,
        drawnHeight: drawn.height,
        ticks: ticks.length,
        // the labels the box does not hold: clipped by it (`overflow: hidden`) when it is shorter than the SVG
        // (4 px of slack: the text box of the lowest label, which sits on the bottom edge, is 2 px taller than its digits)
        outside: ticks.filter(tick => tick.top < box.top - 4 || tick.bottom > box.bottom + 4).length,
      }
    })
    expect(layout.position, 'the SVG is in the flow, not absolute').toBe('static')
    // the panels of the chart, not the 26 px of the credit line
    expect(layout.boxHeight, 'the height of the chart box in print').toBeGreaterThan(200)
    expect(layout.boxHeight).toBeGreaterThanOrEqual(layout.drawnHeight - 1)
    expect(layout.ticks, 'tick labels of the y axes').toBeGreaterThan(5)
    expect(layout.outside, 'tick labels outside the chart box').toBe(0)
  })
})
