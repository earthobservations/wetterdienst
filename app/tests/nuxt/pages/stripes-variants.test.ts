import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import { useRouter } from '#imports'
import StripesPage from '~/pages/stripes.vue'
import { stripesAnswer } from '../../helpers/stripes-answer'

// The stripes page draws the years as stripes, bars or bars with a scale (GH-4156): the switch above the chart, the variant in
// the link, and what the chart is given for each. The chart's own drawing is held by tests/unit/stripes-bars.test.ts.

// Real Leaflet draws nothing in happy-dom (the page's station map)
vi.mock('@vue-leaflet/vue-leaflet', async () => {
  const { defineComponent, h } = await import('vue')
  return {
    LMap: defineComponent({
      setup: (_, { slots, expose }) => {
        expose({ leafletObject: { fitBounds: vi.fn() } })
        return () => h('div', slots.default?.())
      },
    }),
    LTileLayer: defineComponent({ setup: () => () => null }),
  }
})

// ECharts draws nothing in the test's document: the chart on the page is a recorder, held to the option it is given. The
// option is then drawn by the real library, for the colours and the texts it holds.
const echarts = vi.hoisted(() => {
  const chart = { on: vi.fn(), resize: vi.fn(), setOption: vi.fn(), getDom: vi.fn(), dispose: vi.fn() }
  const state = { realInit: null as null | ((...args: any[]) => any) }
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
  return { loadEcharts: () => ({ init: echarts.init }) }
})
vi.mock('~/utils/chart-image', () => ({ svgToBlob: vi.fn(async () => new Blob(['image'])), downloadBlob: vi.fn() }))

const station = { station_id: '1048', name: 'Berlin-Tempelhof', region: 'Berlin', latitude: 52.47, longitude: 13.4, start_timestamp: '1950-01-01', end_timestamp: '2020-01-01' }
// twenty years, so that the bars have heights to tell apart; too few for the period of the method, so the whole record is the reference
const YEARS = Array.from({ length: 20 }, (_, i) => ({ year: 2001 + i, value: 8 + (i % 7) / 2 }))

