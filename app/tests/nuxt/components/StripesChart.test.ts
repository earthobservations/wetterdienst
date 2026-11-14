import { mockNuxtImport, mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import StripesChart from '~/components/StripesChart.vue'

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

// 1950 to 2024 without 1962 to 1964; the value of a year is its distance from 1950 in tenths of a degree
const VALUES = Array.from({ length: 75 }, (_, i) => 1950 + i)
  .filter(year => year < 1962 || year > 1964)
  .map(year => ({ timestamp: `${year}-01-01T00:00:00+00:00`, value: (year - 1950) / 10 }))
const DISPLAY = { showTitle: true, showYears: true, showSource: true, showDataAvailability: true, showTimeseries: false, showTrendline: false }
const TITLE = 'Climate stripes (Temperature) for Donaueschingen, Germany (00011)'

type Mounted = Awaited<ReturnType<typeof mountSuspended>>
let wrapper: Mounted | undefined

async function showChart(props: Record<string, unknown> = {}) {
  wrapper = await mountSuspended(StripesChart, {
    props: { values: VALUES, kind: 'temperature', unit: '°C', title: TITLE, display: DISPLAY, label: TITLE, cameraFile: 'climate_stripes_temperature_00011', ...props },
    attachTo: document.body,
  })
  await vi.waitFor(() => expect(echarts.chart.setOption).toHaveBeenCalled())
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
function pointer(type: string, init: { clientX?: number, pointerType?: string, button?: number } = {}) {
  const event = new MouseEvent(type, { bubbles: true, cancelable: true, clientX: init.clientX ?? 0, clientY: 0, button: init.button ?? 0 })
  Object.defineProperty(event, 'pointerType', { value: init.pointerType ?? 'mouse' })
  Object.defineProperty(event, 'pointerId', { value: 1 })
  return event
}
function movePointerTo(x: number) {
  stage().dispatchEvent(pointer('pointermove', { clientX: x }))
}
function key(name: string, init: KeyboardEventInit = {}) {
  stage().dispatchEvent(new KeyboardEvent('keydown', { key: name, bubbles: true, cancelable: true, ...init }))
}
const rows = () => [...readout()!.querySelectorAll('dt')].map((dt, i) => [dt.textContent!.trim(), readout()!.querySelectorAll('dd')[i]!.textContent!.trim()])
const buttonNamed = (name: string) => document.body.querySelector<HTMLButtonElement>(`.sc-toolbar button[aria-label="${name}"]`)!

beforeEach(() => {
  echarts.chart.on.mockClear()
  echarts.chart.setOption.mockClear()
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
  it('draws the stripes in an SVG chart as tall as the page has always had them, and listens for the zoom of the library', async () => {
    await showChart()
    expect(echarts.init).toHaveBeenCalledTimes(1)
    expect(echarts.init.mock.calls[0]![2]).toEqual({ renderer: 'svg', width: 800, height: 600 })
    expect(echarts.chart.on).toHaveBeenCalledWith('datazoom', expect.any(Function))
    expect(lastOption().series.map((s: any) => s.id)).toEqual(['stripes', 'availability', 'labels'])
    expect(lastOption().animation).toBe(false)
  })

  it('is shorter without a title, and draws again for what the page switches', async () => {
    const shown = await showChart()
    const before = drawn()
    await shown.setProps({ display: { ...DISPLAY, showTitle: false, showTimeseries: true } })
    await vi.waitFor(() => expect(drawn()).toBe(before + 1))
    expect(echarts.chart.resize).toHaveBeenLastCalledWith({ width: 800, height: 550 })
    expect(lastOption().series.map((s: any) => s.id)).toEqual(['stripes', 'availability', 'timeseries', 'labels'])
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
      props: { values: VALUES, kind: 'temperature', unit: '°C', title: TITLE, display: DISPLAY, cameraFile: 'f' },
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

  it('draws nothing where there is no year with a value', async () => {
    await mountSuspended(StripesChart, {
      props: { values: [{ timestamp: '2000-01-01T00:00:00+00:00', value: null }], kind: 'temperature', unit: '°C', title: TITLE, display: DISPLAY, cameraFile: 'f' },
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
    expect(rows()).toEqual([['Value', '4.20 °C'], ['Class', 'Middle']])
    expect(readout()!.getAttribute('role')).toBe('group')
    expect(readout()!.getAttribute('aria-label')).toBe('Climate stripe for 1992')
    stage().dispatchEvent(pointer('pointerleave'))
    await nextTick()
    expect(readout()).toBeNull()
  })

  it('names the trend too where the page draws it', async () => {
    await showChart({ display: { ...DISPLAY, showTimeseries: true, showTrendline: true } })
    movePointerTo(xOfYear(2000))
    await nextTick()
    expect(rows().map(([name]) => name)).toEqual(['Value', 'Trend', 'Class'])
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

  it('jump ten years with Page Up and Page Down and to the ends with Home and End, and say the trend where it is drawn', async () => {
    await showChart({ display: { ...DISPLAY, showTimeseries: true, showTrendline: true } })
    key('End')
    await nextTick()
    expect(announce()).toMatch(/^2024: Value: 7\.40 °C; Trend: .* °C$/)
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
    expect(buttonNamed('Zoom out').disabled).toBe(true)
    expect(buttonNamed('Reset zoom').disabled).toBe(true)
    expect(buttonNamed('Earlier years').disabled).toBe(true)
    expect(buttonNamed('Later years').disabled).toBe(true)
    buttonNamed('Zoom in').click()
    await nextTick()
    expect(buttonNamed('Zoom out').disabled).toBe(false)
    expect(buttonNamed('Later years').disabled).toBe(false)
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

  it('keeps the zoom where the colours or the language change, and starts over for other years', async () => {
    const shown = await showChart()
    buttonNamed('Zoom in').click()
    await nextTick()
    const zoomed = lastZoom()
    await shown.setProps({ unit: '°F' })
    await nextTick()
    expect(buttonNamed('Reset zoom').disabled).toBe(false)
    expect(lastZoom()).toMatchObject({ start: zoomed.start, end: zoomed.end })
    await shown.setProps({ values: VALUES.filter(item => !item.timestamp.startsWith('1950')) })
    await nextTick()
    expect(buttonNamed('Reset zoom').disabled).toBe(true)
  })
})

describe('the image', () => {
  it('is saved as the camera does: a PNG of 1400 by 700 px at twice the size, in the light theme, named for the station', async () => {
    await showChart()
    buttonNamed('Download plot as a PNG').click()
    await vi.waitFor(() => expect(image.downloadBlob).toHaveBeenCalled())
    const [svg, options] = image.svgToBlob.mock.calls[0] as unknown as [string, any]
    expect(options).toMatchObject({ format: 'png', width: 1400, height: 700, scale: 2 })
    expect(options.background).toMatch(/^#|^rgb/)
    expect(svg).toContain('width="1400" height="700"')
    expect(svg).toContain(TITLE)
    expect(image.downloadBlob.mock.calls[0]![1]).toBe('climate_stripes_temperature_00011.png')
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
    expect(svg).not.toContain('rgb(250, 250, 250)')
  })

  it('is 600 px high where the title is off', async () => {
    await showChart({ display: { ...DISPLAY, showTitle: false } })
    buttonNamed('Download plot as a PNG').click()
    await vi.waitFor(() => expect(image.svgToBlob).toHaveBeenCalled())
    expect((image.svgToBlob.mock.calls[0] as unknown as [string, any])[1]).toMatchObject({ width: 1400, height: 600, scale: 2 })
  })

  it('is saved for the menu at the size asked for, with the title broken for the width of the image, and in the range the stripes are zoomed to', async () => {
    const shown = await showChart()
    buttonNamed('Zoom in').click()
    await nextTick()
    buttonNamed('Later years').click()
    await nextTick()
    await (shown.vm as any).save({ format: 'jpeg', filename: 'name', width: 320, height: 600, scale: 3 })
    const [svg, options] = image.svgToBlob.mock.calls[0] as unknown as [string, any]
    expect(options).toMatchObject({ format: 'jpeg', width: 320, height: 600, scale: 3 })
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
