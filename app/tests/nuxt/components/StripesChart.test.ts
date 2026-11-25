import { mockNuxtImport, mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import StripesChart from '~/components/StripesChart.vue'
import { extraLinesHeight, frameOf, stripesChartHeight } from '~/utils/stripes-option'
import { recordOf, stripesAnswer } from '../../helpers/stripes-answer'

// ECharts draws nothing in the test's document: the chart on the page is a recorder, held to the option it is given. A chart
// that has no element to draw into (the copy a saved image is made of) is the real library, drawing to an SVG string.
const echarts = vi.hoisted(() => {
  const chart = {
    on: vi.fn(),
    resize: vi.fn(),
    setOption: vi.fn(),
    getDom: vi.fn(),
    dispose: vi.fn(),
  }
  const state = { realInit: null as null | ((...args: any[]) => any), loadFails: false }
  const init = vi.fn((element: HTMLElement | null, ...rest: unknown[]) => {
    if (element === null)
      return state.realInit!(null, ...rest)
    chart.getDom.mockReturnValue(element)
    return chart
  })
  return { chart, init, state }
})
vi.mock('~/utils/echarts-loader', async () => {
  const actual = await vi.importActual<typeof import('~/utils/echarts-loader')>('~/utils/echarts-loader')
  const real = actual.loadEcharts()
  echarts.state.realInit = (element: null, theme: unknown, options: unknown) => real.init(element as any, theme as any, options as any)
  return {
    loadEcharts: () => {
      if (echarts.state.loadFails)
        throw new Error('chunk gone')
      return { init: echarts.init }
    },
  }
})

// the saved image: its rasterising needs a canvas, which the test's document has not
const image = vi.hoisted(() => ({
  svgToBlob: vi.fn(async (_svg: string, _options: Record<string, unknown>) => new Blob(['image'])),
  downloadBlob: vi.fn((_blob: Blob, _filename: string) => {}),
}))
vi.mock('~/utils/chart-image', () => image)

// the toast that tells a failure
const { toastAdd } = vi.hoisted(() => ({ toastAdd: vi.fn() }))
mockNuxtImport('useToast', () => () => ({ add: toastAdd }))

// the light theme a saved image is drawn in: its text is a colour of its own, which the theme of the page (dark, as the test has it) is not
const LIGHT_TEXT = 'rgb(1, 2, 3)'
vi.mock('~/utils/chart-theme', async (importOriginal) => {
  const original = await importOriginal<typeof import('~/utils/chart-theme')>()
  return {
    ...original,
    readDocumentChartTheme: vi.fn((scheme?: 'light' | 'dark') => scheme === 'light'
      ? { ...original.EMPTY_CHART_THEME, text: LIGHT_TEXT, textMuted: LIGHT_TEXT, paper: 'rgb(255, 255, 255)' }
      : { ...original.EMPTY_CHART_THEME, dark: true, text: 'rgb(250, 250, 250)', textMuted: 'rgb(250, 250, 250)', paper: 'rgb(0, 0, 0)' }),
  }
})

// Nuxt's reload of the page: the test's document does not take it
const { reloadNuxtApp } = vi.hoisted(() => ({ reloadNuxtApp: vi.fn() }))
mockNuxtImport('reloadNuxtApp', () => reloadNuxtApp)

// 1950 to 2024 without 1962 to 1964; the value of a year is its distance from 1950 in tenths of a degree, classed against the
// whole record as the backend does (the mean of 1971 to 2000 is the centre)
const ANSWER = stripesAnswer(recordOf(1950, 2024, year => (year - 1950) / 10, [1962, 1963, 1964]))
const VALUES = ANSWER.values
const REFERENCE = ANSWER.reference
const DISPLAY = { showTitle: true, showYears: true, showSource: true, showDataAvailability: true }
const TITLE = 'Climate stripes (Temperature) for Donaueschingen, Germany (00011)'

type Mounted = Awaited<ReturnType<typeof mountSuspended>>
let wrapper: Mounted | undefined

async function showChart(props: Record<string, unknown> = {}) {
  wrapper = await mountSuspended(StripesChart, {
    props: { values: VALUES, reference: REFERENCE, kind: 'temperature', unit: '°C', title: TITLE, display: DISPLAY, label: TITLE, cameraFile: 'climate_stripes_temperature_00011', ...props },
    attachTo: document.body,
  })
  // the first mount of the file loads the language and the component's parts, which a loaded machine takes longer over than vitest's second
  await vi.waitFor(() => expect(echarts.chart.setOption).toHaveBeenCalled(), { timeout: 5000 })
  await flushPromises()
  return wrapper
}

// the test's document has no layout: the chart is 800 px wide, the plot from 20 to 780 px, a stripe is 760 / 75 px wide
const PLOT_LEFT = 20
const PLOT_WIDTH = 760
const xOfYear = (year: number, start = 1949.5, end = 2024.5) => PLOT_LEFT + ((year - start) / (end - start)) * PLOT_WIDTH
const stage = () => document.body.querySelector<HTMLElement>('.sc-stage')!
const readout = () => document.body.querySelector<HTMLElement>('[data-testid="stripes-readout"]')
const announce = () => document.body.querySelector('[data-testid="stripes-announce"]')!.textContent?.trim()
const lastOption = () => echarts.chart.setOption.mock.calls.at(-1)![0] as any
const drawn = () => echarts.chart.setOption.mock.calls.filter(([, flags]) => flags?.notMerge).length
function lastZoom() {
  const call = echarts.chart.setOption.mock.calls.filter(([option]) => option.dataZoom && !option.grid).at(-1)![0]
  return { start: call.dataZoom[0].startValue as number, end: call.dataZoom[0].endValue as number, labels: call.series[0] }
}

// a pointer event as a browser gives it; happy-dom has the class and not every field
// the stripes of a chart of 800 px with a title and the availability line are 578 px high (GH-4133: 16:9 stripes, 428 px, and the
// margins on top of them) and run from 50 to 478 px
const STRIPES_MIDDLE = 300
function pointer(type: string, init: { clientX?: number, clientY?: number, pointerType?: string, button?: number } = {}) {
  const event = new MouseEvent(type, { bubbles: true, cancelable: true, clientX: init.clientX ?? 0, clientY: init.clientY ?? STRIPES_MIDDLE, button: init.button ?? 0 })
  Object.defineProperty(event, 'pointerType', { value: init.pointerType ?? 'mouse' })
  Object.defineProperty(event, 'pointerId', { value: 1 })
  return event
}
function movePointerTo(x: number, y = STRIPES_MIDDLE) {
  stage().dispatchEvent(pointer('pointermove', { clientX: x, clientY: y }))
}
function key(name: string, init: KeyboardEventInit = {}) {
  stage().dispatchEvent(new KeyboardEvent('keydown', { key: name, bubbles: true, cancelable: true, ...init }))
}
const rows = () => [...readout()!.querySelectorAll('dt')].map((dt, i) => [dt.textContent!.trim(), readout()!.querySelectorAll('dd')[i]!.textContent!.trim()])
const buttonNamed = (name: string) => document.body.querySelector<HTMLButtonElement>(`.sc-toolbar button[aria-label="${name}"]`)!
/** Off: `aria-disabled`, never `disabled`, which would drop the focus of a button that turns off while it has it (WCAG 2.4.3, GH-4101) */
const isOff = (name: string) => buttonNamed(name).getAttribute('aria-disabled') === 'true'

beforeEach(() => {
  echarts.chart.on.mockClear()
  echarts.chart.setOption.mockReset()
  echarts.chart.dispose.mockClear()
  echarts.init.mockClear()
  echarts.state.loadFails = false
  image.svgToBlob.mockClear()
  image.downloadBlob.mockClear()
  reloadNuxtApp.mockClear()
  toastAdd.mockClear()
  document.body.innerHTML = ''
})

describe('the variants (GH-4156)', () => {
  const switcher = () => document.body.querySelector<HTMLElement>('[role="radiogroup"]')!
  const radio = (name: string) => [...switcher().querySelectorAll<HTMLButtonElement>('[role="radio"]')].find(button => button.textContent?.trim() === name)!
  const svgOf = () => (image.svgToBlob.mock.calls.at(-1) as unknown as [string, any])[0]
  const textsOf = (svg: string) => [...svg.matchAll(/<text[^>]*>([^<]*)<\/text>/g)].map(match => match[1]!)

  it('has a switch of the four, the stripes the one chosen where nothing else is asked for, which asks the page for another', async () => {
    const shown = await showChart()
    expect(switcher().getAttribute('aria-label')).toBe('Chart style')
    expect([...switcher().querySelectorAll('[role="radio"]')].map(button => [button.textContent?.trim(), button.getAttribute('aria-checked')])).toEqual([['Stripes', 'true'], ['Bars', 'false'], ['Bars with scale', 'false'], ['Table', 'false']])
    radio('Bars with scale').click()
    expect(shown.emitted('update:variant')).toEqual([['barsScale']])
    // the page owns the choice: the chart draws what it is given
    expect(radio('Stripes').getAttribute('aria-checked')).toBe('true')
    radio('Table').click()
    expect(shown.emitted('update:variant')).toEqual([['barsScale'], ['table']])
  })

  it('moves along the four by the arrow keys, as the forecast\'s switch does, the table the last', async () => {
    const shown = await showChart({ variant: 'barsScale' })
    radio('Bars with scale').dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true }))
    expect(shown.emitted('update:variant')).toEqual([['table']])
  })

  describe('the table view (GH-4233)', () => {
    it('shows the switch and nothing of the chart: no figure, no toolbar, no camera, no hint to its keys, and draws nothing', async () => {
      // nothing is drawn, so there is no drawing to wait for
      wrapper = await mountSuspended(StripesChart, {
        props: { values: VALUES, reference: REFERENCE, kind: 'temperature', unit: '°C', title: TITLE, display: DISPLAY, label: TITLE, cameraFile: 'f', variant: 'table' },
        attachTo: document.body,
      })
      await flushPromises()
      expect(radio('Table').getAttribute('aria-checked')).toBe('true')
      expect(document.body.querySelector('[role="figure"]')).toBeNull()
      expect(document.body.querySelector('.sc-toolbar')).toBeNull()
      expect(document.body.querySelector('[aria-label="Download plot as a PNG"]')).toBeNull()
      expect(document.body.querySelector('[data-testid="stripes-announce"]')).toBeNull()
      expect(drawn()).toBe(0)
      expect(echarts.init).not.toHaveBeenCalled()
    })

    it('takes the chart away where the table is chosen, and draws the drawing it had where one is chosen again', async () => {
      const shown = await showChart({ variant: 'bars' })
      expect(document.body.querySelector('[role="figure"]')).not.toBeNull()
      const before = drawn()
      await shown.setProps({ variant: 'table' })
      await vi.waitFor(() => expect(document.body.querySelector('[role="figure"]')).toBeNull())
      expect(echarts.chart.dispose).toHaveBeenCalled()
      expect(drawn()).toBe(before)
      await shown.setProps({ variant: 'barsScale' })
      await vi.waitFor(() => expect(drawn()).toBe(before + 1))
      expect(lastOption().series.map((s: any) => s.id)).toContain('grid')
      expect(document.body.querySelector('[role="figure"]')).not.toBeNull()
    })

    it('saves the camera\'s image of the drawing the chart goes back to, not of the table', async () => {
      const shown = await showChart({ variant: 'bars' })
      await shown.setProps({ variant: 'table' })
      await shown.setProps({ variant: 'bars' })
      await vi.waitFor(() => expect(document.body.querySelector('.sc-toolbar')).not.toBeNull())
      image.svgToBlob.mockClear()
      document.body.querySelector<HTMLButtonElement>('[aria-label="Download plot as a PNG"]')!.click()
      await vi.waitFor(() => expect(image.svgToBlob).toHaveBeenCalled())
      expect(svgOf()).toContain('<svg')
    })

    it('puts no crosshair away that the table could keep: a readout is gone with the chart', async () => {
      const shown = await showChart()
      document.body.querySelector<HTMLElement>('[role="figure"]')!.focus()
      document.body.querySelector<HTMLElement>('[role="figure"]')!.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true }))
      await nextTick()
      expect(document.body.querySelector('[data-testid="stripes-readout"]')).not.toBeNull()
      await shown.setProps({ variant: 'table' })
      await nextTick()
      expect(document.body.querySelector('[data-testid="stripes-readout"]')).toBeNull()
    })
  })

  it('keeps the switch where the chart could not be drawn, outside what is out of reach (inert)', async () => {
    echarts.state.loadFails = true
    vi.spyOn(console, 'error').mockImplementation(() => {})
    await mountSuspended(StripesChart, {
      props: { values: VALUES, reference: REFERENCE, kind: 'temperature', unit: '°C', title: TITLE, display: DISPLAY, cameraFile: 'f' },
      attachTo: document.body,
    })
    await vi.waitFor(() => expect(document.body.querySelector('[role="alert"]')).not.toBeNull())
    expect(document.body.querySelector('.sc-toolbar')!.hasAttribute('inert')).toBe(true)
    expect(switcher().closest('[inert]')).toBeNull()
  })

  it.each([
    ['stripes', ['stripes', 'availability', 'labels']],
    ['bars', ['bars', 'zeroline', 'availability', 'labels']],
    ['barsScale', ['bars', 'grid', 'zeroline', 'availability', 'labels']],
  ])('draws %s for the variant it is given, and draws again where it changes', async (variant, ids) => {
    const shown = await showChart({ variant })
    expect(lastOption().series.map((s: any) => s.id)).toEqual(ids)
    expect(radio({ stripes: 'Stripes', bars: 'Bars', barsScale: 'Bars with scale' }[variant]!).getAttribute('aria-checked')).toBe('true')
    const before = drawn()
    await shown.setProps({ variant: variant === 'stripes' ? 'bars' : 'stripes' })
    await vi.waitFor(() => expect(drawn()).toBe(before + 1))
    expect(lastOption().series[0].id).toBe(variant === 'stripes' ? 'bars' : 'stripes')
  })

  it('is as high as the stripes for the bars, and as high as the scale needs for the bars with one (its room left of the plot, its subtitle)', async () => {
    const shown = await showChart()
    const stripes = (echarts.init.mock.calls[0]![2] as { height: number }).height
    await shown.setProps({ variant: 'bars' })
    await vi.waitFor(() => expect(echarts.chart.resize).toHaveBeenLastCalledWith({ width: 800, height: stripes }))
    await shown.setProps({ variant: 'barsScale' })
    const scaled = stripesChartHeight(DISPLAY, 800, 1, { frame: frameOf({ variant: 'barsScale', subtitleLines: ['x'] }) })
    await vi.waitFor(() => expect(echarts.chart.resize).toHaveBeenLastCalledWith({ width: 800, height: scaled }))
    // the stripes of the scale are as high as the plot is wide over their ratio, and the subtitle's row is on top of that
    expect(scaled).not.toBe(stripes)
  })

  it('moves the ticks of the bars with a scale with the zoom: the grid and the labels are the window\'s update', async () => {
    await showChart({ variant: 'barsScale' })
    document.body.querySelector<HTMLButtonElement>('.sc-toolbar button[aria-label="Zoom in"]')!.click()
    await nextTick()
    const update = echarts.chart.setOption.mock.calls.filter(([option]) => option.dataZoom && !option.grid).at(-1)![0]
    expect(update.series.map((s: any) => s.id)).toEqual(['labels', 'grid'])
  })

  it('saves the bars as the page shows them: the camera and the menu, with the title, the source and what the colours are relative to', async () => {
    const shown = await showChart({ variant: 'bars' })
    await (shown.vm as any).save({ format: 'png', filename: 'name', width: 800, height: 578, scale: 3 })
    const svg = svgOf()
    // bars, not stripes: the stripes' rectangles would be as high as the plot
    const heights = [...svg.matchAll(/<path d="M[\d.-]+ [\d.-]+l[\d.]+ 0l0 ([\d.]+)l/g)].map(match => Number(match[1]))
    expect(new Set(heights).size).toBeGreaterThan(10)
    const texts = textsOf(svg)
    expect(texts).toContain(TITLE)
    expect(texts).toContain('Source: Deutscher Wetterdienst')
    expect(texts.some(text => text.startsWith('Colours:'))).toBe(true)
    // the zero line is in the saved image
    expect(svg).toContain('stroke=')
  })

  it('saves the bars with a scale with their axis, the years along it and the subtitle, in the language of the page', async () => {
    const shown = await showChart({ variant: 'barsScale' })
    await (shown.vm as any).save({ format: 'svg', filename: 'name', width: 800, height: 600, scale: 1 })
    const texts = textsOf(svgOf())
    expect(texts).toContain('Relative to the mean of 1971–2000 [°C]')
    expect(texts).toContain('0')
    // the ticks with their sign: a minus is the language's own, a plus is written out
    expect(texts.some(text => /^[+\-−]\d/.test(text))).toBe(true)
    // round years, not the first and the last
    const years = texts.filter(text => /^\d{4}$/.test(text)).map(Number)
    expect(years.length).toBeGreaterThan(3)
    expect(years.every(year => year % 5 === 0)).toBe(true)
  })

  it('says the whole record where the station has too few years in the period, in the subtitle', async () => {
    const short = stripesAnswer(recordOf(2005, 2024, year => (year - 2005) / 10))
    const shown = await showChart({ variant: 'barsScale', values: short.values, reference: short.reference })
    await (shown.vm as any).save({ format: 'svg', filename: 'name', width: 800, height: 600, scale: 1 })
    expect(textsOf(svgOf())).toContain('Relative to the mean of the whole record (2005–2024) [°C]')
  })

  it('has the camera save the bars with a scale at the width it has always had, as high as its scale needs, with the subtitle', async () => {
    await showChart({ variant: 'barsScale' })
    image.svgToBlob.mockClear()
    document.body.querySelector<HTMLButtonElement>('.sc-controls button[aria-label="Download plot as a PNG"]')!.click()
    await vi.waitFor(() => expect(image.downloadBlob).toHaveBeenCalled())
    const options = (image.svgToBlob.mock.calls[0] as unknown as [string, any])[1]
    expect(options).toMatchObject({ format: 'png', width: 1400, scale: 2 })
    // the stripes of the camera are as high as 1400 px less the room of the scale is wide over their ratio, and the subtitle's row and the line of the colours are on top
    const frame = frameOf({ variant: 'barsScale', subtitleLines: ['Relative to the mean of 1971–2000 [°C]'] })
    expect(options.height).toBe(stripesChartHeight(DISPLAY, 1400, 1, { clamp: false, frame }) + extraLinesHeight(DISPLAY, 2))
    expect(svgOf()).toContain(`height="${options.height}"`)
    expect(textsOf(svgOf())).toContain('Relative to the mean of 1971–2000 [°C]')
  })

  it('writes a line on where the days came from into the saved image, and nothing where there is none (GH-4390)', async () => {
    const notice = 'Read from the mirror of NOAA\'s data on AWS; the most recent days may be missing. The record read there ends in 2011.'
    const heightOf = (svg: string) => Number(/height="(\d+)"/.exec(svg)![1])
    const plain = await showChart()
    await (plain.vm as any).save({ format: 'svg', filename: 'plain', width: 1400, height: 600, scale: 1 })
    expect(textsOf(svgOf()).join(' ')).not.toContain('mirror')
    const plainHeight = heightOf(svgOf())
    plain.unmount()
    const shown = await showChart({ noticeLine: notice })
    await (shown.vm as any).save({ format: 'svg', filename: 'mirror', width: 1400, height: 600, scale: 1 })
    // the svg escapes the apostrophe
    expect(textsOf(svgOf()).join(' ').replaceAll('&#39;', '\'')).toContain(notice)
    // the image is higher by the line
    expect(heightOf(svgOf())).toBeGreaterThan(plainHeight)
  })

  it('breaks the line on where the days came from for a narrow image, into lines none of which is the whole of it, which make the image higher (GH-4390)', async () => {
    const notice = 'Read from the mirror of NOAA\'s data on AWS; the most recent days may be missing. The record read there ends in 2011.'
    const heightOf = (svg: string) => Number(/height="(\d+)"/.exec(svg)![1])
    const plain = (svg: string) => textsOf(svg).map(text => text.replaceAll('&#39;', '\''))
    const shown = await showChart({ noticeLine: notice })
    await (shown.vm as any).save({ format: 'svg', filename: 'wide', width: 1400, height: 600, scale: 1 })
    const wide = { texts: plain(svgOf()), height: heightOf(svgOf()) }
    await (shown.vm as any).save({ format: 'svg', filename: 'narrow', width: 400, height: 600, scale: 1 })
    const narrow = { texts: plain(svgOf()), height: heightOf(svgOf()) }
    // wide enough, one line holds it all; narrow, no line does, and the lines together are the notice
    expect(wide.texts).toContain(notice)
    expect(narrow.texts).not.toContain(notice)
    expect(narrow.texts.join(' ')).toContain(notice)
    expect(narrow.height).toBeGreaterThan(wide.height)
  })

  it('writes the line on where the days came from where the source line is not shown, which it is not under (GH-4390)', async () => {
    const notice = 'Read from the mirror of NOAA\'s data on AWS; the most recent days may be missing.'
    const shown = await showChart({ noticeLine: notice, display: { ...DISPLAY, showSource: false } })
    await (shown.vm as any).save({ format: 'svg', filename: 'no-source', width: 1400, height: 600, scale: 1 })
    const texts = textsOf(svgOf()).map(text => text.replaceAll('&#39;', '\''))
    expect(texts).toContain(notice)
    // no source line and no note of what wetterdienst did to the data: the notice is the first line under the colours' sentence
    expect(texts.join(' ')).not.toContain('Source:')
    expect(texts.join(' ')).not.toContain('Processed by wetterdienst')
  })

  it('breaks a long subtitle into lines for a narrow image, which make it higher', async () => {
    const shown = await showChart({ variant: 'barsScale' })
    await (shown.vm as any).save({ format: 'svg', filename: 'wide', width: 800, height: 600, scale: 1 })
    const wide = textsOf(svgOf()).filter(text => text.includes('Relative to'))
    await (shown.vm as any).save({ format: 'svg', filename: 'narrow', width: 200, height: 600, scale: 1 })
    const narrow = textsOf(svgOf()).filter(text => /Relative|mean|1971|°C/.test(text))
    expect(wide).toHaveLength(1)
    expect(narrow.length).toBeGreaterThan(1)
  })
})

