import type { Page } from '@playwright/test'
import { expect, test } from '@playwright/test'
import { ApiFailure, defaultHandlers, isSnowRequest, mockBackend } from './accessibility/mock-backend'

// The snow panel of the forecast (GH-4091): for the 15 stations that have DWD's MOSMIX-SNOW, the meteogram gets three plots on
// its time axis (the new snow as bars, the snow depth and the chance of more than 10 cm as lines) with their source named under
// the chart. Another station looks as it did. The API is answered by the mock backend (a snow forecast for Z901 and Z914 with
// values at hours between the steps that the panel must leave out, a forecast for the rest), so the spec needs nothing but the app.

const SNOW_STATION = '/meteogram?station=Z914&view=chart'
const OTHER_STATION = '/meteogram?station=10384&view=chart'

const svg = (page: Page) => page.locator('.mg-canvas svg').first()
const figure = (page: Page) => page.getByRole('figure').first()
const readout = (page: Page) => page.getByTestId('meteogram-readout')
const announced = (page: Page) => page.getByTestId('meteogram-announce')
const credit = (page: Page) => page.getByTestId('meteogram-snow-credit')
const toggle = (page: Page, panel: string) => page.locator(`button[data-panel="${panel}"]`)

// the threshold and its unit are one word (no-break space), as the readout, the table and the titles write them
const CHANCE = '>10\u00A0cm new'
const READOUT_CHANCE = 'Chance of > 10\u00A0cm new snow in 24\u00A0h'
const READOUT_NEW = 'New snow, 3\u00A0h'

// the room a title keeps in its plot in Chromium, where the choice of the languages that say "new" was measured: 8 %
const HEADROOM = 1.08

const INDIGO = { light: '#4f46e5', dark: '#818cf8' }

async function open(page: Page, baseURL: string, path = SNOW_STATION, size?: { width: number, height: number }, override: Parameters<typeof mockBackend>[2] = {}) {
  if (size)
    await page.setViewportSize(size)
  const backend = await mockBackend(page, baseURL, override)
  await page.goto(path)
  await expect(svg(page)).toBeVisible()
  await expect(svg(page).locator('text').first()).toBeVisible()
  return backend
}

/** The snow request answered by `answer`, every other one as the default mock does */
function snowAnswers(answer: (url: URL) => unknown) {
  const defaults = defaultHandlers()
  return { values: (url: URL, route: any) => isSnowRequest(url) ? answer(url) : defaults.values!(url, route) }
}

/** The texts of the SVG that are an axis title: turned to read upwards, in the colour they are drawn in */
async function titles(page: Page) {
  return svg(page).locator('text').evaluateAll(texts => texts.map((text) => {
    const matrix = text.getScreenCTM()
    const turned = !!matrix && Math.abs(matrix.b) / Math.hypot(matrix.a, matrix.b) > 0.9
    const box = text.getBoundingClientRect()
    return { text: text.textContent ?? '', turned, fill: text.getAttribute('fill') ?? '', top: box.top, bottom: box.bottom, left: box.left, right: box.right }
  }).filter(entry => entry.turned))
}

/** The boxes of the bars of the new snow: the paths of the SVG painted in the colour of the series */
async function bars(page: Page, colour: string) {
  return svg(page).locator(`path[fill="${colour}"]`).evaluateAll(paths => paths.map((path) => {
    const box = path.getBoundingClientRect()
    return { left: box.left, right: box.right, top: box.top, bottom: box.bottom, width: box.width, height: box.height }
  }))
}

// WCAG 2.x relative luminance, and the contrast ratio of two colours
function channels(color: string) {
  const hex = /^#([\da-f]{2})([\da-f]{2})([\da-f]{2})$/i.exec(color)
  if (hex)
    return [1, 2, 3].map(i => Number.parseInt(hex[i]!, 16))
  const rgb = /^rgba?\(\s*(\d+)[\s,]+(\d+)[\s,]+(\d+)/.exec(color)!
  return [1, 2, 3].map(i => Number(rgb[i]))
}
function luminance(color: string) {
  const [r, g, b] = channels(color).map(c => c / 255).map(c => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4))
  return 0.2126 * r! + 0.7152 * g! + 0.0722 * b!
}
function contrast(a: string, b: string) {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi! + 0.05) / (lo! + 0.05)
}
/** What the chart lies on: the background of the card that holds it, as the browser paints it */
function paperOf(page: Page) {
  return page.locator('.mg-canvas').evaluate((canvas) => {
    for (let element: Element | null = canvas; element; element = element.parentElement) {
      const color = getComputedStyle(element).backgroundColor
      if (color && color !== 'rgba(0, 0, 0, 0)' && color !== 'transparent')
        return color
    }
    return 'rgb(255, 255, 255)'
  })
}

