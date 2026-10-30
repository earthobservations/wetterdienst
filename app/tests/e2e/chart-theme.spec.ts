import type { Download, Page } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { expect, test } from '@playwright/test'
import { mockBackend } from './accessibility/mock-backend'

// The Plotly charts take the colours of the page (GH-3528): their paper, plot, text, grid, axis lines and
// hover label come from the app's CSS tokens (utils/chart-theme.ts), in dark mode too, and follow a switch
// of the colour scheme without a reload. The data colours (the series, the stripes) are not the theme's.
// The API is answered by the mock backend, so the spec needs nothing but the app.

interface Chrome {
  paper: string
  plot: string
  svg: string
  text: string
  tick: string | null
  zeroline: string | null
  grid: string
  hoverBg: string
  hoverText: string
  data: string
}

type Rgb = [number, number, number]

function channels(color: string): Rgb {
  // a series' label colour is written as hex, which Plotly holds as it was given
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
/** `color` as it looks on `over`: a wash (rgba) is mixed into what lies under it, so its ratio is the one the eye has */
function onPaper(color: string, over: string): string {
  const alpha = /^rgba\(\s*\d+[\s,]+\d+[\s,]+\d+[\s,/]+([\d.]+)\s*\)$/.exec(color)?.[1]
  if (alpha === undefined || Number(alpha) >= 1)
    return color
  const [top, under] = [channels(color), channels(over)]
  return `rgb(${top.map((c, i) => Math.round(c * Number(alpha) + under[i]! * (1 - Number(alpha)))).join(', ')})`
}
function contrast(a: string, b: string) {
  a = onPaper(a, b)
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi! + 0.05) / (lo! + 0.05)
}

/** What the first drawn chart of the page has for chrome, as Plotly holds it, and how it is painted */
async function chromeOf(page: Page): Promise<Chrome> {
  return page.locator('.js-plotly-plot').first().evaluate((chart) => {
    const full = (chart as any)._fullLayout
    const svg = chart.querySelector('.main-svg') as SVGElement
    // the series' colours, which a switch of the scheme leaves as they are
    const data = JSON.stringify((chart as any).data.map((trace: any) => [trace.line?.color, trace.marker?.color, trace.marker?.colorscale]))
    return {
      paper: full.paper_bgcolor,
      plot: full.plot_bgcolor,
      svg: getComputedStyle(svg).backgroundColor,
      text: full.font.color,
      // the stripes draw no tick labels, so their axis holds no font of its own
      tick: full.xaxis.tickfont?.color ?? null,
      // a chart that draws no zero line holds no colour for it
      zeroline: full.yaxis.zerolinecolor ?? null,
      grid: full.yaxis.gridcolor,
      hoverBg: full.hoverlabel.bgcolor,
      hoverText: full.hoverlabel.font.color,
      data,
    }
  })
}

async function setColorScheme(page: Page, label: 'Light' | 'Dark') {
  await page.getByLabel('Settings', { exact: true }).click()
  await page.getByRole('button', { name: label, exact: true }).click()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog')).toHaveCount(0)
}

/** The page's own background as rgb(), through a canvas as the app resolves its tokens: the browser reports an oklch() as it was written */
async function bodyBackground(page: Page) {
  return page.evaluate(() => {
    const context = document.createElement('canvas').getContext('2d', { willReadFrequently: true })!
    context.fillStyle = getComputedStyle(document.body).backgroundColor
    context.fillRect(0, 0, 1, 1)
    const [r, g, b] = context.getImageData(0, 0, 1, 1).data
    return `rgb(${r}, ${g}, ${b})`
  })
}

const EXPLORER = '/explorer?provider=dwd&network=observation&resolution=daily&dataset=climate_summary&parameters=temperature_air_max_2m,temperature_air_mean_2m&mode=station&stations=00011'

interface Case {
  name: string
  path: string
  reach: (page: Page) => Promise<void>
  /** Whether the chart draws a zero line, which carries meaning and is held to 3:1 */
  zeroLine: boolean
  /** Whether the series keep their colours across the switch (the meteogram's wash and bands are lighter on dark) */
  seriesFixed: boolean
}

const fetchButton = (page: Page) => page.getByRole('button', { name: 'Show', exact: true })
const plotly = (page: Page) => page.locator('.js-plotly-plot .main-svg').first()