describe('drawing', () => {
  it('draws the stripes in an SVG chart as tall as its width gives it at the ratio of the stripes, and listens for the zoom of the library', async () => {
    await showChart()
    expect(echarts.init).toHaveBeenCalledTimes(1)
    expect(echarts.init.mock.calls[0]![2]).toEqual({ renderer: 'svg', width: 800, height: 578 })
    expect(echarts.chart.on).toHaveBeenCalledWith('datazoom', expect.any(Function))
    expect(lastOption().series.map((s: any) => s.id)).toEqual(['stripes', 'availability', 'labels'])
    expect(lastOption().animation).toBe(false)
  })

  it('is shorter without a title (the title is on top of the stripes, which keep their height), and draws again for what the page switches', async () => {
    const shown = await showChart()
    const before = drawn()
    await shown.setProps({ display: { ...DISPLAY, showTitle: false } })
    await vi.waitFor(() => expect(drawn()).toBe(before + 1), { timeout: 5000 })
    expect(echarts.chart.resize).toHaveBeenLastCalledWith({ width: 800, height: 568 })
    expect(lastOption().series.map((s: any) => s.id)).toEqual(['stripes', 'availability', 'labels'])
  })

  it('says it is drawn, and in which scheme', async () => {
    await showChart()
    const canvas = document.body.querySelector<HTMLElement>('.sc-canvas')!
    expect(canvas.dataset.drawn).toBe('true')
    // the page of the test is dark (the theme it reads is the mock's)
    expect(canvas.dataset.chartScheme).toBe('dark')
  })

  it('is a named figure with one tab stop, described by its keys', async () => {
    await showChart({ describedBy: 'summary' })
    expect(stage().getAttribute('role')).toBe('figure')
    expect(stage().getAttribute('tabindex')).toBe('0')
    expect(stage().getAttribute('aria-label')).toBe(TITLE)
    expect(stage().getAttribute('aria-describedby')!.split(' ')[0]).toBe('summary')
    expect(document.body.querySelector(`#${stage().getAttribute('aria-describedby')!.split(' ')[1]}`)!.textContent).toContain('arrow keys')
    // the canvas is the picture; what it says is in the readout, the sentence and the table
    expect(document.body.querySelector('.sc-canvas')!.getAttribute('aria-hidden')).toBe('true')
  })

  it('disposes the chart where it goes', async () => {
    const shown = await showChart()
    shown.unmount()
    expect(echarts.chart.dispose).toHaveBeenCalled()
  })

  it('says so where the chart\'s code could not be loaded, and loads it again on Retry', async () => {
    echarts.state.loadFails = true
    vi.spyOn(console, 'error').mockImplementation(() => {})
    const shown = await mountSuspended(StripesChart, {
      props: { values: VALUES, reference: REFERENCE, kind: 'temperature', unit: '°C', title: TITLE, display: DISPLAY, cameraFile: 'f' },
      attachTo: document.body,
    })
    await vi.waitFor(() => expect(document.body.querySelector('[role="alert"]')).not.toBeNull())
    expect(document.body.querySelector('[role="alert"]')!.textContent).toContain('The chart could not be drawn')
    expect((shown.vm as any).renderFailed).toBe(true)
    // the reload is offered where the code is what failed
    const reload = [...document.body.querySelectorAll('button')].find(button => button.textContent?.includes('Reload'))!
    reload.click()
    expect(reloadNuxtApp).toHaveBeenCalledWith({ force: true })

    echarts.state.loadFails = false
    const retry = [...document.body.querySelectorAll('button')].find(button => button.textContent?.includes('Retry'))!
    retry.click()
    await vi.waitFor(() => expect(echarts.chart.setOption).toHaveBeenCalled())
    await flushPromises()
    expect((shown.vm as any).renderFailed).toBe(false)
    expect(document.body.querySelector('[role="alert"]')).toBeNull()
  })

  it('puts the toolbar and the chart out of reach while it could not be drawn, and back where it is', async () => {
    echarts.state.loadFails = true
    vi.spyOn(console, 'error').mockImplementation(() => {})
    const shown = await mountSuspended(StripesChart, {
      props: { values: VALUES, reference: REFERENCE, kind: 'temperature', unit: '°C', title: TITLE, display: DISPLAY, cameraFile: 'f' },
      attachTo: document.body,
    })
    await vi.waitFor(() => expect((shown.vm as any).renderFailed).toBe(true))
    const toolbar = document.body.querySelector('.sc-toolbar')!
    const scroller = document.body.querySelector('.sc-scroller')!
    expect(toolbar.hasAttribute('inert')).toBe(true)
    expect(scroller.hasAttribute('inert')).toBe(true)
    // the notice and its Retry are not
    expect(document.body.querySelector('[role="alert"]')!.closest('[inert]')).toBeNull()

    echarts.state.loadFails = false
    const retry = [...document.body.querySelectorAll('button')].find(button => button.textContent?.includes('Retry'))!
    retry.click()
    await vi.waitFor(() => expect((shown.vm as any).renderFailed).toBe(false))
    await nextTick()
    expect(toolbar.hasAttribute('inert')).toBe(false)
    expect(scroller.hasAttribute('inert')).toBe(false)
  })

  it('moves the focus to Retry where a drawing fails while it is in the toolbar or on the chart, which the notice puts out of reach', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    const shown = await showChart()
    const retry = () => [...document.body.querySelectorAll('button')].find(button => button.textContent?.includes('Retry'))
    const failAfter = async (focus: () => void) => {
      focus()
      echarts.chart.setOption.mockImplementation(() => {
        throw new Error('drawing failed')
      })
      await shown.setProps({ display: { ...DISPLAY, showTitle: !(shown.props('display') as typeof DISPLAY).showTitle } })
      await vi.waitFor(() => expect((shown.vm as any).renderFailed).toBe(true))
      await nextTick()
    }
    const recover = async () => {
      echarts.chart.setOption.mockReset()
      retry()!.click()
      await vi.waitFor(() => expect((shown.vm as any).renderFailed).toBe(false))
      await nextTick()
    }

    // in the toolbar
    await failAfter(() => buttonNamed('Zoom in').focus())
    expect(document.activeElement).toBe(retry())
    await recover()

    // on the chart
    await failAfter(() => stage().focus())
    expect(document.activeElement).toBe(retry())
    await recover()

    // elsewhere: it stays
    const elsewhere = document.body.appendChild(document.createElement('button'))
    await failAfter(() => elsewhere.focus())
    expect(document.activeElement).toBe(elsewhere)
  })

  it('names the keys of the chart as ARIA writes them: the plus key is Plus, since + is the separator', async () => {
    await showChart()
    const shortcuts = stage().getAttribute('aria-keyshortcuts')!.split(' ')
    expect(shortcuts).toContain('Plus')
    expect(shortcuts.some(key => key.includes('+'))).toBe(false)
    expect(shortcuts).toEqual(expect.arrayContaining(['ArrowLeft', 'ArrowRight', 'PageUp', 'PageDown', 'Home', 'End', '-', '0', 'Escape']))
  })

  it('draws nothing where there is no year with a value', async () => {
    await mountSuspended(StripesChart, {
      props: { values: [{ timestamp: '2000-01-01T00:00:00+00:00', value: null, anomaly: null, stripe_class: null }], reference: REFERENCE, kind: 'temperature', unit: '°C', title: TITLE, display: DISPLAY, cameraFile: 'f' },
      attachTo: document.body,
    })
    await flushPromises()
    expect(echarts.chart.setOption).not.toHaveBeenCalled()
  })
})

