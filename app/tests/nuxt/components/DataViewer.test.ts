import type { DataSettings } from '~/types/data-settings.type'
import type { ParameterSelection } from '~/types/parameter-selection-state.type'
import type { StationSelectionState } from '~/types/station-selection-state.type'
import { mockNuxtImport, mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { getQuery, setResponseStatus } from 'h3'
import { afterAll, afterEach, beforeAll, describe, expect, it, onTestFinished, vi } from 'vitest'
import { defineComponent, h, ref } from 'vue'
import { clearNuxtData } from '#app'
import { UApp, USelectMenu } from '#components'
import { useToast } from '#imports'
import DataViewer from '~/components/DataViewer.vue'
import QueryPanel from '~/components/QueryPanel.vue'
import { SETTINGS_DEFAULTS } from '~/composables/useSettings'
import { seriesColour } from '~/utils/explorer-model'
import { providersAnswer } from '../fixtures/providers'

// DuckDB, as far as Run Query reaches it: the query itself is answered by the test's `answer`, as the
// Arrow table DuckDB gives, every statement loading the table at once. It gives no result schema,
// which the check of an edited query reads
const duckdb = vi.hoisted(() => ({ answer: async (_sql: string): Promise<Record<string, unknown>[]> => [] }))
vi.mock('@duckdb/duckdb-wasm', () => ({
  getPlatformFeatures: async () => ({ wasmExceptions: true }),
  ConsoleLogger: class {},
  AsyncDuckDB: class {
    async instantiate() {}
    async terminate() {}
    async connect() {
      const query = async (sql: string) => {
        const rows = /^(?:DROP|CREATE|INSERT) /.test(sql) ? [] : await duckdb.answer(sql)
        const { Table, tableFromJSON } = await import('apache-arrow')
        return rows.length > 0 ? tableFromJSON(rows) : new Table()
      }
      return {
        close: async () => {},
        query,
        // the run's query, read as the batches of the table it answers
        send: async (sql: string) => (await query(sql)).batches,
        cancelSent: async () => false,
      }
    }
  },
}))

// ECharts draws nothing in the test's document: each chart the page shows is a recorder of the options it is given, and
// has the element it was handed. A chart with no element to draw into (the copy a saved image is made of) is the real
// library, drawing to an SVG string.
const echarts = vi.hoisted(() => {
  const instances: { el: HTMLElement, setOption: ReturnType<typeof vi.fn>, dispose: ReturnType<typeof vi.fn> }[] = []
  // every setOption of every chart, in the order they were made
  const log: { instance: (typeof instances)[number], option: any, flags: any }[] = []
  const state = { realInit: null as null | ((...args: any[]) => any) }
  const init = vi.fn((element: HTMLElement | null, ...rest: unknown[]) => {
    if (element === null)
      return state.realInit!(null, ...rest)
    const instance: (typeof instances)[number] & Record<string, unknown> = {
      el: element,
      setOption: vi.fn((option: unknown, flags: unknown) => {
        log.push({ instance, option, flags })
      }),
      dispose: vi.fn(),
      on: vi.fn(),
      resize: vi.fn(),
      getDom: () => element,
    }
    instances.push(instance)
    return instance
  })
  return { init, instances, log, state }
})
// The library is the real one but for `init`, which gives the page's charts the recorder above: the chart code module is
// loaded once, and every chart that asks for it has the same. The copy a saved image is made of has no element: that is the
// real `init`, drawing to an SVG string.
vi.mock('echarts/core', async (importOriginal) => {
  const original = await importOriginal<typeof import('echarts/core')>()
  echarts.state.realInit = (element: null, theme: unknown, options: unknown) => original.init(element as any, theme as any, options as any)
  return { ...original, init: echarts.init }
})

// The saved image: its rasterising needs a canvas, which the test's document has not. A vector is the SVG itself, as it is;
// the files and the names they are handed to the browser by are recorded.
const image = vi.hoisted(() => ({
  options: [] as Record<string, any>[],
  downloads: [] as { blob: Blob, filename: string }[],
  fail: null as Error | null,
}))
vi.mock('~/utils/chart-image', () => ({
  svgToBlob: async (svg: string, options: Record<string, any>) => {
    if (image.fail) {
      const error = image.fail
      image.fail = null
      throw error
    }
    image.options.push({ ...options, svg })
    return options.format === 'svg' ? new Blob([svg], { type: 'image/svg+xml' }) : new Blob(['png'], { type: `image/${options.format}` })
  },
  downloadBlob: (blob: Blob, filename: string) => {
    image.downloads.push({ blob, filename })
  },
}))

// every drawing (a `notMerge` setOption) of every chart of the page, in the order they were made, and the figure each is in
function drawings() {
  return echarts.log
    .filter(({ flags }) => flags?.notMerge)
    .map(({ instance, option }) => ({ instance, option: option as any, figure: instance.el.closest('[role="figure"]')?.getAttribute('aria-label') ?? '' }))
}
// the lines of a drawing: the series, the zero line and the legend are not
const linesOf = (option: any): any[] => option.series.filter((series: any) => series.type === 'line' && series.id !== 'zero')
const lastDrawn = () => drawings().at(-1)!
// the newest drawing of each chart, by its figure's name: "Chart of A" is A's, as there is no axis title to name a facet by
const facetsDrawn = () => new Map(drawings().map(({ figure, option }) => [figure.replace(/^Chart of /, ''), option]))
function forgetDrawings() {
  echarts.log.length = 0
}
// whether the page is dark, which the series' colours are of
const isDark = () => document.documentElement.classList.contains('dark')

// The date reader as it is, counted: the chart reads one date for every row it plots
const { timestampDates } = vi.hoisted(() => ({ timestampDates: { calls: 0 } }))
vi.mock('~/utils/timestamp', async (importOriginal) => {
  const original = await importOriginal<typeof import('~/utils/timestamp')>()
  return {
    ...original,
    timestampDate: (text: string) => {
      timestampDates.calls++
      return original.timestampDate(text)
    },
  }
})

// Nuxt's reload of the page, for every test in the file: the test's document, whose address earlier
// tests' downloads have moved, does not take it
const { reloadNuxtApp } = vi.hoisted(() => ({ reloadNuxtApp: vi.fn() }))
mockNuxtImport('reloadNuxtApp', () => reloadNuxtApp)

const settings: DataSettings = {
  shape: 'long',
  skipEmpty: false,
  skipThreshold: 0.95,
  skipCriteria: 'min',
  dropNulls: true,
  useNearbyStationDistance: 1,
  stationDistanceHomogeneous: 40,
  stationDistanceHeterogeneous: 20,
  useStationDistancePerParameter: {},
  minGainOfValuePairs: 0.1,
  numAdditionalStations: 3,
}

// how the English glossary names the parameters these tests plot
const airTemperature = 'Mean air temperature (2 m)'
const precipitationAmount = 'Precipitation amount'

const parameterSelection: ParameterSelection = {
  provider: 'dwd',
  network: 'observation',
  resolution: 'daily',
  dataset: 'climate_summary',
  parameters: ['temperature_air_mean_2m'],
}

type Station = StationSelectionState['selection']['stations'][number]

function byStation(stationId: string): StationSelectionState {
  return {
    mode: 'station',
    selection: { stations: [{ station_id: stationId, name: stationId } as Station] },
    interpolation: { source: 'manual' },
    dateRange: {},
  }
}

const row = {
  station_id: '01048',
  resolution: 'daily',
  dataset: 'climate_summary',
  parameter: 'temperature_air_mean_2m',
  timestamp: '2020-01-01T00:00:00Z',
  value: 1.5,
  quality_flags: null,
}

// DataViewer's copy buttons use UTooltip, which needs the TooltipProvider app.vue's <UApp> supplies;
// attached, so the download menu can open into the document
// each test's viewers, unmounted after it, so none of them outlives it into the next
const mounted: { unmount: () => void }[] = []

async function mountDataViewer(stationSelection = ref(byStation('01048'))) {
  const wrapper = await mountSuspended(defineComponent({
    setup: () => () => h(UApp, null, {
      default: () => h(DataViewer, { parameterSelection, stationSelection: stationSelection.value, settings }),
    }),
  }), { attachTo: document.body })
  mounted.push(wrapper)
  const viewer = wrapper.findComponent(DataViewer)
  return { wrapper, viewer, stationSelection }
}

// the download menu's items as it offers them: opened the way a keyboard opens it
async function openDownloads(wrapper: Awaited<ReturnType<typeof mountDataViewer>>['wrapper']) {
  // a menu an item was just chosen from closes first; it opens again only once it has
  await vi.waitFor(() => expect(document.body.querySelectorAll('[role="menuitem"]')).toHaveLength(0))
  await wrapper.find('button[aria-haspopup="menu"]').trigger('keydown', { key: 'Enter' })
  await vi.waitFor(() => expect(document.body.querySelectorAll('[role="menuitem"]')).toHaveLength(3))
  return [...document.body.querySelectorAll<HTMLElement>('[role="menuitem"]')]
}

function fetchData(viewer: Awaited<ReturnType<typeof mountDataViewer>>['viewer']) {
  return (viewer.vm as unknown as { fetchData: () => Promise<void> }).fetchData()
}

function offered(items: HTMLElement[]) {
  return items.map(item => [item.textContent?.trim(), !item.hasAttribute('data-disabled')])
}

// the content of the file a download saves, caught where it is handed to the browser
function catchDownload() {
  const saved: Blob[] = []
  vi.spyOn(URL, 'createObjectURL').mockImplementation((blob) => {
    saved.push(blob as Blob)
    // happy-dom follows the clicked link, so this becomes `window.location`; Nuxt 4.6's prefetch
    // scheduler resolves the route against it, which a `blob:` URL cannot be a base for
    return 'http://localhost:3000/download'
  })
  vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {})
  return saved
}

// A hold on the mocked endpoint, opened by the test at the point where the order of two answers
// matters, rather than a delay a slow runner can outlast
function gate() {
  let open!: () => void
  const opened = new Promise<void>((resolve) => {
    open = resolve
  })
  return { opened, open }
}

// The reasons requests are aborted with. The mocked endpoint heeds no signal, so a test sees an abort
// here rather than by its answer going missing
function abortsSeen() {
  const reasons: unknown[] = []
  const abort = AbortController.prototype.abort
  vi.spyOn(AbortController.prototype, 'abort').mockImplementation(function (this: AbortController, reason?: unknown) {
    reasons.push(reason)
    abort.call(this, reason)
  })
  return reasons
}

const clipboard = Object.getOwnPropertyDescriptor(navigator, 'clipboard')

afterEach(() => {
  for (const wrapper of mounted.splice(0))
    wrapper.unmount()
  // the clipboard is a getter on Navigator's prototype, not the navigator's own: a test's own is removed
  if (clipboard)
    Object.defineProperty(navigator, 'clipboard', clipboard)
  else
    delete (navigator as { clipboard?: unknown }).clipboard
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
  // a test's own answer, which would answer the next test's queries
  duckdb.answer = async () => []
  // toasts are the app's, not a viewer's: one left over would be shown, and found, in the next test
  useToast().clear()
  // the charts of a test and the files it saved are not the next test's
  echarts.instances.length = 0
  echarts.log.length = 0
  echarts.init.mockClear()
  image.options.length = 0
  image.downloads.length = 0
  image.fail = null
  document.body.innerHTML = ''
})

