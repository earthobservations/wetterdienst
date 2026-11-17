import type { Download, Locator, Page } from '@playwright/test'
import type { Handlers } from './accessibility/mock-backend'
import { readFileSync } from 'node:fs'
import { expect, test } from '@playwright/test'
import { mockBackend } from './accessibility/mock-backend'

// The Explorer's chart (GH-4096): Apache ECharts, drawn as SVG, in place of Plotly. Its chrome takes the colours of the page (the
// legend, the labels of the axes and the readout are the page's text and muted text, 4.5:1 on what is behind them), in dark mode
// too, and follows a switch of the colour scheme without a reload; the series are data and keep their hues (the same hue one step
// darker on the light page where the hue itself is under 3:1 on white). A saved or printed chart is the light one, at the size it
// is shown at. A long series is cut to what the plot can tell apart. The API is answered by the mock backend, so the spec needs
// nothing but the app.

type Rgb = [number, number, number]

function channels(color: string): Rgb {
  const hex = /^#([\da-f]{2})([\da-f]{2})([\da-f]{2})$/i.exec(color)
  if (hex)
    return [Number.parseInt(hex[1]!, 16), Number.parseInt(hex[2]!, 16), Number.parseInt(hex[3]!, 16)]
  const match = /^rgba?\(\s*(\d+)[\s,]+(\d+)[\s,]+(\d+)/.exec(color)
  if (!match)
    throw new Error(`not an rgb() colour: ${JSON.stringify(color)}`)
  return [Number(match[1]), Number(match[2]), Number(match[3])]
}
// WCAG 2.x relative luminance, and the contrast ratio of two colours
function luminance(color: string) {
  const [r, g, b] = channels(color).map(c => c / 255).map(c => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4))
  return 0.2126 * r! + 0.7152 * g! + 0.0722 * b!
}
function contrast(a: string, b: string) {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi! + 0.05) / (lo! + 0.05)
}

/** Two series: the daily maximum and mean temperature of the station, 30 days each, in the answer of the mock backend */
const PATH = '/explorer?provider=dwd&network=observation&resolution=daily&dataset=climate_summary&parameters=temperature_air_max_2m,temperature_air_mean_2m&mode=station&stations=00011'
/** The hues of the first two series: the same on both pages but for the green, a step darker on the light one */
const SERIES = { light: ['#3b82f6', '#16a34a'], dark: ['#3b82f6', '#22c55e'] }

const fetchButton = (page: Page) => page.getByRole('button', { name: 'Show', exact: true })
/** The chart, once it is drawn: the SVG is in its canvas */
const chartSvg = (page: Page) => page.locator('.xc-canvas[data-drawn="true"] svg').first()
const canvas = (page: Page) => page.locator('.xc-canvas').first()

async function showChart(page: Page, baseURL: string, path = PATH, handlers: Handlers = {}) {
  const backend = await mockBackend(page, baseURL, handlers)
  await page.goto(path)
  await fetchButton(page).click()
  await expect(page.getByRole('table').first()).toBeVisible()
  await page.getByRole('button', { name: 'Show as chart', exact: true }).click()
  await expect(chartSvg(page)).toBeVisible()
  return backend
}

async function setColorScheme(page: Page, label: 'Light' | 'Dark') {
  await page.getByLabel('Settings', { exact: true }).click()
  await page.getByRole('button', { name: label, exact: true }).click()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog')).toHaveCount(0)
}

/** What the chart draws, as the browser paints it: the colours of its texts and marks, and what is behind it */
async function paintOf(page: Page) {
  return page.locator('.explorer-chart').first().evaluate((chart) => {
    const context = document.createElement('canvas').getContext('2d', { willReadFrequently: true })!
    const rgb = (color: string) => {
      context.clearRect(0, 0, 1, 1)
      context.fillStyle = color
      context.fillRect(0, 0, 1, 1)
      const [r, g, b, a] = context.getImageData(0, 0, 1, 1).data
      return { text: `rgb(${r}, ${g}, ${b})`, opaque: a === 255 }
    }
    // the first opaque background from the chart outwards: its card
    let element: Element | null = chart
    let behind = ''
    while (element && !behind) {
      const found = rgb(getComputedStyle(element).backgroundColor)
      if (found.opaque)
        behind = found.text
      element = element.parentElement
    }
    const svg = chart.querySelector('.xc-canvas svg')!
    const texts = [...svg.querySelectorAll('text')].map(text => ({ text: text.textContent ?? '', fill: getComputedStyle(text).fill }))
    // the colours of the marks of the series: the strokes of the lines, which are in the legend as well
    const hexes = new Set(['#3b82f6', '#16a34a', '#22c55e'])
    const marks = [...new Set([...svg.querySelectorAll('path')].map(path => path.getAttribute('stroke') ?? '').filter(stroke => hexes.has(stroke)))].sort()
    return { behind: behind || rgb(getComputedStyle(document.body).backgroundColor).text, texts, marks }
  })
}

