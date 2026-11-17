import type { Download, Locator, Page } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { expect, test } from '@playwright/test'
import { STRIPE_PALETTES } from '../../app/utils/stripes'
import { CAMERA_SCALE, CAMERA_WIDTH, extraLinesHeight, frameOf, STRIPES_MAX_HEIGHT, STRIPES_MIN_HEIGHT, STRIPES_RATIO, stripesChartHeight } from '../../app/utils/stripes-option'
import { stripesAnswer } from '../helpers/stripes-answer'
import { mockBackend } from './accessibility/mock-backend'

// The climate stripes (GH-4068): Apache ECharts, drawn as SVG. Their chrome takes the colours of the page (the title, the
// years and the source are the page's text and muted text, 4.5:1 on what is behind them), in dark mode too, and follows a switch
// of the colour scheme without a reload; the stripes themselves are data and keep their colours. A saved or printed chart is
// the light one. The title and the source are laid out for a phone (GH-3961). The API is answered by the mock backend, so the
// spec needs nothing but the app.

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

const PATH = '/stripes?kind=temperature&station=00011'
const fetchButton = (page: Page) => page.getByRole('button', { name: 'Show', exact: true })
/** The chart, once it is drawn: the SVG is in its canvas */
const chartSvg = (page: Page) => page.locator('.sc-canvas[data-drawn="true"] svg').first()
const canvas = (page: Page) => page.locator('.sc-canvas').first()

async function showStripes(page: Page, baseURL: string, path = PATH) {
  await mockBackend(page, baseURL)
  await page.goto(path)
  await fetchButton(page).click()
  await expect(chartSvg(page)).toBeVisible()
}

async function setColorScheme(page: Page, label: 'Light' | 'Dark') {
  await page.getByLabel('Settings', { exact: true }).click()
  await page.getByRole('button', { name: label, exact: true }).click()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog')).toHaveCount(0)
}

