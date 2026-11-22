import type { H3Event } from 'h3'
import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { getQuery, setResponseHeader, setResponseStatus } from 'h3'
import { afterEach, beforeEach, describe, expect, it, onTestFinished, vi } from 'vitest'
import { nextTick } from 'vue'
import { clearNuxtData, clearNuxtState, useMyLocation, useRouter } from '#imports'
import MapPage from '~/pages/map.vue'
import { compactGhcnStations } from '../../../server/utils/ghcnStations'
import { ghcnAnnualAnswer, valuesAnswer } from '../../helpers/stripes-backend'

// The map tool (GH-3650): the layers the chips choose, the station a click or the list picks and what the panel shows
// of it, the answers that are empty or fail, the address, and the order of the map and its panel on a phone. The map
// itself (Leaflet, which draws nothing in the test's document) is a stand-in that raises the events the real one does.

const { stage } = vi.hoisted(() => ({
  stage: { props: {} as Record<string, any>, emit: ((..._args: any[]) => {}) as (...args: any[]) => void },
}))
vi.mock('~/components/StationMap.vue', async () => {
  const { defineComponent, h } = await import('vue')
  // `__esModule`, so that Vue takes the `default` of the module a lazily loaded component is; without it the module is
  // taken for the component, and a mocked module answers every name it has not got with an error
  return {
    __esModule: true,
    default: defineComponent({
      props: ['stations', 'selected', 'place', 'label', 'recentre', 'reporting', 'position', 'locate', 'grouping', 'panelOpen', 'describedBy', 'fullscreen', 'hold', 'goTo'],
      emits: ['pick', 'view', 'group'],
      setup(props, { emit }) {
        stage.props = props
        stage.emit = emit as (...args: any[]) => void
        return () => h('div', { 'data-testid': 'station-map', 'role': 'application', 'aria-label': props.label })
      },
    }),
  }
})

function station(station_id: string, name: string, latitude: number, longitude: number, extra: Record<string, unknown> = {}) {
  return { station_id, name, region: null, latitude, longitude, elevation: null, start_timestamp: null, end_timestamp: null, ...extra }
}

const FORECAST_STATIONS = [
  station('10147', 'HAMBURG-FUHLSBUETTEL', 53.63, 10.0, { elevation: 11 }),
  station('10384', 'BERLIN-TEMPELHOF', 52.47, 13.4),
  station('10865', 'MUENCHEN-STADT', 48.16, 11.54),
  station('07157', 'PARIS-ORLY', 48.72, 2.38),
  station('99999', 'NO POSITION', null as unknown as number, null as unknown as number),
]
/** An `end_timestamp` as the REST API gives one for a station that is running: the day of its last value, some days ago */
function daysAgo(days: number) {
  return new Date(Date.now() - days * 86_400_000).toISOString().replace(/T.*$/, 'T00:00:00+00:00')
}

const DAILY_STATIONS = [
  station('01975', 'Hamburg-Fuhlsbüttel', 53.6332, 9.9881, { region: 'Hamburg', elevation: 11, start_timestamp: '1891-01-01T00:00:00+00:00', end_timestamp: daysAgo(1) }),
  station('00011', 'Donaueschingen (Landeplatz)', 47.9737, 8.5205, { region: 'Baden-Württemberg', start_timestamp: '1980-09-01T00:00:00+00:00', end_timestamp: '2001-12-31T00:00:00+00:00' }),
  station('00183', 'Arkona', 54.6791, 13.4343, { region: 'Mecklenburg-Vorpommern', end_timestamp: daysAgo(2) }),
]
// the number of a forecast point is also the number of another station among the measuring ones (59 of them are, in
// DWD's lists): Jan Mayen's 01001 is Doberlug-Kirchhain's
const JAN_MAYEN = station('01001', 'JAN MAYEN', 70.93, -8.67)
const DOBERLUG = station('01001', 'Doberlug-Kirchhain', 51.6475, 13.5742, { region: 'Brandenburg', start_timestamp: '1948-01-01T00:00:00+00:00', end_timestamp: daysAgo(1) })
function addCollision() {
  FORECAST_STATIONS.push(JAN_MAYEN)
  DAILY_STATIONS.push(DOBERLUG)
}
function removeCollision() {
  for (const [list, one] of [[FORECAST_STATIONS, JAN_MAYEN], [DAILY_STATIONS, DOBERLUG]] as const) {
    const at = list.indexOf(one)
    if (at !== -1)
      list.splice(at, 1)
  }
}
// NOAA GHCN daily: Hamburg-Fuhlsbüttel (it has a WMO number, which is the forecast point's: the same station), a station of a record
// that has stopped, one of a record of three years, and one that reaches the ten years of a span and that the backend refuses
const GHCN_HAMBURG = station('GM000010147', 'HAMBURG FUHLSBUETTEL', 53.635, 9.99, { elevation: 11, wmo_id: '10147', start_timestamp: '1891-01-01T00:00:00.000000+00:00', end_timestamp: null })
const GHCN_STOPPED = station('GME00122866', 'GLUCKSTADT', 53.7983, 9.4306, { start_timestamp: '1931-01-01T00:00:00.000000+00:00', end_timestamp: '2021-12-31T00:00:00.000000+00:00' })
const GHCN_SHORT = station('BF1BI000002', 'ALICE TOWN 0.3 SSE', 53.9, 10.3, { start_timestamp: '2023-01-01T00:00:00.000000+00:00', end_timestamp: null })
const GHCN_REFUSED = station('GME00122482', 'FREIBURG/ELBE', 53.8292, 9.2494, { start_timestamp: '1970-01-01T00:00:00.000000+00:00', end_timestamp: null })
const GHCN_NEW_YORK = station('USW00094728', 'NEW YORK CNTRL PK TWR', 40.7789, -73.9692, { elevation: 42.7, start_timestamp: '1869-01-01T00:00:00.000000+00:00', end_timestamp: null })
const GHCN_STATIONS = [GHCN_HAMBURG, GHCN_STOPPED, GHCN_SHORT, GHCN_REFUSED, GHCN_NEW_YORK]
const HOURLY_STATIONS = [station('00044', 'Großenkneten', 52.9336, 8.237, { start_timestamp: '1990-01-01T00:00:00+00:00', end_timestamp: daysAgo(1) })]
// an annual list ends with last year, as the real one does
const LAST_YEAR = `${new Date().getUTCFullYear() - 1}-12-31T00:00:00+00:00`
const STRIPES_STATIONS = [
  { station_id: '01975', name: 'Hamburg-Fuhlsbüttel', region: 'Hamburg', latitude: 53.6332, longitude: 9.9881, start_timestamp: null, end_timestamp: LAST_YEAR },
  { station_id: '00011', name: 'Donaueschingen (Landeplatz)', region: 'Baden-Württemberg', latitude: 47.9737, longitude: 8.5205, start_timestamp: null, end_timestamp: LAST_YEAR },
]
// the solar radiation is 38 days behind today as a whole, which its stations do not show against each other: Feldberg
// is running, Freiburg stopped in 2015, and a station of no end is of no known status
const FELDBERG = station('01346', 'Feldberg/Schwarzwald', 47.8738, 8.0038, { start_timestamp: '2023-01-01T00:00:00+00:00', end_timestamp: daysAgo(38) })
const FREIBURG = station('01443', 'Freiburg', 48.0231, 7.8344, { start_timestamp: '1973-01-01T00:00:00+00:00', end_timestamp: '2015-12-31T00:00:00+00:00' })
const NO_END = station('09999', 'Nullend', 47.9, 7.4, { start_timestamp: '2006-01-01T00:00:00+00:00', end_timestamp: null })
let solarStations: Array<Omit<ReturnType<typeof station>, 'end_timestamp'> & { end_timestamp: string | null }> = [FELDBERG, FREIBURG, NO_END]
const FREIBURG_FORECAST = station('10401', 'FREIBURG', 48.02, 7.84)
// a stripes station that stopped, nearer to the clicks the tests make than the one that runs
const HAMBURG_OLD_STRIPES = { station_id: '99002', name: 'Hamburg-Alt', region: 'Hamburg', latitude: 53.61, longitude: 9.99, start_timestamp: null, end_timestamp: '2009-12-31T00:00:00+00:00' }
const COVERAGE = {
  daily: { description: null, datasets: { climate_summary: { description: null, parameters: [] }, more_precip: { description: null, parameters: [] }, solar: { description: null, parameters: [] } } },
  hourly: { description: null, datasets: { temperature_air: { description: null, parameters: [] } } },
}

/** What each endpoint is asked for, and what a test makes it answer instead */
const asked: { stations: Array<Record<string, string>>, stripesValues: string[], stripesQueries: Array<Record<string, string>>, values: string[] } = { stations: [], stripesValues: [], stripesQueries: [], values: [] }
let stationsFailures = 0
/** How many requests for the details of a station of GHCN daily, by its id, fail with a 500 before one is answered */
let ghcnDetailFailures = 0
/** How many requests for the list of the stations of GHCN daily fail with a 502 before one is answered, and how many were made */
let ghcnListFailures = 0
const ghcnListAsked = { count: 0 }
/** How long the list of the stations of GHCN daily is held before it is answered, in milliseconds */
let ghcnListDelay = 0
/** The gate the details of a station of GHCN daily wait at before they are answered, where a test has closed it (`holdDetails`); the test opens it, and `afterEach` does where it did not */
let ghcnDetailGate: Promise<void> | null = null
let openDetails: (() => void) | null = null
function holdDetails() {
  ghcnDetailGate = new Promise<void>((resolve) => {
    openDetails = resolve
  })
  return () => openDetails?.()
}
/** A station of GHCN daily nearer to the forecast point of Hamburg than the station that has its WMO number, which the list has where it is set */
let ghcnNeighbour = false
const GHCN_NEIGHBOUR = station('GM000099999', 'HAMBURG NEBENAN', 53.6301, 10.0001, { start_timestamp: '2001-01-01T00:00:00.000000+00:00', end_timestamp: null })
/** How many stations of no consequence the list has beside the five of the tests: over the 10,000 from which a layer is always grouped */
let ghcnFiller = 0
let stripesStatus = 200
/** The stations that have stripes: the annual record's, which the map asks of the generic API */
let stripesStations: Array<typeof STRIPES_STATIONS[number]> = STRIPES_STATIONS

async function stationsOf(event: H3Event) {
  const query = getQuery(event) as Record<string, string>
  asked.stations.push(query)
  if (stationsFailures > 0 && query.network === 'mosmix') {
    stationsFailures--
    // a 500, which a request is not asked for again: the REST API answers a failure of its own or of the source's so
    setResponseStatus(event, 500)
    return { detail: 'The forecast stations are not available' }
  }
  // GHCN daily: the backend is asked for the one station the panel has details of (the list is the app's server's)
  if (query.network === 'ghcn') {
    if (ghcnDetailGate)
      await ghcnDetailGate
    if (ghcnDetailFailures > 0) {
      ghcnDetailFailures--
      setResponseStatus(event, 500)
      return { detail: 'The stations are not available' }
    }
    return { stations: GHCN_STATIONS.filter(entry => query.stations!.split(',').includes(entry.station_id)) }
  }
  if (query.network === 'mosmix')
    return { stations: FORECAST_STATIONS }
  // the stations that have stripes: the annual record, the historical and the recent period of it (GH-4258)
  if (query.parameters?.startsWith('annual/'))
    return { stations: stripesStations }
  if (query.parameters === 'hourly/temperature_air')
    return { stations: HOURLY_STATIONS }
  return { stations: query.parameters === 'daily/solar' ? solarStations : DAILY_STATIONS }
}

/** The list of the stations of GHCN daily that the app's server hands out, as columns: the WMO number but no elevation */
async function ghcnListOf(event: H3Event) {
  ghcnListAsked.count++
  if (ghcnListDelay)
    await new Promise(resolve => setTimeout(resolve, ghcnListDelay))
  if (ghcnListFailures > 0) {
    ghcnListFailures--
    setResponseStatus(event, 502)
    setResponseHeader(event, 'content-type', 'application/problem+json')
    return { type: 'urn:wetterdienst:problem:backend-unreachable', title: 'Bad Gateway', status: 502, detail: 'The backend could not be reached. The cause is in the server log.' }
  }
  const filler = Array.from({ length: ghcnFiller }, (_, index) => station(`FILL${index}`, `FILLER ${index}`, -40 + (index % 50) / 10, -150 + Math.floor(index / 50) / 10, { start_timestamp: '2000-01-01T00:00:00+00:00' }))
  return compactGhcnStations([...GHCN_STATIONS, ...(ghcnNeighbour ? [GHCN_NEIGHBOUR] : []), ...filler])
}

/**
 * The annual values the map's stripes are made of (GH-4258): the API's for a station of DWD (`/api/values`), the app's own
 * server's for a station of GHCN daily (`/_ghcn/annual`); the app makes the classes of them itself
 */
function stripesValuesOf(ghcn: boolean) {
  return (event: H3Event) => {
    const query = getQuery(event) as Record<string, string>
    const stationId = String(ghcn ? query.station : query.stations)
    asked.stripesValues.push(stationId)
    asked.stripesQueries.push(query)
    if (stripesStatus !== 200) {
      setResponseStatus(event, stripesStatus)
      return { detail: 'This station has no complete years.' }
    }
    const years = Array.from({ length: 20 }, (_, index) => ({ year: 2000 + index, value: 8 + index * 0.05 }))
    // a station of GHCN daily with too few years with data for a scale of its own: the app refuses it
    if (ghcn && stationId === GHCN_REFUSED.station_id)
      return ghcnAnnualAnswer(years.slice(0, 5), { stationId, method: 'midrange' })
    return ghcn
      ? ghcnAnnualAnswer(years, { stationId, method: 'midrange' })
      : valuesAnswer(years, { stationId })
  }
}

function forecastValues(stationId: string) {
  const start = new Date()
  start.setUTCMinutes(0, 0, 0)
  return Array.from({ length: 72 }, (_, hour) => ({
    station_id: stationId,
    resolution: 'hourly',
    dataset: 'large',
    parameter: 'temperature_air_2m',
    timestamp: new Date(start.getTime() + hour * 3_600_000).toISOString(),
    value: 8 + 4 * Math.sin(hour / 4),
    quality_flags: null,
  }))
}

