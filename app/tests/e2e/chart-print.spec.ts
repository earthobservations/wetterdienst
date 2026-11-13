import type { Page } from '@playwright/test'
import { expect, test } from '@playwright/test'
import { mockBackend } from './accessibility/mock-backend'
import { pdfTextRuns } from './pdf-text'

// The charts on paper (GH-3558, GH-3518). A printed chart is scaled to the printable width of the sheet, so the type
// that is 11 px on the screen is as small on paper as the chart is wide on the screen: the three charts (the forecast's
// meteogram, the Explorer's chart and the climate stripes) are capped at 820 px (`.app-chart`, main.css).
// This measures the size of the chart's text in the PDF Chromium prints (`page.pdf`, which only Chromium has: the
// playwright config runs this spec in a Chromium project), on A4 and Letter with 0.4 in and 1 in margins, rather than
// estimating it from the zoom. The API is answered by the mock backend, so the spec needs nothing but the app.

const EXPLORER = '/explorer?provider=dwd&network=observation&resolution=daily&dataset=climate_summary&parameters=temperature_air_max_2m,temperature_air_mean_2m&mode=station&stations=00011'

/** The widest a chart is drawn (`.app-chart` in main.css) */
const MAX_WIDTH = 820

const plotly = (page: Page) => page.locator('.js-plotly-plot .main-svg').first()

interface Chart {
  name: string
  path: string
  reach: (page: Page) => Promise<void>
  /**
   * The smallest type of the chart on paper in points, on every sheet below and from every window: what it measures
   * today (6.24 pt or more on A4 with 1 in margins, which is 12 px at the scale of 0.7) less a margin, so that a
   * change that shrinks the print (a chart that is wider on the screen again, a font under 12 px) fails here
   */
  floor: number
}

const CHARTS: Chart[] = [
  {
    name: 'the explorer\'s chart',
    path: EXPLORER,
    // the tick labels, 12 px (5.2 pt from a 1100 px window without the cap)
    floor: 6.2,
    reach: async (page) => {
      await page.getByRole('button', { name: 'Show', exact: true }).click()
      await expect(page.getByRole('table').first()).toBeVisible()
      await page.getByRole('button', { name: 'Show as chart', exact: true }).click()
      await expect(plotly(page)).toBeVisible()
    },
  },
  {
    name: 'the climate stripes',
    path: '/stripes?kind=temperature&station=00011',
    // "Data availability" is the smallest, 12 px since GH-3558 (11 px before: 5.7 pt, and 4.8 pt without the cap)
    floor: 6.2,
    reach: async (page) => {
      await page.getByRole('button', { name: 'Show', exact: true }).click()
      await expect(plotly(page)).toBeVisible()
    },
  },
]

/** The forecast's chart: ECharts, drawn as SVG into `.mg-canvas`, and scaled to the sheet like a picture when it is printed */
const FORECAST: Pick<Chart, 'name' | 'path' | 'reach'> & { floor: number } = {
  name: 'the forecast\'s meteogram',
  path: '/meteogram?station=01001',
  // the ticks and axis titles are 12 px of a chart of at most 820 px
  floor: 6.2,
  reach: async (page) => {
    await expect(page.locator('.mg-canvas svg').first()).toBeVisible()
  },
}

const SHEETS = [
  { format: 'A4', margin: '0.4in' },
  { format: 'A4', margin: '1in' },
  { format: 'Letter', margin: '0.4in' },
  { format: 'Letter', margin: '1in' },
] as const

/** Every piece of text the charts of the page draw: their tick labels, titles, legend and annotations, one string per line */
async function chartTexts(page: Page): Promise<string[]> {
  const texts = await page.locator('.js-plotly-plot').evaluateAll((charts) => {
    const found = new Set<string>()
    for (const text of charts.flatMap(chart => [...chart.querySelectorAll('svg.main-svg text')])) {
      const lines = text.querySelectorAll('tspan')
      for (const part of lines.length ? lines : [text]) {
        const value = part.textContent?.trim()
        if (value)
          found.add(value)
      }
    }
    return [...found]
  })
  return texts
}

/**
 * The texts of the forecast's chart that the PDF reader of this spec finds once the picture is scaled to the sheet: the day
 * names and the hours, which are 12 px like every other text of the chart. (The axes' numbers and their rotated titles are
 * 12 px as well, and are not found in a scaled print by `pdf-text.ts`, which reads one run for each piece of text.)
 */
