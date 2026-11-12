import type { H3Event } from 'h3'
import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { getQuery, setResponseHeader, setResponseStatus } from 'h3'
import { afterEach, beforeEach, describe, expect, it, onTestFinished, vi } from 'vitest'
import { nextTick } from 'vue'
import { clearNuxtData, clearNuxtState, useMyLocation, useRouter } from '#imports'
import MapPage from '~/pages/map.vue'

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
      props: ['stations', 'selected', 'place', 'label', 'recentre', 'reporting', 'position', 'locate'],
      emits: ['pick', 'view'],
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
const asked: { stations: Array<Record<string, string>>, stripesValues: string[], values: string[] } = { stations: [], stripesValues: [], values: [] }
let stationsFailures = 0
let stripesStatus = 200

function stationsOf(event: H3Event) {
  const query = getQuery(event) as Record<string, string>
  asked.stations.push(query)
  if (stationsFailures > 0 && query.network === 'mosmix') {
    stationsFailures--
    // a 500, which a request is not asked for again: the REST API answers a failure of its own or of the source's so
    setResponseStatus(event, 500)
    return { detail: 'The forecast stations are not available' }
  }
  if (query.network === 'mosmix')
    return { stations: FORECAST_STATIONS }
  if (query.parameters === 'hourly/temperature_air')
    return { stations: HOURLY_STATIONS }
  return { stations: query.parameters === 'daily/solar' ? solarStations : DAILY_STATIONS }
}

