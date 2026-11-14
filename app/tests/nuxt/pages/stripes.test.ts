import type { H3Event } from 'h3'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import process from 'node:process'
import { mockNuxtImport, mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { createError, getQuery, setResponseStatus } from 'h3'
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h, nextTick } from 'vue'
import { UApp } from '#components'
import { clearNuxtData, useSettings, useToast } from '#imports'
import MapStations from '~/components/MapStations.vue'
import StationPicker from '~/components/StationPicker.vue'
import StripesChart from '~/components/StripesChart.vue'
import StripesPage from '~/pages/stripes.vue'
import { SERIES_LABEL } from '~/utils/chart-theme'

// the placeholder of the tool before a result (GH-3850), where the result card has nothing to show yet
const PLACEHOLDER = 'Search for a station or pick one on the map, then click “Show” to create climate stripes'

// Real Leaflet draws nothing in happy-dom. The LMap stub holds a stand-in Leaflet map, as LMap
// holds the real one, for the station map to centre; it never emits ready, so no markers are built.
const { leafletMap } = vi.hoisted(() => ({
  leafletMap: { fitBounds: vi.fn() },
}))
vi.mock('@vue-leaflet/vue-leaflet', async () => {
  const { defineComponent, h } = await import('vue')
  return {
    LMap: defineComponent({
      setup: (_, { slots, expose }) => {
        expose({ leafletObject: leafletMap })
        return () => h('div', slots.default?.())
      },
    }),
    LTileLayer: defineComponent({ setup: () => () => null }),
  }
})

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
  svgToBlob: vi.fn(async () => new Blob(['image'])),
  downloadBlob: vi.fn(),
}))
vi.mock('~/utils/chart-image', () => image)

// Nuxt's reload of the page: the test's document does not take it
const { reloadNuxtApp } = vi.hoisted(() => ({ reloadNuxtApp: vi.fn() }))
mockNuxtImport('reloadNuxtApp', () => reloadNuxtApp)

// the messages of a language as its file has them (the build compiles an imported JSON of the locales)
const messagesOf = (code: string) => JSON.parse(readFileSync(join(process.cwd(), 'i18n', 'locales', `${code}.json`), 'utf8'))
const de = messagesOf('de')
const deHh = messagesOf('de-hh')
const en = messagesOf('en')
const fr = messagesOf('fr')
const lb = messagesOf('lb')

// every test starts with a chart that has drawn nothing, and a chart whose code loads
beforeEach(() => {
  echarts.chart.setOption.mockReset()
  echarts.chart.on.mockClear()
  echarts.chart.resize.mockClear()
  echarts.chart.dispose.mockClear()
  echarts.init.mockClear()
  echarts.state.loadFails = false
  image.svgToBlob.mockClear()
  image.downloadBlob.mockClear()
})

describe('stripes Page', () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn()
  })

  it('renders the page', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({ stations: [] }), { status: 200 }),
    )

    const wrapper = await mountSuspended(StripesPage)
    expect(wrapper.exists()).toBe(true)
  })

  it('displays climate stripes title', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({ stations: [] }), { status: 200 }),
    )

    const wrapper = await mountSuspended(StripesPage)
    const text = wrapper.text()

    expect(text).toContain('Climate stripes')
  })

  it('has station selection', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({ stations: [] }), { status: 200 }),
    )

    const wrapper = await mountSuspended(StripesPage)

    expect(wrapper.html()).toBeTruthy()
  })

  it('allows selecting kind (temperature/precipitation)', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({ stations: [] }), { status: 200 }),
    )

    const wrapper = await mountSuspended(StripesPage)
    const vm = wrapper.vm as any

    expect(vm.kind).toBeDefined()
    expect(['temperature', 'precipitation']).toContain(vm.kind)
  })

  it('fetches stations based on kind', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({ stations: [] }), { status: 200 }),
    )

    const wrapper = await mountSuspended(StripesPage)
    const vm = wrapper.vm as any

    expect(vm.stations).toBeDefined()
  })

  it('clicking the about toggle reveals the explanatory text', async () => {
    const wrapper = await mountSuspended(StripesPage, { attachTo: document.body })
    expect(wrapper.text()).not.toContain('data visualization designed to communicate')

    const aboutButton = wrapper.findAll('button').find(b => b.text().includes('About climate stripes'))
    await aboutButton!.trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('data visualization designed to communicate')
  })

  it('clicking Show plots the stripes, and clicking Reset clears the plot', async () => {
    const station = { station_id: '1048', name: 'Berlin-Tempelhof', region: 'Berlin', start_timestamp: '1950-01-01', end_timestamp: '2020-01-01' }
    registerEndpoint('/api/stripes/stations', () => ({ stations: [station] }))
    registerEndpoint('/api/stripes/values', () => ({
      series: { station },
      values: [{ timestamp: '2000-01-01T00:00:00+00:00', value: 9.5 }],
    }))

    const wrapper = await mountSuspended(StripesPage, { attachTo: document.body })
    const vm = wrapper.vm as any
    // Let the stations useFetch resolve so the "clear selection if not in
    // stations list" watcher doesn't wipe the station set directly below.
    await new Promise(resolve => setTimeout(resolve, 50))
    await wrapper.vm.$nextTick()

    vm.selectedStation = station
    await wrapper.vm.$nextTick()

    const fetchButton = wrapper.findAll('button').find(b => b.text() === 'Show')
    expect(fetchButton?.attributes('disabled')).toBeUndefined()
    await fetchButton!.trigger('click')
    await new Promise(resolve => setTimeout(resolve, 100))
    await wrapper.vm.$nextTick()

    expect(vm.hasPlot).toBe(true)

    const resetButton = wrapper.findAll('button').find(b => b.text() === 'Reset')
    await resetButton!.trigger('click')
    await wrapper.vm.$nextTick()

    expect(vm.hasPlot).toBe(false)
  })
})

describe('stripes Page station map', () => {
  const tempelhof = { station_id: '1048', name: 'Berlin-Tempelhof', region: 'Berlin', latitude: 52.47, longitude: 13.4, start_timestamp: '1950-01-01', end_timestamp: '2020-01-01' }
  const potsdam = { station_id: '3987', name: 'Potsdam', region: 'Brandenburg', latitude: 52.38, longitude: 13.06, start_timestamp: '1893-01-01', end_timestamp: '2020-01-01' }

  let wrapper: Awaited<ReturnType<typeof mountSuspended>> | undefined

  afterEach(() => {
    wrapper?.unmount()
    wrapper = undefined
    leafletMap.fitBounds.mockClear()
  })

  it('picks its station with the shared station picker, for one station, which a pick on the map shows as a chip in the list', async () => {
    registerEndpoint('/api/stripes/stations', () => ({ stations: [tempelhof, potsdam] }))
    wrapper = await mountSuspended(StripesPage, { attachTo: document.body, route: '/stripes?kind=precipitation' })
    const vm = wrapper.vm as any
    await vi.waitFor(() => expect(vm.stations).toHaveLength(2))
    const picker = wrapper.findComponent(StationPicker)
    expect((picker.props() as any).tool).toBe('stripes')
    expect((picker.props() as any).multiple).toBeFalsy()

    await wrapper.findAll('[role="radio"]').find((radio: { text: () => string }) => radio.text() === 'Map')!.trigger('click')
    await vi.waitFor(() => expect(wrapper!.findComponent(MapStations).exists()).toBe(true))
    wrapper.findComponent(MapStations).vm.$emit('update:selectedStations', [tempelhof])
    await vi.waitFor(() => expect(vm.selectedStation?.station_id).toBe('1048'))

    await wrapper.findAll('[role="radio"]').find((radio: { text: () => string }) => radio.text() === 'List')!.trigger('click')
    expect(wrapper.findAll('[data-station-chip]').map((chip: { text: () => string }) => chip.text())).toEqual(['Berlin-Tempelhof (1048) ×'])
    // a pick replaces the one before
    wrapper.findComponent(StationPicker).vm.$emit('update:selected', [potsdam])
    await vi.waitFor(() => expect(vm.selectedStation?.station_id).toBe('3987'))
    // and the chip clears it
    await wrapper.find('[data-station-chip]').trigger('click')
    await vi.waitFor(() => expect(vm.selectedStation).toBeNull())
  })

  it('stays centred on all stations, as the user chose, when the map\'s section renders again', async () => {
    registerEndpoint('/api/stripes/stations', () => ({ stations: [tempelhof, potsdam] }))
    // precipitation, as the pages the tests above leave mounted hold the temperature stations' fetch
    wrapper = await mountSuspended(StripesPage, { attachTo: document.body, route: '/stripes?kind=precipitation' })
    const vm = wrapper.vm as any
    await vi.waitFor(() => expect(vm.stations).toHaveLength(2))
    await wrapper.findAll('[role="radio"]').find((radio: { text: () => string }) => radio.text() === 'Map')!.trigger('click')
    await vi.waitFor(() => expect(wrapper!.findComponent(MapStations).exists()).toBe(true))
    const map = wrapper.findComponent(MapStations)
    const fitBounds = leafletMap.fitBounds
    // an icon button beside the zoom buttons: its name is its label
    const centreButton = () => map.find('[data-testid="map-center"]')
    const centreLabel = () => centreButton().attributes('aria-label')

    // a station is chosen on the map, which centres on it
    map.vm.$emit('update:selectedStations', [tempelhof])
    await vi.waitFor(() => expect(centreLabel()).toBe('Center on all stations'))
    expect(fitBounds).toHaveBeenCalled()
    await centreButton().trigger('click')
    expect(centreLabel()).toBe('Center on selected station')
    const fits = fitBounds.mock.calls.length

    // the map's section renders again, with the same station chosen: the component around the map
    // renders the page's slot content anew
    map.vm.$parent!.$forceUpdate()
    await nextTick()
    await nextTick()

    expect(centreLabel()).toBe('Center on selected station')
    expect(fitBounds).toHaveBeenCalledTimes(fits)
  })
})