test.describe('at a station that has a snow forecast', () => {
  test('draws the three plots, titled and in their colours, with the toggle on and the source named under the chart', async ({ page, baseURL }) => {
    const backend = await open(page, baseURL!)
    await expect(toggle(page, 'snow')).toHaveAttribute('aria-pressed', 'true')
    await expect(toggle(page, 'snow')).toHaveAccessibleName('Snow')
    const found = await titles(page)
    expect(found.map(entry => entry.text)).toEqual(expect.arrayContaining(['New snow', 'Snow depth', CHANCE]))
    // the titles are in the colours of the label of the series, which the chart's axes' text has
    expect(found.find(entry => entry.text === 'New snow')!.fill).toBe(INDIGO.light)
    await expect(credit(page)).toHaveText('Snow forecast from MOSMIX-SNOW, DWD.')
    // beside the symbols' credit, not instead of it
    await expect(page.getByTestId('meteogram-credit')).toBeVisible()
    // every request was one the mock answers
    expect(backend.unanswered).toEqual([])
  })

  test('draws a bar for the new snow of the steps of 3 hours, 27 px wide at 10 px an hour, and leaves out the hours between', async ({ page, baseURL }) => {
    await open(page, baseURL!, SNOW_STATION, { width: 1280, height: 900 })
    const drawn = await bars(page, INDIGO.light)
    // snow falls for 18 hours of the run: a bar for each of the 6 steps in it; a step with none has none
    expect(drawn.length).toBeGreaterThanOrEqual(5)
    expect(drawn.length).toBeLessThanOrEqual(8)
    for (const bar of drawn) {
      // the 3 hours of a step at the width of an hour, less a tenth between the bars: 10 px each
      expect(bar.width, JSON.stringify(bar)).toBeGreaterThan(24)
      expect(bar.width, JSON.stringify(bar)).toBeLessThan(31)
      expect(bar.height, JSON.stringify(bar)).toBeLessThan(72)
    }
    // the hours between the steps have "40 cm" of new snow in the mock: drawn, they would stretch the axis to 46 cm and the real
    // bars (5.4 cm at most) would be 8 px high. The tallest stands over half the plot
    expect(Math.max(...drawn.map(bar => bar.height))).toBeGreaterThan(40)
    // the bars stand 3 hours apart
    const lefts = drawn.map(bar => bar.left).sort((a, b) => a - b)
    for (let i = 1; i < lefts.length; i++) {
      const steps = (lefts[i]! - lefts[i - 1]!) / 30
      expect(Math.abs(steps - Math.round(steps)), `${lefts[i]! - lefts[i - 1]!} px apart`).toBeLessThan(0.1)
    }
  })

  // ECharts 6 widened the x extent of the plots that carry bars (`containShape`), which put the snow plot's hours up to 15 px off
  // the others' at the start of a 72 h chart (and the precipitation's 5 px): the same instant must be at the same pixel in every plot
  test('puts the same instant at the same pixel in every plot: the line of now, which each plot has', async ({ page, baseURL }) => {
    for (const width of [800, 1280]) {
      await open(page, baseURL!, SNOW_STATION, { width, height: 900 })
      const xs = await svg(page).locator('path[stroke="rgb(234,88,12)"]').evaluateAll(paths => paths.map(path => path.getBoundingClientRect().left + path.getBoundingClientRect().width / 2))
      // a line in each of the 8 plots (the header has none)
      expect(xs.length, `${width} px`).toBe(8)
      expect(Math.max(...xs) - Math.min(...xs), `${width} px: ${xs.join(', ')}`).toBeLessThan(0.6)
    }
  })

  test('draws each bar over the hours it covers: it ends where the hour label of its step is, and fills its window', async ({ page, baseURL }) => {
    await open(page, baseURL!, SNOW_STATION, { width: 1280, height: 900 })
    // zoomed to a few hours round the 12th hour, where it snows in the mock (the zoom keeps the crosshair where it is): the axis labels
    // every hour
    await figure(page).focus()
    await page.keyboard.press('Home')
    for (let i = 0; i < 12; i++)
      await page.keyboard.press('ArrowRight')
    for (let i = 0; i < 5; i++)
      await page.keyboard.press('+')
    await page.keyboard.press('Escape')
    await page.waitForTimeout(400)
    const hourPx = await svg(page).locator('text').filter({ hasText: /^\d{2}[:.]\d{2}$/ }).evaluateAll((texts) => {
      const xs = texts.map(text => text.getBoundingClientRect().left + text.getBoundingClientRect().width / 2).sort((a, b) => a - b)
      return xs[1]! - xs[0]!
    })
    expect(hourPx, 'the labels are an hour apart').toBeGreaterThan(40)
    const labelXs = await svg(page).locator('text').filter({ hasText: /^\d{2}[:.]\d{2}$/ }).evaluateAll(texts => texts.map(text => text.getBoundingClientRect().left + text.getBoundingClientRect().width / 2))
    const whole = (all: { left: number, right: number, width: number }[], hours: number) => all.filter(bar => Math.abs(bar.width - 0.9 * hours * hourPx) < 1)
    const snow = whole(await bars(page, INDIGO.light), 3)
    // the precipitation is rain, mixed or snow by the temperature of the hour: the bars of all three
    const rain = whole([...await bars(page, '#3b82f6'), ...await bars(page, '#0ea5e9'), ...await bars(page, '#cbd5e1')], 1)
    expect(snow.length, 'whole bars of the new snow in the window').toBeGreaterThan(0)
    expect(rain.length, 'whole bars of the precipitation in the window').toBeGreaterThan(0)
    // a bar of a window (T - w, T] ends a tenth of its window before the label of T (it is 0.9 of it, centred on its middle)
    for (const [bars, hours] of [[snow, 3], [rain, 1]] as const) {
      for (const bar of bars) {
        const gap = Math.min(...labelXs.map(x => Math.abs(x - (bar.right + 0.05 * hours * hourPx))))
        expect(gap, `a bar of ${hours} h ends at ${bar.right}, labels at ${labelXs.join(', ')}`).toBeLessThan(2)
      }
    }
  })

  test('zooms with the other panels: the bars widen with the hours, as the keys zoom the whole chart', async ({ page, baseURL }) => {
    await open(page, baseURL!, SNOW_STATION, { width: 1280, height: 900 })
    // the widest bar: one at the edge of the window is cut by it
    const widest = async () => Math.max(0, ...(await bars(page, INDIGO.light)).map(bar => bar.width))
    const before = await widest()
    await figure(page).focus()
    await page.keyboard.press('+')
    await page.keyboard.press('+')
    await expect.poll(widest).toBeGreaterThan(before * 1.8)
    await page.keyboard.press('0')
    await expect.poll(widest).toBeCloseTo(before, 0)
  })

  test('reads the three values of an hour that has them in the readout, and none of an hour between', async ({ page, baseURL }) => {
    await open(page, baseURL!, SNOW_STATION, { width: 1280, height: 900 })
    await figure(page).focus()
    // twelve hours in a row: every third has the snow's values, which the live region says as well
    const hours: boolean[] = []
    for (let i = 0; i < 24; i++) {
      await page.keyboard.press('ArrowRight')
      await expect(readout(page)).toBeVisible()
      const text = (await readout(page).textContent())!
      const sentence = (await announced(page).textContent())!
      const has = text.includes(READOUT_NEW)
      hours.push(has)
      expect(sentence.includes(READOUT_NEW), sentence).toBe(has)
      if (has) {
        expect(text).toContain('Snow depth')
        expect(text).toContain(READOUT_CHANCE)
        // in the units of the answer: centimetres, and percent
        expect(text).toMatch(/Snow depth\s*\d+(\.\d)? cm/)
        expect(text).toMatch(new RegExp(`${READOUT_CHANCE}\\s*\\d+%`))
      }
      else {
        expect(text).not.toContain('Snow depth')
        expect(text).not.toContain('Chance of')
      }
    }
    // 24 hours in a row have 8 steps of 3 hours, every third one
    expect(hours.filter(Boolean)).toHaveLength(8)
    const steps = hours.flatMap((has, i) => has ? [i] : [])
    expect(new Set(steps.slice(1).map((step, i) => step - steps[i]!))).toEqual(new Set([3]))
  })

  test('is taken away and given back by its toggle, with the credit', async ({ page, baseURL }) => {
    await open(page, baseURL!)
    await toggle(page, 'snow').click()
    await expect(toggle(page, 'snow')).toHaveAttribute('aria-pressed', 'false')
    await expect.poll(async () => (await titles(page)).map(entry => entry.text)).not.toContain('New snow')
    await expect(credit(page)).toHaveCount(0)
    // the link says it
    await expect(page).toHaveURL(/panels=temp%2Cwind%2Cprecip%2Ccloud%2Cpressure|panels=temp,wind,precip,cloud,pressure/)
    await toggle(page, 'snow').click()
    await expect.poll(async () => (await titles(page)).map(entry => entry.text)).toContain('New snow')
    await expect(credit(page)).toBeVisible()
  })

  test('opens from a link that has it off', async ({ page, baseURL }) => {
    await open(page, baseURL!, `${SNOW_STATION}&panels=temp,wind,precip,cloud,pressure`)
    await expect(toggle(page, 'snow')).toHaveAttribute('aria-pressed', 'false')
    expect((await titles(page)).map(entry => entry.text)).not.toContain('New snow')
    await expect(credit(page)).toHaveCount(0)
  })

  test('is in the table of the values, with the steps of 3 hours', async ({ page, baseURL }) => {
    await page.setViewportSize({ width: 1280, height: 900 })
    await mockBackend(page, baseURL!)
    await page.goto(SNOW_STATION.replace('chart', 'table'))
    const table = page.getByRole('table').first()
    await expect(table).toBeVisible()
    await expect(table.getByRole('columnheader', { name: 'New snow cm' })).toBeVisible()
    await expect(table.getByRole('columnheader', { name: 'Snow depth cm' })).toBeVisible()
    await expect(table.getByRole('columnheader', { name: /Chance of > 10\s*cm new snow in 24\s*h %/ })).toBeVisible()
  })
})