function stubMediaQueries(wide: boolean) {
  window.matchMedia = ((query: string) => ({
    matches: /min-width:\s*72rem/.test(query) ? wide : false,
    media: query,
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia
}

registerEndpoint('/api/stations', stationsOf)
registerEndpoint('/api/values', stripesValuesOf(false))
registerEndpoint('/_ghcn/annual', stripesValuesOf(true))
registerEndpoint('/_ghcn/map-stations', ghcnListOf)
registerEndpoint('/api/coverage', () => COVERAGE)

const originalMatchMedia = window.matchMedia
const mounted: Array<{ unmount: () => void }> = []
let valuesStatus = 200

async function mountMap(route = '/map') {
  const wrapper = await mountSuspended(MapPage, { route, attachTo: document.body })
  mounted.push(wrapper)
  // the layers are in the panel of the button over the map (GH-4209), which these tests keep open
  await openLayers(wrapper)
  return wrapper
}
/** The place of each layer's radio in the panel of the layers button */
const LAYER_INDEX = { forecast: 0, measured: 1, ghcn: 2 } as const
/** Chooses a layer in the panel of the layers button, which a click elsewhere on the page has closed: opens it again */
async function chooseLayer(wrapper: Awaited<ReturnType<typeof mountSuspended>>, layer: 'forecast' | 'measured' | 'ghcn') {
  // a click elsewhere on the page closes the panel a moment later: let that finish, and open it again if it did
  await new Promise(resolve => setTimeout(resolve, 80))
  await openLayers(wrapper)
  await vi.waitFor(() => expect(wrapper.findAll('[data-testid="map-layers"] [role="radio"]')).toHaveLength(3))
  await wrapper.findAll('[data-testid="map-layers"] [role="radio"]')[LAYER_INDEX[layer]]!.trigger('click')
}

/** Opens the panel of the layers button, once */
async function openLayers(wrapper: Awaited<ReturnType<typeof mountSuspended>>) {
  // by the button's own word, not by the panel: a panel that a click elsewhere has closed is in the page for a moment more
  if (wrapper.find('[data-testid="map-layers-button"]').attributes('aria-expanded') !== 'true')
    await wrapper.find('[data-testid="map-layers-button"]').trigger('click')
  await vi.waitFor(() => expect(wrapper.find('[data-testid="map-layers-panel"]').exists()).toBe(true))
}
const text = (wrapper: Awaited<ReturnType<typeof mountMap>>) => wrapper.text().replace(/\s+/g, ' ')
const panel = (wrapper: Awaited<ReturnType<typeof mountMap>>) => wrapper.find('[data-testid="map-panel"]')
/** The radio of a layer in the panel of the layers button */
const layerButton = (wrapper: Awaited<ReturnType<typeof mountMap>>, layer: 'forecast' | 'measured' | 'ghcn') => wrapper.findAll('[data-testid="map-layers"] [role="radio"]')[LAYER_INDEX[layer]]!

/** The list is there once its first station is: the forecast's, by the point nearest the centre of Germany */
async function listed(wrapper: Awaited<ReturnType<typeof mountMap>>) {
  await vi.waitFor(() => expect(wrapper.find('[data-testid="map-list"]').exists()).toBe(true))
}

beforeEach(() => {
  stubMediaQueries(true)
  globalThis.fetch = vi.fn(async (input: RequestInfo | URL) => {
    const url = new URL(String(input), 'http://localhost')
    asked.values.push(url.searchParams.get('stations') ?? '')
    if (valuesStatus !== 200)
      return new Response(JSON.stringify({ detail: 'The forecast could not be read' }), { status: valuesStatus })
    return new Response(JSON.stringify({ values: forecastValues(url.searchParams.get('stations') ?? '') }), { status: 200 })
  }) as typeof fetch
})

afterEach(async () => {
  mounted.splice(0).forEach(wrapper => wrapper.unmount())
  // the next page has its own map: a test must not read the props of this one's, or raise its events
  stage.props = {}
  stage.emit = () => {}
  clearNuxtData()
  asked.stations.length = asked.stripesValues.length = asked.stripesQueries.length = asked.values.length = 0
  stationsFailures = 0
  ghcnDetailFailures = 0
  ghcnListFailures = 0
  ghcnListAsked.count = 0
  ghcnListDelay = 0
  ghcnFiller = 0
  openDetails?.()
  openDetails = null
  ghcnDetailGate = null
  ghcnNeighbour = false
  stripesStatus = 200
  valuesStatus = 200
  removeCollision()
  solarStations = [FELDBERG, FREIBURG, NO_END]
  stripesStations = STRIPES_STATIONS
  FORECAST_STATIONS.splice(FORECAST_STATIONS.indexOf(FREIBURG_FORECAST) >>> 0, FORECAST_STATIONS.includes(FREIBURG_FORECAST) ? 1 : 0)
  window.matchMedia = originalMatchMedia
  await useRouter().replace({ query: {} })
})

describe('the map tool', () => {
  it('is a page of its own: a title, what it is for, and the panel with the map', async () => {
    const wrapper = await mountMap()
    expect(wrapper.find('h1').text()).toBe('Station map')
    expect(text(wrapper)).toContain('Pick a station or any point on the map for its forecast, climate stripes and measurements.')
    expect(panel(wrapper).exists()).toBe(true)
    // the map's own code is loaded apart from the page
    await vi.waitFor(() => expect(wrapper.find('[data-testid="station-map"]').exists()).toBe(true))
    expect(wrapper.find('[data-testid="station-map"]').attributes('aria-label')).toBe('Station map: Forecast stations')
  })

  it('has the forecast stations as the first layer, chosen in the panel of a button by radios that say which one they are in words and by being checked', async () => {
    const wrapper = await mountMap()
    const group = wrapper.find('[data-testid="map-layers"]')
    expect(group.findAll('[role="radio"]').map(radio => radio.attributes('aria-checked'))).toEqual(['true', 'false', 'false'])
    expect(group.findAll('label').map(label => label.text())).toEqual(['Forecast stations', 'DWD measurements', 'NOAA GHCN daily'])
    expect(layerButton(wrapper, 'forecast').attributes('aria-checked')).toBe('true')
    expect(layerButton(wrapper, 'measured').attributes('aria-checked')).toBe('false')
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-count"]').text()).toBe('Stations shown: 4'))
    // DWD MOSMIX, as the forecast page asks for it, and nothing of the measurements yet
    expect(asked.stations).toHaveLength(1)
    expect(asked.stations[0]).toMatchObject({ provider: 'dwd', network: 'mosmix', parameters: 'hourly/large', all: 'true' })
  })

  it('draws the stations that have a position, the forecast points only, and not the one that has none', async () => {
    const wrapper = await mountMap()
    await vi.waitFor(() => expect(stage.props.stations).toHaveLength(4))
    expect(stage.props.stations.map((entry: any) => entry.station_id)).not.toContain('99999')
    expect(wrapper.exists()).toBe(true)
  })

  it('shows the measuring stations of a source when its chip is pressed, and their resolution and dataset choices with it', async () => {
    const wrapper = await mountMap()
    await listed(wrapper)
    expect(wrapper.find('[data-testid="map-resolution"]').exists()).toBe(false)
    await chooseLayer(wrapper, 'measured')
    expect(layerButton(wrapper, 'measured').attributes('aria-checked')).toBe('true')
    expect(layerButton(wrapper, 'forecast').attributes('aria-checked')).toBe('false')
    await vi.waitFor(() => expect(stage.props.stations.map((entry: any) => entry.station_id)).toEqual(['01975', '00011', '00183']))
    expect(asked.stations.at(-1)).toMatchObject({ provider: 'dwd', network: 'observation', parameters: 'daily/climate_summary', all: 'true' })
    expect(wrapper.find('[data-testid="map-resolution"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="map-dataset"]').exists()).toBe(true)
    expect(stage.props.label).toBe('Station map: DWD measurements')
  })

  it('asks for the stations of another resolution, keeping the dataset it has and taking the daily climate summary or the first where it has none', async () => {
    const wrapper = await mountMap()
    await chooseLayer(wrapper, 'measured')
    await vi.waitFor(() => expect(stage.props.stations).toHaveLength(3))
    const vm = wrapper.vm as any
    // the coverage has come: hourly has one dataset, which is not the one the daily source had
    await vi.waitFor(() => expect(vm.resolutionItems.map((item: any) => item.value)).toEqual(['daily', 'hourly']))
    vm.resolutionChoice = 'hourly'
    await vi.waitFor(() => expect(asked.stations.at(-1)).toMatchObject({ parameters: 'hourly/temperature_air' }))
    expect(vm.source).toEqual({ resolution: 'hourly', dataset: 'temperature_air' })
    await vi.waitFor(() => expect(stage.props.stations.map((entry: any) => entry.station_id)).toEqual(['00044']))
    // and back: the dataset of the daily source that the hourly one has not is the climate summary
    vm.resolutionChoice = 'daily'
    expect(vm.source).toEqual({ resolution: 'daily', dataset: 'climate_summary' })
    // a dataset of the resolution, by its own choice
    vm.datasetChoice = 'more_precip'
    await vi.waitFor(() => expect(asked.stations.at(-1)).toMatchObject({ parameters: 'daily/more_precip' }))
  })

  it('says so where a dataset has no stations', async () => {
    const wrapper = await mountMap()
    await chooseLayer(wrapper, 'measured')
    await vi.waitFor(() => expect(stage.props.stations).toHaveLength(3))
    registerEndpoint('/api/stations', (event) => {
      const query = getQuery(event) as Record<string, string>
      return { stations: query.network === 'mosmix' ? FORECAST_STATIONS : [] }
    })
    ;(wrapper.vm as any).datasetChoice = 'more_precip'
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-empty"]').text()).toBe('This dataset has no stations with a position.'))
    // the panel then offers no centre to pick
    expect(wrapper.find('[data-testid="map-pick-centre"]').exists()).toBe(false)
    registerEndpoint('/api/stations', stationsOf)
  })
})

describe('the list beside the map', () => {
  it('lists the stations nearest the centre of the map, nearest first, each with its distance, and follows the map as it moves', async () => {
    const wrapper = await mountMap()
    await listed(wrapper)
    // the map reports where it is centred: Munich
    stage.emit('view', { latitude: 48.16, longitude: 11.54, zoom: 9 })
    await nextTick()
    const items = wrapper.findAll('[data-testid="map-list"] li')
    expect(items.map(item => item.find('.font-semibold').text())).toEqual(['MUENCHEN-STADT', 'BERLIN-TEMPELHOF', 'HAMBURG-FUHLSBUETTEL', 'PARIS-ORLY'])
    expect(items[0]!.text()).toContain('10865')
    expect(items[0]!.text()).toMatch(/\d+ m$/)
    expect(items[1]!.text()).toMatch(/\d+ km$/)
    // nearest first: each is farther than the one before
    const distances = items.map(item => Number(item.find('.tabular-nums').text().replace(/[^\d.]/g, '')))
    expect(distances[1]!).toBeGreaterThan(distances[0]! / 1000)
    stage.emit('view', { latitude: 53.5, longitude: 10, zoom: 9 })
    await nextTick()
    expect(wrapper.find('[data-testid="map-list"] li .font-semibold').text()).toBe('HAMBURG-FUHLSBUETTEL')
  })

  it('finds a name in either spelling of an umlaut, as the header\'s search does, and says how many stations there are where it lists only the first 20', async () => {
    const many = Array.from({ length: 25 }, (_, index) => station(`H${index}`, `HAMBURG-TEST ${index}`, 53 + index / 100, 10))
    FORECAST_STATIONS.push(...many)
    onTestFinished(() => {
      for (const one of many)
        FORECAST_STATIONS.splice(FORECAST_STATIONS.indexOf(one), 1)
    })
    const wrapper = await mountMap()
    await listed(wrapper)
    const search = wrapper.find('input[type="search"]')
    // the list writes MUENCHEN: both spellings of the umlaut find it
    for (const typed of ['münchen', 'muenchen']) {
      await search.setValue(typed)
      expect(wrapper.findAll('[data-testid="map-list"] li').map(item => item.find('.font-semibold').text()), typed).toEqual(['MUENCHEN-STADT'])
      expect(wrapper.find('[data-testid="map-results-of"]').exists()).toBe(false)
    }
    await search.setValue('hamburg')
    expect(wrapper.findAll('[data-testid="map-list"] li')).toHaveLength(20)
    expect(wrapper.find('[data-testid="map-results-of"]').text()).toBe('Showing the first 20 of 26 stations. Type more to narrow them down.')
    await search.setValue('hamburg-test 24')
    expect(wrapper.find('[data-testid="map-results-of"]').exists()).toBe(false)
  })

  it('finds a station by the start of its name, by its number, and says where none matches', async () => {
    const wrapper = await mountMap()
    await listed(wrapper)
    const search = wrapper.find('input[type="search"]')
    expect(search.attributes('aria-label')).toBe('Find a station')
    await search.setValue('muench')
    expect(wrapper.findAll('[data-testid="map-list"] li').map(item => item.find('.font-semibold').text())).toEqual(['MUENCHEN-STADT'])
    expect(wrapper.find('.map-list-title').text()).toBe('Results')
    await search.setValue('10147')
    expect(wrapper.findAll('[data-testid="map-list"] li').map(item => item.find('.font-semibold').text())).toEqual(['HAMBURG-FUHLSBUETTEL'])
    await search.setValue('nowhere')
    expect(wrapper.find('[data-testid="map-no-results"]').text()).toBe('No station matches this search.')
    expect(wrapper.find('[data-testid="map-list"]').exists()).toBe(false)
  })
})

describe('a station picked', () => {
  /** A click on the map near Hamburg-Fuhlsbüttel but not on it: about 20 km from it */
  const NEAR_HAMBURG = { latitude: 53.45, longitude: 10.2, tolerance: 0.5 }

  it('is the station nearest to a click on the map, with the place told apart from the station, and what the panel shows of it', async () => {
    const wrapper = await mountMap()
    await listed(wrapper)
    stage.emit('pick', NEAR_HAMBURG)
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-station-name"]').text()).toBe('HAMBURG-FUHLSBUETTEL'))
    expect(panel(wrapper).text()).toContain('Station 10147')
    expect(panel(wrapper).text()).toContain('11 m above sea level')
    expect(wrapper.find('[data-testid="map-place"]').text()).toMatch(/^A point on the map, \d+ km from this station$/)
    // the map is told which station is picked and where the place is
    expect(stage.props.selected.station_id).toBe('10147')
    expect(stage.props.place).toMatchObject({ latitude: 53.45, longitude: 10.2 })
    // told to a screen reader
    expect(wrapper.find('[data-testid="map-announcement"]').text()).toBe('HAMBURG-FUHLSBUETTEL chosen')
  })

  it('is the station itself, with no place apart, for a click on its dot', async () => {
    const wrapper = await mountMap()
    await listed(wrapper)
    stage.emit('pick', { latitude: 53.6305, longitude: 10.0, tolerance: 0.5 })
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-station-name"]').exists()).toBe(true))
    expect(wrapper.find('[data-testid="map-place"]').exists()).toBe(false)
    expect(stage.props.place).toBeNull()
  })

  it('shows the forecast as day rows of the forecast point, and links to the forecast', async () => {
    const wrapper = await mountMap()
    await listed(wrapper)
    stage.emit('pick', NEAR_HAMBURG)
    const card = () => wrapper.find('[data-testid="map-card-forecast"]')
    await vi.waitFor(() => expect(card().find('[data-testid="day-rows"]').exists()).toBe(true))
    expect(card().find('h3').text()).toBe('Forecast')
    expect(card().findAll('[data-testid="day-rows"] li').length).toBeGreaterThanOrEqual(3)
    expect(asked.values).toEqual(['10147'])
    expect(card().find('a[href^="/meteogram"]').attributes('href')).toBe('/meteogram?station=10147')
    // the forecast point is the picked one, and the click was some way from it: the card says how far
    expect(card().text()).toMatch(/HAMBURG-FUHLSBUETTEL, \d+ km away/)
  })

  it('has no "away" note on a card for a click on the dot of the station', async () => {
    const wrapper = await mountMap()
    await listed(wrapper)
    stage.emit('pick', { latitude: 53.6305, longitude: 10.0, tolerance: 0.5 })
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-card-forecast"] [data-testid="day-rows"]').exists()).toBe(true))
    expect(wrapper.find('[data-testid="map-card-forecast"]').text()).not.toContain('away')
  })

  it('shows the climate stripes of the nearest station that has them, told by name and distance, and links to the stripes', async () => {
    const wrapper = await mountMap()
    await listed(wrapper)
    stage.emit('pick', NEAR_HAMBURG)
    const card = () => wrapper.find('[data-testid="map-card-stripes"]')
    await vi.waitFor(() => expect(card().find('[role="img"]').exists()).toBe(true))
    expect(card().find('h3').text()).toBe('Climate stripes')
    // Hamburg-Fuhlsbüttel measures: the nearest of the stations that have stripes, about 20 km from the place
    expect(card().text()).toMatch(/Hamburg-Fuhlsbüttel, \d+ km away/)
    expect(card().find('[role="img"]').attributes('aria-label')).toBe('Climate stripes of Hamburg-Fuhlsbüttel')
    expect(card().findAll('.map-stripes span')).toHaveLength(20)
    // the figure is described in words: the span of the years, the lowest and the highest
    expect(card().find('figcaption').text()).toMatch(/^From 2000 to 2019\. Lowest value 8\.0 .+ in 2000, highest value 9\.0 .+ in 2019\. Colours: the mean of the whole record \(2000–2019\) .+ \(Ed Hawkins. method\)\.$/)
    expect(card().find('a[href^="/stripes"]').attributes('href')).toBe('/stripes?kind=temperature&station=01975')
    expect(asked.stripesValues).toEqual(['01975'])
    // made by the app of the generic API (GH-4258): the stations that have stripes are the annual record's, the historical and the recent
    // period of it, and the years are the annual values of the station
    const annual = asked.stations.filter(query => query.parameters?.startsWith('annual/'))
    expect(annual.map(query => query.periods).sort()).toEqual(['historical', 'recent'])
    expect(annual[0]).toMatchObject({ provider: 'dwd', network: 'observation', parameters: 'annual/climate_summary/temperature_air_mean_2m', all: 'true' })
    expect(asked.stripesQueries[0]).toMatchObject({ provider: 'dwd', network: 'observation', parameters: 'annual/climate_summary/temperature_air_mean_2m', periods: 'historical', stations: '01975' })
  })

  it('links to the measurements in the explorer and to the station history, each at the nearest station of the source, already filled in', async () => {
    const wrapper = await mountMap()
    await listed(wrapper)
    stage.emit('pick', NEAR_HAMBURG)
    const card = () => wrapper.find('[data-testid="map-card-measured"]')
    await vi.waitFor(() => expect(card().findAll('a')).toHaveLength(2))
    expect(card().find('h3').text()).toBe('Measurements')
    expect(card().text()).toContain('Climate summary, Daily')
    expect(card().text()).toContain('since 1891')
    expect(card().text()).toMatch(/Hamburg-Fuhlsbüttel, \d+ km away/)
    const [explorer, history] = card().findAll('a')
    const explorerLink = new URL(explorer!.attributes('href')!, 'http://x')
    expect(explorerLink.pathname).toBe('/explorer')
    expect(Object.fromEntries(explorerLink.searchParams)).toEqual({
      provider: 'dwd',
      network: 'observation',
      resolution: 'daily',
      dataset: 'climate_summary',
      mode: 'station',
      stations: '01975',
    })
    expect(explorer!.text()).toBe('Open the measurements in the Explorer')
    const historyLink = new URL(history!.attributes('href')!, 'http://x')
    expect(historyLink.pathname).toBe('/history')
    expect(Object.fromEntries(historyLink.searchParams)).toMatchObject({ provider: 'dwd', network: 'observation', dataset: 'climate_summary', stations: '01975' })
    expect(history!.text()).toBe('Open the station history')
  })

  it('says for how long a station that has stopped measured', async () => {
    const wrapper = await mountMap()
    await chooseLayer(wrapper, 'measured')
    await vi.waitFor(() => expect(stage.props.stations).toHaveLength(3))
    stage.emit('pick', { latitude: 47.97, longitude: 8.52, tolerance: 0.5 })
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-card-measured"]').text()).toContain('1980 to 2001'))
  })

  it('takes the link of the measurements from the source the chips have, and the station of the layer it is the layer of', async () => {
    const wrapper = await mountMap()
    await chooseLayer(wrapper, 'measured')
    await vi.waitFor(() => expect(stage.props.stations).toHaveLength(3))
    stage.emit('pick', { latitude: 53.6, longitude: 10.0, tolerance: 0.5 })
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-station-name"]').text()).toBe('Hamburg-Fuhlsbüttel'))
    const card = wrapper.find('[data-testid="map-card-measured"]')
    expect(new URL(card.find('a').attributes('href')!, 'http://x').searchParams.get('stations')).toBe('01975')
    // the layer's own station, 3.7 km from the click: the card says how far, as the others do
    expect(card.text()).toMatch(/Hamburg-Fuhlsbüttel, [\d.]+ km away/)
    // the forecast is the nearest forecast point, which the panel asks the list of
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-card-forecast"]').text()).toMatch(/HAMBURG-FUHLSBUETTEL, [\d.]+ (m|km) away/))
  })

  it('says there is no station near where there is none within 100 km, for the stripes and the measurements, and still shows the forecast', async () => {
    const wrapper = await mountMap()
    await listed(wrapper)
    // a click near Paris: a forecast point is there, and none of the German stations that have stripes or measure
    stage.emit('pick', { latitude: 48.8, longitude: 2.3, tolerance: 0.5 })
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-station-name"]').text()).toBe('PARIS-ORLY'))
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-card-measured"]').text()).toContain('No station within 100 km.'))
    expect(wrapper.find('[data-testid="map-card-stripes"]').text()).toContain('No station within 100 km.')
    expect(wrapper.find('[data-testid="map-card-measured"]').findAll('a')).toHaveLength(0)
    expect(wrapper.find('[data-testid="map-card-stripes"]').findAll('a')).toHaveLength(0)
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-card-forecast"] [data-testid="day-rows"]').exists()).toBe(true))
    // nothing was asked for the stripes of a station that is not near
    expect(asked.stripesValues).toEqual([])
  })

  it('keeps the place and takes the nearest station of the other layer when the layer is changed', async () => {
    const wrapper = await mountMap()
    await listed(wrapper)
    stage.emit('pick', NEAR_HAMBURG)
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-station-name"]').text()).toBe('HAMBURG-FUHLSBUETTEL'))
    await chooseLayer(wrapper, 'measured')
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-station-name"]').text()).toBe('Hamburg-Fuhlsbüttel'))
    expect(stage.props.selected.station_id).toBe('01975')
    expect(wrapper.find('[data-testid="map-place"]').exists()).toBe(true)
  })

  it('moves the focus to the station\'s name when it is chosen in the list, and back to its place in the list on Back', async () => {
    const wrapper = await mountMap()
    await listed(wrapper)
    const item = wrapper.find('[data-station-id="10384"]')
    await item.trigger('click')
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-station-name"]').text()).toBe('BERLIN-TEMPELHOF'))
    expect(document.activeElement).toBe(wrapper.find('[data-testid="map-station-name"]').element)
    await wrapper.find('[data-testid="map-back"]').trigger('click')
    await vi.waitFor(() => expect(document.activeElement).toBe(wrapper.find('[data-station-id="10384"]').element))
    expect(wrapper.find('[data-testid="map-station-name"]').exists()).toBe(false)
  })

  it('does not take the focus when the map picks it, which a click on the map is not a move in the panel', async () => {
    const wrapper = await mountMap()
    await listed(wrapper)
    const before = document.activeElement
    stage.emit('pick', NEAR_HAMBURG)
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-station-name"]').exists()).toBe(true))
    expect(document.activeElement).toBe(before)
  })

  it('is the station nearest the centre of the map for the keyboard\'s way to a place', async () => {
    const wrapper = await mountMap()
    await listed(wrapper)
    stage.emit('view', { latitude: 48.0, longitude: 11.6, zoom: 9 })
    const button = wrapper.find('[data-testid="map-pick-centre"]')
    expect(button.attributes('aria-describedby')).toBe('map-pick-centre-hint')
    expect(wrapper.find('#map-pick-centre-hint').text()).toBe('Picks the place at the centre of the map, which the arrow keys move.')
    await button.trigger('click')
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-station-name"]').text()).toBe('MUENCHEN-STADT'))
    expect(document.activeElement).toBe(wrapper.find('[data-testid="map-station-name"]').element)
    expect(wrapper.find('[data-testid="map-place"]').exists()).toBe(true)
  })
})

describe('the answers that fail', () => {
  it('tells where the stations of the layer could not be loaded, with the reason, and loads them again on Retry', async () => {
    stationsFailures = 1
    const wrapper = await mountMap()
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-failure"]').exists()).toBe(true))
    expect(wrapper.find('[data-testid="map-failure"]').text()).toContain('The stations could not be loaded')
    expect(wrapper.find('[data-testid="map-failure"]').text()).toContain('The forecast stations are not available')
    // nothing is drawn, and the panel does not claim a count
    expect(stage.props.stations).toEqual([])
    expect(wrapper.find('[data-testid="map-count"]').exists()).toBe(false)
    const retry = wrapper.find('[data-testid="map-failure"] button')
    expect(retry.text()).toBe('Retry')
    await retry.trigger('click')
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-count"]').exists()).toBe(true))
    expect(wrapper.find('[data-testid="map-failure"]').exists()).toBe(false)
    expect(stage.props.stations).toHaveLength(4)
  })

  it('tells a 200 page of HTML for the stations as a failure, not as a list with no stations (GH-3841)', async () => {
    // a `NUXT_API_BASE` that points at another site, or a proxy's error page: status 200, a page, no JSON
    registerEndpoint('/api/stations', (event) => {
      setResponseHeader(event, 'content-type', 'text/html')
      return '<!doctype html><html><body>Service is starting</body></html>'
    })
    // whatever way the test ends
    onTestFinished(() => {
      registerEndpoint('/api/stations', stationsOf)
    })
    const wrapper = await mountMap()
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-failure"]').exists()).toBe(true))
    expect(wrapper.find('[data-testid="map-failure"]').text()).toContain('The stations could not be loaded')
    expect(wrapper.find('[data-testid="map-failure"]').text()).toContain('The API answered with a web page, not data')
    // not the answer of a layer that has no stations, and nothing is drawn or counted
    expect(wrapper.find('[data-testid="map-empty"]').exists()).toBe(false)
    expect(stage.props.stations).toEqual([])
    expect(wrapper.find('[data-testid="map-count"]').exists()).toBe(false)
    // a retry that is answered with the stations brings them
    registerEndpoint('/api/stations', stationsOf)
    await wrapper.find('[data-testid="map-failure"] button').trigger('click')
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-count"]').exists()).toBe(true))
    expect(wrapper.find('[data-testid="map-failure"]').exists()).toBe(false)
  })

  it('tells JSON without the list of stations as a failure as well, and a real empty list as no stations (GH-3841)', async () => {
    registerEndpoint('/api/stations', () => ({ detail: 'something else' }))
    onTestFinished(() => {
      registerEndpoint('/api/stations', stationsOf)
    })
    const failed = await mountMap()
    await vi.waitFor(() => expect(failed.find('[data-testid="map-failure"]').exists()).toBe(true))
    expect(failed.find('[data-testid="map-failure"]').text()).toContain('no list of `stations`')
    expect(failed.find('[data-testid="map-empty"]').exists()).toBe(false)
    failed.unmount()
    mounted.pop()
    clearNuxtData()

    // the control: the list the backend gives for a layer with no stations is empty, and that is no failure
    registerEndpoint('/api/stations', () => ({ stations: [] }))
    const empty = await mountMap()
    await vi.waitFor(() => expect(empty.find('[data-testid="map-empty"]').exists()).toBe(true))
    expect(empty.find('[data-testid="map-empty"]').text()).toBe('This dataset has no stations with a position.')
    expect(empty.find('[data-testid="map-failure"]').exists()).toBe(false)
    registerEndpoint('/api/stations', stationsOf)
  })

  it('tells where the forecast could not be read, in the card, and reads it again on Retry', async () => {
    valuesStatus = 502
    const wrapper = await mountMap()
    await listed(wrapper)
    stage.emit('pick', { latitude: 53.6, longitude: 10.0, tolerance: 0.5 })
    const card = () => wrapper.find('[data-testid="map-card-forecast"]')
    await vi.waitFor(() => expect(card().find('[role="alert"]').exists()).toBe(true))
    expect(card().find('[role="alert"]').text()).toBe('Backend error 502: The forecast could not be read')
    // the other cards are not taken down by it
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-card-stripes"] [role="img"]').exists()).toBe(true))
    valuesStatus = 200
    await card().find('[data-testid="map-forecast"] button').trigger('click')
    await vi.waitFor(() => expect(card().find('[data-testid="day-rows"]').exists()).toBe(true))
    expect(card().find('[role="alert"]').exists()).toBe(false)
  })

  it('tells where a station has no stripes, with the reason, and offers to ask again', async () => {
    stripesStatus = 422
    const wrapper = await mountMap()
    await listed(wrapper)
    stage.emit('pick', { latitude: 53.6, longitude: 10.0, tolerance: 0.5 })
    const card = () => wrapper.find('[data-testid="map-card-stripes"]')
    await vi.waitFor(() => expect(card().find('[role="alert"]').exists()).toBe(true))
    expect(card().find('[role="alert"]').text()).toContain('This station has no complete years.')
    expect(card().find('[role="img"]').exists()).toBe(false)
    stripesStatus = 200
    await card().find('[data-testid="map-stripes"] button').trigger('click')
    await vi.waitFor(() => expect(card().find('[role="img"]').exists()).toBe(true))
  })

  it('tells where the list a card is made from could not be loaded, and loads it again on Retry', async () => {
    const wrapper = await mountMap()
    await listed(wrapper)
    // the measuring stations fail when the panel asks for them, after the forecast points came
    registerEndpoint('/api/stations', (event) => {
      const query = getQuery(event) as Record<string, string>
      if (query.network === 'observation') {
        setResponseStatus(event, 502)
        return { detail: 'down' }
      }
      return { stations: FORECAST_STATIONS }
    })
    stage.emit('pick', { latitude: 53.6, longitude: 10.0, tolerance: 0.5 })
    const card = () => wrapper.find('[data-testid="map-card-measured"]')
    await vi.waitFor(() => expect(card().find('[role="alert"]').exists()).toBe(true))
    expect(card().find('[role="alert"]').text()).toBe('The stations could not be loaded')
    registerEndpoint('/api/stations', stationsOf)
    await card().find('button').trigger('click')
    await vi.waitFor(() => expect(card().findAll('a')).toHaveLength(2))
  })
})

describe('the address', () => {
  it('is empty for the plain map, and holds the station and the place picked, the layer and the source, so that a link opens the same map', async () => {
    const wrapper = await mountMap()
    await listed(wrapper)
    const router = useRouter()
    expect(router.currentRoute.value.query).toEqual({})
    stage.emit('pick', { latitude: 53.45, longitude: 10.2, tolerance: 0.5 })
    await vi.waitFor(() => expect(router.currentRoute.value.query.station).toBe('10147'))
    expect(router.currentRoute.value.query).toEqual({ station: '10147', lat: '53.4500', lon: '10.2000' })
    await chooseLayer(wrapper, 'measured')
    await vi.waitFor(() => expect(router.currentRoute.value.query.layer).toBe('measured'))
    await vi.waitFor(() => expect(router.currentRoute.value.query.station).toBe('01975'))
    await wrapper.find('[data-testid="map-back"]').trigger('click')
    await vi.waitFor(() => expect(router.currentRoute.value.query).toEqual({ layer: 'measured' }))
  })

  it('opens on the station of the search, as the header\'s search links to it (`?station=`), and tells a screen reader', async () => {
    const wrapper = await mountMap('/map?station=10865')
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-station-name"]').text()).toBe('MUENCHEN-STADT'))
    expect(wrapper.find('[data-testid="map-announcement"]').text()).toBe('MUENCHEN-STADT chosen')
    // the map moves to it, once
    expect(stage.props.recentre).toBeGreaterThan(0)
    expect(stage.props.selected.station_id).toBe('10865')
  })

  it('opens on the layer and the source it names', async () => {
    const wrapper = await mountMap('/map?layer=measured&resolution=hourly&dataset=temperature_air&station=00044')
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-station-name"]').text()).toBe('Großenkneten'))
    expect(layerButton(wrapper, 'measured').attributes('aria-checked')).toBe('true')
    expect(asked.stations.some(query => query.parameters === 'hourly/temperature_air')).toBe(true)
  })

  it('starts the search of the panel on the text of the address (`?q=`), which the "more" of the header\'s search leads to', async () => {
    const wrapper = await mountMap('/map?layer=measured&q=hamburg')
    await vi.waitFor(() => expect(wrapper.findAll('[data-testid="map-list"] li').map(item => item.find('.font-semibold').text())).toEqual(['Hamburg-Fuhlsbüttel']))
    expect((wrapper.find('input[type="search"]').element as HTMLInputElement).value).toBe('hamburg')
    expect(wrapper.find('.map-list-title').text()).toBe('Results')
    // the text is the search's: the address the page writes does not carry it on
    await useRouter().push({ path: '/map', query: { layer: 'measured', q: 'arkona' } })
    await vi.waitFor(() => expect(wrapper.findAll('[data-testid="map-list"] li').map(item => item.find('.font-semibold').text())).toEqual(['Arkona']))
  })

  it('says where the address names a station the layer does not have, and shows the list', async () => {
    const wrapper = await mountMap('/map?station=00000')
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-unknown"]').exists()).toBe(true))
    expect(wrapper.find('[data-testid="map-unknown"]').text()).toBe('There is no station 00000 on this map.')
    expect(wrapper.find('[data-testid="map-station-name"]').exists()).toBe(false)
    await vi.waitFor(() => expect(useRouter().currentRoute.value.query.station).toBeUndefined())
  })

  it('takes a station that the address names from outside while the map is open, as the header\'s search does', async () => {
    const wrapper = await mountMap()
    await listed(wrapper)
    await useRouter().push({ path: '/map', query: { station: '10384' } })
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-station-name"]').text()).toBe('BERLIN-TEMPELHOF'))
    const before = stage.props.recentre
    await useRouter().push({ path: '/map', query: { station: '10865' } })
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-station-name"]').text()).toBe('MUENCHEN-STADT'))
    expect(stage.props.recentre).toBeGreaterThan(before)
  })

  it('does not take its own earlier address for one from outside when it has moved on', async () => {
    const wrapper = await mountMap()
    await listed(wrapper)
    // the second pick comes while the address of the first is on its way: when it arrives, the page has moved on
    stage.emit('pick', { latitude: 53.6, longitude: 10.0, tolerance: 0.5 })
    await nextTick()
    stage.emit('pick', { latitude: 48.2, longitude: 11.5, tolerance: 0.5 })
    await vi.waitFor(() => expect(useRouter().currentRoute.value.query.station).toBe('10865'))
    await new Promise(resolve => setTimeout(resolve, 50))
    expect(wrapper.find('[data-testid="map-station-name"]').text()).toBe('MUENCHEN-STADT')
    expect(useRouter().currentRoute.value.query.station).toBe('10865')
    // a pick of the page's own is no pick from outside: the map is never moved to it (it was where the reader clicked)
    expect(stage.props.recentre).toBe(0)
  })
})

describe('the layout of the map and its panel', () => {
  it('has the panel first on a wide screen, beside the map, in the order the window shows them', async () => {
    stubMediaQueries(true)
    const wrapper = await mountMap()
    const parts = wrapper.findAll('.map-tool > *').map(part => part.attributes('data-testid'))
    expect(parts).toEqual(['map-panel', 'map-stage'])
  })

  it('has the map first on a phone, the panel a sheet under it, in the order the window shows them: the keyboard meets them so', async () => {
    stubMediaQueries(false)
    const wrapper = await mountMap()
    const parts = wrapper.findAll('.map-tool > *').map(part => part.attributes('data-testid'))
    expect(parts).toEqual(['map-stage', 'map-panel'])
    await vi.waitFor(() => expect(wrapper.find('[data-testid="station-map"]').exists()).toBe(true))
    // the chips are before the map, and the panel's search after it
    const order = [...wrapper.element.querySelectorAll('[data-testid="map-layers-button"], [data-testid="station-map"], input[type="search"]')].map(element => element.getAttribute('data-testid') ?? 'search')
    expect(order).toEqual(['map-layers-button', 'station-map', 'search'])
  })

  it('keeps the one map element while the panel changes from the list to a station and back', async () => {
    const wrapper = await mountMap()
    await listed(wrapper)
    const map = wrapper.find('[data-testid="station-map"]').element
    stage.emit('pick', { latitude: 53.6, longitude: 10.0, tolerance: 0.5 })
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-station-name"]').exists()).toBe(true))
    expect(wrapper.find('[data-testid="station-map"]').element).toBe(map)
  })

  it('is named by its h1, with the panel and its cards named by headings', async () => {
    const wrapper = await mountMap()
    await listed(wrapper)
    expect(wrapper.findAll('h1')).toHaveLength(1)
    expect(panel(wrapper).attributes('aria-labelledby')).toBe('map-panel-title')
    expect(wrapper.find('#map-panel-title').exists()).toBe(true)
    stage.emit('pick', { latitude: 53.6, longitude: 10.0, tolerance: 0.5 })
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-card-measured"]').exists()).toBe(true))
    expect(wrapper.findAll('[data-testid^="map-card-"] h3').map(heading => heading.text())).toEqual(['Forecast', 'Climate stripes', 'Measurements'])
    expect(wrapper.find('#map-panel-title').text()).toBe('HAMBURG-FUHLSBUETTEL')
  })
})

describe('a pick when the layer or the dataset changes', () => {
  const headingOf = (wrapper: Awaited<ReturnType<typeof mountMap>>) => wrapper.find('[data-testid="map-station-name"]')

  it('is picked again by the place it was at, never by the number of the station: Jan Mayen is not Doberlug-Kirchhain', async () => {
    addCollision()
    const wrapper = await mountMap('/map?station=01001')
    await vi.waitFor(() => expect(headingOf(wrapper).text()).toBe('JAN MAYEN'))
    await chooseLayer(wrapper, 'measured')
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-none-near"]').exists()).toBe(true))
    // no measuring station is within 100 km of Jan Mayen: nothing is picked, and what is shown is not the station with its number
    expect(headingOf(wrapper).exists()).toBe(false)
    expect(wrapper.find('[data-testid="map-none-near"]').text()).toBe('No station within 100 km of that point.')
    expect(wrapper.find('[data-testid="map-announcement"]').text()).toBe('No station within 100 km of that point.')
    expect(stage.props.selected).toBeNull()
    await vi.waitFor(() => expect(useRouter().currentRoute.value.query).toEqual({ layer: 'measured' }))
    // and back: the place is kept, and the forecast point at it is Jan Mayen again
    await chooseLayer(wrapper, 'forecast')
    await vi.waitFor(() => expect(headingOf(wrapper).text()).toBe('JAN MAYEN'))
    await vi.waitFor(() => expect(useRouter().currentRoute.value.query).toEqual({ station: '01001' }))
  })

  it('is picked again by the place in the other direction too: Doberlug-Kirchhain is not Jan Mayen', async () => {
    addCollision()
    const wrapper = await mountMap('/map?layer=measured&station=01001')
    await vi.waitFor(() => expect(headingOf(wrapper).text()).toBe('Doberlug-Kirchhain'))
    await chooseLayer(wrapper, 'forecast')
    // the forecast point within reach of Doberlug is Berlin-Tempelhof, 91 km away
    await vi.waitFor(() => expect(headingOf(wrapper).exists()).toBe(true))
    expect(headingOf(wrapper).text()).toBe('BERLIN-TEMPELHOF')
    expect(stage.props.selected.station_id).toBe('10384')
    await vi.waitFor(() => expect(useRouter().currentRoute.value.query.station).toBe('10384'))
    expect(wrapper.find('[data-testid="map-place"]').text()).toMatch(/9\d km from this station/)
  })

  it('keeps the station of the address across a change of layer: it has its place from the start', async () => {
    const wrapper = await mountMap('/map?station=10147')
    await vi.waitFor(() => expect(headingOf(wrapper).text()).toBe('HAMBURG-FUHLSBUETTEL'))
    await chooseLayer(wrapper, 'measured')
    await vi.waitFor(() => expect(headingOf(wrapper).text()).toBe('Hamburg-Fuhlsbüttel'))
    expect(wrapper.find('[data-testid="map-unknown"]').exists()).toBe(false)
    await vi.waitFor(() => expect(useRouter().currentRoute.value.query).toMatchObject({ layer: 'measured', station: '01975' }))
    await chooseLayer(wrapper, 'forecast')
    await vi.waitFor(() => expect(headingOf(wrapper).text()).toBe('HAMBURG-FUHLSBUETTEL'))
    await vi.waitFor(() => expect(useRouter().currentRoute.value.query).toEqual({ station: '10147' }))
  })

  it('keeps the place of a station chosen in the list, which the page wrote to the address and read back, across a change of layer', async () => {
    const wrapper = await mountMap()
    await listed(wrapper)
    await wrapper.find('[data-station-id="10147"]').trigger('click')
    await vi.waitFor(() => expect(useRouter().currentRoute.value.query.station).toBe('10147'))
    // the address the page wrote is not taken for one from outside, which would take the place out of the pick
    await new Promise(resolve => setTimeout(resolve, 30))
    await chooseLayer(wrapper, 'measured')
    await vi.waitFor(() => expect(headingOf(wrapper).text()).toBe('Hamburg-Fuhlsbüttel'))
  })

  it('tells the station it has picked again, which is another than the one in the heading before', async () => {
    const wrapper = await mountMap('/map?station=10147')
    await vi.waitFor(() => expect(headingOf(wrapper).text()).toBe('HAMBURG-FUHLSBUETTEL'))
    await chooseLayer(wrapper, 'measured')
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-announcement"]').text()).toBe('Hamburg-Fuhlsbüttel chosen'))
  })

  it('picks again for another dataset by the place, and takes a station that is under the place for the same station', async () => {
    const wrapper = await mountMap('/map?layer=measured&station=00011')
    await vi.waitFor(() => expect(headingOf(wrapper).text()).toBe('Donaueschingen (Landeplatz)'))
    // the hourly list has no station within 100 km of it
    ;(wrapper.vm as any).source = { resolution: 'hourly', dataset: 'temperature_air' }
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-none-near"]').exists()).toBe(true))
    expect(headingOf(wrapper).exists()).toBe(false)
  })

  it('does not show the stations of the list before it for the one asked for: the list and its status are the key\'s', async () => {
    const wrapper = await mountMap('/map?layer=measured')
    await vi.waitFor(() => expect(stage.props.stations).toHaveLength(3))
    const vm = wrapper.vm as any
    vm.source = { resolution: 'hourly', dataset: 'temperature_air' }
    // at once, before the answer: nothing of the daily list
    await nextTick()
    expect(stage.props.stations.every((entry: any) => entry.station_id !== '01975')).toBe(true)
    await vi.waitFor(() => expect(stage.props.stations.map((entry: any) => entry.station_id)).toEqual(['00044']))
  })
})

describe('the station the tool picks for a place', () => {
  it('is within 100 km of the place, in the layer shown too: a click far from every station picks none and says so', async () => {
    const wrapper = await mountMap()
    await listed(wrapper)
    // the forecast layer: the Atlantic off Portugal, 1,500 km from the nearest of the points
    stage.emit('pick', { latitude: 38, longitude: -20, tolerance: 0.5 })
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-none-near"]').exists()).toBe(true))
    expect(wrapper.find('[data-testid="map-station-name"]').exists()).toBe(false)
    expect(useRouter().currentRoute.value.query).toEqual({})
    // the measurements: south-east England, 361 km from Geilenkirchen in the real list
    await chooseLayer(wrapper, 'measured')
    await vi.waitFor(() => expect(stage.props.stations).toHaveLength(3))
    stage.emit('pick', { latitude: 51.22, longitude: 0.88, tolerance: 0.5 })
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-none-near"]').text()).toContain('100 km'))
    expect(wrapper.find('[data-testid="map-station-name"]').exists()).toBe(false)
    // a pick that has a station clears the note
    stage.emit('pick', { latitude: 53.6, longitude: 10.0, tolerance: 0.5 })
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-station-name"]').exists()).toBe(true))
    expect(wrapper.find('[data-testid="map-none-near"]').exists()).toBe(false)
  })

  it('is within 100 km for the centre of the map as well', async () => {
    const wrapper = await mountMap()
    await listed(wrapper)
    stage.emit('view', { latitude: 38, longitude: -20, zoom: 5 })
    await wrapper.find('[data-testid="map-pick-centre"]').trigger('click')
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-none-near"]').exists()).toBe(true))
  })

  describe('where a station has stopped measuring', () => {
    // a closed station is nearer to the click than the one that reports; it is not the one offered
    const CLOSED_NEAR = station('99001', 'Hamburg-Altstadt', 53.55, 10.0, { start_timestamp: '1900-01-01T00:00:00+00:00', end_timestamp: '2009-12-31T00:00:00+00:00' })
    const mountWithClosed = async () => {
      DAILY_STATIONS.push(CLOSED_NEAR)
      const wrapper = await mountMap('/map?layer=measured')
      await vi.waitFor(() => expect(stage.props.stations).toHaveLength(4))
      return wrapper
    }
    afterEach(() => {
      const at = DAILY_STATIONS.indexOf(CLOSED_NEAR)
      if (at !== -1)
        DAILY_STATIONS.splice(at, 1)
    })

    it('prefers the nearest that still reports, though a closed one is nearer', async () => {
      const wrapper = await mountWithClosed()
      stage.emit('pick', { latitude: 53.5, longitude: 10.0, tolerance: 0.1 })
      await vi.waitFor(() => expect(wrapper.find('[data-testid="map-station-name"]').text()).toBe('Hamburg-Fuhlsbüttel'))
    })

    it('is the closed station itself where it is picked directly, on its dot', async () => {
      const wrapper = await mountWithClosed()
      stage.emit('pick', { latitude: 53.5505, longitude: 10.0, tolerance: 1 })
      await vi.waitFor(() => expect(wrapper.find('[data-testid="map-station-name"]').text()).toBe('Hamburg-Altstadt'))
      // its years are told, as it is no running station
      expect(wrapper.find('[data-testid="map-card-measured"]').text()).toContain('1900 to 2009')
    })

    it('is the nearest closed station where none reports within reach, with its years', async () => {
      const wrapper = await mountMap('/map?layer=measured')
      await vi.waitFor(() => expect(stage.props.stations).toHaveLength(3))
      // Donaueschingen stopped in 2001 and no station that reports is within 100 km of it
      stage.emit('pick', { latitude: 47.9, longitude: 8.6, tolerance: 0.1 })
      await vi.waitFor(() => expect(wrapper.find('[data-testid="map-station-name"]').text()).toBe('Donaueschingen (Landeplatz)'))
      expect(wrapper.find('[data-testid="map-card-measured"]').text()).toContain('1980 to 2001')
    })

    it('is the same station when the layer is changed with a closed station picked on its dot', async () => {
      const wrapper = await mountWithClosed()
      stage.emit('pick', { latitude: 53.5505, longitude: 10.0, tolerance: 1 })
      await vi.waitFor(() => expect(wrapper.find('[data-testid="map-station-name"]').text()).toBe('Hamburg-Altstadt'))
      ;(wrapper.vm as any).source = { resolution: 'daily', dataset: 'more_precip' }
      // the other dataset's list has come and the pick has been made again in it (the heading is the old pick's until then)
      await vi.waitFor(() => expect(asked.stations.at(-1)).toMatchObject({ parameters: 'daily/more_precip' }))
      await new Promise(resolve => setTimeout(resolve, 80))
      await vi.waitFor(() => expect(wrapper.find('[data-testid="map-station-name"]').exists()).toBe(true))
      expect(wrapper.find('[data-testid="map-station-name"]').text()).toBe('Hamburg-Altstadt')
    })

    it('picks again for the place, the one that reports before a closed one that is nearer, when the layer is changed', async () => {
      DAILY_STATIONS.push(CLOSED_NEAR)
      const wrapper = await mountMap()
      await listed(wrapper)
      // a place on the forecast layer, 3 km from the closed Hamburg-Altstadt, 12 km from Hamburg-Fuhlsbüttel
      stage.emit('pick', { latitude: 53.52, longitude: 10.0, tolerance: 0.1, tap: 0 })
      await vi.waitFor(() => expect(wrapper.find('[data-testid="map-station-name"]').text()).toBe('HAMBURG-FUHLSBUETTEL'))
      await chooseLayer(wrapper, 'measured')
      await vi.waitFor(() => expect(wrapper.find('[data-testid="map-station-name"]').text()).toBe('Hamburg-Fuhlsbüttel'))
    })

    it('shows a station that reports as running, since its first year, where its end is some days ago', async () => {
      const wrapper = await mountMap()
      await listed(wrapper)
      stage.emit('pick', { latitude: 53.6, longitude: 10.0, tolerance: 0.5 })
      const card = () => wrapper.find('[data-testid="map-card-measured"]')
      await vi.waitFor(() => expect(card().text()).toContain('since 1891'))
      expect(card().text()).not.toContain('1891 to')
    })
  })
})

describe('why a farther station was picked, and which place the pick is for (GH-3875)', () => {
  // the case of the issue: a station that stopped long ago is nearer to the place than the one that reports
  const CLOSED = station('99001', 'Hamburg-Altstadt', 53.55, 10.0, { start_timestamp: '1900-01-01T00:00:00+00:00', end_timestamp: '2009-12-31T00:00:00+00:00' })
  const why = (wrapper: Awaited<ReturnType<typeof mountMap>>) => wrapper.find('[data-testid="map-why"]')
  const headingOf = (wrapper: Awaited<ReturnType<typeof mountMap>>) => wrapper.find('[data-testid="map-station-name"]')
  const mountMeasured = async (closed = CLOSED) => {
    DAILY_STATIONS.push(closed)
    const wrapper = await mountMap('/map?layer=measured')
    await vi.waitFor(() => expect(stage.props.stations).toHaveLength(4))
    return wrapper
  }
  afterEach(() => {
    const at = DAILY_STATIONS.indexOf(CLOSED)
    if (at !== -1)
      DAILY_STATIONS.splice(at, 1)
    const noEnd = DAILY_STATIONS.findIndex(entry => entry.station_id === '99003')
    if (noEnd !== -1)
      DAILY_STATIONS.splice(noEnd, 1)
  })

  it('says that the station is the nearest that reports, and names the nearer one that has stopped, with its distance and its last year', async () => {
    const wrapper = await mountMeasured()
    stage.emit('pick', { latitude: 53.5, longitude: 10.0, tolerance: 0.1 })
    await vi.waitFor(() => expect(headingOf(wrapper).text()).toBe('Hamburg-Fuhlsbüttel'))
    expect(why(wrapper).find('p').text()).toBe('The nearest station that still reports. Closer: Hamburg-Altstadt, 5.6 km, until 2009.')
    expect(why(wrapper).find('button').text()).toBe('Pick Hamburg-Altstadt instead')
    // it is a note of the measurements card, which is about this station
    expect(wrapper.find('[data-testid="map-card-measured"]').find('[data-testid="map-why"]').exists()).toBe(true)
  })

  it('has the announcement of the pick say it too, so that a screen reader hears why the station is not the nearest', async () => {
    const wrapper = await mountMeasured()
    stage.emit('pick', { latitude: 53.5, longitude: 10.0, tolerance: 0.1 })
    await vi.waitFor(() => expect(headingOf(wrapper).exists()).toBe(true))
    expect(wrapper.find('[data-testid="map-announcement"]').text()).toBe('Hamburg-Fuhlsbüttel chosen. The nearest station that still reports. Closer: Hamburg-Altstadt, 5.6 km, until 2009.')
  })

  it('says it when the layer is changed and the station for the place is picked again', async () => {
    DAILY_STATIONS.push(CLOSED)
    const wrapper = await mountMap()
    await listed(wrapper)
    stage.emit('pick', { latitude: 53.52, longitude: 10.0, tolerance: 0.1, tap: 0 })
    await vi.waitFor(() => expect(headingOf(wrapper).text()).toBe('HAMBURG-FUHLSBUETTEL'))
    // on the forecast layer the card of the measurements says it, and offers no pick: the station shown is the forecast's
    await vi.waitFor(() => expect(why(wrapper).text()).toContain('Closer: Hamburg-Altstadt'))
    expect(wrapper.find('[data-testid="map-pick-closer"]').exists()).toBe(false)
    await chooseLayer(wrapper, 'measured')
    await vi.waitFor(() => expect(headingOf(wrapper).text()).toBe('Hamburg-Fuhlsbüttel'))
    expect(why(wrapper).text()).toContain('The nearest station that still reports. Closer: Hamburg-Altstadt, 3.3 km, until 2009.')
    expect(wrapper.find('[data-testid="map-announcement"]').text()).toContain('Closer: Hamburg-Altstadt')
  })

  it('picks the nearer station on request, for the same place, and moves the focus to its heading', async () => {
    const wrapper = await mountMeasured()
    stage.emit('pick', { latitude: 53.5, longitude: 10.0, tolerance: 0.1 })
    await vi.waitFor(() => expect(why(wrapper).exists()).toBe(true))
    await wrapper.find('[data-testid="map-pick-closer"]').trigger('click')
    await vi.waitFor(() => expect(headingOf(wrapper).text()).toBe('Hamburg-Altstadt'))
    // the place is the one clicked, as it was: 5.6 km from the station now picked
    expect(wrapper.find('[data-testid="map-place"]').text()).toBe('A point on the map, 5.6 km from this station')
    // the nearest is the station, so there is nothing more to say, and the button that was pressed is gone
    expect(why(wrapper).exists()).toBe(false)
    expect(wrapper.find('[data-testid="map-announcement"]').text()).toBe('Hamburg-Altstadt chosen')
    expect(document.activeElement).toBe(headingOf(wrapper).element)
    expect(wrapper.find('[data-testid="map-card-measured"]').text()).toContain('1900 to 2009')
  })

  it('says nothing where the station is the nearest, or the one picked on its dot', async () => {
    const wrapper = await mountMeasured()
    stage.emit('pick', { latitude: 53.5505, longitude: 10.0, tolerance: 1 })
    await vi.waitFor(() => expect(headingOf(wrapper).text()).toBe('Hamburg-Altstadt'))
    expect(why(wrapper).exists()).toBe(false)
    stage.emit('pick', { latitude: 53.6332, longitude: 9.9881, tolerance: 1 })
    await vi.waitFor(() => expect(headingOf(wrapper).text()).toBe('Hamburg-Fuhlsbüttel'))
    expect(why(wrapper).exists()).toBe(false)
    expect(wrapper.find('[data-testid="map-announcement"]').text()).toBe('Hamburg-Fuhlsbüttel chosen')
  })

  it('names the nearer station without a year where its list gives it no end', async () => {
    const wrapper = await mountMeasured(station('99003', 'Hamburg-Ohneende', 53.55, 10.0) as typeof CLOSED)
    stage.emit('pick', { latitude: 53.5, longitude: 10.0, tolerance: 0.1 })
    await vi.waitFor(() => expect(why(wrapper).exists()).toBe(true))
    expect(why(wrapper).text()).toContain('Closer: Hamburg-Ohneende, 5.6 km, no end date known.')
  })

  describe('the place of the pick', () => {
    it('is a point on the map for a click, and is told so', async () => {
      const wrapper = await mountMeasured()
      stage.emit('pick', { latitude: 53.5, longitude: 10.0, tolerance: 0.1 })
      await vi.waitFor(() => expect(wrapper.find('[data-testid="map-place"]').text()).toMatch(/^A point on the map, \d+ km from this station$/))
    })

    it('is the centre of the map for the keyboard pick of it, and is told so', async () => {
      DAILY_STATIONS.push(CLOSED)
      const wrapper = await mountMap('/map?layer=measured')
      await vi.waitFor(() => expect(stage.props.stations).toHaveLength(4))
      stage.emit('view', { latitude: 53.5, longitude: 10.0, zoom: 9 })
      await wrapper.find('[data-testid="map-pick-centre"]').trigger('click')
      await vi.waitFor(() => expect(wrapper.find('[data-testid="map-place"]').text()).toMatch(/^The place at the centre of the map when it was picked, \d+ km from this station$/))
    })

    it('is the position of the forecast station that was chosen, where the layer is changed to the measurements: no click was made, and none is told', async () => {
      DAILY_STATIONS.push(CLOSED)
      const wrapper = await mountMap()
      await listed(wrapper)
      await wrapper.find('[data-station-id="10147"]').trigger('click')
      await vi.waitFor(() => expect(headingOf(wrapper).text()).toBe('HAMBURG-FUHLSBUETTEL'))
      await chooseLayer(wrapper, 'measured')
      await vi.waitFor(() => expect(headingOf(wrapper).text()).toBe('Hamburg-Fuhlsbüttel'))
      const place = wrapper.find('[data-testid="map-place"]')
      expect(place.text()).toMatch(/^The position of HAMBURG-FUHLSBUETTEL, .* from this station$/)
      expect(place.text()).not.toContain('point')
    })
  })

  describe('the place that the address brings', () => {
    it('is told as the place picked, not as a click: a link, a reload or the browser\'s Back does not say how the place was made', async () => {
      DAILY_STATIONS.push(CLOSED)
      const wrapper = await mountMap('/map?layer=measured&station=01975&lat=53.5&lon=10.0')
      await vi.waitFor(() => expect(headingOf(wrapper).text()).toBe('Hamburg-Fuhlsbüttel'))
      expect(wrapper.find('[data-testid="map-place"]').text()).toMatch(/^The place picked, \d+ km from this station$/)
      expect(wrapper.find('[data-testid="map-place"]').text()).not.toContain('point')
    })

    it('has the announcement of the station of the address carry the reason, as that of a pick does', async () => {
      DAILY_STATIONS.push(CLOSED)
      const wrapper = await mountMap('/map?layer=measured&station=01975&lat=53.5&lon=10.0')
      await vi.waitFor(() => expect(wrapper.find('[data-testid="map-announcement"]').text()).toBe('Hamburg-Fuhlsbüttel chosen. The nearest station that still reports. Closer: Hamburg-Altstadt, 5.6 km, until 2009.'))
    })

    it('says nothing of a nearer station that has stopped where the station is not the one the rule picks for the place: the reader chose it', async () => {
      DAILY_STATIONS.push(CLOSED)
      // Hamburg-Fuhlsbüttel is the one the rule picks for the place; the closed one is picked by address, a station of its own
      const wrapper = await mountMap('/map?layer=measured&station=00183&lat=53.5&lon=10.0')
      await vi.waitFor(() => expect(headingOf(wrapper).text()).toBe('Arkona'))
      expect(why(wrapper).exists()).toBe(false)
      expect(wrapper.find('[data-testid="map-announcement"]').text()).toBe('Arkona chosen')
    })
  })

  it('keeps the origin of the place through a dataset that has no station within reach: the position of the station chosen from the list is not told as a click', async () => {
    DAILY_STATIONS.push(CLOSED)
    // the solar radiation of this test has stations in the Black Forest only, 700 km from Hamburg
    solarStations = [FELDBERG, FREIBURG]
    const wrapper = await mountMap()
    await listed(wrapper)
    await wrapper.find('[data-station-id="10147"]').trigger('click')
    await vi.waitFor(() => expect(headingOf(wrapper).text()).toBe('HAMBURG-FUHLSBUETTEL'))
    await chooseLayer(wrapper, 'measured')
    await vi.waitFor(() => expect(headingOf(wrapper).text()).toBe('Hamburg-Fuhlsbüttel'))
    ;(wrapper.vm as any).source = { resolution: 'daily', dataset: 'solar' }
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-none-near"]').exists()).toBe(true))
    ;(wrapper.vm as any).source = { resolution: 'daily', dataset: 'more_precip' }
    await vi.waitFor(() => expect(headingOf(wrapper).text()).toBe('Hamburg-Fuhlsbüttel'))
    const place = wrapper.find('[data-testid="map-place"]')
    expect(place.text()).toMatch(/^The position of HAMBURG-FUHLSBUETTEL, .* from this station$/)
    expect(place.text()).not.toContain('point')
  })

  describe('the dots of the stations that have stopped', () => {
    it('are drawn apart from the dots that report on the measuring layer, which the map is told by the rule of its list, and the legend says what each is', async () => {
      DAILY_STATIONS.push(CLOSED)
      const wrapper = await mountMap('/map?layer=measured')
      await vi.waitFor(() => expect(stage.props.stations).toHaveLength(4))
      const reporting = stage.props.reporting as (entry: unknown) => boolean
      expect(reporting(DAILY_STATIONS.find(entry => entry.station_id === '01975'))).toBe(true)
      expect(reporting(CLOSED)).toBe(false)
      const legend = wrapper.find('[data-testid="map-legend"]')
      // the legend is in the panel of the layers button, under the switch, with a heading of its own (GH-4227), and not a box on the map
      expect(wrapper.find('[data-testid="map-layers-panel"] #map-legend-title').text()).toBe('Legend')
      expect(wrapper.find('[data-testid="map-layers-panel"] [data-testid="map-legend"]').exists()).toBe(true)
      expect(wrapper.find('.map-canvas > .map-legend').exists()).toBe(false)
      // and the map's own description says what its dots and discs are, for a screen reader that does not open the panel
      expect(stage.props.describedBy).toBe('map-legend-description')
      expect(wrapper.find('#map-legend-description').text()).toBe('A filled dot is a station that still reports, a hollow dot one that has stopped. A number is a group of stations: click to zoom in. The filled part of its ring shows how many still report.')
      // the map opens at an outer zoom, where the stations are grouped: the legend says what a number is
      expect(legend.findAll('li').map(item => item.text())).toEqual(['Still reporting', 'Stopped reporting', '12 A number is a group of stations: click to zoom in. The filled part of its ring shows how many still report.'])
      // the two swatches are different shapes (filled and hollow), and no colour alone
      expect(legend.find('[data-testid="map-legend-reporting"]').classes()).not.toContain('map-legend-dot-stopped')
      expect(legend.find('[data-testid="map-legend-stopped"]').classes()).toContain('map-legend-dot-stopped')
      expect(legend.findAll('span[aria-hidden="true"]')).toHaveLength(3)
      // from the zoom where every station is its own dot there are no groups, and the legend has the two dots only
      stage.emit('view', { latitude: 53, longitude: 10, zoom: 9 })
      await vi.waitFor(() => expect(wrapper.find('[data-testid="map-legend"]').findAll('li').map(item => item.text())).toEqual(['Still reporting', 'Stopped reporting']))
    })

    it('are not told apart on the forecast layer, whose points have no status: no rule, and a legend of the groups only', async () => {
      const wrapper = await mountMap()
      await listed(wrapper)
      expect(stage.props.reporting).toBeUndefined()
      expect(wrapper.find('[data-testid="map-legend"]').findAll('li').map(item => item.text())).toEqual(['12 A number is a group of stations: click to zoom in'])
      await chooseLayer(wrapper, 'measured')
      await vi.waitFor(() => expect(wrapper.find('[data-testid="map-legend"]').findAll('li')).toHaveLength(3))
      await chooseLayer(wrapper, 'forecast')
      await vi.waitFor(() => expect(wrapper.find('[data-testid="map-legend"]').findAll('li')).toHaveLength(1))
      expect(wrapper.find('#map-legend-description').text()).toBe('A number is a group of stations: click to zoom in.')
      // at the zoom where no station is grouped the forecast's points need no legend, in the panel or in the map's description
      stage.emit('view', { latitude: 53, longitude: 10, zoom: 9 })
      await vi.waitFor(() => expect(wrapper.find('[data-testid="map-legend"]').exists()).toBe(false))
      expect(wrapper.find('#map-legend-title').exists()).toBe(false)
      expect(wrapper.find('#map-legend-description').text()).toBe('')
      expect(stage.props.describedBy).toBeUndefined()
    })
  })
})

describe('an address edited by hand', () => {
  it('names a dataset of the resolution, where it names one the resolution has not: the source is one that DWD has, and no request is made for the other', async () => {
    const wrapper = await mountMap('/map?layer=measured&resolution=hourly')
    await vi.waitFor(() => expect(stage.props.stations.map((entry: any) => entry.station_id)).toEqual(['00044']))
    expect((wrapper.vm as any).source).toEqual({ resolution: 'hourly', dataset: 'temperature_air' })
    expect(asked.stations.filter(query => query.network === 'observation').map(query => query.parameters)).toEqual(['hourly/temperature_air'])
    await vi.waitFor(() => expect(useRouter().currentRoute.value.query).toMatchObject({ layer: 'measured', resolution: 'hourly', dataset: 'temperature_air' }))
  })

  it('names a resolution that DWD has not: the default source', async () => {
    const wrapper = await mountMap('/map?layer=measured&resolution=weekly&dataset=nothing')
    await vi.waitFor(() => expect(stage.props.stations).toHaveLength(3))
    expect((wrapper.vm as any).source).toEqual({ resolution: 'daily', dataset: 'climate_summary' })
  })

  it('names a station that does not exist, with a position: nothing is opened at the position, and the panel says so', async () => {
    const wrapper = await mountMap('/map?station=abc&lat=0&lon=0')
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-unknown"]').exists()).toBe(true))
    expect(wrapper.find('[data-testid="map-unknown"]').text()).toBe('There is no station abc on this map.')
    expect(wrapper.find('[data-testid="map-station-name"]').exists()).toBe(false)
    expect(stage.props.selected).toBeNull()
    await vi.waitFor(() => expect(useRouter().currentRoute.value.query).toEqual({}))
  })

  it('does not leave a move to a station that is not there for the next pick: the map is not recentred by it', async () => {
    const wrapper = await mountMap('/map?station=99998')
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-unknown"]').exists()).toBe(true))
    stage.emit('pick', { latitude: 53.6, longitude: 10.0, tolerance: 0.5 })
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-station-name"]').exists()).toBe(true))
    expect(stage.props.recentre).toBe(0)
  })

  it('moves the map to the station of the address once, when the station is there', async () => {
    const wrapper = await mountMap('/map?station=10865')
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-station-name"]').exists()).toBe(true))
    expect(stage.props.recentre).toBe(1)
  })
})

// A position of the address with no station (GH-3790): what the search of the header leads to for coordinates typed in
describe('an address that names a position and no station', () => {
  it('picks the station for the place as a click on the map would, and moves the map to the position, not to the station', async () => {
    const wrapper = await mountMap('/map?lat=52.5200&lon=13.4000')
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-station-name"]').text()).toBe('BERLIN-TEMPELHOF'))
    expect(stage.props.selected.station_id).toBe('10384')
    // the place is the position, which is not the station's (it is 6 km off it)
    expect(stage.props.place).toEqual({ latitude: 52.52, longitude: 13.4 })
    expect(stage.props.goTo).toMatchObject({ latitude: 52.52, longitude: 13.4, count: 1 })
    // the station is not what the map is recentred on, and it is kept where it is
    expect(stage.props.recentre).toBe(0)
    // the address says the station and the place from then on, so that a link is the same map
    await vi.waitFor(() => expect(useRouter().currentRoute.value.query).toEqual({ station: '10384', lat: '52.5200', lon: '13.4000' }))
    expect(wrapper.find('[data-testid="map-announcement"]').text()).toBe('BERLIN-TEMPELHOF chosen')
  })

  it('waits for the list of stations, which a pick is made from', async () => {
    const wrapper = await mountMap('/map?lat=48.1&lon=11.5')
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-station-name"]').text()).toBe('MUENCHEN-STADT'))
    expect(stage.props.goTo).toMatchObject({ latitude: 48.1, longitude: 11.5 })
  })

  it('says that there is no station within reach where there is none, and still moves the map to the position', async () => {
    const wrapper = await mountMap('/map?lat=-33.9&lon=151.2')
    await vi.waitFor(() => expect(stage.props.goTo).toMatchObject({ latitude: -33.9, longitude: 151.2, count: 1 }))
    await vi.waitFor(() => expect(wrapper.text()).toContain('No station within'))
    expect(stage.props.selected).toBeNull()
    // the address keeps the position, so that a link and a reload ask about the same place; and it takes nothing more of it
    await vi.waitFor(() => expect(useRouter().currentRoute.value.query).toEqual({ lat: '-33.9000', lon: '151.2000' }))
    expect(stage.props.goTo.count).toBe(1)
    expect(wrapper.text()).toContain('No station within')
  })

  it('moves the map to the position where the list of stations fails, and shows the failure', async () => {
    stationsFailures = 3
    const wrapper = await mountMap('/map?lat=52.52&lon=13.4')
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-failure"]').exists()).toBe(true))
    expect(stage.props.goTo).toMatchObject({ latitude: 52.52, longitude: 13.4, count: 1 })
    expect(stage.props.selected).toBeNull()
    // the position is still the address's
    expect(useRouter().currentRoute.value.query).toMatchObject({ lat: '52.52', lon: '13.4' })
  })

  it('takes a position that the search of the header writes while the map is open, once, and again where it is typed again', async () => {
    const wrapper = await mountMap('/map?station=10865')
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-station-name"]').text()).toBe('MUENCHEN-STADT'))
    const router = useRouter()
    await router.push('/map?lat=52.5200&lon=13.4000')
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-station-name"]').text()).toBe('BERLIN-TEMPELHOF'))
    expect(stage.props.goTo.count).toBe(1)
    await router.push('/map?lat=53.6&lon=10.0')
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-station-name"]').text()).toBe('HAMBURG-FUHLSBUETTEL'))
    expect(stage.props.goTo.count).toBe(2)
  })

  it('is no position for a latitude or a longitude that is not one: the plain map', async () => {
    const wrapper = await mountMap('/map?lat=north&lon=13.4')
    await vi.waitFor(() => expect(stage.props.stations.length).toBeGreaterThan(0))
    expect(stage.props.goTo ?? null).toBeNull()
    expect(wrapper.find('[data-testid="map-station-name"]').exists()).toBe(false)
  })
})

describe('the coverage of the dataset choices', () => {
  it('is asked for again at the next visit of the layer where it failed', async () => {
    let asks = 0
    registerEndpoint('/api/coverage', (event) => {
      asks++
      if (asks === 1) {
        setResponseStatus(event, 500)
        return { detail: 'down' }
      }
      return COVERAGE
    })
    try {
      const wrapper = await mountMap()
      await listed(wrapper)
      const vm = wrapper.vm as any
      await chooseLayer(wrapper, 'measured')
      await vi.waitFor(() => expect(stage.props.stations).toHaveLength(3))
      expect(asks).toBe(1)
      // the choices are the one source shown
      expect(vm.resolutionItems.map((item: any) => item.value)).toEqual(['daily'])
      await chooseLayer(wrapper, 'forecast')
      await chooseLayer(wrapper, 'measured')
      await vi.waitFor(() => expect(vm.resolutionItems.map((item: any) => item.value)).toEqual(['daily', 'hourly']))
      expect(asks).toBe(2)
      // and not again once it has come
      await chooseLayer(wrapper, 'forecast')
      await chooseLayer(wrapper, 'measured')
      await nextTick()
      expect(asks).toBe(2)
    }
    finally {
      registerEndpoint('/api/coverage', () => COVERAGE)
    }
  })
})

describe('the station picked for a place, by the clock of its own dataset', () => {
  const headingOf = (wrapper: Awaited<ReturnType<typeof mountMap>>) => wrapper.find('[data-testid="map-station-name"]')
  const measuredCard = (wrapper: Awaited<ReturnType<typeof mountMap>>) => wrapper.find('[data-testid="map-card-measured"]')

  it('reads the stations of the solar radiation as running by the newest end of their list, which is 38 days old: Feldberg is picked over Freiburg, which is nearer and stopped in 2015', async () => {
    const wrapper = await mountMap('/map?layer=measured&resolution=daily&dataset=solar')
    await vi.waitFor(() => expect(stage.props.stations).toHaveLength(3))
    stage.emit('pick', { latitude: 47.8, longitude: 7.3, tolerance: 0.1, tap: 0 })
    await vi.waitFor(() => expect(headingOf(wrapper).text()).toBe('Feldberg/Schwarzwald'))
    // a running station is told since its first year, though its end is 38 days ago
    expect(measuredCard(wrapper).text()).toContain('since 2023')
    expect(measuredCard(wrapper).text()).not.toContain('2023 to')
  })

  it('offers the nearest closed station, with its years, where none of the list that reports is in reach', async () => {
    solarStations = [FREIBURG, NO_END, { ...FELDBERG, latitude: 53.0, longitude: 13.0 }]
    const wrapper = await mountMap('/map?layer=measured&resolution=daily&dataset=solar')
    await vi.waitFor(() => expect(stage.props.stations).toHaveLength(3))
    stage.emit('pick', { latitude: 47.9, longitude: 7.45, tolerance: 0.1, tap: 0 })
    // Nullend is nearer than Freiburg, and neither has an end that says it is running: the nearest closed is Nullend
    await vi.waitFor(() => expect(headingOf(wrapper).text()).toBe('Nullend'))
    // a station with no end says nothing of how long it measured, and is no "since 2006"
    expect(measuredCard(wrapper).text()).not.toContain('since')
    expect(measuredCard(wrapper).text()).not.toContain('2006')
    expect(measuredCard(wrapper).text()).toContain('Solar radiation, Daily')
  })

  it('does not take a station with no end for a running one: it never comes before a station that reports', async () => {
    const wrapper = await mountMap('/map?layer=measured&resolution=daily&dataset=solar')
    await vi.waitFor(() => expect(stage.props.stations).toHaveLength(3))
    // Nullend is 12 km from the click, Feldberg 53
    stage.emit('pick', { latitude: 47.8, longitude: 7.3, tolerance: 0.1, tap: 0 })
    await vi.waitFor(() => expect(headingOf(wrapper).text()).toBe('Feldberg/Schwarzwald'))
    // Nullend is no station that is offered, but the nearer one that is named as why Feldberg is farther
    expect(measuredCard(wrapper).text()).toMatch(/Feldberg\/Schwarzwald, \d+ km away/)
    expect(measuredCard(wrapper).text()).toContain('Closer: Nullend, 13 km, no end date known.')
    expect(new URL(measuredCard(wrapper).find('a').attributes('href')!, 'http://x').searchParams.get('stations')).toBe('01346')
  })

  it('has the measurements card of another layer take the running station of the dataset chosen, by the clock of that dataset', async () => {
    FORECAST_STATIONS.push(FREIBURG_FORECAST)
    // the forecast layer, a station of Freiburg, and the source the chips have left at the solar radiation
    const wrapper = await mountMap('/map?resolution=daily&dataset=solar&station=10401')
    await vi.waitFor(() => expect(headingOf(wrapper).text()).toBe('FREIBURG'))
    await vi.waitFor(() => expect(measuredCard(wrapper).text()).toContain('Feldberg/Schwarzwald'))
    expect(measuredCard(wrapper).text()).toMatch(/Feldberg\/Schwarzwald, \d+ km away/)
    expect(measuredCard(wrapper).text()).toContain('since 2023')
    // Freiburg is nearer, and named as why the card is not about it
    expect(measuredCard(wrapper).text()).toMatch(/Closer: Freiburg, \d+ m, until 2015\./)
    const link = new URL(measuredCard(wrapper).find('a').attributes('href')!, 'http://x')
    expect(link.searchParams.get('stations')).toBe('01346')
    expect(link.searchParams.get('dataset')).toBe('solar')
  })

  it('has the measurements card of the daily climate summary decided by that list\'s clock, not the solar one\'s', async () => {
    const wrapper = await mountMap('/map?station=10147')
    await vi.waitFor(() => expect(headingOf(wrapper).text()).toBe('HAMBURG-FUHLSBUETTEL'))
    await vi.waitFor(() => expect(measuredCard(wrapper).text()).toContain('since 1891'))
  })

  it('has the stripes card take the station of the stripes list that reports, by its own clock, over a stopped one that is nearer', async () => {
    stripesStations = [HAMBURG_OLD_STRIPES, ...STRIPES_STATIONS]
    const wrapper = await mountMap()
    await listed(wrapper)
    stage.emit('pick', { latitude: 53.6, longitude: 10.0, tolerance: 0.1, tap: 0 })
    const card = () => wrapper.find('[data-testid="map-card-stripes"]')
    await vi.waitFor(() => expect(card().text()).toContain('Hamburg-Fuhlsbüttel'))
    expect(card().text()).not.toContain('Hamburg-Alt')
    expect(card().find('a[href^="/stripes"]').attributes('href')).toBe('/stripes?kind=temperature&station=01975')
  })

  it('has the stripes card take the nearest stopped station where none reports within reach', async () => {
    stripesStations = [HAMBURG_OLD_STRIPES, { ...STRIPES_STATIONS[1]! }]
    const wrapper = await mountMap()
    await listed(wrapper)
    stage.emit('pick', { latitude: 53.6, longitude: 10.0, tolerance: 0.1, tap: 0 })
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-card-stripes"]').text()).toContain('Hamburg-Alt'))
  })

  it('does not apply the rule on the forecast layer: a forecast point has no end, and the nearest is picked', async () => {
    const wrapper = await mountMap()
    await listed(wrapper)
    stage.emit('pick', { latitude: 53.5, longitude: 10.0, tolerance: 0.1, tap: 0 })
    await vi.waitFor(() => expect(headingOf(wrapper).text()).toBe('HAMBURG-FUHLSBUETTEL'))
  })
})

describe('a tap of a finger and a click of a mouse', () => {
  const CLOSED_BESIDE = station('99003', 'Hamburg-Nord', 53.6, 10.0, { start_timestamp: '1900-01-01T00:00:00+00:00', end_timestamp: '2009-12-31T00:00:00+00:00' })
  afterEach(() => {
    const at = DAILY_STATIONS.indexOf(CLOSED_BESIDE)
    if (at !== -1)
      DAILY_STATIONS.splice(at, 1)
  })

  async function measuredMap() {
    DAILY_STATIONS.push(CLOSED_BESIDE)
    const wrapper = await mountMap('/map?layer=measured')
    await vi.waitFor(() => expect(stage.props.stations).toHaveLength(4))
    return wrapper
  }
  const name = (wrapper: Awaited<ReturnType<typeof mountMap>>) => wrapper.find('[data-testid="map-station-name"]')

  it('picks the station whose dot is under the click, a closed one too', async () => {
    const wrapper = await measuredMap()
    stage.emit('pick', { latitude: 53.6003, longitude: 10.0, tolerance: 0.5, tap: 0 })
    await vi.waitFor(() => expect(name(wrapper).text()).toBe('Hamburg-Nord'))
    expect(wrapper.find('[data-testid="map-place"]').exists()).toBe(false)
  })

  it('picks the station for the place, one that reports first, for a click that is beside a dot and not on it', async () => {
    const wrapper = await measuredMap()
    // 9 km from the closed dot, beyond its 0.5 km
    stage.emit('pick', { latitude: 53.52, longitude: 10.0, tolerance: 0.5, tap: 0 })
    await vi.waitFor(() => expect(name(wrapper).text()).toBe('Hamburg-Fuhlsbüttel'))
    expect(wrapper.find('[data-testid="map-place"]').exists()).toBe(true)
  })

  it('prefers the station that reports to the nearest dot in the ring a tap has, a closed one only where none that reports is in it', async () => {
    const wrapper = await measuredMap()
    // the closed dot is 2 km from the tap, Hamburg-Fuhlsbüttel 12; the ring of the tap is 15 km
    stage.emit('pick', { latitude: 53.582, longitude: 10.0, tolerance: 0.5, tap: 15 })
    await vi.waitFor(() => expect(name(wrapper).text()).toBe('Hamburg-Fuhlsbüttel'))
    // the tap was not on the station: its place is told, as for any pick beside a station
    expect(wrapper.find('[data-testid="map-place"]').exists()).toBe(true)
    // a ring that holds the closed dot alone has it
    await wrapper.find('[data-testid="map-back"]').trigger('click')
    stage.emit('pick', { latitude: 53.582, longitude: 10.0, tolerance: 0.5, tap: 5 })
    await vi.waitFor(() => expect(name(wrapper).text()).toBe('Hamburg-Nord'))
    expect(wrapper.find('[data-testid="map-place"]').exists()).toBe(true)
  })

  it('has no ring for a mouse: the same click is the station for the place, the one that reports', async () => {
    const wrapper = await measuredMap()
    stage.emit('pick', { latitude: 53.582, longitude: 10.0, tolerance: 0.5, tap: 0 })
    await vi.waitFor(() => expect(name(wrapper).text()).toBe('Hamburg-Fuhlsbüttel'))
  })
})

describe('a click while the list is not there', () => {
  it('does nothing while the list is on its way, and says nothing of there being no station when it comes', async () => {
    let release!: () => void
    const held = new Promise<void>((resolve) => {
      release = resolve
    })
    registerEndpoint('/api/stations', async (event) => {
      if ((getQuery(event) as Record<string, string>).network === 'observation')
        await held
      return stationsOf(event)
    })
    try {
      const wrapper = await mountMap('/map?layer=measured')
      await vi.waitFor(() => expect(stage.props.label).toBeTruthy())
      stage.emit('pick', { latitude: 53.6, longitude: 10.0, tolerance: 0.5, tap: 0 })
      await nextTick()
      expect(wrapper.find('[data-testid="map-none-near"]').exists()).toBe(false)
      expect(wrapper.find('[data-testid="map-announcement"]').text()).toBe('')
      release()
      await vi.waitFor(() => expect(stage.props.stations).toHaveLength(3))
      expect(wrapper.find('[data-testid="map-none-near"]').exists()).toBe(false)
      expect(wrapper.find('[data-testid="map-station-name"]').exists()).toBe(false)
    }
    finally {
      release()
      registerEndpoint('/api/stations', stationsOf)
    }
  })

  it('does nothing after the list failed, and nothing is left over when Retry has brought it', async () => {
    stationsFailures = 1
    const wrapper = await mountMap()
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-failure"]').exists()).toBe(true))
    stage.emit('pick', { latitude: 53.6, longitude: 10.0, tolerance: 0.5, tap: 0 })
    stage.emit('view', { latitude: 53.6, longitude: 10.0, zoom: 8 })
    await nextTick()
    expect(wrapper.find('[data-testid="map-none-near"]').exists()).toBe(false)
    await wrapper.find('[data-testid="map-failure"] button').trigger('click')
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-count"]').exists()).toBe(true))
    expect(wrapper.find('[data-testid="map-none-near"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="map-announcement"]').text()).toBe('')
  })
})

describe('an address that names a source DWD does not have', () => {
  it('asks for no list of it on the forecast layer either, where the measuring stations are asked for by the panel', async () => {
    const wrapper = await mountMap('/map?layer=forecast&resolution=daily&dataset=nonsense&station=10147')
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-card-measured"] a').exists()).toBe(true))
    const asks = asked.stations.filter(query => !query.parameters?.startsWith('annual/') && query.network === 'observation').map(query => query.parameters)
    expect(asks).toEqual(['daily/climate_summary'])
    expect((wrapper.vm as any).source).toEqual({ resolution: 'daily', dataset: 'climate_summary' })
    // no failed list, and no Retry that cannot help
    expect(wrapper.find('[data-testid="map-card-measured"] [role="alert"]').exists()).toBe(false)
  })

  it('keeps the station the address names when it makes the source right', async () => {
    const wrapper = await mountMap('/map?layer=measured&resolution=daily&dataset=nonsense&station=01975')
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-station-name"]').text()).toBe('Hamburg-Fuhlsbüttel'))
    expect(wrapper.find('[data-testid="map-unknown"]').exists()).toBe(false)
    await vi.waitFor(() => expect(useRouter().currentRoute.value.query).toEqual({ layer: 'measured', station: '01975' }))
  })
})

describe('a station that the address names in another view', () => {
  it('is a pick of that view, announced: the same number of the forecast layer is another station than the measuring one', async () => {
    addCollision()
    const wrapper = await mountMap('/map?layer=measured&station=01001')
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-station-name"]').text()).toBe('Doberlug-Kirchhain'))
    expect(wrapper.find('[data-testid="map-announcement"]').text()).toBe('Doberlug-Kirchhain chosen')
    const before = stage.props.recentre
    // the search of the header opens the map on the forecast point of the same number
    await useRouter().push({ path: '/map', query: { station: '01001' } })
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-station-name"]').text()).toBe('JAN MAYEN'))
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-announcement"]').text()).toBe('JAN MAYEN chosen'))
    // and the map is moved to it
    expect(stage.props.recentre).toBeGreaterThan(before)
    expect(stage.props.selected.name).toBe('JAN MAYEN')
  })
})

describe('the note of a station the layer has not got', () => {
  it('is gone when the layer is changed: it was about the station of another view', async () => {
    const wrapper = await mountMap('/map?station=abc')
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-unknown"]').exists()).toBe(true))
    await chooseLayer(wrapper, 'measured')
    await vi.waitFor(() => expect(stage.props.stations).toHaveLength(3))
    expect(wrapper.find('[data-testid="map-unknown"]').exists()).toBe(false)
  })
})

/** An answer of `/api/stations` for the measuring stations that a test holds back until it releases it */
function holdMeasuring(only?: (parameters: string) => boolean) {
  let release!: () => void
  const held = new Promise<void>((resolve) => {
    release = resolve
  })
  registerEndpoint('/api/stations', async (event) => {
    const query = getQuery(event) as Record<string, string>
    if (query.network === 'observation' && (!only || only(query.parameters!)))
      await held
    return stationsOf(event)
  })
  return { release, restore: () => registerEndpoint('/api/stations', stationsOf) }
}

describe('the yellow disc of the station picked', () => {
  const CLOSED = station('99001', 'Hamburg-Altstadt', 53.55, 10.0, { start_timestamp: '1900-01-01T00:00:00+00:00', end_timestamp: '2009-12-31T00:00:00+00:00' })
  afterEach(() => {
    const at = DAILY_STATIONS.indexOf(CLOSED)
    if (at !== -1)
      DAILY_STATIONS.splice(at, 1)
  })

  it('is part of the station: a click on it, which is bigger than a dot, keeps the pick, a closed station too, and does not take it to the station that reports', async () => {
    DAILY_STATIONS.push(CLOSED)
    const wrapper = await mountMap('/map?layer=measured')
    await vi.waitFor(() => expect(stage.props.stations).toHaveLength(4))
    // a click on the dot of the closed station picks it
    stage.emit('pick', { latitude: 53.5505, longitude: 10.0, tolerance: 0.5, tap: 0, disc: 3 })
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-station-name"]').text()).toBe('Hamburg-Altstadt'))
    // a click 2 km from it, beyond its dot (0.5) and on its disc (3): still that station
    stage.emit('pick', { latitude: 53.568, longitude: 10.0, tolerance: 0.5, tap: 0, disc: 3 })
    await nextTick()
    expect(wrapper.find('[data-testid="map-station-name"]').text()).toBe('Hamburg-Altstadt')
    expect(wrapper.find('[data-testid="map-place"]').exists()).toBe(false)
    // beyond the disc it is a click on the map: the station that reports
    stage.emit('pick', { latitude: 53.58, longitude: 10.0, tolerance: 0.5, tap: 0, disc: 3 })
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-station-name"]').text()).toBe('Hamburg-Fuhlsbüttel'))
  })

  it('is no part of a station that is not picked: with none picked the disc reaches nothing', async () => {
    DAILY_STATIONS.push(CLOSED)
    const wrapper = await mountMap('/map?layer=measured')
    await vi.waitFor(() => expect(stage.props.stations).toHaveLength(4))
    stage.emit('pick', { latitude: 53.568, longitude: 10.0, tolerance: 0.5, tap: 0, disc: 3 })
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-station-name"]').text()).toBe('Hamburg-Fuhlsbüttel'))
  })
})

describe('what the page does with the pick of the centre of the map', () => {
  const CLOSED = station('99004', 'Hamburg-Mitte', 53.55, 10.0, { start_timestamp: '1900-01-01T00:00:00+00:00', end_timestamp: '2009-12-31T00:00:00+00:00' })
  afterEach(() => {
    const at = DAILY_STATIONS.indexOf(CLOSED)
    if (at !== -1)
      DAILY_STATIONS.splice(at, 1)
  })

  it('is the station within half a kilometre of it, whatever its status: a closed one 0.3 km away is picked, not the one that reports 9 km away', async () => {
    DAILY_STATIONS.push(CLOSED)
    const wrapper = await mountMap('/map?layer=measured')
    await vi.waitFor(() => expect(stage.props.stations).toHaveLength(4))
    stage.emit('view', { latitude: 53.5527, longitude: 10.0, zoom: 12 })
    await wrapper.find('[data-testid="map-pick-centre"]').trigger('click')
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-station-name"]').text()).toBe('Hamburg-Mitte'))
  })

  it('is the station within half a kilometre, with no place told, and the station for the place beyond it', async () => {
    const wrapper = await mountMap('/map?layer=measured')
    await vi.waitFor(() => expect(stage.props.stations).toHaveLength(3))
    // 0.3 km from Hamburg-Fuhlsbüttel
    stage.emit('view', { latitude: 53.6359, longitude: 9.9881, zoom: 12 })
    await wrapper.find('[data-testid="map-pick-centre"]').trigger('click')
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-station-name"]').text()).toBe('Hamburg-Fuhlsbüttel'))
    expect(wrapper.find('[data-testid="map-place"]').exists()).toBe(false)
    await wrapper.find('[data-testid="map-back"]').trigger('click')
    // 9 km from it
    stage.emit('view', { latitude: 53.7132, longitude: 9.9881, zoom: 12 })
    await wrapper.find('[data-testid="map-pick-centre"]').trigger('click')
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-station-name"]').text()).toBe('Hamburg-Fuhlsbüttel'))
    expect(wrapper.find('[data-testid="map-place"]').exists()).toBe(true)
  })
})

describe('an address that is followed while a list is on its way', () => {
  const name = (wrapper: Awaited<ReturnType<typeof mountMap>>) => wrapper.find('[data-testid="map-station-name"]')

  it('is not picked again by the place of the pick before it: the station of the address is the one shown when the list comes', async () => {
    const held = holdMeasuring()
    try {
      const wrapper = await mountMap('/map?station=10147')
      await vi.waitFor(() => expect(name(wrapper).text()).toBe('HAMBURG-FUHLSBUETTEL'))
      // the layer is changed, and the measuring list is on its way: a pick again waits for it
      await chooseLayer(wrapper, 'measured')
      // the address is another's, from outside, with the station of Arkona
      await useRouter().push({ path: '/map', query: { layer: 'measured', station: '00183' } })
      held.release()
      await vi.waitFor(() => expect(name(wrapper).text()).toBe('Arkona'))
      expect(wrapper.find('[data-testid="map-none-near"]').exists()).toBe(false)
    }
    finally {
      held.release()
      held.restore()
    }
  })

  it('takes the place the address has, and none where it has none: the place of the pick before is not the new pick\'s', async () => {
    const wrapper = await mountMap()
    await listed(wrapper)
    stage.emit('pick', { latitude: 53.45, longitude: 10.2, tolerance: 0.5, tap: 0, disc: 0 })
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-place"]').exists()).toBe(true))
    await useRouter().push({ path: '/map', query: { station: '10384' } })
    await vi.waitFor(() => expect(name(wrapper).text()).toBe('BERLIN-TEMPELHOF'))
    // no place is told, and none is written to the address, from the old pick
    expect(wrapper.find('[data-testid="map-place"]').exists()).toBe(false)
    await vi.waitFor(() => expect(useRouter().currentRoute.value.query).toEqual({ station: '10384' }))
  })

  it('says nothing of the station before while the list of the new one is on its way', async () => {
    const wrapper = await mountMap('/map?station=10147')
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-announcement"]').text()).toBe('HAMBURG-FUHLSBUETTEL chosen'))
    const held = holdMeasuring(parameters => parameters === 'daily/solar')
    try {
      await useRouter().push({ path: '/map', query: { layer: 'measured', resolution: 'daily', dataset: 'solar', station: '01346' } })
      await nextTick()
      // the status is not "HAMBURG-FUHLSBUETTEL chosen" under another page's heading
      expect(wrapper.find('[data-testid="map-announcement"]').text()).toBe('')
      held.release()
      await vi.waitFor(() => expect(wrapper.find('[data-testid="map-announcement"]').text()).toBe('Feldberg/Schwarzwald chosen'))
    }
    finally {
      held.release()
      held.restore()
    }
  })

  it('has no note of a point without a station once the layer is changed, while the other layer\'s list is on its way', async () => {
    const wrapper = await mountMap()
    await listed(wrapper)
    // Arkona is 240 km from the nearest forecast point
    stage.emit('pick', { latitude: 54.7, longitude: 13.4, tolerance: 0.5, tap: 0, disc: 0 })
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-none-near"]').exists()).toBe(true))
    const held = holdMeasuring()
    try {
      await chooseLayer(wrapper, 'measured')
      await nextTick()
      expect(wrapper.find('[data-testid="map-none-near"]').exists()).toBe(false)
      held.release()
      // and the station of the place in the new list is picked
      await vi.waitFor(() => expect(name(wrapper).text()).toBe('Arkona'))
    }
    finally {
      held.release()
      held.restore()
    }
  })
})

describe('the list of the measuring stations asked for with care', () => {
  it('is not asked for when the reader has left the layer while the coverage was on its way, and nothing needs it', async () => {
    let release!: () => void
    const held = new Promise<void>((resolve) => {
      release = resolve
    })
    registerEndpoint('/api/coverage', async () => {
      await held
      return COVERAGE
    })
    try {
      const wrapper = await mountMap('/map?layer=measured')
      await vi.waitFor(() => expect(stage.props.label).toBeTruthy())
      await chooseLayer(wrapper, 'forecast')
      release()
      await new Promise(resolve => setTimeout(resolve, 80))
      expect(asked.stations.filter(query => query.network === 'observation')).toEqual([])
    }
    finally {
      release()
      registerEndpoint('/api/coverage', () => COVERAGE)
    }
  })

  it('asks for the source as written where the coverage failed, and Retry asks the coverage again and makes the source right', async () => {
    let coverageAsks = 0
    registerEndpoint('/api/coverage', (event) => {
      coverageAsks++
      if (coverageAsks === 1) {
        setResponseStatus(event, 500)
        return { detail: 'down' }
      }
      return COVERAGE
    })
    registerEndpoint('/api/stations', (event) => {
      const query = getQuery(event) as Record<string, string>
      if (query.parameters === 'daily/nonsense') {
        asked.stations.push(query)
        setResponseStatus(event, 400)
        return { detail: 'no such dataset' }
      }
      return stationsOf(event)
    })
    try {
      const wrapper = await mountMap('/map?layer=measured&dataset=nonsense')
      await vi.waitFor(() => expect(wrapper.find('[data-testid="map-failure"]').exists()).toBe(true))
      // with no coverage the source is asked for as it is written, which fails
      expect(asked.stations.filter(query => query.network === 'observation').map(query => query.parameters)).toEqual(['daily/nonsense'])
      await wrapper.find('[data-testid="map-failure"] button').trigger('click')
      await vi.waitFor(() => expect(wrapper.find('[data-testid="map-count"]').exists()).toBe(true))
      expect(coverageAsks).toBe(2)
      expect((wrapper.vm as any).source).toEqual({ resolution: 'daily', dataset: 'climate_summary' })
      expect(asked.stations.at(-1)).toMatchObject({ parameters: 'daily/climate_summary' })
    }
    finally {
      registerEndpoint('/api/coverage', () => COVERAGE)
      registerEndpoint('/api/stations', stationsOf)
    }
  })

  it('makes a source right that is set while a station is picked on the forecast layer, whose list the panel asks for', async () => {
    const wrapper = await mountMap('/map?station=10147')
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-station-name"]').exists()).toBe(true))
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-card-measured"] a').exists()).toBe(true))
    ;(wrapper.vm as any).source = { resolution: 'daily', dataset: 'nonsense' }
    await vi.waitFor(() => expect((wrapper.vm as any).source).toEqual({ resolution: 'daily', dataset: 'climate_summary' }))
    await new Promise(resolve => setTimeout(resolve, 60))
    expect(asked.stations.some(query => query.parameters === 'daily/nonsense')).toBe(false)
  })
})

describe('an end that is no date', () => {
  it('shows nothing of how long a station measured, and no "NaN"', async () => {
    solarStations = [{ ...NO_END, end_timestamp: 'soon' }, FELDBERG]
    const wrapper = await mountMap('/map?layer=measured&resolution=daily&dataset=solar')
    await vi.waitFor(() => expect(stage.props.stations).toHaveLength(2))
    stage.emit('pick', { latitude: 47.9, longitude: 7.45, tolerance: 0.1, tap: 0, disc: 0 })
    // Feldberg reports and is picked; the station of no usable end is picked directly on its dot
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-station-name"]').text()).toBe('Feldberg/Schwarzwald'))
    stage.emit('pick', { latitude: 47.9, longitude: 7.4, tolerance: 0.5, tap: 0, disc: 0 })
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-station-name"]').text()).toBe('Nullend'))
    const card = wrapper.find('[data-testid="map-card-measured"]').text()
    expect(card).not.toContain('NaN')
    expect(card).not.toContain('since')
    expect(card).not.toContain('2006 to')
  })
})

// "Use my location" (GH-3651): the reader's position, rounded, marked on the map and picked as a place, kept out of the address
describe('the reader\'s own position', () => {
  function mockBrowser(options: { code?: number, permission?: PermissionState, fix?: { latitude: number, longitude: number } } = {}) {
    const getCurrentPosition = vi.fn((success: (position: unknown) => void, failure: (error: unknown) => void) => {
      if (options.code)
        failure({ code: options.code })
      else
        success({ coords: options.fix ?? { latitude: 53.5412, longitude: 10.1987 } })
    })
    Object.defineProperty(navigator, 'geolocation', { configurable: true, value: { getCurrentPosition } })
    Object.defineProperty(navigator, 'permissions', { configurable: true, value: { query: vi.fn(async () => ({ state: options.permission ?? 'prompt' })) } })
    return getCurrentPosition
  }
  beforeEach(() => {
    clearNuxtState(['wd-location-position', 'wd-location-failure', 'wd-location-busy', 'wd-location-remember', 'wd-location-loaded'])
  })
  afterEach(() => {
    delete (navigator as any).geolocation
    delete (navigator as any).permissions
    vi.unstubAllGlobals()
    clearNuxtState(['wd-location-position', 'wd-location-failure', 'wd-location-busy', 'wd-location-remember', 'wd-location-loaded'])
  })
  const locate = (wrapper: Awaited<ReturnType<typeof mountMap>>) => wrapper.find('[data-testid="use-my-location-button"]')
  /** Opens the Stored control and presses "Forget my position" in its popover, which is teleported to the body */
  async function forgetFromStored(wrapper: Awaited<ReturnType<typeof mountMap>>) {
    await vi.waitFor(() => expect(wrapper.find('[data-testid="use-my-location-stored"]').exists()).toBe(true))
    await wrapper.find('[data-testid="use-my-location-stored"]').trigger('click')
    await vi.waitFor(() => expect(document.body.querySelector('[data-testid="use-my-location-forget"]')).not.toBeNull())
    document.body.querySelector<HTMLElement>('[data-testid="use-my-location-forget"]')!.click()
  }

  it('is asked for by the button alone: a map that is only opened asks the browser nothing', async () => {
    const getCurrentPosition = mockBrowser()
    const wrapper = await mountMap()
    await listed(wrapper)
    expect(getCurrentPosition).not.toHaveBeenCalled()
    expect(stage.props.position ?? null).toBeNull()
  })

  it('is marked on the map, which is told to centre on it, and the nearest station is picked as a place of its own', async () => {
    mockBrowser()
    const wrapper = await mountMap()
    await listed(wrapper)
    await locate(wrapper).trigger('click')
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-station-name"]').text()).toBe('HAMBURG-FUHLSBUETTEL'))

    // rounded to two decimals before the map or the panel sees it
    expect(stage.props.position).toEqual({ latitude: 53.54, longitude: 10.2 })
    expect(stage.props.locate).toBe(1)
    expect(stage.props.place).toEqual({ latitude: 53.54, longitude: 10.2 })
    expect(wrapper.find('[data-testid="map-place"]').text()).toMatch(/^Your position, \d+ km from this station$/)
    expect(wrapper.find('[data-testid="map-announcement"]').text()).toBe('HAMBURG-FUHLSBUETTEL chosen')
    // found in the list the map holds: no request carries the position
    expect(asked.stations.filter(query => query.latitude || query.longitude || query.rank)).toEqual([])
  })

  it('centres again for each press', async () => {
    mockBrowser()
    const wrapper = await mountMap()
    await listed(wrapper)
    await locate(wrapper).trigger('click')
    await vi.waitFor(() => expect(stage.props.locate).toBe(1))
    await wrapper.find('[data-testid="map-back"]').trigger('click')
    await locate(wrapper).trigger('click')
    await vi.waitFor(() => expect(stage.props.locate).toBe(2))
  })

  it('is kept out of the address, which is copied and shared: the station is in it, the position is not', async () => {
    mockBrowser()
    const wrapper = await mountMap()
    await listed(wrapper)
    const router = useRouter()
    await locate(wrapper).trigger('click')
    await vi.waitFor(() => expect(router.currentRoute.value.query.station).toBe('10147'))
    expect(router.currentRoute.value.query).toEqual({ station: '10147' })
  })

  it('is picked again in the other layer, by the position', async () => {
    mockBrowser()
    const wrapper = await mountMap()
    await listed(wrapper)
    await locate(wrapper).trigger('click')
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-station-name"]').exists()).toBe(true))
    await chooseLayer(wrapper, 'measured')
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-station-name"]').text()).toBe('Hamburg-Fuhlsbüttel'))
    expect(stage.props.position).toEqual({ latitude: 53.54, longitude: 10.2 })
    expect(wrapper.find('[data-testid="map-place"]').text()).toMatch(/^Your position, /)
  })

  it('leaves the list and the search as they were where the reader refuses, and says why in the alert region', async () => {
    const getCurrentPosition = mockBrowser({ code: 1 })
    const wrapper = await mountMap()
    await listed(wrapper)
    await locate(wrapper).trigger('click')
    await vi.waitFor(() => expect(wrapper.find('[data-testid="use-my-location-problem"]').text()).toContain('Your browser blocks location for this site'))
    expect(getCurrentPosition).toHaveBeenCalledTimes(1)
    expect(wrapper.find('[data-testid="map-station-name"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="map-list"]').exists()).toBe(true)
    expect(wrapper.find('#map-search').exists()).toBe(true)
    expect(stage.props.position ?? null).toBeNull()
  })

  it('is not asked for again where the browser reports the permission as denied', async () => {
    const getCurrentPosition = mockBrowser({ permission: 'denied' })
    const wrapper = await mountMap()
    await listed(wrapper)
    await locate(wrapper).trigger('click')
    await vi.waitFor(() => expect(wrapper.find('[data-testid="use-my-location-problem"]').text()).toContain('set Location to Allow'))
    expect(getCurrentPosition).not.toHaveBeenCalled()
  })

  it('takes the mark off the map when the reader forgets the position', async () => {
    mockBrowser()
    const wrapper = await mountMap()
    await listed(wrapper)
    await locate(wrapper).trigger('click')
    await vi.waitFor(() => expect(stage.props.position).toEqual({ latitude: 53.54, longitude: 10.2 }))
    // the button is in the list of the panel, which the station card replaces: the card shows the option to keep the
    // position (GH-4011), and the list is not in the page, so there is one copy of it to tab to
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-station-name"]').exists()).toBe(true))
    await vi.waitFor(() => expect(wrapper.find('button[role="checkbox"]').exists()).toBe(true))
    expect(wrapper.findAll('button[role="checkbox"]')).toHaveLength(1)
    expect(wrapper.findAll('[data-testid="use-my-location-note"]')).toHaveLength(1)
    expect(wrapper.find('[data-testid="use-my-location-button"]').exists()).toBe(false)
    expect(wrapper.find('.map-detail [data-testid="use-my-location"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="use-my-location-stored"]').exists()).toBe(false)
    expect(localStorage.getItem('wd-location')).toBeNull()

    // ticked, the box gives way to the Stored control, on the card, and the position is kept
    await wrapper.find('button[role="checkbox"]').trigger('click')
    await vi.waitFor(() => expect(wrapper.find('.map-detail [data-testid="use-my-location-stored"]').exists()).toBe(true))
    expect(wrapper.findAll('[data-testid="use-my-location-stored"]')).toHaveLength(1)
    expect(wrapper.find('button[role="checkbox"]').exists()).toBe(false)
    expect(JSON.parse(localStorage.getItem('wd-location')!)).toEqual({ latitude: 53.54, longitude: 10.2 })

    // forgotten from the card: the mark and the position go, the station stays, and the focus goes to the card's heading
    await forgetFromStored(wrapper)
    await vi.waitFor(() => expect(stage.props.position).toBeNull())
    expect(localStorage.getItem('wd-location')).toBeNull()
    expect(wrapper.find('[data-testid="use-my-location-stored"]').exists()).toBe(false)
    expect(wrapper.find('button[role="checkbox"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="map-station-name"]').text()).toBe('HAMBURG-FUHLSBUETTEL')
    await vi.waitFor(() => expect(document.activeElement).toBe(wrapper.find('[data-testid="map-station-name"]').element))
  })

  it('shows the option on the list again, with the button, after the way back from the card', async () => {
    mockBrowser()
    const wrapper = await mountMap()
    await listed(wrapper)
    await locate(wrapper).trigger('click')
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-back"]').exists()).toBe(true))
    await wrapper.find('[data-testid="map-back"]').trigger('click')
    // the list has the full copy, and the card's is gone with it: one box, one note, and the button
    await vi.waitFor(() => expect(wrapper.find('[data-testid="use-my-location-button"]').exists()).toBe(true))
    expect(wrapper.findAll('button[role="checkbox"]')).toHaveLength(1)
    expect(wrapper.findAll('[data-testid="use-my-location-note"]')).toHaveLength(1)
  })

  it('shows no option on a card whose station the reader picked themselves', async () => {
    mockBrowser()
    const wrapper = await mountMap('/map?station=10147')
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-station-name"]').exists()).toBe(true))
    expect(wrapper.find('.map-detail [data-testid="use-my-location"]').exists()).toBe(false)
  })

  it('is forgotten by the panel as well: a position with no station within reach leaves no place and no notice behind', async () => {
    // the Gulf of Guinea: no station within 100 km
    mockBrowser({ fix: { latitude: 0.0004, longitude: 0.0004 } })
    const wrapper = await mountMap()
    await listed(wrapper)
    await locate(wrapper).trigger('click')
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-none-near"]').exists()).toBe(true))
    expect(stage.props.position).toEqual({ latitude: 0, longitude: 0 })

    await vi.waitFor(() => expect(wrapper.find('button[role="checkbox"]').exists()).toBe(true))
    await wrapper.find('button[role="checkbox"]').trigger('click')
    await forgetFromStored(wrapper)
    await vi.waitFor(() => expect(stage.props.position).toBeNull())
    expect(wrapper.find('[data-testid="map-none-near"]').exists()).toBe(false)
  })

  it('is forgotten by a station picked from it: the station stays, the place and the position do not', async () => {
    mockBrowser()
    const wrapper = await mountMap()
    await listed(wrapper)
    await locate(wrapper).trigger('click')
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-place"]').exists()).toBe(true))

    // forgotten from elsewhere than the panel's list, which a station picked has replaced
    useMyLocation().forget()
    await vi.waitFor(() => expect(stage.props.position).toBeNull())
    expect(wrapper.find('[data-testid="map-station-name"]').text()).toBe('HAMBURG-FUHLSBUETTEL')
    expect(wrapper.find('[data-testid="map-place"]').exists()).toBe(false)
    expect(stage.props.place).toBeNull()
    expect(wrapper.text()).not.toContain('Your position')
  })
})

describe('the layers button (GH-4209)', () => {
  const button = (wrapper: Awaited<ReturnType<typeof mountMap>>) => wrapper.find('[data-testid="map-layers-button"]')
  const panelOf = (wrapper: Awaited<ReturnType<typeof mountMap>>) => wrapper.find('[data-testid="map-layers-panel"]')

  it('is the only control over the map but the status: one button, named, which says whether its panel is open and which panel it is', async () => {
    const wrapper = await mountMap()
    const trigger = button(wrapper)
    expect(trigger.element.tagName).toBe('BUTTON')
    expect(trigger.attributes('aria-label')).toBe('Layers and grouping')
    expect(trigger.attributes('aria-expanded')).toBe('true')
    expect(trigger.attributes('aria-controls')).toBe(panelOf(wrapper).attributes('id'))
    expect(panelOf(wrapper).attributes('aria-label')).toBe('Layers and grouping')
    // the layers (and, on the measurements, the source) and the switch are in the panel, none of them on the map
    expect(panelOf(wrapper).find('[data-testid="map-layers"]').exists()).toBe(true)
    expect(wrapper.find('.map-chips [role="radio"], .map-chips [role="switch"]').exists()).toBe(false)
    await listed(wrapper)
    expect(panelOf(wrapper).find('[data-testid="map-grouping"]').exists()).toBe(true)
  })

  it('opens on a press and closes on the next, saying so, to the map as well (which swallows the click that closes it)', async () => {
    const wrapper = await mountMap()
    await vi.waitFor(() => expect(stage.props.panelOpen).toBe(true))
    await button(wrapper).trigger('click')
    await vi.waitFor(() => expect(panelOf(wrapper).exists()).toBe(false))
    expect(button(wrapper).attributes('aria-expanded')).toBe('false')
    expect(stage.props.panelOpen).toBe(false)
    await button(wrapper).trigger('click')
    await vi.waitFor(() => expect(panelOf(wrapper).exists()).toBe(true))
    expect(button(wrapper).attributes('aria-expanded')).toBe('true')
    expect(stage.props.panelOpen).toBe(true)
  })

  it('closes on Escape, and the focus is the button\'s again', async () => {
    const wrapper = await mountMap()
    const trigger = button(wrapper).element as HTMLButtonElement
    // the focus is in the panel, as a keyboard that opened it has it
    ;(panelOf(wrapper).find('[role="radio"]').element as HTMLElement).focus()
    document.activeElement!.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    await vi.waitFor(() => expect(panelOf(wrapper).exists()).toBe(false))
    await vi.waitFor(() => expect(document.activeElement).toBe(trigger))
  })

  it('closes on a press outside it', async () => {
    const wrapper = await mountMap()
    // the popover listens for a press outside from the turn after it opened
    await listed(wrapper)
    document.body.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, pointerType: 'mouse' }))
    await vi.waitFor(() => expect(panelOf(wrapper).exists()).toBe(false))
    expect(button(wrapper).attributes('aria-expanded')).toBe('false')
  })
})

