import type { ExplorerSeries } from '~/utils/explorer-model'
import { mockNuxtImport, mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ExplorerChart from '~/components/ExplorerChart.vue'
import { boundsOf } from '~/utils/explorer-model'
import { explorerFrame, xOfTime } from '~/utils/explorer-option'

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

// the toast that tells the camera's outcome
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

const HOUR = 3_600_000
const DAY = 24 * HOUR
const START = Date.UTC(2026, 8, 1)

// two stations' daily temperatures of 30 days, and a trendline through the first
function daily(id: string, name: string, colorIndex: number, base: number, count = 30, step = DAY, firstAt = START): ExplorerSeries {
  return { id, name, colorIndex, kind: 'values', x: Array.from({ length: count }, (_, i) => firstAt + i * step), y: Array.from({ length: count }, (_, i) => Math.round((base + 4 * Math.sin(i / 4)) * 10) / 10) }
}
const A = daily('00011 - temp', '00011 - Temperature', 0, 12)
const B = daily('01048 - temp', '01048 - Temperature', 1, 8)
const TREND: ExplorerSeries = { id: '00011 - temp:trend', name: '00011 - Temperature (Trendline)', colorIndex: 0, kind: 'trend', x: [A.x[0]!, A.x.at(-1)!], y: [11, 13] }
const SERIES = [A, B, TREND]
const END = START + 29 * DAY

type Mounted = Awaited<ReturnType<typeof mountSuspended>>
let wrapper: Mounted | undefined

async function showChart(props: Record<string, unknown> = {}) {
  wrapper = await mountSuspended(ExplorerChart, {
    props: { series: SERIES, large: false, height: 400, label: 'Chart of the values', cameraFile: 'newplot', ...props },
    attachTo: document.body,
  })
  // the first mount of the file loads the language and the component's parts, which a loaded machine takes longer over than vitest's second
  await vi.waitFor(() => expect(echarts.chart.setOption).toHaveBeenCalled(), { timeout: 5000 })
  await flushPromises()
  return wrapper
}

// the test's document has no layout: the chart is 800 px wide, and where everything is, is the frame's
function frameOf(series: ExplorerSeries[] = SERIES, window = boundsOf(series)!, hidden: string[] = []) {
  const bounds = boundsOf(series)!
  const input = { series, hidden: new Set(hidden), theme: {} as any, window, bounds, width: 800, height: 400, large: false, locale: 'en' }
  return { frame: explorerFrame(input), window }
}
function xOf(t: number, window?: { start: number, end: number }) {
  const { frame, window: win } = frameOf(SERIES, window)
  return xOfTime(t, frame, win)
}
const stage = () => document.body.querySelector<HTMLElement>('.xc-stage')!
const readout = () => document.body.querySelector<HTMLElement>('[data-testid="explorer-readout"]')
const announce = () => document.body.querySelector('[data-testid="explorer-announce"]')!.textContent?.trim()
const drawn = () => echarts.chart.setOption.mock.calls.filter(([, flags]) => flags?.notMerge).length
const lastDrawing = () => echarts.chart.setOption.mock.calls.filter(([, flags]) => flags?.notMerge).at(-1)![0] as any
/** The crosshair's moment of the newest merge: null where it is taken away */
function crosshair() {
  const call = echarts.chart.setOption.mock.calls.filter(([option, flags]) => !flags?.notMerge && option.series?.[0]?.id === 'cursor').at(-1)
  return call ? (call[0].series[0].data[0]?.[0] ?? null) as number | null : undefined
}
function lastZoom() {
  const option = lastDrawing()
  return { start: option.dataZoom[0].startValue as number, end: option.dataZoom[0].endValue as number }
}

// a pointer event as a browser gives it; happy-dom has the class and not every field
function PLOT_MIDDLE() {
  const { frame } = frameOf()
  return frame.plot.top + frame.plot.height / 2
}
function pointer(type: string, init: { clientX?: number, clientY?: number, pointerType?: string, button?: number } = {}) {
  const event = new MouseEvent(type, { bubbles: true, cancelable: true, clientX: init.clientX ?? 0, clientY: init.clientY ?? PLOT_MIDDLE(), button: init.button ?? 0 })
  Object.defineProperty(event, 'pointerType', { value: init.pointerType ?? 'mouse' })
  Object.defineProperty(event, 'pointerId', { value: 1 })
  return event
}
function movePointerTo(x: number, y = PLOT_MIDDLE()) {
  stage().dispatchEvent(pointer('pointermove', { clientX: x, clientY: y }))
}
function key(name: string, init: KeyboardEventInit = {}) {
  stage().dispatchEvent(new KeyboardEvent('keydown', { key: name, bubbles: true, cancelable: true, ...init }))
}
const rows = () => [...readout()!.querySelectorAll('dt')].map((dt, i) => [dt.textContent!.trim(), readout()!.querySelectorAll('dd')[i]!.textContent!.trim()])
const buttonNamed = (name: string) => document.body.querySelector<HTMLButtonElement>(`.xc-toolbar button[aria-label="${name}"]`)!
/** Off: `aria-disabled`, never `disabled`, which would drop the focus of a button that turns off while it has it (WCAG 2.4.3, GH-4101) */
const isOff = (name: string) => buttonNamed(name).getAttribute('aria-disabled') === 'true'
const legendButtons = () => [...document.body.querySelectorAll<HTMLButtonElement>('.xc-legend button')]

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

describe('drawing', () => {
  it('draws an SVG chart as tall as the page has always had it, and listens for the zoom of the library', async () => {
    await showChart()
    expect(echarts.init).toHaveBeenCalledTimes(1)
    expect(echarts.init.mock.calls[0]![2]).toEqual({ renderer: 'svg', width: 800, height: 400 })
    expect(echarts.chart.on).toHaveBeenCalledWith('datazoom', expect.any(Function))
    expect(lastDrawing().series.map((s: any) => s.id)).toEqual(['00011 - temp', '01048 - temp', '00011 - temp:trend', 'legend', 'cursor'])
    expect(lastDrawing().animation).toBe(false)
  })

  it('is 300 px high as a facet, and higher where the legend takes many rows of a narrow chart', async () => {
    await showChart({ height: 300 })
    expect(echarts.init.mock.calls[0]![2]).toEqual({ renderer: 'svg', width: 800, height: 300 })
    expect(stage().style.height).toBe('300px')
  })

  it('draws again for what changes, and not for what does not', async () => {
    const shown = await showChart()
    const before = drawn()
    await shown.setProps({ large: true })
    await vi.waitFor(() => expect(drawn()).toBe(before + 1), { timeout: 5000 })
    expect(lastDrawing().series[0].showSymbol).toBe(false)
    await shown.setProps({ large: true })
    await flushPromises()
    expect(drawn()).toBe(before + 1)
  })

  it('says it is drawn, and in which scheme', async () => {
    await showChart()
    const canvas = document.body.querySelector<HTMLElement>('.xc-canvas')!
    expect(canvas.dataset.drawn).toBe('true')
    // the page of the test is dark (the theme it reads is the mock's)
    expect(canvas.dataset.chartScheme).toBe('dark')
  })

  it('is a named figure with one tab stop, described by its keys', async () => {
    await showChart({ describedBy: 'summary' })
    expect(stage().getAttribute('role')).toBe('figure')
    expect(stage().getAttribute('tabindex')).toBe('0')
    expect(stage().getAttribute('aria-label')).toBe('Chart of the values')
    expect(stage().getAttribute('aria-describedby')!.split(' ')[0]).toBe('summary')
    expect(document.body.querySelector(`#${stage().getAttribute('aria-describedby')!.split(' ')[1]}`)!.textContent).toContain('arrow keys')
    // the canvas is the picture; what it says is in the readout, the sentence and the table
    expect(document.body.querySelector('.xc-canvas')!.getAttribute('aria-hidden')).toBe('true')
  })

  it('names the keys of the chart as ARIA writes them: the plus key is Plus, since + is the separator', async () => {
    await showChart()
    const shortcuts = stage().getAttribute('aria-keyshortcuts')!.split(' ')
    expect(shortcuts).toContain('Plus')
    expect(shortcuts.some(key => key.includes('+'))).toBe(false)
    expect(shortcuts).toEqual(expect.arrayContaining(['ArrowLeft', 'ArrowRight', 'PageUp', 'PageDown', 'Home', 'End', '-', '0', 'Escape']))
  })

  it('disposes the chart where it goes', async () => {
    const shown = await showChart()
    shown.unmount()
    expect(echarts.chart.dispose).toHaveBeenCalled()
  })

  it('draws nothing where no series has a point', async () => {
    await mountSuspended(ExplorerChart, { props: { series: [], large: false, height: 400, label: 'x', cameraFile: 'f' }, attachTo: document.body })
    await flushPromises()
    expect(echarts.chart.setOption).not.toHaveBeenCalled()
  })

  it('cuts a long series to what the plot can tell apart, and keeps its highest and lowest value', async () => {
    const long: ExplorerSeries = { id: 'long', name: 'long', colorIndex: 0, kind: 'values', x: Array.from({ length: 87_600 }, (_, i) => START + i * HOUR), y: Array.from({ length: 87_600 }, (_, i) => Math.sin(i / 500)) }
    long.y[40_001] = 5
    await showChart({ series: [long], large: true })
    const data = lastDrawing().series[0].data as [number, number | null][]
    expect(data.length).toBeLessThan(4 * 800)
    expect(Math.max(...data.map(point => point[1]!))).toBe(5)
  })

  it('says so where the chart\'s code could not be loaded, and loads it again on Retry', async () => {
    echarts.state.loadFails = true
    vi.spyOn(console, 'error').mockImplementation(() => {})
    const shown = await mountSuspended(ExplorerChart, { props: { series: SERIES, large: false, height: 400, label: 'x', cameraFile: 'f' }, attachTo: document.body })
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

  it('tells a Retry that fails too anew, and the reload is offered only where the code is what failed', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    const shown = await showChart()
    echarts.chart.setOption.mockImplementation(() => {
      throw new Error('drawing failed')
    })
    await shown.setProps({ large: true })
    await vi.waitFor(() => expect((shown.vm as any).renderFailed).toBe(true))
    expect((shown.vm as any).renderFailures).toBe(1)
    expect([...document.body.querySelectorAll('button')].some(button => button.textContent?.includes('Reload'))).toBe(false)
    const retry = () => [...document.body.querySelectorAll('button')].find(button => button.textContent?.includes('Retry'))!
    retry().click()
    await vi.waitFor(() => expect((shown.vm as any).renderFailures).toBe(2))
    // the button is the same one, which keeps its focus
    expect(retry()).toBeTruthy()
  })

  it('puts the toolbar and the chart out of reach while it could not be drawn, and back where it is', async () => {
    echarts.state.loadFails = true
    vi.spyOn(console, 'error').mockImplementation(() => {})
    const shown = await mountSuspended(ExplorerChart, { props: { series: SERIES, large: false, height: 400, label: 'x', cameraFile: 'f' }, attachTo: document.body })
    await vi.waitFor(() => expect((shown.vm as any).renderFailed).toBe(true))
    const toolbar = document.body.querySelector('.xc-toolbar')!
    const frame = document.body.querySelector('.xc-frame')!
    expect(toolbar.hasAttribute('inert')).toBe(true)
    expect(frame.hasAttribute('inert')).toBe(true)
    // the notice and its Retry are not
    expect(document.body.querySelector('[role="alert"]')!.closest('[inert]')).toBeNull()

    echarts.state.loadFails = false
    const retry = [...document.body.querySelectorAll('button')].find(button => button.textContent?.includes('Retry'))!
    retry.click()
    await vi.waitFor(() => expect((shown.vm as any).renderFailed).toBe(false))
    await flushPromises()
    expect(toolbar.hasAttribute('inert')).toBe(false)
    expect(frame.hasAttribute('inert')).toBe(false)
  })

  it('moves the focus to Retry where a drawing fails while it is in the toolbar, the legend or on the chart, which the notice puts out of reach', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    const shown = await showChart()
    const retry = () => [...document.body.querySelectorAll('button')].find(button => button.textContent?.includes('Retry'))
    let large = false
    const failAfter = async (focus: () => void) => {
      focus()
      echarts.chart.setOption.mockImplementation(() => {
        throw new Error('drawing failed')
      })
      large = !large
      await shown.setProps({ large })
      await vi.waitFor(() => expect((shown.vm as any).renderFailed).toBe(true))
      await flushPromises()
    }
    const recover = async () => {
      echarts.chart.setOption.mockReset()
      retry()!.click()
      await vi.waitFor(() => expect((shown.vm as any).renderFailed).toBe(false))
      await flushPromises()
    }

    await failAfter(() => buttonNamed('Zoom in').focus())
    expect(document.activeElement).toBe(retry())
    await recover()

    await failAfter(() => legendButtons()[0]!.focus())
    expect(document.activeElement).toBe(retry())
    await recover()

    await failAfter(() => stage().focus())
    expect(document.activeElement).toBe(retry())
    await recover()

    // elsewhere: it stays
    const elsewhere = document.body.appendChild(document.createElement('button'))
    await failAfter(() => elsewhere.focus())
    expect(document.activeElement).toBe(elsewhere)
  })
})

describe('the legend', () => {
  it('has a button for each series, in the order the legend draws them, that says it is on and which series it is', async () => {
    await showChart()
    const buttons = legendButtons()
    expect(buttons.map(button => button.getAttribute('aria-label'))).toEqual(['00011 - Temperature', '01048 - Temperature', '00011 - Temperature (Trendline)'])
    expect(buttons.every(button => button.getAttribute('aria-pressed') === 'true')).toBe(true)
    expect(document.body.querySelector('.xc-legend')!.getAttribute('role')).toBe('group')
    // it is before the chart in the tab order
    expect(document.body.querySelector('.xc-legend')!.compareDocumentPosition(stage()) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('turns a series off with a click, which draws the chart without it, and on again with another', async () => {
    await showChart()
    const before = drawn()
    legendButtons()[1]!.click()
    await vi.waitFor(() => expect(drawn()).toBe(before + 1), { timeout: 5000 })
    expect(lastDrawing().series.map((s: any) => s.id)).not.toContain('01048 - temp')
    expect(legendButtons()[1]!.getAttribute('aria-pressed')).toBe('false')
    // the legend still lists it, drawn as one that is off
    expect(lastDrawing().series.find((s: any) => s.id === 'legend').data).toHaveLength(3)
    legendButtons()[1]!.click()
    await vi.waitFor(() => expect(drawn()).toBe(before + 2), { timeout: 5000 })
    expect(lastDrawing().series.map((s: any) => s.id)).toContain('01048 - temp')
    expect(legendButtons()[1]!.getAttribute('aria-pressed')).toBe('true')
  })

  it('leaves a series that is off out of the readout and the keys', async () => {
    await showChart()
    legendButtons()[1]!.click()
    await flushPromises()
    key('ArrowRight')
    await flushPromises()
    expect(rows().map(([name]) => name)).toEqual(['00011 - Temperature'])
  })

  it('leaves the moments of a series that is off out of the keys', async () => {
    // a series whose readings are at noon: with it off the keys go from one midnight to the next, not by its noons
    const noons = daily('noon', 'Noon', 2, 5, 30, DAY, START + 12 * HOUR)
    await showChart({ series: [A, noons] })
    legendButtons()[1]!.click()
    await flushPromises()
    key('ArrowRight')
    key('ArrowRight')
    await flushPromises()
    // the time is given (the readings of the other series are at noon), and it is midnight: the next day, not the noon between
    expect(announce()).toMatch(/^Sep 2, 2026, 00:00 UTC: /)
  })

  it('forgets a series an answer no longer has, so that one that comes back is on', async () => {
    const shown = await showChart()
    legendButtons()[1]!.click()
    await flushPromises()
    await shown.setProps({ series: [A] })
    await flushPromises()
    await shown.setProps({ series: SERIES })
    await flushPromises()
    expect(legendButtons().every(button => button.getAttribute('aria-pressed') === 'true')).toBe(true)
  })

  it('does not take the keys of the chart, which its buttons keep for themselves', async () => {
    await showChart()
    legendButtons()[0]!.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true, cancelable: true }))
    await flushPromises()
    expect(readout()).toBeNull()
  })
})

describe('the readout', () => {
  it('shows the day, and the value of each series that has one there, under the pointer, and takes it away where the pointer leaves', async () => {
    await showChart()
    expect(readout()).toBeNull()
    movePointerTo(xOf(START + 10 * DAY))
    await flushPromises()
    expect(readout()!.textContent).toContain('Sep 11, 2026')
    expect(rows().map(([name]) => name)).toEqual(['00011 - Temperature', '01048 - Temperature'])
    expect(rows()[0]![1]).toBe(String(A.y[10]))
    expect(readout()!.getAttribute('role')).toBe('group')
    expect(readout()!.getAttribute('aria-label')).toBe('Values at Sep 11, 2026')
    stage().dispatchEvent(pointer('pointerleave'))
    await flushPromises()
    expect(readout()).toBeNull()
  })

  it('gives the time in UTC where the readings are not at midnight', async () => {
    const hourly = daily('h', 'Hourly', 0, 5, 48, HOUR, START + 6 * HOUR)
    await showChart({ series: [hourly] })
    const { frame, window } = frameOf([hourly])
    movePointerTo(xOfTime(START + 10 * HOUR, frame, window))
    await flushPromises()
    expect(readout()!.textContent).toContain('Sep 1, 2026, 10:00 UTC')
  })

  it('lists a series only at a moment it has a point at, as the hover label of the chart did', async () => {
    const sparse = daily('s', 'Sparse', 2, 3, 10, 3 * DAY)
    await showChart({ series: [A, sparse] })
    const bounds = boundsOf([A, sparse])!
    const { frame } = frameOf([A, sparse])
    movePointerTo(xOfTime(START + 3 * DAY, frame, bounds))
    await flushPromises()
    expect(rows().map(([name]) => name)).toEqual(['00011 - Temperature', 'Sparse'])
    movePointerTo(xOfTime(START + 4 * DAY, frame, bounds))
    await flushPromises()
    expect(rows().map(([name]) => name)).toEqual(['00011 - Temperature'])
  })

  it('has none over the legend, the time labels or the gutter, which are no plot', async () => {
    await showChart()
    const { frame } = frameOf()
    const x = xOf(START + 10 * DAY)
    for (const y of [2, frame.plot.top - 2, frame.plot.top + frame.plot.height + 4, 395]) {
      movePointerTo(x, y)
      await flushPromises()
      expect(readout(), `the pointer at ${y} px`).toBeNull()
    }
    movePointerTo(frame.plot.left - 10)
    await flushPromises()
    expect(readout()).toBeNull()
    movePointerTo(x)
    await flushPromises()
    expect(readout()).not.toBeNull()
    // a tap there selects nothing either
    stage().dispatchEvent(pointer('click', { clientX: x, clientY: 395, pointerType: 'touch' }))
    movePointerTo(x, 3)
    await flushPromises()
    expect(readout()).toBeNull()
  })

  it('has a crosshair at the moment, and a dot on each series, drawn in the chart and not as an element of the page', async () => {
    await showChart()
    expect(crosshair()).toBeNull()
    movePointerTo(xOf(START + 10 * DAY))
    await flushPromises()
    expect(crosshair()).toBe(START + 10 * DAY)
    stage().dispatchEvent(pointer('pointerleave'))
    await flushPromises()
    expect(crosshair()).toBeNull()
  })

  it('is docked at an edge of the chart, on the side the crosshair is not on, so that a pointer does not meet it on the way, and is persistent and closed by Escape (WCAG 1.4.13)', async () => {
    await showChart()
    movePointerTo(xOf(START + 5 * DAY))
    await flushPromises()
    const element = readout()!
    // the crosshair is in the left half: the readout is at the right edge, clear of it
    const left = Number.parseFloat(element.style.left)
    expect(left).toBeGreaterThan(xOf(START + 5 * DAY) + 6)
    expect(left + Number.parseFloat(element.style.width)).toBeLessThanOrEqual(800)
    // a pointer over the readout leaves the crosshair where it was and keeps the readout
    element.dispatchEvent(pointer('pointermove', { clientX: left + 20 }))
    await flushPromises()
    expect(readout()).not.toBeNull()
    expect(readout()!.textContent).toContain('Sep 6, 2026')
    // persistent: it stays while the pointer rests
    await new Promise(resolve => setTimeout(resolve, 50))
    expect(readout()).not.toBeNull()
    // dismissible: Escape, wherever the focus is, and not consumed
    const escape = new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true })
    document.body.dispatchEvent(escape)
    await flushPromises()
    expect(readout()).toBeNull()
    expect(escape.defaultPrevented).toBe(false)
    // and the crosshair goes with it
    expect(crosshair()).toBeNull()
    // a jitter of the pointer at the same moment brings it back no more than a pixel does
    movePointerTo(xOf(START + 5 * DAY))
    await flushPromises()
    expect(readout()).toBeNull()
    // another moment is a new hover
    movePointerTo(xOf(START + 12 * DAY))
    await flushPromises()
    expect(readout()).not.toBeNull()
  })

  it('goes to the other edge where the crosshair is in the right half', async () => {
    await showChart()
    movePointerTo(xOf(START + 25 * DAY))
    await flushPromises()
    expect(Number.parseFloat(readout()!.style.left)).toBeLessThan(xOf(START + 25 * DAY) - 6)
  })

  it('has a Close button for a touch, which closes it', async () => {
    await showChart()
    movePointerTo(xOf(START + 10 * DAY))
    await flushPromises()
    readout()!.querySelector<HTMLButtonElement>('.xc-close')!.click()
    await flushPromises()
    expect(readout()).toBeNull()
  })

  it('gives the focus back to the chart where its Close button, which had it, goes with the readout', async () => {
    await showChart()
    key('ArrowRight')
    await flushPromises()
    const close = () => readout()!.querySelector<HTMLButtonElement>('.xc-close')!
    close().focus()
    expect(document.activeElement).toBe(close())
    // without scrolling the page to the chart, which is where the focus already is in the page
    const focus = vi.spyOn(stage(), 'focus')
    close().click()
    await flushPromises()
    expect(readout()).toBeNull()
    expect(document.activeElement).toBe(stage())
    expect(focus).toHaveBeenCalledWith({ preventScroll: true })

    // by Escape while it has the focus
    key('ArrowRight')
    await flushPromises()
    close().focus()
    document.activeElement!.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }))
    await flushPromises()
    expect(readout()).toBeNull()
    expect(document.activeElement).toBe(stage())
  })

  it('stays for a tap until it is closed, and a pointer that leaves does not take it away', async () => {
    await showChart()
    stage().dispatchEvent(pointer('click', { clientX: xOf(START + 8 * DAY), pointerType: 'touch' }))
    await flushPromises()
    expect(readout()!.textContent).toContain('Sep 9, 2026')
    stage().dispatchEvent(pointer('pointerleave', { pointerType: 'touch' }))
    await flushPromises()
    expect(readout()).not.toBeNull()
  })

  it('has none for a moment out of the window, which is out of sight', async () => {
    await showChart()
    key('ArrowRight')
    await flushPromises()
    buttonNamed('Zoom in').click()
    buttonNamed('Zoom in').click()
    buttonNamed('Zoom in').click()
    await flushPromises()
    buttonNamed('Later').click()
    buttonNamed('Later').click()
    await flushPromises()
    // the first moment is behind the window now
    expect(readout()).toBeNull()
  })
})