// the chart's drawings, and what they drew
const drawnOptions = () => echarts.chart.setOption.mock.calls.filter(([, flags]) => flags?.notMerge).map(([option]) => option as any)
const draws = () => drawnOptions().length
const drawnOption = () => drawnOptions().at(-1)!
/** The texts of an option, drawn as the library draws them */
function textsOf(option: unknown, width = 800, height = 600) {
  const chart = echarts.state.realInit!(null, null, { renderer: 'svg', ssr: true, width, height })
  chart.setOption(option)
  const svg = chart.renderToSVGString() as string
  chart.dispose()
  return [...svg.matchAll(/<text[^>]*>([^<]*)<\/text>/g)].map(match => match[1]!)
}
/** The fills of the stripes of an option, in the order of its years */
function fillsOf(option: unknown) {
  const chart = echarts.state.realInit!(null, null, { renderer: 'svg', ssr: true, width: 800, height: 600 })
  chart.setOption(option)
  const svg = chart.renderToSVGString() as string
  chart.dispose()
  return [...svg.matchAll(/<path d="M[^"]*" fill="(rgb\([^"]*\))"/g)].map(match => match[1]!)
}

// the test's document has no layout: the chart is 800 px wide, its plot from 20 to 780 px
const stage = () => document.body.querySelector<HTMLElement>('.sc-stage')!
const readout = () => document.body.querySelector<HTMLElement>('[data-testid="stripes-readout"]')
const readoutRows = () => [...(readout()?.querySelectorAll('dt') ?? [])].map((dt, i) => [dt.textContent!.trim(), readout()!.querySelectorAll('dd')[i]!.textContent!.trim()])
/** Moves the pointer over the stripe of `year` in a chart that shows the years `first` to `last` */
function hoverYear(year: number, first: number, last: number) {
  const x = 20 + ((year - (first - 0.5)) / (last - first + 1)) * 760
  const event = new MouseEvent('pointermove', { bubbles: true, cancelable: true, clientX: x })
  Object.defineProperty(event, 'pointerType', { value: 'mouse' })
  stage().dispatchEvent(event)
}
const zoomButton = (name: string) => document.body.querySelector<HTMLButtonElement>(`.sc-toolbar button[aria-label="${name}"]`)!

const TWO_YEARS = [
  { timestamp: '2019-01-01T00:00:00+00:00', value: 9.1 },
  { timestamp: '2020-01-01T00:00:00+00:00', value: 9.5 },
]

describe('stripes Page years', () => {
  const station = { station_id: '1048', name: 'Berlin-Tempelhof', region: 'Berlin', latitude: 52.47, longitude: 13.4, start_timestamp: '1950-01-01', end_timestamp: '2020-01-01' }

  // a browser five hours west of UTC, where the first moment of a year in UTC is still the year before
  let zone: string | undefined
  beforeAll(() => {
    zone = process.env.TZ
    process.env.TZ = 'America/New_York'
    // the zone taken up, else the test passes in UTC against getFullYear as well
    expect(new Date(2020, 0, 1).getTimezoneOffset()).toBe(300)
  })

  let wrapper: Awaited<ReturnType<typeof mountSuspended>> | undefined
  afterEach(() => {
    wrapper?.unmount()
    wrapper = undefined
  })

  afterAll(() => {
    if (zone === undefined)
      delete process.env.TZ
    else
      process.env.TZ = zone
  })

  // the page with the station chosen and Show clicked, whatever language its button is written in
  async function show(route: string) {
    registerEndpoint('/api/stripes/stations', () => ({ stations: [station] }))
    registerEndpoint('/api/stripes/values', () => ({ series: { station }, values: TWO_YEARS }))
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

  async function withLocale(language: string, body: () => Promise<void>) {
    const harness = await mountSuspended(defineComponent({
      setup: () => ({ setLocale: useI18n().setLocale }),
      render: () => h('div'),
    }))
    await (harness.vm as any).setLocale(language)
    try {
      await body()
    }
    finally {
      await (harness.vm as any).setLocale('en')
      harness.unmount()
    }
  }

  it('labels each year as the backend gives it', async () => {
    await show('/stripes?kind=precipitation&show_years=true')
    // each year's value comes at its first moment in UTC, which is the year before in a zone west of it
    expect(drawnOption().series[0].data.map((point: number[]) => point[0])).toEqual([2019, 2020])
    expect(textsOf(drawnOption())).toEqual(expect.arrayContaining(['2019', '2020']))
  })

  it('names the value and the trend of the readout in the active language', async () => {
    // they read "Value:" and "Trend:" in every language (GH-2610)
    await withLocale('de', async () => {
      await show('/stripes?kind=temperature&show_timeseries=true&show_trendline=true')
      hoverYear(2019, 2019, 2020)
      await nextTick()
      expect(readoutRows().map(([name]) => name)).toEqual(['Wert', 'Trend', 'Klasse'])
      expect(readout()!.textContent).not.toContain('Value')
    })
  })

  // the numbers of the readout are written with the language's separators (GH-2971)
  it.each([
    ['en', '9.10'],
    ['de', '9,10'],
    ['fr', '9,10'],
    ['pl', '9,10'],
  ])('writes the numbers of the readout as %s does', async (language, expected) => {
    await withLocale(language, async () => {
      await show('/stripes?kind=temperature')
      hoverYear(2019, 2019, 2020)
      await nextTick()
      expect(readoutRows()[0]![1]).toBe(expected)
    })
  })

  it('draws the chart again in the language it is switched to', async () => {
    const harness = await mountSuspended(defineComponent({
      setup: () => ({ setLocale: useI18n().setLocale }),
      render: () => h('div'),
    }))
    try {
      await show('/stripes?kind=temperature')
      expect(textsOf(drawnOption())).toContain('Source: Deutscher Wetterdienst')
      const before = draws()
      await (harness.vm as any).setLocale('de')
      await vi.waitFor(() => expect(draws()).toBeGreaterThan(before))
      expect(textsOf(drawnOption())).toContain('Quelle: Deutscher Wetterdienst')
    }
    finally {
      await (harness.vm as any).setLocale('en')
      harness.unmount()
    }
  })
})

// the loading of the chart's code can take seconds on a busy runner, past the default test timeout
describe('stripes Page chart that could not be drawn', { timeout: 15_000 }, () => {
  const station = { station_id: '1048', name: 'Berlin-Tempelhof', region: 'Berlin', latitude: 52.47, longitude: 13.4, start_timestamp: '1950-01-01', end_timestamp: '2020-01-01' }

  // the chart area's Retry button, and the alert beside it, not a toast's
  const retry = () => [...document.body.querySelectorAll('button')].find(button => button.textContent?.trim() === 'Retry')
  const note = () => retry()?.parentElement?.querySelector('[role="alert"]')?.textContent?.trim()
  const downloadMenu = () => document.body.querySelector('button[aria-haspopup="menu"]')
  const toasts = () => [...document.body.querySelectorAll('[data-slot="title"]')].map(title => title.textContent?.trim())

  let wrapper: Awaited<ReturnType<typeof mountSuspended>> | undefined
  afterEach(() => {
    vi.restoreAllMocks()
    echarts.state.loadFails = false
    wrapper?.unmount()
    wrapper = undefined
    useToast().clear()
    document.documentElement.classList.remove('dark')
    document.body.innerHTML = ''
  })

  // the page in the app's UApp, which shows its toasts, with the station chosen and Show clicked
  async function showStripes(values: Array<{ timestamp: string, value: number | null }> = TWO_YEARS) {
    // what a test left in the settings by the options it switched does not decide what is drawn
    const route = '/stripes?kind=precipitation&show_years=true&show_title=true&show_source=true&show_data_availability=true'
    registerEndpoint('/api/stripes/stations', () => ({ stations: [station] }))
    registerEndpoint('/api/stripes/values', () => ({ series: { station }, values }))
    wrapper = await mountSuspended(defineComponent({
      setup: () => () => h(UApp, null, { default: () => h(StripesPage) }),
    }), { attachTo: document.body, route })
    const vm = wrapper.findComponent(StripesPage).vm as any
    await vi.waitFor(() => expect(vm.stations).toHaveLength(1))
    vm.selectedStation = station
    await nextTick()
    await wrapper.findAll('button').find((b: { text: () => string }) => b.text() === 'Show')!.trigger('click')
    return vm
  }
  const failDrawings = () => echarts.chart.setOption.mockImplementation(() => {
    throw new Error('drawing failed')
  })
  const drawAgain = () => echarts.chart.setOption.mockReset()
  const twenty = Array.from({ length: 20 }, (_, i) => ({ timestamp: `${2001 + i}-01-01T00:00:00+00:00`, value: i }))

  it('says so where the chart\'s code failed to load, and loads it again on Retry', async () => {
    echarts.state.loadFails = true
    const logged = vi.spyOn(console, 'error').mockImplementation(() => {})
    await showStripes()
    await vi.waitFor(() => expect(retry()).toBeDefined(), { timeout: 5000 })
    expect(note()).toBe('The chart could not be drawn. Its code could not be loaded. If trying again does not help, reload the page.')
    expect(logged).toHaveBeenCalledWith('The chart could not be drawn', expect.any(Error))
    // no image of stripes that are not drawn
    expect(downloadMenu()).toBeNull()

    echarts.state.loadFails = false
    retry()!.click()
    await vi.waitFor(() => expect(retry()).toBeUndefined(), { timeout: 5000 })
    expect(draws()).toBe(1)
    expect(downloadMenu()).not.toBeNull()
  })

  it('says so where drawing fails, and draws the stripes on Retry', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    failDrawings()
    await showStripes()
    await vi.waitFor(() => expect(retry()).toBeDefined())
    expect(note()).toBe('The chart could not be drawn')

    drawAgain()
    retry()!.click()
    await vi.waitFor(() => expect(retry()).toBeUndefined())
    expect(draws()).toBe(1)
  })

  it('takes the note away with the stripes on Reset where the code failed to load', async () => {
    echarts.state.loadFails = true
    vi.spyOn(console, 'error').mockImplementation(() => {})
    await showStripes()
    await vi.waitFor(() => expect(retry()).toBeDefined(), { timeout: 5000 })

    await wrapper!.findAll('button').find((b: { text: () => string }) => b.text() === 'Reset')!.trigger('click')
    expect(retry()).toBeUndefined()
    expect(document.body.textContent).toContain(PLACEHOLDER)
  })

  it('takes the note, and its Retry of the earlier values, away as Show fetches the stripes anew', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    failDrawings()
    const vm = await showStripes()
    await vi.waitFor(() => expect(retry()).toBeDefined())
    drawAgain()
    // the next values held, so the fetch is still under way
    let answer!: () => void
    const answered = new Promise<void>((resolve) => {
      answer = resolve
    })
    registerEndpoint('/api/stripes/values', async () => {
      await answered
      return { series: { station }, values: [{ timestamp: '2020-01-01T00:00:00+00:00', value: 9.5 }] }
    })

    await wrapper!.findAll('button').find((b: { text: () => string }) => b.text() === 'Show')!.trigger('click')
    expect(retry()).toBeUndefined()
    // the held fetch let finish here, so it draws nothing into the next test
    answer()
    await vi.waitFor(() => expect(vm.isLoading).toBe(false))
  })

  it('takes the chart away on Reset, and draws nothing into the cleared chart area', async () => {
    await showStripes()
    await vi.waitFor(() => expect(draws()).toBe(1))
    echarts.chart.dispose.mockClear()

    await wrapper!.findAll('button').find((b: { text: () => string }) => b.text() === 'Reset')!.trigger('click')
    expect(echarts.chart.dispose).toHaveBeenCalled()
    await new Promise(resolve => setTimeout(resolve, 50))
    expect(draws()).toBe(1)
    expect(document.querySelector('.sc-stage')).toBeNull()
  })

  it('draws the stripes again from the values it has where a display option changes, and fetches nothing', async () => {
    const vm = await showStripes()
    await vi.waitFor(() => expect(downloadMenu()).not.toBeNull())
    // a request is sent as the fetch starts, so one sent for the option is seen by the redraw
    const fetched = vi.spyOn(globalThis, '$fetch')
    const before = draws()

    vm.showYears = false
    await vi.waitFor(() => expect(draws()).toBe(before + 1))
    expect(textsOf(drawnOption())).not.toContain('2020')
    expect(fetched).not.toHaveBeenCalled()
    expect(vm.isLoading).toBe(false)
  })

  it('saves the stripes from a copy drawn off screen, in the light theme whatever the page shows, and leaves the chart as it is', async () => {
    const vm = await showStripes()
    await vi.waitFor(() => expect(downloadMenu()).not.toBeNull())
    const before = echarts.chart.setOption.mock.calls.length
    echarts.chart.dispose.mockClear()
    echarts.init.mockClear()
    image.svgToBlob.mockClear()
    image.downloadBlob.mockClear()

    await vm.downloadStripes('png')

    // a chart of its own, with no element, which is gone once saved; the one shown was not touched
    expect(echarts.init).toHaveBeenCalledTimes(1)
    expect(echarts.init.mock.calls[0]![0]).toBeNull()
    expect(echarts.chart.setOption.mock.calls.length).toBe(before)
    expect(echarts.chart.dispose).not.toHaveBeenCalled()
    const [svg, options] = image.svgToBlob.mock.calls[0] as unknown as [string, { format: string, width: number, height: number, scale: number }]
    expect(options).toMatchObject({ format: 'png', width: 800, height: 600, scale: 3 })
    expect(svg).toContain('Climate stripes (Precipitation) for Berlin-Tempelhof, Germany (1048)')
    expect(image.downloadBlob.mock.calls[0]![1]).toBe('climate_stripes_precipitation_1048_Berlin-Tempelhof.png')
  })

  it('names the files of the menu for each format, and saves a vector at the scale of one', async () => {
    const vm = await showStripes()
    await vi.waitFor(() => expect(downloadMenu()).not.toBeNull())
    image.svgToBlob.mockClear()
    image.downloadBlob.mockClear()
    await vm.downloadStripes('jpeg')
    await vm.downloadStripes('svg')
    expect(image.svgToBlob.mock.calls.map(call => (call as unknown as [string, { format: string, scale: number }])[1])).toMatchObject([{ format: 'jpeg', scale: 3 }, { format: 'svg', scale: 1 }])
    expect(image.downloadBlob.mock.calls.map(call => call[1])).toEqual([
      'climate_stripes_precipitation_1048_Berlin-Tempelhof.jpeg',
      'climate_stripes_precipitation_1048_Berlin-Tempelhof.svg',
    ])
  })

  it('saves the stripes at the zoom they are shown in', async () => {
    const vm = await showStripes(twenty)
    await vi.waitFor(() => expect(downloadMenu()).not.toBeNull())
    zoomButton('Zoom in').click()
    await nextTick()
    zoomButton('Later years').click()
    await nextTick()
    image.svgToBlob.mockClear()

    await vm.downloadStripes('png')

    const svg = (image.svgToBlob.mock.calls[0] as unknown as [string])[0]
    const years = [...svg.matchAll(/<text[^>]*>(\d{4})<\/text>/g)].map(match => match[1])
    expect(years).toHaveLength(2)
    expect(years).not.toContain('2001')
    expect(years.at(-1)).toBe('2020')
  })

  it('draws the stripes again in the dark scheme in the zoom they are shown in', async () => {
    await showStripes(twenty)
    await vi.waitFor(() => expect(downloadMenu()).not.toBeNull())
    zoomButton('Zoom in').click()
    await nextTick()
    const before = draws()
    const canvas = () => document.body.querySelector<HTMLElement>('.sc-canvas')!
    expect(canvas().dataset.chartScheme).toBe('light')

    document.documentElement.classList.add('dark')
    await vi.waitFor(() => expect(draws()).toBe(before + 1))
    expect(canvas().dataset.chartScheme).toBe('dark')
    // the zoom is the chart's own state: a reset is still there to go back from
    expect(zoomButton('Reset zoom').disabled).toBe(false)
    expect(drawnOption().dataZoom[0].endValue - drawnOption().dataZoom[0].startValue).toBeLessThan(20)
  })

  it('has the camera of the toolbar save the PNG the modebar\'s had, named for the station', async () => {
    await showStripes()
    await vi.waitFor(() => expect(downloadMenu()).not.toBeNull())
    image.svgToBlob.mockClear()
    image.downloadBlob.mockClear()
    zoomButton('Download plot as a PNG').click()
    await vi.waitFor(() => expect(image.downloadBlob).toHaveBeenCalledOnce())
    // the size the camera has always saved, 1400 px wide at twice the size
    expect((image.svgToBlob.mock.calls[0] as unknown as [string, unknown])[1]).toMatchObject({ format: 'png', width: 1400, height: 700, scale: 2 })
    expect(image.downloadBlob.mock.calls[0]![1]).toBe('climate_stripes_precipitation_1048.png')
  })

  it('says the stripes image could not be saved where its export fails', async () => {
    const vm = await showStripes()
    await vi.waitFor(() => expect(downloadMenu()).not.toBeNull())
    const failed = new Error('export failed')
    image.svgToBlob.mockRejectedValueOnce(failed)
    const logged = vi.spyOn(console, 'error').mockImplementation(() => {})

    await vm.downloadStripes('png')

    await vi.waitFor(() => expect(toasts()).toContain('The chart image could not be saved'))
    expect(logged).toHaveBeenCalledWith('The chart image could not be saved', failed)
  })
})

// The numbers follow the unit settings (GH-3980): the request carries the unit, the page says the unit the answer names,
// and the colours, which are relative, are the same
describe('stripes Page units', () => {
  const station = { station_id: '1048', name: 'Berlin-Tempelhof', region: 'Berlin', latitude: 52.47, longitude: 13.4, start_timestamp: '1950-01-01', end_timestamp: '2020-01-01' }

  // the query of each request of values, and the backend's answer: in the unit asked for, from degree Celsius
  const asked: Array<Record<string, string>> = []
  const other = { ...station, station_id: '3987', name: 'Potsdam' }
  // an answer of the values held until the test lets it go
  let gate: Promise<void> | null = null
  function serveValues() {
    registerEndpoint('/api/stripes/stations', () => ({ stations: [station] }))
    registerEndpoint('/api/stripes/values', async (event) => {
      const query = getQuery(event) as Record<string, string>
      asked.push(query)
      await gate
      const targets = JSON.parse(query.unit_targets ?? '{}') as { temperature?: string, precipitation?: string }
      const fahrenheit = targets.temperature === 'degree_fahrenheit'
      return {
        series: { station, unit: targets.precipitation ?? targets.temperature ?? 'degree_celsius' },
        values: [
          { timestamp: '2019-01-01T00:00:00+00:00', value: fahrenheit ? 9 * 1.8 + 32 : 9 },
          { timestamp: '2020-01-01T00:00:00+00:00', value: fahrenheit ? 11 * 1.8 + 32 : 11 },
        ],
      }
    })
  }

  let wrapper: Awaited<ReturnType<typeof mountSuspended>> | undefined
  afterEach(() => {
    wrapper?.unmount()
    wrapper = undefined
    asked.length = 0
    gate = null
    const { units } = useSettings().settings.value
    units.temperature = 'degree_celsius'
    units.precipitation = 'millimeter'
  })

  const showButton = () => wrapper!.findAll('button').find((b: { text: () => string }) => b.text() === 'Show')!
  async function show(route: string, years?: { startYear: number, endYear: number }) {
    serveValues()
    wrapper = await mountSuspended(StripesPage, { attachTo: document.body, route })
    const vm = wrapper.vm as any
    await vi.waitFor(() => expect(vm.stations.length).toBeGreaterThan(0))
    vm.selectedStation = station
    if (years)
      Object.assign(vm, years)
    await nextTick()
    echarts.chart.setOption.mockClear()
    await showButton().trigger('click')
    await vi.waitFor(() => expect(draws()).toBeGreaterThan(0))
    return vm
  }
  // the readout of the first of the two years, which names the unit the answer says its values are in
  async function hoveredValue() {
    hoverYear(2019, 2019, 2020)
    await nextTick()
    return readoutRows()[0]![1]
  }
  // the colours of the stripes, which are relative to the values and do not change with the unit
  const colours = () => fillsOf(drawnOption())
  // the sentence the figure is described by, and the head of the table of the years, behind its button
  const sentence = () => document.getElementById(document.body.querySelector('[role="figure"]')?.getAttribute('aria-describedby')?.split(' ')[0] ?? '')?.textContent?.trim() ?? ''
  async function tableHead() {
    await vi.waitFor(() => expect(sentence()).not.toBe(''))
    if (!document.body.querySelector('table'))
      [...document.body.querySelectorAll('button')].find(button => button.textContent?.trim() === 'Show as table')!.click()
    await vi.waitFor(() => expect(document.body.querySelector('table')).not.toBeNull())
    return [...document.body.querySelectorAll('table thead th')].map(th => th.textContent?.trim())
  }

  it('asks for degree Celsius by default, and says it in the sentence, the table and the readout', async () => {
    await show('/stripes?kind=temperature&show_timeseries=true')
    expect(asked.map(query => JSON.parse(query.unit_targets!))).toEqual([{ temperature: 'degree_celsius' }])
    await vi.waitFor(() => expect(sentence()).toContain('Lowest value 9.00 °C in 2019, highest value 11.00 °C in 2020.'))
    expect(await tableHead()).toContain('Value (°C)')
    expect(await hoveredValue()).toBe('9.00 °C')
    expect(colours()).toEqual(['rgb(5, 48, 97)', 'rgb(178, 24, 43)'])
  })

  it('asks for degree Fahrenheit where the settings choose it, and says it everywhere it writes a number', async () => {
    useSettings().settings.value.units.temperature = 'degree_fahrenheit'
    await show('/stripes?kind=temperature&show_timeseries=true')
    expect(asked.map(query => JSON.parse(query.unit_targets!))).toEqual([{ temperature: 'degree_fahrenheit' }])
    await vi.waitFor(() => expect(sentence()).toContain('Lowest value 48.20 °F in 2019, highest value 51.80 °F in 2020.'))
    expect(await tableHead()).toContain('Value (°F)')
    expect(await hoveredValue()).toBe('48.20 °F')
    // the colours are relative, the same as in degree Celsius
    expect(colours()).toEqual(['rgb(5, 48, 97)', 'rgb(178, 24, 43)'])
  })

  it('asks the precipitation stripes for the unit of precipitation', async () => {
    useSettings().settings.value.units.temperature = 'degree_fahrenheit'
    useSettings().settings.value.units.precipitation = 'liter_per_square_meter'
    await show('/stripes?kind=precipitation')
    expect(asked.map(query => JSON.parse(query.unit_targets!))).toEqual([{ precipitation: 'liter_per_square_meter' }])
    expect(await tableHead()).toContain('Value (l/m²)')
  })

  it('fetches the values shown again, not the selection the form holds now, where the unit changes (GH-3980)', async () => {
    const vm = await show('/stripes?kind=temperature', { startYear: 2005, endYear: 2015 })
    expect(asked).toHaveLength(1)
    // a station and years chosen, and not confirmed with Show
    vm.selectedStation = other
    vm.startYear = 1990
    vm.endYear = 2000
    await nextTick()

    useSettings().settings.value.units.temperature = 'degree_fahrenheit'
    await vi.waitFor(() => expect(asked).toHaveLength(2))

    expect(asked[1]).toMatchObject({ station: '1048', start_year: '2005', end_year: '2015' })
    expect(JSON.parse(asked[1]!.unit_targets!)).toEqual({ temperature: 'degree_fahrenheit' })
  })

  it('fetches again, in the new unit, once a fetch under way ends, where the unit changes during it', async () => {
    await show('/stripes?kind=temperature')
    let release!: () => void
    gate = new Promise<void>((resolve) => {
      release = resolve
    })
    await showButton().trigger('click')
    await vi.waitFor(() => expect(asked).toHaveLength(2))

    // the fetch under way asked for degree Celsius
    useSettings().settings.value.units.temperature = 'degree_fahrenheit'
    await nextTick()
    expect(asked).toHaveLength(2)
    gate = null
    release()

    await vi.waitFor(() => expect(asked).toHaveLength(3))
    expect(JSON.parse(asked[2]!.unit_targets!)).toEqual({ temperature: 'degree_fahrenheit' })
    await vi.waitFor(() => expect(sentence()).toContain('°F'))
  })

  it('fetches the values again, in the new unit, where the settings change while the stripes are shown', async () => {
    await show('/stripes?kind=temperature')
    useSettings().settings.value.units.temperature = 'degree_kelvin'
    await vi.waitFor(() => expect(asked).toHaveLength(2))
    expect(JSON.parse(asked[1]!.unit_targets!)).toEqual({ temperature: 'degree_kelvin' })
    await vi.waitFor(() => expect(sentence()).toContain('K in 2019'))
    expect(await tableHead()).toContain('Value (K)')
  })
})

describe('stripes Page values that could not be fetched', () => {
  const tempelhof = { station_id: '1048', name: 'Berlin-Tempelhof', region: 'Berlin', latitude: 52.47, longitude: 13.4, start_timestamp: '1950-01-01', end_timestamp: '2020-01-01' }
  const potsdam = { station_id: '3987', name: 'Potsdam', region: 'Brandenburg', latitude: 52.38, longitude: 13.06, start_timestamp: '1893-01-01', end_timestamp: '2020-01-01' }
  const values = (station: typeof tempelhof) => ({
    series: { station },
    values: [
      { timestamp: '2019-01-01T00:00:00+00:00', value: 9.1 },
      { timestamp: '2020-01-01T00:00:00+00:00', value: 9.5 },
    ],
  })

  // the chart area's note of the failed fetch
  const note = () => [...document.body.querySelectorAll('[role="alert"] > span')].map(line => line.textContent?.trim()).join(' / ') || undefined
  const downloadMenu = () => document.body.querySelector('button[aria-haspopup="menu"]')

  // an answer held until the test lets it go
  function held<T>(answer: () => T) {
    let release!: () => void
    const released = new Promise<void>((resolve) => {
      release = resolve
    })
    const handler = async () => {
      await released
      return answer()
    }
    return { release, handler }
  }

  let wrapper: Awaited<ReturnType<typeof mountSuspended>> | undefined
  afterEach(() => {
    vi.restoreAllMocks()
    wrapper?.unmount()
    wrapper = undefined
    document.body.innerHTML = ''
  })

  // the requests the page makes, each settled however it ended
  let requests: Promise<unknown>[] = []
  function recordRequests() {
    const original = globalThis.$fetch
    requests = []
    vi.spyOn(globalThis, '$fetch').mockImplementation(((...args: Parameters<typeof original>) => {
      const request = original(...args)
      requests.push(request.catch(() => {}))
      return request
    }) as typeof original)
  }
  // every request recorded settled, and the page done with its answer
  async function settled() {
    await Promise.all(requests)
    await new Promise(resolve => setTimeout(resolve, 0))
  }

  const button = (label: string) => wrapper!.findAll('button').find((b: { text: () => string }) => b.text() === label)!

  // the page in the app's UApp, with the stations fetched
  async function mountPage() {
    registerEndpoint('/api/stripes/stations', () => ({ stations: [tempelhof, potsdam] }))
    wrapper = await mountSuspended(defineComponent({
      setup: () => () => h(UApp, null, { default: () => h(StripesPage) }),
    }), { attachTo: document.body, route: '/stripes?kind=precipitation' })
    const vm = wrapper.findComponent(StripesPage).vm as any
    await vi.waitFor(() => expect(vm.stations).toHaveLength(2))
    return vm
  }

  async function show(vm: any, station: typeof tempelhof) {
    vm.selectedStation = station
    await nextTick()
    await button('Show').trigger('click')
  }

  it('shows the placeholder of the tools, and no result card, before there is anything to put in it (GH-3850)', async () => {
    registerEndpoint('/api/stripes/values', () => new Promise(() => {}))
    const vm = await mountPage()
    expect(document.querySelector('[data-testid="tool-placeholder"]')?.getAttribute('data-tool')).toBe('stripes')
    expect(document.body.textContent).not.toContain('Visualization')
    expect(document.body.textContent, 'the card that holds the station and the years').toContain('Station and period')

    // the card comes for the loading, which has no other place to be
    await show(vm, tempelhof)
    expect(document.querySelector('[data-testid="tool-placeholder"]')).toBeNull()
    expect(document.body.textContent).toContain('Visualization')
    expect(document.body.textContent, 'the loading has its place in the card').toContain('Loading data')
  })

  it('tells the backend\'s reason in the chart area', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    registerEndpoint('/api/stripes/values', (event) => {
      setResponseStatus(event, 404)
      return { detail: 'No precipitation data for station 1048' }
    })
    const vm = await mountPage()
    await show(vm, tempelhof)

    await vi.waitFor(() => expect(note()).toBe('Failed to load data / No precipitation data for station 1048'))
    expect(vm.isLoading).toBe(false)
    expect(document.body.textContent).not.toContain(PLACEHOLDER)

    // Reset takes the note away
    await button('Reset').trigger('click')
    expect(note()).toBeUndefined()
    expect(document.body.textContent).toContain(PLACEHOLDER)
  })

  it('takes another station\'s stripes away as this one\'s are fetched, and tells why they could not be', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    registerEndpoint('/api/stripes/values', () => values(tempelhof))
    const vm = await mountPage()
    await show(vm, tempelhof)
    await vi.waitFor(() => expect(downloadMenu()).not.toBeNull())

    const failing = held(() => {
      throw createError({ statusCode: 502, statusMessage: 'Bad Gateway' })
    })
    registerEndpoint('/api/stripes/values', failing.handler)
    echarts.chart.dispose.mockClear()
    await show(vm, potsdam)
    // Tempelhof's stripes gone while Potsdam's are fetched
    expect(vm.hasPlot).toBe(false)
    expect(echarts.chart.dispose).toHaveBeenCalled()
    expect(downloadMenu()).toBeNull()

    failing.release()
    await vi.waitFor(() => expect(note()).toBe('Failed to load data / 502 Bad Gateway'))
    expect(vm.hasPlot).toBe(false)
    expect(vm.lastFetchedData).toBeNull()
  })

  it('offers no image of stripes that could not be drawn, while or after they are fetched anew in vain', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    registerEndpoint('/api/stripes/values', () => values(tempelhof))
    echarts.chart.setOption.mockImplementation(() => {
      throw new Error('drawing failed')
    })
    const vm = await mountPage()
    await show(vm, tempelhof)
    await vi.waitFor(() => expect(vm.plotFailed).toBe(true))

    const failing = held(() => {
      throw createError({ statusCode: 502, statusMessage: 'Bad Gateway' })
    })
    registerEndpoint('/api/stripes/values', failing.handler)
    await button('Show').trigger('click')
    // no empty chart area, with an image of nothing offered
    expect(vm.hasPlot).toBe(false)
    expect(downloadMenu()).toBeNull()

    failing.release()
    await vi.waitFor(() => expect(note()).toBe('Failed to load data / 502 Bad Gateway'))
    expect(vm.hasPlot).toBe(false)
    expect(downloadMenu()).toBeNull()
  })

  it('keeps the station\'s stripes, and tells the failure above them, where Show fetches them anew in vain', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    registerEndpoint('/api/stripes/values', () => values(tempelhof))
    const vm = await mountPage()
    await show(vm, tempelhof)
    await vi.waitFor(() => expect(downloadMenu()).not.toBeNull())

    registerEndpoint('/api/stripes/values', () => {
      throw createError({ statusCode: 502, statusMessage: 'Bad Gateway' })
    })
    vm.startYear = 2019
    await nextTick()
    await button('Show').trigger('click')

    await vi.waitFor(() => expect(note()).toBe('Failed to load data / 502 Bad Gateway'))
    expect(vm.hasPlot).toBe(true)
    expect(vm.lastFetchedData).not.toBeNull()
    expect(downloadMenu()).not.toBeNull()
  })

  it('stops a fetch on Reset, where no stripes were shown, and draws nothing', async () => {
    const vm = await mountPage()
    recordRequests()
    const answer = held(() => values(tempelhof))
    registerEndpoint('/api/stripes/values', answer.handler)
    echarts.chart.setOption.mockClear()
    await show(vm, tempelhof)
    expect(vm.isLoading).toBe(true)
    expect(button('Reset').attributes('disabled')).toBeUndefined()
    await button('Reset').trigger('click')
    expect(vm.isLoading).toBe(false)

    answer.release()
    await settled()
    expect(draws()).toBe(0)
    expect(vm.hasPlot).toBe(false)
    expect(document.body.textContent).toContain(PLACEHOLDER)
  })

  it('tells nothing where the kind changed while a fetch that then failed was under way', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    const failing = held(() => {
      throw createError({ statusCode: 502, statusMessage: 'Bad Gateway' })
    })
    registerEndpoint('/api/stripes/values', failing.handler)
    const vm = await mountPage()
    recordRequests()
    await show(vm, tempelhof)
    expect(vm.isLoading).toBe(true)

    vm.kind = 'temperature'
    await nextTick()
    expect(vm.isLoading).toBe(false)

    failing.release()
    await settled()
    expect(note()).toBeUndefined()
    expect(vm.fetchError).toBeNull()
  })

  it('draws nothing where another station was chosen while the fetch was under way', async () => {
    const vm = await mountPage()
    recordRequests()
    const answer = held(() => values(tempelhof))
    registerEndpoint('/api/stripes/values', answer.handler)
    echarts.chart.setOption.mockClear()
    await show(vm, tempelhof)
    expect(vm.isLoading).toBe(true)

    vm.selectedStation = potsdam
    await nextTick()
    // the fetch stopped at once: Potsdam's stripes can be asked for
    expect(vm.isLoading).toBe(false)
    expect(button('Show').attributes('disabled')).toBeUndefined()
    answer.release()
    await settled()
    expect(draws()).toBe(0)
    expect(vm.hasPlot).toBe(false)
    expect(vm.lastFetchedData).toBeNull()
    expect(vm.isLoading).toBe(false)
  })

  it('tells nothing where another station was chosen while a fetch that then failed was under way', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    const failing = held(() => {
      throw createError({ statusCode: 502, statusMessage: 'Bad Gateway' })
    })
    registerEndpoint('/api/stripes/values', failing.handler)
    const vm = await mountPage()
    recordRequests()
    await show(vm, tempelhof)

    vm.selectedStation = potsdam
    await nextTick()
    // the fetch stopped at once: Potsdam's stripes can be asked for
    expect(vm.isLoading).toBe(false)
    expect(button('Show').attributes('disabled')).toBeUndefined()
    failing.release()
    await settled()
    expect(note()).toBeUndefined()
    expect(vm.fetchError).toBeNull()
    expect(vm.isLoading).toBe(false)
  })
})