describe('the groups of stations at the outer zooms (GH-4079)', () => {
  const GROUPED = { radius: 60, separateFrom: 9 }
  const grouping = (wrapper: Awaited<ReturnType<typeof mountMap>>) => wrapper.find('[data-testid="map-grouping"]')

  it('opens grouped, and the reader turns the grouping off and on with a switch (GH-4209)', async () => {
    const wrapper = await mountMap()
    await listed(wrapper)
    expect(stage.props.grouping).toEqual(GROUPED)
    expect(wrapper.find('[data-testid="map-grouping-note"]').exists()).toBe(false)
    await grouping(wrapper).trigger('click')
    await vi.waitFor(() => expect(stage.props.grouping).toBeNull())
    // no groups, so nothing to say of them
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-legend"]').exists()).toBe(false))
    await grouping(wrapper).trigger('click')
    await vi.waitFor(() => expect(stage.props.grouping).toEqual(GROUPED))
  })

  it('is a switch with a name of its own, which a keyboard and a screen reader reach like the other switches', async () => {
    const wrapper = await mountMap()
    await listed(wrapper)
    const control = grouping(wrapper)
    expect(control.attributes('role')).toBe('switch')
    expect(control.attributes('aria-checked')).toBe('true')
    expect(control.attributes('disabled')).toBeUndefined()
    expect(wrapper.find(`label[for="${control.attributes('id')}"]`).text()).toBe('Group stations')
    await control.trigger('click')
    await vi.waitFor(() => expect(grouping(wrapper).attributes('aria-checked')).toBe('false'))
  })

  it('cannot be turned off on a layer of more than 10,000 stations, whose switch is on and disabled, and says why', async () => {
    const extra = Array.from({ length: 10_000 }, (_, index) => station(`X${index}`, `Point ${index}`, 40 + (index % 100) / 10, index % 90))
    FORECAST_STATIONS.push(...extra)
    try {
      const wrapper = await mountMap()
      await listed(wrapper)
      expect(wrapper.find('[data-testid="map-grouping-note"]').text()).toBe('Layers of more than 10,000 stations are always grouped.')
      expect(grouping(wrapper).attributes('aria-describedby')).toBe('map-grouping-note')
      expect(grouping(wrapper).attributes('aria-checked')).toBe('true')
      expect(grouping(wrapper).attributes('disabled')).toBeDefined()
      ;(wrapper.vm as any).grouped = false
      // the choice is kept, and the groups stay
      await nextTick()
      expect(stage.props.grouping).toEqual(GROUPED)
      expect(grouping(wrapper).attributes('aria-checked')).toBe('true')
      // a layer of fewer stations follows the switch again, which the choice made on the other layer has set
      await chooseLayer(wrapper, 'measured')
      await vi.waitFor(() => expect(wrapper.find('[data-testid="map-grouping-note"]').exists()).toBe(false))
      await vi.waitFor(() => expect(stage.props.grouping).toBeNull())
      await vi.waitFor(() => expect(grouping(wrapper).exists()).toBe(true))
      expect(grouping(wrapper).attributes('aria-checked')).toBe('false')
      expect(grouping(wrapper).attributes('disabled')).toBeUndefined()
    }
    finally {
      FORECAST_STATIONS.splice(FORECAST_STATIONS.length - extra.length, extra.length)
    }
  })

  it('says what a click on a group did: the map has zoomed in on it', async () => {
    const wrapper = await mountMap()
    await listed(wrapper)
    stage.emit('group', 1234, null)
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-announcement"]').text()).toBe('Zoomed in on a group. Stations in it: 1,234'))
  })

  it('says how many of the stations of a group report where the layer has a status for its stations', async () => {
    const wrapper = await mountMap('/map?layer=measured')
    await vi.waitFor(() => expect(stage.props.stations).toHaveLength(3))
    stage.emit('group', 1234, 800)
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-announcement"]').text()).toBe('Zoomed in on a group. Stations in it: 1,234, of them reporting: 800'))
    // and a group none of whose stations report says so
    stage.emit('group', 12, 0)
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-announcement"]').text()).toBe('Zoomed in on a group. Stations in it: 12, of them reporting: 0'))
  })

  it('says it again for a second click on the same group: the status is emptied first, or a screen reader would not read the same text twice', async () => {
    const wrapper = await mountMap()
    await listed(wrapper)
    const spoken = () => wrapper.find('[data-testid="map-announcement"]').text()
    stage.emit('group', 40, null)
    await vi.waitFor(() => expect(spoken()).toBe('Zoomed in on a group. Stations in it: 40'))
    stage.emit('group', 40, null)
    // emptied at once, and said again after a moment, not in the same frame
    await nextTick()
    expect(spoken()).toBe('')
    await vi.waitFor(() => expect(spoken()).toBe('Zoomed in on a group. Stations in it: 40'))
  })
})