test.describe('the explorer\'s chart colours', () => {
  test('are the page\'s in light and in dark mode, readable on it, and follow a switch without a reload, the series keeping their hues', async ({ page, baseURL, context }) => {
    await context.addInitScript(() => localStorage.setItem('nuxt-color-mode', 'light'))
    const backend = await showChart(page, baseURL!)
    await expect(page.locator('html')).not.toHaveClass(/dark/)
    await expect(canvas(page)).toHaveAttribute('data-chart-scheme', 'light')

    const light = await paintOf(page)
    expect(luminance(light.behind)).toBeGreaterThan(0.9)
    // no reload: a mark set on the window is still there after the switch
    await page.evaluate(() => ((window as any).__chartThemeMark = 1))
    await setColorScheme(page, 'Dark')
    await expect(page.locator('html')).toHaveClass(/dark/)
    await expect(canvas(page)).toHaveAttribute('data-chart-scheme', 'dark')
    const dark = await paintOf(page)
    expect(await page.evaluate(() => (window as any).__chartThemeMark)).toBe(1)
    expect(luminance(dark.behind)).toBeLessThan(0.05)

    // the series are data: the same hues, the green a step darker on the light page, and every mark 3:1 on the paper (WCAG 1.4.11)
    expect(light.marks).toEqual([...SERIES.light].sort())
    expect(dark.marks).toEqual([...SERIES.dark].sort())
    for (const [scheme, paint] of [['light', light], ['dark', dark]] as const) {
      for (const mark of paint.marks)
        expect(contrast(mark, paint.behind), `${scheme}: the series in ${mark} on ${paint.behind}`).toBeGreaterThanOrEqual(3)
    }

    // WCAG 1.4.3: every text of the chart, 4.5:1 on what is behind it, in both schemes (the legend, the labels of the axes)
    for (const [scheme, paint] of [['light', light], ['dark', dark]] as const) {
      expect(paint.texts.length).toBeGreaterThan(8)
      expect(paint.texts.some(text => /Maximum air temperature|Mean air temperature/.test(text.text)), 'the legend names the series').toBe(true)
      for (const { text, fill } of paint.texts)
        expect(contrast(fill, paint.behind), `${scheme}: ${text} in ${fill} on ${paint.behind}`).toBeGreaterThanOrEqual(4.5)
    }
    // the chrome changed with the scheme
    expect(dark.texts[0]!.fill).not.toBe(light.texts[0]!.fill)

    await setColorScheme(page, 'Light')
    await expect(canvas(page)).toHaveAttribute('data-chart-scheme', 'light')
    expect(await paintOf(page)).toEqual(light)
    expect(backend.unanswered).toEqual([])
  })

  test('are drawn dark at once on a page that opens in dark mode', async ({ page, baseURL, context }) => {
    await context.addInitScript(() => localStorage.setItem('nuxt-color-mode', 'dark'))
    await showChart(page, baseURL!)
    await expect(canvas(page)).toHaveAttribute('data-chart-scheme', 'dark')
    const paint = await paintOf(page)
    expect(luminance(paint.behind)).toBeLessThan(0.05)
    expect(paint.marks).toEqual([...SERIES.dark].sort())
  })

  test('are the same in both facets, which follow the scheme', async ({ page, baseURL, context }) => {
    await context.addInitScript(() => localStorage.setItem('nuxt-color-mode', 'light'))
    await showChart(page, baseURL!)
    await page.getByLabel('Facet by parameter').check()
    await expect(page.locator('.xc-canvas[data-drawn="true"]')).toHaveCount(2)
    const schemes = () => page.locator('.xc-canvas').evaluateAll(charts => charts.map(chart => (chart as HTMLElement).dataset.chartScheme))
    expect(await schemes()).toEqual(['light', 'light'])
    await setColorScheme(page, 'Dark')
    await expect.poll(schemes, { message: 'both facets are drawn dark' }).toEqual(['dark', 'dark'])
    await setColorScheme(page, 'Light')
    await expect.poll(schemes).toEqual(['light', 'light'])
  })

  test('hold the zero line at 3:1 where the axis crosses zero, and put it at 0', async ({ page, baseURL, context }) => {
    await context.addInitScript(() => localStorage.setItem('nuxt-color-mode', 'light'))
    const cold = (url: URL) => ({
      values: Array.from({ length: 30 }, (_, day) => ({
        station_id: '00011',
        resolution: 'daily',
        dataset: 'climate_summary',
        parameter: (url.searchParams.get('parameters') ?? '').split(',')[0]!.split('/')[2],
        timestamp: new Date(Date.UTC(2026, 0, day + 1)).toISOString(),
        value: Math.round((8 * Math.sin(day / 4) - 1) * 10) / 10,
        quality_flags: null,
      })),
    })
    await showChart(page, baseURL!, PATH, { values: cold })
    for (const scheme of ['light', 'dark'] as const) {
      if (scheme === 'dark') {
        await setColorScheme(page, 'Dark')
        await expect(canvas(page)).toHaveAttribute('data-chart-scheme', 'dark')
      }
      const { behind } = await paintOf(page)
      const lines = await chartSvg(page).evaluate((svg) => {
        // the label of the axis that says 0 and the y of the line that is as wide as the plot and is not the grid's
        const zero = [...svg.querySelectorAll('text')].find(text => text.textContent === '0')
        const labelY = Number(/translate\([\d.-]+ ([\d.-]+)\)/.exec(zero?.getAttribute('transform') ?? '')?.[1])
        const horizontal = [...svg.querySelectorAll('path')].flatMap((path) => {
          const match = /^M([\d.]+) ([\d.]+)L([\d.]+) ([\d.]+)$/.exec(path.getAttribute('d') ?? '')
          return match && match[2] === match[4] && Number(match[3]) - Number(match[1]) > 400 ? [{ y: Number(match[2]), stroke: getComputedStyle(path).stroke }] : []
        })
        return { labelY, horizontal }
      })
      expect(lines.labelY, `${scheme}: the axis has a 0`).not.toBeNaN()
      // the grid lines share one colour; the zero line is the one line of another, and it reads on the paper (1.4.11)
      const alone = lines.horizontal.filter(line => lines.horizontal.filter(other => other.stroke === line.stroke).length === 1)
      expect(alone, `${scheme}: one line of a colour of its own, the zero line`).toHaveLength(1)
      expect(contrast(alone[0]!.stroke, behind), `${scheme}: the zero line ${alone[0]!.stroke} on ${behind}`).toBeGreaterThanOrEqual(3)
      expect(Math.abs(alone[0]!.y - lines.labelY)).toBeLessThan(1.5)
    }
  })

  test('mark the moment of the readout with a line that reads on the paper and a dot of the series\' colour on each', async ({ page, baseURL, context }) => {
    await context.addInitScript(() => localStorage.setItem('nuxt-color-mode', 'dark'))
    await showChart(page, baseURL!)
    await page.locator('.xc-stage').focus()
    await page.keyboard.press('ArrowRight')
    await expect(page.getByTestId('explorer-readout')).toBeVisible()
    const { behind } = await paintOf(page)
    // a dot is a circle of 5 px, which the browser draws as an arc of a path
    const marks = await chartSvg(page).evaluate(svg => [...svg.querySelectorAll('path')].filter(path => /A5 5 /.test(path.getAttribute('d') ?? '')).map(path => ({ fill: path.getAttribute('fill') })))
    // a dot on each of the two series, in their colours
    expect(marks.map(mark => mark.fill).sort()).toEqual([...SERIES.dark].sort())
    for (const mark of marks)
      expect(contrast(mark.fill!, behind)).toBeGreaterThanOrEqual(3)
  })
})

// A chart that is saved or printed is the light one, whatever the screen shows, so that images in a report or a slide look
// alike (the maintainers' decision, GH-3528). A saved image is drawn again off screen in the light theme, at the size and under
// the file name it has always had; the chart on the page stays as it is.