describe('stripes Page chart whose code a redeploy replaced', { timeout: 15_000 }, () => {
  // A redeploy replaces the chart's hashed chunk under an open tab: every Retry asks for the gone chunk
  // again and fails, and only reloading the page loads the new one
  const station = { station_id: '1048', name: 'Berlin-Tempelhof', region: 'Berlin', latitude: 52.47, longitude: 13.4, start_timestamp: '1950-01-01', end_timestamp: '2020-01-01' }
  const button = (label: string) => [...document.body.querySelectorAll('button')].find(button => button.textContent?.trim() === label)
  const note = () => button('Retry')?.parentElement?.querySelector('[role="alert"]')?.textContent?.trim()
  const hint = 'If trying again does not help, reload the page.'

  let wrapper: Awaited<ReturnType<typeof mountSuspended>> | undefined
  afterEach(() => {
    vi.restoreAllMocks()
    echarts.state.loadFails = false
    reloadNuxtApp.mockClear()
    wrapper?.unmount()
    wrapper = undefined
    document.body.innerHTML = ''
  })

  // the page with the station chosen and Show clicked, while the chart's chunk fails to load
  async function shownWithoutCode() {
    echarts.state.loadFails = true
    vi.spyOn(console, 'error').mockImplementation(() => {})
    registerEndpoint('/api/stripes/stations', () => ({ stations: [station] }))
    registerEndpoint('/api/stripes/values', () => ({ series: { station }, values: TWO_YEARS }))
    wrapper = await mountSuspended(StripesPage, { attachTo: document.body, route: '/stripes?kind=precipitation' })
    const vm = wrapper.vm as any
    await vi.waitFor(() => expect(vm.stations).toHaveLength(1))
    vm.selectedStation = station
    await nextTick()
    button('Show')!.click()
    await vi.waitFor(() => expect(button('Retry')).toBeDefined(), { timeout: 5000 })
  }

  it('says to reload the page, and reloads it, where the chart\'s code failed to load', async () => {
    await shownWithoutCode()
    // the two apart, as a screen reader reads the alert
    expect(note()).toBe(`The chart could not be drawn. Its code could not be loaded. ${hint}`)
    button('Reload page')!.click()
    // forced: unforced, Nuxt drops a second click within ten seconds of a first that did not help
    expect(reloadNuxtApp).toHaveBeenCalledExactlyOnceWith({ force: true })
  })

  it('offers no reload once the code loaded and only its drawing failed', async () => {
    // a reload loads nothing the drawing needs: Retry is the way
    await shownWithoutCode()
    echarts.state.loadFails = false
    echarts.chart.setOption.mockImplementationOnce(() => {
      throw new Error('drawing failed')
    })
    button('Retry')!.click()
    await vi.waitFor(() => expect(echarts.chart.setOption).toHaveBeenCalledOnce(), { timeout: 5000 })
    await vi.waitFor(() => expect(note()).toBe('The chart could not be drawn'))
    expect(button('Reload page')).toBeUndefined()
  })
})