describe('a pick that is carried across layers by its WMO number (GH-4077)', () => {
  const headingOf = (wrapper: Awaited<ReturnType<typeof mountMap>>) => wrapper.find('[data-testid="map-station-name"]')
  const NEAR_THE_POINT = station('00999', 'Hamburg-Nahe', 53.6295, 10.0003, { start_timestamp: '1990-01-01T00:00:00+00:00', end_timestamp: daysAgo(1) })
  const undo: Array<() => void> = []

  /** Gives a station of a list a WMO number for the test: put back as it was afterwards */
  function numbered(list: Array<Record<string, any>>, stationId: string, wmo: string | null) {
    const entry = list.find(candidate => candidate.station_id === stationId)!
    entry.wmo_id = wmo
    undo.push(() => {
      delete entry.wmo_id
    })
  }
  /** A station that the position would pick, since it is nearer to the forecast point of Hamburg than Fuhlsbüttel is */
  function addNearer(extra: Record<string, unknown> = {}) {
    const nearer = { ...NEAR_THE_POINT, ...extra }
    DAILY_STATIONS.push(nearer)
    undo.push(() => {
      DAILY_STATIONS.splice(DAILY_STATIONS.indexOf(nearer), 1)
    })
    return nearer
  }
  afterEach(() => {
    while (undo.length)
      undo.pop()!()
  })

  it('picks the station of the other layer that has the same WMO number, though another is nearer to the place, and says it is the same station', async () => {
    numbered(FORECAST_STATIONS, '10147', '10147')
    numbered(DAILY_STATIONS, '01975', '10147')
    addNearer()
    const wrapper = await mountMap('/map?station=10147')
    await vi.waitFor(() => expect(headingOf(wrapper).text()).toBe('HAMBURG-FUHLSBUETTEL'))
    expect(wrapper.find('[data-testid="map-same-station"]').exists()).toBe(false)
    await chooseLayer(wrapper, 'measured')
    await vi.waitFor(() => expect(headingOf(wrapper).text()).toBe('Hamburg-Fuhlsbüttel'))
    expect(wrapper.find('[data-testid="map-same-station"]').text()).toBe('The same station, by its WMO number 10147.')
    expect(wrapper.find('[data-testid="map-announcement"]').text()).toBe('Hamburg-Fuhlsbüttel chosen. The same station, by its WMO number 10147.')
    // the place was the position of the forecast point: it is the position of the station now, so no place apart is told
    expect(wrapper.find('[data-testid="map-place"]').exists()).toBe(false)
    await vi.waitFor(() => expect(useRouter().currentRoute.value.query).toEqual({ layer: 'measured', station: '01975' }))
    // and back by the number as well
    await chooseLayer(wrapper, 'forecast')
    await vi.waitFor(() => expect(headingOf(wrapper).text()).toBe('HAMBURG-FUHLSBUETTEL'))
    expect(wrapper.find('[data-testid="map-same-station"]').exists()).toBe(true)
    await vi.waitFor(() => expect(useRouter().currentRoute.value.query).toEqual({ station: '10147' }))
  })

  it('keeps the place of a click, which is not the position of a station, and carries the station by its number all the same', async () => {
    numbered(FORECAST_STATIONS, '10147', '10147')
    numbered(DAILY_STATIONS, '01975', '10147')
    addNearer()
    const wrapper = await mountMap()
    await listed(wrapper)
    // a click 3 km from the forecast point of Hamburg picks it (the one in reach), with the click as its place
    stage.emit('pick', { latitude: 53.66, longitude: 10.0, tolerance: 0.5, tap: 0, disc: 0.5 })
    await vi.waitFor(() => expect(headingOf(wrapper).text()).toBe('HAMBURG-FUHLSBUETTEL'))
    await chooseLayer(wrapper, 'measured')
    await vi.waitFor(() => expect(headingOf(wrapper).text()).toBe('Hamburg-Fuhlsbüttel'))
    expect(wrapper.find('[data-testid="map-same-station"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="map-place"]').text()).toMatch(/^A point on the map, .* from this station$/)
  })

  it('picks again by the position where the station has no WMO number: the nearer station, and no word of the same', async () => {
    numbered(DAILY_STATIONS, '01975', '10147')
    addNearer()
    const wrapper = await mountMap('/map?station=10147')
    await vi.waitFor(() => expect(headingOf(wrapper).text()).toBe('HAMBURG-FUHLSBUETTEL'))
    await chooseLayer(wrapper, 'measured')
    await vi.waitFor(() => expect(headingOf(wrapper).text()).toBe('Hamburg-Nahe'))
    expect(wrapper.find('[data-testid="map-same-station"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="map-announcement"]').text()).toBe('Hamburg-Nahe chosen')
  })

  it('picks again by the position where the other layer has no station with the number', async () => {
    numbered(FORECAST_STATIONS, '10147', '10147')
    addNearer()
    const wrapper = await mountMap('/map?station=10147')
    await vi.waitFor(() => expect(headingOf(wrapper).text()).toBe('HAMBURG-FUHLSBUETTEL'))
    await chooseLayer(wrapper, 'measured')
    await vi.waitFor(() => expect(headingOf(wrapper).text()).toBe('Hamburg-Nahe'))
    expect(wrapper.find('[data-testid="map-same-station"]').exists()).toBe(false)
  })

  it('picks again by the position where the number is on several stations of the other layer: none of them is taken for the same', async () => {
    numbered(FORECAST_STATIONS, '10147', '10147')
    numbered(DAILY_STATIONS, '01975', '10147')
    addNearer({ wmo_id: '10147' })
    const wrapper = await mountMap('/map?station=10147')
    await vi.waitFor(() => expect(headingOf(wrapper).text()).toBe('HAMBURG-FUHLSBUETTEL'))
    await chooseLayer(wrapper, 'measured')
    // the nearer of the two is the station for the place, as without a number
    await vi.waitFor(() => expect(headingOf(wrapper).text()).toBe('Hamburg-Nahe'))
    expect(wrapper.find('[data-testid="map-same-station"]').exists()).toBe(false)
  })

  it('does not carry a number that the reader has left: a station chosen in the list that has none is picked again by its place', async () => {
    numbered(FORECAST_STATIONS, '10147', '10147')
    numbered(DAILY_STATIONS, '01975', '10147')
    addNearer()
    FORECAST_STATIONS.push(FREIBURG_FORECAST)
    undo.push(() => {
      FORECAST_STATIONS.splice(FORECAST_STATIONS.indexOf(FREIBURG_FORECAST), 1)
    })
    const wrapper = await mountMap()
    await listed(wrapper)
    await wrapper.find('[data-station-id="10147"]').trigger('click')
    await vi.waitFor(() => expect(headingOf(wrapper).text()).toBe('HAMBURG-FUHLSBUETTEL'))
    await wrapper.find('[data-testid="map-back"]').trigger('click')
    await vi.waitFor(() => expect(headingOf(wrapper).exists()).toBe(false))
    // a station with no number, then a change of layer: the number of the one before is not kept
    ;(wrapper.vm as any).search = 'FREIBURG'
    await vi.waitFor(() => expect(wrapper.find('[data-station-id="10401"]').exists()).toBe(true))
    await wrapper.find('[data-station-id="10401"]').trigger('click')
    await vi.waitFor(() => expect(headingOf(wrapper).text()).toBe('FREIBURG'))
    await chooseLayer(wrapper, 'measured')
    await vi.waitFor(() => expect(headingOf(wrapper).exists()).toBe(true))
    expect(headingOf(wrapper).text()).not.toBe('Hamburg-Fuhlsbüttel')
    expect(wrapper.find('[data-testid="map-same-station"]').exists()).toBe(false)
  })

  it('takes the station of another card by the number as well: the cards of the other kinds are the same station, not the one nearest to the place', async () => {
    numbered(FORECAST_STATIONS, '10147', '10147')
    numbered(DAILY_STATIONS, '01975', '10147')
    addNearer()
    const wrapper = await mountMap('/map?station=10147')
    await vi.waitFor(() => expect(headingOf(wrapper).text()).toBe('HAMBURG-FUHLSBUETTEL'))
    const card = () => wrapper.find('[data-testid="map-card-measured"]')
    await vi.waitFor(() => expect(card().find('[data-testid="map-card-same-measured"]').exists()).toBe(true))
    expect(card().find('[data-testid="map-card-same-measured"]').text()).toBe('Hamburg-Fuhlsbüttel · The same station, by its WMO number 10147.')
    // the links are at that station, and no nearer one that has stopped is offered in its place
    expect(card().findAll('a').map(link => link.attributes('href')).every(href => href!.includes('stations=01975'))).toBe(true)
    expect(card().find('[data-testid="map-why"]').exists()).toBe(false)
    expect(card().text()).not.toContain('away')
  })

  it('has the cards of the other kinds go by the position where the station has no number', async () => {
    addNearer()
    const wrapper = await mountMap('/map?station=10147')
    await vi.waitFor(() => expect(headingOf(wrapper).text()).toBe('HAMBURG-FUHLSBUETTEL'))
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-card-measured"]').text()).toContain('Hamburg-Nahe'))
    expect(wrapper.find('[data-testid="map-card-same-measured"]').exists()).toBe(false)
  })
})