describe('the keys', () => {
  it('step through the moments that have a value, and say each one', async () => {
    await showChart()
    key('ArrowRight')
    await flushPromises()
    expect(readout()!.textContent).toContain('Sep 1, 2026')
    expect(announce()).toBe(`Sep 1, 2026: 00011 - Temperature: ${A.y[0]}; 01048 - Temperature: ${B.y[0]}`)
    key('ArrowRight')
    await flushPromises()
    expect(announce()).toContain('Sep 2, 2026')
    key('ArrowLeft')
    key('ArrowLeft')
    await flushPromises()
    // Left stops at the first
    expect(announce()).toContain('Sep 1, 2026')
    expect(crosshair()).toBe(START)
  })

  it('go ten moments with Shift, by a window with Page Up and Page Down, and to the ends with Home and End', async () => {
    await showChart()
    key('Home')
    key('ArrowRight', { shiftKey: true })
    await flushPromises()
    expect(announce()).toContain('Sep 11, 2026')
    key('End')
    await flushPromises()
    expect(announce()).toContain('Sep 30, 2026')
    key('PageUp')
    await flushPromises()
    // the whole chart is the window: a page is all of it, and stops at the first
    expect(announce()).toContain('Sep 1, 2026')
    buttonNamed('Zoom in').click()
    buttonNamed('Zoom in').click()
    await flushPromises()
    key('Home')
    key('PageDown')
    await flushPromises()
    const first = announce()
    expect(first).toMatch(/^Sep (?:[7-9]|1\d), 2026/)
  })

  it('zoom with plus, minus and 0, round the crosshair', async () => {
    await showChart()
    key('+')
    await flushPromises()
    const zoomed = lastZoom()
    expect(zoomed.end - zoomed.start).toBeCloseTo(29 * DAY / 1.5, -3)
    key('-')
    await flushPromises()
    expect(lastZoom().end - lastZoom().start).toBeCloseTo(29 * DAY, -3)
    key('+')
    key('+')
    key('0')
    await flushPromises()
    expect(lastZoom()).toMatchObject({ start: START, end: END })
  })

  it('move the window with the crosshair where a moment is out of it', async () => {
    await showChart()
    key('+')
    key('+')
    key('+')
    await flushPromises()
    const win = lastZoom()
    key('End')
    await flushPromises()
    expect(lastZoom().end).toBeCloseTo(END, -3)
    expect(lastZoom().start).toBeGreaterThan(win.start)
  })

  it('zoom round the middle of the window where the crosshair is out of it, and round the crosshair where it is in', async () => {
    await showChart()
    key('ArrowRight')
    await flushPromises()
    // in view: the window stays round the crosshair, the first moment, at the left edge
    buttonNamed('Zoom in').click()
    buttonNamed('Zoom in').click()
    buttonNamed('Zoom in').click()
    await flushPromises()
    expect(lastZoom().start).toBeCloseTo(START, -4)
    // moved away from it: the crosshair is behind the window
    buttonNamed('Later').click()
    buttonNamed('Later').click()
    await flushPromises()
    expect(readout()).toBeNull()
    const before = lastZoom()
    buttonNamed('Zoom in').click()
    await flushPromises()
    const after = lastZoom()
    const middle = (window: { start: number, end: number }) => (window.start + window.end) / 2
    // round the middle of the window, as with no crosshair, and not drawn towards a moment that is out of sight
    expect(Math.abs(middle(after) - middle(before))).toBeLessThan(0.01 * (before.end - before.start))
    expect(after.end - after.start).toBeLessThan(before.end - before.start)
  })

  it('has no crosshair where no series that is shown has a value at its moment', async () => {
    const noons = daily('noon', 'Noon', 2, 5, 30, DAY, START + 12 * HOUR)
    await showChart({ series: [A, noons] })
    key('ArrowRight')
    key('ArrowRight')
    await flushPromises()
    expect(crosshair()).toBe(START + 12 * HOUR)
    // the series that has the noon is turned off: the moment stays, and there is nothing to mark
    legendButtons()[1]!.click()
    await flushPromises()
    expect(crosshair()).toBeNull()
  })

  it('leave Escape and the keys with a modifier alone', async () => {
    await showChart()
    const escape = new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true })
    stage().dispatchEvent(escape)
    expect(escape.defaultPrevented).toBe(false)
    const ctrl = new KeyboardEvent('keydown', { key: 'ArrowRight', ctrlKey: true, bubbles: true, cancelable: true })
    stage().dispatchEvent(ctrl)
    expect(ctrl.defaultPrevented).toBe(false)
    await flushPromises()
    expect(readout()).toBeNull()
  })

  it('take the readout away where the focus leaves the chart', async () => {
    await showChart()
    key('ArrowRight')
    await flushPromises()
    expect(readout()).not.toBeNull()
    stage().dispatchEvent(new FocusEvent('blur', { relatedTarget: document.body }))
    await flushPromises()
    expect(readout()).toBeNull()
  })
})