test.describe('at another station', () => {
  test('looks as it did: no toggle, no plot, no credit, and no request for snow values', async ({ page, baseURL }) => {
    const snowValuesRequested: string[] = []
    page.on('request', (request) => {
      if (request.url().includes('hourly%2Fsnow%2F') || request.url().includes('hourly/snow/'))
        snowValuesRequested.push(request.url())
    })
    const backend = await open(page, baseURL!, OTHER_STATION)
    await page.waitForLoadState('networkidle')
    await expect(toggle(page, 'snow')).toHaveCount(0)
    expect((await titles(page)).map(entry => entry.text)).not.toContain('New snow')
    await expect(credit(page)).toHaveCount(0)
    expect(snowValuesRequested).toEqual([])
    expect(backend.unanswered).toEqual([])
    // the link of a panel that is off does not name the snow one
    await toggle(page, 'wind').click()
    await expect(page).toHaveURL(/panels=temp(%2C|,)precip(%2C|,)cloud(%2C|,)pressure(&|$)/)
  })
})

test.describe('where the snow forecast is not to be had', () => {
  test('out of season (a 404, ProductOutOfSeasonError) draws no panel and shows no error', async ({ page, baseURL }) => {
    await open(page, baseURL!, SNOW_STATION, undefined, snowAnswers(() => new ApiFailure(404, 'No MOSMIX-SNOW run is listed: DWD publishes it from November to April only', { type: 'ProductOutOfSeasonError' })))
    await page.waitForLoadState('networkidle')
    await expect(toggle(page, 'snow')).toHaveCount(0)
    await expect(page.getByRole('alert')).toHaveCount(0)
    expect((await titles(page)).map(entry => entry.text)).not.toContain('New snow')
    // the forecast is there, whole
    await expect(toggle(page, 'temp')).toHaveAttribute('aria-pressed', 'true')
    expect((await titles(page)).map(entry => entry.text)).toContain('Temp')
  })

  test('a failure of the snow request (a 502) leaves the rest of the forecast, with no panel and no error', async ({ page, baseURL }) => {
    await open(page, baseURL!, SNOW_STATION, undefined, snowAnswers(() => new ApiFailure(502, 'DWD could not be reached')))
    await page.waitForLoadState('networkidle')
    await expect(toggle(page, 'snow')).toHaveCount(0)
    await expect(page.getByRole('alert')).toHaveCount(0)
    expect((await titles(page)).map(entry => entry.text)).toContain('Temp')
  })

  test('a failure of the list of the snow stations does the same', async ({ page, baseURL }) => {
    const defaults = defaultHandlers()
    await open(page, baseURL!, SNOW_STATION, undefined, {
      stations: (url, route) => url.searchParams.get('parameters') === 'hourly/snow' ? new ApiFailure(500, 'Upstream failed') : defaults.stations!(url, route),
    })
    await page.waitForLoadState('networkidle')
    await expect(toggle(page, 'snow')).toHaveCount(0)
    await expect(page.getByRole('alert')).toHaveCount(0)
    expect((await titles(page)).map(entry => entry.text)).toContain('Temp')
  })
})