describe('what a pick carries across layers is the pick the reader made last (GH-4077)', () => {
  const headingOf = (wrapper: Awaited<ReturnType<typeof mountMap>>) => wrapper.find('[data-testid="map-station-name"]')
  const undo: Array<() => void> = []
  function numbered(list: Array<Record<string, any>>, stationId: string, wmo: string | null) {
    const entry = list.find(candidate => candidate.station_id === stationId)!
    entry.wmo_id = wmo
    undo.push(() => {
      delete entry.wmo_id
    })
  }
  function added(list: Array<Record<string, any>>, entry: Record<string, any>) {
    list.push(entry)
    undo.push(() => {
      list.splice(list.indexOf(entry), 1)
    })
  }
  afterEach(() => {
    while (undo.length)
      undo.pop()!()
  })
  // a click on the Gulf of Guinea, where no station is within reach
  const SEA = { latitude: 0, longitude: 0, tolerance: 0.5, tap: 0, disc: 0.5 }

  it('is no station after a click on the sea: the number of the station before is not carried to the next layer for a place with none', async () => {
    numbered(FORECAST_STATIONS, '10147', '10147')
    numbered(DAILY_STATIONS, '01975', '10147')
    const wrapper = await mountMap('/map?station=10147')
    await vi.waitFor(() => expect(headingOf(wrapper).text()).toBe('HAMBURG-FUHLSBUETTEL'))
    // a click on the sea: the reader's pick is a place with no station
    stage.emit('pick', SEA)
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-none-near"]').exists()).toBe(true))
    await chooseLayer(wrapper, 'measured')
    // the place is where it was clicked: no station, and no "same station" at 6,000 km
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-none-near"]').exists()).toBe(true))
    expect(headingOf(wrapper).exists()).toBe(false)
    expect(wrapper.find('[data-testid="map-same-station"]').exists()).toBe(false)
    expect(stage.props.selected).toBeNull()
  })

  it('is the station of an address that was named after a pick of the sea, and is not the one before it: the address is a new pick', async () => {
    numbered(FORECAST_STATIONS, '10147', '10147')
    numbered(DAILY_STATIONS, '01975', '10147')
    const wrapper = await mountMap('/map?station=10147')
    await vi.waitFor(() => expect(headingOf(wrapper).text()).toBe('HAMBURG-FUHLSBUETTEL'))
    stage.emit('pick', SEA)
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-none-near"]').exists()).toBe(true))
    // back in the history to the address of the plain map, and a layer chosen: nothing is picked, and nothing said of the same
    await useRouter().push('/map')
    await chooseLayer(wrapper, 'measured')
    await nextTick()
    expect(headingOf(wrapper).exists()).toBe(false)
    expect(wrapper.find('[data-testid="map-same-station"]').exists()).toBe(false)
  })

  it('forgets the station of an address that is another pick: the number is the one of the new station when its list brings it', async () => {
    numbered(FORECAST_STATIONS, '10147', '10147')
    numbered(DAILY_STATIONS, '01975', '10147')
    // Munich has no measuring station within reach in the mock, and no number
    const wrapper = await mountMap('/map?station=10147')
    await vi.waitFor(() => expect(headingOf(wrapper).text()).toBe('HAMBURG-FUHLSBUETTEL'))
    await useRouter().push('/map?station=10865')
    await vi.waitFor(() => expect(headingOf(wrapper).text()).toBe('MUENCHEN-STADT'))
    await chooseLayer(wrapper, 'measured')
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-none-near"]').exists()).toBe(true))
    expect(wrapper.find('[data-testid="map-same-station"]').exists()).toBe(false)
  })

  it('keeps the number of the pick through a layer that has no station near, and finds the station again in the next that has it', async () => {
    // Jan Mayen's number is on a forecast point; the measuring list has a station of the same id with another number
    // (59 ids are two stations), and a decoy that carries that other number, in another place
    const DECOY = station('10999', 'DECOY', 48.2, 11.5, { wmo_id: '99992' })
    added(FORECAST_STATIONS, DECOY)
    addCollision()
    undo.push(removeCollision)
    numbered(FORECAST_STATIONS, '01001', '99991')
    numbered(DAILY_STATIONS, '01001', '99992')
    const wrapper = await mountMap('/map?station=01001')
    await vi.waitFor(() => expect(headingOf(wrapper).text()).toBe('JAN MAYEN'))
    await chooseLayer(wrapper, 'measured')
    // nothing of Jan Mayen's number in the measuring list, and no station within reach of it
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-none-near"]').exists()).toBe(true))
    // back: the number that was remembered is Jan Mayen's, not that of the station of the same id in the list between (which
    // would have taken the decoy, 6,000 km away)
    await chooseLayer(wrapper, 'forecast')
    await vi.waitFor(() => expect(headingOf(wrapper).text()).toBe('JAN MAYEN'))
    expect(wrapper.find('[data-testid="map-same-station"]').text()).toBe('The same station, by its WMO number 99991.')
  })

  describe('a number that a closed station keeps (the Stationslexikon, 10427: Altastenberg until 1954, Kahler Asten after)', () => {
    const CLOSED_PREDECESSOR = station('00098', 'Altastenberg', 53.6333, 9.9881, { wmo_id: '10147', start_timestamp: '1900-01-01T00:00:00+00:00', end_timestamp: '1954-12-31T00:00:00+00:00' })

    it('is not taken for the station that reports where the list has only the closed one: the station is picked again by the place', async () => {
      numbered(FORECAST_STATIONS, '10147', '10147')
      // the closed station holds the number, the one that reports (and is nearer to nothing else) has none
      added(DAILY_STATIONS, CLOSED_PREDECESSOR)
      const wrapper = await mountMap('/map?station=10147')
      await vi.waitFor(() => expect(headingOf(wrapper).text()).toBe('HAMBURG-FUHLSBUETTEL'))
      await chooseLayer(wrapper, 'measured')
      // the station for the place: the one that reports within reach, before the closed one that is nearer
      await vi.waitFor(() => expect(headingOf(wrapper).text()).toBe('Hamburg-Fuhlsbüttel'))
      expect(wrapper.find('[data-testid="map-same-station"]').exists()).toBe(false)
    })

    it('is taken in a list that has no status, the forecast\'s points: a closed station of the observations is still the same station', async () => {
      numbered(DAILY_STATIONS, '00011', '10148')
      // a forecast point of the same number: the layer is a forecast, whose points have no status; Donaueschingen closed in 2001
      added(FORECAST_STATIONS, station('10148', 'DONAUESCHINGEN', 47.98, 8.52, { wmo_id: '10148' }))
      const wrapper = await mountMap('/map?layer=measured&station=00011')
      await vi.waitFor(() => expect(headingOf(wrapper).text()).toBe('Donaueschingen (Landeplatz)'))
      await chooseLayer(wrapper, 'forecast')
      await vi.waitFor(() => expect(headingOf(wrapper).text()).toBe('DONAUESCHINGEN'))
    })

    it('has the cards go by the id first where the station picked is one of the observations: the stripes of that station, not of a station that has its number', async () => {
      numbered(DAILY_STATIONS, '01975', '10147')
      // the stripes list holds another station with the same number, nearer to the place than the station itself is
      stripesStations = [
        { ...STRIPES_STATIONS[0]!, station_id: '77777', name: 'Same number, other id', latitude: 53.6333, longitude: 9.9882, wmo_id: '10147' } as any,
        STRIPES_STATIONS[0]!,
      ]
      const wrapper = await mountMap('/map?layer=measured&station=01975')
      await vi.waitFor(() => expect(headingOf(wrapper).text()).toBe('Hamburg-Fuhlsbüttel'))
      const card = () => wrapper.find('[data-testid="map-card-stripes"]')
      await vi.waitFor(() => expect(card().find('a[href^="/stripes"]').exists()).toBe(true))
      expect(card().find('a[href^="/stripes"]').attributes('href')).toContain('station=01975')
    })

    it('has the card of a station that reports skip a closed station that has its number: the one nearest that reports is offered', async () => {
      numbered(FORECAST_STATIONS, '10147', '10147')
      added(DAILY_STATIONS, CLOSED_PREDECESSOR)
      const wrapper = await mountMap('/map?station=10147')
      await vi.waitFor(() => expect(headingOf(wrapper).text()).toBe('HAMBURG-FUHLSBUETTEL'))
      await vi.waitFor(() => expect(wrapper.find('[data-testid="map-card-measured"]').text()).toContain('Hamburg-Fuhlsbüttel'))
      expect(wrapper.find('[data-testid="map-card-same-measured"]').exists()).toBe(false)
    })
  })
})