describe('stripes Page requests answered with a 500', () => {
  const station = { station_id: '1048', name: 'Berlin-Tempelhof', region: 'Berlin', latitude: 52.47, longitude: 13.4, start_timestamp: '1950-01-01', end_timestamp: '2020-01-01' }

  let wrapper: Awaited<ReturnType<typeof mountSuspended>> | undefined
  // disposers of the endpoints these tests register, so none answers a later test
  const endpoints: Array<() => void> = []
  afterEach(() => {
    endpoints.splice(0).forEach(dispose => dispose())
    vi.restoreAllMocks()
    wrapper?.unmount()
    wrapper = undefined
    useToast().clear()
    document.body.innerHTML = ''
  })

  // counted at the endpoint, which a request reaches however it is made
  function failing() {
    const asked = { count: 0 }
    return {
      asked,
      handler: (event: H3Event) => {
        asked.count++
        setResponseStatus(event, 500)
        return { detail: 'Upstream failed' }
      },
    }
  }

  it('asks /api/stripes/stations once', async () => {
    const { asked, handler } = failing()
    endpoints.push(registerEndpoint('/api/stripes/stations', handler))
    // precipitation, as the pages the first tests leave mounted hold the temperature stations' fetch
    wrapper = await mountSuspended(StripesPage, { route: '/stripes?kind=precipitation' })
    const vm = wrapper.vm as any
    // a request asked again is under way until its second answer
    await vi.waitFor(() => {
      expect(asked.count).toBeGreaterThan(0)
      expect(vm.stationsPending).toBe(false)
    })
    expect(asked.count).toBe(1)
  })

  it('asks /api/stripes/values once, and tells its error', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    endpoints.push(registerEndpoint('/api/stripes/stations', () => ({ stations: [station] })))
    const { asked, handler } = failing()
    endpoints.push(registerEndpoint('/api/stripes/values', handler))
    wrapper = await mountSuspended(defineComponent({
      setup: () => () => h(UApp, null, { default: () => h(StripesPage) }),
    }), { attachTo: document.body, route: '/stripes?kind=precipitation' })
    const vm = wrapper.findComponent(StripesPage).vm as any
    await vi.waitFor(() => expect(vm.stations).toHaveLength(1))
    vm.selectedStation = station
    await nextTick()
    await wrapper.findAll('button').find((b: { text: () => string }) => b.text() === 'Show')!.trigger('click')
    await vi.waitFor(() => expect(document.body.textContent).toContain('Upstream failed'))
    expect(asked.count).toBe(1)
  })
})