/** The size of a downloaded PNG or JPEG, and its pixel at the top left: the paper, which is the margin of the chart */
async function imageOf(page: Page, download: Download) {
  const base64 = readFileSync((await download.path())!).toString('base64')
  return page.evaluate(async (data) => {
    const image = await createImageBitmap(new Blob([Uint8Array.from(atob(data), c => c.charCodeAt(0))]))
    const canvas = document.createElement('canvas')
    canvas.width = image.width
    canvas.height = image.height
    const context = canvas.getContext('2d', { willReadFrequently: true })!
    context.drawImage(image, 0, 0)
    const [r, g, b] = context.getImageData(2, 2, 1, 1).data
    return { width: image.width, height: image.height, corner: `rgb(${r}, ${g}, ${b})` }
  }, base64)
}

test.describe('a saved explorer chart', () => {
  test.beforeEach(async ({ context }) => {
    await context.addInitScript(() => localStorage.setItem('nuxt-color-mode', 'dark'))
  })

  async function menu(page: Page, item: string) {
    await page.getByRole('button', { name: 'Download chart' }).click()
    const saved = page.waitForEvent('download')
    await page.getByRole('menuitem', { name: item, exact: true }).click()
    return saved
  }

  test('is the light one, as large as the chart on the page (one pixel to a pixel), named chart, from the menu', async ({ page, baseURL }) => {
    await showChart(page, baseURL!)
    const shown = (await page.locator('.xc-canvas').boundingBox())!
    for (const [item, extension] of [['PNG', 'png'], ['JPEG', 'jpeg']] as const) {
      const download = await menu(page, item)
      expect(download.suggestedFilename()).toBe(`chart.${extension}`)
      const image = await imageOf(page, download)
      expect(luminance(image.corner), `the saved image is light (its corner is ${image.corner})`).toBeGreaterThan(0.9)
      expect(image.width).toBe(Math.round(shown.width))
      expect(image.height).toBe(Math.round(shown.height))
      // the chart on the page is as dark as it was, and the copy that was drawn for the image is gone
      await expect(canvas(page)).toHaveAttribute('data-chart-scheme', 'dark')
      await expect(page.locator('.xc-canvas')).toHaveCount(1)
    }
  })

  test('is a vector of the size of the chart from the menu, with the light chart\'s colours and its legend', async ({ page, baseURL }) => {
    await showChart(page, baseURL!)
    const download = await menu(page, 'SVG')
    expect(download.suggestedFilename()).toBe('chart.svg')
    const svg = readFileSync((await download.path())!, 'utf8')
    const shown = (await page.locator('.xc-canvas').boundingBox())!
    expect(svg).toContain(`width="${Math.round(shown.width)}" height="${Math.round(shown.height)}"`)
    // the legend names the series, in the file
    expect(svg).toMatch(/00011 - (Maximum|Mean) air temperature/)
    // on the light paper: the first thing the vector draws is a rect that is neither empty nor transparent, and it is light
    const paper = /^<svg[^>]*>\s*<rect[^>]*fill="([^"]*)"/.exec(svg)?.[1]
    expect(paper, 'the vector draws its paper').toMatch(/^(rgb|#)/)
    expect(luminance(paper!)).toBeGreaterThan(0.9)
    // the dark theme's text colour is not in it, nor the dark page's green
    const dark = (await paintOf(page)).texts[0]!.fill
    expect(svg).not.toContain(dark.replaceAll(' ', ''))
    expect(svg).toContain(SERIES.light[1])
    expect(svg).not.toContain(SERIES.dark[1])
  })

  test('is the light one and as large as the chart, from the camera of the toolbar, named newplot', async ({ page, baseURL }) => {
    await showChart(page, baseURL!)
    const shown = (await page.locator('.xc-canvas').boundingBox())!
    const saved = page.waitForEvent('download')
    await page.getByRole('button', { name: 'Download plot as a PNG' }).click()
    const download = await saved
    expect(download.suggestedFilename()).toBe('newplot.png')
    const image = await imageOf(page, download)
    expect(luminance(image.corner)).toBeGreaterThan(0.9)
    expect([image.width, image.height]).toEqual([Math.round(shown.width), Math.round(shown.height)])
    await expect(canvas(page)).toHaveAttribute('data-chart-scheme', 'dark')
  })

  test('is the chart as it is shown: the window it is zoomed to and the series its legend has on', async ({ page, baseURL }) => {
    await showChart(page, baseURL!)
    await page.getByRole('button', { name: 'Zoom in', exact: true }).click()
    await page.getByRole('button', { name: 'Zoom in', exact: true }).click()
    await expect(page.getByRole('button', { name: 'Reset zoom' })).toBeEnabled()
    // the second series is turned off: its colour is not in the file
    await page.locator('.xc-legend button').nth(1).click()
    await expect(page.locator('.xc-legend button').nth(1)).toHaveAttribute('aria-pressed', 'false')
    const download = await menu(page, 'SVG')
    const svg = readFileSync((await download.path())!, 'utf8')
    expect(svg).toContain(SERIES.light[0])
    expect(svg).not.toContain(SERIES.light[1])
    // the days of the window and not the whole month: the axis has days of September in the middle, not all of them
    const days = [...svg.matchAll(/>Sep (\d+)<\/text>/g)].map(match => Number(match[1]))
    expect(days.length).toBeGreaterThan(1)
    expect(Math.max(...days) - Math.min(...days)).toBeLessThan(29)
  })

  test('stacks the facets, each as large as it is shown, from the menu, and each facet has a camera of its own', async ({ page, baseURL }) => {
    await showChart(page, baseURL!)
    await page.getByLabel('Facet by parameter').check()
    await expect(page.locator('.xc-canvas[data-drawn="true"]')).toHaveCount(2)
    const boxes = await page.locator('.xc-canvas').evaluateAll(canvases => canvases.map(element => ({ width: Math.round(element.getBoundingClientRect().width), height: Math.round(element.getBoundingClientRect().height) })))
    const download = await menu(page, 'PNG')
    expect(download.suggestedFilename()).toBe('chart.png')
    const image = await imageOf(page, download)
    expect(luminance(image.corner)).toBeGreaterThan(0.9)
    expect(image.width).toBe(Math.max(...boxes.map(box => box.width)))
    expect(image.height).toBe(boxes.reduce((sum, box) => sum + box.height, 0))
    // the camera of one facet saves that facet alone
    const saved = page.waitForEvent('download')
    await page.getByRole('button', { name: 'Download plot as a PNG' }).nth(1).click()
    const one = await imageOf(page, await saved)
    expect([one.width, one.height]).toEqual([boxes[1]!.width, boxes[1]!.height])
  })
})

