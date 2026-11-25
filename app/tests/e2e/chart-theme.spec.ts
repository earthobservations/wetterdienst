import type { Locator, Page } from '@playwright/test'
import { expect, test } from '@playwright/test'
import { mockBackend } from './accessibility/mock-backend'

// The colours of the page in the charts of the app (GH-3528): the forecast's chart and the widget's, and the focus ring of the
// controls of the Explorer's chart, in dark mode too. The Explorer's own chart (ECharts, GH-4096) has its colours held in
// explorer-chart.spec.ts, the stripes' in stripes-chart.spec.ts and the forecast's in meteogram-chart.spec.ts, where the series
// and the stripes are data and the chrome is the theme's. The API is answered by the mock backend, so the spec needs nothing but
// the app.

type Rgb = [number, number, number]

function channels(color: string): Rgb {
  // a series' label colour is written as hex
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

async function setColorScheme(page: Page, label: 'Light' | 'Dark') {
  await page.getByLabel('Settings', { exact: true }).click()
  await page.getByRole('button', { name: label, exact: true }).click()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog')).toHaveCount(0)
}

/**
 * The colour behind the chart as rgb(): the first opaque background from the chart outwards (its card, in the design
 * of GH-3518, where the body is the page's canvas), through a canvas as the app resolves its tokens: the browser
 * reports an oklch() as it was written
 */
async function behindChart(page: Page) {
  return page.evaluate(() => {
    const context = document.createElement('canvas').getContext('2d', { willReadFrequently: true })!
    const rgb = (color: string) => {
      context.clearRect(0, 0, 1, 1)
      context.fillStyle = color
      context.fillRect(0, 0, 1, 1)
      const [r, g, b, a] = context.getImageData(0, 0, 1, 1).data
      return { text: `rgb(${r}, ${g}, ${b})`, opaque: a === 255 }
    }
    let element: Element | null = document.querySelector('.xc-canvas, .mg-canvas')?.parentElement ?? document.body
    while (element) {
      const found = rgb(getComputedStyle(element).backgroundColor)
      if (found.opaque)
        return found.text
      element = element.parentElement
    }
    return rgb(getComputedStyle(document.body).backgroundColor).text
  })
}

const EXPLORER = '/explorer?provider=dwd&network=observation&resolution=daily&dataset=climate_summary&parameters=temperature_air_max_2m,temperature_air_mean_2m&mode=station&stations=00011'

const fetchButton = (page: Page) => page.getByRole('button', { name: 'Show', exact: true })
/** The Explorer's chart (ECharts, SVG): its SVG is in the canvas once it is drawn */
const explorerChart = (page: Page) => page.locator('.xc-canvas[data-drawn="true"] svg').first()
/** The forecast's chart, which ECharts draws as SVG into an element that says the colour scheme it is drawn in */
const forecastChart = (page: Page) => page.locator('.mg-canvas').first()

async function openExplorerChart(page: Page, baseURL: string) {
  await mockBackend(page, baseURL)
  await page.goto(EXPLORER)
  await fetchButton(page).click()
  await expect(page.getByRole('table').first()).toBeVisible()
  await page.getByRole('button', { name: 'Show as chart', exact: true }).click()
  await expect(explorerChart(page)).toBeVisible()
}

/** The outline a control has when it has the focus, as the browser paints it: its colour and its width */
function ringOf(element: Locator) {
  return element.evaluate((node) => {
    const style = getComputedStyle(node)
    const context = document.createElement('canvas').getContext('2d', { willReadFrequently: true })!
    context.fillStyle = style.outlineColor
    context.fillRect(0, 0, 1, 1)
    const [r, g, b] = context.getImageData(0, 0, 1, 1).data
    return { color: `rgb(${r}, ${g}, ${b})`, width: Number.parseFloat(style.outlineWidth), style: style.outlineStyle }
  })
}

test.describe('the focus ring of the controls of the explorer\'s chart is the page\'s own, 3:1 on the dark paper (WCAG 1.4.11)', () => {
  // the buttons of the toolbar, the legend's and the chart itself: Plotly's own modebar had a black outline, 21:1 on white and 1.2:1 on the dark paper
  test.beforeEach(async ({ page, baseURL, context }) => {
    await context.addInitScript(() => localStorage.setItem('nuxt-color-mode', 'dark'))
    await openExplorerChart(page, baseURL!)
    await expect(page.locator('.xc-canvas').first()).toHaveAttribute('data-chart-scheme', 'dark')
  })

  test('a toolbar button', async ({ page }) => {
    // reset is off until the chart is zoomed
    await page.getByRole('button', { name: 'Zoom in', exact: true }).focus()
    await page.keyboard.press('Enter')
    const button = page.getByRole('button', { name: 'Reset zoom', exact: true })
    await expect(button).toBeEnabled()
    await button.focus()
    // reached by the keyboard, which is what the ring is for
    await page.keyboard.press('Shift+Tab')
    await page.keyboard.press('Tab')
    await expect(button).toBeFocused()
    const ring = await ringOf(button)
    expect(ring.style).toBe('solid')
    expect(ring.width).toBeGreaterThanOrEqual(2)
    const paper = await behindChart(page)
    expect(luminance(paper), `the paper is the dark one (${paper})`).toBeLessThan(0.05)
    expect(contrast(ring.color, paper)).toBeGreaterThanOrEqual(3)
  })

  test('a legend item', async ({ page }) => {
    const item = page.locator('.xc-legend button').first()
    await item.focus()
    await page.keyboard.press('Shift+Tab')
    await page.keyboard.press('Tab')
    await expect(item).toBeFocused()
    const ring = await ringOf(item)
    expect(ring.style).toBe('solid')
    expect(ring.width).toBeGreaterThanOrEqual(2)
    expect(contrast(ring.color, await behindChart(page))).toBeGreaterThanOrEqual(3)
  })

  test('the chart', async ({ page }) => {
    const stage = page.locator('.xc-stage')
    await stage.focus()
    await page.keyboard.press('Shift+Tab')
    await page.keyboard.press('Tab')
    await expect(stage).toBeFocused()
    const ring = await ringOf(stage)
    expect(ring.style).toBe('solid')
    expect(ring.width).toBeGreaterThanOrEqual(2)
    expect(contrast(ring.color, await behindChart(page))).toBeGreaterThanOrEqual(3)
  })
})

// The text that names a series (GH-3618): the Forecast's y axes, as its temperature axis, its weekend day labels, and its
// freezing line, which carries meaning, are read on the paper in both schemes. The chart is SVG, so the colours are read from
// what is painted.
test('the Forecast\'s axis labels, weekend day labels and freezing line reach contrast in both schemes', async ({ page, baseURL, context }) => {
  await context.addInitScript(() => localStorage.setItem('nuxt-color-mode', 'light'))
  // a Friday, so that the days of the forecast (it runs three days from now) hold a weekend whenever this runs: the
  // page's clock and the forecast the mock serves both start at this instant, not at the day the test runs
  const friday = new Date('2026-10-30T09:00:00Z')
  await page.clock.setSystemTime(friday)
  await mockBackend(page, baseURL!, {}, friday)
  await page.goto('/meteogram?station=01001')
  await expect(forecastChart(page)).toBeVisible()
  // the window opens on the first hours; the weekend is a scroll away on a narrow window
  await page.setViewportSize({ width: 1600, height: 1000 })

  const painted = () => page.locator('.mg-canvas svg').first().evaluate((svg) => {
    const fill = (element: Element) => element.getAttribute('fill') ?? getComputedStyle(element).fill
    const texts = [...svg.querySelectorAll('text')].map(text => ({ text: text.textContent ?? '', color: fill(text) }))
    const lines = [...svg.querySelectorAll('path')].map(path => path.getAttribute('stroke')).filter(Boolean) as string[]
    return { texts, lines }
  })

  for (const scheme of ['light', 'dark'] as const) {
    if (scheme === 'dark') {
      await setColorScheme(page, 'Dark')
      await expect(forecastChart(page)).toHaveAttribute('data-chart-scheme', 'dark')
    }
    const paper = await behindChart(page)
    const { texts } = await painted()
    // the numbers of the axes and the axes' titles are in the series' label colours; the days and hours in the text colours
    const axes = texts.filter(entry => /^-?[\d.,]+$/.test(entry.text) && !/^\d{2}[:.]\d{2}$/.test(entry.text))
    expect(axes.length, `${scheme}: the labels of the axes`).toBeGreaterThanOrEqual(8)
    for (const entry of texts)
      expect(contrast(entry.color, paper), `${scheme}: ${entry.text} ${entry.color}`).toBeGreaterThanOrEqual(4.5)
    // the weekend's labels are in a colour of their own (the Saturday and the Sunday of the three days)
    const days = texts.filter(entry => /^(?:Thu|Fri|Sat|Sun|Mon|Tue|Wed) \d{2}\/\d{2}$/.test(entry.text))
    const weekend = days.filter(entry => /^(?:Sat|Sun)/.test(entry.text))
    expect(weekend.length, `${scheme}: the weekend's labels ${JSON.stringify(days)}`).toBeGreaterThanOrEqual(1)
    expect(new Set(weekend.map(entry => entry.color)).size).toBe(1)
    expect(days.filter(entry => !/^(?:Sat|Sun)/.test(entry.text)).every(entry => entry.color !== weekend[0]!.color)).toBe(true)
  }
})

// The Forecast's own chrome (GH-3642): the icons of its panel toggles, on and off, and of its summary line, measured as the
// browser paints them (the colour of the icon and the backgrounds under it, down to the page), in both schemes.
// A mark that carries meaning needs 3:1 (1.4.11); the label colours clear 4.5:1 on the toolbar, which is held here as well
test('the Forecast\'s panel toggles and summary icons reach contrast in both schemes', async ({ page, baseURL, context }) => {
  await context.addInitScript(() => localStorage.setItem('nuxt-color-mode', 'light'))
  // the page's clock and the forecast the mock serves both start at this instant, as in the test above
  const now = new Date('2026-10-30T09:00:00Z')
  await page.clock.setSystemTime(now)
  await mockBackend(page, baseURL!, {}, now)
  await page.goto('/meteogram?station=01001')
  await expect(forecastChart(page)).toBeVisible()

  // the icon's colour and every background that lies under it, from the page to the icon's own button, as rgba
  const marks = () => page.evaluate(() => {
    const canvas = document.createElement('canvas')
    canvas.width = canvas.height = 1
    const context = canvas.getContext('2d', { willReadFrequently: true })!
    const rgba = (css: string) => {
      context.clearRect(0, 0, 1, 1)
      context.fillStyle = '#000'
      context.fillStyle = css
      context.fillRect(0, 0, 1, 1)
      const [r, g, b, a] = context.getImageData(0, 0, 1, 1).data
      return [r!, g!, b!, a! / 255]
    }
    const read = (icon: Element) => {
      const layers: number[][] = []
      // not the icon's own: a CSS icon is a mask over a background of its own colour
      for (let node = icon.parentElement; node; node = node.parentElement) {
        const layer = rgba(getComputedStyle(node).backgroundColor)
        if (layer[3]! > 0)
          layers.unshift(layer)
      }
      return { color: rgba(getComputedStyle(icon).color), layers }
    }
    const toggles = Array.from(document.querySelectorAll('button[data-panel]')).map(button => ({
      panel: (button as HTMLElement).dataset.panel!,
      pressed: button.getAttribute('aria-pressed'),
      ...read(button.querySelector('[class*="i-ph"]')!),
    }))
    const summary = Array.from(document.querySelectorAll('[data-summary-icon]')).map(icon => ({ panel: (icon as HTMLElement).dataset.summaryIcon!, ...read(icon) }))
    return { toggles, summary }
  })
  // the colours of a mark, which a toggle and a summary icon both have (a toggle adds whether it is pressed)
  type Mark = Awaited<ReturnType<typeof marks>>['summary'][number]
  // the layers composed over the white of the page (the dark scheme's page is a layer of its own), as rgb()
  const ground = (mark: Mark) => mark.layers.reduce((under, layer) => onPaper(`rgba(${layer[0]}, ${layer[1]}, ${layer[2]}, ${layer[3]})`, under), 'rgb(255, 255, 255)')
  const colour = (mark: Mark) => `rgb(${mark.color[0]}, ${mark.color[1]}, ${mark.color[2]})`

  for (const scheme of ['light', 'dark'] as const) {
    if (scheme === 'dark') {
      await setColorScheme(page, 'Dark')
      await expect(forecastChart(page)).toHaveAttribute('data-chart-scheme', 'dark')
    }
    const { toggles, summary } = await marks()
    expect(toggles.map(toggle => toggle.panel), `${scheme}: the panel toggles`).toEqual(['temp', 'wind', 'precip', 'cloud', 'pressure'])
    expect(summary.map(icon => icon.panel), `${scheme}: the summary's icons`).toEqual(['temp', 'wind', 'precip', 'cloud', 'pressure'])
    for (const toggle of toggles) {
      expect(toggle.pressed, `${scheme}: ${toggle.panel} says it is on`).toBe('true')
      expect(contrast(colour(toggle), ground(toggle)), `${scheme}: the ${toggle.panel} toggle that is on, ${colour(toggle)} on ${ground(toggle)}`).toBeGreaterThanOrEqual(3)
    }
    for (const icon of summary)
      expect(contrast(colour(icon), ground(icon)), `${scheme}: the ${icon.panel} icon, ${colour(icon)} on ${ground(icon)}`).toBeGreaterThanOrEqual(4.5)

    // a toggle that is off keeps the greys of the app, which clear 3:1 as well (the page keeps one panel on: the last off stays on)
    await page.locator('button[data-panel]').evaluateAll(buttons => buttons.forEach(button => (button as HTMLElement).click()))
    await expect(page.locator('button[data-panel][aria-pressed="false"]')).toHaveCount(4)
    const off = (await marks()).toggles.filter(toggle => toggle.pressed === 'false')
    expect(off.length, `${scheme}: the toggles that are off`).toBe(4)
    for (const toggle of off)
      expect(contrast(colour(toggle), ground(toggle)), `${scheme}: the ${toggle.panel} toggle that is off, ${colour(toggle)} on ${ground(toggle)}`).toBeGreaterThanOrEqual(3)
    await page.locator('button[data-panel][aria-pressed="false"]').evaluateAll(buttons => buttons.forEach(button => (button as HTMLElement).click()))
    await expect(page.locator('button[data-panel][aria-pressed="true"]')).toHaveCount(5)
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
      await expect(forecastChart(page)).toBeVisible()
      await expect(page.locator('html')).toHaveClass(widgetTheme === 'dark' ? /dark/ : /^(?!.*dark)/)
      // the chart is drawn in the widget's scheme
      await expect(forecastChart(page)).toHaveAttribute('data-chart-scheme', widgetTheme)
      expect(await saved(page)).toBe(chosen)

      // the app, opened after the widget, is in the scheme it was saved in
      await page.goto('/')
      await expect(page.locator('html')).toHaveClass(chosen === 'dark' ? /dark/ : /^(?!.*dark)/)
      expect(await saved(page)).toBe(chosen)
    })
  }
})