const drawnOptions = () => echarts.chart.setOption.mock.calls.filter(([, flags]) => flags?.notMerge).map(([option]) => option as any)
const draws = () => drawnOptions().length
const drawnOption = () => drawnOptions().at(-1)!
const seriesIds = () => drawnOption().series.map((s: any) => s.id)
function drawn(option: unknown) {
  const chart = echarts.state.realInit!(null, null, { renderer: 'svg', ssr: true, width: 800, height: 600 })
  chart.setOption(option)
  const svg = chart.renderToSVGString() as string
  chart.dispose()
  return {
    texts: [...svg.matchAll(/<text[^>]*>([^<]*)<\/text>/g)].map(match => match[1]!),
    fills: [...svg.matchAll(/<path d="M[^"]*" fill="(#(?!FFD700)[0-9a-fA-F]{6})"/g)].map(match => match[1]!.toLowerCase()),
  }
}

// the station picker has a radio group of its own
const switcher = () => document.body.querySelector<HTMLElement>('[role="radiogroup"][aria-label="Chart style"]')!
const radios = () => [...switcher().querySelectorAll<HTMLButtonElement>('[role="radio"]')]
const radio = (name: string) => radios().find(button => button.textContent?.trim() === name)!
const checked = () => radios().filter(button => button.getAttribute('aria-checked') === 'true').map(button => button.textContent?.trim())
const queryVariant = () => useRouter().currentRoute.value.query.variant

let wrapper: Awaited<ReturnType<typeof mountSuspended>> | undefined
afterEach(() => {
  wrapper?.unmount()
  wrapper = undefined
  document.body.innerHTML = ''
  echarts.chart.setOption.mockReset()
})

async function show(route: string) {
  registerEndpoint('/api/stripes/stations', () => ({ stations: [station] }))
  registerEndpoint('/api/stripes/values', () => ({ series: { station, unit: 'degree_celsius' }, ...stripesAnswer(YEARS.map(({ year, value }) => ({ year, value }))) }))
  wrapper = await mountSuspended(StripesPage, { attachTo: document.body, route })
  const vm = wrapper.vm as any
  await vi.waitFor(() => expect(vm.stations).toHaveLength(1))
  vm.selectedStation = station
  await nextTick()
  echarts.chart.setOption.mockClear()
  await vm.fetchAndPlotStripes()
  await vi.waitFor(() => expect(draws()).toBeGreaterThan(0))
  return vm
}

describe('stripes Page variants (GH-4156)', () => {
  it('draws the stripes, and says so in the switch, where the link names no variant', async () => {
    await show('/stripes?kind=temperature&show_years=true')
    expect(switcher().getAttribute('aria-label')).toBe('Chart style')
    expect(radios().map(button => button.textContent?.trim())).toEqual(['Stripes', 'Bars', 'Bars with scale'])
    expect(checked()).toEqual(['Stripes'])
    expect(seriesIds()).toContain('stripes')
  })

  it.each([
    ['bars', 'Bars', ['bars', 'zeroline']],
    ['bars_scale', 'Bars with scale', ['bars', 'grid', 'zeroline']],
  ])('draws what the link names, %s, in the chart, and keeps it in the link', async (name, label, ids) => {
    await show(`/stripes?kind=temperature&variant=${name}`)
    expect(checked()).toEqual([label])
    expect(seriesIds()).toEqual(expect.arrayContaining(ids))
    expect(seriesIds()).not.toContain('stripes')
    await vi.waitFor(() => expect(queryVariant()).toBe(name))
  })

  it('takes the stripes for a variant of the link that is none, and writes the one it took into the link', async () => {
    await show('/stripes?kind=temperature&variant=pie')
    expect(checked()).toEqual(['Stripes'])
    await vi.waitFor(() => expect(queryVariant()).toBe('stripes'))
  })

  it('draws again as the switch changes, from the same values, and puts each choice in the link', async () => {
    const vm = await show('/stripes?kind=temperature')
    const before = draws()
    radio('Bars').click()
    await vi.waitFor(() => expect(draws()).toBe(before + 1))
    expect(seriesIds()).toContain('bars')
    expect(checked()).toEqual(['Bars'])
    await vi.waitFor(() => expect(queryVariant()).toBe('bars'))
    radio('Bars with scale').click()
    await vi.waitFor(() => expect(draws()).toBe(before + 2))
    expect(seriesIds()).toContain('grid')
    await vi.waitFor(() => expect(queryVariant()).toBe('bars_scale'))
    radio('Stripes').click()
    await vi.waitFor(() => expect(draws()).toBe(before + 3))
    expect(seriesIds()).toContain('stripes')
    await vi.waitFor(() => expect(queryVariant()).toBe('stripes'))
    expect(vm.isLoading).toBe(false)
  })

  it('keeps the colours of the stripes in the bars: the same class, the same colour, for each year', async () => {
    await show('/stripes?kind=temperature')
    const stripes = drawn(drawnOption()).fills
    expect(stripes).toHaveLength(YEARS.length)
    radio('Bars').click()
    await vi.waitFor(() => expect(seriesIds()).toContain('bars'))
    expect(drawn(drawnOption()).fills).toEqual(stripes)
  })

  it('keeps the title, the source and the years of the page in the bars', async () => {
    await show('/stripes?kind=temperature&variant=bars&show_title=true&show_source=true&show_years=true')
    const { texts } = drawn(drawnOption())
    expect(texts).toContain('Climate stripes (Temperature) for Berlin-Tempelhof, Germany (1048)')
    expect(texts).toContain('Source: Deutscher Wetterdienst')
    expect(texts.filter(text => /^\d{4}$/.test(text))).toEqual(['2001', '2020'])
  })

  it('says under the title what the bars with a scale are relative to, with the unit', async () => {
    await show('/stripes?kind=temperature&variant=bars_scale&show_title=true')
    // the years of the test are few: the whole record stands in for 1971 to 2000
    expect(drawn(drawnOption()).texts).toContain('Relative to the mean of the whole record (2001–2020) [°C]')
  })

  it('keeps the variant where another kind of stripes is asked for', async () => {
    const vm = await show('/stripes?kind=temperature&variant=bars')
    vm.kind = 'precipitation'
    await nextTick()
    // the stripes of the other kind are fetched anew, and the choice of how to draw them is still the reader's
    await vi.waitFor(() => expect(useRouter().currentRoute.value.query.kind).toBe('precipitation'))
    expect(queryVariant()).toBe('bars')
  })
})