describe('the readout', () => {
  it('shows the year, its value in the unit, and its class under the pointer, and takes it away where the pointer leaves', async () => {
    await showChart()
    expect(readout()).toBeNull()
    movePointerTo(xOfYear(1992))
    await nextTick()
    expect(readout()!.textContent).toContain('1992')
    // 1992 lies 0.7 °C above the mean of the reference (the mean of 1971 to 2000): in the band `Warmer`, with its anomaly
    expect(rows()).toEqual([['Value', '4.20 °C'], ['Class', 'Warmer (+0.7 °C)']])
    expect(readout()!.getAttribute('role')).toBe('group')
    expect(readout()!.getAttribute('aria-label')).toBe('Climate stripe for 1992')
    stage().dispatchEvent(pointer('pointerleave'))
    await nextTick()
    expect(readout()).toBeNull()
  })

  it('names no trend, even where the display of an older version asks for it (GH-4170)', async () => {
    await showChart({ display: { ...DISPLAY, showTimeseries: true, showTrendline: true } as typeof DISPLAY })
    movePointerTo(xOfYear(2000))
    await nextTick()
    expect(rows().map(([name]) => name)).toEqual(['Value', 'Class'])
  })

  it('has none over the title, the years and the source, or the margin above the stripes, which are no stripes', async () => {
    await showChart()
    // the stripes: 30 px of margin and the title above the plot, the blank of the availability line's range to 50, 478 below
    for (const y of [10, 40, 49, 479, 520, 570]) {
      movePointerTo(xOfYear(1992), y)
      await nextTick()
      expect(readout(), `the pointer at ${y} px`).toBeNull()
    }
    movePointerTo(xOfYear(1992), 60)
    await nextTick()
    expect(readout()).not.toBeNull()
    // leaving them upwards takes it away again
    movePointerTo(xOfYear(1992), 10)
    await nextTick()
    expect(readout()).toBeNull()
    // a tap there selects nothing either
    stage().dispatchEvent(pointer('click', { clientX: xOfYear(1990), clientY: 520, pointerType: 'touch' }))
    await nextTick()
    expect(readout()).toBeNull()
  })

  it('starts no zoom box over the title or the years', async () => {
    await showChart()
    stage().dispatchEvent(pointer('pointerdown', { clientX: xOfYear(1970), clientY: 520 }))
    stage().dispatchEvent(pointer('pointermove', { clientX: xOfYear(1980), clientY: 520 }))
    await nextTick()
    expect(document.body.querySelector('.sc-selection')).toBeNull()
    stage().dispatchEvent(pointer('pointerup', { clientX: xOfYear(1980), clientY: 520 }))
    await nextTick()
    expect(isOff('Reset zoom')).toBe(true)
  })

  it('has none for a year without a value, or the margin', async () => {
    await showChart()
    movePointerTo(xOfYear(1963))
    await nextTick()
    expect(readout()).toBeNull()
    movePointerTo(5)
    await nextTick()
    expect(readout()).toBeNull()
  })

  it('is next to the stripe it is for, where a pointer moves onto it without crossing another, and is closed by Escape without the pointer moving (WCAG 1.4.13)', async () => {
    await showChart()
    movePointerTo(xOfYear(2010))
    await nextTick()
    const element = readout()!
    const ring = document.body.querySelector<HTMLElement>('.sc-cursor')!
    // the stripe is near the right edge, which leaves no room: the readout ends a few px inside the stripe, and has no gap to it
    expect(Number.parseFloat(element.style.left) + Number.parseFloat(element.style.width)).toBeCloseTo(Number.parseFloat(ring.style.left) + 4, 0)
    // a pointer over the readout leaves the crosshair where it was and keeps the readout
    element.dispatchEvent(pointer('pointermove', { clientX: 60 }))
    await nextTick()
    expect(readout()).not.toBeNull()
    expect(readout()!.textContent).toContain('2010')
    // persistent: it stays while the pointer rests
    await new Promise(resolve => setTimeout(resolve, 50))
    expect(readout()).not.toBeNull()
    // dismissible: Escape, wherever the focus is, and not consumed
    const escape = new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true })
    document.body.dispatchEvent(escape)
    await nextTick()
    expect(readout()).toBeNull()
    expect(escape.defaultPrevented).toBe(false)
    // a jitter of the pointer at the same stripe brings it back no more than a pixel does
    movePointerTo(xOfYear(2010) + 1)
    await nextTick()
    expect(readout()).toBeNull()
    // another stripe is a new hover
    movePointerTo(xOfYear(2015))
    await nextTick()
    expect(readout()).not.toBeNull()
  })

  it('has a Close button for a touch, which closes it', async () => {
    await showChart()
    movePointerTo(xOfYear(1980))
    await nextTick()
    readout()!.querySelector<HTMLButtonElement>('.sc-close')!.click()
    await nextTick()
    expect(readout()).toBeNull()
  })

  it('gives the focus back to the chart where its Close button, which had it, goes with the readout', async () => {
    await showChart()
    // by a click (or Enter, which is one)
    key('ArrowRight')
    await nextTick()
    const close = () => readout()!.querySelector<HTMLButtonElement>('.sc-close')!
    close().focus()
    expect(document.activeElement).toBe(close())
    // without scrolling the page to the chart, which is where the focus already is in the page
    const focus = vi.spyOn(stage(), 'focus')
    close().click()
    await nextTick()
    expect(readout()).toBeNull()
    expect(document.activeElement).toBe(stage())
    expect(focus).toHaveBeenCalledWith({ preventScroll: true })

    // by Escape while it has the focus
    key('ArrowRight')
    await nextTick()
    close().focus()
    document.activeElement!.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }))
    await nextTick()
    expect(readout()).toBeNull()
    expect(document.activeElement).toBe(stage())
  })

  it('stays for a tap until it is closed, and a pointer that leaves does not take it away', async () => {
    await showChart()
    const tap = pointer('click', { clientX: xOfYear(1990), pointerType: 'touch' })
    stage().dispatchEvent(tap)
    await nextTick()
    expect(readout()!.textContent).toContain('1990')
    stage().dispatchEvent(pointer('pointerleave', { pointerType: 'touch' }))
    await nextTick()
    expect(readout()).not.toBeNull()
  })

  it('marks the stripe it is for with a ring that is no colour of the scale', async () => {
    await showChart()
    movePointerTo(xOfYear(1992))
    await nextTick()
    const ring = document.body.querySelector<HTMLElement>('.sc-cursor')!
    expect(ring.getAttribute('aria-hidden')).toBe('true')
    expect(Number.parseFloat(ring.style.left)).toBeCloseTo(xOfYear(1992 - 0.5), 0)
    expect(Number.parseFloat(ring.style.width)).toBeCloseTo(760 / 75, 0)
  })
})