const CASES: Case[] = [
  {
    name: 'the explorer\'s chart',
    path: EXPLORER,
    zeroLine: true,
    seriesFixed: true,
    reach: async (page) => {
      await fetchButton(page).click()
      await expect(page.getByRole('table').first()).toBeVisible()
      await page.getByRole('button', { name: 'Show as chart', exact: true }).click()
      await expect(plotly(page)).toBeVisible()
    },
  },
  {
    name: 'the stripes',
    path: '/stripes?kind=temperature&station=00011',
    zeroLine: false,
    seriesFixed: true,
    reach: async (page) => {
      await fetchButton(page).click()
      await expect(plotly(page)).toBeVisible()
    },
  },
  {
    name: 'the meteogram',
    path: '/meteogram?station=01001',
    zeroLine: false,
    seriesFixed: false,
    reach: async (page) => {
      await expect(plotly(page)).toBeVisible()
    },
  },
]

for (const chart of CASES) {
  test.describe(chart.name, () => {
    test.beforeEach(async ({ context }) => {
      // the colour mode as the settings keep it, light to begin with
      await context.addInitScript(() => localStorage.setItem('nuxt-color-mode', 'light'))
    })

    test('is dark in dark mode, light in light mode, and follows a switch without a reload', async ({ page, baseURL }) => {
      const backend = await mockBackend(page, baseURL!)
      await page.goto(chart.path)
      await expect(page.locator('html')).not.toHaveClass(/dark/)
      await chart.reach(page)

      const light = await chromeOf(page)
      // the paper and the plot are the page's white, and what is painted is what Plotly holds
      expect(luminance(light.paper)).toBeGreaterThan(0.9)
      expect(light.plot).toBe(light.paper)
      expect(light.svg).toBe(light.paper)

      // no reload: a mark set on the window is still there after the switch
      await page.evaluate(() => ((window as any).__chartThemeMark = 1))
      await setColorScheme(page, 'Dark')
      await expect(page.locator('html')).toHaveClass(/dark/)
      await expect.poll(async () => (await chromeOf(page)).paper, { message: 'the chart is drawn dark' }).not.toBe(light.paper)

      const dark = await chromeOf(page)
      expect(await page.evaluate(() => (window as any).__chartThemeMark)).toBe(1)
      expect(luminance(dark.paper)).toBeLessThan(0.05)
      expect(dark.plot).toBe(dark.paper)
      expect(dark.svg).toBe(dark.paper)
      // and it is the page's own dark: the same colour as the body behind the chart
      expect(dark.paper).toBe(await bodyBackground(page))
      if (chart.seriesFixed)
        expect(dark.data).toBe(light.data)

      // WCAG 1.4.3 (text, 4.5:1) and 1.4.11 (the zero line, which carries meaning, 3:1), in both schemes
      for (const [scheme, c] of [['light', light], ['dark', dark]] as const) {
        expect(contrast(c.text, c.plot), `${scheme}: text`).toBeGreaterThanOrEqual(4.5)
        if (c.tick)
          expect(contrast(c.tick, c.plot), `${scheme}: tick labels`).toBeGreaterThanOrEqual(4.5)
        expect(contrast(c.hoverText, c.hoverBg), `${scheme}: hover label`).toBeGreaterThanOrEqual(4.5)
        if (chart.zeroLine)
          expect(contrast(c.zeroline!, c.plot), `${scheme}: zero line`).toBeGreaterThanOrEqual(3)
        // the grid is there to be seen against the plot, if faintly
        expect(c.grid, `${scheme}: grid`).not.toBe(c.plot)
      }

      // and back
      await setColorScheme(page, 'Light')
      await expect.poll(async () => (await chromeOf(page)).paper).toBe(light.paper)
      expect(backend.unanswered).toEqual([])
    })

    test('is drawn dark at once on a page that opens in dark mode', async ({ page, baseURL, context }) => {
      await context.addInitScript(() => localStorage.setItem('nuxt-color-mode', 'dark'))
      await mockBackend(page, baseURL!)
      await page.goto(chart.path)
      await expect(page.locator('html')).toHaveClass(/dark/)
      await chart.reach(page)
      const dark = await chromeOf(page)
      expect(luminance(dark.paper)).toBeLessThan(0.05)
      expect(dark.svg).toBe(dark.paper)
    })
  })
}

