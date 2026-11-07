import type { H3Event } from 'h3'
import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { getQuery, setResponseStatus } from 'h3'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import { clearNuxtData, useRouter } from '#imports'
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
      props: ['stations', 'selected', 'place', 'label', 'recentre'],
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
const DAILY_STATIONS = [
  station('01975', 'Hamburg-Fuhlsbüttel', 53.6332, 9.9881, { region: 'Hamburg', elevation: 11, start_timestamp: '1891-01-01T00:00:00+00:00' }),
  station('00011', 'Donaueschingen (Landeplatz)', 47.9737, 8.5205, { region: 'Baden-Württemberg', start_timestamp: '1980-09-01T00:00:00+00:00', end_timestamp: '2001-12-31T00:00:00+00:00' }),
  station('00183', 'Arkona', 54.6791, 13.4343, { region: 'Mecklenburg-Vorpommern' }),
]
const HOURLY_STATIONS = [station('00044', 'Großenkneten', 52.9336, 8.237)]
const STRIPES_STATIONS = [
  { station_id: '01975', name: 'Hamburg-Fuhlsbüttel', region: 'Hamburg', latitude: 53.6332, longitude: 9.9881, start_timestamp: null, end_timestamp: null },
  { station_id: '00011', name: 'Donaueschingen (Landeplatz)', region: 'Baden-Württemberg', latitude: 47.9737, longitude: 8.5205, start_timestamp: null, end_timestamp: null },
]
const COVERAGE = {
  daily: { description: null, datasets: { climate_summary: { description: null, parameters: [] }, more_precip: { description: null, parameters: [] } } },
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
  return { stations: query.parameters === 'hourly/temperature_air' ? HOURLY_STATIONS : DAILY_STATIONS }
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
registerEndpoint('/api/stripes/stations', () => ({ stations: STRIPES_STATIONS }))
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
    // the forecast point is the picked one: no "away" note
    expect(card().text()).not.toContain('away')
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
    // the layer's own station: no "away" note for the measurements
    expect(card.text()).not.toContain('away')
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