test.describe('the colours', () => {
  for (const scheme of ['light', 'dark'] as const) {
    test(`keep 3:1 for the bars and 4.5:1 for the text against the paper, in the ${scheme} scheme`, async ({ page, baseURL, context }) => {
      await context.addInitScript(mode => localStorage.setItem('nuxt-color-mode', mode), scheme)
      await open(page, baseURL!, SNOW_STATION, { width: 1280, height: 900 })
      await expect(page.locator('.mg-canvas')).toHaveAttribute('data-chart-scheme', scheme)
      const paper = await paperOf(page)
      const drawn = await bars(page, INDIGO[scheme])
      expect(drawn.length, 'bars in the colour of the scheme').toBeGreaterThan(3)
      expect(contrast(INDIGO[scheme], paper), `bars on ${paper}`).toBeGreaterThanOrEqual(3)
      // the lines: the colours the series are drawn in, read from the SVG
      const strokes = await svg(page).locator('path[stroke]').evaluateAll(paths => [...new Set(paths.map(path => path.getAttribute('stroke') ?? ''))])
      for (const stroke of strokes.filter(color => color.startsWith('#') && ['#0f766e', '#2dd4bf', '#b45309', '#daa520'].includes(color)))
        expect(contrast(stroke, paper), `${stroke} on ${paper}`).toBeGreaterThanOrEqual(3)
      expect(strokes.some(color => ['#0f766e', '#2dd4bf'].includes(color)), 'the snow depth line').toBe(true)
      expect(strokes.some(color => ['#b45309', '#daa520'].includes(color)), 'the chance line').toBe(true)
      // the text that names the series: the three titles and the tick labels of the three axes
      const labels = (await svg(page).locator('text').evaluateAll(texts => texts.map(text => ({ text: text.textContent ?? '', fill: text.getAttribute('fill') ?? '' }))))
        .filter(entry => ['#4f46e5', '#818cf8', '#0f766e', '#2dd4bf', '#b45309', '#daa520'].includes(entry.fill))
      expect(labels.length).toBeGreaterThan(6)
      for (const label of labels)
        expect(contrast(label.fill, paper), `${label.text} (${label.fill}) on ${paper}`).toBeGreaterThanOrEqual(4.5)
    })
  }
})