test.describe('a printed explorer chart', () => {
  test('is drawn light for as long as the page is printed, and dark again after', async ({ page, baseURL, context }) => {
    await context.addInitScript(() => localStorage.setItem('nuxt-color-mode', 'dark'))
    await showChart(page, baseURL!)
    await expect(canvas(page)).toHaveAttribute('data-chart-scheme', 'dark')
    await page.emulateMedia({ media: 'print' })
    await expect(canvas(page)).toHaveAttribute('data-chart-scheme', 'light')
    const printed = await paintOf(page)
    expect(printed.marks).toEqual([...SERIES.light].sort())
    for (const { fill } of printed.texts)
      expect(luminance(fill)).toBeLessThan(0.3)
    await page.emulateMedia({ media: 'screen' })
    await expect(canvas(page)).toHaveAttribute('data-chart-scheme', 'dark')
  })

  test('is not drawn again where a page that is light is printed', async ({ page, baseURL, context }) => {
    await context.addInitScript(() => localStorage.setItem('nuxt-color-mode', 'light'))
    await showChart(page, baseURL!)
    const drawings = () => page.evaluate(() => performance.getEntriesByName('explorer:drawn').length)
    const before = await drawings()
    expect(before).toBeGreaterThan(0)
    await page.emulateMedia({ media: 'print' })
    await page.evaluate(() => window.dispatchEvent(new Event('beforeprint')))
    await page.waitForTimeout(1000)
    await page.evaluate(() => window.dispatchEvent(new Event('afterprint')))
    await page.emulateMedia({ media: 'screen' })
    await page.waitForTimeout(500)
    expect(await drawings(), 'drawings while it was printed').toBe(before)
  })

  test('is scaled to the width of the sheet, whole (the legend in it), without its toolbar, the legend\'s buttons and its readout', async ({ page, baseURL, context }) => {
    await context.addInitScript(() => localStorage.setItem('nuxt-color-mode', 'light'))
    await showChart(page, baseURL!)
    await page.locator('.xc-stage').focus()
    await page.keyboard.press('ArrowRight')
    await expect(page.getByTestId('explorer-readout')).toBeVisible()
    await page.emulateMedia({ media: 'print' })
    await expect(page.locator('.xc-toolbar')).toBeHidden()
    await expect(page.locator('.xc-legend')).toBeHidden()
    await expect(page.getByTestId('explorer-readout')).toBeHidden()
    // the chart is in the flow, with its own height: a box of 0 px with the SVG cut off was the print of the forecast (GH-4080)
    const box = (await chartSvg(page).boundingBox())!
    const column = await page.locator('.explorer-chart').evaluate(element => element.clientWidth)
    expect(box.width).toBeLessThanOrEqual(column + 1)
    expect(box.width).toBeGreaterThan(300)
    expect(box.height).toBeGreaterThan(box.width * 0.35)
    // the legend is in the picture, and so are the labels of the axes
    const texts = await chartSvg(page).evaluate(svg => [...svg.querySelectorAll('text')].map(text => text.textContent))
    expect(texts.some(text => /air temperature/.test(text ?? ''))).toBe(true)
    expect(texts.length).toBeGreaterThan(8)
  })
})

// The zoom is the chart's: it stays where the colours or the language change, and a reset goes back to all of it
test('a zoomed chart stays zoomed where the scheme switches, and its reset still goes back to the whole range', async ({ page, baseURL, context }) => {
  await context.addInitScript(() => localStorage.setItem('nuxt-color-mode', 'light'))
  await showChart(page, baseURL!)
  const window = () => canvas(page).getAttribute('data-window')
  const whole = await window()

  // a box dragged on the plot zooms it in
  await page.locator('.xc-stage').scrollIntoViewIfNeeded()
  const plot = (await page.locator('.xc-stage').boundingBox())!
  await page.mouse.move(plot.x + plot.width * 0.3, plot.y + plot.height * 0.5)
  await page.mouse.down()
  await page.mouse.move(plot.x + plot.width * 0.6, plot.y + plot.height * 0.5, { steps: 5 })
  await page.mouse.up()
  await expect.poll(window).not.toBe(whole)
  const zoomed = await window()

  await setColorScheme(page, 'Dark')
  await expect(canvas(page)).toHaveAttribute('data-chart-scheme', 'dark')
  expect(await window()).toBe(zoomed)
  await page.emulateMedia({ media: 'print' })
  await expect(canvas(page)).toHaveAttribute('data-chart-scheme', 'light')
  expect(await window()).toBe(zoomed)
  await page.emulateMedia({ media: 'screen' })

  // a double click is the way back
  await page.locator('.xc-stage').dblclick({ position: { x: 5, y: 5 } })
  await expect.poll(window).toBe(whole)
})

// The vertical grid lines are the ticks of the time axis: evenly spaced, and none a few px from another (the library's own ticks added
// every month start and the end of the axis, which a label hides and a grid line does not)
async function gridXs(page: Page) {
  return chartSvg(page).evaluate((svg) => {
    // the lines of the grid are the paths of one colour that run from the top of the plot to its foot, and the horizontal ones are the other way
    const lines = [...svg.querySelectorAll('path')].flatMap((path) => {
      const match = /^M([\d.]+) ([\d.]+)L([\d.]+) ([\d.]+)$/.exec(path.getAttribute('d') ?? '')
      return match && match[1] === match[3] && Math.abs(Number(match[4]) - Number(match[2])) > 100 ? [{ x: Number(match[1]), stroke: path.getAttribute('stroke') }] : []
    })
    const common = lines.map(line => line.stroke).sort((a, b) => lines.filter(l => l.stroke === b).length - lines.filter(l => l.stroke === a).length)[0]
    return lines.filter(line => line.stroke === common).map(line => line.x).sort((a, b) => a - b)
  })
}