test('a zoomed chart of the explorer stays zoomed when the scheme switches', async ({ page, baseURL, context }) => {
  await context.addInitScript(() => localStorage.setItem('nuxt-color-mode', 'light'))
  await mockBackend(page, baseURL!)
  await page.goto(EXPLORER)
  await fetchButton(page).click()
  await expect(page.getByRole('table').first()).toBeVisible()
  await page.getByRole('button', { name: 'Show as chart', exact: true }).click()
  await expect(plotly(page)).toBeVisible()

  const range = () => page.locator('.js-plotly-plot').first().evaluate(chart => (chart as any)._fullLayout.xaxis.range as string[])
  const full = await range()
  // a box drawn on the plot zooms it in
  const area = page.locator('.js-plotly-plot .nsewdrag').first()
  await area.scrollIntoViewIfNeeded()
  const drag = (await area.boundingBox())!
  await page.mouse.move(drag.x + drag.width * 0.3, drag.y + drag.height * 0.5)
  await page.mouse.down()
  await page.mouse.move(drag.x + drag.width * 0.6, drag.y + drag.height * 0.5, { steps: 5 })
  await page.mouse.up()
  await expect.poll(range).not.toEqual(full)
  const zoomed = await range()

  await setColorScheme(page, 'Dark')
  await expect.poll(async () => luminance((await chromeOf(page)).paper)).toBeLessThan(0.05)
  expect(await range()).toEqual(zoomed)
})

test('the focus ring of a modebar button is the page\'s own, 3:1 on the dark paper (WCAG 1.4.11)', async ({ page, baseURL, context }) => {
  // Plotly's own is a black outline: 21:1 on white, 1.2:1 on the dark paper
  await context.addInitScript(() => localStorage.setItem('nuxt-color-mode', 'dark'))
  await mockBackend(page, baseURL!)
  await page.goto('/stripes?kind=temperature&station=00011')
  await fetchButton(page).click()
  await expect(plotly(page)).toBeVisible()

  const button = page.locator('.js-plotly-plot .modebar-btn[data-attr="zoom"][data-val="reset"]')
  await button.focus()
  await page.keyboard.press('Shift+Tab')
  await page.keyboard.press('Tab')
  await expect(button).toBeFocused()
  const ring = await button.evaluate((element) => {
    const style = getComputedStyle(element)
    const context = document.createElement('canvas').getContext('2d', { willReadFrequently: true })!
    context.fillStyle = style.outlineColor
    context.fillRect(0, 0, 1, 1)
    const [r, g, b] = context.getImageData(0, 0, 1, 1).data
    return { color: `rgb(${r}, ${g}, ${b})`, width: Number.parseFloat(style.outlineWidth) }
  })
  expect(ring.width).toBeGreaterThanOrEqual(2)
  expect(contrast(ring.color, (await chromeOf(page)).paper)).toBeGreaterThanOrEqual(3)
})

/** Every Plotly chart of the page: its paper, as Plotly holds it */
const papers = (page: Page) => page.locator('.js-plotly-plot').evaluateAll(charts => charts.map(chart => (chart as any)._fullLayout.paper_bgcolor as string))

async function openExplorerChart(page: Page, baseURL: string) {
  await mockBackend(page, baseURL)
  await page.goto(EXPLORER)
  await fetchButton(page).click()
  await expect(page.getByRole('table').first()).toBeVisible()
  await page.getByRole('button', { name: 'Show as chart', exact: true }).click()
  await expect(plotly(page)).toBeVisible()
}

test('both charts of a faceted Explorer follow the scheme', async ({ page, baseURL, context }) => {
  await context.addInitScript(() => localStorage.setItem('nuxt-color-mode', 'light'))
  await openExplorerChart(page, baseURL!)
  await page.getByLabel('Facet by parameter').check()
  await expect(page.locator('.js-plotly-plot')).toHaveCount(2)
  await expect(plotly(page)).toBeVisible()

  const light = await papers(page)
  expect(light.map(luminance).every(l => l > 0.9)).toBe(true)
  await setColorScheme(page, 'Dark')
  await expect.poll(async () => (await papers(page)).map(luminance).every(l => l < 0.05), { message: 'both facets are drawn dark' }).toBe(true)
  await setColorScheme(page, 'Light')
  await expect.poll(() => papers(page)).toEqual(light)
})

// A chart that is saved or printed is the light one, whatever the screen shows, so that images in a report
// or a slide look alike (the maintainers' decision, GH-3528). A saved image is drawn again off screen in the
// light theme; the chart on the page stays as it is.

