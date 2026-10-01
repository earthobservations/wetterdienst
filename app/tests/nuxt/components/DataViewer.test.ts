import type { DataSettings } from '~/types/data-settings.type'
import type { ParameterSelection } from '~/types/parameter-selection-state.type'
import type { StationSelectionState } from '~/types/station-selection-state.type'
import { mockNuxtImport, mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { getQuery, setResponseStatus } from 'h3'
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest'
import { defineComponent, h, ref } from 'vue'
import { UApp, USelectMenu } from '#components'
import { useToast } from '#imports'
import DataViewer from '~/components/DataViewer.vue'
import QueryPanel from '~/components/QueryPanel.vue'

// DuckDB, as far as Run Query reaches it: the query itself is answered by the test's `answer`, as the
// Arrow table DuckDB gives, every statement loading the table at once. It gives no result schema,
// which the check of an edited query reads
const duckdb = vi.hoisted(() => ({ answer: async (_sql: string): Promise<Record<string, unknown>[]> => [] }))
vi.mock('@duckdb/duckdb-wasm', () => ({
  getJsDelivrBundles: () => ({}),
  selectBundle: async () => ({ mainWorker: 'worker.js', mainModule: 'duckdb.wasm', pthreadWorker: null }),
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

// Plotly draws nothing in the test's document: each chart it is handed is known by its y axis' title,
// and exported as an SVG of its on-screen size that names it
const plotly = vi.hoisted(() => {
  const titles = new WeakMap<HTMLElement, string>()
  const draw = async (root: HTMLElement, _data: unknown, layout?: { yaxis?: { title?: unknown } }) => {
    titles.set(root, String(layout?.yaxis?.title))
  }
  return {
    newPlot: vi.fn(draw),
    react: vi.fn(draw),
    purge: vi.fn(),
    downloadImage: vi.fn(async () => 'chart'),
    toImage: vi.fn(async (root: HTMLElement) => `data:image/svg+xml,${encodeURIComponent(
      `<svg xmlns="http://www.w3.org/2000/svg" width="700" height="300"><text>${titles.get(root)}</text></svg>`,
    )}`),
    Snapshot: { svgToImg: vi.fn(async () => `data:image/png;base64,${btoa('png')}`) },
  }
})
vi.mock('plotly.js-basic-dist-min', () => plotly)

// Nuxt's reload of the page, for every test in the file: the test's document, whose address earlier
// tests' downloads have moved, does not take it
const { reloadNuxtApp } = vi.hoisted(() => ({ reloadNuxtApp: vi.fn() }))
mockNuxtImport('reloadNuxtApp', () => reloadNuxtApp)

const settings: DataSettings = {
  humanize: true,
  convertUnits: true,
  unitTargets: {},
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
  quality: null,
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
    return 'blob:download'
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
    // every column the rows carry, those the column picker hides by default included
    expect(text.split('\n')[0]).toBe('station_id,resolution,dataset,parameter,timestamp,value,quality')
    expect(text.split('\n')[1]).toContain('01048')
    expect(text.split('\n')[1]).toContain('1.5')
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
    const [header, line] = (await saved[0]!.text()).split('\n')
    expect(header).toContain('temperature_air_mean_2m')
    expect(line).toContain('1.5')
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
    expect(asked[0]!.station).toBe('01048')
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
      if (query.station === '04411')
        await newerHold.opened
      return { values: [{ ...row, station_id: String(query.station) }] }
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
    expect(asked[0]!.station).toBe('01048')
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
      return { values: [{ ...row, station_id: String(query.station) }] }
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
      if (query.station === '01048')
        await firstHold.opened
      return { values: [{ ...row, station_id: String(query.station) }] }
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
    expect(asked[0]!.station).toBe('04411')
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
      return { values: [{ ...row, station_id: String(query.station) }] }
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
    expect(asked[0]!.station).toBe('01048')
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
    expect(copied[0]!.split('\n')[0]).toBe('station_id,parameter,timestamp,value,quality')
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
        return { detail: [{ loc: ['query', 'station'], msg: 'Cannot be combined with name' }] }
      }
      return { values: [row] }
    })
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    const saved = catchDownload()
    const items = await openDownloads(wrapper)
    items[2]!.click()
    await vi.waitFor(() => expect(document.body.textContent).toContain('station: Cannot be combined with name'))
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
      const station = String(getQuery(event).station)
      if (station === '04411')
        await hold.opened
      return { values: rows(station === '04411' ? 40 : 500, station) }
    })
    const { wrapper, viewer, stationSelection } = await mountDataViewer()
    await fetchData(viewer)
    await wrapper.find('button[aria-label="Last Page"]').trigger('click')
    await vi.waitFor(() => expect(pageShown(wrapper).page).toBe('10'))
    stationSelection.value = byStation('04411')
    await wrapper.vm.$nextTick()
    const fetching = fetchData(viewer)
    // the pager goes back to the first page as Fetch is pressed, while the table waits for the answer
    await vi.waitFor(() => expect(pageShown(wrapper).page).toBe('1'))
    // the 500 rows' last page, moved to again while the 40 are fetched
    await wrapper.find('button[aria-label="Last Page"]').trigger('click')
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
    await wrapper.find('button[aria-label="Last Page"]').trigger('click')
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
    await wrapper.find('button[aria-label="Last Page"]').trigger('click')
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
    await wrapper.find('button[aria-label="Last Page"]').trigger('click')
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
    registerEndpoint('/api/values', event => ({ values: rows(3, String(getQuery(event).station)) }))
    // the worker DuckDB is started in, from a script made on the spot
    vi.stubGlobal('Worker', class {})
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:worker')
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {})
    const hold = gate()
    let asked = false
    duckdb.answer = async () => {
      asked = true
      await hold.opened
      // a quality of its own, as an Arrow table built from rows drops a column that is null in every one
      return rows(1, '01048').map(row => ({ ...row, value: 99, quality: 1 }))
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

  it('takes the columns of the station rows a Fetch replaces interpolated rows with', async () => {
    registerEndpoint('/api/interpolate', () => ({ values: pointModes[0].values }))
    registerEndpoint('/api/values', () => ({ values: [row] }))
    const { wrapper, viewer, stationSelection } = await mountDataViewer(ref(atPoint('interpolation')))
    await fetchData(viewer)
    stationSelection.value = byStation('01048')
    await wrapper.vm.$nextTick()
    await fetchData(viewer)
    await wrapper.vm.$nextTick()
    expect(picked(wrapper)).toEqual(['station_id', 'parameter', 'timestamp', 'value', 'quality'])
    expect(wrapper.findComponent(QueryPanel).props('expectedColumns')).toEqual(Object.keys(row))
  })

  // one column per parameter: none of them among the table's fixed columns
  const wide = { station_id: '01048', resolution: 'daily', dataset: 'climate_summary', timestamp: '2020-01-01T00:00:00Z', temperature_air_mean_2m: 1.5 }

  it('shows and copies the columns a wide-shaped table carries', async () => {
    registerEndpoint('/api/values', () => ({ values: [wide] }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    await wrapper.vm.$nextTick()
    // no empty parameter, value and quality, where the measurement was left out
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
    expect(headers(wrapper)).toEqual(['station_id', 'parameter', 'timestamp', 'value', 'quality'])
    panel.vm.$emit('dataTransformed', [{ parameter: 'temperature_air_mean_2m', avg_value: 3.5 }])
    await wrapper.vm.$nextTick()
    expect(headers(wrapper)).toEqual(['parameter'])
  })
})

// the graph view, faceted by parameter where asked, as its toggle and checkbox are clicked
async function showChart(wrapper: Awaited<ReturnType<typeof mountDataViewer>>['wrapper'], faceted: boolean) {
  await wrapper.findAll('button').find(button => button.find('[class~="i-lucide:chart-line"]').exists())!.trigger('click')
  if (faceted) {
    const label = wrapper.findAll('label').find(label => label.text() === 'Facet by parameter')!
    await wrapper.find(`#${label.attributes('for')}`).trigger('click')
  }
  await flushPromises()
}

// two parameters, a facet each
const twoParameters = [row, { ...row, parameter: 'precipitation_height', value: 0.2 }]

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

  it('saves the facets as one SVG, stacked in the order the page shows them', async () => {
    // it looked for the single chart, which faceting replaces, and saved nothing without a word
    registerEndpoint('/api/values', () => ({ values: twoParameters }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    await showChart(wrapper, true)
    const saved = catchDownload()
    ;(await openDownloads(wrapper))[2]!.click()
    await vi.waitFor(() => expect(saved).toHaveLength(1))
    const svg = new DOMParser().parseFromString(await saved[0]!.text(), 'image/svg+xml').documentElement
    expect([svg.getAttribute('width'), svg.getAttribute('height')]).toEqual(['700', '600'])
    const charts = [...svg.children].map(chart => [chart.getAttribute('y'), chart.textContent])
    expect(charts).toEqual([['0', 'temperature_air_mean_2m'], ['300', 'precipitation_height']])
    await vi.waitFor(() => expect(document.body.textContent).toContain('Chart downloaded as SVG'))
  })

  it('saves the facets it was chosen for when faceting is turned off before Plotly is at hand', async () => {
    // faceting was looked at again after awaiting Plotly, and the first facet saved as the single chart.
    // Plotly is loaded here already, so the wait is its cached promise's: the load itself is not held
    registerEndpoint('/api/values', () => ({ values: twoParameters }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    await showChart(wrapper, true)
    const saved = catchDownload()
    plotly.downloadImage.mockClear()
    ;(await openDownloads(wrapper))[2]!.click()
    // unticked before the download goes on past its await of Plotly
    const label = wrapper.findAll('label').find(label => label.text() === 'Facet by parameter')!
    ;(document.getElementById(label.attributes('for')!) as HTMLElement).click()
    await vi.waitFor(() => expect(document.body.textContent).toContain('Chart downloaded as SVG'))
    expect(plotly.downloadImage).not.toHaveBeenCalled()
    expect(saved).toHaveLength(1)
    const svg = new DOMParser().parseFromString(await saved[0]!.text(), 'image/svg+xml').documentElement
    expect(svg.children).toHaveLength(2)
  })

  it('saves the single chart through Plotly\'s own download', async () => {
    registerEndpoint('/api/values', () => ({ values: twoParameters }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    await showChart(wrapper, false)
    plotly.downloadImage.mockClear()
    ;(await openDownloads(wrapper))[1]!.click()
    await vi.waitFor(() => expect(document.body.textContent).toContain('Chart downloaded as JPEG'))
    expect(plotly.downloadImage).toHaveBeenCalledWith(expect.any(HTMLDivElement), expect.objectContaining({ format: 'jpeg', filename: 'chart' }))
  })

  it('saves the facets as one PNG, drawn from their stacked SVG', async () => {
    registerEndpoint('/api/values', () => ({ values: twoParameters }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    await showChart(wrapper, true)
    plotly.Snapshot.svgToImg.mockClear()
    const saved = catchDownload()
    ;(await openDownloads(wrapper))[0]!.click()
    await vi.waitFor(() => expect(saved).toHaveLength(1))
    expect(plotly.Snapshot.svgToImg).toHaveBeenCalledOnce()
    const [drawn] = plotly.Snapshot.svgToImg.mock.calls[0] as unknown as [{ svg: string, format: string, width: number, height: number }]
    expect([drawn.format, drawn.width, drawn.height]).toEqual(['png', 700, 600])
    expect(drawn.svg).toContain('precipitation_height')
    expect(saved[0]!.type).toBe('image/png')
    expect(await saved[0]!.text()).toBe('png')
    await vi.waitFor(() => expect(document.body.textContent).toContain('Chart downloaded as PNG'))
  })

  it.each([false, true])('says there is no chart where Clear emptied it after the menu was opened, faceted: %s', async (faceted) => {
    registerEndpoint('/api/values', () => ({ values: twoParameters }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    await showChart(wrapper, faceted)
    const saved = catchDownload()
    plotly.downloadImage.mockClear()
    const items = await openDownloads(wrapper)
    // chosen before the menu has updated, as from the explorer sidebar
    ;(viewer.vm as unknown as { clearData: () => void }).clearData()
    items[0]!.click()
    await vi.waitFor(() => expect(document.body.textContent).toContain('No data available for chart'))
    expect(saved).toHaveLength(0)
    expect(plotly.downloadImage).not.toHaveBeenCalled()
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

  it('lists the columns a wide-shaped table carries, its parameters in place of parameter, value and quality', async () => {
    registerEndpoint('/api/values', () => ({ values: [{ station_id: '01048', resolution: 'daily', dataset: 'climate_summary', timestamp: '2020-01-01T00:00:00Z', temperature_air_mean_2m: 1.5, precipitation_height: 0.2 }] }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    await wrapper.vm.$nextTick()
    expect(await availableColumns(wrapper)).toEqual(['station_id', 'resolution', 'dataset', 'timestamp', 'temperature_air_mean_2m', 'precipitation_height'])
  })

  // each point mode's rows as the REST API answers them, with a distance of their own and no quality.
  // The distance comes first, so that the list is seen to follow the table's order, not the rows'
  const { quality: _, ...measured } = row
  it.each([
    { mode: 'interpolation', endpoint: '/api/interpolate', values: [{ distance_mean: 12.3, ...measured, taken_station_ids: ['01048', '04411'] }], columns: ['taken_station_ids', 'distance_mean'] },
    { mode: 'summary', endpoint: '/api/summarize', values: [{ distance: 4.2, ...measured, taken_station_id: '01048' }], columns: ['taken_station_id', 'distance'] },
  ] as const)('lists the $mode rows\' own columns, after the table\'s, and no quality', async ({ mode, endpoint, values, columns }) => {
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
    expect(await availableColumns(wrapper)).toEqual(['station_id', 'resolution', 'dataset', 'parameter', 'timestamp', 'value', 'quality'])
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
    plotly.newPlot.mockClear()
    plotly.react.mockClear()
    const { wrapper } = await withQueryRows()
    await showChart(wrapper, faceted)
    const draw = faceted ? plotly.react : plotly.newPlot
    await vi.waitFor(() => expect(draw).toHaveBeenCalled())
    const [trace] = draw.mock.lastCall![1] as { x: string[], y: number[] }[]
    expect([trace!.x, trace!.y]).toEqual([['2020-01-01T00:00:00.000Z'], [1.5]])
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
  function seriesDrawn(faceted: boolean) {
    const draw = faceted ? plotly.react : plotly.newPlot
    const [, traces] = draw.mock.lastCall as unknown as [HTMLElement, { name: string }[]]
    return traces.map(trace => trace.name)
  }

  it.each([false, true])('keeps a series per station fetched when interpolation is selected without fetching, faceted: %s', async (faceted) => {
    registerEndpoint('/api/values', () => ({ values: twoStations }))
    const { wrapper, viewer, stationSelection } = await mountDataViewer()
    await fetchData(viewer)
    await showChart(wrapper, faceted)
    const series = faceted ? ['01048', '04411'] : ['01048 - temperature_air_mean_2m', '04411 - temperature_air_mean_2m']
    expect(seriesDrawn(faceted)).toEqual(series)
    // the rows shown are still both stations': merged, they made one series zig-zagging between them
    stationSelection.value = atPoint('interpolation')
    await flushPromises()
    expect(seriesDrawn(faceted)).toEqual(series)
  })

  it.each([false, true])('draws interpolated rows fetched over station rows as interpolated, faceted: %s', async (faceted) => {
    registerEndpoint('/api/values', () => ({ values: twoStations }))
    registerEndpoint('/api/interpolate', () => ({ values: [{ ...row, taken_station_ids: ['01048', '04411'] }] }))
    const { wrapper, viewer, stationSelection } = await mountDataViewer()
    await fetchData(viewer)
    await showChart(wrapper, faceted)
    stationSelection.value = atPoint('interpolation')
    await flushPromises()
    const draw = faceted ? plotly.react : plotly.newPlot
    draw.mockClear()
    await fetchData(viewer)
    await flushPromises()
    // every drawing of the answer: grouped by the mode of the request before it, the rows were drawn
    // as a station's first, the request answered being taken as the rows' only a few ticks later
    const drawn = draw.mock.calls.map(([, traces]) => (traces as { name: string }[]).map(trace => trace.name))
    expect(drawn.length).toBeGreaterThan(0)
    expect(drawn.every(names => names.join() === (faceted ? 'interpolated' : 'temperature_air_mean_2m'))).toBe(true)
  })
})

describe('dataViewer chart images while drawn', () => {
  // The chart drawn again, as the trendline is ticked, and held by Plotly until the test opens the
  // gate: the single chart's newPlot, or the first facet's react, the others waiting behind it
  async function redrawHeld(wrapper: Awaited<ReturnType<typeof mountDataViewer>>['wrapper'], faceted: boolean) {
    const draw = faceted ? plotly.react : plotly.newPlot
    const drawn = draw.getMockImplementation()!
    const held = gate()
    draw.mockImplementationOnce(async (...args) => {
      await held.opened
      return drawn(...args)
    })
    const calls = draw.mock.calls.length
    const label = wrapper.findAll('label').find(label => label.text() === 'Trendline')!
    await wrapper.find(`#${label.attributes('for')}`).trigger('click')
    await vi.waitFor(() => expect(draw).toHaveBeenCalledTimes(calls + 1))
    return held
  }

  async function toggleFaceting(wrapper: Awaited<ReturnType<typeof mountDataViewer>>['wrapper']) {
    const label = wrapper.findAll('label').find(label => label.text() === 'Facet by parameter')!
    await wrapper.find(`#${label.attributes('for')}`).trigger('click')
    await flushPromises()
  }

  // what exports a chart: Plotly's own download for the single one, toImage for each facet
  function exports(faceted: boolean) {
    return faceted ? plotly.toImage : plotly.downloadImage
  }

  it.each([false, true])('saves the chart once it is drawn, where it was chosen while being drawn, faceted: %s', async (faceted) => {
    // exported at once, a chart Plotly had yet to draw saved as an empty figure
    registerEndpoint('/api/values', () => ({ values: twoParameters }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    await showChart(wrapper, faceted)
    const saved = catchDownload()
    const held = await redrawHeld(wrapper, faceted)
    exports(faceted).mockClear()
    ;(await openDownloads(wrapper))[0]!.click()
    await flushPromises()
    expect(exports(faceted)).not.toHaveBeenCalled()
    held.open()
    await vi.waitFor(() => expect(document.body.textContent).toContain('Chart downloaded as PNG'))
    expect(exports(faceted)).toHaveBeenCalledTimes(faceted ? 2 : 1)
    expect(saved).toHaveLength(faceted ? 1 : 0)
  })

  it.each([false, true])('waits for a drawing started while it waits, faceted: %s', async (faceted) => {
    registerEndpoint('/api/values', () => ({ values: twoParameters }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    await showChart(wrapper, faceted)
    catchDownload()
    const first = await redrawHeld(wrapper, faceted)
    exports(faceted).mockClear()
    ;(await openDownloads(wrapper))[0]!.click()
    // the trendline unticked again: drawn anew, over the chart the first drawing finishes
    const second = await redrawHeld(wrapper, faceted)
    first.open()
    await flushPromises()
    expect(exports(faceted)).not.toHaveBeenCalled()
    second.open()
    await vi.waitFor(() => expect(document.body.textContent).toContain('Chart downloaded as PNG'))
    expect(exports(faceted)).toHaveBeenCalledTimes(faceted ? 2 : 1)
  })

  it.each([
    { faceted: false, toggled: false },
    { faceted: true, toggled: false },
    { faceted: false, toggled: true },
    { faceted: true, toggled: true },
  ])('says there is no chart where Clear emptied it while it was being drawn, faceted: $faceted, faceting turned: $toggled', async ({ faceted, toggled }) => {
    registerEndpoint('/api/values', () => ({ values: twoParameters }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    await showChart(wrapper, faceted)
    const saved = catchDownload()
    const held = await redrawHeld(wrapper, faceted)
    exports(faceted).mockClear()
    ;(await openDownloads(wrapper))[0]!.click()
    await flushPromises()
    if (toggled)
      await toggleFaceting(wrapper)
    ;(viewer.vm as unknown as { clearData: () => void }).clearData()
    held.open()
    await vi.waitFor(() => expect(document.body.textContent).toContain('No data available for chart'))
    expect(exports(faceted)).not.toHaveBeenCalled()
    expect(saved).toHaveLength(0)
  })

  it.each([false, true])('saves the chart as a Fetch drew it anew while it was drawn, a facet added, faceted: %s', async (faceted) => {
    // the charts taken when chosen were saved: gone from the page, and a facet short of it
    const answers = [twoParameters, [...twoParameters, { ...row, parameter: 'wind_speed', value: 3.1 }]]
    registerEndpoint('/api/values', () => ({ values: answers.shift() }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    await showChart(wrapper, faceted)
    const saved = catchDownload()
    const held = await redrawHeld(wrapper, faceted)
    exports(faceted).mockClear()
    ;(await openDownloads(wrapper))[2]!.click()
    await flushPromises()
    await fetchData(viewer)
    await flushPromises()
    held.open()
    await vi.waitFor(() => expect(document.body.textContent).toContain('Chart downloaded as SVG'))
    if (faceted) {
      const svg = new DOMParser().parseFromString(await saved[0]!.text(), 'image/svg+xml').documentElement
      expect([...svg.children].map(chart => chart.textContent)).toEqual(['temperature_air_mean_2m', 'precipitation_height', 'wind_speed'])
    }
    else {
      const [chart] = plotly.downloadImage.mock.lastCall as unknown as [HTMLElement]
      expect(chart.isConnected).toBe(true)
      expect(chart).toBe(plotly.newPlot.mock.lastCall![0])
    }
  })

  it.each([false, true])('saves the charts as drawn where faceting is turned the other way while they are drawn, faceted: %s', async (faceted) => {
    // the charts taken when chosen were saved: unmounted, and the facets beyond the one being drawn
    // never drawn, which the drawing skips once they are gone
    registerEndpoint('/api/values', () => ({ values: twoParameters }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    await showChart(wrapper, faceted)
    const saved = catchDownload()
    const held = await redrawHeld(wrapper, faceted)
    plotly.downloadImage.mockClear()
    plotly.toImage.mockClear()
    ;(await openDownloads(wrapper))[2]!.click()
    await flushPromises()
    await toggleFaceting(wrapper)
    held.open()
    await vi.waitFor(() => expect(document.body.textContent).toContain('Chart downloaded as SVG'))
    if (faceted) {
      expect(plotly.toImage).not.toHaveBeenCalled()
      const [chart] = plotly.downloadImage.mock.lastCall as unknown as [HTMLElement]
      expect(chart.isConnected).toBe(true)
      expect(chart).toBe(plotly.newPlot.mock.lastCall![0])
    }
    else {
      expect(plotly.downloadImage).not.toHaveBeenCalled()
      const svg = new DOMParser().parseFromString(await saved[0]!.text(), 'image/svg+xml').documentElement
      expect([...svg.children].map(chart => chart.textContent)).toEqual(['temperature_air_mean_2m', 'precipitation_height'])
    }
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

// the traces and layout the chart was last drawn with: the single chart's, or the last facet's
function lastDrawn(faceted: boolean) {
  const draw = faceted ? plotly.react : plotly.newPlot
  const [, traces, layout] = draw.mock.lastCall as unknown as [HTMLElement, { name: string, x: string[], y: number[], mode: string }[], { hovermode: string }]
  return { traces, layout }
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
    plotly.newPlot.mockClear()
    plotly.react.mockClear()
    const { wrapper } = await withChartQuery([row, { ...row, timestamp, value: 9 }])
    await showChart(wrapper, faceted)
    await vi.waitFor(() => expect((faceted ? plotly.react : plotly.newPlot)).toHaveBeenCalled())
    const [trace] = lastDrawn(faceted).traces
    expect([trace!.x, trace!.y]).toEqual([['2020-01-01T00:00:00.000Z'], [1.5]])
  })
})

describe('dataViewer chart of the rows it can plot', () => {
  // a parameter whose rows have no value, and one whose rows have no timestamp, beside one plotted
  const unplotted = [
    row,
    { ...row, parameter: 'precipitation_height', value: null },
    { ...row, parameter: 'wind_speed', timestamp: null, value: 3.1 },
  ]

  it('draws no series for the rows it leaves out', async () => {
    // each was an empty trace with a legend entry
    plotly.newPlot.mockClear()
    const { wrapper } = await withChartQuery(unplotted)
    await showChart(wrapper, false)
    await vi.waitFor(() => expect(plotly.newPlot).toHaveBeenCalled())
    expect(lastDrawn(false).traces.map(trace => trace.name)).toEqual(['01048 - temperature_air_mean_2m'])
  })

  it('draws no facet for the rows it leaves out', async () => {
    // each was an empty panel of its own, which the stacked image took in
    plotly.react.mockClear()
    const { wrapper } = await withChartQuery(unplotted)
    await showChart(wrapper, true)
    await vi.waitFor(() => expect(plotly.react).toHaveBeenCalled())
    expect(wrapper.findAll('h4').map(heading => heading.text())).toEqual(['temperature_air_mean_2m'])
    expect(plotly.react).toHaveBeenCalledOnce()
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
    // the rows left out were counted: drawn as thin lines without markers, hovered point by point
    plotly.newPlot.mockClear()
    plotly.react.mockClear()
    const { wrapper } = await withChartQuery([...days(10), ...days(600).map(day => ({ ...day, value: null }))])
    await showChart(wrapper, faceted)
    await vi.waitFor(() => expect(faceted ? plotly.react : plotly.newPlot).toHaveBeenCalled())
    const { traces, layout } = lastDrawn(faceted)
    expect([traces[0]!.mode, layout.hovermode]).toEqual(['lines+markers', 'x unified'])
  })

  it.each([false, true])('draws the points of a large result as a large one, faceted: %s', async (faceted) => {
    plotly.newPlot.mockClear()
    plotly.react.mockClear()
    const { wrapper } = await withChartQuery(days(501))
    await showChart(wrapper, faceted)
    await vi.waitFor(() => expect(faceted ? plotly.react : plotly.newPlot).toHaveBeenCalled())
    const { traces, layout } = lastDrawn(faceted)
    expect([traces[0]!.mode, layout.hovermode]).toEqual(['lines', 'closest'])
  })
})

// the chart drawn again, as the trendline is ticked or unticked
async function toggleTrendline(wrapper: Awaited<ReturnType<typeof mountDataViewer>>['wrapper']) {
  const label = wrapper.findAll('label').find(label => label.text() === 'Trendline')!
  await wrapper.find(`#${label.attributes('for')}`).trigger('click')
}

// the next drawing Plotly is handed, held until the test opens the gate
function holdNextDraw(draw: typeof plotly.react) {
  const drawn = draw.getMockImplementation()!
  const held = gate()
  draw.mockImplementationOnce(async (...args) => {
    await held.opened
    return drawn(...args)
  })
  return held
}

describe('dataViewer chart renders in order', () => {
  // two days of two parameters: a facet each, a series each long enough for a trendline
  const twoDays = [...twoParameters, ...twoParameters.map(value => ({ ...value, timestamp: '2020-01-02T00:00:00Z', value: value.value + 1 }))]

  it('draws each facet as last changed where an older drawing goes on after a newer one', async () => {
    // the older drawing went on to the facets it had left, with the trendline it read at its start
    registerEndpoint('/api/values', () => ({ values: twoDays }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    await showChart(wrapper, true)
    const held = holdNextDraw(plotly.react)
    const calls = plotly.react.mock.calls.length
    // ticked: the first facet's drawing held
    await toggleTrendline(wrapper)
    await vi.waitFor(() => expect(plotly.react).toHaveBeenCalledTimes(calls + 1))
    // unticked again: both facets drawn without it
    await toggleTrendline(wrapper)
    await vi.waitFor(() => expect(plotly.react).toHaveBeenCalledTimes(calls + 3))
    held.open()
    await flushPromises()
    // each facet's series as last drawn
    const last = new Map(plotly.react.mock.calls.slice(calls).map(([chart, traces]) => [chart, (traces as { name: string }[]).map(trace => trace.name)]))
    expect([...last.values()]).toEqual([['01048'], ['01048']])
  })
})

describe('dataViewer chart images after a failed drawing', () => {
  // what draws a chart, and what exports it: the single chart's newPlot and Plotly's own download, or
  // each facet's react and toImage
  const draws = (faceted: boolean) => faceted ? plotly.react : plotly.newPlot
  const exports = (faceted: boolean) => faceted ? plotly.toImage : plotly.downloadImage

  const failed = new Error('drawing failed')

  // the chart shown, and drawn again as the trendline is ticked, where Plotly throws for as many of
  // its drawings as given: the failure is told in the console
  async function shownAndFailing(faceted: boolean, failures: number) {
    registerEndpoint('/api/values', () => ({ values: twoParameters }))
    const mountedViewer = await mountDataViewer()
    await fetchData(mountedViewer.viewer)
    await showChart(mountedViewer.wrapper, faceted)
    const logged = vi.spyOn(console, 'error').mockImplementation(() => {})
    for (let failure = 0; failure < failures; failure++)
      draws(faceted).mockRejectedValueOnce(failed)
    const calls = draws(faceted).mock.calls.length
    await toggleTrendline(mountedViewer.wrapper)
    await vi.waitFor(() => expect(draws(faceted)).toHaveBeenCalledTimes(calls + 1))
    await flushPromises()
    expect(logged).toHaveBeenCalledWith('The chart could not be drawn', failed)
    exports(faceted).mockClear()
    return { ...mountedViewer, calls: calls + 1 }
  }

  it.each([false, true])('draws the chart again before saving it where its drawing failed, faceted: %s', async (faceted) => {
    // the chart Plotly had failed to draw was exported, an empty figure, and reported downloaded
    const { wrapper, calls } = await shownAndFailing(faceted, 1)
    catchDownload()
    ;(await openDownloads(wrapper))[0]!.click()
    await vi.waitFor(() => expect(document.body.textContent).toContain('Chart downloaded as PNG'))
    expect(draws(faceted)).toHaveBeenCalledTimes(calls + (faceted ? 2 : 1))
    expect(exports(faceted)).toHaveBeenCalledTimes(faceted ? 2 : 1)
    expect(draws(faceted).mock.invocationCallOrder.at(-1)).toBeLessThan(exports(faceted).mock.invocationCallOrder[0]!)
  })

  it.each([false, true])('says the chart could not be drawn where drawing it again fails too, faceted: %s', async (faceted) => {
    const { wrapper } = await shownAndFailing(faceted, 2)
    const saved = catchDownload()
    ;(await openDownloads(wrapper))[0]!.click()
    // told by a toast, not only by the chart area's note, shown since the first drawing failed
    const toasts = () => [...document.body.querySelectorAll('[data-slot="title"]')].map(title => title.textContent?.trim())
    await vi.waitFor(() => expect(toasts()).toContain('The chart could not be drawn'))
    expect(document.body.textContent).not.toContain('Chart downloaded')
    expect(exports(faceted)).not.toHaveBeenCalled()
    expect(saved).toHaveLength(0)
  })

  it.each([false, true])('draws the chart again where its newest drawing failed and an older one finished after it, faceted: %s', async (faceted) => {
    // the older drawing, finished last, stands for the chart as drawn only while it is the newest
    registerEndpoint('/api/values', () => ({ values: twoParameters }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    await showChart(wrapper, faceted)
    const draw = draws(faceted)
    const held = holdNextDraw(draw)
    draw.mockRejectedValueOnce(failed)
    vi.spyOn(console, 'error').mockImplementation(() => {})
    const calls = draw.mock.calls.length
    // ticked: held; unticked again: failed
    await toggleTrendline(wrapper)
    await vi.waitFor(() => expect(draw).toHaveBeenCalledTimes(calls + 1))
    await toggleTrendline(wrapper)
    await vi.waitFor(() => expect(draw).toHaveBeenCalledTimes(calls + 2))
    held.open()
    await flushPromises()
    catchDownload()
    exports(faceted).mockClear()
    ;(await openDownloads(wrapper))[0]!.click()
    await vi.waitFor(() => expect(document.body.textContent).toContain('Chart downloaded as PNG'))
    expect(draw).toHaveBeenCalledTimes(calls + 2 + (faceted ? 2 : 1))
    expect(draw.mock.invocationCallOrder.at(-1)).toBeLessThan(exports(faceted).mock.invocationCallOrder[0]!)
  })

  it.each([false, true])('tells no failure of a drawing a newer one has replaced, faceted: %s', async (faceted) => {
    // the console said the chart could not be drawn, where the newer drawing had drawn it
    registerEndpoint('/api/values', () => ({ values: twoParameters }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    await showChart(wrapper, faceted)
    const draw = draws(faceted)
    const held = gate()
    draw.mockImplementationOnce(async () => {
      await held.opened
      throw failed
    })
    const logged = vi.spyOn(console, 'error').mockImplementation(() => {})
    const calls = draw.mock.calls.length
    // ticked: held, to fail; unticked again: drawn
    await toggleTrendline(wrapper)
    await vi.waitFor(() => expect(draw).toHaveBeenCalledTimes(calls + 1))
    await toggleTrendline(wrapper)
    await vi.waitFor(() => expect(draw).toHaveBeenCalledTimes(calls + (faceted ? 3 : 2)))
    held.open()
    await flushPromises()
    expect(logged).not.toHaveBeenCalled()
  })
})

describe('dataViewer chart images after Plotly failed to load', () => {
  // The chart shown while Plotly's chunk fails to load, as after a redeploy under an open tab: the
  // viewer loads Plotly itself, when its chart is first shown. Taken as shown once the failure is
  // told, where a load still under way could be answered by the next load's module
  async function shownWithoutPlotly(wrapper: Awaited<ReturnType<typeof mountDataViewer>>['wrapper'], faceted: boolean) {
    vi.doMock('plotly.js-basic-dist-min', () => {
      throw new Error('chunk failed to load')
    })
    const logged = vi.spyOn(console, 'error').mockImplementation(() => {})
    await showChart(wrapper, faceted)
    await vi.waitFor(() => expect(logged).toHaveBeenCalledWith('The chart could not be drawn', expect.any(Error)))
  }

  function loadPlotly() {
    vi.doMock('plotly.js-basic-dist-min', () => plotly)
  }

  afterEach(loadPlotly)

  it.each([false, true])('loads Plotly again and saves the chart once drawn, faceted: %s', async (faceted) => {
    // the chart never drawn was exported, an empty figure, and reported downloaded
    registerEndpoint('/api/values', () => ({ values: twoParameters }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    const draw = faceted ? plotly.react : plotly.newPlot
    draw.mockClear()
    await shownWithoutPlotly(wrapper, faceted)
    expect(draw).not.toHaveBeenCalled()
    loadPlotly()
    catchDownload()
    ;(await openDownloads(wrapper))[0]!.click()
    // the module loaded anew, which a busy runner can take a while over
    await vi.waitFor(() => expect(document.body.textContent).toContain('Chart downloaded as PNG'), { timeout: 5000 })
    expect(draw).toHaveBeenCalledTimes(faceted ? 2 : 1)
  })

  it.each([false, true])('says there is no chart where Clear emptied it after the menu was opened, faceted: %s', async (faceted) => {
    // the failed chart was drawn again, which failed as well, and told as not drawn
    registerEndpoint('/api/values', () => ({ values: twoParameters }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    await shownWithoutPlotly(wrapper, faceted)
    const saved = catchDownload()
    const items = await openDownloads(wrapper)
    ;(viewer.vm as unknown as { clearData: () => void }).clearData()
    items[0]!.click()
    await vi.waitFor(() => expect(document.body.textContent).toContain('No data available for chart'))
    await flushPromises()
    expect(document.body.textContent).not.toContain('The chart could not be drawn')
    expect(saved).toHaveLength(0)
  })
})

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
  // a wide-shaped row: a column per parameter, and no parameter, value or quality
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
    // where it offered the long shape's parameter, value and quality, which the wide rows lack
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
    plotly.newPlot.mockClear()
    const { wrapper } = await withChartQuery([{ ...row, timestamp: '2020-01-01 00:00', value: 9 }])
    await showChart(wrapper, false)
    await vi.waitFor(() => expect(plotly.newPlot).toHaveBeenCalled())
    const [trace] = lastDrawn(false).traces
    expect(trace!.x).toEqual(['2020-01-01T00:00:00.000Z'])
  })

  it('leaves out a row whose timestamp is a date that does not exist', async () => {
    // read as 2020-03-01 by a Date, which rolls a day past the month's end over
    plotly.newPlot.mockClear()
    const { wrapper } = await withChartQuery([row, { ...row, timestamp: '2020-02-30', value: 9 }])
    await showChart(wrapper, false)
    await vi.waitFor(() => expect(plotly.newPlot).toHaveBeenCalled())
    const [trace] = lastDrawn(false).traces
    expect([trace!.x, trace!.y]).toEqual([['2020-01-01T00:00:00.000Z'], [1.5]])
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
    plotly.newPlot.mockClear()
    const { wrapper } = await withChartQuery(threeDays(value))
    await showChart(wrapper, false)
    await toggleTrendline(wrapper)
    await vi.waitFor(() => expect(lastDrawn(false).traces).toHaveLength(2))
    const [trace, trend] = lastDrawn(false).traces
    expect([trace!.x, trace!.y]).toEqual([['2020-01-01T00:00:00.000Z', '2020-01-02T00:00:00.000Z'], [1.5, 2.5]])
    expect(trend!.y.map(y => Math.round(y * 1e6) / 1e6)).toEqual([1.5, 2.5])
  })

  it('plots an integer past 2^53, which plainRows writes as its digits, as its number', async () => {
    plotly.newPlot.mockClear()
    const { wrapper } = await withChartQuery([{ ...row, value: '10000000000000000000' }, { ...row, timestamp: '2020-01-02T00:00:00Z', value: '-9007199254740993' }])
    await showChart(wrapper, false)
    await vi.waitFor(() => expect(plotly.newPlot).toHaveBeenCalled())
    const [trace] = lastDrawn(false).traces
    expect(trace!.y).toEqual([1e19, -9007199254740992])
  })
})

describe('dataViewer facets large or small by their own points', () => {
  // a day's row each of the parameter, from 2020-01-01 on
  const daysOf = (parameter: string, count: number) => Array.from({ length: count }, (_, day) => ({ ...row, parameter, timestamp: new Date(Date.UTC(2020, 0, day + 1)).toISOString() }))

  // each facet's trace mode and hover mode, as it was last drawn, by its parameter
  function facetsDrawn() {
    const drawn = new Map<string, [string, string]>()
    for (const [, traces, layout] of plotly.react.mock.calls as unknown as [HTMLElement, { mode: string }[], { hovermode: string, yaxis: { title: string } }][])
      drawn.set(layout.yaxis.title, [traces[0]!.mode, layout.hovermode])
    return Object.fromEntries(drawn)
  }

  it('draws small facets as small ones where all of them together pass the threshold', async () => {
    // all six facets' 600 points were counted: each drawn as thin lines without markers, hovered
    // point by point
    plotly.react.mockClear()
    const parameters = ['a', 'b', 'c', 'd', 'e', 'f']
    const { wrapper } = await withChartQuery(parameters.flatMap(parameter => daysOf(parameter, 100)))
    await showChart(wrapper, true)
    await vi.waitFor(() => expect(Object.keys(facetsDrawn())).toHaveLength(6))
    expect(facetsDrawn()).toEqual(Object.fromEntries(parameters.map(parameter => [parameter, ['lines+markers', 'x unified']])))
  })

  it('draws a large facet as a large one beside a small one', async () => {
    plotly.react.mockClear()
    const { wrapper } = await withChartQuery([...daysOf('a', 501), ...daysOf('b', 10)])
    await showChart(wrapper, true)
    await vi.waitFor(() => expect(Object.keys(facetsDrawn())).toHaveLength(2))
    expect(facetsDrawn()).toEqual({ a: ['lines', 'closest'], b: ['lines+markers', 'x unified'] })
  })
})

describe('dataViewer chart series apart from the table\'s sort', () => {
  // one parameter from two stations, the second station's value the greater
  const twoStations = [row, { ...row, station_id: '04411', value: 2.5 }]

  // the series the chart was last drawn with, each by its name and colour, faceted or not
  function seriesDrawn(faceted: boolean) {
    const [, traces] = (faceted ? plotly.react : plotly.newPlot).mock.lastCall as unknown as [HTMLElement, { name: string, line: { color: string } }[]]
    return traces.map(trace => [trace.name, trace.line.color])
  }

  it.each([false, true])('keeps the series\' legend places and colours where the table is sorted, faceted: %s', async (faceted) => {
    registerEndpoint('/api/values', () => ({ values: twoStations }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    await wrapper.vm.$nextTick()
    plotly.newPlot.mockClear()
    plotly.react.mockClear()
    await showChart(wrapper, faceted)
    await vi.waitFor(() => expect(faceted ? plotly.react : plotly.newPlot).toHaveBeenCalled())
    const unsorted = seriesDrawn(faceted)
    expect(unsorted.map(([name]) => name)).toEqual(faceted ? ['01048', '04411'] : ['01048 - temperature_air_mean_2m', '04411 - temperature_air_mean_2m'])
    // back to the table, sorted by value descending, the second station's row first: the stations
    // swapped their legend places and colours
    await wrapper.findAll('button').find(button => button.find('[class~="i-lucide:table"]').exists())!.trigger('click')
    const value = () => wrapper.findAll('thead th span').find(span => span.text().replace(/[↕↑↓]/g, '') === 'value')!
    await value().trigger('click')
    await value().trigger('click')
    expect(wrapper.findAll('tbody tr').map(tr => tr.findAll('td')[0]!.text())).toEqual(['04411', '01048'])
    plotly.newPlot.mockClear()
    plotly.react.mockClear()
    await wrapper.findAll('button').find(button => button.find('[class~="i-lucide:chart-line"]').exists())!.trigger('click')
    await flushPromises()
    await vi.waitFor(() => expect(faceted ? plotly.react : plotly.newPlot).toHaveBeenCalled())
    expect(seriesDrawn(faceted)).toEqual(unsorted)
  })
})

describe('dataViewer parameter statistics of rows that are not long values', () => {
  function stats(viewer: Awaited<ReturnType<typeof mountDataViewer>>['viewer']) {
    return (viewer.vm as unknown as { parameterStats: unknown[] }).parameterStats
  }

  it('takes none of a wide-shaped table, where it showed one row for an undefined parameter', async () => {
    const wide = { station_id: '01048', resolution: 'daily', dataset: 'climate_summary', timestamp: '2020-01-01T00:00:00Z', temperature_air_mean_2m: 1.5, temperature_air_mean_2m_quality: 10 }
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
    expect(stats(viewer)).toEqual([{ parameter: 'temperature_air_mean_2m', dataset: 'climate_summary', count: 1, min: 1.5, max: 1.5, mean: 1.5, sum: 1.5 }])
    const panel = wrapper.findComponent(QueryPanel)
    // `SELECT timestamp, parameter, AVG(value) AS avg_value FROM data GROUP BY timestamp, parameter`
    panel.vm.$emit('dataTransformed', [{ timestamp: '2020-01-01T00:00:00Z', parameter: 'temperature_air_mean_2m', avg_value: 1.5 }])
    await wrapper.vm.$nextTick()
    expect(stats(viewer)).toEqual([])
    // `SELECT parameter, value FROM data`: no dataset, a missing value counted as none, and a value
    // as text, `value::VARCHAR AS value`, left out
    panel.vm.$emit('dataTransformed', [{ parameter: 'precipitation_height', value: 2 }, { parameter: 'precipitation_height', value: 4 }, { parameter: 'wind_speed', value: null }, { parameter: 'wind_speed', value: '3' }, { parameter: 'humidity', value: '50' }])
    await wrapper.vm.$nextTick()
    expect(stats(viewer)).toEqual([
      { parameter: 'precipitation_height', dataset: '', count: 2, min: 2, max: 4, mean: 3, sum: 6 },
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
      { parameter: 'wind_speed', dataset: '2019', count: 1, min: 1, max: 1, mean: 1, sum: 1 },
      { parameter: 'wind_speed', dataset: '2020', count: 1, min: 3, max: 3, mean: 3, sum: 3 },
    ])
  })
})

describe('dataViewer chart that could not be drawn', () => {
  // the chart area's Retry button, and the alert beside it, not a toast's: the chart area stayed
  // empty without a word
  const retry = () => [...document.body.querySelectorAll('button')].find(button => button.textContent?.trim() === 'Retry')
  const alert = () => retry()?.parentElement?.querySelector('[role="alert"]') ?? undefined
  const note = () => alert()?.textContent?.trim()
  const draws = (faceted: boolean) => faceted ? plotly.react : plotly.newPlot

  afterEach(() => {
    vi.doMock('plotly.js-basic-dist-min', () => plotly)
  })

  it.each([false, true])('says so in the chart area and draws the chart again on Retry, faceted: %s', async (faceted) => {
    registerEndpoint('/api/values', () => ({ values: twoParameters }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    await showChart(wrapper, faceted)
    expect(retry()).toBeUndefined()
    vi.spyOn(console, 'error').mockImplementation(() => {})
    const draw = draws(faceted)
    draw.mockRejectedValueOnce(new Error('drawing failed'))
    const calls = draw.mock.calls.length
    await toggleTrendline(wrapper)
    await vi.waitFor(() => expect(retry()).toBeDefined())
    expect(note()).toContain('The chart could not be drawn')
    retry()!.click()
    await vi.waitFor(() => expect(retry()).toBeUndefined())
    expect(note()).toBeUndefined()
    // the failed drawing, then the chart drawn again: each facet's
    expect(draw).toHaveBeenCalledTimes(calls + 1 + (faceted ? 2 : 1))
  })

  it.each([false, true])('says so where Plotly failed to load, and loads it again on Retry, faceted: %s', async (faceted) => {
    registerEndpoint('/api/values', () => ({ values: twoParameters }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    vi.doMock('plotly.js-basic-dist-min', () => {
      throw new Error('chunk failed to load')
    })
    vi.spyOn(console, 'error').mockImplementation(() => {})
    const draw = draws(faceted)
    draw.mockClear()
    await showChart(wrapper, faceted)
    await vi.waitFor(() => expect(retry()).toBeDefined())
    expect(note()).toContain('The chart could not be drawn')
    vi.doMock('plotly.js-basic-dist-min', () => plotly)
    retry()!.click()
    // the module loaded anew, which a busy runner can take a while over
    await vi.waitFor(() => expect(retry()).toBeUndefined(), { timeout: 5000 })
    expect(draw).toHaveBeenCalledTimes(faceted ? 2 : 1)
  })

  it.each([false, true])('says only that there is no chart where no row can be plotted and Plotly failed to load, faceted: %s', async (faceted) => {
    // the render of no chart fails as well, but there is no chart to draw again
    const { wrapper } = await withChartQuery([{ ...row, value: null }])
    vi.doMock('plotly.js-basic-dist-min', () => {
      throw new Error('chunk failed to load')
    })
    const logged = vi.spyOn(console, 'error').mockImplementation(() => {})
    await showChart(wrapper, faceted)
    await vi.waitFor(() => expect(logged).toHaveBeenCalledWith('The chart could not be drawn', expect.any(Error)))
    await flushPromises()
    expect(wrapper.text()).toContain('No data available for chart')
    expect(retry()).toBeUndefined()
  })

  it('tells a Retry that fails too anew, and keeps the focus on Retry', async () => {
    // a Retry that failed again left the note as it was, which a screen reader does not announce
    // again; the note, Retry with it, is not taken away while the drawing runs, which would lose
    // the focus
    registerEndpoint('/api/values', () => ({ values: twoParameters }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    await showChart(wrapper, false)
    vi.spyOn(console, 'error').mockImplementation(() => {})
    plotly.newPlot.mockRejectedValueOnce(new Error('drawing failed'))
    await toggleTrendline(wrapper)
    await vi.waitFor(() => expect(retry()).toBeDefined())
    const first = alert()
    expect(first?.textContent).toContain('The chart could not be drawn')
    const held = gate()
    plotly.newPlot.mockImplementationOnce(async () => {
      await held.opened
      throw new Error('drawing failed again')
    })
    const calls = plotly.newPlot.mock.calls.length
    const button = retry()!
    button.focus()
    button.click()
    await vi.waitFor(() => expect(plotly.newPlot).toHaveBeenCalledTimes(calls + 1))
    await flushPromises()
    expect(alert()).toBe(first)
    held.open()
    await vi.waitFor(() => expect(alert()).not.toBe(first))
    expect(note()).toContain('The chart could not be drawn')
    expect(retry()).toBe(button)
    expect(document.activeElement).toBe(button)
  })
})

describe('dataViewer chart image whose export fails', () => {
  // the step that fails: Plotly's own download of the single chart, a facet's SVG, or the stacked
  // SVG turned into PNG, as where it passes the browser's canvas size. Nothing was saved, unhandled,
  // and nothing said so
  it.each([
    { faceted: false, format: 'PNG', item: 0, step: () => plotly.downloadImage },
    { faceted: true, format: 'SVG', item: 2, step: () => plotly.toImage },
    { faceted: true, format: 'PNG', item: 0, step: () => plotly.Snapshot.svgToImg },
  ])('says the image could not be saved, faceted: $faceted, $format', async ({ faceted, item, step }) => {
    registerEndpoint('/api/values', () => ({ values: twoParameters }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    await showChart(wrapper, faceted)
    const saved = catchDownload()
    const failed = new Error('export failed')
    ;(step() as unknown as { mockRejectedValueOnce: (error: Error) => void }).mockRejectedValueOnce(failed)
    const logged = vi.spyOn(console, 'error').mockImplementation(() => {})
    ;(await openDownloads(wrapper))[item]!.click()
    await vi.waitFor(() => expect(document.body.textContent).toContain('The chart image could not be saved'))
    expect(logged).toHaveBeenCalledWith('The chart image could not be saved', failed)
    expect(document.body.textContent).not.toContain('Chart downloaded')
    expect(saved).toHaveLength(0)
  })

  it.each(['PNG', 'JPEG'])('says the image could not be saved where the stack passes the canvas size, %s', async (format) => {
    // Plotly answers with an empty "data:," there rather than failing: an empty file was saved, and
    // reported downloaded
    registerEndpoint('/api/values', () => ({ values: twoParameters }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    await showChart(wrapper, true)
    const saved = catchDownload()
    plotly.Snapshot.svgToImg.mockResolvedValueOnce('data:,')
    vi.spyOn(console, 'error').mockImplementation(() => {})
    ;(await openDownloads(wrapper))[format === 'PNG' ? 0 : 1]!.click()
    await vi.waitFor(() => expect(document.body.textContent).toContain('The chart image could not be saved'))
    expect(document.body.textContent).not.toContain('Chart downloaded')
    expect(saved).toHaveLength(0)
  })
})

describe('dataViewer chart whose Plotly chunk a redeploy replaced', () => {
  // A redeploy replaces Plotly's hashed chunk under an open tab: every Retry asks for the gone chunk
  // again and fails, and only reloading the page loads the new one, which nothing said
  const button = (label: string) => [...document.body.querySelectorAll('button')].find(button => button.textContent?.trim() === label)
  const note = () => button('Retry')?.parentElement?.querySelector('[role="alert"]')?.textContent?.trim()
  const hint = 'If trying again does not help, reload the page.'

  afterEach(() => {
    vi.doMock('plotly.js-basic-dist-min', () => plotly)
    reloadNuxtApp.mockClear()
  })

  async function shownWithoutPlotly(faceted: boolean) {
    registerEndpoint('/api/values', () => ({ values: twoParameters }))
    const mountedViewer = await mountDataViewer()
    await fetchData(mountedViewer.viewer)
    vi.doMock('plotly.js-basic-dist-min', () => {
      throw new Error('chunk failed to load')
    })
    vi.spyOn(console, 'error').mockImplementation(() => {})
    await showChart(mountedViewer.wrapper, faceted)
    await vi.waitFor(() => expect(button('Retry')).toBeDefined())
    return mountedViewer
  }

  it.each([false, true])('says to reload the page, and reloads it, where Plotly failed to load, faceted: %s', async (faceted) => {
    await shownWithoutPlotly(faceted)
    // the two apart, as a screen reader reads the alert
    expect(note()).toBe(`The chart could not be drawn. Its code could not be loaded. ${hint}`)
    button('Reload page')!.click()
    // forced: unforced, Nuxt drops a second click within ten seconds of a first that did not help
    expect(reloadNuxtApp).toHaveBeenCalledExactlyOnceWith({ force: true })
  })

  it.each([false, true])('offers no reload once Plotly loaded and only its drawing failed, faceted: %s', async (faceted) => {
    // a reload loads nothing the drawing needs: Retry is the way
    await shownWithoutPlotly(faceted)
    vi.doMock('plotly.js-basic-dist-min', () => plotly)
    const draw = faceted ? plotly.react : plotly.newPlot
    draw.mockRejectedValueOnce(new Error('drawing failed'))
    const calls = draw.mock.calls.length
    button('Retry')!.click()
    // the module loaded anew, which a busy runner can take a while over
    await vi.waitFor(() => expect(draw).toHaveBeenCalledTimes(calls + 1), { timeout: 5000 })
    await flushPromises()
    expect(note()).toContain('The chart could not be drawn')
    expect(note()).not.toContain(hint)
    expect(button('Reload page')).toBeUndefined()
  })
})

describe('dataViewer facets\' station colours', () => {
  // each facet's series as it was last drawn, each by its name and colour, by the facet's parameter
  function facetsDrawn() {
    const drawn = new Map<string, string[][]>()
    for (const [, traces, layout] of plotly.react.mock.calls as unknown as [HTMLElement, { name: string, line: { color: string } }[], { yaxis: { title: string } }][])
      drawn.set(layout.yaxis.title, traces.map(trace => [trace.name, trace.line.color]))
    return Object.fromEntries(drawn)
  }

  const second = { ...row, station_id: '04411' }
  const precipitation = { ...row, parameter: 'precipitation_height', value: 0.2 }
  const blue = '#3b82f6'
  const green = '#22c55e'

  it.each([
    // the first station has no precipitation: the second station was coloured first in that facet
    ['a facet lacks the first station', [row, second, { ...precipitation, station_id: '04411' }], [['04411', green]]],
    // the second station's precipitation comes before the first's: it was coloured first in that facet
    ['a facet\'s rows come in another order', [row, second, { ...precipitation, station_id: '04411' }, precipitation], [['04411', green], ['01048', blue]]],
  ])('gives each station one colour in every facet where %s', async (_, values, precipitationSeries) => {
    registerEndpoint('/api/values', () => ({ values }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    await wrapper.vm.$nextTick()
    plotly.react.mockClear()
    await showChart(wrapper, true)
    await vi.waitFor(() => expect(Object.keys(facetsDrawn())).toHaveLength(2))
    expect(facetsDrawn()).toEqual({
      temperature_air_mean_2m: [['01048', blue], ['04411', green]],
      precipitation_height: precipitationSeries,
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
    const rows = Array.from({ length: count }, (_, i) => ({ parameter: 'temperature_air_mean_2m', value: i - 100_000 }))
    wrapper.findComponent(QueryPanel).vm.$emit('dataTransformed', rows)
    await wrapper.vm.$nextTick()
    const sum = (count * (count - 1)) / 2 - count * 100_000
    expect((viewer.vm as unknown as { parameterStats: unknown[] }).parameterStats).toEqual([
      { parameter: 'temperature_air_mean_2m', dataset: '', count, min: -100_000, max: 99_999, mean: sum / count, sum },
    ])
  })
})

describe('dataViewer trendline of many points', () => {
  it('draws the trendline of a series of more points than a call takes arguments, where it threw', async () => {
    // past V8's argument limit of about 120k, as 3 years of one station's 10-minute values, each
    // ten minutes on and one more than the last
    const count = 200_000
    const start = Date.UTC(2020, 0, 1)
    const rows = Array.from({ length: count }, (_, i) => ({ ...row, timestamp: new Date(start + i * 600_000).toISOString(), value: i }))
    plotly.newPlot.mockClear()
    const { wrapper } = await withChartQuery(rows)
    await showChart(wrapper, false)
    await toggleTrendline(wrapper)
    await vi.waitFor(() => expect(lastDrawn(false).traces).toHaveLength(2))
    const [, trend] = lastDrawn(false).traces
    expect(trend!.x).toEqual([new Date(start).toISOString(), new Date(start + (count - 1) * 600_000).toISOString()])
    expect(trend!.y[0]).toBeCloseTo(0, 0)
    expect(trend!.y[1]).toBeCloseTo(count - 1, 0)
  })
})