function expectEvenlySpaced(xs: number[], what: string) {
  expect(xs.length, `${what}: the grid lines`).toBeGreaterThanOrEqual(2)
  const gaps = xs.slice(1).map((x, i) => x - xs[i]!)
  // a month is 28 to 31 days: calendar steps differ by a tenth, a doubled line is a few px from its neighbour
  expect(Math.min(...gaps), `${what}: the closest two lines of ${JSON.stringify(xs)}`).toBeGreaterThan(0.8 * Math.max(...gaps))
  expect(Math.min(...gaps)).toBeGreaterThan(40)
}

test('the grid lines are evenly spaced, whole, zoomed by a box, and by the keys', async ({ page, baseURL, context }) => {
  await context.addInitScript(() => localStorage.setItem('nuxt-color-mode', 'light'))
  // a year of days, so that zooming passes the month starts and the end of the axis
  const year = (url: URL) => ({
    values: Array.from({ length: 365 }, (_, day) => ({
      station_id: '00011',
      resolution: 'daily',
      dataset: 'climate_summary',
      parameter: (url.searchParams.get('parameters') ?? '').split(',')[0]!.split('/')[2],
      timestamp: new Date(Date.UTC(2025, 0, day + 1)).toISOString(),
      value: Math.round((10 + 8 * Math.sin(day / 58) + (day % 5)) * 10) / 10,
      quality_flags: null,
    })),
  })
  await showChart(page, baseURL!, PATH, { values: year })
  expectEvenlySpaced(await gridXs(page), 'the whole year')

  await page.locator('.xc-stage').scrollIntoViewIfNeeded()
  const plot = (await page.locator('.xc-stage').boundingBox())!
  const before = await canvas(page).getAttribute('data-window')
  await page.mouse.move(plot.x + plot.width * 0.3, plot.y + plot.height * 0.5)
  await page.mouse.down()
  await page.mouse.move(plot.x + plot.width * 0.65, plot.y + plot.height * 0.5, { steps: 5 })
  await page.mouse.up()
  await expect.poll(() => canvas(page).getAttribute('data-window')).not.toBe(before)
  expectEvenlySpaced(await gridXs(page), 'zoomed by a box')

  await page.locator('.xc-stage').focus()
  for (const keys of [['+'], ['+'], ['-'], ['-', '-']]) {
    for (const key of keys)
      await page.keyboard.press(key)
    await page.waitForTimeout(150)
    expectEvenlySpaced(await gridXs(page), `after ${keys.join('')}`)
  }
})

test('the chart takes a zoom by the wheel with Ctrl, a y axis that follows the window, and a reset by the key', async ({ page, baseURL, context }) => {
  await context.addInitScript(() => localStorage.setItem('nuxt-color-mode', 'light'))
  await showChart(page, baseURL!)
  const window = () => canvas(page).getAttribute('data-window')
  const whole = await window()
  await page.locator('.xc-stage').scrollIntoViewIfNeeded()
  const plot = (await page.locator('.xc-stage').boundingBox())!
  await page.mouse.move(plot.x + plot.width / 2, plot.y + plot.height / 2)
  await page.keyboard.down('Control')
  await page.mouse.wheel(0, -300)
  await page.keyboard.up('Control')
  await expect.poll(window).not.toBe(whole)
  await page.locator('.xc-stage').focus()
  await page.keyboard.press('0')
  await expect.poll(window).toBe(whole)
})

// WCAG 2.4.3 (GH-4101): a toolbar button that turns off while it has the focus is off (`aria-disabled`) and keeps the focus; `disabled`
// would drop it to the page, and a keyboard user would start again from the top. Pressed again, it does nothing.
test.describe('a toolbar button that turns off while it has the focus', () => {
  const windowOf = (page: Page) => canvas(page).getAttribute('data-window')
  /** The key that is pressed on a focused button until it is off, then once more */
  async function pressUntilOff(page: Page, button: Locator, key: string) {
    for (let press = 0; press < 40; press++)
      await page.keyboard.press(key)
    await expect(button).toHaveAttribute('aria-disabled', 'true')
  }
  const focusedLabel = (page: Page) => page.evaluate(() => document.activeElement?.getAttribute('aria-label') ?? document.activeElement?.tagName)

  test('Reset zoom keeps the focus on Space, and does nothing when it is pressed again', async ({ page, baseURL }) => {
    await showChart(page, baseURL!)
    const reset = page.locator('.xc-toolbar button[aria-label="Reset zoom"]')
    await page.getByRole('button', { name: 'Zoom in', exact: true }).click()
    await expect(reset).not.toHaveAttribute('aria-disabled', 'true')
    const zoomed = await windowOf(page)
    await reset.focus()
    await page.keyboard.press('Space')
    await expect(reset).toHaveAttribute('aria-disabled', 'true')
    await expect.poll(() => windowOf(page)).not.toBe(zoomed)
    const whole = await windowOf(page)
    await expect(reset).toBeFocused()
    expect(await focusedLabel(page)).toBe('Reset zoom')
    // still a button in the tab order, not a disabled one
    expect(await reset.evaluate((button: HTMLButtonElement) => [button.disabled, button.tabIndex])).toEqual([false, 0])
    await page.keyboard.press('Space')
    await page.keyboard.press('Enter')
    await expect(reset).toBeFocused()
    await expect(reset).toHaveAttribute('aria-disabled', 'true')
    expect(await windowOf(page)).toBe(whole)
  })

  test('an unavailable Reset zoom does nothing when it is pressed: a readout dismissed by Escape stays closed', async ({ page, baseURL }) => {
    await showChart(page, baseURL!)
    const readout = page.getByTestId('explorer-readout')
    // the pointer's readout: one the keyboard put there goes when the focus leaves the chart, the pointer's stays
    await page.locator('.xc-stage').scrollIntoViewIfNeeded()
    const box = (await page.locator('.xc-stage').boundingBox())!
    await page.mouse.move(box.x + box.width * 0.25 - 12, box.y + box.height * 0.55)
    await page.mouse.move(box.x + box.width * 0.25, box.y + box.height * 0.55, { steps: 4 })
    await expect(readout).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(readout).toHaveCount(0)
    // a reset of the zoom would show the readout again: the whole chart is shown, so Reset zoom is off and must not
    const reset = page.locator('.xc-toolbar button[aria-label="Reset zoom"]')
    await expect(reset).toHaveAttribute('aria-disabled', 'true')
    await reset.focus()
    // read at once, not polled for: a readout that came back is drawn by the time the key press has returned (it goes again on its own, so a
    // polled check would not see it)
    await page.keyboard.press('Enter')
    expect(await readout.count()).toBe(0)
    await page.keyboard.press('Space')
    expect(await readout.count()).toBe(0)
    await expect(reset).toBeFocused()
  })

  test('Zoom in keeps the focus at its limit, and Later at the end of the chart', async ({ page, baseURL }) => {
    await showChart(page, baseURL!)
    const zoomIn = page.locator('.xc-toolbar button[aria-label="Zoom in"]')
    await zoomIn.focus()
    await pressUntilOff(page, zoomIn, 'Enter')
    await expect(zoomIn).toBeFocused()
    const atLimit = await windowOf(page)
    await page.keyboard.press('Enter')
    await expect(zoomIn).toBeFocused()
    expect(await windowOf(page)).toBe(atLimit)

    const later = page.locator('.xc-toolbar button[aria-label="Later"]')
    await later.focus()
    await pressUntilOff(page, later, 'Space')
    await expect(later).toBeFocused()
    expect(await focusedLabel(page)).toBe('Later')
  })
})