/** The pixel at the top left of a downloaded PNG or JPEG: the paper, which is the margin of every chart */
async function cornerOf(page: Page, download: Download): Promise<string> {
  const file = await download.path()
  const base64 = readFileSync(file).toString('base64')
  return page.evaluate(async (data) => {
    const image = await createImageBitmap(new Blob([Uint8Array.from(atob(data), c => c.charCodeAt(0))]))
    const canvas = document.createElement('canvas')
    canvas.width = image.width
    canvas.height = image.height
    const context = canvas.getContext('2d', { willReadFrequently: true })!
    context.drawImage(image, 0, 0)
    const [r, g, b] = context.getImageData(2, 2, 1, 1).data
    return `rgb(${r}, ${g}, ${b})`
  }, base64)
}

async function expectLight(page: Page, download: Download) {
  const corner = await cornerOf(page, download)
  expect(luminance(corner), `the saved image is light (its corner is ${corner})`).toBeGreaterThan(0.9)
  // the chart on the page is as dark as it was, and the copy that was drawn for the image is gone
  expect(luminance((await papers(page))[0]!)).toBeLessThan(0.05)
  await expect(page.locator('.js-plotly-plot[aria-hidden="true"]')).toHaveCount(0)
}

test.describe('a saved chart is the light one', () => {
  test.beforeEach(async ({ context }) => {
    await context.addInitScript(() => localStorage.setItem('nuxt-color-mode', 'dark'))
  })

  test('the Explorer\'s download menu and the camera of its modebar, single and faceted', async ({ page, baseURL }) => {
    await openExplorerChart(page, baseURL!)
    expect(luminance((await papers(page))[0]!)).toBeLessThan(0.05)

    const menu = async (format: string) => {
      await page.getByRole('button', { name: 'Download chart' }).click()
      const saved = page.waitForEvent('download')
      await page.getByRole('menuitem', { name: format, exact: true }).click()
      return saved
    }
    await expectLight(page, await menu('PNG'))
    await expectLight(page, await menu('JPEG'))

    // the camera is Plotly's own icon and name, and saves the same
    const camera = page.locator('.js-plotly-plot .modebar-btn[aria-label="Download plot as a PNG"]')
    await expect(camera).toHaveCount(1)
    const saved = page.waitForEvent('download')
    await camera.click()
    await expectLight(page, await saved)

    // faceted: the charts are stacked into one image, each drawn light
    await page.getByLabel('Facet by parameter').check()
    await expect(page.locator('.js-plotly-plot')).toHaveCount(2)
    await expectLight(page, await menu('PNG'))
  })

  test('the stripes\' download menu and the camera of its modebar', async ({ page, baseURL }) => {
    await mockBackend(page, baseURL!)
    await page.goto('/stripes?kind=temperature&station=00011')
    await fetchButton(page).click()
    await expect(plotly(page)).toBeVisible()

    await page.getByRole('button', { name: 'Download image' }).click()
    const menuSaved = page.waitForEvent('download')
    await page.getByRole('menuitem', { name: 'Download as PNG' }).click()
    await expectLight(page, await menuSaved)

    const camera = page.locator('.js-plotly-plot .modebar-btn[aria-label="Download plot as a PNG"]')
    await expect(camera).toHaveCount(1)
    const saved = page.waitForEvent('download')
    await camera.click()
    await expectLight(page, await saved)
  })
})