test.describe('on a phone', () => {
  for (const width of [320, 390]) {
    test(`keeps the titles of the snow plots inside their plots and left of their tick labels at ${width} px, and does not scroll the page sideways`, async ({ page, baseURL }) => {
      await open(page, baseURL!, SNOW_STATION, { width, height: 844 })
      const found = await titles(page)
      const stage = (await page.locator('.mg-stage').boundingBox())!
      // the tick labels of the plots: the numbers that are not turned
      const numbers = await svg(page).locator('text').evaluateAll(texts => texts.map((text) => {
        const matrix = text.getScreenCTM()
        const turned = !!matrix && Math.abs(matrix.b) / Math.hypot(matrix.a, matrix.b) > 0.9
        const box = text.getBoundingClientRect()
        return { text: text.textContent ?? '', turned, left: box.left, right: box.right, top: box.top, bottom: box.bottom }
      }).filter(entry => !entry.turned && /^[-\d.,]+$/.test(entry.text) && entry.right < 100))
      for (const name of ['New snow', 'Snow depth', CHANCE]) {
        const title = found.find(entry => entry.text === name)
        expect(title, name).toBeDefined()
        expect(title!.left, `${name} is cut at the left`).toBeGreaterThanOrEqual(stage.x - 0.5)
        // left of the tick labels of its own plot (GH-4132: each title is next to its own labels, not at the left edge for all): the two
        // labels nearest to the middle of the title
        const middleOf = (entry: { top: number, bottom: number }) => (entry.top + entry.bottom) / 2
        const own = [...numbers].sort((a, b) => Math.abs(middleOf(a) - middleOf(title!)) - Math.abs(middleOf(b) - middleOf(title!))).slice(0, 2)
        expect(own.length, `${name} has labels beside it`).toBe(2)
        expect(title!.right, `${name} is under the labels`).toBeLessThanOrEqual(Math.min(...own.map(label => label.left)) + 0.5)
      }
      // each title lies inside the rows of its own plot (72 px high each), and never on the plot above or below
      const rows = await page.evaluate((chance) => {
        const texts = [...document.querySelectorAll<SVGTextElement>('.mg-canvas svg text')]
        const unit = (label: string) => texts.find(text => text.textContent === label)!.getBoundingClientRect()
        return { snow: unit('New snow'), depth: unit('Snow depth'), chance: unit(chance) }
      }, CHANCE)
      expect(rows.snow.height, 'New snow').toBeLessThanOrEqual(72)
      expect(rows.depth.height, 'Snow depth').toBeLessThanOrEqual(72)
      expect(rows.chance.height, CHANCE).toBeLessThanOrEqual(72)
      expect(rows.snow.bottom).toBeLessThan(rows.depth.top)
      expect(rows.depth.bottom).toBeLessThan(rows.chance.top)
      expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(0)
      // the credit wraps in the card and is not cut
      const box = (await credit(page).boundingBox())!
      expect(box.x).toBeGreaterThanOrEqual(0)
      expect(box.x + box.width).toBeLessThanOrEqual(width)
    })
  }

  test('has the readout of a snow hour inside the chart at 390 px, with the three values', async ({ page, baseURL }) => {
    await open(page, baseURL!, SNOW_STATION, { width: 390, height: 844 })
    await figure(page).focus()
    // to the first hour that has the snow: at most three keys
    let text = ''
    for (let i = 0; i < 4 && !text.includes('New snow'); i++) {
      await page.keyboard.press('ArrowRight')
      await expect(readout(page)).toBeVisible()
      text = (await readout(page).textContent())!
    }
    expect(text).toContain(READOUT_NEW)
    expect(text).toContain('Snow depth')
    expect(text).toContain(READOUT_CHANCE)
    const stage = (await page.locator('.mg-stage').boundingBox())!
    const box = (await readout(page).boundingBox())!
    expect(box.x).toBeGreaterThanOrEqual(stage.x - 0.5)
    expect(box.x + box.width).toBeLessThanOrEqual(stage.x + stage.width + 0.5)
  })

  test('scrolls with the axes in view: the snow plots are one with the others', async ({ page, baseURL }) => {
    await open(page, baseURL!, SNOW_STATION, { width: 390, height: 844 })
    const strip = page.getByTestId('meteogram-scroller')
    expect(await strip.evaluate(element => element.scrollWidth > element.clientWidth)).toBe(true)
    const before = (await titles(page)).find(entry => entry.text === 'New snow')!
    const firstHours = await svg(page).locator('text').filter({ hasText: /^\d{2}[:.]\d{2}$/ }).allTextContents()
    await strip.evaluate((element) => {
      element.scrollLeft = 300
    })
    // the window moved, and the snow plots with the rest of the chart: other hours are labelled
    await expect.poll(async () => (await svg(page).locator('text').filter({ hasText: /^\d{2}[:.]\d{2}$/ }).allTextContents()).join()).not.toBe(firstHours.join())
    const after = (await titles(page)).find(entry => entry.text === 'New snow')!
    expect(Math.round(after.left)).toBe(Math.round(before.left))
  })
})

