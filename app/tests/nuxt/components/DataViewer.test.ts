import type { DataSettings } from '~/types/data-settings.type'
import type { ParameterSelection } from '~/types/parameter-selection-state.type'
import type { StationSelectionState } from '~/types/station-selection-state.type'
import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { getQuery, setResponseStatus } from 'h3'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h, ref } from 'vue'
import { UApp } from '#components'
import DataViewer from '~/components/DataViewer.vue'
import QueryPanel from '~/components/QueryPanel.vue'

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
    registerEndpoint('/api/values', () => ({ values: [row] }))
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    const saved = catchDownload()
    const fetchSpy = vi.spyOn(globalThis, 'fetch')
    const [csv] = await openDownloads(wrapper)
    csv!.click()
    await vi.waitFor(() => expect(saved).toHaveLength(1))
    expect(fetchSpy).not.toHaveBeenCalled()
    const text = await saved[0]!.text()
    // every column the rows carry, those the column picker hides by default included
    expect(text.split('\n')[0]).toBe('station_id,resolution,dataset,parameter,timestamp,value,quality')
    expect(text.split('\n')[1]).toContain('01048')
    expect(text.split('\n')[1]).toContain('1.5')
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
    registerEndpoint('/api/values', async (event) => {
      const query = getQuery(event)
      if (query.format === 'geojson') {
        asked.push(query)
        return { type: 'FeatureCollection', features: [] }
      }
      if (query.station === '04411')
        await new Promise(resolve => setTimeout(resolve, 200))
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
    await vi.waitFor(() => expect(saved).toHaveLength(1))
    expect(asked[0]!.station).toBe('01048')
    await newer
  })

  it('aborts a GeoJSON download chosen while a newer Fetch is under way, once that Fetch\'s answer replaces the table', async () => {
    // it was aborted only when Fetch was pressed, so one chosen after that was saved for a table gone
    let asked = false
    registerEndpoint('/api/values', async (event) => {
      const query = getQuery(event)
      if (query.format === 'geojson') {
        asked = true
        await new Promise(resolve => setTimeout(resolve, 300))
        return { type: 'FeatureCollection', features: [] }
      }
      if (query.station === '04411')
        await new Promise(resolve => setTimeout(resolve, 50))
      return { values: [{ ...row, station_id: String(query.station) }] }
    })
    const { wrapper, viewer, stationSelection } = await mountDataViewer()
    await fetchData(viewer)
    const saved = catchDownload()
    const items = await openDownloads(wrapper)
    stationSelection.value = byStation('04411')
    await wrapper.vm.$nextTick()
    const newer = fetchData(viewer)
    items[2]!.click()
    await vi.waitFor(() => expect(asked).toBe(true))
    await newer
    await vi.waitFor(() => expect(document.body.textContent).toContain('Download cancelled: the table changed'))
    expect(saved).toHaveLength(0)
  })

  it('keeps the request of the fetch started last, whichever finishes last', async () => {
    const asked: Record<string, unknown>[] = []
    registerEndpoint('/api/values', async (event) => {
      const query = getQuery(event)
      if (query.format === 'geojson') {
        asked.push(query)
        return { type: 'FeatureCollection', features: [] }
      }
      // the first fetch answers last
      if (query.station === '01048')
        await new Promise(resolve => setTimeout(resolve, 100))
      return { values: [{ ...row, station_id: String(query.station) }] }
    })
    const { wrapper, viewer, stationSelection } = await mountDataViewer()
    const first = fetchData(viewer)
    stationSelection.value = byStation('04411')
    await wrapper.vm.$nextTick()
    await fetchData(viewer)
    await first
    const saved = catchDownload()
    const items = await openDownloads(wrapper)
    items[2]!.click()
    await vi.waitFor(() => expect(saved).toHaveLength(1))
    expect(asked[0]!.station).toBe('04411')
  })

  it('keeps a cleared table empty when a fetch under way answers', async () => {
    // the answer is to a request the table no longer follows once it is cleared
    let answered = false
    registerEndpoint('/api/values', async () => {
      await new Promise(resolve => setTimeout(resolve, 100))
      answered = true
      return { values: [row] }
    })
    const { wrapper, viewer } = await mountDataViewer()
    const fetching = fetchData(viewer)
    ;(viewer.vm as unknown as { clearData: () => void }).clearData()
    await fetching
    await vi.waitFor(() => expect(answered).toBe(true))
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).not.toContain('1.5')
    expect(offered(await openDownloads(wrapper))).toEqual([['CSV', false], ['JSON', false], ['GeoJSON', false]])
  })

  it('downloads GeoJSON for the station the table shows when the selection moved during the fetch', async () => {
    // the table showed one answer while GeoJSON asked for another
    const asked: Record<string, unknown>[] = []
    registerEndpoint('/api/values', async (event) => {
      const query = getQuery(event)
      if (query.format === 'geojson') {
        asked.push(query)
        return { type: 'FeatureCollection', features: [] }
      }
      await new Promise(resolve => setTimeout(resolve, 50))
      return { values: [{ ...row, station_id: String(query.station) }] }
    })
    const { wrapper, viewer, stationSelection } = await mountDataViewer()
    const fetching = fetchData(viewer)
    stationSelection.value = byStation('04411')
    await wrapper.vm.$nextTick()
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
    registerEndpoint('/api/values', async (event) => {
      if (getQuery(event).format === 'geojson') {
        asked = true
        await new Promise(resolve => setTimeout(resolve, 200))
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
    await vi.waitFor(() => expect(saved).toHaveLength(1))
  })

  it('saves no GeoJSON that Clear overtook while it was being asked for', async () => {
    // it described a table that was no longer on screen, and said it was downloaded
    let asked = false
    registerEndpoint('/api/values', async (event) => {
      if (getQuery(event).format === 'geojson') {
        asked = true
        await new Promise(resolve => setTimeout(resolve, 150))
        return { type: 'FeatureCollection', features: [] }
      }
      return { values: [row] }
    })
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    const saved = catchDownload()
    ;(await openDownloads(wrapper))[2]!.click()
    await vi.waitFor(() => expect(asked).toBe(true))
    ;(viewer.vm as unknown as { clearData: () => void }).clearData()
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
    registerEndpoint('/api/values', async (event) => {
      if (getQuery(event).format === 'geojson') {
        asked = true
        await new Promise(resolve => setTimeout(resolve, 150))
        return { type: 'FeatureCollection', features: [] }
      }
      return { values: [row] }
    })
    const { wrapper, viewer } = await mountDataViewer()
    await fetchData(viewer)
    const saved = catchDownload()
    ;(await openDownloads(wrapper))[2]!.click()
    await vi.waitFor(() => expect(asked).toBe(true))
    const panel = wrapper.findComponent(QueryPanel)
    const rows = kept ? panel.props('data') : [{ timestamp: '2020-01-01', parameter: 'temperature_air_mean_2m', avg_value: 1.5 }]
    panel.vm.$emit('dataTransformed', rows)
    if (kept) {
      await vi.waitFor(() => expect(saved).toHaveLength(1))
    }
    else {
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
