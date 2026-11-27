import { mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import KostraChart from '~/components/KostraChart.vue'
import { KOSTRA_DURATIONS, parseKostra } from '~/utils/kostra'
import { pixelOfDuration } from '~/utils/kostra-option'
import { depthOf, kostraAnswer } from '../../helpers/kostra-answer'

// The curves of the Heavy-rainfall tool (GH-4500): ECharts draws nothing in the test's document, so the chart on the page is a recorder, held
// to the option it is given. The legend and the readout are the component's own elements, which the pointer and the keys work.

const echarts = vi.hoisted(() => {
  const chart = { on: vi.fn(), resize: vi.fn(), setOption: vi.fn(), getDom: vi.fn(), dispose: vi.fn() }
  const state = { loadFails: false }
  const init = vi.fn((element: HTMLElement) => {
    chart.getDom.mockReturnValue(element)
    return chart
  })
  return { chart, init, state }
})
vi.mock('~/utils/echarts-loader', () => ({
  loadEcharts: () => {
    if (echarts.state.loadFails)
      throw new Error('chunk gone')
    return { init: echarts.init }
  },
}))

const table = parseKostra(kostraAnswer())!
type Mounted = Awaited<ReturnType<typeof mountSuspended>>
let wrapper: Mounted | undefined

async function showChart(props: Record<string, unknown> = {}) {
  wrapper = await mountSuspended(KostraChart, { props: { table, quantity: 'depth', ...props }, attachTo: document.body })
  await vi.waitFor(() => expect(echarts.chart.setOption).toHaveBeenCalled(), { timeout: 5000 })
  await flushPromises()
  return wrapper
}

const stage = () => document.body.querySelector<HTMLElement>('[data-testid="kostra-stage"]')!
const readout = () => document.body.querySelector<HTMLElement>('[data-testid="kostra-readout"]')
const announce = () => document.body.querySelector('[data-testid="kostra-chart-announcement"]')!.textContent?.trim()
const lastOption = () => echarts.chart.setOption.mock.calls.at(-1)![0] as any
const rows = () => [...readout()!.querySelectorAll('.kostra-readout-row')].map(row => [row.querySelector('dt')!.textContent!.replace(/\s+/g, ' ').trim(), row.querySelector('dd')!.textContent!.trim()])

function pointer(type: string, init: { clientX?: number, pointerType?: string } = {}) {
  const event = new MouseEvent(type, { bubbles: true, cancelable: true, clientX: init.clientX ?? 0 })
  Object.defineProperty(event, 'pointerType', { value: init.pointerType ?? 'mouse' })
  return event
}
function key(name: string, init: KeyboardEventInit = {}) {
  stage().dispatchEvent(new KeyboardEvent('keydown', { key: name, bubbles: true, cancelable: true, ...init }))
}
const settle = () => vi.waitFor(() => expect(echarts.chart.setOption.mock.calls.length).toBeGreaterThan(0))

beforeEach(() => {
  wrapper?.unmount()
  wrapper = undefined
  echarts.chart.on.mockClear()
  echarts.chart.setOption.mockReset()
  echarts.chart.dispose.mockClear()
  echarts.chart.resize.mockClear()
  echarts.init.mockClear()
  echarts.state.loadFails = false
  document.body.innerHTML = ''
})

describe('the chart', () => {
  it('draws nine curves as SVG, one for each return period, from the table', async () => {
    await showChart()
    expect(echarts.init).toHaveBeenCalledTimes(1)
    expect(echarts.init.mock.calls[0]![2]).toMatchObject({ renderer: 'svg', width: 800 })
    const option = lastOption()
    expect(option.series.map((item: any) => item.id)).toEqual(['curve-1', 'curve-2', 'curve-3', 'curve-5', 'curve-10', 'curve-20', 'curve-30', 'curve-50', 'curve-100'])
    expect(option.series[8].data[0]).toEqual([Math.log10(5), depthOf(5, 100)])
    // drawn afresh, not merged into what was there
    expect(echarts.chart.setOption.mock.calls.at(-1)![1]).toEqual({ notMerge: true })
  })

  it('draws the intensity when the quantity changes, from the same table', async () => {
    const shown = await showChart()
    const depth = lastOption().series[0].data[0][1]
    await shown.setProps({ quantity: 'intensity' })
    await vi.waitFor(() => expect(lastOption().series[0].data[0][1]).not.toBe(depth))
    expect(lastOption().series[0].data[0][1]).toBe(table.rows[0]![0]!.intensity)
  })

  it('has a legend of the nine return periods, each with its number and the colour of its curve, and a title that says what the numbers are', async () => {
    await showChart()
    const legend = document.body.querySelector('[data-testid="kostra-legend"]')!
    expect(legend.querySelector('.kostra-legend-title')!.textContent).toBe('Return period (years)')
    const items = [...legend.querySelectorAll<HTMLElement>('.kostra-legend-item')]
    expect(items.map(item => item.textContent!.trim())).toEqual(['1', '2', '3', '5', '10', '20', '30', '50', '100'])
    // the colour is a line of the curve's own, and the number is the cue that does not depend on it
    expect(items[0]!.querySelector<HTMLElement>('.kostra-swatch')!.style.background).not.toBe(items[8]!.querySelector<HTMLElement>('.kostra-swatch')!.style.background)
  })

  it('is one stop of the keyboard, named for what it shows and described by the note the page gives', async () => {
    await showChart({ describedBy: 'note-id' })
    expect(stage().getAttribute('tabindex')).toBe('0')
    expect(stage().getAttribute('role')).toBe('group')
    expect(stage().getAttribute('aria-label')).toContain('Chart: Depth in mm against the duration of the rain')
    expect(stage().getAttribute('aria-describedby')).toBe('note-id')
  })
})

describe('the readout', () => {
  it('is none until a duration is read', async () => {
    await showChart()
    expect(readout()).toBeNull()
  })

  it('is at the duration the pointer is over: its label and the nine values', async () => {
    await showChart()
    const hour = KOSTRA_DURATIONS.indexOf(60)
    stage().dispatchEvent(pointer('pointermove', { clientX: pixelOfDuration(60, 800) }))
    await vi.waitFor(() => expect(readout()).not.toBeNull())
    expect(readout()!.querySelector('[data-testid="kostra-readout-title"]')!.textContent).toBe('1 h')
    expect(rows()).toHaveLength(9)
    expect(rows()[0]).toEqual(['1 year', depthOf(60, 1).toFixed(1)])
    expect(rows()[8]).toEqual(['100 years', depthOf(60, 100).toFixed(1)])
    // and the chart is given the crosshair at the same duration
    await vi.waitFor(() => expect(lastOption().series.map((item: any) => item.id)).toContain('cursor-line'))
    expect(lastOption().series.find((item: any) => item.id === 'cursor-line').data[0][0]).toBe(Math.log10(KOSTRA_DURATIONS[hour]!))
  })

  it('goes when the pointer leaves, but not a touch: a tap stays until it is closed', async () => {
    await showChart()
    stage().dispatchEvent(pointer('pointermove', { clientX: pixelOfDuration(60, 800) }))
    await vi.waitFor(() => expect(readout()).not.toBeNull())
    stage().dispatchEvent(pointer('pointerleave'))
    await vi.waitFor(() => expect(readout()).toBeNull())
    stage().dispatchEvent(pointer('click', { clientX: pixelOfDuration(1440, 800), pointerType: 'touch' }))
    await vi.waitFor(() => expect(readout()).not.toBeNull())
    stage().dispatchEvent(pointer('pointerleave', { pointerType: 'touch' }))
    await flushPromises()
    expect(readout()!.querySelector('[data-testid="kostra-readout-title"]')!.textContent).toBe('1 d')
  })

  it('has a button that closes it', async () => {
    await showChart()
    stage().dispatchEvent(pointer('click', { clientX: pixelOfDuration(60, 800) }))
    await vi.waitFor(() => expect(readout()).not.toBeNull())
    readout()!.querySelector<HTMLButtonElement>('[data-testid="kostra-readout-close"]')!.click()
    await vi.waitFor(() => expect(readout()).toBeNull())
    expect(document.activeElement).toBe(stage())
  })

  it('says no value for a curve DWD gives none for there', async () => {
    await showChart({ table: parseKostra(kostraAnswer({ missing: [[60, 100]] }))! })
    stage().dispatchEvent(pointer('click', { clientX: pixelOfDuration(60, 800) }))
    await vi.waitFor(() => expect(readout()).not.toBeNull())
    expect(rows()[8]).toEqual(['100 years', 'no value'])
  })
})

describe('the keys', () => {
  it('step through the durations: the right arrow from the first, the left from the last, Home and End, and say each in words', async () => {
    await showChart()
    stage().focus()
    key('ArrowRight')
    await vi.waitFor(() => expect(readout()!.querySelector('[data-testid="kostra-readout-title"]')!.textContent).toBe('5 min'))
    key('ArrowRight')
    await vi.waitFor(() => expect(readout()!.querySelector('[data-testid="kostra-readout-title"]')!.textContent).toBe('10 min'))
    expect(announce()).toMatch(/^10 min: 1 year: \d+\.\d; 2 years: /)
    expect(announce()).toContain(`100 years: ${depthOf(10, 100).toFixed(1)}`)
    key('End')
    await vi.waitFor(() => expect(readout()!.querySelector('[data-testid="kostra-readout-title"]')!.textContent).toBe('7 d'))
    key('ArrowRight')
    await flushPromises()
    expect(readout()!.querySelector('[data-testid="kostra-readout-title"]')!.textContent).toBe('7 d')
    key('Home')
    await vi.waitFor(() => expect(readout()!.querySelector('[data-testid="kostra-readout-title"]')!.textContent).toBe('5 min'))
    key('ArrowLeft')
    await flushPromises()
    expect(readout()!.querySelector('[data-testid="kostra-readout-title"]')!.textContent).toBe('5 min')
  })

  it('start from the last duration with the left arrow, and take three at a time with Shift', async () => {
    await showChart()
    stage().focus()
    key('ArrowLeft')
    await vi.waitFor(() => expect(readout()!.querySelector('[data-testid="kostra-readout-title"]')!.textContent).toBe('7 d'))
    key('ArrowLeft', { shiftKey: true })
    await vi.waitFor(() => expect(readout()!.querySelector('[data-testid="kostra-readout-title"]')!.textContent).toBe('4 d'))
  })

  it('close the readout with Escape, and bring it back with the next key', async () => {
    await showChart()
    stage().focus()
    key('Home')
    await vi.waitFor(() => expect(readout()).not.toBeNull())
    key('Escape')
    await vi.waitFor(() => expect(readout()).toBeNull())
    key('ArrowRight')
    await vi.waitFor(() => expect(readout()).not.toBeNull())
  })

  it('leave every other key alone, and the keys of a button inside the chart', async () => {
    await showChart()
    stage().focus()
    const event = new KeyboardEvent('keydown', { key: 'a', bubbles: true, cancelable: true })
    stage().dispatchEvent(event)
    expect(event.defaultPrevented).toBe(false)
    key('Home')
    await vi.waitFor(() => expect(readout()).not.toBeNull())
    const close = readout()!.querySelector<HTMLButtonElement>('[data-testid="kostra-readout-close"]')!
    const inside = new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true, cancelable: true })
    close.dispatchEvent(inside)
    expect(inside.defaultPrevented).toBe(false)
  })

  it('take the readout away when the focus leaves the chart', async () => {
    await showChart()
    stage().focus()
    key('Home')
    await vi.waitFor(() => expect(readout()).not.toBeNull())
    stage().dispatchEvent(new FocusEvent('focusout', { bubbles: true, relatedTarget: document.body }))
    await vi.waitFor(() => expect(readout()).toBeNull())
  })
})

describe('a drawing that fails', () => {
  it('says so with a Retry, and draws when the retry works', async () => {
    echarts.state.loadFails = true
    wrapper = await mountSuspended(KostraChart, { props: { table, quantity: 'depth' }, attachTo: document.body })
    await vi.waitFor(() => expect(document.body.querySelector('[role="alert"]')).not.toBeNull())
    expect(document.body.querySelector('[role="alert"]')!.textContent).toBe('The chart could not be drawn.')
    expect(stage().hasAttribute('inert')).toBe(true)
    echarts.state.loadFails = false
    document.body.querySelector<HTMLButtonElement>('[data-testid="kostra-chart-retry"]')!.click()
    await vi.waitFor(() => expect(echarts.chart.setOption).toHaveBeenCalled())
    await vi.waitFor(() => expect(document.body.querySelector('[role="alert"]')).toBeNull())
    expect(stage().hasAttribute('inert')).toBe(false)
    await settle()
  })
})