test('the chart has no animation, and draws as it is with reduced motion asked for', async ({ page, baseURL, context }) => {
  await context.addInitScript(() => localStorage.setItem('nuxt-color-mode', 'light'))
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await showChart(page, baseURL!)
  await page.locator('.xc-stage').focus()
  await page.keyboard.press('ArrowRight')
  await page.getByRole('button', { name: 'Zoom in', exact: true }).click()
  // the chart's own drawing: the buttons round it have transitions of their own, which are no part of it
  const motion = await page.locator('.xc-canvas').evaluate(element => ({
    animations: element.getAnimations({ subtree: true }).length,
    smil: element.querySelectorAll('animate, animateTransform, animateMotion, set').length,
  }))
  expect(motion).toEqual({ animations: 0, smil: 0 })
  // the lines are there at once, not drawn into place
  expect((await paintOf(page)).marks.length).toBeGreaterThan(0)
})

test('a gap in the data is a gap in the line', async ({ page, baseURL, context }) => {
  await context.addInitScript(() => localStorage.setItem('nuxt-color-mode', 'light'))
  // twenty days, with the values of the 8th to the 12th missing (rows that have no value: the settings keep them with `drop_nulls` off)
  const gappy = (url: URL) => ({
    values: Array.from({ length: 20 }, (_, day) => ({
      station_id: '00011',
      resolution: 'daily',
      dataset: 'climate_summary',
      parameter: (url.searchParams.get('parameters') ?? '').split(',')[0]!.split('/')[2],
      timestamp: new Date(Date.UTC(2026, 8, day + 1)).toISOString(),
      value: day >= 7 && day <= 11 ? null : 10 + day / 2,
      quality_flags: null,
    })),
  })
  await showChart(page, baseURL!, PATH, { values: gappy })
  // the line of the series is two pieces, one move for each
  const pieces = await chartSvg(page).evaluate((svg) => {
    const line = [...svg.querySelectorAll('path')].filter(path => path.getAttribute('stroke') === '#3b82f6' && (path.getAttribute('d') ?? '').includes('L'))
    return line.map(path => ((path.getAttribute('d') ?? '').match(/M/g) ?? []).length)
  })
  expect(pieces.length).toBeGreaterThan(0)
  expect(Math.max(...pieces)).toBe(2)
  // and the readout does not pretend a value for the days of the gap: none of the points has them, the keys step over them
  await page.locator('.xc-stage').focus()
  for (let i = 0; i < 8; i++)
    await page.keyboard.press('ArrowRight')
  await expect(page.getByTestId('explorer-announce')).toHaveText(/^Sep 13, 2026: /)
})

test('rows that are missing are a gap in the line: the hours and the days with no row at all (GH-4100)', async ({ page, baseURL, context }) => {
  await context.addInitScript(() => localStorage.setItem('nuxt-color-mode', 'light'))
  // eight days of hourly values as the API answers them with the default settings: a value that is missing is no row. The hours 30 to 35 of
  // the third day and the whole of the fifth day are not in the answer
  const first = Date.UTC(2026, 8, 1)
  const missing = (hour: number) => (hour >= 30 && hour <= 35) || (hour >= 96 && hour < 120)
  const sparse = (url: URL) => ({
    values: Array.from({ length: 8 * 24 }, (_, hour) => hour).filter(hour => !missing(hour)).map(hour => ({
      station_id: '00011',
      resolution: 'hourly',
      dataset: 'temperature_air',
      parameter: (url.searchParams.get('parameters') ?? '').split(',')[0]!.split('/')[2],
      timestamp: new Date(first + hour * 3_600_000).toISOString(),
      value: 10 + 5 * Math.sin(hour / 6),
      quality_flags: null,
    })),
  })
  await showChart(page, baseURL!, '/explorer?provider=dwd&network=observation&resolution=hourly&dataset=temperature_air&parameters=temperature_air_mean_2m&mode=station&stations=00011', { values: sparse })
  // the line of the series is three pieces: a move for each, where it was one line joining the hours either side of the gaps
  const pieces = await chartSvg(page).evaluate((svg) => {
    const line = [...svg.querySelectorAll('path')].filter(path => path.getAttribute('stroke') === '#3b82f6' && (path.getAttribute('d') ?? '').includes('L'))
    return line.map(path => ((path.getAttribute('d') ?? '').match(/M/g) ?? []).length)
  })
  expect(Math.max(...pieces)).toBe(3)
  // and the readout still has what the answer has, no more: the keys step over the hours that have no row
  await page.locator('.xc-stage').focus()
  // the first press is the first hour: the 31st is the 30th, which has no row, so it is the 36th hour, 12:00 on the 2nd
  for (let i = 0; i < 31; i++)
    await page.keyboard.press('ArrowRight')
  await expect(page.getByTestId('explorer-announce')).toHaveText(/^Sep 2, 2026, 12:00/)
})