/** What the chart draws, as the browser paints it: the colours of its texts, the fills of its stripes, and what is behind it */
async function paintOf(page: Page) {
  return page.locator('.stripes-chart').first().evaluate((chart) => {
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
    const svg = chart.querySelector('.sc-canvas svg')!
    const texts = [...svg.querySelectorAll('text')].map(text => ({ text: text.textContent ?? '', fill: getComputedStyle(text).fill, size: Number.parseFloat(getComputedStyle(text).fontSize) }))
    const stripes = [...svg.querySelectorAll('path')].map(path => path.getAttribute('fill') ?? '').filter(fill => /^#[\da-f]{6}$/i.test(fill) && fill.toLowerCase() !== '#ffd700')
    return { behind: behind || rgb(getComputedStyle(document.body).backgroundColor).text, texts, stripes }
  })
}

test.describe('the stripes\' colours', () => {
  test('are the page\'s in light and in dark mode, readable on it, and follow a switch without a reload, the stripes keeping theirs', async ({ page, baseURL, context }) => {
    await context.addInitScript(() => localStorage.setItem('nuxt-color-mode', 'light'))
    const backend = await mockBackend(page, baseURL!)
    await page.goto(`${PATH}&show_data_availability=true&show_source=true&show_years=true&show_title=true`)
    await expect(page.locator('html')).not.toHaveClass(/dark/)
    await fetchButton(page).click()
    await expect(chartSvg(page)).toBeVisible()
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
    // the stripes are data: the same in both
    expect(dark.stripes.length).toBeGreaterThan(50)
    expect(dark.stripes).toEqual(light.stripes)

    // WCAG 1.4.3: every text of the chart, 4.5:1 on what is behind it, in both schemes (the title, the years, the source, the
    // label of the availability line, which is gold on a card)
    for (const [scheme, paint] of [['light', light], ['dark', dark]] as const) {
      expect(paint.texts.map(text => text.text)).toEqual(expect.arrayContaining(['1955', '2024', 'Data availability']))
      expect(paint.texts.some(text => text.text.startsWith('Source:'))).toBe(true)
      for (const { text, fill } of paint.texts)
        expect(contrast(fill, paint.behind), `${scheme}: ${text} in ${fill} on ${paint.behind}`).toBeGreaterThanOrEqual(4.5)
    }
    // the chrome changed with the scheme
    expect(dark.texts.find(text => text.text === '2024')!.fill).not.toBe(light.texts.find(text => text.text === '2024')!.fill)

    await setColorScheme(page, 'Light')
    await expect(canvas(page)).toHaveAttribute('data-chart-scheme', 'light')
    expect(backend.unanswered).toEqual([])
  })

  test('are drawn dark at once on a page that opens in dark mode', async ({ page, baseURL, context }) => {
    await context.addInitScript(() => localStorage.setItem('nuxt-color-mode', 'dark'))
    await showStripes(page, baseURL!)
    await expect(canvas(page)).toHaveAttribute('data-chart-scheme', 'dark')
    expect(luminance((await paintOf(page)).behind)).toBeLessThan(0.05)
  })

  test('have a focus ring of the page\'s own, 3:1 on the dark card (WCAG 1.4.11)', async ({ page, baseURL, context }) => {
    await context.addInitScript(() => localStorage.setItem('nuxt-color-mode', 'dark'))
    await showStripes(page, baseURL!)
    const stage = page.locator('.sc-stage')
    await stage.focus()
    await page.keyboard.press('Shift+Tab')
    await page.keyboard.press('Tab')
    await expect(stage).toBeFocused()
    const ring = await stage.evaluate((element) => {
      const style = getComputedStyle(element)
      const context = document.createElement('canvas').getContext('2d', { willReadFrequently: true })!
      context.fillStyle = style.outlineColor
      context.fillRect(0, 0, 1, 1)
      const [r, g, b] = context.getImageData(0, 0, 1, 1).data
      return { color: `rgb(${r}, ${g}, ${b})`, width: Number.parseFloat(style.outlineWidth) }
    })
    expect(ring.width).toBeGreaterThanOrEqual(2)
    expect(contrast(ring.color, (await paintOf(page)).behind)).toBeGreaterThanOrEqual(3)
  })

  test('are marked by a ring of black in white that reads on every stripe and on the card, where a key stops at one', async ({ page, baseURL, context }) => {
    await context.addInitScript(() => localStorage.setItem('nuxt-color-mode', 'dark'))
    await showStripes(page, baseURL!)
    await page.locator('.sc-stage').focus()
    await page.keyboard.press('ArrowRight')
    const ring = await page.locator('.sc-cursor').evaluate((element) => {
      const style = getComputedStyle(element)
      return { border: style.borderTopColor, shadow: style.boxShadow, width: style.borderTopWidth }
    })
    expect(ring.border).toBe('rgb(0, 0, 0)')
    expect(ring.shadow).toContain('rgb(255, 255, 255)')
    expect(Number.parseFloat(ring.width)).toBeGreaterThanOrEqual(2)
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

test.describe('a saved stripes chart', () => {
  test.beforeEach(async ({ context }) => {
    await context.addInitScript(() => localStorage.setItem('nuxt-color-mode', 'dark'))
  })

  // the line of text a saved image has under its source, 20 px, for what its colours are relative to (the chart is wide enough for one)
  const REFERENCE_LINE = 20

  async function menu(page: Page, item: string) {
    await page.getByRole('button', { name: 'Download image' }).click()
    const saved = page.waitForEvent('download')
    await page.getByRole('menuitem', { name: item }).click()
    return saved
  }

  test('is the light one and the size of the chart on the page times three, from the menu (the height the page gives it, GH-4133), and a line higher for what the colours are relative to (GH-4157)', async ({ page, baseURL }) => {
    await showStripes(page, baseURL!)
    const shown = (await page.locator('.sc-canvas').boundingBox())!
    for (const [item, extension] of [['Download as PNG', 'png'], ['Download as JPG', 'jpeg']] as const) {
      const download = await menu(page, item)
      expect(download.suggestedFilename()).toMatch(new RegExp(`^climate_stripes_temperature_00011_.+\\.${extension}$`))
      const image = await imageOf(page, download)
      expect(luminance(image.corner), `the saved image is light (its corner is ${image.corner})`).toBeGreaterThan(0.9)
      expect(image.width).toBe(Math.round(shown.width) * 3)
      expect(image.height).toBe((Math.round(shown.height) + REFERENCE_LINE) * 3)
      // the chart on the page is as dark as it was
      await expect(canvas(page)).toHaveAttribute('data-chart-scheme', 'dark')
    }
  })

  test('is a vector of the size of the chart from the menu, with the light chart\'s colours', async ({ page, baseURL }) => {
    await showStripes(page, baseURL!)
    const shown = (await page.locator('.sc-canvas').boundingBox())!
    const download = await menu(page, 'Download as SVG')
    expect(download.suggestedFilename()).toMatch(/^climate_stripes_temperature_00011_.+\.svg$/)
    const svg = readFileSync((await download.path())!, 'utf8')
    expect(svg).toMatch(new RegExp(`<svg width="\\d+" height="${Math.round(shown.height) + REFERENCE_LINE}"`))
    expect(svg).toContain('Climate stripes')
    // and says what its colours are relative to, under the source (GH-4157)
    expect(svg).toContain('Colours: mean of 1971–2000, ±2.6 σ of 1955–2000')
    // on the light paper: the first thing the vector draws is a rect that is neither empty nor transparent, and it is light
    const paper = /^<svg[^>]*>\s*<rect[^>]*fill="([^"]*)"/.exec(svg)?.[1]
    expect(paper, 'the vector draws its paper').toMatch(/^(rgb|#)/)
    expect(luminance(paper!)).toBeGreaterThan(0.9)
    // the dark theme's text colour is not in it
    const dark = (await paintOf(page)).texts.find(text => text.text === '2024')!.fill
    expect(svg).not.toContain(dark.replaceAll(' ', ''))
  })

  test('is 2800 by 1870 px (the stripes 16:9 at 1400 px wide, and a line for the colours\' reference) and light, from the camera of the toolbar, named for the station', async ({ page, baseURL }) => {
    await showStripes(page, baseURL!)
    const saved = page.waitForEvent('download')
    await page.getByRole('button', { name: 'Download plot as a PNG' }).click()
    const download = await saved
    expect(download.suggestedFilename()).toBe('climate_stripes_temperature_00011.png')
    const image = await imageOf(page, download)
    expect(luminance(image.corner)).toBeGreaterThan(0.9)
    expect([image.width, image.height]).toEqual([2800, 1870])
    await expect(canvas(page)).toHaveAttribute('data-chart-scheme', 'dark')
  })

  test('is 1400 by 925 times two without a title, the stripes keeping their height', async ({ page, baseURL }) => {
    await showStripes(page, baseURL!, `${PATH}&show_title=false`)
    const saved = page.waitForEvent('download')
    await page.getByRole('button', { name: 'Download plot as a PNG' }).click()
    const image = await imageOf(page, await saved)
    expect([image.width, image.height]).toEqual([2800, 1850])
  })

  test('is the range the chart is zoomed to', async ({ page, baseURL }) => {
    await showStripes(page, baseURL!)
    await page.getByRole('button', { name: 'Zoom in' }).click()
    await expect(page.getByRole('button', { name: 'Reset zoom' })).toBeEnabled()
    const download = await menu(page, 'Download as SVG')
    const svg = readFileSync((await download.path())!, 'utf8')
    const years = [...svg.matchAll(/>(\d{4})<\/text>/g)].map(match => Number(match[1]))
    expect(years).toHaveLength(2)
    expect(years[0]).toBeGreaterThan(1955)
    expect(years[1]).toBeLessThan(2024)
  })
})

// WCAG 2.4.3 (GH-4101): a toolbar button that turns off while it has the focus is off (`aria-disabled`) and keeps the focus; `disabled`
// would drop it to the page, and a keyboard user would start again from the top. Pressed again, it does nothing.
test.describe('a toolbar button that turns off while it has the focus', () => {
  /** The years the axis names, which a zoom or a move changes */
  const yearsOf = (page: Page) => chartSvg(page).locator('text').filter({ hasText: /^\d{4}$/ }).allTextContents()
  const focusedLabel = (page: Page) => page.evaluate(() => document.activeElement?.getAttribute('aria-label') ?? document.activeElement?.tagName)
  async function pressUntilOff(page: Page, button: Locator, key: string) {
    for (let press = 0; press < 40; press++)
      await page.keyboard.press(key)
    await expect(button).toHaveAttribute('aria-disabled', 'true')
  }

  test('Reset zoom keeps the focus on Space, and does nothing when it is pressed again', async ({ page, baseURL }) => {
    await showStripes(page, baseURL!)
    const reset = page.locator('.sc-toolbar button[aria-label="Reset zoom"]')
    await page.getByRole('button', { name: 'Zoom in', exact: true }).click()
    await expect(reset).not.toHaveAttribute('aria-disabled', 'true')
    const zoomed = await yearsOf(page)
    await reset.focus()
    await page.keyboard.press('Space')
    await expect(reset).toHaveAttribute('aria-disabled', 'true')
    await expect.poll(() => yearsOf(page)).not.toEqual(zoomed)
    const whole = await yearsOf(page)
    await expect(reset).toBeFocused()
    expect(await focusedLabel(page)).toBe('Reset zoom')
    // still a button in the tab order, not a disabled one
    expect(await reset.evaluate((button: HTMLButtonElement) => [button.disabled, button.tabIndex])).toEqual([false, 0])
    await page.keyboard.press('Space')
    await page.keyboard.press('Enter')
    await expect(reset).toBeFocused()
    await expect(reset).toHaveAttribute('aria-disabled', 'true')
    expect(await yearsOf(page)).toEqual(whole)
  })

  test('an unavailable Reset zoom does nothing when it is pressed: a readout dismissed by Escape stays closed', async ({ page, baseURL }) => {
    await showStripes(page, baseURL!)
    const readout = page.getByTestId('stripes-readout')
    // the pointer's readout: one the keyboard put there goes when the focus leaves the chart, the pointer's stays
    await page.locator('.sc-stage').scrollIntoViewIfNeeded()
    const box = (await page.locator('.sc-stage').boundingBox())!
    await page.mouse.move(box.x + box.width * 0.4, box.y + box.height * 0.5)
    await expect(readout).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(readout).toHaveCount(0)
    // a reset of the zoom would show the readout again: the whole chart is shown, so Reset zoom is off and must not
    const reset = page.locator('.sc-toolbar button[aria-label="Reset zoom"]')
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
    await showStripes(page, baseURL!)
    const zoomIn = page.locator('.sc-toolbar button[aria-label="Zoom in"]')
    await zoomIn.focus()
    await pressUntilOff(page, zoomIn, 'Enter')
    await expect(zoomIn).toBeFocused()
    const atLimit = await yearsOf(page)
    await page.keyboard.press('Enter')
    await expect(zoomIn).toBeFocused()
    expect(await yearsOf(page)).toEqual(atLimit)

    const later = page.locator('.sc-toolbar button[aria-label="Later years"]')
    await later.focus()
    await pressUntilOff(page, later, 'Space')
    await expect(later).toBeFocused()
    expect(await focusedLabel(page)).toBe('Later years')
  })
})

test.describe('a printed stripes chart', () => {
  test('is drawn light for as long as the page is printed, and dark again after', async ({ page, baseURL, context }) => {
    await context.addInitScript(() => localStorage.setItem('nuxt-color-mode', 'dark'))
    await showStripes(page, baseURL!)
    await expect(canvas(page)).toHaveAttribute('data-chart-scheme', 'dark')
    await page.emulateMedia({ media: 'print' })
    await expect(canvas(page)).toHaveAttribute('data-chart-scheme', 'light')
    const printed = await paintOf(page)
    expect(luminance(printed.texts.find(text => text.text === '2024')!.fill)).toBeLessThan(0.2)
    await page.emulateMedia({ media: 'screen' })
    await expect(canvas(page)).toHaveAttribute('data-chart-scheme', 'dark')
  })

  test('is not drawn again where a page that is light is printed', async ({ page, baseURL, context }) => {
    await context.addInitScript(() => localStorage.setItem('nuxt-color-mode', 'light'))
    await showStripes(page, baseURL!)
    const drawings = () => page.evaluate(() => performance.getEntriesByName('stripes:drawn').length)
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

  test('is scaled to the width of the sheet, without its toolbar and its readout', async ({ page, baseURL, context }) => {
    await context.addInitScript(() => localStorage.setItem('nuxt-color-mode', 'light'))
    await showStripes(page, baseURL!)
    await page.locator('.sc-stage').focus()
    await page.keyboard.press('ArrowRight')
    await expect(page.getByTestId('stripes-readout')).toBeVisible()
    await page.emulateMedia({ media: 'print' })
    await expect(page.locator('.sc-toolbar')).toBeHidden()
    await expect(page.getByTestId('stripes-readout')).toBeHidden()
    await expect(page.locator('.sc-cursor')).toBeHidden()
    const box = (await chartSvg(page).boundingBox())!
    const column = await page.locator('.stripes-chart').evaluate(element => element.clientWidth)
    expect(box.width).toBeLessThanOrEqual(column + 1)
  })
})

// The zoom is the chart's: it stays where the colours or the language change, and a reset goes back to all of it
test('a zoomed chart stays zoomed where the scheme switches, and its reset still goes back to the whole record', async ({ page, baseURL, context }) => {
  await context.addInitScript(() => localStorage.setItem('nuxt-color-mode', 'light'))
  await showStripes(page, baseURL!)
  const years = async () => (await paintOf(page)).texts.map(text => text.text).filter(text => /^\d{4}$/.test(text)).join('-')
  expect(await years()).toBe('1955-2024')

  // a box dragged on the plot zooms it in
  const plot = (await page.locator('.sc-stage').boundingBox())!
  await page.mouse.move(plot.x + plot.width * 0.3, plot.y + plot.height * 0.5)
  await page.mouse.down()
  await page.mouse.move(plot.x + plot.width * 0.6, plot.y + plot.height * 0.5, { steps: 5 })
  await page.mouse.up()
  await expect.poll(years).not.toBe('1955-2024')
  const zoomed = await years()

  await setColorScheme(page, 'Dark')
  await expect(canvas(page)).toHaveAttribute('data-chart-scheme', 'dark')
  expect(await years()).toBe(zoomed)
  await page.emulateMedia({ media: 'print' })
  await expect(canvas(page)).toHaveAttribute('data-chart-scheme', 'light')
  expect(await years()).toBe(zoomed)
  await page.emulateMedia({ media: 'screen' })

  // a double click is the way back, and so is the button
  await page.locator('.sc-stage').dblclick({ position: { x: 5, y: 5 } })
  await expect.poll(years).toBe('1955-2024')
})

test('the stripes take a zoom by the wheel with Ctrl, and by the keys', async ({ page, baseURL, context }) => {
  await context.addInitScript(() => localStorage.setItem('nuxt-color-mode', 'light'))
  await showStripes(page, baseURL!)
  const years = async () => (await paintOf(page)).texts.map(text => text.text).filter(text => /^\d{4}$/.test(text)).join('-')
  const plot = (await page.locator('.sc-stage').boundingBox())!
  await page.mouse.move(plot.x + plot.width / 2, plot.y + plot.height / 2)
  await page.keyboard.down('Control')
  await page.mouse.wheel(0, -300)
  await page.keyboard.up('Control')
  await expect.poll(years).not.toBe('1955-2024')
  await page.locator('.sc-stage').focus()
  await page.keyboard.press('0')
  await expect.poll(years).toBe('1955-2024')
})

test('the chart has no animation, and draws as it is with reduced motion asked for', async ({ page, baseURL, context }) => {
  await context.addInitScript(() => localStorage.setItem('nuxt-color-mode', 'light'))
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await showStripes(page, baseURL!)
  const motion = await page.locator('.sc-canvas').evaluate(element => ({
    animations: element.getAnimations({ subtree: true }).length,
    smil: element.querySelectorAll('animate, animateTransform, animateMotion, set').length,
  }))
  expect(motion).toEqual({ animations: 0, smil: 0 })
  // the stripes are there at once, not grown into place
  expect((await paintOf(page)).stripes.length).toBeGreaterThan(50)
})

// The title is broken into lines where it is wider than the chart, and the source has a row of its own below the years (GH-3961).
// Measured on the boxes of the drawn text, in the window sizes of a phone and a tablet.
interface Box { left: number, top: number, right: number, bottom: number }

for (const [width, scheme, availability] of [[320, 'light', true], [320, 'dark', true], [320, 'light', false], [390, 'light', true], [768, 'light', true]] as const) {
  test(`the stripes' title is whole and their source clears the years, in a ${width} px window (${scheme}, data availability ${availability ? 'on' : 'off'})`, async ({ page, baseURL, context }) => {
    await context.addInitScript(mode => localStorage.setItem('nuxt-color-mode', mode), scheme)
    await page.setViewportSize({ width, height: 900 })
    await showStripes(page, baseURL!, `${PATH}&show_data_availability=${availability}&show_source=true&show_years=true&show_title=true`)

    const boxes = await page.locator('.sc-canvas svg').first().evaluate((svg) => {
      const box = (element: Element) => {
        const { left, top, right, bottom } = element.getBoundingClientRect()
        return { left, top, right, bottom }
      }
      const texts = [...svg.querySelectorAll('text')].map(element => ({ text: element.textContent ?? '', box: box(element) }))
      const firstYear = texts.findIndex(text => /^\d{4}$/.test(text.text))
      return {
        chart: box(svg),
        toolbar: box(document.querySelector('.sc-toolbar')!),
        // the lines of the title come first in the chart, then the years, the availability label and the source
        title: texts.slice(0, firstYear).map(text => text.box),
        years: texts.filter(text => /^\d{4}$/.test(text.text)).map(text => text.box),
        source: texts.find(text => text.text.startsWith('Source:'))?.box,
        availability: texts.find(text => text.text === 'Data availability')?.box,
      }
    })
    const intersects = (a: Box, b: Box) => a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom

    expect(boxes.years).toHaveLength(2)
    expect(boxes.source, 'the source is drawn').toBeTruthy()
    for (const year of boxes.years)
      expect(intersects(boxes.source!, year), `the source and a year: ${JSON.stringify([boxes.source, year])}`).toBe(false)
    if (availability)
      expect(intersects(boxes.source!, boxes.availability!), 'the source and "Data availability"').toBe(false)
    // the source is whole inside the chart, the years above it
    expect(boxes.source!.left).toBeGreaterThanOrEqual(boxes.chart.left)
    expect(boxes.source!.right).toBeLessThanOrEqual(boxes.chart.right)
    expect(boxes.source!.bottom).toBeLessThanOrEqual(boxes.chart.bottom)

    expect(boxes.title.length).toBeGreaterThan(0)
    for (const line of boxes.title) {
      expect(line.left, 'the title is not cut at the left').toBeGreaterThanOrEqual(boxes.chart.left)
      expect(line.right, 'the title is not cut at the right').toBeLessThanOrEqual(boxes.chart.right)
      expect(line.top).toBeGreaterThanOrEqual(boxes.chart.top)
      // the toolbar is above the chart, not over its title
      expect(intersects(line, boxes.toolbar), 'a line of the title and the toolbar').toBe(false)
    }
    // the narrow chart breaks its title; a chart that holds it in one line does not
    if (width <= 390)
      expect(boxes.title.length, 'the title is broken into lines').toBeGreaterThan(1)
    else
      expect(boxes.title).toHaveLength(1)

    // WCAG 1.4.10: the page does not scroll sideways, and the chart and its toolbar stay in the window
    expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(0)
    expect(boxes.toolbar.right).toBeLessThanOrEqual(width)
    expect(boxes.chart.right).toBeLessThanOrEqual(width)
  })
}

test('the readout stays inside the chart on a phone, and is closed by its button', async ({ page, baseURL, context }) => {
  await context.addInitScript(() => localStorage.setItem('nuxt-color-mode', 'light'))
  await page.setViewportSize({ width: 320, height: 900 })
  await showStripes(page, baseURL!)
  const stage = page.locator('.sc-stage')
  await stage.scrollIntoViewIfNeeded()
  const box = (await stage.boundingBox())!
  await stage.focus()
  await page.keyboard.press('End')
  const readout = page.getByTestId('stripes-readout')
  await expect(readout).toBeVisible()
  const readoutBox = (await readout.boundingBox())!
  expect(readoutBox.x).toBeGreaterThanOrEqual(box.x)
  expect(readoutBox.x + readoutBox.width).toBeLessThanOrEqual(box.x + box.width)
  expect(readoutBox.y + readoutBox.height).toBeLessThanOrEqual(box.y + box.height)
  await readout.getByRole('button', { name: 'Close the values' }).click()
  await expect(readout).toHaveCount(0)
})

// The stripes keep their shape (GH-4133): as high as they are wide over the ratio, between a least and a most, whatever the
// window is, so that on a phone the chart, its years and its availability line are no tall narrow block, and on a wide
// screen it is no flat band. Measured on the drawn stripes (their paths), not on the chart's box, which has the title (of
// as many lines as the width makes) and the years on top of them.
async function measureStripes(page: Page) {
  return page.locator('.sc-canvas svg').first().evaluate((svg) => {
    const boxes = [...svg.querySelectorAll('path')]
      .filter(path => /^#[\da-f]{6}$/i.test(path.getAttribute('fill') ?? '') && (path.getAttribute('fill') ?? '').toLowerCase() !== '#ffd700')
      .map(path => path.getBoundingClientRect())
    const left = Math.min(...boxes.map(box => box.left))
    const right = Math.max(...boxes.map(box => box.right))
    const top = Math.min(...boxes.map(box => box.top))
    const bottom = Math.max(...boxes.map(box => box.bottom))
    return { stripes: { width: right - left, height: bottom - top }, chart: svg.getBoundingClientRect().toJSON() }
  })
}
const stripesHeight = async (page: Page) => (await measureStripes(page)).stripes.height

for (const [width, height] of [[320, 700], [390, 844], [768, 900], [1280, 900], [1600, 900]] as const) {
  test(`the stripes are as high as they are wide over ${STRIPES_RATIO.toFixed(2)}, in a ${width} px window`, async ({ page, baseURL }) => {
    await page.setViewportSize({ width, height })
    await showStripes(page, baseURL!)
    const measured = await measureStripes(page)
    const expected = Math.min(STRIPES_MAX_HEIGHT, Math.max(STRIPES_MIN_HEIGHT, (measured.chart.width - 40) / STRIPES_RATIO))
    // the stripes span the plot, which is the chart's width less its 20 px at either side
    expect(measured.stripes.width).toBeGreaterThan(measured.chart.width - 40 - 3)
    expect(measured.stripes.width).toBeLessThan(measured.chart.width - 40 + 3)
    expect(measured.stripes.height, `the stripes' height at ${width} px, of a chart ${measured.chart.width} px wide`).toBeGreaterThan(expected - 3)
    expect(measured.stripes.height).toBeLessThan(expected + 3)
    if (width <= 390) {
      // a phone's stripes are held to the least, not the thinner 16:9 of their width
      expect(measured.stripes.height, 'the least the stripes are high').toBeGreaterThan(STRIPES_MIN_HEIGHT - 3)
      // the whole chart, its years and its availability line, fits a screen of a phone with room to spare for the page's own bar
      // (the form is above it, so it is scrolled to): no tall block that the screen cannot hold
      expect(measured.chart.height, 'the chart is lower than the screen').toBeLessThanOrEqual(height - 200)
    }
  })
}

test('the stripes follow a change of the window: lower in a narrower one, held to the least in the narrowest', async ({ page, baseURL }) => {
  await page.setViewportSize({ width: 1280, height: 900 })
  await showStripes(page, baseURL!)
  const wide = await stripesHeight(page)
  expect(wide).toBeGreaterThan(STRIPES_MIN_HEIGHT + 100)
  // measured on the stripes: the chart's own height also depends on how many lines the title is broken into
  await page.setViewportSize({ width: 390, height: 844 })
  await expect.poll(() => stripesHeight(page)).toBeLessThan(wide - 100)
  expect(await stripesHeight(page)).toBeGreaterThan(STRIPES_MIN_HEIGHT - 3)
  expect(await stripesHeight(page)).toBeLessThan(STRIPES_MIN_HEIGHT + 3)
  await page.setViewportSize({ width: 320, height: 700 })
  await expect.poll(() => stripesHeight(page)).toBeLessThan(STRIPES_MIN_HEIGHT + 3)
  expect(await stripesHeight(page)).toBeGreaterThan(STRIPES_MIN_HEIGHT - 3)
})

// The availability line covers exactly the stripes that have a value (GH-4153): a run from the left edge of its first stripe to the
// right edge of its last, and a year between two gaps is a bar as wide as its stripe. It was a line from the middle of a stripe to the
// middle of another, half a stripe short at each end and none at all for a lone year.
const range = (from: number, to: number) => Array.from({ length: to - from + 1 }, (_, index) => from + index)
for (const [width, height] of [[390, 844], [1280, 900]] as const) {
  test(`the availability line lies under each stripe that has a value, and a lone year has its own bar, in a ${width} px window`, async ({ page, baseURL }) => {
    await page.setViewportSize({ width, height })
    // 1944; a gap (1945); a run to 1950; a gap; a lone year (1952); a gap; a run of two (1954, 1955); a long run; a gap of 2010 to 2012;
    // a run; a gap; a lone year (2020) and a gap; a run at the end
    const years = [1944, ...range(1946, 1950), 1952, 1954, 1955, ...range(1957, 2009), ...range(2013, 2018), 2020, 2022, 2023, 2024]
    const runs = [[1944, 1944], [1946, 1950], [1952, 1952], [1954, 1955], [1957, 2009], [2013, 2018], [2020, 2020], [2022, 2024]]
    await mockBackend(page, baseURL!, {
      'stripes/values': () => ({
        series: { station: { station_id: '00011', name: 'Donaueschingen (Landeplatz)', region: 'Baden-Württemberg', latitude: 47.97, longitude: 8.52, elevation: 680, start_timestamp: '1944-01-01T00:00:00+00:00', end_timestamp: null }, resolution: 'annual', dataset: 'climate_summary', parameter: 'temperature_air_mean_2m', unit: 'degree_celsius' },
        ...stripesAnswer(years.map(year => ({ year, value: Math.round((8 + (year - 1944) * 0.03 + 0.8 * Math.sin(year / 3)) * 100) / 100 }))),
      }),
    })
    await page.goto(`${PATH}&show_data_availability=true&show_source=true&show_years=true&show_title=true`)
    await fetchButton(page).click()
    await expect(chartSvg(page)).toBeVisible()
    const drawn = await chartSvg(page).evaluate((svg) => {
      const box = (element: Element) => {
        const { left, right, top, bottom } = element.getBoundingClientRect()
        return { left, right, top, bottom }
      }
      const paths = [...svg.querySelectorAll('path')]
      const fill = (element: Element) => (element.getAttribute('fill') ?? '').replaceAll(' ', '').toLowerCase()
      return {
        stripes: paths.filter(path => /^#[\da-f]{6}$/.test(fill(path)) && fill(path) !== '#ffd700').map(box),
        gold: paths.filter(path => fill(path) === '#ffd700').map(box),
      }
    })
    expect(drawn.stripes).toHaveLength(years.length)
    // the line is one bar for each run, so a run of one year (1944, 1952, 2020) has one too
    expect(drawn.gold).toHaveLength(runs.length)
    // 2 px: what the browser measures, not what the option says, and the browsers round the SVG's px a little differently
    runs.forEach(([first, last], index) => {
      const bar = drawn.gold[index]!
      const firstStripe = drawn.stripes[years.indexOf(first!)]!
      const lastStripe = drawn.stripes[years.indexOf(last!)]!
      expect(Math.abs(bar.left - firstStripe.left), `${first} to ${last}: left edge`).toBeLessThanOrEqual(2)
      expect(Math.abs(bar.right - lastStripe.right), `${first} to ${last}: right edge`).toBeLessThanOrEqual(2)
      // under the stripes, not over them
      expect(bar.top).toBeGreaterThan(firstStripe.bottom)
    })
    // a lone year (1952) is as wide as its stripe, which was no line at all
    const lone = drawn.gold[2]!
    const stripe = drawn.stripes[years.indexOf(1952)]!
    expect(lone.right - lone.left).toBeGreaterThan(0)
    expect(Math.abs((lone.right - lone.left) - (stripe.right - stripe.left))).toBeLessThanOrEqual(2)
  })
}

// The colours follow Ed Hawkins' method (GH-4157): the classes the backend gives each year against the station's whole record,
// 16 discrete colours from blue to red, with the page saying what they are relative to. The mock backend classes a warming
// record of 1955 to 2024 as the real one does: the mean of 1971 to 2000 is the centre, and the
// record has the 46 years of 1955 to 2000 of the 100 of 1901 to 2000 the standard deviation is calculated from (30 are needed).
const TEMPERATURE_PALETTE = STRIPE_PALETTES.temperature
for (const [width, height] of [[390, 844], [1280, 900]] as const) {
  test(`the stripes are discrete colours of the backend's classes, from blue to red, in a ${width} px window`, async ({ page, baseURL }) => {
    await page.setViewportSize({ width, height })
    await showStripes(page, baseURL!)
    const { stripes } = await paintOf(page)
    const drawn = stripes.map(fill => fill.toLowerCase())
    expect(drawn).toHaveLength(70)
    // a discrete scale: only colours of the palette, never one mixed between two of them
    expect(drawn.filter(fill => !TEMPERATURE_PALETTE.includes(fill))).toEqual([])
    // the record warms: it starts in the blue half and ends in the red half
    expect(TEMPERATURE_PALETTE.indexOf(drawn[0]!)).toBeLessThan(8)
    expect(TEMPERATURE_PALETTE.indexOf(drawn.at(-1)!)).toBeGreaterThanOrEqual(8)
    // and says what the colours are relative to, in view
    await expect(page.getByTestId('stripes-reference')).toContainText('Colours: the mean of 1971–2000 is the centre of the scale, which spans ±2.6 standard deviations of 1955–2000')
  })
}

test('the table of the years has each one\'s anomaly and class', async ({ page, baseURL }) => {
  await showStripes(page, baseURL!)
  await page.getByRole('button', { name: 'Show as table' }).click()
  await expect(page.locator('table thead th')).toHaveText(['Year', 'Value (°C)', 'Anomaly (°C)', 'Class'])
  const first = page.locator('table tbody tr').first()
  await expect(first.locator('th')).toHaveText('1955')
  // the first year is below the mean of 1971 to 2000
  await expect(first.locator('td').nth(1)).toHaveText(/^-\d/)
})

// The same years as bars, and as bars with a scale (GH-4156): a switch above the chart, kept in the link; the bars are the year's
// anomaly in the colour of its class, so a bar and a stripe of a year are one colour.
const variantSwitch = (page: Page) => page.getByRole('radiogroup', { name: 'Chart style' })
const variantOption = (page: Page, name: string) => variantSwitch(page).getByRole('radio', { name, exact: true })
/** The bars of the drawn chart: the rects that are no gold, with their fill, from the browser's own layout */
function barsOnPage(page: Page) {
  return chartSvg(page).evaluate((svg) => {
    const fill = (element: Element) => (element.getAttribute('fill') ?? '').replaceAll(' ', '').toLowerCase()
    return [...svg.querySelectorAll('path')]
      .filter(path => /^#[\da-f]{6}$/.test(fill(path)) && fill(path) !== '#ffd700')
      .map((path) => {
        const { top, bottom, height } = path.getBoundingClientRect()
        return { top, bottom, height, fill: fill(path) }
      })
  })
}

test.describe('the stripes as bars', () => {
  test('are chosen with the switch, which names the three and says the one drawn, and are kept in the link', async ({ page, baseURL }) => {
    await showStripes(page, baseURL!)
    await expect(variantSwitch(page).getByRole('radio')).toHaveText(['Stripes', 'Bars', 'Bars with scale'])
    await expect(variantOption(page, 'Stripes')).toHaveAttribute('aria-checked', 'true')
    const stripes = await barsOnPage(page)
    // stripes are as high as each other
    expect(new Set(stripes.map(stripe => Math.round(stripe.height))).size).toBe(1)

    await variantOption(page, 'Bars').click()
    await expect(variantOption(page, 'Bars')).toHaveAttribute('aria-checked', 'true')
    await expect(page).toHaveURL(/[?&]variant=bars(&|$)/)
    const bars = await barsOnPage(page)
    expect(bars).toHaveLength(stripes.length)
    // bars are as high as their anomalies: they differ, and the same year is the same colour in both
    expect(new Set(bars.map(bar => Math.round(bar.height))).size).toBeGreaterThan(10)
    expect(bars.map(bar => bar.fill)).toEqual(stripes.map(stripe => stripe.fill))

    await variantOption(page, 'Bars with scale').click()
    await expect(page).toHaveURL(/[?&]variant=bars_scale(&|$)/)
    await variantOption(page, 'Stripes').click()
    await expect(page).toHaveURL(/[?&]variant=stripes(&|$)/)
  })

  test('are drawn from a link that names them, with the switch on the one named, in a 390 and a 1280 px window', async ({ page, baseURL }) => {
    for (const [width, height] of [[390, 844], [1280, 900]] as const) {
      await page.setViewportSize({ width, height })
      await showStripes(page, baseURL!, `${PATH}&variant=bars_scale`)
      await expect(variantOption(page, 'Bars with scale')).toHaveAttribute('aria-checked', 'true')
      const texts = await chartSvg(page).evaluate(svg => [...svg.querySelectorAll('text')].map(text => text.textContent ?? ''))
      // the subtitle, the y axis (zero and signed ticks) and round years along the x axis
      expect(texts).toContain('Relative to the mean of 1971–2000 [°C]')
      expect(texts).toContain('0')
      expect(texts.some(text => /^[+\-−]\d/.test(text))).toBe(true)
      const years = texts.filter(text => /^\d{4}$/.test(text)).map(Number)
      expect(years.length).toBeGreaterThan(2)
      expect(years.every(year => year % 5 === 0)).toBe(true)
      // nothing wider than the window: no horizontal scroll on a phone
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
    }
  })

  test('take the unknown variant of a link for the stripes', async ({ page, baseURL }) => {
    await showStripes(page, baseURL!, `${PATH}&variant=pie`)
    await expect(variantOption(page, 'Stripes')).toHaveAttribute('aria-checked', 'true')
  })

  test('are above and below a zero line: the first years of a warming record are cool (down), the last warm (up)', async ({ page, baseURL }) => {
    await showStripes(page, baseURL!, `${PATH}&variant=bars`)
    const bars = await barsOnPage(page)
    const zero = await chartSvg(page).evaluate((svg) => {
      // the zero line: the one horizontal line over the width of the plot, in the zero line's colour (no grid in the bars)
      const lines = [...svg.querySelectorAll('path[fill="none"]')].filter(path => /^M[\d.]+ [\d.]+L[\d.]+ [\d.]+$/.test(path.getAttribute('d') ?? ''))
      return lines.map(line => line.getBoundingClientRect().top)
    })
    expect(zero).toHaveLength(1)
    // within a px of the bar's edge: the line is a row under the bars' base
    const first = bars[0]!
    const last = bars.at(-1)!
    expect(first.top).toBeGreaterThanOrEqual(zero[0]! - 2)
    expect(last.bottom).toBeLessThanOrEqual(zero[0]! + 2)
    expect(first.fill).not.toBe(last.fill)
  })

  test('draw the colours of precipitation as bars: brown for dry, teal for wet, from the classes of the backend', async ({ page, baseURL }) => {
    await showStripes(page, baseURL!, '/stripes?kind=precipitation&station=00011&variant=bars')
    const fills = (await barsOnPage(page)).map(bar => bar.fill)
    expect(fills.length).toBeGreaterThan(10)
    expect(fills.filter(fill => !STRIPE_PALETTES.precipitation.includes(fill))).toEqual([])
  })

  test('are saved as they are shown: the vector of the menu and the camera, with the axis and the subtitle of the scale', async ({ page, baseURL }) => {
    await showStripes(page, baseURL!, `${PATH}&variant=bars_scale`)
    await page.getByRole('button', { name: 'Download image' }).click()
    const saved = page.waitForEvent('download')
    await page.getByRole('menuitem', { name: 'Download as SVG' }).click()
    const svg = readFileSync((await (await saved).path())!, 'utf8')
    const texts = [...svg.matchAll(/<text[^>]*>([^<]*)<\/text>/g)].map(match => match[1]!)
    expect(texts).toContain('Relative to the mean of 1971–2000 [°C]')
    expect(texts).toContain('Source: Deutscher Wetterdienst')
    expect(texts).toContain('0')
    expect(svg).toContain('Climate stripes')

    const camera = page.waitForEvent('download')
    await page.getByRole('button', { name: 'Download plot as a PNG' }).click()
    const download = await camera
    expect(download.suggestedFilename()).toBe('climate_stripes_temperature_00011.png')
    const image = await imageOf(page, download)
    const frame = frameOf({ variant: 'barsScale', subtitleLines: ['Relative to the mean of 1971–2000 [°C]'] })
    const display = { showTitle: true, showYears: true, showSource: true, showDataAvailability: true }
    const high = stripesChartHeight(display, CAMERA_WIDTH, 1, { clamp: false, frame }) + extraLinesHeight(display, 1)
    expect([image.width, image.height]).toEqual([CAMERA_WIDTH * CAMERA_SCALE, high * CAMERA_SCALE])
  })

  // GH-4170: Hawkins' design has no line over the years; a link made while the page had them still loads, and draws none
  for (const variant of ['stripes', 'bars', 'bars_scale']) {
    for (const scheme of ['light', 'dark'] as const) {
      test(`draw no time series or trend line, also for a link that asks for them (${variant}, ${scheme})`, async ({ page, baseURL, context }) => {
        await context.addInitScript(mode => localStorage.setItem('nuxt-color-mode', mode), scheme)
        const strokes = (page: Page) => chartSvg(page).evaluate(svg => [...svg.querySelectorAll('path[stroke-width]')].map(path => path.getAttribute('stroke-width')))
        const dashed = (page: Page) => chartSvg(page).evaluate(svg => svg.querySelectorAll('path[stroke-dasharray]').length)
        await showStripes(page, baseURL!, `${PATH}&variant=${variant}`)
        const without = await strokes(page)
        await showStripes(page, baseURL!, `${PATH}&variant=${variant}&show_timeseries=true&show_trendline=true`)
        expect(await strokes(page)).toEqual(without)
        expect(await strokes(page)).not.toContain('4')
        expect(await dashed(page)).toBe(0)
      })
    }
  }

  test('keep the numbers of their y axis where the chart is zoomed: a zoom changes the years, not the axis', async ({ page, baseURL }) => {
    await showStripes(page, baseURL!, `${PATH}&variant=bars_scale`)
    // the numbers of the y axis are the texts right-aligned at the plot's edge (the years along the x axis are centred)
    const ticks = (page: Page) => chartSvg(page).evaluate(svg => [...svg.querySelectorAll('text[text-anchor="end"]')].map(text => text.textContent ?? ''))
    const before = await ticks(page)
    // an axis with a zero and ticks of both signs, with or without decimals: the list is not empty
    expect(before.length).toBeGreaterThan(2)
    expect(before).toContain('0')
    await page.getByRole('button', { name: 'Zoom in' }).click()
    await expect(page.getByRole('button', { name: 'Reset zoom' })).toBeEnabled()
    await expect.poll(async () => (await ticks(page)).join(',')).toBe(before.join(','))
  })

  // The switch has the longest labels in French and Czech ("Barres avec échelle", "Sloupce se stupnicí"), and ran 3 to 5 px past the
  // chart's block on a phone of 320 px
  for (const language of ['fr', 'cs', 'de', 'nl', 'pl', 'it', 'lb', 'de-hh'] as const) {
    test(`has a switch that fits the chart's block in ${language}, in a 320 px window`, async ({ page, baseURL, context }) => {
      const catalog = JSON.parse(readFileSync(fileURLToPath(new URL(`../../i18n/locales/${language}.json`, import.meta.url)), 'utf-8'))
      await context.addCookies([{ name: 'wd_lang', value: language, url: baseURL! }])
      await page.setViewportSize({ width: 320, height: 844 })
      await mockBackend(page, baseURL!)
      await page.goto(`${PATH}&variant=bars_scale`)
      await page.getByRole('button', { name: catalog.common.fetch, exact: true }).click()
      await expect(chartSvg(page)).toBeVisible()
      const place = await page.locator('.sc-controls').evaluate((controls) => {
        const box = controls.getBoundingClientRect()
        const group = controls.querySelector('[role="radiogroup"]')!.getBoundingClientRect()
        return { left: box.left, right: box.right, groupLeft: group.left, groupRight: group.right }
      })
      // 1 px: what the browser measures, not what the CSS says
      expect(place.groupRight, 'the switch ends where the chart\'s block does or before').toBeLessThanOrEqual(place.right + 1)
      expect(place.groupLeft).toBeGreaterThanOrEqual(place.left - 1)
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), 'the page does not scroll sideways').toBe(true)
      // each of the three options is whole: its text is not cut by its own box
      const cut = await variantSwitch(page).getByRole('radio').evaluateAll(options => options.filter(option => option.scrollWidth > option.clientWidth + 1).map(option => option.textContent))
      expect(cut).toEqual([])
    })
  }
})