describe('stripes Page requests answered with a 503 once', () => {
  const station = { station_id: '1048', name: 'Berlin-Tempelhof', region: 'Berlin', latitude: 52.47, longitude: 13.4, start_timestamp: '1950-01-01', end_timestamp: '2020-01-01' }

  let wrapper: Awaited<ReturnType<typeof mountSuspended>> | undefined
  // disposers of the endpoints these tests register, so none answers a later test
  const endpoints: Array<() => void> = []
  afterEach(() => {
    endpoints.splice(0).forEach(dispose => dispose())
    wrapper?.unmount()
    wrapper = undefined
    useToast().clear()
    document.body.innerHTML = ''
  })

  // a 503 the first time only, as a proxy gives while the backend restarts
  function flaky(answer: unknown) {
    const asked = { count: 0 }
    return {
      asked,
      handler: (event: H3Event) => {
        asked.count++
        if (asked.count === 1) {
          setResponseStatus(event, 503)
          return { detail: 'Service Unavailable' }
        }
        return answer
      },
    }
  }

  it('asks /api/stripes/stations once more, and lists what that answer brings', async () => {
    const { asked, handler } = flaky({ stations: [station] })
    endpoints.push(registerEndpoint('/api/stripes/stations', handler))
    // precipitation, as the pages the first tests leave mounted hold the temperature stations' fetch
    wrapper = await mountSuspended(StripesPage, { route: '/stripes?kind=precipitation' })
    const vm = wrapper.vm as any
    await vi.waitFor(() => expect(vm.stations).toHaveLength(1))
    expect(asked.count).toBe(2)
  })

  it('asks /api/stripes/values once more, and plots what that answer brings', async () => {
    endpoints.push(registerEndpoint('/api/stripes/stations', () => ({ stations: [station] })))
    const { asked, handler } = flaky({ series: { station }, values: [{ timestamp: '2000-01-01T00:00:00+00:00', value: 9.5 }] })
    endpoints.push(registerEndpoint('/api/stripes/values', handler))
    wrapper = await mountSuspended(defineComponent({
      setup: () => () => h(UApp, null, { default: () => h(StripesPage) }),
    }), { attachTo: document.body, route: '/stripes?kind=precipitation' })
    const vm = wrapper.findComponent(StripesPage).vm as any
    await vi.waitFor(() => expect(vm.stations).toHaveLength(1))
    vm.selectedStation = station
    await nextTick()
    await wrapper.findAll('button').find((b: { text: () => string }) => b.text() === 'Show')!.trigger('click')
    await vi.waitFor(() => expect(vm.hasPlot).toBe(true))
    expect(asked.count).toBe(2)
    expect(document.body.textContent).not.toContain('Service Unavailable')
  })
})