// A title is turned to read up the plot, so its length is bounded by the height of the plot it names: 72 px for the new snow and the
// depth and the chance. In whichever browser runs, a title must fit its plot (a longer one runs onto the plot next to it).
// The 8 % of room (`HEADROOM`) is not a bound of the browser that runs: it is how the languages that say "new" in the chance's title
// were chosen, from measurements in Chrome, whose font is about 6 % narrower than Firefox's. It is held in Chromium alone, where
// those measurements were made; Firefox measures its own wider font against the plot itself.
test.describe('the titles in every language, at 320 px', () => {
  const LANGUAGES = ['en', 'de', 'de-hh', 'es', 'fr', 'it', 'lb', 'nl', 'pl', 'cs', 'da']
  for (const language of LANGUAGES) {
    test(`fit the plots they name in ${language}`, async ({ page, baseURL, context, browserName }) => {
      await context.addCookies([{ name: 'wd_lang', value: language, url: baseURL! }])
      await open(page, baseURL!, SNOW_STATION, { width: 320, height: 844 })
      // the lines of the titles, turned: those of one plot have the one centre; the plots from the top are wind, precipitation,
      // the new snow, the depth, the chance, the clouds, the temperature and the pressure
      const plots = await page.evaluate(() => {
        const found = [...document.querySelectorAll<SVGTextElement>('.mg-canvas svg text')].flatMap((text) => {
          const matrix = text.getScreenCTM()
          if (!matrix || Math.abs(matrix.b) / Math.hypot(matrix.a, matrix.b) <= 0.9)
            return []
          const box = text.getBoundingClientRect()
          return box.left < document.querySelector('.mg-stage')!.getBoundingClientRect().left + 40 ? [{ centre: Math.round((box.top + box.bottom) / 2), height: box.height }] : []
        })
        const byCentre = new Map<number, number>()
        for (const { centre, height } of found) {
          const key = [...byCentre.keys()].find(known => Math.abs(known - centre) <= 2) ?? centre
          byCentre.set(key, Math.max(byCentre.get(key) ?? 0, height))
        }
        return [...byCentre.entries()].sort(([a], [b]) => a - b).map(([, height]) => height)
      })
      expect(plots).toHaveLength(8)
      // the height of the plot each title names, as the layout gives it
      const room = 72
      expect(plots[2]!, 'the new snow').toBeLessThanOrEqual(room)
      expect(plots[3]!, 'the depth').toBeLessThanOrEqual(room)
      expect(plots[4]!, 'the chance').toBeLessThanOrEqual(room)
      if (browserName === 'chromium') {
        expect(plots[2]!, 'the new snow, with room to spare').toBeLessThanOrEqual(room / HEADROOM)
        expect(plots[3]!, 'the depth, with room to spare').toBeLessThanOrEqual(room / HEADROOM)
        expect(plots[4]!, 'the chance, with room to spare').toBeLessThanOrEqual(room / HEADROOM)
      }
    })
  }
})