// printing: the charts are drawn light for as long as the page is printed, and a print that comes before they
// are has a transparent paper and dark text (main.css)
for (const chart of CASES) {
  test(`${chart.name} is light when printed, dark again after`, async ({ page, baseURL, context }) => {
    await context.addInitScript(() => localStorage.setItem('nuxt-color-mode', 'dark'))
    await mockBackend(page, baseURL!)
    await page.goto(chart.path)
    await chart.reach(page)
    await expect.poll(async () => luminance((await chromeOf(page)).paper)).toBeLessThan(0.05)

    await page.emulateMedia({ media: 'print' })
    await expect.poll(async () => luminance((await chromeOf(page)).paper), { message: 'drawn light for the print' }).toBeGreaterThan(0.9)
    // and it says so, which is what the print rules of main.css leave a chart alone by
    await expect(page.locator('.js-plotly-plot').first()).toHaveAttribute('data-chart-scheme', 'light')

    await page.emulateMedia({ media: 'screen' })
    await expect.poll(async () => luminance((await chromeOf(page)).paper)).toBeLessThan(0.05)
    await expect(page.locator('.js-plotly-plot').first()).toHaveAttribute('data-chart-scheme', 'dark')
  })

  test(`${chart.name} is not drawn again where a page that is light is printed`, async ({ page, baseURL, context }) => {
    await context.addInitScript(() => localStorage.setItem('nuxt-color-mode', 'light'))
    await mockBackend(page, baseURL!)
    await page.goto(chart.path)
    await chart.reach(page)
    await expect.poll(async () => luminance((await chromeOf(page)).paper)).toBeGreaterThan(0.9)
    // every drawing of Plotly, a redraw or a restyle, ends in this event
    const chartElement = page.locator('.js-plotly-plot').first()
    await chartElement.evaluate((element) => {
      ;(window as any).__afterplot = 0
      ;(element as any).on('plotly_afterplot', () => (window as any).__afterplot++)
    })
    await page.emulateMedia({ media: 'print' })
    await page.evaluate(() => window.dispatchEvent(new Event('beforeprint')))
    await page.waitForTimeout(1000)
    await page.evaluate(() => window.dispatchEvent(new Event('afterprint')))
    await page.emulateMedia({ media: 'screen' })
    await page.waitForTimeout(500)
    expect(await page.evaluate(() => (window as any).__afterplot), 'drawings while it was printed').toBe(0)
  })
}

test('the print rules make a chart that is still dark readable, and leave one drawn light as it is', async ({ page, baseURL }) => {
  // the redraw for a print is asynchronous for some charts, so a print that comes before it is made readable by
  // main.css, for the charts that say they are drawn dark; the rules are tried on stand-ins for the charts' parts
  await mockBackend(page, baseURL!)
  await page.goto('/')
  await page.evaluate(() => {
    for (const scheme of ['dark', 'light']) {
      const chart = document.createElement('div')
      chart.className = 'js-plotly-plot'
      chart.id = `chart-${scheme}`
      chart.dataset.chartScheme = scheme
      chart.innerHTML = '<svg class="main-svg" style="background: rgb(15, 23, 43)"><text style="fill: rgb(226, 232, 240)">Mo</text></svg><canvas class="meteogram-overlay-canvas"></canvas>'
      document.body.appendChild(chart)
    }
  })
  await page.emulateMedia({ media: 'print' })
  const styleOf = (scheme: string) => page.evaluate((id) => {
    const chart = document.getElementById(id)!
    return {
      background: getComputedStyle(chart.querySelector('.main-svg')!).backgroundColor,
      text: getComputedStyle(chart.querySelector('text')!).fill,
      barbs: getComputedStyle(chart.querySelector('.meteogram-overlay-canvas')!).filter,
    }
  }, `chart-${scheme}`)
  expect(await styleOf('dark')).toEqual({ background: 'rgba(0, 0, 0, 0)', text: 'rgb(0, 0, 0)', barbs: 'invert(1)' })
  expect(await styleOf('light')).toEqual({ background: 'rgb(15, 23, 43)', text: 'rgb(226, 232, 240)', barbs: 'none' })
})

test('zoomed stripes stay zoomed where the scheme switches or the page is printed, and are saved as shown', async ({ page, baseURL, context }) => {
  await context.addInitScript(() => localStorage.setItem('nuxt-color-mode', 'light'))
  await mockBackend(page, baseURL!)
  await page.goto('/stripes?kind=temperature&station=00011')
  await fetchButton(page).click()
  await expect(plotly(page)).toBeVisible()

  const range = () => page.locator('.js-plotly-plot').first().evaluate(chart => (chart as any)._fullLayout.xaxis.range as number[])
  const full = await range()
  const area = page.locator('.js-plotly-plot .nsewdrag').first()
  await area.scrollIntoViewIfNeeded()
  const box = (await area.boundingBox())!
  await page.mouse.move(box.x + box.width * 0.3, box.y + box.height * 0.5)
  await page.mouse.down()
  await page.mouse.move(box.x + box.width * 0.6, box.y + box.height * 0.5, { steps: 5 })
  await page.mouse.up()
  await expect.poll(range).not.toEqual(full)
  const zoomed = await range()
  const initial = () => page.locator('.js-plotly-plot').first().evaluate(chart => [(chart as any)._fullLayout.xaxis._rangeInitial0, (chart as any)._fullLayout.xaxis._rangeInitial1] as number[])
  expect(await initial(), 'the range a reset goes back to is the full one').toEqual(full)

  // the scheme switched: drawn again, in the range it was in
  await setColorScheme(page, 'Dark')
  await expect.poll(async () => luminance((await chromeOf(page)).paper)).toBeLessThan(0.05)
  expect(await range()).toEqual(zoomed)
  // and a reset still goes back to the full view, not to the zoom the chart was redrawn at
  expect(await initial()).toEqual(full)
  // printed: light, and in that range still
  await page.emulateMedia({ media: 'print' })
  await expect.poll(async () => luminance((await chromeOf(page)).paper)).toBeGreaterThan(0.9)
  expect(await range()).toEqual(zoomed)
  await page.emulateMedia({ media: 'screen' })
  await expect.poll(async () => luminance((await chromeOf(page)).paper)).toBeLessThan(0.05)
  expect(await range()).toEqual(zoomed)
})