test('readings at fixed times are no gaps, and a missing reading is one: 06, 12 and 18 UTC with the 12:00 of one day missing (GH-4100)', async ({ page, baseURL, context }) => {
  await context.addInitScript(() => localStorage.setItem('nuxt-color-mode', 'light'))
  const first = Date.UTC(2026, 8, 1)
  // fifteen days of three readings, whose steps are 6, 6 and 12 hours (the 12 of the night is the usual one), the 12:00 of the 8th missing
  const readings = Array.from({ length: 15 }, (_, day) => [6, 12, 18].map(hour => ({ day, hour }))).flat().filter(({ day, hour }) => !(day === 7 && hour === 12))
  const subdaily = (url: URL) => ({
    values: readings.map(({ day, hour }) => ({
      station_id: '00011',
      resolution: 'subdaily',
      dataset: 'climate_summary',
      parameter: (url.searchParams.get('parameters') ?? '').split(',')[0]!.split('/')[2],
      timestamp: new Date(first + day * 86_400_000 + hour * 3_600_000).toISOString(),
      value: 10 + day / 2 + (hour === 12 ? 4 : 0),
      quality_flags: null,
    })),
  })
  await showChart(page, baseURL!, PATH, { values: subdaily })
  const pieces = await chartSvg(page).evaluate((svg) => {
    const line = [...svg.querySelectorAll('path')].filter(path => path.getAttribute('stroke') === '#3b82f6' && (path.getAttribute('d') ?? '').includes('L'))
    return line.map(path => ((path.getAttribute('d') ?? '').match(/M/g) ?? []).length)
  })
  // two pieces: the one missing reading, not one piece for each day
  expect(Math.max(...pieces)).toBe(2)
})

test.describe('a long series', () => {
  // ten years of hourly values of one station: 87,648 points, with a spike and a dip that a reader must still see
  const HOURS = 87_648
  const START = Date.UTC(2016, 0, 1)
  const decade = (url: URL) => ({
    values: Array.from({ length: HOURS }, (_, i) => ({
      station_id: '00011',
      resolution: 'hourly',
      dataset: 'temperature_air',
      parameter: (url.searchParams.get('parameters') ?? '').split(',')[0]!.split('/')[2],
      timestamp: new Date(START + i * 3_600_000).toISOString(),
      value: i === 40_001 ? 61.7 : i === 70_003 ? -48.3 : Math.round((10 + 12 * Math.sin(i / 24 / 365 * 2 * Math.PI * 24) + 5 * Math.sin(i / 24 * 2 * Math.PI) + (i % 7) / 10) * 10) / 10,
      quality_flags: null,
    })),
  })
  /** The span of the window the chart shows, in ms */
  const windowSpan = async (page: Page) => {
    const [start, end] = (await canvas(page).getAttribute('data-window'))!.split('/').map(Number)
    return end! - start!
  }
  const LONG = '/explorer?provider=dwd&network=observation&resolution=hourly&dataset=temperature_air&parameters=temperature_air_mean_2m&mode=station&stations=00011'

  test('is cut to what the plot can tell apart, keeps its highest and lowest value, and is drawn in a moment', async ({ page, baseURL, context }) => {
    test.setTimeout(120_000)
    await context.addInitScript(() => localStorage.setItem('nuxt-color-mode', 'light'))
    await showChart(page, baseURL!, LONG, { values: decade })
    // the draw time, from the chart code's first moment to its drawing
    const drawn = await page.evaluate(() => {
      const start = performance.getEntriesByName('explorer:draw-start').at(-1)!
      const end = performance.getEntriesByName('explorer:drawn').at(-1)!
      return end.startTime - start.startTime
    })
    expect(drawn, `the first drawing took ${Math.round(drawn)} ms`).toBeLessThan(2000)

    // what the chart draws of the series: the points of its line, and the y pixel of each value on the axis (from two of its labels)
    const drawing = () => chartSvg(page).evaluate((svg) => {
      const lines = [...svg.querySelectorAll('path')].filter(path => path.getAttribute('stroke') === '#3b82f6' && (path.getAttribute('d') ?? '').includes('L'))
      const d = lines.map(path => path.getAttribute('d') ?? '').sort((a, b) => b.length - a.length)[0] ?? ''
      const ys = [...d.matchAll(/[ML][\d.-]+ ([\d.-]+)/g)].map(match => Number(match[1]))
      // the labels of the y axis are the ones that end at the plot's left edge (the time labels are in the middle of theirs)
      const axis = [...svg.querySelectorAll('text')]
        .filter(text => text.getAttribute('text-anchor') === 'end')
        .map(text => ({ value: Number(text.textContent), y: Number(/translate\([\d.-]+ ([\d.-]+)\)/.exec(text.getAttribute('transform') ?? '')?.[1]) }))
        .filter(label => Number.isFinite(label.value) && Number.isFinite(label.y))
      return { points: ys.length, topY: Math.min(...ys), bottomY: Math.max(...ys), axis }
    })
    const yOf = (axis: { value: number, y: number }[], value: number) => {
      const [a, b] = [axis[0]!, axis.at(-1)!]
      return a.y + (value - a.value) / (b.value - a.value) * (b.y - a.y)
    }
    const whole = await drawing()
    // 87,648 points were a drawing of as many; 4 for each px of the plot (800 px) at most are now
    expect(whole.points).toBeLessThan(4 * 800)
    expect(whole.points).toBeGreaterThan(800)
    // the labels of the y axis (not the years) reach the spike and the dip, and the line reaches them: its highest point is at the spike's pixel
    expect(Math.max(...whole.axis.map(label => label.value))).toBeGreaterThanOrEqual(61.7)
    expect(Math.min(...whole.axis.map(label => label.value))).toBeLessThanOrEqual(-48.3)
    expect(Math.abs(whole.topY - yOf(whole.axis, 61.7)), 'the line reaches the spike').toBeLessThan(1.5)
    expect(Math.abs(whole.bottomY - yOf(whole.axis, -48.3)), 'the line reaches the dip').toBeLessThan(1.5)

    // zoomed to a month, the series is its own points again: one for each hour of the window, and the one beyond each edge
    const stage = page.locator('.xc-stage')
    await stage.focus()
    // at the end of the ten years, so that the spike and the dip are far out of the window
    await page.keyboard.press('End')
    for (let i = 0; i < 12; i++)
      await page.keyboard.press('+')
    await expect.poll(async () => (await windowSpan(page)) < 40 * 24 * 3_600_000).toBe(true)
    const hours = (await windowSpan(page)) / 3_600_000
    expect(hours).toBeGreaterThan(200)
    await expect.poll(async () => Math.abs((await drawing()).points - (hours + 2)), { message: `the points drawn of ${Math.round(hours)} hours` }).toBeLessThanOrEqual(3)
    // and the axis is the window's: the spike and the dip, which are out of it, are not in its range
    const zoomed = await drawing()
    expect(Math.max(...zoomed.axis.map(label => label.value))).toBeLessThan(40)
    expect(Math.min(...zoomed.axis.map(label => label.value))).toBeGreaterThan(-20)
  })

  test('has a table of every value, and the keys step through them one at a time', async ({ page, baseURL, context }) => {
    test.setTimeout(120_000)
    await context.addInitScript(() => localStorage.setItem('nuxt-color-mode', 'light'))
    await showChart(page, baseURL!, LONG, { values: decade })
    const stage = page.locator('.xc-stage')
    await stage.focus()
    await page.keyboard.press('Home')
    await expect(page.getByTestId('explorer-announce')).toHaveText(/^Jan 1, 2016, 00:00 UTC: /)
    await page.keyboard.press('ArrowRight')
    await expect(page.getByTestId('explorer-announce')).toHaveText(/^Jan 1, 2016, 01:00 UTC: /)
    await page.keyboard.press('End')
    await expect(page.getByTestId('explorer-announce')).toHaveText(/^Dec 30, 2025, 23:00 UTC: /)
  })
})

