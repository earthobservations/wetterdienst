import type { Download, Page } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { expect, test } from '@playwright/test'
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
    const stripes = [...svg.querySelectorAll('path')].map(path => path.getAttribute('fill') ?? '').filter(fill => fill.startsWith('rgb('))
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

  async function menu(page: Page, item: string) {
    await page.getByRole('button', { name: 'Download image' }).click()
    const saved = page.waitForEvent('download')
    await page.getByRole('menuitem', { name: item }).click()
    return saved
  }

  test('is the light one and the size of the chart on the page times three, from the menu', async ({ page, baseURL }) => {
    await showStripes(page, baseURL!)
    const shown = (await page.locator('.sc-canvas').boundingBox())!
    for (const [item, extension] of [['Download as PNG', 'png'], ['Download as JPG', 'jpeg']] as const) {
      const download = await menu(page, item)
      expect(download.suggestedFilename()).toMatch(new RegExp(`^climate_stripes_temperature_00011_.+\\.${extension}$`))
      const image = await imageOf(page, download)
      expect(luminance(image.corner), `the saved image is light (its corner is ${image.corner})`).toBeGreaterThan(0.9)
      expect(image.width).toBe(Math.round(shown.width) * 3)
      expect(image.height).toBe(600 * 3)
      // the chart on the page is as dark as it was
      await expect(canvas(page)).toHaveAttribute('data-chart-scheme', 'dark')
    }
  })

  test('is a vector of the size of the chart from the menu, with the light chart\'s colours', async ({ page, baseURL }) => {
    await showStripes(page, baseURL!)
    const download = await menu(page, 'Download as SVG')
    expect(download.suggestedFilename()).toMatch(/^climate_stripes_temperature_00011_.+\.svg$/)
    const svg = readFileSync((await download.path())!, 'utf8')
    expect(svg).toMatch(/<svg width="\d+" height="600"/)
    expect(svg).toContain('Climate stripes')
    // the dark theme's text colour is not in it
    const dark = (await paintOf(page)).texts.find(text => text.text === '2024')!.fill
    expect(svg).not.toContain(dark.replaceAll(' ', ''))
  })

  test('is 2800 by 1400 px, and light, from the camera of the toolbar, named for the station', async ({ page, baseURL }) => {
    await showStripes(page, baseURL!)
    const saved = page.waitForEvent('download')
    await page.getByRole('button', { name: 'Download plot as a PNG' }).click()
    const download = await saved
    expect(download.suggestedFilename()).toBe('climate_stripes_temperature_00011.png')
    const image = await imageOf(page, download)
    expect(luminance(image.corner)).toBeGreaterThan(0.9)
    expect([image.width, image.height]).toEqual([2800, 1400])
    await expect(canvas(page)).toHaveAttribute('data-chart-scheme', 'dark')
  })

  test('is 1400 by 600 times two without a title', async ({ page, baseURL }) => {
    await showStripes(page, baseURL!, `${PATH}&show_title=false`)
    const saved = page.waitForEvent('download')
    await page.getByRole('button', { name: 'Download plot as a PNG' }).click()
    const image = await imageOf(page, await saved)
    expect([image.width, image.height]).toEqual([2800, 1200])
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
