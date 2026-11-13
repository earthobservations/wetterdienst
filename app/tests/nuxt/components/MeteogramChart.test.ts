import { mockNuxtImport, mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import MeteogramChart from '~/components/MeteogramChart.vue'
import { HOUR_MS } from '~/utils/meteogram-geometry'
import { buildSeries } from '~/utils/meteogram-series'
import { meteogramUnits } from '~/utils/meteogram-units'
import { FORECAST_START, FORECAST_UNITS, forecastValues } from '../../helpers/meteogram-forecast'

// ECharts draws nothing in the test's document: its calls are recorded, and the chart is held to the option it is given
const echarts = vi.hoisted(() => {
  const chart = {
    on: vi.fn(),
    resize: vi.fn(),
    setOption: vi.fn(),
    dispatchAction: vi.fn(),
    getDom: vi.fn(),
    dispose: vi.fn(),
  }
  const init = vi.fn((element: HTMLElement) => {
    chart.getDom.mockReturnValue(element)
    return chart
  })
  return { chart, init }
})
vi.mock('~/utils/echarts-loader', () => ({ loadEcharts: () => ({ init: echarts.init }) }))

// Nuxt's reload of the page: the test's document does not take it
const { reloadNuxtApp } = vi.hoisted(() => ({ reloadNuxtApp: vi.fn() }))
mockNuxtImport('reloadNuxtApp', () => reloadNuxtApp)

const t0 = new Date(FORECAST_START).getTime()
const ALL_PANELS = { temp: true, wind: true, precip: true, cloud: true, pressure: true }
const units = meteogramUnits(FORECAST_UNITS, (key, named) => key + (named ? JSON.stringify(named) : ''))

type Mounted = Awaited<ReturnType<typeof mountSuspended>>
let wrapper: Mounted | undefined

async function showChart(props: Record<string, unknown> = {}) {
  wrapper = await mountSuspended(MeteogramChart, {
    props: {
      series: buildSeries(forecastValues() as any),
      panels: ALL_PANELS,
      horizonHours: null,
      zone: 'Europe/Berlin',
      stationCoords: { latitude: 52.5, longitude: 13.4 },
      units,
      label: 'Forecast chart for Berlin',
      ...props,
    },
    attachTo: document.body,
  })
  await vi.waitFor(() => expect(echarts.chart.setOption).toHaveBeenCalled())
  await flushPromises()
  return wrapper
}

const stage = () => document.body.querySelector<HTMLElement>('.mg-stage')!
const readout = () => document.body.querySelector<HTMLElement>('[data-testid="meteogram-readout"]')
const announce = () => document.body.querySelector('[data-testid="meteogram-announce"]')!.textContent?.trim()
const lastOption = () => echarts.chart.setOption.mock.calls.at(-1)![0] as any
function zoomWindow() {
  const call = echarts.chart.dispatchAction.mock.calls.filter(([action]) => action.type === 'dataZoom').at(-1)![0]
  return { start: call.startValue as number, end: call.endValue as number }
}

// a pointer event as a browser gives it; happy-dom has the class and not every field
function pointer(type: string, init: { clientX?: number, clientY?: number, pointerType?: string, button?: number } = {}) {
  const event = new MouseEvent(type, { bubbles: true, cancelable: true, clientX: init.clientX ?? 0, clientY: init.clientY ?? 0, button: init.button ?? 0 })
  Object.defineProperty(event, 'pointerType', { value: init.pointerType ?? 'mouse' })
  Object.defineProperty(event, 'pointerId', { value: 1 })
  return event
}
function key(name: string, init: KeyboardEventInit = {}) {
  stage().dispatchEvent(new KeyboardEvent('keydown', { key: name, bubbles: true, cancelable: true, ...init }))
}

beforeEach(() => {
  echarts.chart.on.mockClear()
  echarts.chart.setOption.mockClear()
  echarts.chart.dispatchAction.mockClear()
  echarts.chart.dispose.mockClear()
  echarts.init.mockClear()
  vi.restoreAllMocks()
})
afterEach(() => {
  wrapper?.unmount()
  wrapper = undefined
  document.body.innerHTML = ''
})

describe('the chart is drawn', { timeout: 15_000 }, () => {
  it('once, as an SVG of the width the screen gives and the height the panels have', async () => {
    await showChart()
    expect(echarts.init).toHaveBeenCalledTimes(1)
    const [, , options] = echarts.init.mock.calls[0] as any
    expect(options.renderer).toBe('svg')
    // a window with no width to measure is a desktop's: 800 px, and the five panels' fixed heights
    expect(options.width).toBe(800)
    expect(options.height).toBe(674)
    expect(echarts.chart.setOption).toHaveBeenCalledTimes(1)
  })

  it('names the figure by its station and gives it one tab stop', async () => {
    await showChart()
    expect(stage().getAttribute('role')).toBe('figure')
    expect(stage().getAttribute('aria-label')).toBe('Forecast chart for Berlin')
    expect(stage().tabIndex).toBe(0)
    expect(document.body.querySelectorAll('[tabindex="0"]').length).toBe(1)
  })

  it('has the same shape on a phone and on a desktop: the panels at their heights and the hour at its width', async () => {
    const widths = [320, 800, 1400]
    const seen: { height: number, window: number }[] = []
    for (const width of widths) {
      echarts.init.mockClear()
      echarts.chart.setOption.mockClear()
      vi.spyOn(HTMLElement.prototype, 'clientWidth', 'get').mockReturnValue(width)
      const mounted = await showChart()
      const [, , options] = echarts.init.mock.calls[0] as any
      const dataZoom = lastOption().dataZoom[0]
      // the hours across the plot, and with them the width of one
      const plot = width - 68 - 10
      seen.push({ height: options.height, window: plot / ((dataZoom.endValue - dataZoom.startValue) / HOUR_MS) })
      mounted.unmount()
      wrapper = undefined
      vi.restoreAllMocks()
    }
    expect(new Set(seen.map(s => s.height)).size).toBe(1)
    // 10 px for each hour on every screen a ten-day forecast does not fit
    for (const { window } of seen)
      expect(window).toBeCloseTo(10, 5)
  })

  it('opens in the first hours and scrolls sideways under the chart, which stays in place', async () => {
    await showChart()
    const dataZoom = lastOption().dataZoom[0]
    expect(dataZoom.startValue).toBe(t0)
    // 722 px of plot at 10 px for an hour
    expect((dataZoom.endValue - dataZoom.startValue) / HOUR_MS).toBeCloseTo(72.2, 5)
    const track = document.body.querySelector<HTMLElement>('.mg-track')!
    // the forecast's 240 hours at that spacing, and the gutters
    expect(Number.parseInt(track.style.width)).toBe(240 * 10 + 68 + 10)
    expect(stage().style.width).toBe('800px')
  })

  it('links the zoom of every panel and the header: one dataZoom for every x axis', async () => {
    await showChart()
    const option = lastOption()
    expect(option.xAxis).toHaveLength(6)
    expect(option.dataZoom).toHaveLength(1)
    expect(option.dataZoom[0].xAxisIndex).toEqual([0, 1, 2, 3, 4, 5])
  })

  it('draws no animation for a visitor who asked for none, and says its colour scheme', async () => {
    vi.spyOn(window, 'matchMedia').mockImplementation(query => ({ matches: query.includes('reduce'), media: query, addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {}, dispatchEvent: () => false, onchange: null }) as MediaQueryList)
    await showChart()
    expect(lastOption().animation).toBe(false)
    expect(document.body.querySelector('.mg-canvas')!.getAttribute('data-chart-scheme')).toBeTruthy()
  })

  it('draws again, and keeps the window, where the colours change', async () => {
    await showChart()
    const before = lastOption().dataZoom[0]
    await wrapper!.setProps({ panels: { ...ALL_PANELS, pressure: false } })
    await vi.waitFor(() => expect(echarts.chart.setOption).toHaveBeenCalledTimes(2))
    expect(lastOption().xAxis).toHaveLength(5)
    expect(lastOption().dataZoom[0].startValue).toBe(before.startValue)
  })

  it('draws nothing, and disposes the chart, where there are no values', async () => {
    await showChart()
    await wrapper!.setProps({ series: new Map() })
    await vi.waitFor(() => expect(echarts.chart.dispose).toHaveBeenCalled())
  })
})

describe('the keyboard', { timeout: 15_000 }, () => {
  it('steps the crosshair by an hour with the arrow keys and reads the hour out', async () => {
    await showChart()
    expect(readout()).toBeNull()
    key('ArrowRight')
    await flushPromises()
    // the first key lands on the first hour in the window
    expect(readout()).not.toBeNull()
    expect(readout()!.textContent).toContain('Thu 01/10 02:00')
    expect(announce()).toContain('Thu 01/10 02:00')
    key('ArrowRight')
    await flushPromises()
    expect(announce()).toContain('Thu 01/10 03:00')
    key('ArrowLeft')
    await flushPromises()
    expect(announce()).toContain('Thu 01/10 02:00')
  })

  it('names every value of the hour, with its unit, in the readout and in what is announced', async () => {
    await showChart()
    key('ArrowRight')
    await flushPromises()
    const text = readout()!.textContent!
    for (const word of ['Mean Temp', 'Dew Point', 'Wind', 'Wind gust', 'Direction', 'Pressure', 'Total Cloud Cover'])
      expect(text, word).toContain(word)
    expect(text).toContain('°C')
    expect(text).toContain('hPa')
    expect(announce()).toContain('Pressure:')
  })

  it('steps six hours with Shift, a day with Page Down and to the ends with Home and End', async () => {
    await showChart()
    key('ArrowRight')
    await flushPromises()
    key('ArrowRight', { shiftKey: true })
    await flushPromises()
    expect(announce()).toContain('Thu 01/10 08:00')
    key('PageDown')
    await flushPromises()
    expect(announce()).toContain('Fri 02/10 08:00')
    key('PageUp')
    await flushPromises()
    expect(announce()).toContain('Thu 01/10 08:00')
    key('End')
    await flushPromises()
    expect(announce()).toContain('Sun 11/10 02:00')
    key('Home')
    await flushPromises()
    expect(announce()).toContain('Thu 01/10 02:00')
  })

  it('scrolls the window along with the crosshair, which never leaves it', async () => {
    await showChart()
    key('End')
    await flushPromises()
    const { start, end } = zoomWindow()
    const last = t0 + 240 * HOUR_MS
    expect(end).toBeGreaterThanOrEqual(last)
    expect(start).toBeGreaterThan(t0)
  })

  it('zooms in and out with + and -, and goes back with 0', async () => {
    await showChart()
    const span = () => (zoomWindow().end - zoomWindow().start) / HOUR_MS
    key('+')
    await flushPromises()
    expect(span()).toBeCloseTo(72.2 / 1.5, 3)
    key('+')
    await flushPromises()
    expect(span()).toBeCloseTo(72.2 / 1.5 / 1.5, 3)
    key('-')
    await flushPromises()
    expect(span()).toBeCloseTo(72.2 / 1.5, 3)
    key('0')
    await flushPromises()
    expect(span()).toBeCloseTo(72.2, 3)
    expect(zoomWindow().start).toBe(t0)
  })

  it('stops zooming in at six hours across the plot', async () => {
    await showChart()
    for (let i = 0; i < 12; i++)
      key('+')
    await flushPromises()
    expect((zoomWindow().end - zoomWindow().start) / HOUR_MS).toBeCloseTo(6, 5)
  })

  it('leaves other keys, and any key with a modifier, alone', async () => {
    await showChart()
    const tab = new KeyboardEvent('keydown', { key: 'Tab', bubbles: true, cancelable: true })
    stage().dispatchEvent(tab)
    expect(tab.defaultPrevented).toBe(false)
    const ctrl = new KeyboardEvent('keydown', { key: 'ArrowRight', ctrlKey: true, bubbles: true, cancelable: true })
    stage().dispatchEvent(ctrl)
    expect(ctrl.defaultPrevented).toBe(false)
    expect(readout()).toBeNull()
  })
})

describe('the readout', { timeout: 15_000 }, () => {
  it('closes with Escape, with the focus where it is, and is not taken from a dialog by it', async () => {
    await showChart()
    stage().focus()
    key('ArrowRight')
    await flushPromises()
    expect(readout()).not.toBeNull()
    const escape = new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true })
    document.body.dispatchEvent(escape)
    await flushPromises()
    expect(readout()).toBeNull()
    // not consumed: whatever else Escape closes still gets it
    expect(escape.defaultPrevented).toBe(false)
    expect(document.activeElement).toBe(stage())
    // a key steps it back
    key('ArrowRight')
    await flushPromises()
    expect(readout()).not.toBeNull()
  })

  it('has a button that closes it, which a touch has no Escape for', async () => {
    await showChart()
    key('ArrowRight')
    await flushPromises()
    document.body.querySelector<HTMLButtonElement>('.mg-close')!.click()
    await flushPromises()
    expect(readout()).toBeNull()
  })

  it('follows the pointer from hour to hour and stays while the pointer is over the chart', async () => {
    await showChart()
    stage().dispatchEvent(pointer('pointermove', { clientX: 68 + 10 * 5, clientY: 300 }))
    await flushPromises()
    expect(readout()!.textContent).toContain('Thu 01/10 07:00')
    stage().dispatchEvent(pointer('pointermove', { clientX: 68 + 10 * 30 + 2, clientY: 300 }))
    await flushPromises()
    expect(readout()!.textContent).toContain('Fri 02/10 08:00')
  })

  it('can be moved onto, and stays and keeps its hour while the pointer is over it', async () => {
    await showChart()
    stage().dispatchEvent(pointer('pointermove', { clientX: 68 + 10 * 5, clientY: 300 }))
    await flushPromises()
    const element = readout()!
    // the pointer moves over the readout, whose own move events reach the chart's handler and are no news
    element.dispatchEvent(pointer('pointermove', { clientX: 400, clientY: 300 }))
    await flushPromises()
    expect(readout()).not.toBeNull()
    expect(readout()!.textContent).toContain('Thu 01/10 07:00')
  })

  it('goes where the pointer leaves the chart, and stays where it was a key that put it there', async () => {
    await showChart()
    stage().dispatchEvent(pointer('pointermove', { clientX: 118, clientY: 300 }))
    await flushPromises()
    stage().dispatchEvent(pointer('pointerleave'))
    await flushPromises()
    expect(readout()).toBeNull()

    key('ArrowRight')
    await flushPromises()
    stage().dispatchEvent(pointer('pointerleave'))
    await flushPromises()
    expect(readout()).not.toBeNull()
  })

  it('is dismissed by Escape under the pointer, and comes back where the pointer moves on', async () => {
    await showChart()
    stage().dispatchEvent(pointer('pointermove', { clientX: 118, clientY: 300 }))
    await flushPromises()
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    await flushPromises()
    expect(readout()).toBeNull()
    stage().dispatchEvent(pointer('pointermove', { clientX: 148, clientY: 300 }))
    await flushPromises()
    expect(readout()).not.toBeNull()
  })

  it('stays after a tap, until it is closed', async () => {
    await showChart()
    const tap = pointer('click', { clientX: 168, clientY: 200, pointerType: 'touch' })
    stage().dispatchEvent(tap)
    await flushPromises()
    expect(readout()!.textContent).toContain('Thu 01/10 12:00')
    stage().dispatchEvent(pointer('pointerleave', { pointerType: 'touch' }))
    await flushPromises()
    expect(readout()).not.toBeNull()
  })

  it('writes the weather of the hour as words, and no symbol for assistive technology', async () => {
    await showChart()
    // hour 44 of the fixture is a thunderstorm
    stage().dispatchEvent(pointer('pointermove', { clientX: 68 + 10 * 44, clientY: 300 }))
    await flushPromises()
    // the window shows 72 hours: hour 44 is in view
    expect(readout()!.textContent).toContain('Thunderstorm')
    expect(readout()!.querySelector('img')!.getAttribute('alt')).toBe('')
    expect(readout()!.querySelector('img')!.getAttribute('src')).toContain('/yr-symbols/lightmode/22.svg')
  })

  it('sits level with the pointer at the right of the crosshair, and at its left where the right has no room', async () => {
    await showChart()
    stage().dispatchEvent(pointer('pointermove', { clientX: 118, clientY: 300 }))
    await flushPromises()
    const right = readout()!.style
    expect(Number.parseInt(right.left)).toBe(118 + 2)
    expect(Number.parseInt(right.top)).toBe(300 - 24)
    stage().dispatchEvent(pointer('pointermove', { clientX: 760, clientY: 300 }))
    await flushPromises()
    expect(Number.parseInt(readout()!.style.left)).toBeLessThan(760)
  })
})