test('the explorer loads no Plotly, with the table or the chart, single or faceted', async ({ page, baseURL, context }) => {
  await context.addInitScript(() => localStorage.setItem('nuxt-color-mode', 'light'))
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
  await showChart(page, baseURL!)
  await page.getByLabel('Facet by parameter').check()
  await expect(page.locator('.xc-canvas[data-drawn="true"]')).toHaveCount(2)
  await page.waitForLoadState('networkidle')
  expect(scripts, 'the scripts the page was served').toBeGreaterThan(20)
  expect(plotly, 'a script with Plotly in it').toEqual([])
  expect(await page.locator('.js-plotly-plot').count()).toBe(0)
  expect(await page.evaluate(() => 'Plotly' in window)).toBe(false)
})

// The legend wraps, the toolbar wraps and the readout stays in the chart on a phone (WCAG 1.4.10, 1.4.4)
interface Box { left: number, top: number, right: number, bottom: number }

for (const width of [320, 390]) {
  test(`the chart, its legend, its toolbar and its readout are whole in a ${width} px window`, async ({ page, baseURL, context }) => {
    await context.addInitScript(() => localStorage.setItem('nuxt-color-mode', 'light'))
    await page.setViewportSize({ width, height: 900 })
    await showChart(page, baseURL!)
    await page.locator('.xc-stage').scrollIntoViewIfNeeded()

    const boxes = await page.locator('.explorer-chart').first().evaluate((root) => {
      const box = (element: Element) => {
        const { left, top, right, bottom } = element.getBoundingClientRect()
        return { left, top, right, bottom }
      }
      const svg = root.querySelector('.xc-canvas svg')!
      return {
        chart: box(svg),
        toolbar: box(root.querySelector('.xc-toolbar')!),
        items: [...root.querySelectorAll('.xc-legend button')].map(box),
        // the legend's texts and the labels of the axes, as drawn
        texts: [...svg.querySelectorAll('text')].map(text => ({ text: text.textContent ?? '', box: box(text) })),
      }
    })
    // The legend's two rows are laid out edge to edge (a button is a row high, the rows are a row apart: GH-4144). Firefox places boxes on
    // a grid of 1/60 px and a fractional position of the chart on the page makes those that touch cross by that much, which nobody
    // sees: only a box that is over another by more than half a px intersects it.
    const intersects = (a: Box, b: Box) => a.left < b.right - 0.5 && b.left < a.right - 0.5 && a.top < b.bottom - 0.5 && b.top < a.bottom - 0.5

    // every text is whole inside the chart
    for (const { text, box } of boxes.texts) {
      expect(box.left, `${text} at the left`).toBeGreaterThanOrEqual(boxes.chart.left - 1)
      expect(box.right, `${text} at the right`).toBeLessThanOrEqual(boxes.chart.right + 1)
    }
    // the legend wraps: its items are in the chart, and no two are over each other
    expect(boxes.items).toHaveLength(2)
    for (const item of boxes.items) {
      expect(item.left).toBeGreaterThanOrEqual(boxes.chart.left - 1)
      expect(item.right).toBeLessThanOrEqual(boxes.chart.right + 1)
    }
    expect(intersects(boxes.items[0]!, boxes.items[1]!), 'the legend items overlap').toBe(false)
    // and the toolbar is above the chart, not over its legend
    for (const item of boxes.items)
      expect(intersects(item, boxes.toolbar), 'a legend item and the toolbar').toBe(false)
    // the plot is under the legend: no label of the axes is in a legend's row
    const lowest = Math.max(...boxes.items.map(item => item.bottom))
    const ticks = boxes.texts.filter(text => /^[\d.,-]+$/.test(text.text))
    expect(ticks.length).toBeGreaterThan(2)
    for (const tick of ticks)
      expect(tick.box.top, `the label ${tick.text} is under the legend`).toBeGreaterThanOrEqual(lowest - 12)

    // WCAG 1.4.10: the page does not scroll sideways, and the chart and its toolbar stay in the window
    expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(0)
    expect(boxes.toolbar.right).toBeLessThanOrEqual(width)
    expect(boxes.chart.right).toBeLessThanOrEqual(width)

    // the readout stays inside the chart, and is closed by its button
    const stage = page.locator('.xc-stage')
    const stageBox = (await stage.boundingBox())!
    await stage.focus()
    await page.keyboard.press('End')
    const readout = page.getByTestId('explorer-readout')
    await expect(readout).toBeVisible()
    const readoutBox = (await readout.boundingBox())!
    expect(readoutBox.x).toBeGreaterThanOrEqual(stageBox.x - 1)
    expect(readoutBox.x + readoutBox.width).toBeLessThanOrEqual(stageBox.x + stageBox.width + 1)
    await readout.getByRole('button', { name: 'Close the values' }).click()
    await expect(readout).toHaveCount(0)
  })
}

test('the chart is the whole width of its column, and the page does not scroll sideways, in a 1440 px window', async ({ page, baseURL, context }) => {
  await context.addInitScript(() => localStorage.setItem('nuxt-color-mode', 'light'))
  await page.setViewportSize({ width: 1440, height: 1000 })
  await showChart(page, baseURL!)
  const box = (await page.locator('.explorer-chart').boundingBox())!
  // capped at 820 px (`.app-chart`, main.css), as the other charts are, so that it prints as large as they do
  expect(box.width).toBeLessThanOrEqual(820)
  expect(box.width).toBeGreaterThan(815)
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(0)
})
