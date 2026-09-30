import type { DataSettings } from '~/types/data-settings.type'
import type { ParameterSelection } from '~/types/parameter-selection-state.type'
import type { StationSelectionState } from '~/types/station-selection-state.type'
import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { getQuery, setResponseStatus } from 'h3'
import { afterEach, describe, expect, it, vi } from 'vitest'
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
      return {
        close: async () => {},
        query: async (sql: string) => {
          const rows = /^(?:DROP|CREATE|INSERT) /.test(sql) ? [] : await duckdb.answer(sql)
          const { Table, tableFromJSON } = await import('apache-arrow')
          return rows.length > 0 ? tableFromJSON(rows) : new Table()
        },
      }
    }
  },
}))

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
    const panel = wrapper.findComponent(QueryPanel)
    expect(panel.props('mode')).toBe(mode)
    expect(panel.props('expectedColumns')).toContain(column)
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
    expect(wrapper.findComponent(QueryPanel).props('mode')).toBe('station')
  })

  it('follows the selected mode once Clear has emptied the table', async () => {
    registerEndpoint('/api/interpolate', () => ({ values: pointModes[0].values }))
    const { wrapper, viewer, stationSelection } = await mountDataViewer(ref(atPoint('interpolation')))
    await fetchData(viewer)
    stationSelection.value = byStation('01048')
    await wrapper.vm.$nextTick()
    expect(picked(wrapper)).toContain('taken_station_ids')
    ;(viewer.vm as unknown as { clearData: () => void }).clearData()
    await wrapper.vm.$nextTick()
    expect(picked(wrapper)).toEqual(['station_id', 'parameter', 'timestamp', 'value', 'quality'])
  })

  it('follows the selected mode after an answer with no rows', async () => {
    registerEndpoint('/api/interpolate', () => ({ values: [] }))
    const { wrapper, viewer, stationSelection } = await mountDataViewer(ref(atPoint('interpolation')))
    await fetchData(viewer)
    stationSelection.value = byStation('01048')
    await wrapper.vm.$nextTick()
    expect(picked(wrapper)).toEqual(['station_id', 'parameter', 'timestamp', 'value', 'quality'])
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