describe('the keys', () => {
  it('step through the years that have a stripe, and say each one', async () => {
    await showChart()
    key('ArrowRight')
    await nextTick()
    expect(readout()!.textContent).toContain('1950')
    expect(announce()).toBe('1950: Value: 0.00 °C')
    key('ArrowRight')
    key('ArrowLeft')
    key('ArrowLeft')
    await nextTick()
    // Left stops at the first
    expect(announce()).toContain('1950')
    // over the gap: 1961 to 1965
    for (let i = 0; i < 11; i++)
      key('ArrowRight')
    await nextTick()
    expect(announce()).toBe('1961: Value: 1.10 °C')
    key('ArrowRight')
    await nextTick()
    expect(announce()).toBe('1965: Value: 1.50 °C')
  })

  it('jump ten years with Page Up and Page Down and to the ends with Home and End', async () => {
    await showChart()
    key('End')
    await nextTick()
    expect(announce()).toBe('2024: Value: 7.40 °C')
    key('PageUp')
    await nextTick()
    expect(announce()).toContain('2014:')
    key('Home')
    key('PageDown')
    await nextTick()
    expect(announce()).toContain('1960:')
  })

  it('zoom with plus, minus and 0, round the crosshair', async () => {
    await showChart()
    key('+')
    await nextTick()
    const zoomed = lastZoom()
    expect(zoomed.end - zoomed.start).toBeCloseTo(75 / 1.5)
    key('-')
    await nextTick()
    expect(lastZoom().end - lastZoom().start).toBeCloseTo(75)
    key('+')
    key('+')
    key('0')
    await nextTick()
    expect(lastZoom()).toMatchObject({ start: 1949.5, end: 2024.5 })
  })

  it('move the window with the crosshair where a year is out of it', async () => {
    await showChart()
    key('+')
    key('+')
    key('+')
    await nextTick()
    const win = lastZoom()
    key('End')
    await nextTick()
    expect(lastZoom().end).toBeCloseTo(2024.5)
    expect(lastZoom().start).toBeGreaterThan(win.start)
  })

  it('leave Escape and the keys with a modifier alone', async () => {
    await showChart()
    const escape = new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true })
    stage().dispatchEvent(escape)
    expect(escape.defaultPrevented).toBe(false)
    const ctrl = new KeyboardEvent('keydown', { key: 'ArrowRight', ctrlKey: true, bubbles: true, cancelable: true })
    stage().dispatchEvent(ctrl)
    expect(ctrl.defaultPrevented).toBe(false)
    await nextTick()
    expect(readout()).toBeNull()
  })

  it('take the readout away where the focus leaves the chart', async () => {
    await showChart()
    key('ArrowRight')
    await nextTick()
    expect(readout()).not.toBeNull()
    stage().dispatchEvent(new FocusEvent('blur', { relatedTarget: document.body }))
    await nextTick()
    expect(readout()).toBeNull()
  })
})