function stripesValuesOf(event: H3Event) {
  asked.stripesValues.push(String(getQuery(event).station))
  if (stripesStatus !== 200) {
    setResponseStatus(event, stripesStatus)
    return { detail: 'This station has no complete years.' }
  }
  return {
    metadata: {},
    series: { station: STRIPES_STATIONS[0], resolution: 'annual', dataset: 'climate_summary', parameter: 'temperature_air_mean_2m', unit: 'degree_celsius' },
    values: Array.from({ length: 20 }, (_, index) => ({ timestamp: `${2000 + index}-01-01T00:00:00+00:00`, value: 8 + index * 0.05 })),
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
let stripesStations: Array<typeof STRIPES_STATIONS[number]> = STRIPES_STATIONS
registerEndpoint('/api/stripes/stations', () => ({ stations: stripesStations }))
registerEndpoint('/api/stripes/values', stripesValuesOf)
registerEndpoint('/api/coverage', () => COVERAGE)

const originalMatchMedia = window.matchMedia
const mounted: Array<{ unmount: () => void }> = []
let valuesStatus = 200

async function mountMap(route = '/map') {
  const wrapper = await mountSuspended(MapPage, { route, attachTo: document.body })
  mounted.push(wrapper)
  return wrapper
}
const text = (wrapper: Awaited<ReturnType<typeof mountMap>>) => wrapper.text().replace(/\s+/g, ' ')
const panel = (wrapper: Awaited<ReturnType<typeof mountMap>>) => wrapper.find('[data-testid="map-panel"]')
const layerButton = (wrapper: Awaited<ReturnType<typeof mountMap>>, layer: string) => wrapper.find(`[data-testid="map-layer-${layer}"]`)

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
  asked.stations.length = asked.stripesValues.length = asked.values.length = 0
  stationsFailures = 0
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

  it('has the forecast stations as the first layer, chosen by chips that say which one they are in words and by being pressed', async () => {
    const wrapper = await mountMap()
    const group = wrapper.find('[role="group"][aria-label="Layer"]')
    expect(group.findAll('button').map(button => button.text())).toEqual(['Forecast stations', 'DWD measurements'])
    expect(layerButton(wrapper, 'forecast').attributes('aria-pressed')).toBe('true')
    expect(layerButton(wrapper, 'measured').attributes('aria-pressed')).toBe('false')
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
    await layerButton(wrapper, 'measured').trigger('click')
    expect(layerButton(wrapper, 'measured').attributes('aria-pressed')).toBe('true')
    expect(layerButton(wrapper, 'forecast').attributes('aria-pressed')).toBe('false')
    await vi.waitFor(() => expect(stage.props.stations.map((entry: any) => entry.station_id)).toEqual(['01975', '00011', '00183']))
    expect(asked.stations.at(-1)).toMatchObject({ provider: 'dwd', network: 'observation', parameters: 'daily/climate_summary', all: 'true' })
    expect(wrapper.find('[data-testid="map-resolution"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="map-dataset"]').exists()).toBe(true)
    expect(stage.props.label).toBe('Station map: DWD measurements')
  })

  it('asks for the stations of another resolution, keeping the dataset it has and taking the daily climate summary or the first where it has none', async () => {
    const wrapper = await mountMap()
    await layerButton(wrapper, 'measured').trigger('click')
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
    await layerButton(wrapper, 'measured').trigger('click')
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
    expect(card().find('a').attributes('href')).toBe('/meteogram?station=10147')
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
    expect(card().find('figcaption').text()).toMatch(/^From 2000 to 2019\. Lowest value 8\.0 .+ in 2000, highest value 9\.0 .+ in 2019\.$/)
    expect(card().find('a').attributes('href')).toBe('/stripes?kind=temperature&station=01975')
    expect(asked.stripesValues).toEqual(['01975'])
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
    await layerButton(wrapper, 'measured').trigger('click')
    await vi.waitFor(() => expect(stage.props.stations).toHaveLength(3))
    stage.emit('pick', { latitude: 47.97, longitude: 8.52, tolerance: 0.5 })
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-card-measured"]').text()).toContain('1980 to 2001'))
  })

  it('takes the link of the measurements from the source the chips have, and the station of the layer it is the layer of', async () => {
    const wrapper = await mountMap()
    await layerButton(wrapper, 'measured').trigger('click')
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
    await layerButton(wrapper, 'measured').trigger('click')
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
    await layerButton(wrapper, 'measured').trigger('click')
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
    expect(layerButton(wrapper, 'measured').attributes('aria-pressed')).toBe('true')
    expect(asked.stations.some(query => query.parameters === 'hourly/temperature_air')).toBe(true)
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
    const order = [...wrapper.element.querySelectorAll('[data-testid="map-layer-forecast"], [data-testid="station-map"], input[type="search"]')].map(element => element.getAttribute('data-testid') ?? 'search')
    expect(order).toEqual(['map-layer-forecast', 'station-map', 'search'])
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
    await layerButton(wrapper, 'measured').trigger('click')
    await vi.waitFor(() => expect(wrapper.find('[data-testid="map-none-near"]').exists()).toBe(true))
    // no measuring station is within 100 km of Jan Mayen: nothing is picked, and what is shown is not the station with its number
    expect(headingOf(wrapper).exists()).toBe(false)
    expect(wrapper.find('[data-testid="map-none-near"]').text()).toBe('No station within 100 km of that point.')
    expect(wrapper.find('[data-testid="map-announcement"]').text()).toBe('No station within 100 km of that point.')
    expect(stage.props.selected).toBeNull()
    await vi.waitFor(() => expect(useRouter().currentRoute.value.query).toEqual({ layer: 'measured' }))
    // and back: the place is kept, and the forecast point at it is Jan Mayen again
    await layerButton(wrapper, 'forecast').trigger('click')
    await vi.waitFor(() => expect(headingOf(wrapper).text()).toBe('JAN MAYEN'))
    await vi.waitFor(() => expect(useRouter().currentRoute.value.query).toEqual({ station: '01001' }))
  })

  it('is picked again by the place in the other direction too: Doberlug-Kirchhain is not Jan Mayen', async () => {
    addCollision()
    const wrapper = await mountMap('/map?layer=measured&station=01001')
    await vi.waitFor(() => expect(headingOf(wrapper).text()).toBe('Doberlug-Kirchhain'))
    await layerButton(wrapper, 'forecast').trigger('click')
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
    await layerButton(wrapper, 'measured').trigger('click')
    await vi.waitFor(() => expect(headingOf(wrapper).text()).toBe('Hamburg-Fuhlsbüttel'))
    expect(wrapper.find('[data-testid="map-unknown"]').exists()).toBe(false)
    await vi.waitFor(() => expect(useRouter().currentRoute.value.query).toMatchObject({ layer: 'measured', station: '01975' }))
    await layerButton(wrapper, 'forecast').trigger('click')
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
    await layerButton(wrapper, 'measured').trigger('click')
    await vi.waitFor(() => expect(headingOf(wrapper).text()).toBe('Hamburg-Fuhlsbüttel'))
  })

  it('tells the station it has picked again, which is another than the one in the heading before', async () => {
    const wrapper = await mountMap('/map?station=10147')
    await vi.waitFor(() => expect(headingOf(wrapper).text()).toBe('HAMBURG-FUHLSBUETTEL'))
    await layerButton(wrapper, 'measured').trigger('click')
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
    await layerButton(wrapper, 'measured').trigger('click')
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
      await layerButton(wrapper, 'measured').trigger('click')
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
    await layerButton(wrapper, 'measured').trigger('click')
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
      await layerButton(wrapper, 'measured').trigger('click')
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
    await layerButton(wrapper, 'measured').trigger('click')
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
      expect(legend.attributes('aria-label')).toBe('Legend')
      expect(legend.findAll('li').map(item => item.text())).toEqual(['Still reporting', 'Stopped reporting'])
      // the two swatches are different shapes (filled and hollow), and no colour alone
      expect(legend.find('[data-testid="map-legend-reporting"]').classes()).not.toContain('map-legend-dot-stopped')
      expect(legend.find('[data-testid="map-legend-stopped"]').classes()).toContain('map-legend-dot-stopped')
      expect(legend.findAll('span[aria-hidden="true"]')).toHaveLength(2)
    })

    it('are not told apart on the forecast layer, whose points have no status: no rule, no legend', async () => {
      const wrapper = await mountMap()
      await listed(wrapper)
      expect(stage.props.reporting).toBeUndefined()
      expect(wrapper.find('[data-testid="map-legend"]').exists()).toBe(false)
      await layerButton(wrapper, 'measured').trigger('click')
      await vi.waitFor(() => expect(wrapper.find('[data-testid="map-legend"]').exists()).toBe(true))
      await layerButton(wrapper, 'forecast').trigger('click')
      await vi.waitFor(() => expect(wrapper.find('[data-testid="map-legend"]').exists()).toBe(false))
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
      await layerButton(wrapper, 'measured').trigger('click')
      await vi.waitFor(() => expect(stage.props.stations).toHaveLength(3))
      expect(asks).toBe(1)
      // the choices are the one source shown
      expect(vm.resolutionItems.map((item: any) => item.value)).toEqual(['daily'])
      await layerButton(wrapper, 'forecast').trigger('click')
      await layerButton(wrapper, 'measured').trigger('click')
      await vi.waitFor(() => expect(vm.resolutionItems.map((item: any) => item.value)).toEqual(['daily', 'hourly']))
      expect(asks).toBe(2)
      // and not again once it has come
      await layerButton(wrapper, 'forecast').trigger('click')
      await layerButton(wrapper, 'measured').trigger('click')
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
    expect(card().find('a').attributes('href')).toBe('/stripes?kind=temperature&station=01975')
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
    const asks = asked.stations.filter(query => query.network === 'observation').map(query => query.parameters)
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
    await layerButton(wrapper, 'measured').trigger('click')
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
      await layerButton(wrapper, 'measured').trigger('click')
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
      await layerButton(wrapper, 'measured').trigger('click')
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
      await layerButton(wrapper, 'forecast').trigger('click')
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
    await layerButton(wrapper, 'measured').trigger('click')
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