describe('stripes Page chart after a Retry', { timeout: 15_000 }, () => {
  const station = { station_id: '1048', name: 'Berlin-Tempelhof', region: 'Berlin', latitude: 52.47, longitude: 13.4, start_timestamp: '1950-01-01', end_timestamp: '2020-01-01' }
  // the focus Retry held fell to the page's body once a Retry that worked took the note away
  const retry = () => [...document.body.querySelectorAll('button')].find(button => button.textContent?.trim() === 'Retry')

  let wrapper: Awaited<ReturnType<typeof mountSuspended>> | undefined
  afterEach(() => {
    vi.restoreAllMocks()
    wrapper?.unmount()
    wrapper = undefined
    useToast().clear()
    document.body.innerHTML = ''
  })

  // the stripes shown, their drawing failed, and Retry focused: what its press brings is up to the test
  async function retried() {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    echarts.chart.setOption.mockImplementation(() => {
      throw new Error('drawing failed')
    })
    registerEndpoint('/api/stripes/stations', () => ({ stations: [station] }))
    registerEndpoint('/api/stripes/values', () => ({ series: { station }, values: TWO_YEARS }))
    wrapper = await mountSuspended(defineComponent({
      setup: () => () => h(UApp, null, { default: () => h(StripesPage) }),
    }), { attachTo: document.body, route: '/stripes?kind=precipitation' })
    const vm = wrapper.findComponent(StripesPage).vm as any
    await vi.waitFor(() => expect(vm.stations).toHaveLength(1))
    vm.selectedStation = station
    await nextTick()
    await wrapper.findAll('button').find((b: { text: () => string }) => b.text() === 'Show')!.trigger('click')
    await vi.waitFor(() => expect(retry()).toBeDefined())
    const button = retry()!
    button.focus()
    return { vm, button, chart: () => wrapper!.findComponent(StripesChart).vm as any }
  }

  it('hands the focus on to the stripes once they are drawn', async () => {
    const { button } = await retried()
    echarts.chart.setOption.mockReset()
    button.click()
    await vi.waitFor(() => expect(retry()).toBeUndefined())
    await vi.waitFor(() => expect(document.activeElement).toBe(stage()))
    expect(stage().getAttribute('tabindex')).toBe('0')
  })

  it('leaves the focus where it was moved to meanwhile', async () => {
    const { vm, button } = await retried()
    const elsewhere = document.body.appendChild(document.createElement('button'))
    echarts.chart.setOption.mockReset()
    button.click()
    elsewhere.focus()

    await vi.waitFor(() => expect(vm.plotFailed).toBe(false))
    await nextTick()
    expect(retry()).toBeUndefined()
    expect(document.activeElement).toBe(elsewhere)
  })

  it('keeps the focus on Retry where the stripes fail again', async () => {
    const { button, chart } = await retried()
    const failures = chart().renderFailures
    button.click()
    await vi.waitFor(() => expect(chart().renderFailures).toBeGreaterThan(failures))
    await nextTick()
    expect(retry()).toBe(button)
    expect(document.activeElement).toBe(button)
  })
})

