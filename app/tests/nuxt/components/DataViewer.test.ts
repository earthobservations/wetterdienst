import type { DataSettings } from '~/types/data-settings.type'
import type { ParameterSelection } from '~/types/parameter-selection-state.type'
import type { StationSelectionState } from '~/types/station-selection-state.type'
import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { getQuery, setResponseStatus } from 'h3'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h, ref } from 'vue'
import { UApp } from '#components'
import DataViewer from '~/components/DataViewer.vue'

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
async function mountDataViewer(stationSelection = ref(byStation('01048'))) {
  const wrapper = await mountSuspended(defineComponent({
    setup: () => () => h(UApp, null, {
      default: () => h(DataViewer, { parameterSelection, stationSelection: stationSelection.value, settings }),
    }),
  }), { attachTo: document.body })
  const viewer = wrapper.findComponent(DataViewer)
  return { wrapper, viewer, stationSelection }
}

// the download menu's items as it offers them: opened the way a keyboard opens it
async function openDownloads(wrapper: Awaited<ReturnType<typeof mountDataViewer>>['wrapper']) {
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

afterEach(() => {
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
