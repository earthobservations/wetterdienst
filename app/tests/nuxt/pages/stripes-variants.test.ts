import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import { useRouter } from '#imports'
import StripesPage from '~/pages/stripes.vue'
import { downloadBlob } from '~/utils/chart-image'
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
    expect(radios().map(button => button.textContent?.trim())).toEqual(['Stripes', 'Bars', 'Bars with scale', 'Table'])
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

// The table is the fourth view of the same switch (GH-4233): a view of its own, with no chart behind it, kept in the link
describe('stripes Page table view (GH-4233)', () => {
  const NAMES = ['Stripes', 'Bars', 'Bars with scale', 'Table']
  const PROVIDER = {
    attribution: 'Source: Deutscher Wetterdienst (DWD), Climate Data Center',
    license: { spdx_id: 'CC-BY-4.0', name: 'Creative Commons Attribution 4.0 International', url: 'https://creativecommons.org/licenses/by/4.0/' },
  }

  async function showWithoutDrawing(route: string, metadata?: unknown, years: Array<{ year: number, value: number }> = YEARS) {
    clearNuxtData()
    registerEndpoint('/api/stripes/stations', () => ({ stations: [station] }))
    registerEndpoint('/api/stripes/values', () => ({ ...(metadata ? { metadata } : {}), series: { station, unit: 'degree_celsius' }, ...stripesAnswer(years.map(({ year, value }) => ({ year, value }))) }))
    wrapper = await mountSuspended(StripesPage, { attachTo: document.body, route })
    const vm = wrapper.vm as any
    await vi.waitFor(() => expect(vm.stations).toHaveLength(1))
    vm.selectedStation = station
    await nextTick()
    echarts.chart.setOption.mockClear()
    await vm.fetchAndPlotStripes()
    await vi.waitFor(() => expect(document.body.querySelector('[role="radiogroup"][aria-label="Chart style"]')).not.toBeNull())
    return vm
  }
  const tableRows = () => [...document.body.querySelectorAll('tbody tr')].map(row => [...row.children].map(cell => cell.textContent?.trim()))
  const lastFile = async () => {
    const [blob, name] = vi.mocked(downloadBlob).mock.calls.at(-1)!
    // the mark is read from the bytes (a `Blob.text()` may or may not drop it), and the text is read without it
    const bytes = new Uint8Array(await blob.arrayBuffer())
    return { text: (await blob.text()).replace(/^\uFEFF/, ''), name, type: blob.type, bytes }
  }

  it('has the table as the fourth choice of the switch, after the three drawings', async () => {
    await show('/stripes?kind=temperature')
    expect(radios().map(button => button.textContent?.trim())).toEqual(NAMES)
    expect(radio('Table').getAttribute('role')).toBe('radio')
  })

  it('opens the table where the link says variant=table, draws no chart, and keeps the variant in the link', async () => {
    await showWithoutDrawing('/stripes?kind=temperature&variant=table')
    expect(checked()).toEqual(['Table'])
    await vi.waitFor(() => expect(document.body.querySelector('table')).not.toBeNull())
    expect(tableRows()).toHaveLength(YEARS.length)
    expect(tableRows()[0]![0]).toBe('2001')
    expect(document.body.querySelector('[role="figure"]')).toBeNull()
    // the chart's code is not even loaded for a table
    expect(draws()).toBe(0)
    expect(echarts.init).not.toHaveBeenCalledWith(expect.any(HTMLElement), expect.anything(), expect.anything())
    await vi.waitFor(() => expect(queryVariant()).toBe('table'))
  })

  it('goes through the four views by the switch, puts each in the link, and draws what it goes back to', async () => {
    await show('/stripes?kind=temperature&variant=bars')
    radio('Table').click()
    await vi.waitFor(() => expect(document.body.querySelector('table')).not.toBeNull())
    await vi.waitFor(() => expect(queryVariant()).toBe('table'))
    expect(document.body.querySelector('[role="figure"]')).toBeNull()
    echarts.chart.setOption.mockClear()
    radio('Bars').click()
    // the bars again, not the stripes: the drawing chosen last is the one the chart goes back to
    await vi.waitFor(() => expect(draws()).toBeGreaterThan(0))
    expect(seriesIds()).toContain('bars')
    expect(seriesIds()).not.toContain('stripes')
    expect(document.body.querySelector('table')).toBeNull()
    expect(document.body.querySelector('[role="figure"]')).not.toBeNull()
    await vi.waitFor(() => expect(queryVariant()).toBe('bars'))
  })

  it('takes the stripes for a variant that is none, and a variant given twice for its first', async () => {
    await show('/stripes?kind=temperature&variant=tables')
    expect(checked()).toEqual(['Stripes'])
    expect(document.body.querySelector('table')).toBeNull()
  })

  // what the download button's menu offers: the button opened, its items read
  async function menuItems() {
    const button = [...document.body.querySelectorAll<HTMLButtonElement>('button')].find(candidate => /^Download (?:table|image)$/.test(candidate.textContent?.trim() ?? ''))!
    button.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, button: 0, ctrlKey: false, pointerType: 'mouse' }))
    button.click()
    await vi.waitFor(() => expect(document.body.querySelector('[role="menuitem"]')).not.toBeNull())
    const items = [...document.body.querySelectorAll('[role="menuitem"]')].map(item => item.textContent?.trim())
    button.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    return items
  }

  it('offers the CSV, and nothing else, as the download of the table, and the images in the other views', async () => {
    await showWithoutDrawing('/stripes?kind=temperature&variant=table')
    await vi.waitFor(() => expect(document.body.querySelector('table')).not.toBeNull())
    expect(await menuItems()).toEqual(['Download as CSV'])
  })

  it('offers the images where the stripes are shown', async () => {
    await show('/stripes?kind=temperature')
    expect(await menuItems()).toEqual(['Download as PNG', 'Download as JPG', 'Download as SVG'])
  })

  it('saves the table as CSV: the columns of the table with the unit in the header, plain numbers, and the reference, credit and licence as comments', async () => {
    const vm = await showWithoutDrawing('/stripes?kind=temperature&variant=table', { provider: PROVIDER })
    await vi.waitFor(() => expect(document.body.querySelector('table')).not.toBeNull())
    vi.mocked(downloadBlob).mockClear()
    vm.downloadTable()
    const { text, name, type, bytes } = await lastFile()
    expect(name).toBe('climate_stripes_temperature_1048_Berlin-Tempelhof.csv')
    // a byte order mark, for Excel to read °C and the class names as UTF-8
    expect(Array.from(bytes.slice(0, 3))).toEqual([0xEF, 0xBB, 0xBF])
    expect(type).toContain('text/csv')
    const lines = text.trimEnd().split('\n')
    expect(lines.slice(0, 4)).toEqual([
      '# Climate stripes (Temperature) for Berlin-Tempelhof, Germany (1048)',
      '# Colours: the mean of the whole record (2001–2020) is the centre of the scale, which spans ±2.6 standard deviations of the whole record (2001–2020) (Ed Hawkins\' method).',
      '# Source: Deutscher Wetterdienst (DWD), Climate Data Center',
      '# Licence: Creative Commons Attribution 4.0 International (https://creativecommons.org/licenses/by/4.0/)',
    ])
    expect(lines[4]).toBe('Year,Value (°C),Anomaly (°C),Class')
    expect(lines).toHaveLength(4 + 1 + YEARS.length)
    // the same rows as the table shows, as numbers a program reads
    const first = lines[5]!.split(',')
    expect(first[0]).toBe('2001')
    expect(first[1]).toMatch(/^\d+\.\d{2}$/)
    expect(first[2]).toMatch(/^-?\d+\.\d{2}$/)
    expect(first[3]).toMatch(/^(Much cooler|Cooler|Middle|Warmer|Much warmer)$/)
    expect(lines.slice(5).map(line => line.split(',')[0])).toEqual(YEARS.map(({ year }) => String(year)))
  })

  it('credits the provider by the line the page has where the answer carries none, and writes no licence it does not have', async () => {
    const vm = await showWithoutDrawing('/stripes?kind=temperature&variant=table')
    vi.mocked(downloadBlob).mockClear()
    vm.downloadTable()
    const { text } = await lastFile()
    expect(text.split('\n').filter(line => line.startsWith('#'))).toEqual([
      '# Climate stripes (Temperature) for Berlin-Tempelhof, Germany (1048)',
      expect.stringMatching(/^# Colours: /),
      '# Source: Deutscher Wetterdienst',
    ])
  })

  it('says the spread is from the whole record, in the line\'s brackets, where only the spread falls back to it (a station from 1976)', async () => {
    const from1976 = Array.from({ length: 49 }, (_, i) => ({ year: 1976 + i, value: 8 + (i % 7) / 2 }))
    await showWithoutDrawing('/stripes?kind=temperature&variant=table', undefined, from1976)
    await vi.waitFor(() => expect(document.body.querySelector('[data-testid="stripes-reference"]')).not.toBeNull())
    expect(document.body.querySelector('[data-testid="stripes-reference"]')!.textContent?.trim()).toBe('Relative to the mean of 1976–2000 (spread from the whole record, 1976–2024)')
    radio('Bars').click()
    await vi.waitFor(() => expect(document.body.querySelector('[data-testid="stripes-reference"]')!.textContent?.trim()).toBe('Bars: the difference from the mean of 1976–2000 (spread from the whole record, 1976–2024)'))
  })
})