describe('the GHCN daily layer (GH-4078, GH-4267)', () => {
  /** What the map reports of itself: where it is and how far in (the world, a continent, a town) */
  const viewAt = (latitude: number, longitude: number, zoom = 8) => ({ latitude, longitude, zoom })
  const WORLD_VIEW = viewAt(10, 0, 2)
  const EUROPE_VIEW = viewAt(50, 10, 4)
  const HAMBURG_VIEW = viewAt(53.6, 10, 8)
  const NEW_YORK_VIEW = viewAt(40.8, -74, 8)
  const ghcnAsks = () => asked.stations.filter(query => query.network === 'ghcn')
  const idsOnMap = () => stage.props.stations.map((entry: any) => entry.station_id)
  const ALL_IDS = GHCN_STATIONS.map(entry => entry.station_id).sort()

  /** The map's own code is loaded apart from the page: its stand-in raises events once it is there */
  const mapIsThere = (wrapper: Awaited<ReturnType<typeof mountMap>>) => vi.waitFor(() => expect(wrapper.find('[data-testid="station-map"]').exists()).toBe(true))
  /** The GHCN layer, with the map at Hamburg and its stations loaded */
  async function mountGhcn(route = '/map') {
    const wrapper = await mountMap(route)
    await mapIsThere(wrapper)
    await chooseLayer(wrapper, 'ghcn')
    stage.emit('view', HAMBURG_VIEW)
    await vi.waitFor(() => expect(idsOnMap()).toContain('GM000010147'), { timeout: 3000 })
    return wrapper
  }
  const pickFromList = async (wrapper: Awaited<ReturnType<typeof mountMap>>, id: string) => {
    await wrapper.find(`[data-station-id="${id}"]`).trigger('click')
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-station-name"]').exists()).toBe(true))
  }

  it('is the third layer, named in the panel of the layers button, and the address names it', async () => {
    const wrapper = await mountMap()
    await mapIsThere(wrapper)
    await chooseLayer(wrapper, 'ghcn')
    expect(layerButton(wrapper, 'ghcn').attributes('aria-checked')).toBe('true')
    expect(wrapper.find('[data-testid="station-map"]').attributes('aria-label')).toBe('Station map: NOAA GHCN daily')
    await vi.waitFor(() => expect(useRouter().currentRoute.value.query.layer).toBe('ghcn'))
  })

  it('loads every station once, as soon as the layer is chosen at a view of the whole world: no box, no zoom in, no hint', async () => {
    const wrapper = await mountMap()
    await mapIsThere(wrapper)
    stage.emit('view', WORLD_VIEW)
    await nextTick()
    await chooseLayer(wrapper, 'ghcn')
    await vi.waitFor(() => expect(idsOnMap().sort()).toEqual(ALL_IDS), { timeout: 3000 })
    expect(ghcnListAsked.count).toBe(1)
    // the list is the app's server's; the backend is not asked for a box, or for the whole list (44 MB)
    expect(ghcnAsks()).toEqual([])
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-count"]').text()).toBe('Stations shown: 5'))
    expect(wrapper.find('[data-testid="map-zoom-hint"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="map-zoom-hint-panel"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="map-search-hint"]').exists()).toBe(false)
    // the whole world in view or a continent, a pan or a zoom: the stations are in hand, and nothing is asked again
    for (const view of [EUROPE_VIEW, HAMBURG_VIEW, NEW_YORK_VIEW, WORLD_VIEW])
      stage.emit('view', view)
    await new Promise(resolve => setTimeout(resolve, 500))
    expect(ghcnListAsked.count).toBe(1)
    expect(ghcnAsks()).toEqual([])
    expect(idsOnMap().sort()).toEqual(ALL_IDS)
  })

  it('asks once where the moves come while the list is on its way', async () => {
    ghcnListDelay = 300
    const wrapper = await mountMap()
    await mapIsThere(wrapper)
    await chooseLayer(wrapper, 'ghcn')
    for (const view of [WORLD_VIEW, EUROPE_VIEW, HAMBURG_VIEW])
      stage.emit('view', view)
    expect(wrapper.text()).toContain('Loading stations')
    await vi.waitFor(() => expect(idsOnMap().sort()).toEqual(ALL_IDS), { timeout: 3000 })
    expect(ghcnListAsked.count).toBe(1)
  })

  it('has the list in hand when the layer is chosen again, and asks for it no more', async () => {
    const wrapper = await mountGhcn()
    await chooseLayer(wrapper, 'forecast')
    await vi.waitFor(() => expect(idsOnMap()).toContain('10147'))
    await chooseLayer(wrapper, 'ghcn')
    await vi.waitFor(() => expect(idsOnMap().sort()).toEqual(ALL_IDS))
    expect(ghcnListAsked.count).toBe(1)
  })

  it('lists the stations near the centre of the map and finds one by its name from all of them, the ones far from the view too', async () => {
    const wrapper = await mountGhcn()
    const near = () => wrapper.findAll('[data-testid="map-list"] [data-station-id]').map(item => item.attributes('data-station-id'))
    // Hamburg at the centre: its own station first, and New York is in the list, though it is on the other side of the ocean
    expect(near()[0]).toBe('GM000010147')
    expect(near()).toContain('USW00094728')
    await wrapper.find('#map-search').setValue('new york')
    await vi.waitFor(() => expect(near()).toEqual(['USW00094728']))
  })

  it('is always grouped, and the switch says so, where the list holds more than 10,000 stations', async () => {
    ghcnFiller = 10_000
    const wrapper = await mountGhcn()
    await vi.waitFor(() => expect(stage.props.stations.length).toBe(10_005), { timeout: 5000 })
    expect(stage.props.grouping).not.toBeNull()
    await openLayers(wrapper)
    expect(wrapper.find('[data-testid="map-grouping-note"]').exists()).toBe(true)
    // the measuring stations of DWD, and the stripes' ones, are not asked for
    expect(asked.stations.some(query => query.network === 'observation')).toBe(false)
  })

  it('draws a station that has stopped as the measuring layer does, and the others as reporting, by the years of the list', async () => {
    await mountGhcn()
    const rule = stage.props.reporting as (station: { end_timestamp: string | null }) => boolean
    const byId = (id: string) => stage.props.stations.find((entry: any) => entry.station_id === id)
    expect(rule(byId('GM000010147'))).toBe(true)
    expect(rule(byId('GME00122866'))).toBe(false)
  })

  describe('where the list cannot be loaded', () => {
    // a 502 is asked for once more (`RETRY_TRANSIENT`), so the outage lasts through two requests
    it('shows the failure with Retry, and never a layer with no stations that reads as having none', async () => {
      ghcnListFailures = 2
      const wrapper = await mountMap()
      await mapIsThere(wrapper)
      await chooseLayer(wrapper, 'ghcn')
      const failure = () => wrapper.find('[data-testid="map-failure"]')
      await vi.waitFor(() => expect(failure().exists()).toBe(true), { timeout: 3000 })
      expect(failure().text()).toContain('The stations could not be loaded')
      expect(failure().text()).toContain('The backend could not be reached')
      expect(idsOnMap()).toEqual([])
      expect(wrapper.find('[data-testid="map-empty"]').exists()).toBe(false)
      expect(wrapper.find('[data-testid="map-count"]').exists()).toBe(false)
      await wrapper.find('[data-testid="map-failure"] button').trigger('click')
      await vi.waitFor(() => expect(idsOnMap().sort()).toEqual(ALL_IDS), { timeout: 3000 })
      expect(failure().exists()).toBe(false)
      expect(ghcnListAsked.count).toBe(3)
    })

    it('tells it as a failure with Retry, and not as a station that is not there, where the address names a station', async () => {
      ghcnListFailures = 2
      const wrapper = await mountMap('/map?layer=ghcn&station=USW00094728')
      await vi.waitFor(() => expect(wrapper.find('[data-testid="map-failure"]').exists()).toBe(true), { timeout: 3000 })
      expect(wrapper.find('[data-testid="map-unknown"]').exists()).toBe(false)
      expect(wrapper.find('[data-testid="map-station-name"]').exists()).toBe(false)
      await wrapper.find('[data-testid="map-failure"] button').trigger('click')
      await vi.waitFor(() => expect(wrapper.find('[data-testid="map-station-name"]').text()).toBe('NEW YORK CNTRL PK TWR'), { timeout: 3000 })
    })
  })

  it('has a station picked its own climate stripes, with how a day was made, its measurements in the Explorer, and the nearest forecast point', async () => {
    const wrapper = await mountGhcn()
    await pickFromList(wrapper, 'GM000010147')
    expect(wrapper.find('[data-testid="map-station-name"]').text()).toBe('HAMBURG FUHLSBUETTEL')

    const stripes = wrapper.find('[data-testid="map-card-stripes"]')
    await vi.waitFor(() => expect(stripes.find('[data-testid="map-stripes-method"]').exists()).toBe(true))
    expect(asked.stripesQueries.at(-1)).toMatchObject({ kind: 'temperature', station: 'GM000010147' })
    // the midrange of the daily maximum and minimum, no 24-hour mean (decision on GH-4222)
    expect(stripes.find('[data-testid="map-stripes-method"]').text()).toContain('midrange of the daily maximum and minimum, not a 24-hour mean')
    expect(stripes.find('a[href^="/stripes"]').attributes('href')).toBe('/stripes?kind=temperature&provider=noaa&network=ghcn&station=GM000010147')

    // the Explorer on the network of the layer; the station history is DWD's alone
    const measured = wrapper.find('[data-testid="map-card-measured"]')
    expect(measured.find('[data-testid="map-card-ghcn-source"]').text()).toBe('NOAA GHCN, daily · since 1891')
    const links = measured.findAll('a')
    expect(links).toHaveLength(1)
    expect(Object.fromEntries(new URL(links[0]!.attributes('href')!, 'http://x').searchParams)).toEqual({
      provider: 'noaa',
      network: 'ghcn',
      resolution: 'daily',
      dataset: 'data',
      mode: 'station',
      stations: 'GM000010147',
    })

    // the forecast: the nearest MOSMIX point, as for any station
    const forecast = wrapper.find('[data-testid="map-card-forecast"]')
    await vi.waitFor(() => expect(forecast.find('a').exists()).toBe(true))
    expect(forecast.text()).toContain('HAMBURG-FUHLSBUETTEL')
    expect(forecast.findAll('a').some(link => link.attributes('href') === '/meteogram?station=10147')).toBe(true)

    // DWD's stripes and measurements are not asked for: the cards are about this station
    expect(asked.stations.some(query => query.network === 'observation')).toBe(false)
    expect(stripes.text()).not.toContain('away')
  })

  describe('the details of a station that the list has not (elevation, WMO number)', () => {
    it('are asked for by the station\'s id when it is picked, and the panel has its name at once', async () => {
      const wrapper = await mountGhcn()
      await pickFromList(wrapper, 'GM000010147')
      // the name and the position are the list's
      expect(wrapper.find('[data-testid="map-station-name"]').text()).toBe('HAMBURG FUHLSBUETTEL')
      await vi.waitFor(() => expect(wrapper.find('[data-testid="map-detail"], .map-detail').text()).toContain('11 m above sea level'))
      expect(ghcnAsks()).toEqual([expect.objectContaining({ provider: 'noaa', network: 'ghcn', parameters: 'daily/data', stations: 'GM000010147' })])
      expect(ghcnAsks()[0]!.all).toBeUndefined()
    })

    it('are asked for the station picked, not the one before, where the pick changes while they are on their way', async () => {
      const wrapper = await mountGhcn()
      await pickFromList(wrapper, 'GM000010147')
      // a click on the dot of New York, on the map
      stage.emit('pick', { latitude: 40.7789, longitude: -73.9692, tolerance: 1, tap: 0, disc: 0 })
      await vi.waitFor(() => expect(wrapper.find('[data-testid="map-station-name"]').text()).toBe('NEW YORK CNTRL PK TWR'))
      await vi.waitFor(() => expect(wrapper.find('.map-detail').text()).toContain('43 m above sea level'))
      expect(wrapper.find('.map-detail').text()).not.toContain('11 m above sea level')
    })

    it('give the forecast of the point that has the station\'s WMO number, which is the same station, with the details held: the list has the number', async () => {
      const hamburg = FORECAST_STATIONS[0]!
      FORECAST_STATIONS[0] = { ...hamburg, wmo_id: '10147' } as typeof hamburg
      const open = holdDetails()
      try {
        const wrapper = await mountGhcn()
        await pickFromList(wrapper, 'GM000010147')
        const forecast = wrapper.find('[data-testid="map-card-forecast"]')
        await vi.waitFor(() => expect(forecast.find('[data-testid="map-card-same-forecast"]').exists()).toBe(true))
        expect(forecast.find('[data-testid="map-card-same-forecast"]').text()).toContain('The same station, by its WMO number 10147.')
        // the details have not come (the gate is closed), and the elevation comes with them
        expect(wrapper.find('.map-detail').text()).not.toContain('above sea level')
        open()
        await vi.waitFor(() => expect(wrapper.find('.map-detail').text()).toContain('11 m above sea level'))
      }
      finally {
        FORECAST_STATIONS[0] = hamburg
      }
    })

    it('leave the panel with the list\'s name and position, and no failure, where they cannot be asked for', async () => {
      ghcnDetailFailures = 1
      const wrapper = await mountGhcn()
      await pickFromList(wrapper, 'GM000010147')
      await vi.waitFor(() => expect(ghcnDetailFailures).toBe(0))
      await new Promise(resolve => setTimeout(resolve, 100))
      expect(wrapper.find('[data-testid="map-station-name"]').text()).toBe('HAMBURG FUHLSBUETTEL')
      expect(wrapper.find('.map-detail').text()).not.toContain('above sea level')
      expect(wrapper.find('[data-testid="map-failure"]').exists()).toBe(false)
    })
  })

  it('says a station has no stripes, with no request and no link, where its record is shorter than the ten years they need', async () => {
    const wrapper = await mountGhcn()
    await pickFromList(wrapper, 'BF1BI000002')
    const stripes = wrapper.find('[data-testid="map-card-stripes"]')
    expect(stripes.find('[data-testid="map-stripes-none"]').text()).toBe('No climate stripes for this station.')
    expect(stripes.findAll('a')).toHaveLength(0)
    expect(asked.stripesValues).not.toContain('BF1BI000002')
  })

  it('says a station has no stripes where the app cannot make them of its record (too few years with data), and takes the link away: no failure to try again', async () => {
    const wrapper = await mountGhcn()
    await pickFromList(wrapper, 'GME00122482')
    const stripes = wrapper.find('[data-testid="map-card-stripes"]')
    await vi.waitFor(() => expect(stripes.text()).toContain('No climate stripes for this station.'))
    expect(asked.stripesValues).toContain('GME00122482')
    await vi.waitFor(() => expect(stripes.findAll('a')).toHaveLength(0))
    expect(stripes.find('[role="alert"]').exists()).toBe(false)
    expect(stripes.text()).not.toContain('Retry')
  })

  it('keeps the station picked where the map moves away, and lets it go on Back', async () => {
    const wrapper = await mountGhcn()
    await pickFromList(wrapper, 'GM000010147')
    stage.emit('view', NEW_YORK_VIEW)
    await nextTick()
    expect(wrapper.find('[data-testid="map-station-name"]').text()).toBe('HAMBURG FUHLSBUETTEL')
    await wrapper.find('[data-testid="map-back"]').trigger('click')
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-station-name"]').exists()).toBe(false))
    expect(idsOnMap().sort()).toEqual(ALL_IDS)
  })

  it('opens on the station an address names, wherever it is: it is in the list', async () => {
    const wrapper = await mountMap('/map?layer=ghcn&station=USW00094728')
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-station-name"]').text()).toBe('NEW YORK CNTRL PK TWR'), { timeout: 3000 })
    expect(ghcnListAsked.count).toBe(1)
    expect(wrapper.find('[data-testid="map-unknown"]').exists()).toBe(false)
    // the map is moved to it, as it is for any station of an address
    await vi.waitFor(() => expect(stage.props.recentre).toBeGreaterThan(0))
  })

  it('says a station of the address that the layer has not got, as any layer does', async () => {
    const wrapper = await mountMap('/map?layer=ghcn&station=NOPE')
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-unknown"]').text()).toBe('There is no station NOPE on this map.'), { timeout: 3000 })
    expect(wrapper.find('[data-testid="map-station-name"]').exists()).toBe(false)
    // and no request for the details of a station the list has not got
    expect(ghcnAsks()).toEqual([])
  })

  describe('a pick that is carried to the layer from another (the place is kept)', () => {
    /** The forecast layer with Hamburg picked, the map then moved to New York: the place picked is off the screen */
    async function pickedAndPannedAway() {
      const wrapper = await mountMap()
      await mapIsThere(wrapper)
      await listed(wrapper)
      stage.emit('view', HAMBURG_VIEW)
      await wrapper.find('[data-station-id="10147"]').trigger('click')
      await vi.waitFor(() => expect(wrapper.find('[data-testid="map-station-name"]').text()).toBe('HAMBURG-FUHLSBUETTEL'))
      stage.emit('view', NEW_YORK_VIEW)
      await nextTick()
      return wrapper
    }

    it('picks the nearest station to the place, though the map is elsewhere, and keeps the map where it was moved to', async () => {
      const wrapper = await pickedAndPannedAway()
      const recentred = stage.props.recentre
      await chooseLayer(wrapper, 'ghcn')
      await vi.waitFor(() => expect(wrapper.find('[data-testid="map-station-name"]').text()).toBe('HAMBURG FUHLSBUETTEL'), { timeout: 3000 })
      // the map was not sent to it: it stays where the reader moved it
      expect(stage.props.recentre).toBe(recentred)
      expect(idsOnMap().sort()).toEqual(ALL_IDS)
      expect(wrapper.find('[data-testid="map-none-near"]').exists()).toBe(false)
    })

    it('finds the station of the forecast point by its WMO number, which the list has, and says it is the same station (GH-4077)', async () => {
      const hamburg = FORECAST_STATIONS[0]!
      FORECAST_STATIONS[0] = { ...hamburg, wmo_id: '10147' } as typeof hamburg
      holdDetails()
      try {
        const wrapper = await pickedAndPannedAway()
        await chooseLayer(wrapper, 'ghcn')
        await vi.waitFor(() => expect(wrapper.find('[data-testid="map-station-name"]').text()).toBe('HAMBURG FUHLSBUETTEL'), { timeout: 3000 })
        expect(wrapper.find('[data-testid="map-same-station"]').text()).toContain('The same station, by its WMO number 10147.')
      }
      finally {
        FORECAST_STATIONS[0] = hamburg
      }
    })

    it('picks the station that has the WMO number where another of the list is nearer to the place', async () => {
      const hamburg = FORECAST_STATIONS[0]!
      FORECAST_STATIONS[0] = { ...hamburg, wmo_id: '10147' } as typeof hamburg
      ghcnNeighbour = true
      try {
        const wrapper = await mountMap()
        await mapIsThere(wrapper)
        await listed(wrapper)
        stage.emit('view', HAMBURG_VIEW)
        // a click on the forecast point's dot, which is a place that HAMBURG NEBENAN (0.01 km) is nearer to than its twin (0.8 km)
        stage.emit('pick', { latitude: 53.63, longitude: 10.0, tolerance: 0.05, tap: 0, disc: 0 })
        await vi.waitFor(() => expect(wrapper.find('[data-testid="map-station-name"]').text()).toBe('HAMBURG-FUHLSBUETTEL'))
        await chooseLayer(wrapper, 'ghcn')
        await vi.waitFor(() => expect(wrapper.find('[data-testid="map-station-name"]').text()).toBe('HAMBURG FUHLSBUETTEL'), { timeout: 3000 })
        expect(wrapper.find('[data-testid="map-same-station"]').exists()).toBe(true)
        expect(idsOnMap()).toContain('GM000099999')
      }
      finally {
        FORECAST_STATIONS[0] = hamburg
      }
    })

    it('carries the WMO number of a station of the layer to another layer before its details have come', async () => {
      const hamburg = FORECAST_STATIONS[0]!
      FORECAST_STATIONS[0] = { ...hamburg, wmo_id: '10147' } as typeof hamburg
      holdDetails()
      try {
        const wrapper = await mountGhcn()
        await pickFromList(wrapper, 'GM000010147')
        await chooseLayer(wrapper, 'forecast')
        await vi.waitFor(() => expect(wrapper.find('[data-testid="map-station-name"]').text()).toBe('HAMBURG-FUHLSBUETTEL'), { timeout: 3000 })
        expect(wrapper.find('[data-testid="map-same-station"]').text()).toContain('The same station, by its WMO number 10147.')
      }
      finally {
        FORECAST_STATIONS[0] = hamburg
      }
    })

    it('does so again where the layer is left and chosen again, with the list it has', async () => {
      const wrapper = await mountGhcn()
      await pickFromList(wrapper, 'GM000010147')
      await chooseLayer(wrapper, 'forecast')
      await vi.waitFor(() => expect(wrapper.find('[data-testid="map-station-name"]').text()).toBe('HAMBURG-FUHLSBUETTEL'), { timeout: 3000 })
      stage.emit('view', NEW_YORK_VIEW)
      await nextTick()
      await chooseLayer(wrapper, 'ghcn')
      await vi.waitFor(() => expect(wrapper.find('[data-testid="map-station-name"]').text()).toBe('HAMBURG FUHLSBUETTEL'), { timeout: 3000 })
      expect(ghcnListAsked.count).toBe(1)
    })

    it('says there is no station near where the list has none within reach of the place', async () => {
      const wrapper = await mountMap()
      await mapIsThere(wrapper)
      await listed(wrapper)
      // Paris-Orly of the forecast's points: no station of the mock is within 100 km of it
      stage.emit('view', viewAt(48.72, 2.38))
      await wrapper.find('[data-station-id="07157"]').trigger('click')
      await vi.waitFor(() => expect(wrapper.find('[data-testid="map-station-name"]').text()).toBe('PARIS-ORLY'))
      await chooseLayer(wrapper, 'ghcn')
      await vi.waitFor(() => expect(wrapper.find('[data-testid="map-none-near"]').exists()).toBe(true), { timeout: 3000 })
    })
  })
})