test.describe('on paper', () => {
  test('has the whole snow panel in its chart box, with its tick labels and its credit', async ({ page, baseURL }) => {
    await open(page, baseURL!, SNOW_STATION, { width: 1440, height: 1000 })
    await page.emulateMedia({ media: 'print' })
    const layout = await page.evaluate((chance) => {
      const chart = document.querySelector('.mg-canvas svg')!
      const box = chart.parentElement!.getBoundingClientRect()
      const drawn = chart.getBoundingClientRect()
      const texts = [...chart.querySelectorAll('text')]
      const find = (label: string) => texts.find(text => text.textContent?.trim() === label)?.getBoundingClientRect()
      const snowCredit = document.querySelector('[data-testid="meteogram-snow-credit"]')!.getBoundingClientRect()
      return {
        boxHeight: box.height,
        drawnHeight: drawn.height,
        titles: ['New snow', 'Snow depth', chance].map(label => ({ label, rect: find(label) ? { top: find(label)!.top, bottom: find(label)!.bottom } : null })),
        box: { top: box.top, bottom: box.bottom },
        credit: { top: snowCredit.top, height: snowCredit.height, width: snowCredit.width },
      }
    }, CHANCE)
    expect(layout.boxHeight).toBeGreaterThanOrEqual(layout.drawnHeight - 1)
    for (const { label, rect } of layout.titles) {
      expect(rect, `${label} is drawn`).not.toBeNull()
      expect(rect!.top, `${label} is inside the chart box`).toBeGreaterThanOrEqual(layout.box.top - 1)
      expect(rect!.bottom, `${label} is inside the chart box`).toBeLessThanOrEqual(layout.box.bottom + 1)
    }
    // the source is printed, under the chart
    expect(layout.credit.height).toBeGreaterThan(0)
    expect(layout.credit.top).toBeGreaterThanOrEqual(layout.box.bottom - 1)
  })
})