describe('the window', { timeout: 15_000 }, () => {
  it('follows the strip that is scrolled, and the strip follows the window', async () => {
    await showChart()
    const scroller = document.body.querySelector<HTMLElement>('.mg-scroller')!
    // 100 px at 10 px for an hour: ten hours on
    scroller.scrollLeft = 100
    scroller.dispatchEvent(new Event('scroll'))
    await flushPromises()
    expect(zoomWindow().start).toBe(t0 + 10 * HOUR_MS)
    // the window moves by the keys: the strip goes along
    key('End')
    await flushPromises()
    await vi.waitFor(() => expect(scroller.scrollLeft).toBeGreaterThan(1500))
  })

  it('zooms to the box a mouse drags', async () => {
    await showChart()
    stage().dispatchEvent(pointer('pointerdown', { clientX: 68 + 100, clientY: 200 }))
    stage().dispatchEvent(pointer('pointermove', { clientX: 68 + 200, clientY: 200 }))
    await flushPromises()
    expect(document.body.querySelector('.mg-selection')).not.toBeNull()
    stage().dispatchEvent(pointer('pointerup', { clientX: 68 + 200, clientY: 200 }))
    await flushPromises()
    const { start, end } = zoomWindow()
    expect(start).toBeCloseTo(t0 + 10 * HOUR_MS, -3)
    expect(end).toBeCloseTo(t0 + 20 * HOUR_MS, -3)
    // the click that ends a drag is no tap
    stage().dispatchEvent(pointer('click', { clientX: 68 + 200, clientY: 200 }))
    await flushPromises()
    expect(readout()).toBeNull()
  })

  it('takes a window the library moves (a pinch) and holds it inside the forecast', async () => {
    await showChart()
    const handler = echarts.chart.on.mock.calls.find(([name]) => name === 'datazoom')![1] as (event: unknown) => void
    // the percent of the forecast's span, as the library reports a pinch
    handler({ batch: [{ start: 10, end: 20 }] })
    await flushPromises()
    const { start, end } = zoomWindow()
    expect(start).toBeCloseTo(t0 + 0.1 * 240 * HOUR_MS, -3)
    expect(end).toBeCloseTo(t0 + 0.2 * 240 * HOUR_MS, -3)
  })

  it('goes back to the first hours at the fixed spacing with the reset', async () => {
    const mounted = await showChart()
    key('+')
    key('End')
    await flushPromises()
    ;(mounted.vm as any).resetZoom()
    await flushPromises()
    expect(zoomWindow().start).toBe(t0)
    expect((zoomWindow().end - zoomWindow().start) / HOUR_MS).toBeCloseTo(72.2, 3)
  })

  it('starts over where the horizon changes', async () => {
    await showChart()
    key('End')
    await flushPromises()
    await wrapper!.setProps({ horizonHours: 24 })
    await vi.waitFor(() => expect(echarts.chart.setOption).toHaveBeenCalledTimes(2))
    const dataZoom = lastOption().dataZoom[0]
    expect(dataZoom.startValue).toBe(t0)
    // the whole day fits, and fills the plot up to 22 px for an hour
    expect((dataZoom.endValue - dataZoom.startValue) / HOUR_MS).toBeCloseTo(24, 5)
  })
})