test('a zoomed Forecast stays zoomed where the scheme switches, and its reset still goes back to the full view', async ({ page, baseURL, context }) => {
  await context.addInitScript(() => localStorage.setItem('nuxt-color-mode', 'light'))
  await mockBackend(page, baseURL!)
  await page.goto('/meteogram?station=01001')
  await expect(plotly(page)).toBeVisible()

  const axis = () => page.locator('.js-plotly-plot').first().evaluate((chart) => {
    const xaxis = (chart as any)._fullLayout.xaxis
    return { range: xaxis.range as string[], initial: [xaxis._rangeInitial0, xaxis._rangeInitial1] }
  })
  const full = await axis()
  const area = page.locator('.js-plotly-plot .nsewdrag').first()
  await area.scrollIntoViewIfNeeded()
  const box = (await area.boundingBox())!
  await page.mouse.move(box.x + box.width * 0.3, box.y + box.height * 0.5)
  await page.mouse.down()
  await page.mouse.move(box.x + box.width * 0.6, box.y + box.height * 0.5, { steps: 5 })
  await page.mouse.up()
  await expect.poll(async () => (await axis()).range).not.toEqual(full.range)
  const zoomed = (await axis()).range

  await setColorScheme(page, 'Dark')
  await expect.poll(async () => luminance((await chromeOf(page)).paper)).toBeLessThan(0.05)
  await expect.poll(async () => (await axis()).range).toEqual(zoomed)
  expect((await axis()).initial, 'the range a reset goes back to is the full one').toEqual(full.initial)
})

// The text that names a series (GH-3618): the Forecast's y axes, as its temperature axis, its weekend day labels,
// and its zero line, which carries meaning, are read on the paper in both schemes. The series keep their colours.
test('the Forecast\'s axis labels, weekend day labels and zero line reach contrast in both schemes', async ({ page, baseURL, context }) => {
  await context.addInitScript(() => localStorage.setItem('nuxt-color-mode', 'light'))
  // a Friday, so that the days of the forecast (it runs three days from now) hold a weekend whenever this runs
  await page.clock.setSystemTime(new Date('2026-10-30T09:00:00Z'))
  await mockBackend(page, baseURL!)
  await page.goto('/meteogram?station=01001')
  await expect(plotly(page)).toBeVisible()

  const labels = () => page.locator('.js-plotly-plot').first().evaluate((chart) => {
    const full = (chart as any)._fullLayout
    const axes = Object.keys(full)
      .filter(key => /^yaxis\d*$/.test(key) && full[key].visible)
      .map(key => ({
        axis: key,
        title: full[key].title?.font?.color as string | undefined,
        tick: full[key].tickfont?.color as string | undefined,
        zeroline: full[key].zeroline ? full[key].zerolinecolor as string : null,
      }))
    const days = (full.annotations as { text: string, font: { color: string } }[])
      .filter(annotation => annotation.text.startsWith('<b>'))
      .map(annotation => ({ text: annotation.text, color: annotation.font.color }))
    return { paper: full.paper_bgcolor as string, text: full.font.color as string, axes, days }
  })

  for (const scheme of ['light', 'dark'] as const) {
    if (scheme === 'dark') {
      await setColorScheme(page, 'Dark')
      await expect.poll(async () => luminance((await labels()).paper)).toBeLessThan(0.05)
    }
    const { paper, axes, days } = await labels()
    // the four series' axes and the temperature axis, which has the zero line
    expect(axes.length, `${scheme}: the axes drawn`).toBeGreaterThanOrEqual(4)
    for (const axis of axes) {
      expect(contrast(axis.title!, paper), `${scheme}: ${axis.axis} title ${axis.title}`).toBeGreaterThanOrEqual(4.5)
      expect(contrast(axis.tick!, paper), `${scheme}: ${axis.axis} tick labels ${axis.tick}`).toBeGreaterThanOrEqual(4.5)
    }
    const zero = axes.filter(axis => axis.zeroline)
    expect(zero.length, `${scheme}: the axis with a zero line`).toBe(1)
    expect(contrast(zero[0]!.zeroline!, paper), `${scheme}: zero line ${zero[0]!.zeroline}`).toBeGreaterThanOrEqual(3)
    // the weekend's labels are in a colour of their own (the Saturday and the Sunday of the three days)
    const weekend = days.filter(day => /^<b>(?:Sat|Sun)/.test(day.text))
    expect(weekend.length, `${scheme}: the weekend's labels ${JSON.stringify(days)}`).toBeGreaterThanOrEqual(1)
    for (const day of days)
      expect(contrast(day.color, paper), `${scheme}: ${day.text} ${day.color}`).toBeGreaterThanOrEqual(4.5)
  }
})