describe('the zoom', () => {
  it('has the buttons of what a drag and the keys do, which are off where they would do nothing', async () => {
    await showChart()
    expect(document.body.querySelector('.xc-toolbar')!.getAttribute('role')).toBe('group')
    expect(isOff('Zoom out')).toBe(true)
    expect(isOff('Reset zoom')).toBe(true)
    expect(isOff('Earlier')).toBe(true)
    expect(isOff('Later')).toBe(true)
    buttonNamed('Zoom in').click()
    await flushPromises()
    expect(isOff('Zoom out')).toBe(false)
    expect(isOff('Later')).toBe(false)
    buttonNamed('Later').click()
    await flushPromises()
    expect(lastZoom().end).toBeCloseTo(END, -3)
    buttonNamed('Earlier').click()
    await flushPromises()
    expect(lastZoom().end).toBeLessThan(END)
    buttonNamed('Reset zoom').click()
    await flushPromises()
    expect(lastZoom()).toMatchObject({ start: START, end: END })
  })

  it('has a y axis that follows the window, so that a zoomed chart is not flat', async () => {
    const wide = daily('w', 'W', 0, 0, 30)
    wide.y = wide.y.map((_, i) => (i < 15 ? 5 + (i % 3) : 50 + (i % 3)))
    await showChart({ series: [wide] })
    const full = lastDrawing().yAxis[0]
    expect(full.max).toBeGreaterThanOrEqual(50)
    stage().dispatchEvent(pointer('pointerdown', { clientX: xOf(START + 1 * DAY, boundsOf([wide])!) }))
    stage().dispatchEvent(pointer('pointermove', { clientX: xOf(START + 10 * DAY, boundsOf([wide])!) }))
    stage().dispatchEvent(pointer('pointerup', { clientX: xOf(START + 10 * DAY, boundsOf([wide])!) }))
    await vi.waitFor(() => expect(lastDrawing().yAxis[0].max).toBeLessThan(full.max))
    expect(lastDrawing().yAxis[0].max).toBeLessThan(20)
  })

  it('zooms to a box dragged with a mouse, and resets on a double click', async () => {
    await showChart()
    stage().dispatchEvent(pointer('pointerdown', { clientX: xOf(START + 5 * DAY) }))
    stage().dispatchEvent(pointer('pointermove', { clientX: xOf(START + 15 * DAY) }))
    await flushPromises()
    expect(document.body.querySelector('.xc-selection')).not.toBeNull()
    stage().dispatchEvent(pointer('pointerup', { clientX: xOf(START + 15 * DAY) }))
    await flushPromises()
    expect(lastZoom().start).toBeCloseTo(START + 5 * DAY, -4)
    expect(lastZoom().end).toBeCloseTo(START + 15 * DAY, -4)
    expect(document.body.querySelector('.xc-selection')).toBeNull()
    stage().dispatchEvent(new MouseEvent('dblclick', { bubbles: true }))
    await flushPromises()
    expect(lastZoom()).toMatchObject({ start: START, end: END })
  })

  it('keeps a button that turns off in the tab order with the focus, and does nothing when it is pressed (WCAG 2.4.3, GH-4101)', async () => {
    await showChart()
    buttonNamed('Zoom in').click()
    await flushPromises()
    const reset = buttonNamed('Reset zoom')
    expect(isOff('Reset zoom')).toBe(false)
    reset.focus()
    reset.click()
    await flushPromises()
    // off, and still a button that can have the focus: a `disabled` one would hand it to the page
    expect(isOff('Reset zoom')).toBe(true)
    expect(reset.disabled).toBe(false)
    expect(reset.tabIndex).toBeGreaterThanOrEqual(0)
    expect(document.activeElement).toBe(reset)
    // pressed again, it does nothing: the whole chart stays, and Zoom out (off too) does nothing either
    const calls = echarts.chart.setOption.mock.calls.length
    reset.click()
    buttonNamed('Zoom out').click()
    buttonNamed('Earlier').click()
    await flushPromises()
    expect(echarts.chart.setOption.mock.calls.length).toBe(calls)
    expect(isOff('Reset zoom')).toBe(true)
    expect(document.activeElement).toBe(reset)
  })

  it('starts no zoom box over the legend or the labels', async () => {
    await showChart()
    stage().dispatchEvent(pointer('pointerdown', { clientX: xOf(START + 5 * DAY), clientY: 395 }))
    stage().dispatchEvent(pointer('pointermove', { clientX: xOf(START + 15 * DAY), clientY: 395 }))
    await flushPromises()
    expect(document.body.querySelector('.xc-selection')).toBeNull()
    stage().dispatchEvent(pointer('pointerup', { clientX: xOf(START + 15 * DAY), clientY: 395 }))
    await flushPromises()
    expect(isOff('Reset zoom')).toBe(true)
  })

  it('takes the zoom of the library\'s own gestures (a pinch), and not its echo of a window the component set', async () => {
    await showChart()
    const handler = echarts.chart.on.mock.calls.find(([name]) => name === 'datazoom')![1] as (event: unknown) => void
    handler({ batch: [{ startValue: START + 5 * DAY, endValue: START + 12 * DAY }] })
    await flushPromises()
    expect(lastZoom()).toMatchObject({ start: START + 5 * DAY, end: START + 12 * DAY })
    const calls = echarts.chart.setOption.mock.calls.length
    handler({ batch: [{ startValue: START + 5 * DAY, endValue: START + 12 * DAY }] })
    await flushPromises()
    expect(echarts.chart.setOption.mock.calls.length).toBe(calls)
  })

  it('keeps the zoom where the series change but not the times they cover, and starts over for other times', async () => {
    const shown = await showChart()
    buttonNamed('Zoom in').click()
    await flushPromises()
    const zoomed = lastZoom()
    await shown.setProps({ series: [{ ...A, name: 'Renamed' }, B, TREND] })
    await flushPromises()
    expect(isOff('Reset zoom')).toBe(false)
    expect(lastZoom()).toMatchObject({ start: zoomed.start, end: zoomed.end })
    await shown.setProps({ series: [daily('other', 'Other', 0, 5, 10)] })
    await flushPromises()
    expect(isOff('Reset zoom')).toBe(true)
  })
})