describe('stripes Page chart name', { timeout: 15_000 }, () => {
  const station = { station_id: '1048', name: 'Berlin-Tempelhof', region: 'Berlin', latitude: 52.47, longitude: 13.4, start_timestamp: '1950-01-01', end_timestamp: '2020-01-01' }

  let wrapper: Awaited<ReturnType<typeof mountSuspended>> | undefined
  afterEach(() => {
    wrapper?.unmount()
    wrapper = undefined
    useToast().clear()
    document.body.innerHTML = ''
  })

  it('names the stripes by their kind and station, as a figure', async () => {
    registerEndpoint('/api/stripes/stations', () => ({ stations: [station] }))
    registerEndpoint('/api/stripes/values', () => ({ series: { station }, values: [{ timestamp: '2020-01-01T00:00:00+00:00', value: 9.5 }] }))
    wrapper = await mountSuspended(defineComponent({
      setup: () => () => h(UApp, null, { default: () => h(StripesPage) }),
    }), { attachTo: document.body, route: '/stripes?kind=precipitation' })
    const vm = wrapper.findComponent(StripesPage).vm as any
    await vi.waitFor(() => expect(vm.stations).toHaveLength(1))
    vm.selectedStation = station
    await nextTick()
    echarts.chart.setOption.mockClear()
    await wrapper.findAll('button').find((b: { text: () => string }) => b.text() === 'Show')!.trigger('click')
    await vi.waitFor(() => expect(draws()).toBe(1))

    expect(stage().getAttribute('role')).toBe('figure')
    expect(stage().getAttribute('aria-label')).toBe('Climate stripes (Precipitation) for Berlin-Tempelhof, Germany (1048)')
  })
})

describe('stripes Page station span', () => {
  // as the backend sends a station's span since GH-2439
  const station = { station_id: '1048', name: 'Berlin-Tempelhof', region: 'Berlin', latitude: 52.47, longitude: 13.4, start_timestamp: '1950-01-01T00:00:00.000000+00:00', end_timestamp: '2020-12-31T00:00:00.000000+00:00' }

  let wrapper: Awaited<ReturnType<typeof mountSuspended>> | undefined
  let removeEndpoint: (() => void) | undefined
  afterEach(() => {
    wrapper?.unmount()
    wrapper = undefined
    // so that its station answers no later test
    removeEndpoint?.()
    removeEndpoint = undefined
  })

  it('shows the years a chosen station has records for', async () => {
    removeEndpoint = registerEndpoint('/api/stripes/stations', () => ({ stations: [station] }))
    wrapper = await mountSuspended(StripesPage, { attachTo: document.body, route: '/stripes?kind=precipitation' })
    const vm = wrapper.vm as any
    await vi.waitFor(() => expect(vm.stations).toHaveLength(1))
    // the station as the page fetched it
    vm.selectedStation = vm.stations[0]
    await nextTick()

    expect(wrapper.text().replace(/\s+/g, ' ')).toContain('Available: 1950 - 2020')
  })
})