describe('the zoom', () => {
  it('has the buttons of what a drag and the keys do, which are off where they would do nothing', async () => {
    await showChart()
    expect(document.body.querySelector('.sc-toolbar')!.getAttribute('role')).toBe('group')
    expect(isOff('Zoom out')).toBe(true)
    expect(isOff('Reset zoom')).toBe(true)
    expect(isOff('Earlier years')).toBe(true)
    expect(isOff('Later years')).toBe(true)
    buttonNamed('Zoom in').click()
    await nextTick()
    expect(isOff('Zoom out')).toBe(false)
    expect(isOff('Later years')).toBe(false)
    buttonNamed('Later years').click()
    await nextTick()
    expect(lastZoom().end).toBeCloseTo(2024.5)
    buttonNamed('Earlier years').click()
    await nextTick()
    expect(lastZoom().end).toBeLessThan(2024.5)
    buttonNamed('Reset zoom').click()
    await nextTick()
    expect(lastZoom()).toMatchObject({ start: 1949.5, end: 2024.5 })
  })

  it('names the first and the last year in the window, which moves with it', async () => {
    await showChart()
    buttonNamed('Zoom in').click()
    await nextTick()
    buttonNamed('Later years').click()
    await nextTick()
    const years = lastZoom().labels
    expect(years.id).toBe('labels')
    expect(years.data.length).toBeGreaterThanOrEqual(3)
  })

  it('zooms to a box dragged with a mouse, and resets on a double click', async () => {
    await showChart()
    stage().dispatchEvent(pointer('pointerdown', { clientX: xOfYear(1970) }))
    stage().dispatchEvent(pointer('pointermove', { clientX: xOfYear(1980) }))
    await nextTick()
    expect(document.body.querySelector('.sc-selection')).not.toBeNull()
    stage().dispatchEvent(pointer('pointerup', { clientX: xOfYear(1980) }))
    await nextTick()
    expect(lastZoom().start).toBeCloseTo(1970, 0)
    expect(lastZoom().end).toBeCloseTo(1980, 0)
    expect(document.body.querySelector('.sc-selection')).toBeNull()
    stage().dispatchEvent(new MouseEvent('dblclick', { bubbles: true }))
    await nextTick()
    expect(lastZoom()).toMatchObject({ start: 1949.5, end: 2024.5 })
  })

  it('takes the zoom of the library\'s own gestures (a pinch)', async () => {
    await showChart()
    const handler = echarts.chart.on.mock.calls.find(([name]) => name === 'datazoom')![1] as (event: unknown) => void
    handler({ batch: [{ startValue: 1980, endValue: 2000 }] })
    await nextTick()
    expect(lastZoom()).toMatchObject({ start: 1980, end: 2000 })
    // its echo of a window the component set is no news
    const calls = echarts.chart.setOption.mock.calls.length
    handler({ batch: [{ startValue: 1980, endValue: 2000 }] })
    await nextTick()
    expect(echarts.chart.setOption.mock.calls.length).toBe(calls)
  })

  it('swallows the press of an unavailable button: Reset zoom pressed at the whole chart does not bring a dismissed readout back (GH-4101)', async () => {
    await showChart()
    movePointerTo(xOfYear(2010))
    await nextTick()
    expect(readout()).not.toBeNull()
    // dismissed by Escape (WCAG 1.4.13): what a reset of the zoom would undo, as it shows the readout again
    document.body.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }))
    await nextTick()
    expect(readout()).toBeNull()
    expect(isOff('Reset zoom')).toBe(true)
    buttonNamed('Reset zoom').click()
    await nextTick()
    expect(readout()).toBeNull()
  })

  it('keeps a button that turns off in the tab order with the focus, and does nothing when it is pressed (WCAG 2.4.3, GH-4101)', async () => {
    await showChart()
    buttonNamed('Zoom in').click()
    await nextTick()
    const reset = buttonNamed('Reset zoom')
    expect(isOff('Reset zoom')).toBe(false)
    reset.focus()
    reset.click()
    await nextTick()
    // off, and still a button that can have the focus: a `disabled` one would hand it to the page
    expect(isOff('Reset zoom')).toBe(true)
    expect(reset.disabled).toBe(false)
    expect(reset.tabIndex).toBeGreaterThanOrEqual(0)
    expect(document.activeElement).toBe(reset)
    // pressed again, it does nothing: the whole chart stays, and Zoom out (off too) does nothing either
    const calls = echarts.chart.setOption.mock.calls.length
    reset.click()
    buttonNamed('Zoom out').click()
    buttonNamed('Earlier years').click()
    await nextTick()
    expect(echarts.chart.setOption.mock.calls.length).toBe(calls)
    expect(isOff('Reset zoom')).toBe(true)
    expect(document.activeElement).toBe(reset)
  })

  it('keeps the zoom where the colours or the language change, and starts over for other years', async () => {
    const shown = await showChart()
    buttonNamed('Zoom in').click()
    await nextTick()
    const zoomed = lastZoom()
    await shown.setProps({ unit: '°F' })
    await nextTick()
    expect(isOff('Reset zoom')).toBe(false)
    expect(lastZoom()).toMatchObject({ start: zoomed.start, end: zoomed.end })
    await shown.setProps({ values: VALUES.filter(item => !item.timestamp!.startsWith('1950')) })
    await nextTick()
    expect(isOff('Reset zoom')).toBe(true)
  })
})

