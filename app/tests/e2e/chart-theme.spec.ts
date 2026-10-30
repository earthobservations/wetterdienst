import type { Page } from '@playwright/test'
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