test('the stripes\' "data availability" label reaches contrast in both schemes', async ({ page, baseURL, context }) => {
  await context.addInitScript(() => localStorage.setItem('nuxt-color-mode', 'light'))
  await mockBackend(page, baseURL!)
  await page.goto('/stripes?kind=temperature&station=00011&show_data_availability=true')
  await fetchButton(page).click()
  await expect(plotly(page)).toBeVisible()

  const label = () => page.locator('.js-plotly-plot').first().evaluate((chart) => {
    const full = (chart as any)._fullLayout
    const annotation = (full.annotations as { text: string, font: { color: string } }[]).find(a => a.text === 'Data availability')
    return { paper: full.paper_bgcolor as string, color: annotation?.font.color }
  })
  for (const scheme of ['light', 'dark'] as const) {
    if (scheme === 'dark') {
      await setColorScheme(page, 'Dark')
      await expect.poll(async () => luminance((await label()).paper)).toBeLessThan(0.05)
    }
    const { paper, color } = await label()
    expect(color, `${scheme}: the label is drawn`).toBeTruthy()
    expect(contrast(color!, paper), `${scheme}: ${color}`).toBeGreaterThanOrEqual(4.5)
  }
})

// The widget's ?theme= is the widget's alone (GH-3619): the colour-mode module saves a preference to localStorage,
// which the app reads on the same origin
test.describe('the widget\'s theme', () => {
  const saved = (page: Page) => page.evaluate(() => localStorage.getItem('nuxt-color-mode'))

  for (const [chosen, widgetTheme] of [['light', 'dark'], ['dark', 'light']] as const) {
    test(`?theme=${widgetTheme} leaves the saved ${chosen} scheme of the app as it is`, async ({ page, baseURL, context }) => {
      // set once, before the first page of the test: the widget must not be what changes it
      await context.addInitScript((mode) => {
        if (!sessionStorage.getItem('seeded')) {
          sessionStorage.setItem('seeded', '1')
          localStorage.setItem('nuxt-color-mode', mode)
        }
      }, chosen)
      await mockBackend(page, baseURL!)
      await page.goto('/')
      await expect(page.locator('html')).toHaveClass(chosen === 'dark' ? /dark/ : /^(?!.*dark)/)

      await page.goto(`/widget?station=01001&theme=${widgetTheme}`)
      await expect(plotly(page)).toBeVisible()
      await expect(page.locator('html')).toHaveClass(widgetTheme === 'dark' ? /dark/ : /^(?!.*dark)/)
      // the chart is drawn in the widget's scheme
      expect(luminance((await chromeOf(page)).paper) < 0.05).toBe(widgetTheme === 'dark')
      expect(await saved(page)).toBe(chosen)

      // the app, opened after the widget, is in the scheme it was saved in
      await page.goto('/')
      await expect(page.locator('html')).toHaveClass(chosen === 'dark' ? /dark/ : /^(?!.*dark)/)
      expect(await saved(page)).toBe(chosen)
    })
  }
})