async function forecastTexts(page: Page): Promise<string[]> {
  const texts = await page.locator('.mg-canvas svg text').evaluateAll(texts => [...new Set(texts.map(text => text.textContent?.trim()).filter((value): value is string => !!value))])
  return texts.filter(text => /^(?:[A-Z][a-z]{2}(?: \d{2}\/\d{2})?|\d{2}:\d{2})$/.test(text))
}

/** Prints the page on every sheet and holds the smallest of `texts` to `floor` points (and finds every one of them) */
async function expectPrintedAtLeast(page: Page, texts: string[], floor: number) {
  for (const sheet of SHEETS) {
    const margin = { top: sheet.margin, right: sheet.margin, bottom: sheet.margin, left: sheet.margin }
    const sizes = new Map<string, number>()
    for (const run of pdfTextRuns(await page.pdf({ format: sheet.format, margin }))) {
      // a string the chart draws that is also drawn elsewhere on the page counts at its smallest
      const text = run.text.trim()
      if (texts.includes(text))
        sizes.set(text, Math.min(sizes.get(text) ?? Infinity, run.size))
    }
    // every string of the chart is in the PDF (a string that is not is a measurement that missed it)
    expect(texts.filter(text => !sizes.has(text)), `${sheet.format} ${sheet.margin}: not in the PDF`).toEqual([])
    const [text, size] = [...sizes.entries()].sort((a, b) => a[1] - b[1])[0]!
    expect(size, `${sheet.format} ${sheet.margin}: ${JSON.stringify(text)} in points`).toBeGreaterThanOrEqual(floor)
  }
}

for (const chart of CHARTS) {
  test.describe(chart.name, () => {
    test.beforeEach(async ({ context }) => {
      await context.addInitScript(() => localStorage.setItem('nuxt-color-mode', 'light'))
    })

    // the cap, and the page that carries the chart: nothing is pushed out of the window
    for (const width of [1100, 1440, 1920, 2560]) {
      test(`is at most ${MAX_WIDTH} px wide in a ${width} px window, and the page does not overflow`, async ({ page, baseURL }) => {
        await page.setViewportSize({ width, height: 1080 })
        await mockBackend(page, baseURL!)
        await page.goto(chart.path)
        await chart.reach(page)
        const box = await page.locator('.js-plotly-plot').first().boundingBox()
        expect(box!.width).toBeLessThanOrEqual(MAX_WIDTH)
        // wide enough to be a chart still, in the narrowest of the windows (the column there is 980 px)
        expect(box!.width).toBeGreaterThan(MAX_WIDTH - 5)
        expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(0)
      })
    }

    // from the narrowest window with a column wider than the cap and from a wide one: the print is the same
    for (const width of [1100, 1920]) {
      test(`prints its text at a size that is read on paper, from a ${width} px window`, async ({ page, baseURL, browserName }) => {
        test.skip(browserName !== 'chromium', 'page.pdf is Chromium\'s')
        await page.setViewportSize({ width, height: 1080 })
        await mockBackend(page, baseURL!)
        await page.goto(chart.path)
        await chart.reach(page)
        const texts = await chartTexts(page)
        expect(texts.length).toBeGreaterThan(0)

        await expectPrintedAtLeast(page, texts, chart.floor)
      })
    }
  })
}

test.describe(FORECAST.name, () => {
  test.beforeEach(async ({ context }) => {
    await context.addInitScript(() => localStorage.setItem('nuxt-color-mode', 'light'))
  })

  for (const width of [1100, 1440, 1920, 2560]) {
    test(`is at most ${MAX_WIDTH} px wide in a ${width} px window, and the page does not overflow`, async ({ page, baseURL }) => {
      await page.setViewportSize({ width, height: 1080 })
      await mockBackend(page, baseURL!)
      await page.goto(FORECAST.path)
      await FORECAST.reach(page)
      const box = await page.locator('.meteogram-chart').first().boundingBox()
      expect(box!.width).toBeLessThanOrEqual(MAX_WIDTH)
      expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(0)
    })
  }

  for (const width of [1100, 1920]) {
    test(`prints its text at a size that is read on paper, from a ${width} px window`, async ({ page, baseURL, browserName }) => {
      test.skip(browserName !== 'chromium', 'page.pdf is Chromium\'s')
      await page.setViewportSize({ width, height: 1080 })
      await mockBackend(page, baseURL!)
      await page.goto(FORECAST.path)
      await FORECAST.reach(page)
      const texts = await forecastTexts(page)
      expect(texts.length).toBeGreaterThan(0)

      await expectPrintedAtLeast(page, texts, FORECAST.floor)
    })
  }
})