describe('stripes Page text alternative', () => {
  const station = { station_id: '1048', name: 'Berlin-Tempelhof', region: 'Berlin', latitude: 52.47, longitude: 13.4, start_timestamp: '1950-01-01', end_timestamp: '2020-01-01' }

  let wrapper: Awaited<ReturnType<typeof mountSuspended>> | undefined
  afterEach(() => {
    wrapper?.unmount()
    wrapper = undefined
    document.body.innerHTML = ''
  })

  // the stripes drawn for a station, as the backend answers them: a year without a value among them
  async function showStripes(route = '/stripes?kind=temperature') {
    // the station lists the earlier tests fetched are kept by their request, which this one is too
    clearNuxtData()
    registerEndpoint('/api/stripes/stations', () => ({ stations: [station] }))
    registerEndpoint('/api/stripes/values', () => ({
      metadata: {},
      series: { station, resolution: 'annual', dataset: 'climate_summary', parameter: 'temperature_air_mean_2m', unit: 'degree_celsius' },
      values: [
        { timestamp: '2018-01-01T00:00:00+00:00', value: 8 },
        { timestamp: '2019-01-01T00:00:00+00:00', value: 9.25 },
        { timestamp: '2020-01-01T00:00:00+00:00', value: null },
        { timestamp: '2021-01-01T00:00:00+00:00', value: 10 },
      ],
    }))
    wrapper = await mountSuspended(StripesPage, { attachTo: document.body, route })
    const vm = wrapper.vm as any
    await vi.waitFor(() => expect(vm.stations).toHaveLength(1))
    vm.selectedStation = station
    await nextTick()
    echarts.chart.setOption.mockClear()
    await wrapper.findAll('button').find((b: { text: () => string }) => b.text() === 'Show')!.trigger('click')
    await vi.waitFor(() => expect(draws()).toBeGreaterThan(0))
    await vi.waitFor(() => expect(document.body.querySelector('[role="figure"]')?.getAttribute('aria-describedby')).toBeTruthy())
  }

  const figure = () => document.body.querySelector('[role="figure"]')!
  const toggle = () => [...document.body.querySelectorAll('button')].find(button => button.textContent?.trim() === 'Show as table')

  it('describes the figure by what the stripes show, in words a screen reader reads', async () => {
    await showStripes()
    const description = document.getElementById(figure().getAttribute('aria-describedby')!.split(' ')[0]!)
    expect(description?.textContent?.trim()).toBe(
      'From 2018 to 2021. Lowest value 8.00 °C in 2018, highest value 10.00 °C in 2021. The values are in the table below the chart.',
    )
  })

  it('offers every year as a table behind a button that says whether it is open, and shows none before', async () => {
    await showStripes()
    expect(document.body.querySelector('table')).toBeNull()
    expect(toggle()?.getAttribute('aria-expanded')).toBe('false')

    toggle()!.click()
    await vi.waitFor(() => expect(document.body.querySelector('table')).not.toBeNull())
    expect(toggle()?.getAttribute('aria-expanded')).toBe('true')
    // a reader finds the controlled part by id
    expect(document.getElementById(toggle()!.getAttribute('aria-controls')!)).not.toBeNull()

    const table = document.body.querySelector('table')!
    expect([...table.querySelectorAll('thead th')].map(th => [th.textContent?.trim(), th.getAttribute('scope')])).toEqual([
      ['Year', 'col'],
      ['Value (°C)', 'col'],
      ['Class', 'col'],
    ])
    // the year with no value is not drawn, so it is not listed; each year is the header of its row
    const rows = [...table.querySelectorAll('tbody tr')].map(row => [...row.children].map(cell => `${cell.tagName.toLowerCase()}:${cell.textContent?.trim()}`))
    expect(rows).toEqual([
      ['th:2018', 'td:8.00', 'td:Much cooler'],
      ['th:2019', 'td:9.25', 'td:Warmer'],
      ['th:2021', 'td:10.00', 'td:Much warmer'],
    ])
    expect(table.querySelector('caption')?.textContent?.trim()).toBe(figure().getAttribute('aria-label'))
  })

  it('puts the scrolling table in a region the keyboard reaches, and says what a class is', async () => {
    await showStripes()
    toggle()!.click()
    await vi.waitFor(() => expect(document.body.querySelector('table')).not.toBeNull())
    const region = document.body.querySelector('[role="region"]')!
    expect(region.getAttribute('tabindex')).toBe('0')
    expect(region.getAttribute('aria-label')).toBe(figure().getAttribute('aria-label'))
    expect(region.contains(document.body.querySelector('table'))).toBe(true)
    expect(document.body.textContent).toContain('Class: where the year lies between the coolest and the warmest year shown')
  })

  it('names the classes of a precipitation series by wet and dry', async () => {
    await showStripes('/stripes?kind=precipitation')
    toggle()!.click()
    await vi.waitFor(() => expect(document.body.querySelector('table')).not.toBeNull())
    expect([...document.body.querySelectorAll('tbody tr')].map(row => row.lastElementChild?.textContent?.trim())).toEqual(['Much drier', 'Wetter', 'Much wetter'])
  })

  it('has no table and no description once the stripes are cleared', async () => {
    await showStripes()
    wrapper!.findAll('button').find((b: { text: () => string }) => b.text() === 'Reset')!.trigger('click')
    await vi.waitFor(() => expect(toggle()).toBeUndefined())
    // the card goes with them, and the placeholder takes its place (GH-3850)
    await vi.waitFor(() => expect(document.querySelector('[data-testid="tool-placeholder"]')).not.toBeNull())
    expect(document.querySelector('[role="figure"]')).toBeNull()
  })
})

describe('stripes Page chart in the language of the page, and disposed of at its end', () => {
  const station = { station_id: '1048', name: 'Berlin-Tempelhof', region: 'Berlin', latitude: 52.47, longitude: 13.4, start_timestamp: '1950-01-01', end_timestamp: '2020-01-01' }

  let wrapper: Awaited<ReturnType<typeof mountSuspended>> | undefined
  let harness: Awaited<ReturnType<typeof mountSuspended>> | undefined
  afterEach(async () => {
    wrapper?.unmount()
    wrapper = undefined
    await (harness?.vm as any)?.setLocale('en')
    harness?.unmount()
    harness = undefined
  })

  async function setLocale(language: string) {
    harness = await mountSuspended(defineComponent({
      setup: () => ({ setLocale: useI18n().setLocale }),
      render: () => h('div'),
    }))
    await (harness.vm as any).setLocale(language)
  }

  // what Show does, whatever language its button is written in
  async function showStripes(query = 'kind=temperature') {
    registerEndpoint('/api/stripes/stations', () => ({ stations: [station] }))
    registerEndpoint('/api/stripes/values', () => ({ series: { station }, values: TWO_YEARS }))
    wrapper = await mountSuspended(StripesPage, { attachTo: document.body, route: `/stripes?${query}` })
    const vm = wrapper.vm as any
    await vi.waitFor(() => expect(vm.stations).toHaveLength(1))
    vm.selectedStation = station
    await nextTick()
    echarts.chart.setOption.mockClear()
    await vm.fetchAndPlotStripes()
    await vi.waitFor(() => expect(draws()).toBeGreaterThan(0))
  }

  // the title is the page's own text, and the source and the availability label are the chart's, in the language of the page
  it.each([
    ['en', en],
    ['de', de],
    ['de-hh', deHh],
    ['lb', lb],
  ] as const)('writes the chart in the language of %s', async (code, messages) => {
    await setLocale(code)
    await showStripes('kind=temperature&show_data_availability=true')
    const texts = textsOf(drawnOption())
    expect(texts).toContain(messages.stripes.plotSource)
    expect(texts).toContain(messages.stripes.plotDataAvailability)
    // the buttons of the toolbar are named in it as well
    expect(zoomButton(messages.stripes.chart.zoomIn)).not.toBeNull()
    expect(zoomButton(messages.stripes.chart.savePng)).not.toBeNull()
  })

  it('draws the stripes again, with the buttons of the language it is switched to', async () => {
    await showStripes()
    expect(zoomButton('Zoom in')).not.toBeNull()
    await setLocale('fr')
    await vi.waitFor(() => expect(zoomButton(fr.stripes.chart.zoomIn)).not.toBeNull())
    expect(textsOf(drawnOption())).toContain(fr.stripes.plotSource)
  })

  // the label of the line of years with data is gold, which on white is 2.2:1 (GH-3618)
  it('writes the availability label in the gold that reads on the paper', async () => {
    await showStripes('kind=temperature&show_data_availability=true')
    const chart = echarts.state.realInit!(null, null, { renderer: 'svg', ssr: true, width: 800, height: 600 })
    chart.setOption(drawnOption())
    const svg = chart.renderToSVGString() as string
    chart.dispose()
    expect(svg).toMatch(new RegExp(`fill="${SERIES_LABEL.gold.light}">Data availability<`))
  })

  it('disposes the chart where the page goes', async () => {
    await showStripes()
    echarts.chart.dispose.mockClear()
    wrapper!.unmount()
    wrapper = undefined
    expect(echarts.chart.dispose).toHaveBeenCalled()
  })

  // the image that is saved is in the language of the page, as the chart is
  it('draws the copy of the saved stripes in the language of the page', async () => {
    await setLocale('de')
    await showStripes()
    const vm = wrapper!.vm as any
    image.svgToBlob.mockClear()
    await vm.downloadStripes('png')
    expect((image.svgToBlob.mock.calls[0] as unknown as [string])[0]).toContain(de.stripes.plotSource)
  })

  it('disposes nothing where no stripes were drawn', async () => {
    registerEndpoint('/api/stripes/stations', () => ({ stations: [station] }))
    wrapper = await mountSuspended(StripesPage, { attachTo: document.body })
    echarts.chart.dispose.mockClear()
    wrapper.unmount()
    wrapper = undefined
    expect(echarts.chart.dispose).not.toHaveBeenCalled()
  })
})
