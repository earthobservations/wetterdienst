import type { H3Event } from 'h3'
import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { getQuery } from 'h3'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { UApp } from '#components'
import { useRouter, useSettings, useToast } from '#imports'
import ComparePage from '~/pages/compare.vue'
import { providersAnswer } from '../fixtures/providers'

// The Compare tool (GH-4296): the form, a link that opens the whole comparison, the table with the difference column, the refusal where the two
// sides are not the same kind of number, the credit of both sides and the files. The chart is the Explorer's (`ExplorerChart.vue`), which draws
// nothing in the test's document: here is a recorder of the series it is given.

const charts = vi.hoisted(() => ({ options: [] as any[] }))
vi.mock('echarts/core', async (importOriginal) => {
  const original = await importOriginal<typeof import('echarts/core')>()
  const init = (element: HTMLElement | null, ...rest: unknown[]) => {
    if (element === null)
      return (original.init as any)(null, ...rest)
    return {
      setOption: (option: unknown) => charts.options.push(option),
      dispose: () => {},
      on: () => {},
      resize: () => {},
      getDom: () => element,
    }
  }
  return { ...original, init }
})

const WithApp = defineComponent({ setup: () => () => h(UApp, null, { default: () => h(ComparePage) }) })

const STATIONS = [
  { station_id: '00011', name: 'Donaueschingen', latitude: 47.97, longitude: 8.52, elevation: 680, start_timestamp: '1980-01-01T00:00:00+00:00', end_timestamp: null },
  { station_id: '00044', name: 'Großenkneten', latitude: 52.93, longitude: 8.24, elevation: 44, start_timestamp: '1971-01-01T00:00:00+00:00', end_timestamp: null },
]

function coverage() {
  const parameter = (name: string, unit_type: string, unit: string) => ({ name, name_original: name, unit_type, unit, description: name })
  const parameters = [parameter('precipitation_amount', 'precipitation', 'millimeter'), parameter('temperature_air_mean_2m', 'temperature', 'degree_celsius')]
  return { daily: { description: null, datasets: { climate_summary: { description: null, parameters } } }, monthly: { description: null, datasets: { climate_summary: { description: null, parameters } } } }
}

const info = (unit = '°C', aggregation = 'mean', resolution = 'daily') => ({ resolution, dataset: 'climate_summary', name: 'temperature_air_mean_2m', name_original: 'tmk', description: null, quantity: 'temperature', unit, aggregation, timestamp_position: 'start' })
const row = (station_id: string, date: string, value: number | null) => ({ station_id, resolution: 'daily', dataset: 'climate_summary', parameter: 'temperature_air_mean_2m', timestamp: `${date}T00:00:00+00:00`, value, quality_flags: null })

const endpoints: (() => void)[] = []
const mounted: { unmount: () => void }[] = []
const asked: Record<string, string>[] = []

function backend(values: (query: Record<string, string>) => unknown) {
  endpoints.push(registerEndpoint('/api/coverage', () => coverage()))
  endpoints.push(registerEndpoint('/api/providers', () => providersAnswer()))
  endpoints.push(registerEndpoint('/api/stations', () => ({ stations: STATIONS })))
  endpoints.push(registerEndpoint('/api/values', (event: H3Event) => {
    const query = getQuery(event) as Record<string, string>
    asked.push(query)
    return values(query)
  }))
}

async function open(path: string) {
  const wrapper = await mountSuspended(WithApp, { route: path, attachTo: document.body })
  mounted.push(wrapper)
  return wrapper
}

afterEach(() => {
  mounted.splice(0).forEach(wrapper => wrapper.unmount())
  endpoints.splice(0).forEach(remove => remove())
  asked.length = 0
  charts.options.length = 0
  useSettings().reset()
  useToast().clear()
})

const STATIONS_LINK = '/compare?compare=stations&resolution=daily&parameter=temperature_air_mean_2m&stations=00011,00044&startDate=2026-03-01&endDate=2026-03-04'
const PERIODS_LINK = '/compare?compare=periods&resolution=daily&parameter=temperature_air_mean_2m&stations=00011&periodA=2025-03-01/2025-03-03&periodB=2026-03-01/2026-03-03'