test('the explorer\'s faceted charts are capped as well, and print as large as the single one', async ({ page, baseURL, browserName }) => {
  await page.setViewportSize({ width: 1920, height: 1080 })
  await mockBackend(page, baseURL!)
  await page.goto(EXPLORER)
  await CHARTS[0]!.reach(page)
  await page.getByLabel('Facet by parameter').check()
  await expect(page.locator('.js-plotly-plot')).toHaveCount(2)
  for (const chart of await page.locator('.js-plotly-plot').all())
    expect((await chart.boundingBox())!.width).toBeLessThanOrEqual(MAX_WIDTH - 34)
  // the box of a facet has 34 px of padding and border, which the print is scaled with: the chart is narrower by them
  test.skip(browserName !== 'chromium', 'page.pdf is Chromium\'s')
  await expectPrintedAtLeast(page, await chartTexts(page), CHARTS[0]!.floor)
})

// A page printed from the dark theme is the light page (#3615 made the charts light; the rest of the page was pale
// text on white paper): what an element prints in, as the print medium computes it, is the same in both themes
async function printedStyles(page: Page, baseURL: string, theme: 'light' | 'dark', chart: Pick<Chart, 'path' | 'reach'>) {
  await page.addInitScript(mode => localStorage.setItem('nuxt-color-mode', mode), theme)
  await page.setViewportSize({ width: 1440, height: 1000 })
  await mockBackend(page, baseURL)
  await page.goto(chart.path)
  await chart.reach(page)
  await page.emulateMedia({ media: 'print' })
  // the charts are drawn light for the print, which takes a drawing for some of them
  if (await page.locator('.js-plotly-plot').count())
    await expect(page.locator('.js-plotly-plot').first()).toHaveAttribute('data-chart-scheme', 'light')
  if (await page.locator('.mg-canvas').count())
    await expect(page.locator('.mg-canvas').first()).toHaveAttribute('data-chart-scheme', 'light')
  // the semantic colours (an alert, a badge, a link): probes that wear them, where the page has no such state to reach
  await page.evaluate(() => {
    const probes = document.createElement('div')
    probes.innerHTML = ['text-primary', 'text-secondary', 'text-success', 'text-info', 'text-warning', 'text-error', 'bg-warning', 'bg-error', 'text-muted', 'border-default']
      .map(name => `<span class="${name}" style="border: 1px solid">${name}</span>`)
      .join('')
    document.querySelector('#__nuxt')!.append(probes)
  })
  // and the colours of the page, which the buttons and links transition to (a style read before is a mix of both)
  await page.evaluate(() => Promise.all(document.getAnimations().map(animation => animation.finished.catch(() => {}))))
  return page.evaluate(() => {
    const styles: Record<string, string> = {}
    const walk = (element: Element, path: string) => {
      const style = getComputedStyle(element)
      const box = element.getBoundingClientRect()
      // a chart's own drawing, a map and a hidden element are not the page's chrome
      if (style.display === 'none' || element.matches('svg, .leaflet-container, .js-plotly-plot'))
        return
      if (box.width > 1 && box.height > 1)
        styles[path] = [style.color, style.backgroundColor, style.borderTopColor, style.outlineColor].join(' ')
      let index = 0
      for (const child of element.children)
        walk(child, `${path}/${child.tagName.toLowerCase()}${++index}`)
    }
    // the app's own page: what Nuxt and the toaster append to the body, in an order that depends on the timing, is not
    walk(document.querySelector('#__nuxt')!, 'app')
    return styles
  })
}

for (const chart of [...CHARTS, FORECAST, { name: 'the home page', path: '/', reach: async (page: Page) => page.waitForLoadState('networkidle') }] as Pick<Chart, 'name' | 'path' | 'reach'>[]) {
  test(`${chart.name} prints the same from the dark theme as from the light one`, async ({ browser, baseURL }) => {
    const light = await printedStyles(await (await browser.newContext()).newPage(), baseURL!, 'light', chart)
    const dark = await printedStyles(await (await browser.newContext()).newPage(), baseURL!, 'dark', chart)
    expect(Object.keys(light).length, 'elements compared').toBeGreaterThan(50)
    expect(Object.keys(dark)).toEqual(Object.keys(light))
    expect(Object.entries(dark).filter(([path, style]) => style !== light[path]).map(([path, style]) => `${path}: ${light[path]} -> ${style}`)).toEqual([])
  })
}