describe('the chart that could not be drawn', { timeout: 15_000 }, () => {
  const retry = () => [...document.body.querySelectorAll('button')].find(button => button.textContent?.trim() === 'Retry')
  const note = () => retry()?.parentElement?.querySelector('[role="alert"]')?.textContent?.trim()

  it('says so where drawing fails, and draws the chart on Retry', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    let failing = true
    echarts.chart.setOption.mockImplementation(() => {
      if (failing)
        throw new Error('drawing failed')
    })
    wrapper = await mountSuspended(MeteogramChart, { props: { series: buildSeries(forecastValues() as any), panels: ALL_PANELS, horizonHours: null, zone: 'UTC', units, label: 'x' }, attachTo: document.body })
    await vi.waitFor(() => expect(retry()).toBeDefined())
    expect(note()).toBe('The chart could not be drawn')
    // a failure of drawing is no failure to load the code: no reload is offered
    expect([...document.body.querySelectorAll('button')].some(button => button.textContent?.trim() === 'Reload page')).toBe(false)
    failing = false
    retry()!.click()
    await vi.waitFor(() => expect(retry()).toBeUndefined())
  })

  it('says so where the chart\'s code could not be loaded, and offers the reload that a replaced chunk needs', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    const loader = await import('~/utils/echarts-loader')
    vi.spyOn(loader, 'loadEcharts').mockImplementation(() => {
      throw new Error('chunk failed to load')
    })
    wrapper = await mountSuspended(MeteogramChart, { props: { series: buildSeries(forecastValues() as any), panels: ALL_PANELS, horizonHours: null, zone: 'UTC', units, label: 'x' }, attachTo: document.body })
    await vi.waitFor(() => expect(retry()).toBeDefined())
    expect(note()).toBe('The chart could not be drawn. Its code could not be loaded. If trying again does not help, reload the page.')
    const reload = [...document.body.querySelectorAll('button')].find(button => button.textContent?.trim() === 'Reload page')
    expect(reload).toBeDefined()
    reload!.click()
    expect(reloadNuxtApp).toHaveBeenCalledWith({ force: true })
  })
})