describe('the image', () => {
  it('is saved as the camera does: a PNG as large as the chart is shown, one pixel to a pixel, in the light theme, named newplot', async () => {
    await showChart()
    buttonNamed('Download plot as a PNG').click()
    await vi.waitFor(() => expect(image.downloadBlob).toHaveBeenCalled())
    const [svg, options] = image.svgToBlob.mock.calls[0] as unknown as [string, any]
    expect(options).toMatchObject({ format: 'png', width: 800, height: 400, scale: 1, background: 'rgb(255, 255, 255)' })
    expect(svg).toContain('width="800" height="400"')
    expect(image.downloadBlob.mock.calls[0]![1]).toBe('newplot.png')
    await vi.waitFor(() => expect(toastAdd).toHaveBeenCalledWith({ title: 'Downloaded', description: 'Chart downloaded as PNG', color: 'success' }))
  })

  it('is drawn in the light theme whatever the page shows, on the light paper, with the legend in it', async () => {
    await showChart()
    // the page is dark: the chart on it says so
    expect(document.body.querySelector<HTMLElement>('.xc-canvas')!.dataset.chartScheme).toBe('dark')
    buttonNamed('Download plot as a PNG').click()
    await vi.waitFor(() => expect(image.downloadBlob).toHaveBeenCalled())
    const [svg] = image.svgToBlob.mock.calls[0] as unknown as [string]
    expect(svg).toContain(`fill="${LIGHT_TEXT}"`)
    expect(svg).toMatch(/^<svg[^>]*>\s*<rect[^>]*fill="rgb\(255, 255, 255\)"/)
    expect(svg).not.toContain('rgb(250, 250, 250)')
    // the legend's text, and the labels of the axes
    expect(svg).toContain('00011 - Temperature')
    expect(svg).toContain('01048 - Temperature (Trendline)'.replace('01048', '00011'))
  })

  it('is the chart as it is shown: the window it is zoomed to, and the series its legend has on', async () => {
    const shown = await showChart()
    legendButtons()[1]!.click()
    buttonNamed('Zoom in').click()
    await flushPromises()
    buttonNamed('Later').click()
    await flushPromises()
    await (shown.vm as any).save({ format: 'jpeg', filename: 'chart' })
    const [svg, options] = image.svgToBlob.mock.calls[0] as unknown as [string, any]
    expect(options).toMatchObject({ format: 'jpeg', width: 800, height: 400, scale: 1 })
    expect(image.downloadBlob.mock.calls[0]![1]).toBe('chart.jpeg')
    // the series that is off is in the legend and not among the lines
    expect(svg).not.toMatch(/Sep 1(?!\d)/)
    expect(svg.match(/stroke="#16a34a"/g)?.length ?? 0).toBeLessThanOrEqual(3)
  })

  it('is saved as a vector for the menu, at the same size', async () => {
    const shown = await showChart()
    await (shown.vm as any).save({ format: 'svg', filename: 'chart' })
    expect(image.svgToBlob.mock.calls[0]![1]).toMatchObject({ format: 'svg', scale: 1, width: 800, height: 400 })
    expect(image.downloadBlob.mock.calls[0]![1]).toBe('chart.svg')
  })

  it('hands the drawing of a facet to the viewer, which stacks the facets', async () => {
    const shown = await showChart({ height: 300 })
    const part = await (shown.vm as any).renderSvg()
    expect(part).toMatchObject({ width: 800, height: 300, paper: 'rgb(255, 255, 255)' })
    expect(part.svg).toContain('<svg')
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