describe('the image', () => {
  it('is saved as the camera does: a PNG of 1400 by 955 px (the stripes 16:9, 765 px, the margins on top and the two lines under the source: the note of what wetterdienst did and what the colours are relative to) at twice the size, in the light theme, named for the station', async () => {
    await showChart()
    buttonNamed('Download plot as a PNG').click()
    await vi.waitFor(() => expect(image.downloadBlob).toHaveBeenCalled())
    const [svg, options] = image.svgToBlob.mock.calls[0] as unknown as [string, any]
    expect(options).toMatchObject({ format: 'png', width: 1400, height: 955, scale: 2 })
    expect(options.background).toMatch(/^#|^rgb/)
    expect(svg).toContain('width="1400" height="955"')
    expect(svg).toContain(TITLE)
    expect(image.downloadBlob.mock.calls[0]![1]).toBe('climate_stripes_temperature_00011.png')
  })

  it('says what its colours are relative to, under the source, in a line of its own that makes the image higher (GH-4157)', async () => {
    await showChart()
    buttonNamed('Download plot as a PNG').click()
    await vi.waitFor(() => expect(image.downloadBlob).toHaveBeenCalled())
    const [svg] = image.svgToBlob.mock.calls[0] as unknown as [string, any]
    const texts = [...svg.matchAll(/<text[^>]*>([^<]*)<\/text>/g)].map(match => match[1])
    // the mean of 1971 to 2000, and the standard deviation of the years of 1901 to 2000 the station has
    expect(texts).toContain('Colours: mean of 1971–2000, ±2.6 σ of 1950–2000')
    // the source stays on its row, and the reference is under it
    const y = (text: string) => Number(new RegExp(`<text[^>]*y="([\\d.]+)"[^>]*>${text}</text>`).exec(svg)![1])
    expect(y('Colours: mean of 1971–2000, ±2.6 σ of 1950–2000')).toBeGreaterThan(y('Source: Deutscher Wetterdienst'))
    // the page's chart, which says it under the stripes in the page's own text, has no such line
    expect(lastOption().series.at(-1).data.length).toBeLessThan(texts.length)
  })

  it('says what wetterdienst did to the data directly under the source, before what the colours are relative to, and with the source (GH-3799)', async () => {
    await showChart()
    buttonNamed('Download plot as a PNG').click()
    await vi.waitFor(() => expect(image.downloadBlob).toHaveBeenCalled())
    const [svg] = image.svgToBlob.mock.calls[0] as unknown as [string, any]
    const y = (text: string) => Number(new RegExp(`<text[^>]*y="([\\d.]+)"[^>]*>${text}`).exec(svg)![1])
    expect(y('Processed by wetterdienst')).toBeGreaterThan(y('Source: Deutscher Wetterdienst'))
    expect(y('Colours: mean of')).toBeGreaterThan(y('Processed by wetterdienst'))
  })

  it('says none in the saved image where the source line is not shown (GH-3799)', async () => {
    await showChart({ display: { ...DISPLAY, showSource: false } })
    buttonNamed('Download plot as a PNG').click()
    await vi.waitFor(() => expect(image.downloadBlob).toHaveBeenCalled())
    expect(image.svgToBlob.mock.calls[0]![0] as string).not.toContain('Processed by wetterdienst')
  })

  it('says the whole record where the station has too few years in a period, in the saved image too', async () => {
    const short = stripesAnswer(recordOf(2000, 2020, year => (year - 2000) / 10))
    await showChart({ values: short.values, reference: short.reference })
    buttonNamed('Download plot as a PNG').click()
    await vi.waitFor(() => expect(image.downloadBlob).toHaveBeenCalled())
    const [svg] = image.svgToBlob.mock.calls[0] as unknown as [string, any]
    expect(svg).toContain('Colours: mean of the whole record (2000–2020), ±2.6 σ of the whole record (2000–2020)')
  })

  it('is drawn in the light theme whatever the page shows, on the light paper', async () => {
    await showChart()
    // the page is dark: the chart on it says so
    expect(document.body.querySelector<HTMLElement>('.sc-canvas')!.dataset.chartScheme).toBe('dark')
    buttonNamed('Download plot as a PNG').click()
    await vi.waitFor(() => expect(image.downloadBlob).toHaveBeenCalled())
    const [svg, options] = image.svgToBlob.mock.calls[0] as unknown as [string, { background: string }]
    expect(options.background).toBe('rgb(255, 255, 255)')
    expect(svg).toContain(`fill="${LIGHT_TEXT}"`)
    // on the light paper, in the file too: the first thing the vector draws is the paper
    expect(svg).toMatch(/^<svg[^>]*>\s*<rect[^>]*fill="rgb\(255, 255, 255\)"/)
    expect(svg).not.toContain('rgb(250, 250, 250)')
  })

  it('is 945 px high where the title is off: the stripes keep their 765 px and lose the 10 px of the title', async () => {
    await showChart({ display: { ...DISPLAY, showTitle: false } })
    buttonNamed('Download plot as a PNG').click()
    await vi.waitFor(() => expect(image.svgToBlob).toHaveBeenCalled())
    expect((image.svgToBlob.mock.calls[0] as unknown as [string, any])[1]).toMatchObject({ width: 1400, height: 945, scale: 2 })
  })

  it('is saved for the menu at the size asked for, with the title broken for the width of the image, and in the range the stripes are zoomed to', async () => {
    const shown = await showChart()
    buttonNamed('Zoom in').click()
    await nextTick()
    buttonNamed('Later years').click()
    await nextTick()
    await (shown.vm as any).save({ format: 'jpeg', filename: 'name', width: 320, height: 600, scale: 3 })
    const [svg, options] = image.svgToBlob.mock.calls[0] as unknown as [string, any]
    // the 600 px of the page's chart and the rows that say what the colours are relative to, which a narrow image breaks into lines
    expect(options).toMatchObject({ format: 'jpeg', width: 320, scale: 3 })
    expect(options.height).toBeGreaterThanOrEqual(620)
    expect(image.downloadBlob.mock.calls[0]![1]).toBe('name.jpeg')
    // broken into lines where the image is narrow, not where the page is
    const texts = [...svg.matchAll(/<text[^>]*>([^<]*)<\/text>/g)].map(match => match[1])
    expect(texts.filter(text => TITLE.includes(text!) && text !== TITLE).length).toBeGreaterThan(1)
    // the years of the window and not the whole record
    const years = texts.filter(text => /^\d{4}$/.test(text!))
    expect(years).toHaveLength(2)
    expect(years).not.toContain('1950')
    expect(Number(years[0])).toBeGreaterThan(1960)
  })

  it('is saved as a vector without a scale', async () => {
    const shown = await showChart()
    await (shown.vm as any).save({ format: 'svg', filename: 'name', width: 704, height: 600, scale: 3 })
    expect(image.svgToBlob.mock.calls[0]![1]).toMatchObject({ format: 'svg', scale: 1 })
    expect(image.downloadBlob.mock.calls[0]![1]).toBe('name.svg')
  })

  it('says so where the camera\'s image could not be saved', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    image.svgToBlob.mockRejectedValueOnce(new Error('no canvas'))
    await showChart()
    buttonNamed('Download plot as a PNG').click()
    await vi.waitFor(() => expect(console.error).toHaveBeenCalled())
    await vi.waitFor(() => expect(toastAdd).toHaveBeenCalledWith({ title: 'The chart image could not be saved', color: 'error' }))
    expect(image.downloadBlob).not.toHaveBeenCalled()
  })
})