describe('the compare tool', () => {
  it('is a page with its title, its about text and the placeholder of the tools where the result will be', async () => {
    backend(() => ({ values: [] }))
    const wrapper = await open('/compare')
    expect(wrapper.find('h1').text()).toBe('Compare')
    expect(wrapper.find('[data-testid="tool-placeholder"]').attributes('data-tool')).toBe('compare')
    expect(asked, 'nothing is asked until Show is pressed').toEqual([])
    // the form: what is compared, resolution, parameter, the sides and the period, labelled
    expect(wrapper.find('[data-testid="compare-by-stations"]').attributes('aria-pressed')).toBe('true')
    expect(wrapper.find('[data-testid="compare-by-periods"]').attributes('aria-pressed')).toBe('false')
    expect(wrapper.text()).toContain('Station A')
    expect(wrapper.text()).toContain('Station B')
    await vi.waitFor(() => expect(wrapper.find('[data-testid="compare-fetch"]').exists()).toBe(true))
    expect(wrapper.find('[data-testid="compare-fetch"]').attributes('disabled'), 'no station is chosen').toBeDefined()
  })

  it('starts the period with the last complete month, which the address then holds', async () => {
    backend(() => ({ values: [] }))
    await open('/compare')
    await vi.waitFor(() => expect(useRouter().currentRoute.value.query.compare).toBe('stations'))
    const query = useRouter().currentRoute.value.query
    expect(query.resolution).toBe('daily')
    expect(query.startDate).toMatch(/^\d{4}-\d{2}-01$/)
    expect(query.endDate).toMatch(/^\d{4}-\d{2}-\d{2}$/)
  })

  it('opens the comparison a link names, two stations over a period: one request, and a row for every day with B minus A', async () => {
    backend(() => ({
      metadata: { parameters: [info()] },
      values: [
        row('00011', '2026-03-01', 4),
        row('00011', '2026-03-02', 6),
        row('00011', '2026-03-03', null),
        row('00011', '2026-03-04', 8),
        row('00044', '2026-03-01', 5.5),
        row('00044', '2026-03-02', 5),
        row('00044', '2026-03-03', 9),
        row('00044', '2026-03-04', 8),
      ],
    }))
    const wrapper = await open(STATIONS_LINK)
    await vi.waitFor(() => expect(wrapper.find('[data-testid="compare-table"]').exists()).toBe(true), { timeout: 5000 })
    expect(asked).toHaveLength(1)
    expect(asked[0]).toMatchObject({ provider: 'dwd', network: 'observation', parameters: 'daily/climate_summary/temperature_air_mean_2m', stations: '00011,00044', timestamp: '2026-03-01/2026-03-04', shape: 'long', with_metadata: 'true', drop_nulls: 'false' })
    const rows = wrapper.findAll('[data-testid="compare-row"]').map(each => each.findAll('th, td').map(cell => cell.text()))
    expect(rows).toEqual([
      ['1', '2026-03-01', '2026-03-01', '4', '5.5', '+1.5'],
      ['2', '2026-03-02', '2026-03-02', '6', '5', '-1'],
      // a day with no value on one side has no difference: it is not counted as zero
      ['3', '2026-03-03', '2026-03-03', '', '9', ''],
      ['4', '2026-03-04', '2026-03-04', '8', '8', '0'],
    ])
    // the header names the unit and the sides
    const headers = wrapper.findAll('[data-testid="compare-table"] thead th').map(cell => cell.text())
    expect(headers).toEqual(['Day', 'Date A', 'Date B', 'A (°C)', 'B (°C)', 'B − A (°C)'])
    // the numbers under it are over the three days both have: mean A 6, mean B 6.17, B − A +0.17
    expect(wrapper.find('[data-testid="compare-summary"]').text()).toContain('3 of 4 days compared')
    expect(wrapper.find('[data-testid="compare-mean"]').text()).toBe('On average, A is 6 °C and B is 6.17 °C; B − A = +0.17 °C.')
    expect(wrapper.find('[data-testid="compare-sum"]').exists(), 'a mean is no total').toBe(false)
    expect(wrapper.find('[data-testid="compare-difference-note"]').text()).toContain('side B minus side A, in °C')
    expect(wrapper.find('[data-testid="compare-chart-note"]').text()).toContain('Aligned by calendar date')
  })

  it('draws both series in the one chart, told apart by more than the colour: B is dashed and has square markers', async () => {
    backend(() => ({ metadata: { parameters: [info()] }, values: [row('00011', '2026-03-01', 4), row('00044', '2026-03-01', 5)] }))
    const wrapper = await open(STATIONS_LINK)
    await vi.waitFor(() => expect(charts.options.some(option => option.series?.some((series: any) => series.type === 'line'))).toBe(true), { timeout: 5000 })
    const drawn = charts.options.filter(option => option.series?.some((series: any) => series.type === 'line')).at(-1)
    const lines = drawn.series.filter((series: any) => series.type === 'line')
    expect(lines.map((line: any) => [line.name, line.lineStyle.type, line.symbol])).toEqual([
      ['A · Donaueschingen (00011)', 'solid', 'circle'],
      ['B · Großenkneten (00044)', 'dashed', 'rect'],
    ])
    expect(lines[0].itemStyle.color).not.toBe(lines[1].itemStyle.color)
    // the table is the chart's alternative, and the figure is described by the sentence that says so
    expect(wrapper.find('[role="figure"]').attributes('aria-label')).toBe('Chart of Mean air temperature (2 m): A, Donaueschingen (00011), and B, Großenkneten (00044)')
  })

  it('opens two periods of one station by their place in the period, in two requests, day 1 against day 1', async () => {
    backend((query) => {
      const march = query.timestamp!.startsWith('2025')
      return { metadata: { parameters: [info()] }, values: [1, 2, 3].map(day => row('00011', `${march ? 2025 : 2026}-03-0${day}`, (march ? 10 : 12) - day)) }
    })
    const wrapper = await open(PERIODS_LINK)
    await vi.waitFor(() => expect(wrapper.find('[data-testid="compare-table"]').exists()).toBe(true), { timeout: 5000 })
    expect(asked.map(query => [query.stations, query.timestamp]).sort()).toEqual([['00011', '2025-03-01/2025-03-03'], ['00011', '2026-03-01/2026-03-03']])
    const rows = wrapper.findAll('[data-testid="compare-row"]').map(each => each.findAll('th, td').map(cell => cell.text()))
    expect(rows).toEqual([
      ['1', '2025-03-01', '2026-03-01', '9', '11', '+2'],
      ['2', '2025-03-02', '2026-03-02', '8', '10', '+2'],
      ['3', '2025-03-03', '2026-03-03', '7', '9', '+2'],
    ])
    expect(wrapper.find('[data-testid="compare-chart-note"]').text()).toContain('Aligned by day of the period: day 1 of A with day 1 of B')
    expect(wrapper.find('[data-testid="compare-chart-note"]').text()).not.toContain('is shorter')
  })

  it('says which period is shorter where the two are not as long, and compares as far as it reaches', async () => {
    backend(() => ({ metadata: { parameters: [info()] }, values: [row('00011', '2026-03-01', 1), row('00011', '2026-03-02', 2)] }))
    const wrapper = await open('/compare?compare=periods&resolution=daily&parameter=temperature_air_mean_2m&stations=00011&periodA=2025-03-01/2025-03-02&periodB=2026-03-01/2026-03-04')
    await vi.waitFor(() => expect(wrapper.find('[data-testid="compare-table"]').exists()).toBe(true), { timeout: 5000 })
    expect(wrapper.find('[data-testid="compare-chart-note"]').text()).toContain('Period A is shorter: its 2 days are compared with the first 2 of the other, and the 2 that follow have no partner and no difference.')
    expect(wrapper.findAll('[data-testid="compare-row"]')).toHaveLength(4)
  })

  it('says what is subtracted where the values are totals: the difference of two totals, and the totals of the steps both have', async () => {
    backend(() => ({
      metadata: { parameters: [{ ...info('mm', 'sum'), name: 'precipitation_amount' }] },
      values: [{ ...row('00011', '2026-03-01', 2), parameter: 'precipitation_amount' }, { ...row('00044', '2026-03-01', 5), parameter: 'precipitation_amount' }],
    }))
    const wrapper = await open(STATIONS_LINK.replace('temperature_air_mean_2m', 'precipitation_amount'))
    await vi.waitFor(() => expect(wrapper.find('[data-testid="compare-table"]').exists()).toBe(true), { timeout: 5000 })
    expect(wrapper.find('[data-testid="compare-sum"]').text()).toBe('In total, A is 2 mm and B is 5 mm; B − A = +3 mm.')
    expect(wrapper.find('[data-testid="compare-difference-note"]').text()).toContain('totals (or counts)')
  })

  it('refuses where the two sides are not the same kind of number, with the reason and no table', async () => {
    backend((query) => {
      const march = query.timestamp!.startsWith('2025')
      return { metadata: { parameters: [info(march ? '°C' : 'K')] }, values: [row('00011', march ? '2025-03-01' : '2026-03-01', 1)] }
    })
    const wrapper = await open(PERIODS_LINK)
    await vi.waitFor(() => expect(wrapper.find('[data-testid="compare-refused"]').exists()).toBe(true), { timeout: 5000 })
    expect(wrapper.find('[data-testid="compare-refused"]').text()).toContain('not the same kind of number (another unit)')
    expect(wrapper.find('[data-testid="compare-table"]').exists()).toBe(false)
  })

  it('says it where a station has no value in the period at all, and has nothing to subtract', async () => {
    backend(() => ({ metadata: { parameters: [info()] }, values: [row('00011', '2026-03-01', 1)] }))
    const wrapper = await open(STATIONS_LINK)
    await vi.waitFor(() => expect(wrapper.find('[data-testid="compare-summary"]').exists()).toBe(true), { timeout: 5000 })
    expect(wrapper.find('[data-testid="compare-summary"]').text()).toContain('No step has a value on both sides')
  })

  it('credits the provider once for both sides, with what wetterdienst did to the data', async () => {
    backend(() => ({ metadata: { parameters: [info()] }, values: [row('00011', '2026-03-01', 1), row('00044', '2026-03-01', 2)] }))
    const wrapper = await open(STATIONS_LINK)
    await vi.waitFor(() => expect(wrapper.find('[data-testid="compare-credit"]').exists()).toBe(true), { timeout: 5000 })
    const credit = wrapper.find('[data-testid="compare-credit"]')
    expect(credit.text()).toContain('Both sides come from this source')
    expect(credit.find('[data-testid="provider-credit-line"]').text()).toContain('Source: Deutscher Wetterdienst')
    expect(credit.find('[data-testid="processing-note"]').exists()).toBe(true)
  })

  it('writes the comparison into the address, so that a link opens it', async () => {
    backend(() => ({ values: [] }))
    await open(STATIONS_LINK)
    await vi.waitFor(() => expect(useRouter().currentRoute.value.query.stations).toBe('00011,00044'))
    expect(useRouter().currentRoute.value.query).toMatchObject({ compare: 'stations', resolution: 'daily', parameter: 'temperature_air_mean_2m', startDate: '2026-03-01', endDate: '2026-03-04' })
  })

  it('has the station of the map\'s link as side A, with no comparison to show yet', async () => {
    backend(() => ({ values: [] }))
    const wrapper = await open('/compare?compare=stations&resolution=daily&stations=00011')
    await vi.waitFor(() => expect(wrapper.text()).toContain('Donaueschingen'), { timeout: 5000 })
    expect(asked, 'one station is no comparison').toEqual([])
    expect(wrapper.find('[data-testid="tool-placeholder"]').exists()).toBe(true)
  })

  it('refuses a period longer than a comparison holds, where the reader is choosing, and keeps Show off', async () => {
    backend(() => ({ values: [] }))
    const wrapper = await open('/compare?compare=stations&resolution=daily&parameter=temperature_air_mean_2m&stations=00011,00044&startDate=2000-01-01&endDate=2026-03-01')
    await vi.waitFor(() => expect(wrapper.text()).toContain('A comparison holds at most 3,660 days. Choose a shorter period.'), { timeout: 5000 })
    expect(wrapper.find('[data-testid="compare-fetch"]').attributes('disabled')).toBeDefined()
  })

  it('drops a period that ends before it starts from a link and starts the fields with the last complete month', async () => {
    backend(() => ({ values: [] }))
    await open('/compare?compare=stations&resolution=daily&stations=00011,00044&startDate=2026-03-04&endDate=2026-03-01')
    await vi.waitFor(() => expect(useRouter().currentRoute.value.query.startDate).toMatch(/^\d{4}-\d{2}-01$/))
    expect(useRouter().currentRoute.value.query.startDate).not.toBe('2026-03-04')
  })
})