describe('dataViewer downloads', () => {
  it('offers nothing to download while the table is empty', async () => {
    const { wrapper } = await mountDataViewer()
    expect(offered(await openDownloads(wrapper))).toEqual([['CSV', false], ['JSON', false], ['GeoJSON', false]])
  })

  it('offers every format once the table shows rows', async () => {
    registerEndpoint('/api/values', () => ({ values: [row] }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    expect(offered(await openDownloads(wrapper))).toEqual([['CSV', true], ['JSON', true], ['GeoJSON', true]])
  })

  it('saves the rows the table shows as CSV, without asking the backend again', async () => {
    // counted at the endpoint, which a request reaches however it is made; a spy on fetch misses
    // $fetch, which holds the fetch it was built with
    let asked = 0
    registerEndpoint('/api/values', () => {
      asked++
      return { values: [row] }
    })
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    expect(asked).toBe(1)
    const saved = catchDownload()
    const [csv] = await openDownloads(wrapper)
    csv!.click()
    await vi.waitFor(() => expect(saved).toHaveLength(1))
    expect(asked).toBe(1)
    const text = await saved[0]!.text()
    // every column the rows carry, those the column picker hides by default included, after the comment lines of the credit (GH-4255)
    const lines = text.split('\n').filter(line => !line.startsWith('#'))
    expect(lines[0]).toBe('station_id,resolution,dataset,parameter,timestamp,value,quality_flags')
    expect(lines[1]).toContain('01048')
    expect(lines[1]).toContain('1.5')
  })

  it.each(['CSV', 'JSON'])('saves no %s of a table Clear emptied after the menu was opened', async (format) => {
    registerEndpoint('/api/values', () => ({ values: [row] }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    const saved = catchDownload()
    const items = await openDownloads(wrapper)
    // chosen before the menu has updated, as from the explorer sidebar
    ;(viewer.vm as unknown as { clearData: () => void }).clearData()
    items[format === 'CSV' ? 0 : 1]!.click()
    await vi.waitFor(() => expect(document.body.querySelectorAll('[role="menuitem"]')).toHaveLength(0))
    await wrapper.vm.$nextTick()
    expect(saved).toHaveLength(0)
    expect(document.body.textContent).not.toContain('Values downloaded')
  })

  it('asks for no GeoJSON of a table the query panel rewrote after the menu was opened', async () => {
    let asked = false
    registerEndpoint('/api/values', (event) => {
      if (getQuery(event).format === 'geojson') {
        asked = true
        return { type: 'FeatureCollection', features: [] }
      }
      return { values: [row] }
    })
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    const saved = catchDownload()
    const items = await openDownloads(wrapper)
    // the query's rows come in before the menu has updated
    wrapper.findComponent(QueryPanel).vm.$emit('dataTransformed', [{ timestamp: '2020-01-01', parameter: 'temperature_air_mean_2m', avg_value: 1.5 }])
    items[2]!.click()
    await vi.waitFor(() => expect(document.body.querySelectorAll('[role="menuitem"]')).toHaveLength(0))
    await flushPromises()
    expect(asked).toBe(false)
    expect(saved).toHaveLength(0)
  })

  it('saves every column a wide-shaped table carries, not only the columns it shows', async () => {
    // one column per parameter: the table's fixed columns hold none of them
    registerEndpoint('/api/values', () => ({ values: [{ station_id: '01048', dataset: 'climate_summary', timestamp: '2020-01-01T00:00:00Z', temperature_air_mean_2m: 1.5 }] }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    const saved = catchDownload()
    const [csv] = await openDownloads(wrapper)
    csv!.click()
    await vi.waitFor(() => expect(saved).toHaveLength(1))
    const [header, line] = (await saved[0]!.text()).split('\n').filter(each => !each.startsWith('#'))
    expect(header).toContain('temperature_air_mean_2m')
    expect(line).toContain('1.5')
  })

  // the credit and the note of the rows, on the page and in the files (GH-4255)
  const NOTE = 'Processed by wetterdienst: the provider\'s data was reshaped into a uniform table, and its units converted where they differ.'
  const CC_BY_NAME = 'Creative Commons Attribution 4.0 International'
  const CC_BY_URL = 'https://creativecommons.org/licenses/by/4.0/'

  it('writes the provider\'s credit, its licence and the note as comment lines before the CSV\'s header', async () => {
    registerEndpoint('/api/providers', () => providersAnswer())
    registerEndpoint('/api/values', () => ({ values: [row] }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    await vi.waitFor(() => expect(wrapper.find('[data-testid="explorer-credit"]').text()).toContain('Source: Deutscher Wetterdienst'))
    const saved = catchDownload()
    const [csv] = await openDownloads(wrapper)
    csv!.click()
    await vi.waitFor(() => expect(saved).toHaveLength(1))
    const lines = (await saved[0]!.text()).split('\n')
    expect(lines.slice(0, 3)).toEqual([
      '# Source: Deutscher Wetterdienst',
      `# Licence: ${CC_BY_NAME} (${CC_BY_URL})`,
      `# ${NOTE}`,
    ])
    expect(lines[3]).toBe('station_id,resolution,dataset,parameter,timestamp,value,quality_flags')
    expect(lines).toHaveLength(5)
  })

  it('writes no provider block into the JSON where the list of providers did not come, and keeps the note', async () => {
    // an unknown is not "the provider states no terms", which is what `license: null` says
    clearNuxtData('providers')
    onTestFinished(() => clearNuxtData('providers'))
    registerEndpoint('/api/providers', (event) => {
      setResponseStatus(event, 404)
      return { type: 'urn:wetterdienst:problem:not-found', title: 'Not Found', status: 404, detail: 'Not Found' }
    })
    registerEndpoint('/api/values', () => ({ values: [row] }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    const saved = catchDownload()
    const items = await openDownloads(wrapper)
    items[1]!.click()
    await vi.waitFor(() => expect(saved).toHaveLength(1))
    const json = JSON.parse(await saved[0]!.text())
    expect(json.metadata).toEqual({ processing_note: NOTE })
    expect(json.values).toEqual([row])
    // and the CSV has the note alone
    const csv = catchDownload()
    ;(await openDownloads(wrapper))[0]!.click()
    await vi.waitFor(() => expect(csv).toHaveLength(1))
    expect((await csv[0]!.text()).split('\n').filter(line => line.startsWith('#'))).toEqual([`# ${NOTE}`])
  })

  it('writes the credit as a metadata member of the JSON, and leaves its values as they were', async () => {
    registerEndpoint('/api/providers', () => providersAnswer())
    registerEndpoint('/api/values', () => ({ values: [row] }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    await vi.waitFor(() => expect(wrapper.find('[data-testid="explorer-credit"]').text()).toContain('Source: Deutscher Wetterdienst'))
    const saved = catchDownload()
    const items = await openDownloads(wrapper)
    items[1]!.click()
    await vi.waitFor(() => expect(saved).toHaveLength(1))
    const json = JSON.parse(await saved[0]!.text())
    expect(json.metadata).toEqual({
      provider: { attribution: 'Source: Deutscher Wetterdienst', license: { name: CC_BY_NAME, url: CC_BY_URL } },
      processing_note: NOTE,
    })
    expect(json.values).toEqual([row])
  })

  it('says under the table whose data it is, and the note directly under the credit line', async () => {
    registerEndpoint('/api/providers', () => providersAnswer())
    registerEndpoint('/api/values', () => ({ values: [row] }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    await vi.waitFor(() => expect(wrapper.find('[data-testid="explorer-credit"]').text()).toContain('Source: Deutscher Wetterdienst'))
    const credit = wrapper.find('[data-testid="explorer-credit"]')
    expect(credit.find('[data-testid="provider-credit-licence"]').attributes('href')).toBe(CC_BY_URL)
    expect(credit.find('[data-testid="processing-note"]').text()).toBe(NOTE)
    expect(credit.find('[data-testid="processing-note"]').element.previousElementSibling).toBe(credit.find('[data-testid="provider-credit-line"]').element)
    // and in the chart's view, which is of the same rows
    await wrapper.find('button[aria-label="Show as chart"]').trigger('click')
    await vi.waitFor(() => expect(wrapper.find('[role="figure"]').exists()).toBe(true))
    expect(wrapper.find('[data-testid="explorer-credit"]').text()).toContain('Source: Deutscher Wetterdienst')
  })

  it.each([
    ['interpolation', '/api/interpolate'],
    ['summary', '/api/summarize'],
  ] as const)('says of the rows of a %s that they were calculated, on the page and in the files', async (mode, endpoint) => {
    registerEndpoint('/api/providers', () => providersAnswer())
    registerEndpoint(endpoint, () => ({ values: [{ ...row, taken_station_ids: ['01048', '04411'] }] }))
    const { wrapper, viewer } = await mountDataViewer(ref(atPoint(mode)))
    await fetchData(viewer)
    await vi.waitFor(() => expect(wrapper.find('[data-testid="explorer-credit"]').text()).toContain('Source: Deutscher Wetterdienst'))
    expect(wrapper.find('[data-testid="explorer-credit"] [data-testid="processing-note"]').text()).toBe(`${NOTE} The values were selected or calculated from the provider's readings.`)
    const saved = catchDownload()
    const items = await openDownloads(wrapper)
    items[0]!.click()
    await vi.waitFor(() => expect(saved).toHaveLength(1))
    expect((await saved[0]!.text()).split('\n')[2]).toBe(`# ${NOTE} The values were selected or calculated from the provider's readings.`)
  })

  it('copies rows to the clipboard without the comment lines', async () => {
    registerEndpoint('/api/providers', () => providersAnswer())
    registerEndpoint('/api/values', () => ({ values: [row] }))
    const written: string[] = []
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: async (text: string) => void written.push(text) } })
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    await wrapper.find('button[aria-label="Copy all values"]').trigger('click')
    await vi.waitFor(() => expect(written).toHaveLength(1))
    expect(written[0]).not.toContain('#')
    // the columns the table shows, a header first
    expect(written[0]!.split('\n')[0]).toMatch(/^station_id,/)
  })

  it('asks for GeoJSON with the request that filled the table, not the selection made since', async () => {
    // a download answered for the current selection: another station's data under the table's
    const asked: Record<string, unknown>[] = []
    registerEndpoint('/api/values', (event) => {
      const query = getQuery(event)
      if (query.format === 'geojson') {
        asked.push(query)
        return { type: 'FeatureCollection', features: [] }
      }
      return { values: [row] }
    })
    const { wrapper, viewer, stationSelection } = await mountDataViewer()
    await fetchData(viewer)
    stationSelection.value = byStation('04411')
    await wrapper.vm.$nextTick()
    const saved = catchDownload()
    const items = await openDownloads(wrapper)
    items[2]!.click()
    await vi.waitFor(() => expect(saved).toHaveLength(1))
    expect(asked).toHaveLength(1)
    expect(asked[0]!.stations).toBe('01048')
    // the units the table was fetched in, which the old download left out
    expect(asked[0]!.humanize).toBe('true')
  })

  it('downloads GeoJSON for the table shown while a newer Fetch is still under way', async () => {
    // the request Fetch sent became the table's at once: a download in that gap asked for the new one
    const asked: Record<string, unknown>[] = []
    const newerHold = gate()
    registerEndpoint('/api/values', async (event) => {
      const query = getQuery(event)
      if (query.format === 'geojson') {
        asked.push(query)
        return { type: 'FeatureCollection', features: [] }
      }
      if (query.stations === '04411')
        await newerHold.opened
      return { values: [{ ...row, station_id: String(query.stations) }] }
    })
    const { wrapper, viewer, stationSelection } = await mountDataViewer()
    await fetchData(viewer)
    const saved = catchDownload()
    // the menu is open when the newer Fetch is pressed, as from the sidebar
    const items = await openDownloads(wrapper)
    stationSelection.value = byStation('04411')
    await wrapper.vm.$nextTick()
    const newer = fetchData(viewer)
    items[2]!.click()
    // the newer Fetch answers only once the GeoJSON is saved
    await vi.waitFor(() => expect(saved).toHaveLength(1))
    expect(asked[0]!.stations).toBe('01048')
    newerHold.open()
    await newer
  })

  it('aborts a GeoJSON download chosen while a newer Fetch is under way, once that Fetch\'s answer replaces the table', async () => {
    // it was aborted only when Fetch was pressed, so one chosen after that was saved for a table gone
    let asked = false
    const geojsonHold = gate()
    registerEndpoint('/api/values', async (event) => {
      const query = getQuery(event)
      if (query.format === 'geojson') {
        asked = true
        await geojsonHold.opened
        return { type: 'FeatureCollection', features: [] }
      }
      return { values: [{ ...row, station_id: String(query.stations) }] }
    })
    const { wrapper, viewer, stationSelection } = await mountDataViewer()
    await fetchData(viewer)
    const saved = catchDownload()
    const aborts = abortsSeen()
    const items = await openDownloads(wrapper)
    stationSelection.value = byStation('04411')
    await wrapper.vm.$nextTick()
    const newer = fetchData(viewer)
    items[2]!.click()
    await vi.waitFor(() => expect(asked).toBe(true))
    expect(aborts).not.toContain('table-changed')
    // the newer Fetch answers while the GeoJSON is held, which aborts it there and then
    await newer
    expect(aborts).toContain('table-changed')
    geojsonHold.open()
    await vi.waitFor(() => expect(document.body.textContent).toContain('Download cancelled: the table changed'))
    expect(saved).toHaveLength(0)
  })

  it('answers for the fetch started last where it overtakes one still under way', async () => {
    // useFetch cancels the first (dedupe: 'cancel'); the table and GeoJSON follow the second, and the
    // first, answering after it, reaches neither
    const asked: Record<string, unknown>[] = []
    const firstHold = gate()
    registerEndpoint('/api/values', async (event) => {
      const query = getQuery(event)
      if (query.format === 'geojson') {
        asked.push(query)
        return { type: 'FeatureCollection', features: [] }
      }
      if (query.stations === '01048')
        await firstHold.opened
      return { values: [{ ...row, station_id: String(query.stations) }] }
    })
    const { wrapper, viewer, stationSelection } = await mountDataViewer()
    const first = fetchData(viewer)
    stationSelection.value = byStation('04411')
    await wrapper.vm.$nextTick()
    await fetchData(viewer)
    firstHold.open()
    await first
    expect(wrapper.text()).toContain('04411')
    const saved = catchDownload()
    const items = await openDownloads(wrapper)
    items[2]!.click()
    await vi.waitFor(() => expect(saved).toHaveLength(1))
    expect(asked[0]!.stations).toBe('04411')
  })

  it('keeps a cleared table empty when a fetch under way answers', async () => {
    // the answer is to a request the table no longer follows once it is cleared
    let answered = false
    const hold = gate()
    registerEndpoint('/api/values', async () => {
      await hold.opened
      answered = true
      return { values: [row] }
    })
    const { wrapper, viewer } = await mountDataViewer()
    const fetching = fetchData(viewer)
    ;(viewer.vm as unknown as { clearData: () => void }).clearData()
    hold.open()
    await fetching
    await vi.waitFor(() => expect(answered).toBe(true))
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).not.toContain('1.5')
    expect(offered(await openDownloads(wrapper))).toEqual([['CSV', false], ['JSON', false], ['GeoJSON', false]])
  })

  it('downloads GeoJSON for the station the table shows when the selection moved during the fetch', async () => {
    // the table showed one answer while GeoJSON asked for another
    const asked: Record<string, unknown>[] = []
    const hold = gate()
    registerEndpoint('/api/values', async (event) => {
      const query = getQuery(event)
      if (query.format === 'geojson') {
        asked.push(query)
        return { type: 'FeatureCollection', features: [] }
      }
      await hold.opened
      return { values: [{ ...row, station_id: String(query.stations) }] }
    })
    const { wrapper, viewer, stationSelection } = await mountDataViewer()
    const fetching = fetchData(viewer)
    stationSelection.value = byStation('04411')
    await wrapper.vm.$nextTick()
    // the fetch answers only once the selection has moved
    hold.open()
    await fetching
    await wrapper.vm.$nextTick()
    // the table shows the station the fetch was made for, and GeoJSON asks for that one
    expect(wrapper.text()).toContain('01048')
    const saved = catchDownload()
    const items = await openDownloads(wrapper)
    items[2]!.click()
    await vi.waitFor(() => expect(saved).toHaveLength(1))
    expect(asked[0]!.stations).toBe('01048')
  })

  it('copies the columns the picker shows, where a download writes them all', async () => {
    registerEndpoint('/api/values', () => ({ values: [row] }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    const copied: string[] = []
    Object.defineProperty(navigator, 'clipboard', { value: { writeText: async (text: string) => void copied.push(text) }, configurable: true })
    // "copy all", the second of the two buttons beside the table's tooltip triggers
    await wrapper.findAll('button[data-grace-area-trigger]')[1]!.trigger('click')
    await vi.waitFor(() => expect(copied).toHaveLength(1))
    // the picker's defaults: resolution and dataset hidden
    expect(copied[0]!.split('\n')[0]).toBe('station_id,parameter,timestamp,value,quality_flags')
  })

  it('writes a single value and a single copied row in the singular', async () => {
    // "1 values" and "1 rows copied to clipboard" before the counts had plural forms (GH-2968)
    registerEndpoint('/api/values', () => ({ values: [row] }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    expect(wrapper.text()).toMatch(/1 value(?!s)/)
    Object.defineProperty(navigator, 'clipboard', { value: { writeText: async () => {} }, configurable: true })
    await wrapper.findAll('button[data-grace-area-trigger]')[1]!.trigger('click')
    await vi.waitFor(() => expect(useToast().toasts.value.map(toast => toast.description)).toEqual(['1 row copied to clipboard']))
  })

  it('does not offer GeoJSON again while one is being downloaded', async () => {
    // a second choice sent a second request and saved a second file
    let asked = false
    const hold = gate()
    registerEndpoint('/api/values', async (event) => {
      if (getQuery(event).format === 'geojson') {
        asked = true
        await hold.opened
        return { type: 'FeatureCollection', features: [] }
      }
      return { values: [row] }
    })
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    const saved = catchDownload()
    ;(await openDownloads(wrapper))[2]!.click()
    await vi.waitFor(() => expect(asked).toBe(true))
    expect(offered(await openDownloads(wrapper))[2]).toEqual(['GeoJSON', false])
    hold.open()
    await vi.waitFor(() => expect(saved).toHaveLength(1))
  })

  it('saves no GeoJSON that Clear overtook while it was being asked for', async () => {
    // it described a table that was no longer on screen, and said it was downloaded
    let asked = false
    const hold = gate()
    registerEndpoint('/api/values', async (event) => {
      if (getQuery(event).format === 'geojson') {
        asked = true
        await hold.opened
        return { type: 'FeatureCollection', features: [] }
      }
      return { values: [row] }
    })
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    const saved = catchDownload()
    const aborts = abortsSeen()
    ;(await openDownloads(wrapper))[2]!.click()
    await vi.waitFor(() => expect(asked).toBe(true))
    ;(viewer.vm as unknown as { clearData: () => void }).clearData()
    expect(aborts).toContain('table-changed')
    hold.open()
    // told, where it was dropped without a word
    await vi.waitFor(() => expect(document.body.textContent).toContain('Download cancelled: the table changed'))
    expect(saved).toHaveLength(0)
  })

  it('asks for GeoJSON once, not again when the answer fails', async () => {
    // ofetch retries a failed GET once by default, doubling an expensive request and the wait
    let asked = 0
    registerEndpoint('/api/values', (event) => {
      if (getQuery(event).format === 'geojson') {
        asked++
        setResponseStatus(event, 502)
        return 'Bad Gateway'
      }
      return { values: [row] }
    })
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    catchDownload()
    ;(await openDownloads(wrapper))[2]!.click()
    await vi.waitFor(() => expect(document.body.textContent).toContain('502'))
    expect(asked).toBe(1)
  })

  it.each([
    ['leaving query mode, which hands back the table\'s own rows', true],
    ['a query of its own, whose rows replace the table\'s', false],
  ])('a GeoJSON download under way is saved after %s: %s', async (_, kept) => {
    // it was aborted on every emit from the query panel, the unchanged table included, without a word
    let asked = false
    const hold = gate()
    registerEndpoint('/api/values', async (event) => {
      if (getQuery(event).format === 'geojson') {
        asked = true
        await hold.opened
        return { type: 'FeatureCollection', features: [] }
      }
      return { values: [row] }
    })
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    const saved = catchDownload()
    const aborts = abortsSeen()
    ;(await openDownloads(wrapper))[2]!.click()
    await vi.waitFor(() => expect(asked).toBe(true))
    const panel = wrapper.findComponent(QueryPanel)
    const rows = kept ? panel.props('data') : [{ timestamp: '2020-01-01', parameter: 'temperature_air_mean_2m', avg_value: 1.5 }]
    panel.vm.$emit('dataTransformed', rows)
    await wrapper.vm.$nextTick()
    expect(aborts.includes('table-changed')).toBe(!kept)
    if (kept) {
      hold.open()
      await vi.waitFor(() => expect(saved).toHaveLength(1))
    }
    else {
      hold.open()
      await vi.waitFor(() => expect(document.body.textContent).toContain('Download cancelled: the table changed'))
      expect(saved).toHaveLength(0)
    }
  })

  it('tells a GeoJSON request the backend refuses, and saves nothing', async () => {
    registerEndpoint('/api/values', (event) => {
      // answered as FastAPI answers a refused request: the entries under `detail`, nothing around them
      if (getQuery(event).format === 'geojson') {
        setResponseStatus(event, 422)
        return { detail: [{ loc: ['query', 'stations'], msg: 'Cannot be combined with name' }] }
      }
      return { values: [row] }
    })
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    const saved = catchDownload()
    const items = await openDownloads(wrapper)
    items[2]!.click()
    await vi.waitFor(() => expect(document.body.textContent).toContain('stations: Cannot be combined with name'))
    expect(saved).toHaveLength(0)
  })
})

// the rows a viewer's table page shows, as text, and the page its pager marks as shown
function pageShown(wrapper: Awaited<ReturnType<typeof mountDataViewer>>['wrapper']) {
  const texts = wrapper.findAll('tbody tr').map(tr => tr.text())
  return { rows: texts, page: wrapper.find('[aria-current="page"]').text() }
}

function rows(count: number, stationId: string) {
  return Array.from({ length: count }, (_, i) => ({ ...row, station_id: stationId, value: i }))
}

describe('dataViewer pages', () => {
  it('shows the first page of an answer shorter than the page chosen while it was fetched', async () => {
    const hold = gate()
    registerEndpoint('/api/values', async (event) => {
      const station = String(getQuery(event).stations)
      if (station === '04411')
        await hold.opened
      return { values: rows(station === '04411' ? 40 : 500, station) }
    })
    const { wrapper, viewer, stationSelection } = await mountDataViewer()
    await fetchData(viewer)
    await wrapper.find('button[aria-label="Last page"]').trigger('click')
    await vi.waitFor(() => expect(pageShown(wrapper).page).toBe('10'))
    stationSelection.value = byStation('04411')
    await wrapper.vm.$nextTick()
    const fetching = fetchData(viewer)
    // the pager goes back to the first page as Fetch is pressed, while the table waits for the answer
    await vi.waitFor(() => expect(pageShown(wrapper).page).toBe('1'))
    // the 500 rows' last page, moved to again while the 40 are fetched
    await wrapper.find('button[aria-label="Last page"]').trigger('click')
    await vi.waitFor(() => expect(pageShown(wrapper).page).toBe('10'))
    hold.open()
    await fetching
    await wrapper.vm.$nextTick()
    const shown = pageShown(wrapper)
    expect(shown.page).toBe('1')
    expect(shown.rows).toHaveLength(40)
    expect(shown.rows.every(text => text.includes('04411'))).toBe(true)
  })

  it('shows the first page of a query\'s rows, fewer than the page chosen in the table', async () => {
    registerEndpoint('/api/values', () => ({ values: rows(500, '01048') }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    await wrapper.find('button[aria-label="Last page"]').trigger('click')
    await vi.waitFor(() => expect(pageShown(wrapper).page).toBe('10'))
    wrapper.findComponent(QueryPanel).vm.$emit('dataTransformed', rows(3, '09999'))
    await wrapper.vm.$nextTick()
    const shown = pageShown(wrapper)
    expect(shown.page).toBe('1')
    expect(shown.rows).toHaveLength(3)
    expect(shown.rows.every(text => text.includes('09999'))).toBe(true)
  })

  it('goes back to the first page on Clear', async () => {
    registerEndpoint('/api/values', () => ({ values: rows(500, '01048') }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    await wrapper.find('button[aria-label="Last page"]').trigger('click')
    await vi.waitFor(() => expect(pageShown(wrapper).page).toBe('10'))
    ;(viewer.vm as unknown as { clearData: () => void }).clearData()
    await wrapper.vm.$nextTick()
    expect(pageShown(wrapper)).toEqual({ rows: [], page: '1' })
  })

  it('shows the first page of the fetched rows on leaving query mode', async () => {
    registerEndpoint('/api/values', () => ({ values: rows(500, '01048') }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    const panel = wrapper.findComponent(QueryPanel)
    panel.vm.$emit('dataTransformed', rows(200, '09999'))
    await wrapper.vm.$nextTick()
    await wrapper.find('button[aria-label="Last page"]').trigger('click')
    await vi.waitFor(() => expect(pageShown(wrapper).page).toBe('4'))
    // leaving query mode hands back the fetched rows themselves, as the panel's reset does
    panel.vm.$emit('dataTransformed', panel.props('data'))
    await wrapper.vm.$nextTick()
    const shown = pageShown(wrapper)
    expect(shown.page).toBe('1')
    expect(shown.rows).toHaveLength(50)
    expect(shown.rows.every(text => text.includes('01048'))).toBe(true)
  })
})

describe('dataViewer query panel', () => {
  it('keeps the rows a newer Fetch put in the table when a query started before it answers', async () => {
    // the query's result, of the station fetched before, replaced them
    registerEndpoint('/api/values', event => ({ values: rows(3, String(getQuery(event).stations)) }))
    // the worker DuckDB is started in
    vi.stubGlobal('Worker', class {})
    const hold = gate()
    let asked = false
    duckdb.answer = async () => {
      asked = true
      await hold.opened
      // a quality of its own, as an Arrow table built from rows drops a column that is null in every one
      return rows(1, '01048').map(row => ({ ...row, value: 99, quality_flags: '1' }))
    }
    const { wrapper, viewer, stationSelection } = await mountDataViewer()
    await fetchData(viewer)
    await wrapper.findAll('button').find(button => button.text() === 'Transform with SQL Query')!.trigger('click')
    await wrapper.findAll('button').find(button => button.text() === 'Run Query')!.trigger('click')
    await vi.waitFor(() => expect(asked).toBe(true))
    stationSelection.value = byStation('04411')
    await wrapper.vm.$nextTick()
    await fetchData(viewer)
    hold.open()
    await flushPromises()
    const shown = pageShown(wrapper)
    expect(shown.rows).toHaveLength(3)
    expect(shown.rows.every(text => text.includes('04411'))).toBe(true)
  })
})

function atPoint(mode: 'interpolation' | 'summary'): StationSelectionState {
  return { mode, selection: { stations: [] }, interpolation: { source: 'manual', latitude: 52.5, longitude: 13.4 }, dateRange: {} }
}

// the table's column headers, without the sort mark beside each
function headers(wrapper: Awaited<ReturnType<typeof mountDataViewer>>['wrapper']) {
  return wrapper.findAll('thead th').map(th => th.text().replace(/[↕↑↓]/g, '').trim())
}

// the columns the picker has chosen, as its button lists them; it comes before the page size's
function picked(wrapper: Awaited<ReturnType<typeof mountDataViewer>>['wrapper']) {
  return wrapper.find('button[aria-haspopup="listbox"] [data-slot="value"]').text().split(', ')
}

describe('dataViewer columns', () => {
  // each point mode, and the column its rows add, as the REST API answers them
  const pointModes = [
    { mode: 'interpolation', endpoint: '/api/interpolate', column: 'taken_station_ids', values: [{ ...row, taken_station_ids: ['01048', '04411'] }] },
    { mode: 'summary', endpoint: '/api/summarize', column: 'taken_station_id', values: [{ ...row, taken_station_id: '01048' }] },
  ] as const

  it.each(pointModes)('keeps to the $mode rows shown when station mode is selected without fetching', async ({ mode, endpoint, column, values }) => {
    registerEndpoint(endpoint, () => ({ values }))
    const { wrapper, viewer, stationSelection } = await mountDataViewer(ref(atPoint(mode)))
    await fetchData(viewer)
    await wrapper.vm.$nextTick()
    expect(headers(wrapper)).toContain(column)
    stationSelection.value = byStation('01048')
    await wrapper.vm.$nextTick()
    // still the rows' columns, where the picker was reset to the station columns and the query panel
    // checked the rows against them
    expect(picked(wrapper)).toContain(column)
    expect(headers(wrapper)).toContain(column)
    expect(wrapper.findComponent(QueryPanel).props('expectedColumns')).toContain(column)
  })

  it('shows the flags a provider publishes next to the value', async () => {
    // the source's own flags, one string: the quality flag plain and the further kinds as `kind:code` (GH-2018, GH-2758),
    // and a column the table orders after it, which would otherwise come out ahead of the flags
    registerEndpoint('/api/values', () => ({ values: [{ ...row, taken_station_id: '01048', quality_flags: 'G,measurement:T,source:7' }] }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    expect(picked(wrapper)).toEqual([
      'station_id',
      'parameter',
      'timestamp',
      'value',
      'quality_flags',
      'taken_station_id',
    ])
    expect(wrapper.text()).toContain('G,measurement:T,source:7')
  })

  it('takes the columns of the station rows a Fetch replaces interpolated rows with', async () => {
    registerEndpoint('/api/interpolate', () => ({ values: pointModes[0].values }))
    registerEndpoint('/api/values', () => ({ values: [row] }))
    const { wrapper, viewer, stationSelection } = await mountDataViewer(ref(atPoint('interpolation')))
    await fetchData(viewer)
    stationSelection.value = byStation('01048')
    await wrapper.vm.$nextTick()
    await fetchData(viewer)
    await wrapper.vm.$nextTick()
    expect(picked(wrapper)).toEqual(['station_id', 'parameter', 'timestamp', 'value', 'quality_flags'])
    expect(wrapper.findComponent(QueryPanel).props('expectedColumns')).toEqual(Object.keys(row))
  })

  // one column per parameter: none of them among the table's fixed columns
  const wide = { station_id: '01048', resolution: 'daily', dataset: 'climate_summary', timestamp: '2020-01-01T00:00:00Z', temperature_air_mean_2m: 1.5 }

  it('shows and copies the columns a wide-shaped table carries', async () => {
    registerEndpoint('/api/values', () => ({ values: [wide] }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    await wrapper.vm.$nextTick()
    // no empty parameter, value and quality_flags, where the measurement was left out
    expect(headers(wrapper)).toEqual(['station_id', 'timestamp', 'temperature_air_mean_2m'])
    expect(pageShown(wrapper).rows[0]).toContain('1.5')
    const copied: string[] = []
    Object.defineProperty(navigator, 'clipboard', { value: { writeText: async (text: string) => void copied.push(text) }, configurable: true })
    // "copy all", the second of the two buttons beside the table's tooltip triggers
    await wrapper.findAll('button[data-grace-area-trigger]')[1]!.trigger('click')
    await vi.waitFor(() => expect(copied).toHaveLength(1))
    expect(copied[0]!.split('\n')).toEqual(['station_id,timestamp,temperature_air_mean_2m', '01048,2020-01-01T00:00:00Z,1.5'])
  })

  it('shows the columns of a query\'s own rows', async () => {
    registerEndpoint('/api/values', () => ({ values: [row] }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    // DuckDB names an unaliased column after its expression, a point in it included; a struct comes
    // as an object
    wrapper.findComponent(QueryPanel).vm.$emit('dataTransformed', [{ 'parameter': 'temperature_air_mean_2m', 'avg_value': 2.5, '(value * 1.5)': 2.25, 'range': { min: 1, max: 2 } }])
    await wrapper.vm.$nextTick()
    expect(headers(wrapper)).toEqual(['parameter', 'avg_value', '(value * 1.5)', 'range'])
    expect(picked(wrapper)).toEqual(['parameter', 'avg_value', '(value * 1.5)', 'range'])
    expect(wrapper.findAll('tbody td').map(td => td.text())).toEqual(['temperature_air_mean_2m', '2.5', '2.25', '{"min":1,"max":2}'])
  })

  // a header of the table, with the sort mark beside it, found by its column
  function header(wrapper: Awaited<ReturnType<typeof mountDataViewer>>['wrapper'], column: string) {
    return wrapper.findAll('thead th span').find(span => span.text().replace(/[↕↑↓]/g, '') === column)!
  }

  // `constructor` as well, which every row has through its prototype, though none carries it
  it.each(['avg_value', 'constructor'])('sorts by a query\'s own column %s only while the rows shown carry it', async (column) => {
    registerEndpoint('/api/values', () => ({ values: rows(5, '01048') }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    await wrapper.vm.$nextTick()
    const fetched = pageShown(wrapper).rows
    const panel = wrapper.findComponent(QueryPanel)
    const query = [{ parameter: 'temperature_air_mean_2m', [column]: 2.5 }]
    panel.vm.$emit('dataTransformed', query)
    await wrapper.vm.$nextTick()
    await header(wrapper, column).trigger('click')
    // the order a sort by a column no row has leaves the rows in is the engine's -- V8 keeps it,
    // SpiderMonkey reverses it -- so what is asked is whether the fetched rows were sorted at all
    const sort = vi.spyOn(Array.prototype, 'sort')
    panel.vm.$emit('dataTransformed', panel.props('data'))
    await wrapper.vm.$nextTick()
    expect(pageShown(wrapper).rows).toEqual(fetched)
    const sortedFetched = (sort.mock.contexts as unknown[][]).filter(sorted => sorted.some(r => (r as { station_id?: string } | null)?.station_id === '01048'))
    expect(sortedFetched).toHaveLength(0)
    // and by it again once the query's rows are back
    panel.vm.$emit('dataTransformed', [...query])
    await wrapper.vm.$nextTick()
    expect(header(wrapper, column).text()).toBe(`${column}↑`)
  })

  it('keeps a sort by a fixed column through a query whose rows lack it', async () => {
    registerEndpoint('/api/values', () => ({ values: rows(5, '01048') }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    await wrapper.vm.$nextTick()
    await header(wrapper, 'value').trigger('click')
    await header(wrapper, 'value').trigger('click')
    const panel = wrapper.findComponent(QueryPanel)
    panel.vm.$emit('dataTransformed', [{ parameter: 'temperature_air_mean_2m', avg_value: 2.5 }])
    await wrapper.vm.$nextTick()
    panel.vm.$emit('dataTransformed', panel.props('data'))
    await wrapper.vm.$nextTick()
    expect(header(wrapper, 'value').text()).toBe('value↓')
    expect(wrapper.findAll('tbody tr').map(tr => tr.findAll('td')[3]!.text())).toEqual(['4', '3', '2', '1', '0'])
  })

  it('sorts a query\'s struct by the text it shows', async () => {
    registerEndpoint('/api/values', () => ({ values: [row] }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    wrapper.findComponent(QueryPanel).vm.$emit('dataTransformed', [{ range: { min: 2 } }, { range: { min: 1 } }])
    await wrapper.vm.$nextTick()
    await header(wrapper, 'range').trigger('click')
    expect(wrapper.findAll('tbody td').map(td => td.text())).toEqual(['{"min":1}', '{"min":2}'])
  })

  it('keeps a column hidden in a query\'s rows hidden once the fetched rows are back', async () => {
    registerEndpoint('/api/values', () => ({ values: [row] }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    const panel = wrapper.findComponent(QueryPanel)
    panel.vm.$emit('dataTransformed', [{ parameter: 'temperature_air_mean_2m', avg_value: 2.5 }])
    await wrapper.vm.$nextTick()
    // avg_value unticked in the picker, whose rows carry no resolution or dataset to hide
    wrapper.findComponent(USelectMenu).vm.$emit('update:modelValue', ['parameter'])
    await wrapper.vm.$nextTick()
    expect(headers(wrapper)).toEqual(['parameter'])
    panel.vm.$emit('dataTransformed', panel.props('data'))
    await wrapper.vm.$nextTick()
    expect(headers(wrapper)).toEqual(['station_id', 'parameter', 'timestamp', 'value', 'quality_flags'])
    panel.vm.$emit('dataTransformed', [{ parameter: 'temperature_air_mean_2m', avg_value: 3.5 }])
    await wrapper.vm.$nextTick()
    expect(headers(wrapper)).toEqual(['parameter'])
  })
})

// the graph view, faceted by parameter where asked, as its toggle and checkbox are clicked
async function showChart(wrapper: Awaited<ReturnType<typeof mountDataViewer>>['wrapper'], faceted: boolean) {
  await wrapper.findAll('button').find(button => button.find('[class~="i-ph:chart-line"]').exists())!.trigger('click')
  if (faceted) {
    const label = wrapper.findAll('label').find(label => label.text() === 'Facet by parameter')!
    await wrapper.find(`#${label.attributes('for')}`).trigger('click')
  }
  await flushPromises()
}

// two parameters, a facet each
const twoParameters = [row, { ...row, parameter: 'precipitation_amount', value: 0.2 }]

describe('dataViewer chart images', () => {
  it.each([false, true])('offers no chart image while no chart is shown, faceted: %s', async (faceted) => {
    const { wrapper } = await mountDataViewer()
    await showChart(wrapper, faceted)
    expect(offered(await openDownloads(wrapper))).toEqual([['PNG', false], ['JPEG', false], ['SVG', false]])
  })

  it.each([false, true])('offers every chart image once a chart is shown, faceted: %s', async (faceted) => {
    registerEndpoint('/api/values', () => ({ values: twoParameters }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    await showChart(wrapper, faceted)
    expect(offered(await openDownloads(wrapper))).toEqual([['PNG', true], ['JPEG', true], ['SVG', true]])
  })

  it('saves the facets as one SVG, stacked in the order the page shows them, each as large as it is shown', async () => {
    // it looked for the single chart, which faceting replaces, and saved nothing without a word
    registerEndpoint('/api/values', () => ({ values: twoParameters }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    await showChart(wrapper, true)
    ;(await openDownloads(wrapper))[2]!.click()
    await vi.waitFor(() => expect(image.downloads).toHaveLength(1))
    expect(image.downloads[0]!.filename).toBe('chart.svg')
    // the text of the file, which happy-dom's XML parser does not take
    const svg = await image.downloads[0]!.blob.text()
    expect(svg).toMatch(/^<svg [^>]*width="800" height="600" viewBox="0 0 800 600">/)
    const charts = [...svg.matchAll(/<svg [^>]*x="0" y="(\d+)" width="800" height="(\d+)"[^>]*>([\s\S]*?)<\/svg>/g)]
    expect(charts.map(chart => [chart[1], chart[2]])).toEqual([['0', '300'], ['300', '300']])
    // each is drawn from the rows of its own parameter: the temperature's 1.5 and the precipitation's 0.2 are on their axes
    expect(charts[0]![3]).toMatch(/>1\.5\d?</)
    expect(charts[1]![3]).toContain('>0.2')
    await vi.waitFor(() => expect(document.body.textContent).toContain('Chart downloaded as SVG'))
  })

  it('saves the facets it was chosen for when faceting is turned off before the image is drawn', async () => {
    // faceting was looked at again after awaiting, and the first facet saved as the single chart
    registerEndpoint('/api/values', () => ({ values: twoParameters }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    await showChart(wrapper, true)
    ;(await openDownloads(wrapper))[2]!.click()
    // unticked before the download goes on past its first await
    const label = wrapper.findAll('label').find(label => label.text() === 'Facet by parameter')!
    ;(document.getElementById(label.attributes('for')!) as HTMLElement).click()
    await vi.waitFor(() => expect(document.body.textContent).toContain('Chart downloaded as SVG'))
    expect(image.downloads).toHaveLength(1)
    expect((await image.downloads[0]!.blob.text()).match(/<svg /g)).toHaveLength(3)
  })

  it('saves the single chart as large as it is shown, one pixel to a pixel, and named chart', async () => {
    registerEndpoint('/api/values', () => ({ values: twoParameters }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    await showChart(wrapper, false)
    ;(await openDownloads(wrapper))[1]!.click()
    await vi.waitFor(() => expect(document.body.textContent).toContain('Chart downloaded as JPEG'))
    expect(image.options.at(-1)).toMatchObject({ format: 'jpeg', width: 800, height: 400, scale: 1 })
    expect(image.downloads.map(download => download.filename)).toEqual(['chart.jpeg'])
  })

  it('saves a chart drawn again off screen, in the light theme, and leaves the chart on the page as it is', async () => {
    // a saved chart is the light one whatever the page shows: its own copy, drawn by the library without an element, from
    // the state of the chart on the page, which is not drawn again and loses nothing
    registerEndpoint('/api/values', () => ({ values: twoParameters }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    await showChart(wrapper, false)
    await vi.waitFor(() => expect(drawings()).toHaveLength(1))
    const shown = echarts.instances.at(-1)!
    ;(await openDownloads(wrapper))[1]!.click()
    await vi.waitFor(() => expect(document.body.textContent).toContain('Chart downloaded as JPEG'))
    expect(echarts.init.mock.calls.filter(([element]) => element === null)).toHaveLength(1)
    expect(drawings()).toHaveLength(1)
    expect(shown.dispose).not.toHaveBeenCalled()
    expect(shown.el.isConnected).toBe(true)
  })

  it('has the camera of the toolbar save the same, named newplot as Plotly\'s was, and tell it as the menu does', async () => {
    registerEndpoint('/api/values', () => ({ values: twoParameters }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    await showChart(wrapper, false)
    await vi.waitFor(() => expect(drawings()).toHaveLength(1))
    document.body.querySelector<HTMLButtonElement>('.xc-toolbar button[aria-label="Download plot as a PNG"]')!.click()
    await vi.waitFor(() => expect(image.downloads).toHaveLength(1))
    expect(image.downloads[0]!.filename).toBe('newplot.png')
    expect(image.options.at(-1)).toMatchObject({ format: 'png', width: 800, height: 400, scale: 1 })
    await vi.waitFor(() => expect(document.body.textContent).toContain('Chart downloaded as PNG'))
  })

  it('has a camera for each facet, which saves that facet alone', async () => {
    registerEndpoint('/api/values', () => ({ values: twoParameters }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    await showChart(wrapper, true)
    await vi.waitFor(() => expect(drawings()).toHaveLength(2))
    const cameras = document.body.querySelectorAll<HTMLButtonElement>('.xc-toolbar button[aria-label="Download plot as a PNG"]')
    expect(cameras).toHaveLength(2)
    cameras[1]!.click()
    await vi.waitFor(() => expect(image.downloads).toHaveLength(1))
    expect(image.options.at(-1)).toMatchObject({ width: 800, height: 300 })
    // the labels of its axis are the precipitation's, not the temperature's
    const labels = [...image.options.at(-1)!.svg.matchAll(/>([^<]+)<\/text>/g)].map(match => match[1])
    expect(labels.some(label => label.startsWith('0.2'))).toBe(true)
    expect(labels.some(label => label.startsWith('1.'))).toBe(false)
  })

  it('saves the facets as one PNG, drawn from their stacked SVG', async () => {
    registerEndpoint('/api/values', () => ({ values: twoParameters }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    await showChart(wrapper, true)
    ;(await openDownloads(wrapper))[0]!.click()
    await vi.waitFor(() => expect(image.downloads).toHaveLength(1))
    const options = image.options.at(-1)!
    expect([options.format, options.width, options.height, options.scale]).toEqual(['png', 800, 600, 1])
    expect(options.svg).toContain('y="300"')
    expect(image.downloads[0]!.blob.type).toBe('image/png')
    expect(image.downloads[0]!.filename).toBe('chart.png')
    await vi.waitFor(() => expect(document.body.textContent).toContain('Chart downloaded as PNG'))
  })

  it.each([false, true])('says there is no chart where Clear emptied it after the menu was opened, faceted: %s', async (faceted) => {
    registerEndpoint('/api/values', () => ({ values: twoParameters }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    await showChart(wrapper, faceted)
    const items = await openDownloads(wrapper)
    // chosen before the menu has updated, as from the explorer sidebar
    ;(viewer.vm as unknown as { clearData: () => void }).clearData()
    items[0]!.click()
    await vi.waitFor(() => expect(document.body.textContent).toContain('No data available for chart'))
    expect(image.downloads).toHaveLength(0)
  })
})

describe('dataViewer query panel columns', () => {
  // the columns the query panel lists as available, as it shows them once opened
  async function availableColumns(wrapper: Awaited<ReturnType<typeof mountDataViewer>>['wrapper']) {
    await wrapper.findAll('button').find(button => button.text() === 'Transform with SQL Query')!.trigger('click')
    const hint = wrapper.findAll('div').find(div => div.text().startsWith('Available columns:'))
    expect(hint).toBeDefined()
    return hint!.find('code').text().split(', ')
  }

  it('lists the columns a wide-shaped table carries, its parameters in place of parameter, value and quality_flags', async () => {
    registerEndpoint('/api/values', () => ({ values: [{ station_id: '01048', resolution: 'daily', dataset: 'climate_summary', timestamp: '2020-01-01T00:00:00Z', temperature_air_mean_2m: 1.5, precipitation_amount: 0.2 }] }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    await wrapper.vm.$nextTick()
    expect(await availableColumns(wrapper)).toEqual(['station_id', 'resolution', 'dataset', 'timestamp', 'temperature_air_mean_2m', 'precipitation_amount'])
  })

  // each point mode's rows as the REST API answers them, with a distance of their own and no quality_flags.
  // The distance comes first, so that the list is seen to follow the table's order, not the rows'
  const { quality_flags: _, ...measured } = row
  it.each([
    { mode: 'interpolation', endpoint: '/api/interpolate', values: [{ distance_mean: 12.3, ...measured, taken_station_ids: ['01048', '04411'] }], columns: ['taken_station_ids', 'distance_mean'] },
    { mode: 'summary', endpoint: '/api/summarize', values: [{ distance: 4.2, ...measured, taken_station_id: '01048' }], columns: ['taken_station_id', 'distance'] },
  ] as const)('lists the $mode rows\' own columns, after the table\'s, and no quality_flags', async ({ mode, endpoint, values, columns }) => {
    registerEndpoint(endpoint, () => ({ values }))
    const { wrapper, viewer } = await mountDataViewer(ref(atPoint(mode)))
    await fetchData(viewer)
    await wrapper.vm.$nextTick()
    expect(await availableColumns(wrapper)).toEqual(['station_id', 'resolution', 'dataset', 'parameter', 'timestamp', 'value', ...columns])
  })

  it('lists the columns of the rows it queries, not those of a query\'s result shown', async () => {
    registerEndpoint('/api/values', () => ({ values: [row] }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    wrapper.findComponent(QueryPanel).vm.$emit('dataTransformed', [{ parameter: 'temperature_air_mean_2m', avg_value: 2.5 }])
    await wrapper.vm.$nextTick()
    expect(headers(wrapper)).toEqual(['parameter', 'avg_value'])
    expect(await availableColumns(wrapper)).toEqual(['station_id', 'resolution', 'dataset', 'parameter', 'timestamp', 'value', 'quality_flags'])
  })
})

describe('dataViewer sort of missing values', () => {
  // two rows without a value among two with one, each known by its station
  const withGaps = [
    { ...row, station_id: 'a', value: null },
    { ...row, station_id: 'b', value: 2 },
    { ...row, station_id: 'c', value: null },
    { ...row, station_id: 'd', value: 1 },
  ]

  // the stations of the rows shown, in their order
  function stations(wrapper: Awaited<ReturnType<typeof mountDataViewer>>['wrapper']) {
    return wrapper.findAll('tbody tr').map(tr => tr.findAll('td')[0]!.text())
  }

  it('puts the missing values last in either direction, in the order they came', async () => {
    registerEndpoint('/api/values', () => ({ values: withGaps }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    await wrapper.vm.$nextTick()
    const value = () => wrapper.findAll('thead th span').find(span => span.text().replace(/[↕↑↓]/g, '') === 'value')!
    const sort = vi.spyOn(Array.prototype, 'sort')
    await value().trigger('click')
    expect(stations(wrapper)).toEqual(['d', 'b', 'a', 'c'])
    // the order two missing values are left in is the engine's own where they compare unequal: V8
    // keeps it, SpiderMonkey reverses it, so it is the comparator that is asked
    const table = (sort.mock.contexts as unknown[][]).findIndex(sorted => sorted.some(r => (r as { station_id?: string } | null)?.station_id === 'a'))
    const compare = sort.mock.calls[table]![0]!
    expect(compare(withGaps[0], withGaps[2])).toBe(0)
    expect(compare(withGaps[2], withGaps[0])).toBe(0)
    await value().trigger('click')
    expect(stations(wrapper)).toEqual(['b', 'd', 'a', 'c'])
  })
})

describe('dataViewer rows without a timestamp', () => {
  // a query's row whose timestamp is null -- `NULL AS timestamp`, an outer join, a date past what a
  // JS Date holds -- beside one that has it
  const query = [row, { ...row, timestamp: null, value: 9 }]

  async function withQueryRows() {
    registerEndpoint('/api/values', () => ({ values: [row] }))
    const mountedViewer = await mountDataViewer()
    await fetchData(mountedViewer.viewer)
    mountedViewer.wrapper.findComponent(QueryPanel).vm.$emit('dataTransformed', query)
    await mountedViewer.wrapper.vm.$nextTick()
    return mountedViewer
  }

  it('shows the timestamp empty, as the other cells show a missing value', async () => {
    // the timestamp cell threw on it, and the table was not drawn
    const { wrapper } = await withQueryRows()
    const cells = wrapper.findAll('tbody tr').map(tr => tr.findAll('td').map(td => td.text()))
    expect(cells).toEqual([
      ['01048', 'temperature_air_mean_2m', '2020-01-01T00:00:00Z', '1.5', ''],
      ['01048', 'temperature_air_mean_2m', '', '9', ''],
    ])
  })

  it.each([false, true])('leaves the row out of the chart, faceted: %s', async (faceted) => {
    // it was drawn at 1970-01-01
    forgetDrawings()
    const { wrapper } = await withQueryRows()
    await showChart(wrapper, faceted)
    await vi.waitFor(() => expect(drawings().length).toBeGreaterThan(0))
    expect(linesOf(lastDrawn().option)[0].data).toEqual([[Date.UTC(2020, 0, 1), 1.5]])
  })
})

describe('dataViewer work on a large answer', () => {
  // Fetch opens the table, and the chart's rows, series and facets were made at once all the same: the
  // render watchers read them whatever the view, a second pass over every row of an answer of a million
  // for a chart not on screen (GH-2560)
  it.each([false, true])('reads the rows for the chart once the chart is shown, not before, faceted: %s', async (faceted) => {
    registerEndpoint('/api/values', () => ({ values: rows(50, '01048') }))
    const { wrapper, viewer } = await mountDataViewer()
    timestampDates.calls = 0
    await fetchData(viewer)
    await flushPromises()
    expect(wrapper.findAll('tbody tr')).toHaveLength(50)
    expect(timestampDates.calls).toBe(0)
    // and no chart code is asked for before the chart is
    expect(echarts.init).not.toHaveBeenCalled()

    forgetDrawings()
    await showChart(wrapper, faceted)
    await vi.waitFor(() => expect(drawings().length).toBeGreaterThan(0))
    // once for each row, by the series or by the facets, not by both nor by every computed that reads them
    expect(timestampDates.calls).toBe(50)
  })
})

describe('dataViewer query structs under the table\'s own names', () => {
  it('shows a struct under a fixed column as the text a copy writes', async () => {
    // `SELECT parameter, {'min': min(value), 'max': max(value)} AS value FROM data GROUP BY parameter`
    registerEndpoint('/api/values', () => ({ values: [row] }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    wrapper.findComponent(QueryPanel).vm.$emit('dataTransformed', [{ parameter: 'temperature_air_mean_2m', value: { min: 1, max: 2 } }])
    await wrapper.vm.$nextTick()
    expect(headers(wrapper)).toEqual(['parameter', 'value'])
    // it showed `[object Object]`, where a column of the query's own name showed the text
    expect(wrapper.findAll('tbody td').map(td => td.text())).toEqual(['temperature_air_mean_2m', '{"min":1,"max":2}'])
  })
})

describe('dataViewer chart series', () => {
  // one parameter from two stations, a series each where fetched by station
  const twoStations = [row, { ...row, station_id: '04411', value: 2.5 }]

  // the names of the series the chart was last drawn with, faceted or not
  function seriesDrawn() {
    return linesOf(lastDrawn().option).map(series => series.name)
  }

  it.each([false, true])('keeps a series per station fetched when interpolation is selected without fetching, faceted: %s', async (faceted) => {
    registerEndpoint('/api/values', () => ({ values: twoStations }))
    const { wrapper, viewer, stationSelection } = await mountDataViewer()
    await fetchData(viewer)
    await showChart(wrapper, faceted)
    await vi.waitFor(() => expect(drawings().length).toBeGreaterThan(0))
    const series = faceted ? ['01048', '04411'] : [`01048 - ${airTemperature}`, `04411 - ${airTemperature}`]
    expect(seriesDrawn()).toEqual(series)
    // the rows shown are still both stations': merged, they made one series zig-zagging between them
    stationSelection.value = atPoint('interpolation')
    await flushPromises()
    expect(seriesDrawn()).toEqual(series)
  })

  it.each([false, true])('draws interpolated rows fetched over station rows as interpolated, faceted: %s', async (faceted) => {
    registerEndpoint('/api/values', () => ({ values: twoStations }))
    registerEndpoint('/api/interpolate', () => ({ values: [{ ...row, taken_station_ids: ['01048', '04411'] }] }))
    const { wrapper, viewer, stationSelection } = await mountDataViewer()
    await fetchData(viewer)
    await showChart(wrapper, faceted)
    stationSelection.value = atPoint('interpolation')
    await flushPromises()
    forgetDrawings()
    await fetchData(viewer)
    await flushPromises()
    // every drawing of the answer: grouped by the mode of the request before it, the rows were drawn
    // as a station's first, the request answered being taken as the rows' only a few ticks later
    const drawn = drawings().map(({ option }) => linesOf(option).map(series => series.name))
    expect(drawn.length).toBeGreaterThan(0)
    expect(drawn.every(names => names.join() === (faceted ? 'interpolated' : airTemperature))).toBe(true)
  })
})

// a query's rows, as the query panel hands them over
async function withChartQuery(query: unknown[]) {
  registerEndpoint('/api/values', () => ({ values: [row] }))
  const mountedViewer = await mountDataViewer()
  await fetchData(mountedViewer.viewer)
  mountedViewer.wrapper.findComponent(QueryPanel).vm.$emit('dataTransformed', query)
  await mountedViewer.wrapper.vm.$nextTick()
  return mountedViewer
}

describe('dataViewer chart of a query\'s timestamps that are no date', () => {
  it.each([
    // `CAST(timestamp AS TIME) AS timestamp`: the chart was not drawn, its traces throwing a RangeError
    { timestamp: '01:00:00.000000', faceted: false },
    { timestamp: '01:00:00.000000', faceted: true },
    { timestamp: 'n/a', faceted: false },
    { timestamp: 'n/a', faceted: true },
    // text a browser reads as a date by rules of its own: 2001-01-01 and the year 1048 in Chrome
    { timestamp: '1', faceted: false },
    { timestamp: '1', faceted: true },
    { timestamp: '01048', faceted: false },
    { timestamp: '01048', faceted: true },
    // `epoch(timestamp) AS timestamp`: read as milliseconds, drawn on 1970-01-19
    { timestamp: 1577836800, faceted: false },
    { timestamp: 1577836800, faceted: true },
  ])('leaves out a row whose timestamp is $timestamp, faceted: $faceted', async ({ timestamp, faceted }) => {
    forgetDrawings()
    const { wrapper } = await withChartQuery([row, { ...row, timestamp, value: 9 }])
    await showChart(wrapper, faceted)
    await vi.waitFor(() => expect(drawings().length).toBeGreaterThan(0))
    expect(linesOf(lastDrawn().option)[0].data).toEqual([[Date.UTC(2020, 0, 1), 1.5]])
  })
})

describe('dataViewer chart of the rows it can plot', () => {
  // a parameter whose rows have no value, and one whose rows have no timestamp, beside one plotted
  const unplotted = [
    row,
    { ...row, parameter: 'precipitation_amount', value: null },
    { ...row, parameter: 'wind_speed', timestamp: null, value: 3.1 },
  ]

  it('draws no series for the rows it leaves out', async () => {
    // each was an empty trace with a legend entry
    forgetDrawings()
    const { wrapper } = await withChartQuery(unplotted)
    await showChart(wrapper, false)
    await vi.waitFor(() => expect(drawings().length).toBeGreaterThan(0))
    expect(linesOf(lastDrawn().option).map(series => series.name)).toEqual([`01048 - ${airTemperature}`])
    expect(lastDrawn().option.series.find((series: any) => series.id === 'legend').data).toHaveLength(1)
  })

  it('draws no facet for the rows it leaves out', async () => {
    // each was an empty panel of its own, which the stacked image took in
    forgetDrawings()
    const { wrapper } = await withChartQuery(unplotted)
    await showChart(wrapper, true)
    await vi.waitFor(() => expect(drawings().length).toBeGreaterThan(0))
    expect(wrapper.findAll('h4').map(heading => heading.text())).toEqual([airTemperature])
    expect(echarts.instances).toHaveLength(1)
  })

  it.each([false, true])('says there is no chart and offers no image where no row can be plotted, faceted: %s', async (faceted) => {
    // an empty chart was drawn, and its image offered
    const { wrapper } = await withChartQuery(unplotted.slice(1))
    await showChart(wrapper, faceted)
    expect(wrapper.text()).toContain('No data available for chart')
    expect(offered(await openDownloads(wrapper))).toEqual([['PNG', false], ['JPEG', false], ['SVG', false]])
  })

  // a day's row each, from 2020-01-01 on
  const days = (count: number) => Array.from({ length: count }, (_, day) => ({ ...row, timestamp: new Date(Date.UTC(2020, 0, day + 1)).toISOString() }))

  it.each([false, true])('draws the points of a large result as a small one where most rows are left out, faceted: %s', async (faceted) => {
    // the rows left out were counted: drawn as thin lines without markers
    forgetDrawings()
    const { wrapper } = await withChartQuery([...days(10), ...days(600).map(day => ({ ...day, parameter: 'wind_speed', value: 'n/a' }))])
    await showChart(wrapper, faceted)
    await vi.waitFor(() => expect(drawings().length).toBeGreaterThan(0))
    expect(linesOf(lastDrawn().option)[0]).toMatchObject({ showSymbol: true, lineStyle: { width: 2 } })
  })

  it.each([false, true])('draws the points of a large result as a large one, a thin line without markers, faceted: %s', async (faceted) => {
    forgetDrawings()
    const { wrapper } = await withChartQuery(days(501))
    await showChart(wrapper, faceted)
    await vi.waitFor(() => expect(drawings().length).toBeGreaterThan(0))
    expect(linesOf(lastDrawn().option)[0]).toMatchObject({ showSymbol: false, lineStyle: { width: 1 } })
  })

  it('keeps a gap in the data as a gap in the line, where a row has no value at a date', async () => {
    forgetDrawings()
    const [first, , third] = days(3)
    const { wrapper } = await withChartQuery([first!, { ...days(3)[1]!, value: null }, { ...third!, value: 2.5 }])
    await showChart(wrapper, false)
    await vi.waitFor(() => expect(drawings().length).toBeGreaterThan(0))
    const [line] = linesOf(lastDrawn().option)
    expect(line.connectNulls).toBe(false)
    expect(line.data).toEqual([[Date.UTC(2020, 0, 1), 1.5], [Date.UTC(2020, 0, 2), null], [Date.UTC(2020, 0, 3), 2.5]])
  })

  it.each([false, true])('breaks the line where rows are missing, by the resolution the rows name, faceted: %s (GH-4100)', async (faceted) => {
    forgetDrawings()
    // daily rows of the 1st, 2nd, 3rd, then the 6th, 7th, 8th of January: the 4th and the 5th have no row at all
    const present = [0, 1, 2, 5, 6, 7].map(day => ({ ...row, timestamp: new Date(Date.UTC(2020, 0, day + 1)).toISOString(), value: day }))
    const { wrapper } = await withChartQuery(present)
    await showChart(wrapper, faceted)
    await vi.waitFor(() => expect(drawings().length).toBeGreaterThan(0))
    const [line] = linesOf(lastDrawn().option)
    expect(line.data.map((point: [number, number | null]) => point[1])).toEqual([0, 1, 2, null, 5, 6, 7])
    // the point of no value is between the two days, and every value the rows have is drawn
    expect(line.data[3][0]).toBeGreaterThan(Date.UTC(2020, 0, 3))
    expect(line.data[3][0]).toBeLessThan(Date.UTC(2020, 0, 6))
  })

  it('does not break the line of rows a day apart that name a resolution of months', async () => {
    forgetDrawings()
    const { wrapper } = await withChartQuery([0, 1, 2, 5, 6, 7].map(day => ({ ...row, resolution: 'monthly', timestamp: new Date(Date.UTC(2020, 0, day + 1)).toISOString(), value: day })))
    await showChart(wrapper, false)
    await vi.waitFor(() => expect(drawings().length).toBeGreaterThan(0))
    expect(linesOf(lastDrawn().option)[0].data.map((point: [number, number | null]) => point[1])).toEqual([0, 1, 2, 5, 6, 7])
  })

  it('draws a long series cut to what the plot can show, with every peak of it', async () => {
    // a year of ten-minute readings: 52,560 points, with one spike
    const start = Date.UTC(2020, 0, 1)
    const readings = Array.from({ length: 52_560 }, (_, i) => ({ ...row, timestamp: new Date(start + i * 600_000).toISOString(), value: i === 30_001 ? 99 : Math.sin(i / 300) }))
    forgetDrawings()
    const { wrapper } = await withChartQuery(readings)
    await showChart(wrapper, false)
    await vi.waitFor(() => expect(drawings().length).toBeGreaterThan(0), { timeout: 10_000 })
    const [line] = linesOf(lastDrawn().option)
    expect(line.data.length).toBeLessThan(4 * 800)
    expect(Math.max(...line.data.map((point: [number, number]) => point[1]))).toBe(99)
  }, 30_000)
})

// the chart drawn again, as the trendline is ticked or unticked
async function toggleTrendline(wrapper: Awaited<ReturnType<typeof mountDataViewer>>['wrapper']) {
  const label = wrapper.findAll('label').find(label => label.text() === 'Trendline')!
  await wrapper.find(`#${label.attributes('for')}`).trigger('click')
}

describe('dataViewer sort of numbers and text in one column', () => {
  // a query's BIGINT column, whose value past 2^53 comes as its digits
  const big = '10000000000000000000'
  const mixed = [{ id: big }, { id: 10 }, { id: 2 }]

  it('sorts the numbers before the text, each within its kind, in either direction', async () => {
    registerEndpoint('/api/values', () => ({ values: [row] }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    wrapper.findComponent(QueryPanel).vm.$emit('dataTransformed', mixed)
    await wrapper.vm.$nextTick()
    const id = () => wrapper.findAll('thead th span').find(span => span.text().replace(/[↕↑↓]/g, '') === 'id')!
    const sort = vi.spyOn(Array.prototype, 'sort')
    await id().trigger('click')
    expect(wrapper.findAll('tbody td').map(td => td.text())).toEqual(['2', '10', big])
    // an order the comparator itself holds to, where comparing a number with text as text made the
    // three a cycle, 2 < 10 < big < 2, whose order each engine's sort makes something else of
    const table = (sort.mock.contexts as unknown[][]).findIndex(sorted => sorted.some(r => (r as { id?: unknown } | null)?.id === big))
    const compare = sort.mock.calls[table]![0]!
    expect(compare(mixed[2], mixed[1])).toBeLessThan(0)
    expect(compare(mixed[1], mixed[0])).toBeLessThan(0)
    expect(compare(mixed[2], mixed[0])).toBeLessThan(0)
    expect(compare(mixed[0], mixed[2])).toBeGreaterThan(0)
    await id().trigger('click')
    expect(wrapper.findAll('tbody td').map(td => td.text())).toEqual([big, '10', '2'])
  })
})

describe('dataViewer column picker while the table is empty', () => {
  // a wide-shaped row: a column per parameter, and no parameter, value or quality_flags
  const wide = { station_id: '01048', resolution: 'daily', dataset: 'climate_summary', timestamp: '2020-01-01T00:00:00Z', temperature_air_mean_2m: 1.5 }

  // the columns the picker offers, ticked or not, and whether it can be opened
  function picker(wrapper: Awaited<ReturnType<typeof mountDataViewer>>['wrapper']) {
    const menu = wrapper.findComponent(USelectMenu)
    const { items } = menu.props() as { items: unknown[] }
    return { items, disabled: menu.find('button[aria-haspopup="listbox"]').attributes('disabled') !== undefined }
  }

  it('offers no columns and is disabled until a Fetch fills the table, then the rows\' own', async () => {
    registerEndpoint('/api/values', () => ({ values: [wide] }))
    const { wrapper, viewer } = await mountDataViewer()
    // where it offered the long shape's parameter, value and quality_flags, which the wide rows lack
    expect(picker(wrapper)).toEqual({ items: [], disabled: true })
    await fetchData(viewer)
    await wrapper.vm.$nextTick()
    expect(picker(wrapper)).toEqual({ items: ['station_id', 'resolution', 'dataset', 'timestamp', 'temperature_air_mean_2m'], disabled: false })
    expect(headers(wrapper)).toEqual(['station_id', 'timestamp', 'temperature_air_mean_2m'])
    ;(viewer.vm as unknown as { clearData: () => void }).clearData()
    await wrapper.vm.$nextTick()
    expect(picker(wrapper)).toEqual({ items: [], disabled: true })
  })

  it('offers no columns after an answer with no rows', async () => {
    registerEndpoint('/api/values', () => ({ values: [] }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    await wrapper.vm.$nextTick()
    expect(picker(wrapper)).toEqual({ items: [], disabled: true })
  })
})

describe('dataViewer sort of integers past 2^53', () => {
  // a query's HUGEINT column as plainRows writes it: the integers past 2^53 as their digits, the rest
  // as numbers; and digits within 2^53, sixteen of them as 2^53 has, or with a leading zero, which
  // plainRows never writes, which stay text
  const integers = [
    { n: '10000000000000000000' },
    { n: 5 },
    { n: '-10000000000000000000' },
    { n: '9007199254740993' },
    { n: -3 },
    { n: '-9007199254740993' },
  ]

  it('sorts them by their value among the numbers, in either direction', async () => {
    registerEndpoint('/api/values', () => ({ values: [row] }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    wrapper.findComponent(QueryPanel).vm.$emit('dataTransformed', [...integers, { n: 'x' }, { n: '1000000000000000' }, { n: '010000000000000000000' }, { n: '01048' }])
    await wrapper.vm.$nextTick()
    const n = () => wrapper.findAll('thead th span').find(span => span.text().replace(/[↕↑↓]/g, '') === 'n')!
    const ascending = ['-10000000000000000000', '-9007199254740993', '-3', '5', '9007199254740993', '10000000000000000000', '010000000000000000000', '01048', '1000000000000000', 'x']
    await n().trigger('click')
    expect(wrapper.findAll('tbody td').map(td => td.text())).toEqual(ascending)
    await n().trigger('click')
    expect(wrapper.findAll('tbody td').map(td => td.text())).toEqual(ascending.toReversed())
  })
})

describe('dataViewer query of no rows', () => {
  it('shows an empty table for a query that returned no rows, and the fetched rows on leaving query mode', async () => {
    // the table went on showing every fetched row, as if the query had filtered nothing
    registerEndpoint('/api/values', () => ({ values: rows(3, '01048') }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    await wrapper.vm.$nextTick()
    const panel = wrapper.findComponent(QueryPanel)
    panel.vm.$emit('dataTransformed', [])
    await wrapper.vm.$nextTick()
    expect(pageShown(wrapper).rows).toEqual(['No data'])
    expect(wrapper.text()).toContain('0 values (transformed from 3)')
    panel.vm.$emit('dataTransformed', panel.props('data'))
    await wrapper.vm.$nextTick()
    expect(pageShown(wrapper).rows).toHaveLength(3)
    expect(wrapper.text()).toContain('3 values')
  })
})

describe('dataViewer chart of a query\'s timestamp text', () => {
  // a browser an hour east of UTC, where a time without an offset read as local time is an hour early
  let zone: string | undefined
  beforeAll(() => {
    zone = process.env.TZ
    process.env.TZ = 'Europe/Berlin'
    // the zone taken up, else the tests pass in UTC against `new Date(text)` as well
    expect(new Date(2020, 0, 1).getTimezoneOffset()).toBe(-60)
  })
  afterAll(() => {
    if (zone === undefined)
      delete process.env.TZ
    else
      process.env.TZ = zone
  })

  // the forms timestampDate reads are tested in tests/unit/timestamp.test.ts
  it('places a row whose timestamp has no offset at its time in UTC', async () => {
    // `strftime(timestamp::TIMESTAMP, '%Y-%m-%d %H:%M')`: placed at 2019-12-31T23:00Z in Berlin
    forgetDrawings()
    const { wrapper } = await withChartQuery([{ ...row, timestamp: '2020-01-01 00:00', value: 9 }])
    await showChart(wrapper, false)
    await vi.waitFor(() => expect(drawings().length).toBeGreaterThan(0))
    expect(linesOf(lastDrawn().option)[0].data).toEqual([[Date.UTC(2020, 0, 1), 9]])
  })

  it('leaves out a row whose timestamp is a date that does not exist', async () => {
    // read as 2020-03-01 by a Date, which rolls a day past the month's end over
    forgetDrawings()
    const { wrapper } = await withChartQuery([row, { ...row, timestamp: '2020-02-30', value: 9 }])
    await showChart(wrapper, false)
    await vi.waitFor(() => expect(drawings().length).toBeGreaterThan(0))
    expect(linesOf(lastDrawn().option)[0].data).toEqual([[Date.UTC(2020, 0, 1), 1.5]])
  })
})

describe('dataViewer chart of a query\'s values that are no number', () => {
  // two days' numbers, and a third day's value as a query can put it
  const threeDays = (value: unknown) => [row, { ...row, timestamp: '2020-01-02T00:00:00Z', value: 2.5 }, { ...row, timestamp: '2020-01-03T00:00:00Z', value }]

  it.each([
    // `CAST(value AS VARCHAR) AS value`: the trendline added it up as text, and drew nothing
    '3.5',
    // the y axis turned into one of categories
    'n/a',
    Number.NaN,
    Number.POSITIVE_INFINITY,
  ])('leaves out a row whose value is %s, and draws the trendline of the others', async (value) => {
    forgetDrawings()
    const { wrapper } = await withChartQuery(threeDays(value))
    await showChart(wrapper, false)
    await toggleTrendline(wrapper)
    await vi.waitFor(() => expect(linesOf(lastDrawn().option)).toHaveLength(2))
    const [line, trend] = linesOf(lastDrawn().option)
    expect(line.data).toEqual([[Date.UTC(2020, 0, 1), 1.5], [Date.UTC(2020, 0, 2), 2.5]])
    expect(trend.data.map((point: [number, number]) => [point[0], Math.round(point[1] * 1e6) / 1e6])).toEqual([[Date.UTC(2020, 0, 1), 1.5], [Date.UTC(2020, 0, 2), 2.5]])
  })

  it('plots an integer past 2^53, which plainRows writes as its digits, as its number', async () => {
    forgetDrawings()
    const { wrapper } = await withChartQuery([{ ...row, value: '10000000000000000000' }, { ...row, timestamp: '2020-01-02T00:00:00Z', value: '-9007199254740993' }])
    await showChart(wrapper, false)
    await vi.waitFor(() => expect(drawings().length).toBeGreaterThan(0))
    expect(linesOf(lastDrawn().option)[0].data.map((point: [number, number]) => point[1])).toEqual([1e19, -9007199254740992])
  })
})

describe('dataViewer facets large or small by their own points', () => {
  // a day's row each of the parameter, from 2020-01-01 on
  const daysOf = (parameter: string, count: number) => Array.from({ length: count }, (_, day) => ({ ...row, parameter, timestamp: new Date(Date.UTC(2020, 0, day + 1)).toISOString() }))

  // each facet's markers and line width, as it was last drawn, by its parameter's label: an id the
  // glossary does not know is prettified, so 'a' is 'A'
  function facetStyles() {
    return Object.fromEntries([...facetsDrawn()].map(([facet, option]) => [facet, [linesOf(option)[0].showSymbol, linesOf(option)[0].lineStyle.width]]))
  }

  it('draws small facets as small ones where all of them together pass the threshold', async () => {
    // all six facets' 600 points were counted: each drawn as thin lines without markers
    forgetDrawings()
    const parameters = ['a', 'b', 'c', 'd', 'e', 'f']
    const { wrapper } = await withChartQuery(parameters.flatMap(parameter => daysOf(parameter, 100)))
    await showChart(wrapper, true)
    await vi.waitFor(() => expect(Object.keys(facetStyles())).toHaveLength(6))
    expect(facetStyles()).toEqual(Object.fromEntries(parameters.map(parameter => [parameter.toUpperCase(), [true, 2]])))
  })

  it('draws a large facet as a large one beside a small one', async () => {
    forgetDrawings()
    const { wrapper } = await withChartQuery([...daysOf('a', 501), ...daysOf('b', 10)])
    await showChart(wrapper, true)
    await vi.waitFor(() => expect(Object.keys(facetStyles())).toHaveLength(2))
    expect(facetStyles()).toEqual({ A: [false, 1], B: [true, 2] })
  })
})

describe('dataViewer chart series apart from the table\'s sort', () => {
  // one parameter from two stations, the second station's value the greater
  const twoStations = [row, { ...row, station_id: '04411', value: 2.5 }]

  // the series the chart was last drawn with, each by its name and colour, faceted or not
  function seriesDrawn() {
    return linesOf(lastDrawn().option).map(series => [series.name, series.lineStyle.color])
  }

  it.each([false, true])('keeps the series\' legend places and colours where the table is sorted, faceted: %s', async (faceted) => {
    registerEndpoint('/api/values', () => ({ values: twoStations }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    await wrapper.vm.$nextTick()
    forgetDrawings()
    await showChart(wrapper, faceted)
    await vi.waitFor(() => expect(drawings().length).toBeGreaterThan(0))
    const unsorted = seriesDrawn()
    expect(unsorted.map(([name]) => name)).toEqual(faceted ? ['01048', '04411'] : [`01048 - ${airTemperature}`, `04411 - ${airTemperature}`])
    expect(unsorted.map(([, colour]) => colour)).toEqual([seriesColour(0, isDark()), seriesColour(1, isDark())])
    // back to the table, sorted by value descending, the second station's row first: the stations
    // swapped their legend places and colours
    await wrapper.findAll('button').find(button => button.find('[class~="i-ph:table"]').exists())!.trigger('click')
    const value = () => wrapper.findAll('thead th span').find(span => span.text().replace(/[↕↑↓]/g, '') === 'value')!
    await value().trigger('click')
    await value().trigger('click')
    expect(wrapper.findAll('tbody tr').map(tr => tr.findAll('td')[0]!.text())).toEqual(['04411', '01048'])
    forgetDrawings()
    await wrapper.findAll('button').find(button => button.find('[class~="i-ph:chart-line"]').exists())!.trigger('click')
    await flushPromises()
    await vi.waitFor(() => expect(drawings().length).toBeGreaterThan(0))
    expect(seriesDrawn()).toEqual(unsorted)
  })
})

// the value details' rows as one list: a group's parameter and dataset with each station's numbers
function detailsRows(viewer: Awaited<ReturnType<typeof mountDataViewer>>['viewer']) {
  const { valueDetails } = viewer.vm as unknown as { valueDetails: { groups: { parameter: string, dataset: string, rows: { count: number, min: number | null, max: number | null, mean: number | null, sum: number | null }[] }[] } }
  return valueDetails.groups.flatMap(({ parameter, dataset, rows }) => rows.map(({ count, min, max, mean, sum }) => ({ parameter, dataset, count, min, max, mean, sum })))
}

describe('dataViewer parameter statistics of rows that are not long values', () => {
  function stats(viewer: Awaited<ReturnType<typeof mountDataViewer>>['viewer']) {
    return detailsRows(viewer)
  }

  it('takes none of a wide-shaped table, where it showed one row for an undefined parameter', async () => {
    const wide = { station_id: '01048', resolution: 'daily', dataset: 'climate_summary', timestamp: '2020-01-01T00:00:00Z', temperature_air_mean_2m: 1.5, temperature_air_mean_2m_quality_flags: '10' }
    registerEndpoint('/api/values', () => ({ values: [wide] }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    await wrapper.vm.$nextTick()
    // the wide row is in the table, so it is the statistics that leave it out
    expect(wrapper.findAll('tbody tr')).toHaveLength(1)
    expect(wrapper.find('tbody').text()).toContain('1.5')
    expect(stats(viewer)).toEqual([])
  })

  it('takes a query\'s rows that carry a parameter and a value, and none of those with its own columns', async () => {
    registerEndpoint('/api/values', () => ({ values: [row] }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    await wrapper.vm.$nextTick()
    expect(stats(viewer)).toEqual([{ parameter: 'temperature_air_mean_2m', dataset: 'climate_summary', count: 1, min: 1.5, max: 1.5, mean: 1.5, sum: null }])
    const panel = wrapper.findComponent(QueryPanel)
    // `SELECT timestamp, parameter, AVG(value) AS avg_value FROM data GROUP BY timestamp, parameter`
    panel.vm.$emit('dataTransformed', [{ timestamp: '2020-01-01T00:00:00Z', parameter: 'temperature_air_mean_2m', avg_value: 1.5 }])
    await wrapper.vm.$nextTick()
    expect(stats(viewer)).toEqual([])
    // `SELECT parameter, value FROM data`: no dataset, a missing value counted as none, and a value
    // as text, `value::VARCHAR AS value`, left out
    panel.vm.$emit('dataTransformed', [{ parameter: 'precipitation_amount', value: 2 }, { parameter: 'precipitation_amount', value: 4 }, { parameter: 'wind_speed', value: null }, { parameter: 'wind_speed', value: '3' }, { parameter: 'humidity', value: '50' }])
    await wrapper.vm.$nextTick()
    expect(stats(viewer)).toEqual([
      { parameter: 'precipitation_amount', dataset: '', count: 2, min: 2, max: 4, mean: 3, sum: null },
      { parameter: 'wind_speed', dataset: '', count: 0, min: null, max: null, mean: null, sum: null },
    ])
  })

  it('takes a query\'s dataset of another type as its text, each its own', async () => {
    registerEndpoint('/api/values', () => ({ values: [row] }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    // `SELECT year(timestamp) AS dataset, parameter, value FROM data`
    wrapper.findComponent(QueryPanel).vm.$emit('dataTransformed', [{ dataset: 2019, parameter: 'wind_speed', value: 1 }, { dataset: 2020, parameter: 'wind_speed', value: 3 }])
    await wrapper.vm.$nextTick()
    expect(stats(viewer)).toEqual([
      { parameter: 'wind_speed', dataset: '2019', count: 1, min: 1, max: 1, mean: 1, sum: null },
      { parameter: 'wind_speed', dataset: '2020', count: 1, min: 3, max: 3, mean: 3, sum: null },
    ])
  })
})

describe('dataViewer chart image whose export fails', () => {
  // the step that fails: the rasterising of the single chart, of a facet's SVG as it is saved, or of the stacked SVG as
  // where it passes the browser's canvas size. Nothing was saved, unhandled, and nothing said so
  it.each([
    { faceted: false, format: 'PNG', item: 0 },
    { faceted: true, format: 'SVG', item: 2 },
    { faceted: true, format: 'PNG', item: 0 },
    { faceted: true, format: 'JPEG', item: 1 },
  ])('says the image could not be saved, faceted: $faceted, $format', async ({ faceted, item }) => {
    registerEndpoint('/api/values', () => ({ values: twoParameters }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    await showChart(wrapper, faceted)
    const failed = new Error('export failed')
    image.fail = failed
    const logged = vi.spyOn(console, 'error').mockImplementation(() => {})
    ;(await openDownloads(wrapper))[item]!.click()
    await vi.waitFor(() => expect(document.body.textContent).toContain('The chart image could not be saved'))
    expect(logged).toHaveBeenCalledWith('The chart image could not be saved', failed)
    expect(document.body.textContent).not.toContain('Chart downloaded')
    expect(image.downloads).toHaveLength(0)
  })
})

describe('dataViewer facets\' station colours', () => {
  // each facet's series as it was last drawn, each by its name and colour, by the facet's parameter
  function facetColours() {
    return Object.fromEntries([...facetsDrawn()].map(([facet, option]) => [facet, linesOf(option).map(series => [series.name, series.lineStyle.color])]))
  }

  const second = { ...row, station_id: '04411' }
  const precipitation = { ...row, parameter: 'precipitation_amount', value: 0.2 }
  const first = () => seriesColour(0, isDark())
  const next = () => seriesColour(1, isDark())

  it.each([
    // the first station has no precipitation: the second station was coloured first in that facet
    ['a facet lacks the first station', [row, second, { ...precipitation, station_id: '04411' }], () => [['04411', next()]]],
    // the second station's precipitation comes before the first's: it was coloured first in that facet
    ['a facet\'s rows come in another order', [row, second, { ...precipitation, station_id: '04411' }, precipitation], () => [['04411', next()], ['01048', first()]]],
  ])('gives each station one colour in every facet where %s', async (_, values, precipitationSeries) => {
    registerEndpoint('/api/values', () => ({ values }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    await wrapper.vm.$nextTick()
    forgetDrawings()
    await showChart(wrapper, true)
    await vi.waitFor(() => expect(Object.keys(facetColours())).toHaveLength(2))
    expect(facetColours()).toEqual({
      [airTemperature]: [['01048', first()], ['04411', next()]],
      [precipitationAmount]: precipitationSeries(),
    })
  })
})

describe('dataViewer parameter statistics of many values', () => {
  it('takes a parameter of more values than a call takes arguments, where it threw', async () => {
    registerEndpoint('/api/values', () => ({ values: [row] }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    // past V8's argument limit of about 120k, as 3 years of one station's 10-minute values
    const count = 200_000
    const rows = Array.from({ length: count }, (_, i) => ({ parameter: 'precipitation_amount', value: i - 100_000 }))
    wrapper.findComponent(QueryPanel).vm.$emit('dataTransformed', rows)
    await wrapper.vm.$nextTick()
    // the mean is the running sum over the count, so the sum is held to it; the rows of a query have no sum of their own
    const sum = (count * (count - 1)) / 2 - count * 100_000
    expect(detailsRows(viewer)).toEqual([
      { parameter: 'precipitation_amount', dataset: '', count, min: -100_000, max: 99_999, mean: sum / count, sum: null },
    ])
  })
})

// the value details by station (GH-4296): the stations of the request in the order listed, named, each with the numbers of its
// own values; the aggregation of the answer's own `metadata.parameters` says which parameter has a sum
describe('dataViewer value details by station', () => {
  const metadata = {
    parameters: [
      { resolution: 'daily', dataset: 'climate_summary', name: 'temperature_air_mean_2m', name_original: 'tmk', unit: '\u00B0C', aggregation: 'mean' },
      { resolution: 'daily', dataset: 'climate_summary', name: 'precipitation_amount', name_original: 'rsk', unit: 'mm', aggregation: 'sum' },
    ],
  }
  const at = (station_id: string, parameter: string, value: number | null, day = 1) => ({ ...row, station_id, parameter, value, timestamp: `2020-01-0${day}T00:00:00Z` })
  const stationsOf = (...ids: string[]): StationSelectionState => ({
    mode: 'station',
    selection: { stations: ids.map(id => ({ station_id: id, name: `Station ${id}` }) as Station) },
    interpolation: { source: 'manual' },
    dateRange: {},
  })
  interface Details { split: boolean, stations: { id: string, name: string | null }[], groups: { parameter: string, unit: string | null, sums: boolean, rows: { count: number, sum: number | null }[] }[] }
  const detailsOf = (viewer: Awaited<ReturnType<typeof mountDataViewer>>['viewer']) => (viewer.vm as unknown as { valueDetails: Details }).valueDetails

  it('asks for the answer\'s own facts of the parameters, and for nothing else of the download\'s query', async () => {
    const queries: Record<string, unknown>[] = []
    registerEndpoint('/api/values', (event) => {
      queries.push({ ...getQuery(event) })
      return { values: [row], metadata }
    })
    const { viewer } = await mountDataViewer()
    await fetchData(viewer)
    expect(queries).toHaveLength(1)
    expect(queries[0]!.with_metadata).toBe('true')
  })

  it('takes the stations of the request in the order listed, named, each of their own values, and a sum only where the parameter adds up', async () => {
    registerEndpoint('/api/values', () => ({
      values: [
        at('04411', 'temperature_air_mean_2m', 10),
        at('04411', 'precipitation_amount', 4),
        at('01048', 'temperature_air_mean_2m', 6),
        at('01048', 'precipitation_amount', 2, 1),
        at('01048', 'precipitation_amount', 3, 2),
      ],
      metadata,
    }))
    // 04411 is listed first, whatever the order of the rows
    const { viewer } = await mountDataViewer(ref(stationsOf('04411', '01048')))
    await fetchData(viewer)
    await flushPromises()
    const details = detailsOf(viewer)
    expect(details.split).toBe(true)
    expect(details.stations).toEqual([{ id: '04411', name: 'Station 04411' }, { id: '01048', name: 'Station 01048' }])
    const [rain, temperature] = details.groups
    expect(details.groups.map(group => [group.parameter, group.unit, group.sums])).toEqual([['precipitation_amount', 'mm', true], ['temperature_air_mean_2m', '\u00B0C', false]])
    expect(rain!.rows.map(({ count, sum }) => [count, sum])).toEqual([[1, 4], [2, 5]])
    expect(temperature!.rows.map(({ count, sum }) => [count, sum])).toEqual([[1, null], [1, null]])
  })

  it('keeps the stations of the request as they were asked for, where the selection moves on while the table stays', async () => {
    registerEndpoint('/api/values', () => ({ values: [at('04411', 'precipitation_amount', 1), at('01048', 'precipitation_amount', 2)], metadata }))
    const selection = ref(stationsOf('04411', '01048'))
    const { viewer } = await mountDataViewer(selection)
    await fetchData(viewer)
    selection.value = stationsOf('01048', '04411')
    await flushPromises()
    expect(detailsOf(viewer).stations.map(({ id }) => id)).toEqual(['04411', '01048'])
  })

  it('lists a station that has no value, with none, where the other has some', async () => {
    registerEndpoint('/api/values', () => ({ values: [at('04411', 'precipitation_amount', 1)], metadata }))
    const { viewer } = await mountDataViewer(ref(stationsOf('04411', '01048')))
    await fetchData(viewer)
    const [rain] = detailsOf(viewer).groups
    expect(rain!.rows.map(({ count }) => count)).toEqual([1, 0])
  })

  it('shows no sum of a window longer than the rows, by the resolution the answer states', async () => {
    const hourly = { resolution: 'hourly', dataset: 'climate_summary', unit: 'mm', aggregation: 'sum' }
    registerEndpoint('/api/values', () => ({
      values: [at('01048', 'precipitation_amount_last_6h', 1), at('01048', 'precipitation_amount_last_1h', 2)],
      metadata: { parameters: [{ ...hourly, name: 'precipitation_amount_last_6h' }, { ...hourly, name: 'precipitation_amount_last_1h' }] },
    }))
    const { viewer } = await mountDataViewer()
    await fetchData(viewer)
    expect(detailsOf(viewer).groups.map(group => [group.parameter, group.sums, group.rows[0]!.sum])).toEqual([['precipitation_amount_last_1h', true, 2], ['precipitation_amount_last_6h', false, null]])
  })

  it('gives rows the query panel has rewritten no unit and no sum, whatever the query did to `value`', async () => {
    registerEndpoint('/api/values', () => ({ values: [at('01048', 'precipitation_amount', 4), at('01048', 'precipitation_amount', 6)], metadata }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    expect(detailsOf(viewer).groups.map(group => [group.unit, group.sums, group.rows[0]!.sum])).toEqual([['mm', true, 10]])
    // `SELECT station_id, dataset, parameter, value / 25.4 AS value FROM data`, the rain in inches
    wrapper.findComponent(QueryPanel).vm.$emit('dataTransformed', [at('01048', 'precipitation_amount', 4 / 25.4), at('01048', 'precipitation_amount', 6 / 25.4)])
    await wrapper.vm.$nextTick()
    expect(detailsOf(viewer).groups.map(group => [group.unit, group.sums, group.rows[0]!.sum, group.rows[0]!.count])).toEqual([[null, false, null, 2]])
  })

  it.each(['interpolation', 'summary'] as const)('takes a %s as one series, with no station', async (mode) => {
    registerEndpoint(mode === 'interpolation' ? '/api/interpolate' : '/api/summarize', () => ({
      values: [at('', 'precipitation_amount', 2), at('', 'precipitation_amount', 3, 2)],
      metadata,
    }))
    const { viewer } = await mountDataViewer(ref(atPoint(mode)))
    await fetchData(viewer)
    const details = detailsOf(viewer)
    expect(details.split).toBe(false)
    expect(details.groups).toHaveLength(1)
    expect(details.groups[0]!.rows.map(({ count, sum }) => [count, sum])).toEqual([[2, 5]])
  })
})

describe('dataViewer trendline of many points', () => {
  it('draws the trendline of a series of more points than a call takes arguments, where it threw', async () => {
    // past V8's argument limit of about 120k, as 3 years of one station's 10-minute values, each
    // ten minutes on and one more than the last
    const count = 200_000
    const start = Date.UTC(2020, 0, 1)
    const rows = Array.from({ length: count }, (_, i) => ({ ...row, timestamp: new Date(start + i * 600_000).toISOString(), value: i }))
    forgetDrawings()
    const { wrapper } = await withChartQuery(rows)
    await showChart(wrapper, false)
    await toggleTrendline(wrapper)
    // each drawing sorts every point, which a busy runner can take a while over
    await vi.waitFor(() => expect(linesOf(lastDrawn().option)).toHaveLength(2), { timeout: 10_000 })
    const [, trend] = linesOf(lastDrawn().option)
    expect(trend.data.map((point: [number, number]) => point[0])).toEqual([start, start + (count - 1) * 600_000])
    expect(trend.data[0][1]).toBeCloseTo(0, 0)
    expect(trend.data[1][1]).toBeCloseTo(count - 1, 0)
  }, 30_000)
})

describe('dataViewer failed fetch', () => {
  // each mode's endpoint, all of which the REST API answers with a 500 where it or the source failed
  it.each([
    ['/api/values', byStation('01048')],
    ['/api/interpolate', atPoint('interpolation')],
    ['/api/summarize', atPoint('summary')],
  ] as const)('asks %s once for a request answered with a 500, and tells its error', async (endpoint, selection) => {
    // counted at the endpoint, which a request reaches however it is made
    let asked = 0
    registerEndpoint(endpoint, (event) => {
      asked++
      setResponseStatus(event, 500)
      return { detail: 'Upstream failed' }
    })
    const { viewer } = await mountDataViewer(ref(selection))
    await fetchData(viewer)
    await vi.waitFor(() => expect(document.body.textContent).toContain('Upstream failed'))
    expect(asked).toBe(1)
  })

  it('asks once more where the proxy could not reach the backend, and shows what that answer brings', async () => {
    // a 502 the first time only, as a proxy gives while the backend restarts
    let asked = 0
    registerEndpoint('/api/values', (event) => {
      asked++
      if (asked === 1) {
        setResponseStatus(event, 502)
        return { detail: 'connect ECONNREFUSED' }
      }
      return { values: [row] }
    })
    const { viewer } = await mountDataViewer()
    await fetchData(viewer)
    await vi.waitFor(() => expect((viewer.vm as any).valuesData.values).toHaveLength(1))
    expect(asked).toBe(2)
    expect(document.body.textContent).not.toContain('ECONNREFUSED')
  })

  it('tells the error of a 502 its one retry gets again', async () => {
    let asked = 0
    registerEndpoint('/api/values', (event) => {
      asked++
      setResponseStatus(event, 502)
      return { detail: 'connect ECONNREFUSED' }
    })
    const { viewer } = await mountDataViewer()
    await fetchData(viewer)
    await vi.waitFor(() => expect(document.body.textContent).toContain('ECONNREFUSED'))
    expect(asked).toBe(2)
    expect((viewer.vm as any).valuesStatus).toBe('error')
  })
})

describe('dataViewer nearby station distance', () => {
  // the backend reads it for an interpolation only, and deprecates it for a summary (GH-2333)
  it.each([
    ['/api/interpolate', atPoint('interpolation'), '1'],
    ['/api/summarize', atPoint('summary'), undefined],
  ] as const)('%s is sent use_nearby_station_distance=%s', async (endpoint, selection, sent) => {
    const asked: Record<string, unknown>[] = []
    registerEndpoint(endpoint, (event) => {
      asked.push(getQuery(event))
      return { values: [] }
    })
    const { viewer } = await mountDataViewer(ref(selection))
    await fetchData(viewer)
    await vi.waitFor(() => expect(asked).toHaveLength(1))
    expect(asked[0]!.use_nearby_station_distance).toBe(sent)
  })
})

describe('dataViewer unit targets and names are the app settings\' (GH-3878)', () => {
  // the viewer's one request, given the Explorer's own settings (a link's choice of the names and units, if any)
  async function askedWith(endpoint: string, selection: StationSelectionState, own: Partial<DataSettings> = {}) {
    const asked: Record<string, unknown>[] = []
    registerEndpoint(endpoint, (event) => {
      asked.push(getQuery(event))
      return { values: [] }
    })
    const wrapper = await mountSuspended(defineComponent({
      setup: () => () => h(UApp, null, {
        default: () => h(DataViewer, { parameterSelection, stationSelection: selection, settings: { ...settings, ...own } }),
      }),
    }), { attachTo: document.body })
    mounted.push(wrapper)
    await fetchData(wrapper.findComponent(DataViewer))
    await vi.waitFor(() => expect(asked).toHaveLength(1))
    return asked[0]!
  }
  const unitTargetsAsked = async (endpoint: string, selection: StationSelectionState) =>
    JSON.parse(String((await askedWith(endpoint, selection)).unit_targets))

  // the app settings are one store of the whole page: a test that changes them puts them back
  afterEach(() => {
    useSettings().reset()
  })

  // each mode's endpoint, all of which take unit targets and merge the server's WD_TS_UNIT_TARGETS into them
  it.each([
    ['/api/values', byStation('01048')],
    ['/api/interpolate', atPoint('interpolation')],
    ['/api/summarize', atPoint('summary')],
  ] as const)('asks %s for every type the settings page lists, in the unit the settings hold', async (endpoint, selection) => {
    const targets = await unitTargetsAsked(endpoint, selection)
    expect(targets).toEqual(SETTINGS_DEFAULTS.units)
    // the eight types the Explorer's own picker had, in the units its "Default (...)" named
    expect(targets).toMatchObject({
      temperature: 'degree_celsius',
      speed: 'meter_per_second',
      pressure: 'hectopascal',
      precipitation: 'millimeter',
      precipitation_intensity: 'millimeter_per_hour',
      length_short: 'centimeter',
      length_medium: 'meter',
      length_long: 'kilometer',
    })
  })

  it.each([
    ['/api/values', byStation('01048')],
    ['/api/interpolate', atPoint('interpolation')],
    ['/api/summarize', atPoint('summary')],
  ] as const)('asks %s for the units chosen on the settings page', async (endpoint, selection) => {
    const { settings: app } = useSettings()
    app.value.units.temperature = 'degree_fahrenheit'
    app.value.units.length_long = 'mile'
    app.value.units.conductivity = 'siemens_per_meter'
    expect(await unitTargetsAsked(endpoint, selection))
      .toEqual({ ...SETTINGS_DEFAULTS.units, temperature: 'degree_fahrenheit', length_long: 'mile', conductivity: 'siemens_per_meter' })
  })

  it('asks for a type\'s default where the settings hold a unit that is not on its list', async () => {
    useSettings().settings.value.units.speed = 'furlong'
    expect((await unitTargetsAsked('/api/values', byStation('01048'))).speed).toBe('meter_per_second')
  })

  it('sends the readable names and the unit conversion of the app settings', async () => {
    const query = await askedWith('/api/values', byStation('01048'))
    expect(query).toMatchObject({ humanize: 'true', convert_units: 'true' })
  })

  it('sends what the settings page holds at the next request, after it was changed', async () => {
    const { settings: app } = useSettings()
    app.value.friendlyLabels = false
    app.value.convertUnits = false
    const query = await askedWith('/api/values', byStation('01048'))
    expect(query).toMatchObject({ humanize: 'false', convert_units: 'false' })
  })

  it('sends a link\'s own choice of the names and units over the app settings, each on its own', async () => {
    const { settings: app } = useSettings()
    app.value.friendlyLabels = false
    app.value.convertUnits = true
    const query = await askedWith('/api/values', byStation('01048'), { humanize: true })
    expect(query).toMatchObject({ humanize: 'true', convert_units: 'true' })
    // a second request, with the other one given
    mounted.splice(0).forEach(wrapper => wrapper.unmount())
    app.value.convertUnits = true
    const other = await askedWith('/api/values', byStation('01048'), { convertUnits: false })
    expect(other).toMatchObject({ humanize: 'false', convert_units: 'false' })
  })
})

describe('dataViewer settings the explorer starts from the server\'s', () => {
  // the viewer's one request
  async function asked(endpoint: string, selection: StationSelectionState) {
    const queries: Record<string, unknown>[] = []
    registerEndpoint(endpoint, (event) => {
      queries.push(getQuery(event))
      return { values: [] }
    })
    const wrapper = await mountSuspended(defineComponent({
      setup: () => () => h(UApp, null, {
        default: () => h(DataViewer, {
          parameterSelection,
          stationSelection: selection,
          settings,
        }),
      }),
    }), { attachTo: document.body })
    mounted.push(wrapper)
    await fetchData(wrapper.findComponent(DataViewer))
    await vi.waitFor(() => expect(queries).toHaveLength(1))
    return queries[0]!
  }

  // sent at wetterdienst's own too: one left out would be the server's WD_TS_GEO_STATION_DISTANCE_*,
  // not the one the explorer shows (GH-2359)
  it.each([
    ['/api/interpolate', atPoint('interpolation'), 'interpolation'],
    ['/api/summarize', atPoint('summary'), 'summary'],
  ] as const)('asks %s for both radii at their defaults', async (endpoint, selection, prefix) => {
    const query = await asked(endpoint, selection)
    expect(query[`${prefix}_station_distance_homogeneous`]).toBe('40')
    expect(query[`${prefix}_station_distance_heterogeneous`]).toBe('20')
  })

  it('leaves out a radius the server holds as infinite, so that the server\'s applies', async () => {
    const queries: Record<string, unknown>[] = []
    registerEndpoint('/api/interpolate', (event) => {
      queries.push(getQuery(event))
      return { values: [] }
    })
    const wrapper = await mountSuspended(defineComponent({
      setup: () => () => h(UApp, null, {
        default: () => h(DataViewer, {
          parameterSelection,
          stationSelection: atPoint('interpolation'),
          settings: { ...settings, stationDistanceHomogeneous: Number.POSITIVE_INFINITY },
        }),
      }),
    }), { attachTo: document.body })
    mounted.push(wrapper)
    await fetchData(wrapper.findComponent(DataViewer))
    await vi.waitFor(() => expect(queries).toHaveLength(1))
    expect(queries[0]).not.toHaveProperty('interpolation_station_distance_homogeneous')
    expect(queries[0]!.interpolation_station_distance_heterogeneous).toBe('20')
  })

  // a cleared per-parameter input is NaN, which JSON writes as null and the backend answers with a
  // 422 (GH-3356): the parameter is left out, the others are sent
  describe.each([
    ['/api/interpolate', atPoint('interpolation'), 'interpolation'],
    ['/api/summarize', atPoint('summary'), 'summary'],
  ] as const)('a cleared per-parameter radius for %s', (endpoint, selection, prefix) => {
    async function askedWith(perParameter: Record<string, number>) {
      const queries: Record<string, unknown>[] = []
      registerEndpoint(endpoint, (event) => {
        queries.push(getQuery(event))
        return { values: [] }
      })
      const wrapper = await mountSuspended(defineComponent({
        setup: () => () => h(UApp, null, {
          default: () => h(DataViewer, {
            parameterSelection,
            stationSelection: selection,
            settings: { ...settings, useStationDistancePerParameter: perParameter },
          }),
        }),
      }), { attachTo: document.body })
      mounted.push(wrapper)
      await fetchData(wrapper.findComponent(DataViewer))
      await vi.waitFor(() => expect(queries).toHaveLength(1))
      return queries[0]!
    }

    it('is left out, and the others are sent', async () => {
      const query = await askedWith({ temperature_air_mean_2m: Number.NaN, precipitation_height: 15 })
      expect(JSON.parse(String(query[`${prefix}_station_distance`]))).toEqual({ precipitation_height: 15 })
    })

    it('leaves the whole field out when it is the only one', async () => {
      const query = await askedWith({ temperature_air_mean_2m: Number.NaN })
      expect(query).not.toHaveProperty(`${prefix}_station_distance`)
    })
  })
})

describe('dataViewer chart names', () => {
  // the charts the page shows, by the role and the name a screen reader announces them with
  const figures = () => [...document.body.querySelectorAll('[role="figure"]')].map(figure => [figure.getAttribute('role'), figure.getAttribute('aria-label')])

  it('names the single chart, as a figure', async () => {
    registerEndpoint('/api/values', () => ({ values: twoParameters }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    await showChart(wrapper, false)
    await vi.waitFor(() => expect(drawings()).toHaveLength(1))
    expect(figures()).toEqual([['figure', 'Chart of the values']])
  })

  it('names each facet by its parameter, as a figure', async () => {
    registerEndpoint('/api/values', () => ({ values: twoParameters }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    await showChart(wrapper, true)
    await vi.waitFor(() => expect(drawings()).toHaveLength(2))
    expect(figures()).toEqual([
      ['figure', `Chart of ${airTemperature}`],
      ['figure', `Chart of ${precipitationAmount}`],
    ])
  })
})

describe('dataViewer date range', () => {
  // the backend's single-span parameter is `timestamp`, and it refuses `date`, its old name (GH-2438)
  it.each([
    ['/api/values', byStation('01048')],
    ['/api/interpolate', atPoint('interpolation')],
    ['/api/summarize', atPoint('summary')],
  ] as const)('asks %s for the date range as timestamp', async (endpoint, selection) => {
    const asked: Record<string, unknown>[] = []
    registerEndpoint(endpoint, (event) => {
      asked.push(getQuery(event))
      return { values: [] }
    })
    const { viewer } = await mountDataViewer(ref({ ...selection, dateRange: { startDate: '2020-01-01', endDate: '2020-01-31' } }))
    await fetchData(viewer)
    await vi.waitFor(() => expect(asked).toHaveLength(1))
    expect(asked[0]!.timestamp).toBe('2020-01-01/2020-01-31')
    expect(asked[0]).not.toHaveProperty('date')
  })
})

// A parameter with a long id, which the glossary names in every locale: the label the page showed
// instead was the id prettified, "Wind Direction Mean Last 10min" (GH-2865). The chart's legend and the
// facets took the raw id from the rows, so each place the viewer names a parameter, a dataset or a
// resolution is drawn here in a locale that is not English, and must say what that locale's
// glossary says
describe('dataViewer names what it shows in the active locale', () => {
  const longId = { resolution: '10_minutes', dataset: 'urban_wind', parameter: 'wind_direction_mean_last_10min' }
  const direction = { ...row, ...longId }
  const speed = { ...direction, parameter: 'wind_speed_mean_last_10min', value: 2.5 }

  // what each locale's glossary says of the ids above, spelled out rather than read from the
  // glossary the page is held to
  const names = {
    de: { resolution: 'Alle 10 Minuten', dataset: 'Stadtklima: Wind', direction: 'Mittlere Windrichtung (letzte 10 min)', speed: 'Mittlere Windgeschwindigkeit (letzte 10 min)' },
    fr: { resolution: 'Toutes les 10 minutes', dataset: 'Vent urbain', direction: 'Direction moyenne du vent (10 dernières min)', speed: 'Vitesse moyenne du vent (10 dernières min)' },
    pl: { resolution: 'Co 10 minut', dataset: 'Wiatr miejski', direction: 'Średni kierunek wiatru (ostatnie 10 min)', speed: 'Średnia prędkość wiatru (ostatnie 10 min)' },
  }
  const locales = Object.keys(names) as (keyof typeof names)[]
  // `dataViewer.facetChartLabel` of each
  const chartOf = {
    de: (parameter: string) => `Diagramm von ${parameter}`,
    fr: (parameter: string) => `Graphique de ${parameter}`,
    pl: (parameter: string) => `Wykres: ${parameter}`,
  }

  // the three formats the viewer names a parameter in, with the parts each is made of
  const formats = [
    { format: 'parameter', parts: (n: typeof names.de, parameter: string) => [parameter] },
    { format: 'dataset/parameter', parts: (n: typeof names.de, parameter: string) => [n.dataset, parameter] },
    { format: 'resolution/dataset/parameter', parts: (n: typeof names.de, parameter: string) => [n.resolution, n.dataset, parameter] },
  ]

  async function setLocale(locale: string) {
    const harness = await mountSuspended(defineComponent({
      setup: () => ({ setLocale: useI18n().setLocale }),
      render: () => h('div'),
    }))
    await (harness.vm as unknown as { setLocale: (locale: string) => Promise<void> }).setLocale(locale)
    harness.unmount()
  }

  afterEach(async () => {
    await setLocale('en')
  })

  async function mountIn(locale: string, faceted: boolean, rows: unknown[] = [direction, speed]) {
    registerEndpoint('/api/values', () => ({ values: rows }))
    await setLocale(locale)
    const mountedViewer = await mountDataViewer()
    await fetchData(mountedViewer.viewer)
    // the checkbox is found by its English text, so facets are asked for through the viewer itself
    await showChart(mountedViewer.wrapper, false)
    const vm = mountedViewer.viewer.vm as unknown as { paramLabelFormat: string, facetByParameter: boolean }
    if (faceted)
      forgetDrawings()
    vm.facetByParameter = faceted
    await flushPromises()
    const choose = async (format: string) => {
      vm.paramLabelFormat = format
      await flushPromises()
    }
    return { ...mountedViewer, choose }
  }

  // the id of the row in any form: raw, or prettified as the fallback does
  function idsIn(text: string) {
    return ['wind_direction_mean_last_10min', 'wind_speed_mean_last_10min', 'urban_wind', '10_minutes', 'Wind Direction Mean Last 10min', 'Wind Speed Mean Last 10min', 'Urban Wind', '10 Minutes'].filter(id => text.includes(id))
  }

  describe.each(locales)('in %s', (locale) => {
    const n = names[locale]

    it.each(formats)('names the single chart\'s series by their labels, format $format', async ({ format, parts }) => {
      const { choose } = await mountIn(locale, false)
      await choose(format)
      const drawn = () => linesOf(lastDrawn().option).map(series => series.name)
      await vi.waitFor(() => expect(drawn()).toEqual([n.direction, n.speed].map(parameter => `01048 - ${parts(n, parameter).join(' / ')}`)))
      expect(idsIn(drawn().join('\n'))).toEqual([])
    })

    it.each(formats)('names each facet by its labels, as heading and figure, and gives it no axis title, format $format', async ({ format, parts }) => {
      const { wrapper, choose } = await mountIn(locale, true)
      await choose(format)
      const label = (parameter: string) => parts(n, parameter).join(' / ')
      // the last two draws are the two facets of the format chosen: the chart has no axis title, which the heading is
      const drawn = () => drawings().slice(-2).map(({ option }) => option as { yAxis: { name?: unknown }[] })
      await vi.waitFor(() => expect(drawn()).toHaveLength(2))
      expect(drawn().map(option => option.yAxis[0]!.name)).toEqual([undefined, undefined])
      expect(wrapper.findAll('h4').map(heading => heading.text())).toEqual([label(n.direction), label(n.speed)])
      expect(wrapper.findAll('[role="figure"]').map(figure => figure.attributes('aria-label'))).toEqual([n.direction, n.speed].map(parameter => chartOf[locale](label(parameter))))
      expect(idsIn(wrapper.text())).toEqual([])
    })
  })

  // a day's row each of the two parameters, from 2020-01-01 on: each series long enough for a trendline
  const twoDays = [direction, speed, { ...direction, timestamp: '2020-01-02T00:00:00Z', value: 2.5 }, { ...speed, timestamp: '2020-01-02T00:00:00Z', value: 3.5 }]
  // `dataViewer.trendline` of each, spelled out
  const trendline = { de: 'Trendlinie', fr: 'Ligne de tendance', pl: 'Linia trendu' }

  // the trendline's name was `${name} (trend)` in every language (GH-2869)
  describe.each(locales)('with the trendline in %s', (locale) => {
    it('names the single chart\'s trendlines for their series, in the language', async () => {
      const { viewer } = await mountIn(locale, false, twoDays)
      ;(viewer.vm as unknown as { showTrendline: boolean }).showTrendline = true
      const drawn = () => linesOf(lastDrawn().option).map(series => series.name)
      const series = [names[locale].direction, names[locale].speed].map(parameter => `01048 - ${parameter}`)
      await vi.waitFor(() => expect(drawn()).toEqual([...series, ...series.map(name => `${name} (${trendline[locale]})`)]))
    })

    it('names each facet\'s trendline for its station, in the language', async () => {
      const { viewer } = await mountIn(locale, true, twoDays)
      ;(viewer.vm as unknown as { showTrendline: boolean }).showTrendline = true
      // one trace of the station and one trendline in each of the two facets drawn last
      const drawn = () => drawings().slice(-2).map(({ option }) => linesOf(option).map(series => series.name))
      await vi.waitFor(() => expect(drawn()).toEqual([['01048', `01048 (${trendline[locale]})`], ['01048', `01048 (${trendline[locale]})`]]))
    })
  })

  it('names the trendline in English as before where the language is English', async () => {
    const { viewer } = await mountIn('en', false, twoDays)
    ;(viewer.vm as unknown as { showTrendline: boolean }).showTrendline = true
    const drawn = () => linesOf(lastDrawn().option).map(series => series.name)
    await vi.waitFor(() => expect(drawn()).toContain('01048 - Mean wind direction (last 10 min) (Trendline)'))
  })

  it('names the chart again where the language is changed while it is shown', async () => {
    await mountIn('en', false)
    const drawn = () => linesOf(lastDrawn().option).map(series => series.name)
    await vi.waitFor(() => expect(drawn()).toEqual(['01048 - Mean wind direction (last 10 min)', '01048 - Mean wind speed (last 10 min)']))
    await setLocale('de')
    await vi.waitFor(() => expect(drawn()).toEqual([`01048 - ${names.de.direction}`, `01048 - ${names.de.speed}`]))
  })

  // "Plain-language labels" off: the ids as the API names them, joined by "/", where they were drawn
  // so before the labels
  describe('with plain-language labels off', () => {
    afterEach(() => {
      useSettings().reset()
    })

    it.each([
      { format: 'parameter', ids: ['wind_direction_mean_last_10min', 'wind_speed_mean_last_10min'] },
      { format: 'dataset/parameter', ids: ['urban_wind/wind_direction_mean_last_10min', 'urban_wind/wind_speed_mean_last_10min'] },
      { format: 'resolution/dataset/parameter', ids: ['10_minutes/urban_wind/wind_direction_mean_last_10min', '10_minutes/urban_wind/wind_speed_mean_last_10min'] },
    ])('keeps the ids in the series and the facets, format $format', async ({ format, ids }) => {
      useSettings().settings.value.friendlyLabels = false
      const single = await mountIn('de', false)
      await single.choose(format)
      const drawn = () => linesOf(lastDrawn().option).map(series => series.name)
      await vi.waitFor(() => expect(drawn()).toEqual(ids.map(id => `01048 - ${id}`)))
      single.wrapper.unmount()

      const faceted = await mountIn('de', true)
      await faceted.choose(format)
      await vi.waitFor(() => expect(drawings().length).toBeGreaterThanOrEqual(2))
      expect(faceted.wrapper.findAll('h4').map(heading => heading.text())).toEqual(ids)
      expect(faceted.wrapper.findAll('[role="figure"]').map(figure => figure.attributes('aria-label'))).toEqual(ids.map(id => chartOf.de(id)))
    })
  })
})

describe('dataViewer chart numbers in the active locale', () => {
  async function setLocale(locale: string) {
    const harness = await mountSuspended(defineComponent({
      setup: () => ({ setLocale: useI18n().setLocale }),
      render: () => h('div'),
    }))
    await (harness.vm as unknown as { setLocale: (locale: string) => Promise<void> }).setLocale(locale)
    harness.unmount()
  }

  afterEach(async () => {
    await setLocale('en')
  })

  // how the axis of the chart last drawn writes 1.5 (the value of the rows), single or faceted
  const axisWrites = () => lastDrawn().option.yAxis[0].axisLabel.formatter(1.5)
  // and how the readout writes it
  const readoutWrites = async () => {
    const stage = document.body.querySelector<HTMLElement>('.xc-stage')!
    stage.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true, cancelable: true }))
    await flushPromises()
    return document.body.querySelector('[data-testid="explorer-readout"] dd')!.textContent!.trim()
  }

  it.each([
    ['en', '1.5'],
    ['de', '1,5'],
    ['fr', '1,5'],
    ['pl', '1,5'],
  ])('draws the single chart and the facets with the decimal separator of %s', async (locale, written) => {
    registerEndpoint('/api/values', () => ({ values: twoParameters }))
    await setLocale(locale)
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    await showChart(wrapper, false)
    await vi.waitFor(() => expect(drawings().length).toBeGreaterThan(0))
    expect(axisWrites()).toBe(written)
    expect(await readoutWrites()).toBe(written)

    const vm = viewer.vm as unknown as { facetByParameter: boolean }
    forgetDrawings()
    vm.facetByParameter = true
    await flushPromises()
    await vi.waitFor(() => expect(facetsDrawn().size).toBe(2))
    // each facet has the digits its own axis needs (the precipitation's steps are hundredths): the separator is the language's
    for (const option of facetsDrawn().values())
      expect(option.yAxis[0].axisLabel.formatter(1.5)).toMatch(new RegExp(`^${written.replace('.', '\\.')}0*$`))
  })

  it('draws the chart again in the locale it is switched to', async () => {
    registerEndpoint('/api/values', () => ({ values: [row] }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    await showChart(wrapper, false)
    await vi.waitFor(() => expect(drawings().length).toBeGreaterThan(0))
    // the one value has an axis of hundredths, written with the language's separator
    expect(axisWrites()).toMatch(/^1\.50?$/)

    await setLocale('de')
    await vi.waitFor(() => expect(axisWrites()).toMatch(/^1,50?$/))
  })
})

describe('dataViewer charts at the end of the viewer, and where they go while it stays', () => {
  // the ECharts instance of a chart holds the window's `resize` observer and its SVG until it is disposed
  it('draws no chart, and loads no chart code, while the table is shown', async () => {
    registerEndpoint('/api/values', () => ({ values: twoParameters }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    await flushPromises()
    expect(wrapper.exists()).toBe(true)
    expect(echarts.init).not.toHaveBeenCalled()
  })

  it('disposes the single chart where the viewer goes', async () => {
    registerEndpoint('/api/values', () => ({ values: twoParameters }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    await showChart(wrapper, false)
    await vi.waitFor(() => expect(echarts.instances).toHaveLength(1))
    const [chart] = echarts.instances
    wrapper.unmount()
    expect(chart!.dispose).toHaveBeenCalled()
  })

  it('disposes every facet where the viewer goes', async () => {
    registerEndpoint('/api/values', () => ({ values: twoParameters }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    await showChart(wrapper, true)
    await vi.waitFor(() => expect(echarts.instances).toHaveLength(2))
    const facets = [...echarts.instances]
    wrapper.unmount()
    for (const facet of facets)
      expect(facet.dispose).toHaveBeenCalled()
  })

  it('disposes the single chart where the table is shown in its place', async () => {
    registerEndpoint('/api/values', () => ({ values: twoParameters }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    await showChart(wrapper, false)
    await vi.waitFor(() => expect(echarts.instances).toHaveLength(1))
    const [chart] = echarts.instances
    ;(viewer.vm as unknown as { viewMode: string }).viewMode = 'table'
    await flushPromises()
    expect(chart!.el.isConnected).toBe(false)
    expect(chart!.dispose).toHaveBeenCalled()
  })

  it('disposes the single chart where the facets take its place, and the facets where it comes back', async () => {
    registerEndpoint('/api/values', () => ({ values: twoParameters }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    await showChart(wrapper, false)
    await vi.waitFor(() => expect(echarts.instances).toHaveLength(1))
    const [single] = echarts.instances
    const vm = viewer.vm as unknown as { facetByParameter: boolean }
    vm.facetByParameter = true
    await flushPromises()
    await vi.waitFor(() => expect(echarts.instances).toHaveLength(3))
    expect(single!.dispose).toHaveBeenCalled()

    const facets = echarts.instances.slice(1)
    vm.facetByParameter = false
    await flushPromises()
    for (const facet of facets)
      expect(facet.dispose).toHaveBeenCalled()
  })

  it('disposes the facets of parameters an answer no longer has', async () => {
    registerEndpoint('/api/values', () => ({ values: twoParameters }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    ;(viewer.vm as unknown as { facetByParameter: boolean }).facetByParameter = true
    ;(viewer.vm as unknown as { viewMode: string }).viewMode = 'graph'
    await flushPromises()
    await vi.waitFor(() => expect(echarts.instances).toHaveLength(2))
    const facets = [...echarts.instances]
    // another answer, of one parameter only
    registerEndpoint('/api/values', () => ({ values: [row] }))
    await fetchData(viewer)
    await flushPromises()
    expect(wrapper.exists()).toBe(true)
    expect(facets[1]!.dispose).toHaveBeenCalled()
  })
})
