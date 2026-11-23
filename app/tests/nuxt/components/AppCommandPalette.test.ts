import type { DOMWrapper } from '@vue/test-utils'
import { mockNuxtImport, mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { setResponseStatus } from 'h3'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { clearNuxtData, clearNuxtState } from '#app'
import AppCommandPalette from '~/components/AppCommandPalette.vue'
import { DEFAULT_PLACE } from '~/composables/usePlace'
import { SEARCH_STATIONS_DEFAULTS, useSettings } from '~/composables/useSettings'
import { providersAnswer } from '../fixtures/providers'

// The command palette of the search (GH-3518): the ARIA combobox with a listbox, its keys, and what it finds.

// where a choice of the palette goes: the router is not asked to load the page
const { navigateTo } = vi.hoisted(() => ({ navigateTo: vi.fn() }))
mockNuxtImport('navigateTo', () => navigateTo)

registerEndpoint('/api/providers', () => providersAnswer())
// the glossary, as the backend answers it, cut down to what the search reads; counted, since it is asked for when the search opens and not before
let glossaryRequests = 0
registerEndpoint('/api/glossary', () => {
  glossaryRequests++
  return [
    { name: 'temperature_dew_point_mean_2m', unit_type: 'temperature', unit: 'degree_celsius', unit_symbol: '°C', description: 'The temperature at which the air is saturated with water vapour' },
    { name: 'temperature_air_mean_2m', unit_type: 'temperature', unit: 'degree_celsius', unit_symbol: '°C', description: 'Mean temperature of the air two metres above the ground' },
    { name: 'temperature_air_max_2m', unit_type: 'temperature', unit: 'degree_celsius', unit_symbol: '°C', description: 'Highest temperature of the air two metres above the ground' },
    { name: 'temperature_air_min_2m', unit_type: 'temperature', unit: 'degree_celsius', unit_symbol: '°C', description: 'Lowest temperature of the air two metres above the ground' },
    { name: 'temperature_soil_mean_0_05m', unit_type: 'temperature', unit: 'degree_celsius', unit_symbol: '°C', description: 'Mean temperature of the soil at five centimetres' },
    { name: 'temperature_wet_mean_2m', unit_type: 'temperature', unit: 'degree_celsius', unit_symbol: '°C', description: 'Wet-bulb temperature two metres above the ground' },
    { name: 'wind_speed', unit_type: 'speed', unit: 'meter_per_second', unit_symbol: 'm/s', description: 'Mean speed of the wind' },
  ]
})
const stationQueries: string[] = []
const stationNetworks: string[] = []
let failStations = false
registerEndpoint('/api/stations', (event) => {
  if (failStations) {
    setResponseStatus(event, 500)
    return { detail: 'down' }
  }
  const query = new URL(event.path, 'http://localhost').searchParams
  const name = query.get('name') ?? ''
  stationQueries.push(name)
  stationNetworks.push(`${query.get('provider')}/${query.get('network')}`)
  // the measuring stations, as the places of the questions are looked for: one that reports and one that stopped
  if (query.get('network') === 'observation') {
    return {
      stations: [
        { station_id: '00183', name: 'Arkona', region: 'Mecklenburg-Vorpommern', latitude: 54.68, longitude: 13.43, elevation: 42, start_timestamp: '1991-01-01T00:00:00+00:00', end_timestamp: null },
        { station_id: '00198', name: 'Artern', region: 'Thüringen', latitude: 51.37, longitude: 11.29, elevation: 164, start_timestamp: '1991-01-01T00:00:00+00:00', end_timestamp: '2018-12-31T00:00:00+00:00' },
      ],
    }
  }
  return { stations: [{ station_id: '10384', name: 'BERLIN-TEMPELHOF', region: null, latitude: 52.47, longitude: 13.4, elevation: 49, start_timestamp: null, end_timestamp: null }] }
})

// the stations of the three networks the search matches by name, as the app's server answers them (GH-3790): what is asked is counted
const searchQueries: Array<{ q: string, limit: string, lists: string }> = []
let searchMode: 'answer' | 'fail' | 'pending-once' | 'pending-always' | 'slow' = 'answer'
/** The answer of the server that a test holds back (`slow`) until it lets it go */
let releaseSearch: (() => void) | null = null
let pendingServed = 0
const match = (station_id: string, name: string, extra: Record<string, unknown> = {}) => ({ station_id, name, latitude: 52.4, longitude: 13.4, wmo_id: null, first_year: 1950, last_year: null, reporting: true, ...extra })
registerEndpoint('/_search/stations', async (event) => {
  const query = new URL(event.path, 'http://localhost').searchParams
  searchQueries.push({ q: query.get('q') ?? '', limit: query.get('limit') ?? '', lists: query.get('lists') ?? '' })
  if (searchMode === 'fail') {
    setResponseStatus(event, 500)
    return { detail: 'down' }
  }
  if (searchMode === 'slow') {
    await new Promise<void>((resolve) => {
      releaseSearch = resolve
    })
  }
  const lists = (query.get('lists') ?? '').split(',')
  const networks = [
    { network: 'measured', total: 2, stations: [match('00403', 'Berlin-Dahlem (FU)'), match('00430', 'Berlin-Marzahn', { reporting: false, last_year: 2019 })] },
    { network: 'ghcn', total: 14, stations: ['BERLIN', 'BERLIN TEGEL', 'BERLIN-SCHONEFELD', 'BERLIN-BRANDENBURG'].map((name, index) => match(`GM00000${index}`, name)) },
  ].filter(found => lists.includes(found.network))
  // a list that is never there: no station of the two others, and the third still being read
  if (searchMode === 'pending-always')
    return { query: query.get('q'), networks: [], pending: ['ghcn'], failed: [] }
  // a list that is still being read the first time it is asked, and there the next
  if (searchMode === 'pending-once' && pendingServed++ === 0)
    return { query: query.get('q'), networks: networks.filter(found => found.network !== 'ghcn'), pending: ['ghcn'], failed: [] }
  return { query: query.get('q'), networks, pending: [], failed: [] }
})
// the search of every network for an id (GH-4286): it takes seconds, so the test decides when it is done
const idQueries: Array<Record<string, string>> = []
let releaseIds: (() => void) | null = null
let idAnswer: 'rows' | 'none' | 'fail' = 'rows'
registerEndpoint('/api/station-ids', async (event) => {
  idQueries.push(Object.fromEntries(new URL(event.path, 'http://localhost').searchParams))
  await new Promise<void>((resolve) => {
    releaseIds = resolve
  })
  if (idAnswer === 'fail') {
    setResponseStatus(event, 502)
    return { detail: 'down' }
  }
  const row = (extra: Record<string, unknown>) => ({ resolution: 'daily', dataset: 'climate_summary', name: 'X', latitude: 53.6, longitude: 10, elevation: 11, wmo_id: '10381', wigos_id: null, icao_id: null, matched_by: 'wmo_id', match: 'direct', ...extra })
  return {
    stations: idAnswer === 'none'
      ? []
      : [
          row({ provider: 'noaa', network: 'ghcn', resolution: 'daily', dataset: 'data', station_id: 'GM000010381', name: 'BERLIN-DAHLEM', match: 'equivalent' }),
          row({ provider: 'dwd', network: 'observation', station_id: '00403', name: 'Berlin-Dahlem (FU)' }),
          row({ provider: 'metno', network: 'observation', resolution: 'hourly', dataset: 'temperature_air', station_id: 'SN18700', name: 'OSLO-BLINDERN' }),
        ],
  }
})

// the places by name, as the app's server answers them from Photon (GH-3790, GH-3791): what is asked is counted; only "bad tölz" and "paris" have places
const placeQueries: Array<{ q: string, lang: string }> = []
let placesMode: 'answer' | 'off' | 'fail' | 'slow-first' = 'answer'
/** The first answer of the server that a test holds back (`slow-first`) until it lets it go */
let releasePlaces: (() => void) | null = null
const osmPlace = (id: string, name: string, kind: string, region: string | null, latitude: number, longitude: number) => ({ id, name, kind, region, latitude, longitude })
const PLACES: Record<string, ReturnType<typeof osmPlace>[]> = {
  'bad t': [osmPlace('N240109189', 'Bad Tölz', 'town', 'Bayern, Deutschland', 47.7614, 11.5583), osmPlace('R2145290', 'Landkreis Bad Tölz-Wolfratshausen', 'county', 'Bayern, Deutschland', 47.78, 11.5)],
  'paris': [osmPlace('N17807753', 'Paris', 'city', 'Île-de-France, France', 48.8566, 2.3522), osmPlace('N118', 'Paris', 'city', 'Texas, United States', 33.6609, -95.5555)],
}
registerEndpoint('/_search/places', async (event) => {
  const query = new URL(event.path, 'http://localhost').searchParams
  const q = query.get('q') ?? ''
  placeQueries.push({ q, lang: query.get('lang') ?? '' })
  if (placesMode === 'off')
    return { query: q, state: 'off', places: [], attribution: '© OpenStreetMap contributors' }
  if (placesMode === 'fail') {
    setResponseStatus(event, 503)
    return { type: 'urn:wetterdienst:problem:places-busy', title: 'Service Unavailable', status: 503, detail: 'busy' }
  }
  // the first request is held back until the test lets it go: a newer text overtakes it
  if (placesMode === 'slow-first' && placeQueries.length === 1) {
    await new Promise<void>((resolve) => {
      releasePlaces = resolve
    })
  }
  const key = Object.keys(PLACES).find(name => q.toLowerCase().startsWith(name))
  return { query: q, state: 'ok', places: key ? PLACES[key] : [], attribution: '© OpenStreetMap contributors' }
})

/** What the reader chose in the settings for the lists of stations of the search: the forecast's points and GHCN daily are on, DWD's measuring stations off */
function chooseLists(chosen: Partial<typeof SEARCH_STATIONS_DEFAULTS>) {
  useSettings().settings.value.searchStations = { ...SEARCH_STATIONS_DEFAULTS, ...chosen }
}

const mounted: Array<{ unmount: () => void }> = []
async function mountPalette() {
  const wrapper = await mountSuspended(AppCommandPalette, { attachTo: document.body })
  mounted.push(wrapper)
  return wrapper
}

afterEach(() => {
  mounted.splice(0).forEach(wrapper => wrapper.unmount())
  clearNuxtData()
  stationQueries.length = 0
  stationNetworks.length = 0
  useSettings().settings.value.searchStations = { ...SEARCH_STATIONS_DEFAULTS }
  searchQueries.length = 0
  idQueries.length = 0
  releaseSearch?.()
  releaseSearch = null
  searchMode = 'answer'
  pendingServed = 0
  idAnswer = 'rows'
  releaseIds?.()
  releaseIds = null
  placeQueries.length = 0
  placesMode = 'answer'
  releasePlaces?.()
  releasePlaces = null
  clearNuxtState('places-search-off')
  failStations = false
  navigateTo.mockClear()
})

describe('the command palette', () => {
  it('has a button that closes it, for a touch screen reader that cannot reach the overlay', async () => {
    const wrapper = await mountPalette()
    const close = wrapper.find('[data-testid="palette-close"]')
    expect(close.attributes('aria-label')).toBe('Close')
    await close.trigger('click')
    expect(wrapper.emitted('done')).toHaveLength(1)
  })

  it('is a combobox that controls a named listbox of grouped, named options', async () => {
    const wrapper = await mountPalette()
    const input = wrapper.find('input[role="combobox"]')
    const list = wrapper.find('[role="listbox"]')
    expect(input.attributes('aria-label')).toBe('Search')
    expect(input.attributes('aria-expanded')).toBe('true')
    expect(input.attributes('aria-autocomplete')).toBe('list')
    expect(input.attributes('aria-controls')).toBe(list.attributes('id'))
    expect(list.attributes('aria-label')).toBe('Results')
    const groups = list.findAll('[role="group"]')
    expect(groups.length).toBeGreaterThan(3)
    for (const group of groups)
      expect(wrapper.find(`[id="${group.attributes('aria-labelledby')}"]`).text()).not.toBe('')
    // the first option is the active one, and the field says so
    const options = list.findAll('[role="option"]')
    expect(options[0]!.attributes('aria-selected')).toBe('true')
    expect(input.attributes('aria-activedescendant')).toBe(options[0]!.attributes('id'))
    expect(options.filter(option => option.attributes('aria-selected') === 'true')).toHaveLength(1)
  })

  it('lists every page with the line that says what it is for', async () => {
    const wrapper = await mountPalette()
    const text = wrapper.find('[role="listbox"]').text()
    for (const label of ['Forecast', 'Explorer', 'Climate stripes', 'History', 'Providers', 'Glossary', 'API', 'Home', 'About', 'Support', 'Settings', 'Legal notice', 'Privacy'])
      expect(text, label).toContain(label)
    expect(text).toContain('See a multi-day forecast for your location.')
    expect(text).toContain('Who runs this site, and how to reach them')
  })

  it('lists the map among the tools, with the line that says what it is for, and opens it', async () => {
    const wrapper = await mountPalette()
    const tools = wrapper.findAll('[role="group"]').find(group => group.text().includes('Climate stripes'))!
    const map = tools.findAll('[role="option"]').find(option => option.text().startsWith('Map'))!
    expect(map.text()).toContain('Pick a station or any point on the map for its forecast, climate stripes and measurements.')
    await map.trigger('click')
    expect(navigateTo).toHaveBeenCalledWith('/map')
  })

  it('finds the stations of three lists by name, each in a group of its own with the provider and network on every result, and opens the map on one', async () => {
    // real timers: Vue ignores a click whose time stamp is earlier than the moment its handler was attached, which a
    // clock that was faked and then restored makes of every click after it
    chooseLists({ measured: true })
    const wrapper = await mountPalette()
    const input = wrapper.find('input[role="combobox"]')
    await input.setValue('berl')
    await vi.waitFor(() => expect(wrapper.text()).toContain('BERLIN-TEMPELHOF'))
    const groups = wrapper.findAll('[role="group"]')
    const heading = (group: DOMWrapper<Element>) => wrapper.find(`[id="${group.attributes('aria-labelledby')}"]`).text()
    const headings = groups.map(heading)
    expect(headings.slice(0, 3)).toEqual(['Stations: DWD forecast', 'Stations: DWD measurements', 'Stations: NOAA GHCN daily'])
    const forecast = groups[0]!.find('[role="option"]')
    expect(forecast.text()).toContain('BERLIN-TEMPELHOF')
    expect(forecast.text()).toContain('DWD · MOSMIX forecast · 10384')
    const measured = groups[1]!.findAll('[role="option"]')
    expect(measured).toHaveLength(2)
    expect(measured[0]!.text()).toContain('DWD · measurements · 00403')
    // a station that has stopped says when
    expect(measured[1]!.text()).toContain('DWD · measurements · 00430 · ended 2019')
    expect(groups[2]!.find('[role="option"]').text()).toContain('NOAA · GHCN daily · GM000000')
    // the forecast's points are the backend's own name search, as ever, the other two the app's server
    expect(stationQueries).toEqual(['berl'])
    expect(stationNetworks).toEqual(['dwd/mosmix'])
    expect(searchQueries).toEqual([{ q: 'berl', limit: '4', lists: 'measured,ghcn' }])
    await forecast.trigger('click')
    expect(navigateTo).toHaveBeenCalledWith('/map?station=10384')
  })

  it('leads a station of DWD\'s measurements and of GHCN daily to the map on their layers', async () => {
    chooseLists({ measured: true })
    const wrapper = await mountPalette()
    await wrapper.find('input[role="combobox"]').setValue('berl')
    await vi.waitFor(() => expect(wrapper.text()).toContain('Berlin-Dahlem'))
    const options = wrapper.findAll('[role="option"]')
    await options.find(option => option.text().includes('Berlin-Dahlem'))!.trigger('click')
    expect(navigateTo).toHaveBeenLastCalledWith('/map?layer=measured&station=00403')
    await options.find(option => option.text().includes('BERLIN-SCHONEFELD'))!.trigger('click')
    expect(navigateTo).toHaveBeenLastCalledWith('/map?layer=ghcn&station=GM000002')
  })

  it('shows three stations of a network and a last option for the others, which opens the map\'s own search on the text', async () => {
    const wrapper = await mountPalette()
    await wrapper.find('input[role="combobox"]').setValue('berl')
    await vi.waitFor(() => expect(wrapper.text()).toContain('BERLIN-SCHONEFELD'))
    const ghcn = wrapper.findAll('[role="group"]').find(group => group.text().includes('GM000000'))!
    const options = ghcn.findAll('[role="option"]')
    // 14 stations: three of them and "11 more", not the four the server sent
    expect(options).toHaveLength(4)
    expect(ghcn.text()).not.toContain('BERLIN-BRANDENBURG')
    expect(options.at(-1)!.text()).toBe('11 more on the map (NOAA GHCN daily)')
    await options.at(-1)!.trigger('click')
    expect(navigateTo).toHaveBeenCalledWith('/map?layer=ghcn&q=berl')
  })

  it('says the number of stations of each network in the live region, and does not count the option that leads on', async () => {
    chooseLists({ measured: true })
    const wrapper = await mountPalette()
    await wrapper.find('input[role="combobox"]').setValue('berl')
    await vi.waitFor(() => expect(wrapper.text()).toContain('BERLIN-TEMPELHOF'))
    const status = wrapper.find('[role="status"]').text()
    expect(status).toContain('Stations: DWD forecast: 1')
    expect(status).toContain('Stations: DWD measurements: 2')
    expect(status).toContain('Stations: NOAA GHCN daily: 3')
  })

  it('asks a network whose list is still being read again after a pause, says so, and then lists its stations', async () => {
    searchMode = 'pending-once'
    const wrapper = await mountPalette()
    await wrapper.find('input[role="combobox"]').setValue('berl')
    await vi.waitFor(() => expect(wrapper.find('[role="status"]').text()).toContain('Still reading a list of stations'))
    expect(wrapper.text()).not.toContain('BERLIN-SCHONEFELD')
    await vi.waitFor(() => expect(wrapper.text()).toContain('BERLIN-SCHONEFELD'), { timeout: 6000 })
    expect(wrapper.find('[role="status"]').text()).not.toContain('Still reading')
    expect(searchQueries).toHaveLength(2)
  })

  it('shows the forecast\'s points as soon as the backend has them, and not behind the server that is still answering for its lists', async () => {
    searchMode = 'slow'
    const wrapper = await mountPalette()
    await wrapper.find('input[role="combobox"]').setValue('berl')
    await vi.waitFor(() => expect(wrapper.text()).toContain('BERLIN-TEMPELHOF'))
    // the server has been asked and has not answered: GHCN daily is not there, and the live region says that more may follow
    expect(searchQueries).toHaveLength(1)
    expect(wrapper.text()).not.toContain('BERLIN-SCHONEFELD')
    expect(wrapper.find('[role="status"]').text()).toContain('Still reading a list of stations')
    releaseSearch!()
    await vi.waitFor(() => expect(wrapper.text()).toContain('BERLIN-SCHONEFELD'))
    expect(wrapper.text()).toContain('BERLIN-TEMPELHOF')
    expect(wrapper.find('[role="status"]').text()).not.toContain('Still reading')
    // one request to each, not a second one for the answer that was shown first
    expect(searchQueries).toHaveLength(1)
    expect(stationQueries).toEqual(['berl'])
  })

  it('ends in the failed state, not in "still reading", when a list is not there after the last attempt', async () => {
    searchMode = 'pending-always'
    vi.useFakeTimers()
    try {
      const wrapper = await mountPalette()
      await wrapper.find('input[role="combobox"]').setValue('berl')
      await vi.advanceTimersByTimeAsync(400)
      // the first answer says it is still being read, and the palette asks again every 3 s, 25 times
      for (let step = 0; step < 30; step++)
        await vi.advanceTimersByTimeAsync(3100)
      vi.useRealTimers()
      await vi.waitFor(() => expect(wrapper.find('[role="status"]').text()).toContain('One list of stations could not be read'))
      expect(wrapper.find('[role="status"]').text()).not.toContain('Still reading')
      expect(searchQueries.length).toBe(26)
    }
    finally {
      vi.useRealTimers()
    }
  })

  it('says that a list of stations could not be read, and leaves the pages to choose from', async () => {
    searchMode = 'fail'
    const wrapper = await mountPalette()
    await wrapper.find('input[role="combobox"]').setValue('berl')
    await vi.waitFor(() => expect(wrapper.find('[role="status"]').text()).toContain('could not be read'))
    // the list of the server is not there, the forecast's points, which the backend answers, are
    const headings = wrapper.findAll('[role="group"]').map(group => wrapper.find(`[id="${group.attributes('aria-labelledby')}"]`).text())
    expect(headings).toContain('Stations: DWD forecast')
    expect(headings).not.toContain('Stations: NOAA GHCN daily')
  })

  it('looks only in the lists the settings choose: the forecast\'s points and GHCN daily by default, DWD\'s measuring stations not', async () => {
    const wrapper = await mountPalette()
    await wrapper.find('input[role="combobox"]').setValue('berl')
    await vi.waitFor(() => expect(wrapper.text()).toContain('BERLIN-SCHONEFELD'))
    const headings = wrapper.findAll('[role="group"]').map(group => wrapper.find(`[id="${group.attributes('aria-labelledby')}"]`).text())
    expect(headings.slice(0, 2)).toEqual(['Stations: DWD forecast', 'Stations: NOAA GHCN daily'])
    expect(headings).not.toContain('Stations: DWD measurements')
    // the server is told which of its lists, and the list of the measuring stations is not one of them
    expect(searchQueries).toEqual([{ q: 'berl', limit: '4', lists: 'ghcn' }])
  })

  it('asks the server for the measuring stations only once they are chosen, and not for a list that is turned off', async () => {
    chooseLists({ forecast: false, ghcn: false, measured: true })
    const wrapper = await mountPalette()
    await wrapper.find('input[role="combobox"]').setValue('berl')
    await vi.waitFor(() => expect(wrapper.text()).toContain('Berlin-Dahlem'))
    expect(searchQueries).toEqual([{ q: 'berl', limit: '4', lists: 'measured' }])
    // the backend is not asked for the forecast's points
    expect(stationQueries).toEqual([])
    const headings = wrapper.findAll('[role="group"]').map(group => wrapper.find(`[id="${group.attributes('aria-labelledby')}"]`).text())
    expect(headings).toContain('Stations: DWD measurements')
    expect(headings).not.toContain('Stations: DWD forecast')
    expect(headings).not.toContain('Stations: NOAA GHCN daily')
  })

  it('asks nothing for a name where every list is turned off, and still offers the search of every network for an id', async () => {
    chooseLists({ forecast: false, ghcn: false, measured: false })
    const wrapper = await mountPalette()
    const input = wrapper.find('input[role="combobox"]')
    await input.setValue('berl')
    await new Promise(resolve => setTimeout(resolve, 600))
    expect(searchQueries).toEqual([])
    expect(stationQueries).toEqual([])
    await input.setValue('10381')
    await vi.waitFor(() => expect(wrapper.findAll('[role="option"]').some(option => option.text().includes('Search all networks for 10381'))).toBe(true))
    await input.trigger('keydown', { key: 'Enter' })
    await vi.waitFor(() => expect(idQueries).toEqual([{ wmo_id: '10381' }]))
    expect(searchQueries).toEqual([])
  })

  it('moves the active option with the arrow keys, round the ends', async () => {
    const wrapper = await mountPalette()
    const input = wrapper.find('input[role="combobox"]')
    const options = () => wrapper.findAll('[role="option"]')
    await input.trigger('keydown', { key: 'ArrowDown' })
    expect(input.attributes('aria-activedescendant')).toBe(options()[1]!.attributes('id'))
    await input.trigger('keydown', { key: 'ArrowUp' })
    await input.trigger('keydown', { key: 'ArrowUp' })
    expect(input.attributes('aria-activedescendant')).toBe(options().at(-1)!.attributes('id'))
  })

  it('filters as one types, says how many it found, and is done on Enter', async () => {
    const wrapper = await mountPalette()
    const input = wrapper.find('input[role="combobox"]')
    await input.setValue('glos')
    const options = wrapper.findAll('[role="option"]')
    expect(options[0]!.text()).toContain('Glossary')
    expect(wrapper.find('[role="status"]').text()).toMatch(/^\d+ results?/)
    await input.trigger('keydown', { key: 'Enter' })
    expect(wrapper.emitted('done')).toHaveLength(1)
  })

  it('changes the theme', async () => {
    const wrapper = await mountPalette()
    const input = wrapper.find('input[role="combobox"]')
    await input.setValue('dark')
    const option = wrapper.findAll('[role="option"]').find(candidate => candidate.text().includes('Dark'))!
    await option.trigger('click')
    expect(useColorMode().preference).toBe('dark')
    useColorMode().preference = 'system'
  })

  it('finds a station by its name from three letters on, asking once the typing stops, the backend for the forecast\'s points and the server for GHCN daily', async () => {
    vi.useFakeTimers()
    try {
      const wrapper = await mountPalette()
      const input = wrapper.find('input[role="combobox"]')
      await input.setValue('be')
      await vi.advanceTimersByTimeAsync(400)
      expect(searchQueries).toEqual([])
      expect(wrapper.find('[role="status"]').text()).toContain('Type three letters or more')
      await input.setValue('ber')
      await input.setValue('berl')
      await vi.advanceTimersByTimeAsync(400)
      vi.useRealTimers()
      await vi.waitFor(() => expect(wrapper.text()).toContain('BERLIN-TEMPELHOF'))
      expect(searchQueries).toEqual([{ q: 'berl', limit: '4', lists: 'ghcn' }])
      expect(stationQueries).toEqual(['berl'])
      expect(wrapper.text()).toContain('DWD · MOSMIX forecast · 10384')
    }
    finally {
      vi.useRealTimers()
    }
  })

  it('says so where nothing matches, and the field then controls no list', async () => {
    const wrapper = await mountPalette()
    const input = wrapper.find('input[role="combobox"]')
    await input.setValue('zzzqqq')
    expect(wrapper.text()).toContain('Nothing found')
    expect(wrapper.find('[role="listbox"]').exists()).toBe(false)
    expect(input.attributes('aria-expanded')).toBe('false')
    expect(input.attributes('aria-controls')).toBeUndefined()
  })
})

// The words of the app, a position and the questions (GH-3790)
describe('the command palette finding the words of the app', () => {
  const groupOf = (wrapper: Awaited<ReturnType<typeof mountPalette>>, label: string) =>
    wrapper.findAll('[role="group"]').find(group => wrapper.find(`[id="${group.attributes('aria-labelledby')}"]`).text() === label)
  const headings = (wrapper: Awaited<ReturnType<typeof mountPalette>>) =>
    wrapper.findAll('[role="group"]').map(group => wrapper.find(`[id="${group.attributes('aria-labelledby')}"]`).text())
  const optionsOf = (group: DOMWrapper<Element> | undefined) => group?.findAll('[role="option"]') ?? []
  // the index of the pages is a chunk that is loaded when the search opens: the results come once it is there
  const typed = async (wrapper: Awaited<ReturnType<typeof mountPalette>>, text: string, until: string) => {
    await wrapper.find('input[role="combobox"]').setValue(text)
    await vi.waitFor(() => expect(wrapper.text()).toContain(until), { timeout: 5000 })
  }

  it('asks for the glossary when the search is opened, and once for the visit', async () => {
    const wrapper = await mountPalette()
    await vi.waitFor(() => expect(glossaryRequests).toBeGreaterThan(0))
    const asked = glossaryRequests
    // the next opening has it already
    const again = await mountPalette()
    await again.find('input[role="combobox"]').setValue('dew point')
    await vi.waitFor(() => expect(again.text()).toContain('Dew point (2 m)'))
    expect(glossaryRequests).toBe(asked)
    // the first open lists the pages and the actions: the words are for a text that is typed
    expect(headings(wrapper)).not.toContain('Glossary')
    expect(headings(wrapper)).not.toContain('Ask the weather')
  })

  it('finds an entry of "How weather is measured" and leads to it at its anchor', async () => {
    const wrapper = await mountPalette()
    await typed(wrapper, 'dew point', 'Humidity and dew point')
    const group = groupOf(wrapper, 'How weather is measured')!
    const option = optionsOf(group)[0]!
    expect(option.text()).toContain('Humidity and dew point')
    await option.trigger('click')
    expect(navigateTo).toHaveBeenCalledWith('/measurement#humidity')
  })

  it('finds the glossary by the label the reader sees, the name and the description, and leads to the entry', async () => {
    const wrapper = await mountPalette()
    await typed(wrapper, 'dew point', 'Dew point (2 m)')
    const option = optionsOf(groupOf(wrapper, 'Glossary'))[0]!
    expect(option.text()).toContain('Dew point (2 m)')
    await option.trigger('click')
    expect(navigateTo).toHaveBeenCalledWith('/glossary#temperature_dew_point_mean_2m')
  })

  it('shows a few results of a group with a last option that opens the page that has them all', async () => {
    const wrapper = await mountPalette()
    await typed(wrapper, 'units', 'Convert units')
    const group = groupOf(wrapper, 'Settings')!
    const options = optionsOf(group)
    // three settings and the way on, not the eighteen rows of the page
    expect(options).toHaveLength(4)
    expect(options.at(-1)!.text()).toMatch(/^\d+ more in Settings/)
    await options.at(-1)!.trigger('click')
    expect(navigateTo).toHaveBeenCalledWith('/settings')
  })

  it('leads a setting to its own anchor', async () => {
    const wrapper = await mountPalette()
    await typed(wrapper, 'plain-language', 'Plain-language labels')
    await optionsOf(groupOf(wrapper, 'Settings'))[0]!.trigger('click')
    expect(navigateTo).toHaveBeenCalledWith('/settings#settings-friendly-labels')
  })

  it('leads the more of the glossary to the glossary with what was typed', async () => {
    const wrapper = await mountPalette()
    await typed(wrapper, 'temperature', 'more in Glossary')
    const options = optionsOf(groupOf(wrapper, 'Glossary'))
    await options.at(-1)!.trigger('click')
    expect(navigateTo).toHaveBeenCalledWith('/glossary?q=temperature')
  })

  it('finds the cards of About and Support among the pages of the project', async () => {
    const wrapper = await mountPalette()
    await typed(wrapper, 'donations', 'Support the project')
    const project = groupOf(wrapper, 'Project')!
    const card = optionsOf(project).find(option => option.text().includes('Support the project') && option.text().includes('donations'))!
    await (card).trigger('click')
    expect(navigateTo).toHaveBeenCalledWith('/support#support-donate')
  })

  it('finds the questions of Ask the weather and opens the question on the home page', async () => {
    const wrapper = await mountPalette()
    await typed(wrapper, 'rain', 'Will it rain')
    const group = groupOf(wrapper, 'Ask the weather')!
    const option = (optionsOf(group))[0]!
    expect(option.text()).toContain('rain')
    await option.trigger('click')
    expect(navigateTo).toHaveBeenCalledWith('/?ask=rain')
  })

  it('shows a position that is typed as a place that leads to the map at that point, before everything else', async () => {
    const wrapper = await mountPalette()
    await wrapper.find('input[role="combobox"]').setValue('52.52, 13.40')
    await vi.waitFor(() => expect(headings(wrapper)).toContain('Place'))
    expect(headings(wrapper)[0]).toBe('Place')
    const option = optionsOf(groupOf(wrapper, 'Place'))
    expect(option).toHaveLength(1)
    expect(option[0]!.text()).toContain('52.5200, 13.4000')
    expect(option[0]!.text()).toContain('Show this point on the map')
    // it is the active one, so Enter takes it
    await wrapper.find('input[role="combobox"]').trigger('keydown', { key: 'Enter' })
    expect(navigateTo).toHaveBeenCalledWith('/map?lat=52.5200&lon=13.4000')
  })

  it('reads the hemisphere letters, and shows no place for a text that is no position', async () => {
    const wrapper = await mountPalette()
    const input = wrapper.find('input[role="combobox"]')
    await input.setValue('52°31\'N 13°24\'E')
    await vi.waitFor(() => expect(headings(wrapper)).toContain('Place'))
    expect(wrapper.text()).toContain('52.5167, 13.4000')
    await input.setValue('glossary')
    await vi.waitFor(() => expect(headings(wrapper)).not.toContain('Place'))
  })

  it('puts a point first, then the stations, then the pages of the tools, then the words of the app', async () => {
    chooseLists({ measured: true })
    const wrapper = await mountPalette()
    // a text that is a position, a forecast and a glossary word at once would be odd: the order is the list of GROUP_ORDER, held here by what a query gives
    await typed(wrapper, 'forecast', 'BERLIN-TEMPELHOF')
    await vi.waitFor(() => expect(headings(wrapper)).toContain('How weather is measured'))
    const order = headings(wrapper)
    expect(order.indexOf('Stations: DWD forecast')).toBeLessThan(order.indexOf('Stations: DWD measurements'))
    expect(order.indexOf('Stations: DWD measurements')).toBeLessThan(order.indexOf('Stations: NOAA GHCN daily'))
    expect(order.indexOf('Stations: NOAA GHCN daily')).toBeLessThan(order.indexOf('Tools'))
    expect(order.indexOf('Tools')).toBeLessThan(order.indexOf('How weather is measured'))
  })

  it('puts a page that its name finds before the words of the app that mention it, whenever the index of the words arrives', async () => {
    const wrapper = await mountPalette()
    await wrapper.find('input[role="combobox"]').setValue('glossary')
    // the page is there at once; the entries that say the word come when the index is there, and after it
    const pageFirst = () => wrapper.findAll('[role="group"]').find(group => group.text().includes('What each parameter measures'))
    expect(pageFirst()).toBeDefined()
    await vi.waitFor(() => expect(headings(wrapper)).toContain('How weather is measured'), { timeout: 5000 })
    const order = headings(wrapper)
    expect(order.indexOf('Reference')).toBeGreaterThan(-1)
    expect(order.indexOf('Reference')).toBeLessThan(order.indexOf('How weather is measured'))
  })

  it('says how many results each group has, in the live region', async () => {
    const wrapper = await mountPalette()
    await typed(wrapper, 'dew point', 'Humidity and dew point')
    await vi.waitFor(() => expect(wrapper.text()).toContain('Dew point (2 m)'))
    const status = wrapper.find('[role="status"]').text()
    expect(status).toMatch(/^\d+ results?\. /)
    expect(status).toMatch(/How weather is measured: \d+/)
    expect(status).toMatch(/Glossary: \d+/)
  })

  it('names every group, so that a screen reader announces its heading', async () => {
    const wrapper = await mountPalette()
    await typed(wrapper, 'temperature', 'Glossary')
    for (const group of wrapper.findAll('[role="group"]'))
      expect(wrapper.find(`[id="${group.attributes('aria-labelledby')}"]`).text(), group.html()).not.toBe('')
  })

  it('keeps the combobox pattern: one active option, which the field names, across the new groups', async () => {
    const wrapper = await mountPalette()
    await typed(wrapper, 'temperature', 'Glossary')
    const input = wrapper.find('input[role="combobox"]')
    const options = wrapper.findAll('[role="option"]')
    expect(options.filter(option => option.attributes('aria-selected') === 'true')).toHaveLength(1)
    expect(input.attributes('aria-activedescendant')).toBe(options[0]!.attributes('id'))
    await input.trigger('keydown', { key: 'ArrowUp' })
    expect(input.attributes('aria-activedescendant')).toBe(options.at(-1)!.attributes('id'))
  })
})

// The ids of WMO and ICAO, asked of every network on request (GH-3790, GH-4286)
describe('the command palette finding a station by its WMO, WIGOS or ICAO id', () => {
  const headings = (wrapper: Awaited<ReturnType<typeof mountPalette>>) =>
    wrapper.findAll('[role="group"]').map(group => wrapper.find(`[id="${group.attributes('aria-labelledby')}"]`).text())
  const searchOption = (wrapper: Awaited<ReturnType<typeof mountPalette>>) =>
    wrapper.findAll('[role="option"]').find(option => option.text().includes('Search all networks for'))

  it('offers the search of all networks for a WMO number, a WIGOS identifier and an ICAO code, and asks nothing before it is chosen', async () => {
    const wrapper = await mountPalette()
    const input = wrapper.find('input[role="combobox"]')
    for (const [typed, shown] of [['10381', '10381'], ['0-20000-0-10381', '0-20000-0-10381'], ['eddh', 'EDDH']]) {
      await input.setValue(typed)
      await vi.waitFor(() => expect(searchOption(wrapper)?.text()).toContain(`Search all networks for ${shown}`))
      expect(searchOption(wrapper)!.text()).toContain('Asks every provider that lists the id; takes a few seconds')
    }
    expect(idQueries).toEqual([])
    // a text that is no id has no such option
    await input.setValue('hamburg')
    await vi.waitFor(() => expect(searchOption(wrapper)).toBeUndefined())
  })

  it('runs it on Enter, keeps the search open and says it is searching, then lists the stations, each with its provider and network, and leads to the map or the Explorer', async () => {
    const wrapper = await mountPalette()
    const input = wrapper.find('input[role="combobox"]')
    await input.setValue('10381')
    await vi.waitFor(() => expect(searchOption(wrapper)).toBeDefined())
    // the option is the first one where no list has the number, and Enter takes it
    expect(wrapper.find('[role="option"][aria-selected="true"]').text()).toContain('Search all networks for 10381')
    await input.trigger('keydown', { key: 'Enter' })
    expect(wrapper.emitted('done')).toBeUndefined()
    await vi.waitFor(() => expect(idQueries).toEqual([{ wmo_id: '10381' }]))
    await vi.waitFor(() => expect(wrapper.find('[role="status"]').text()).toBe('Searching all networks …'))
    expect(searchOption(wrapper)!.text()).toContain('Searching all networks …')
    releaseIds!()
    await vi.waitFor(() => expect(wrapper.text()).toContain('OSLO-BLINDERN'))
    const group = wrapper.findAll('[role="group"]').find(candidate => candidate.text().includes('OSLO-BLINDERN'))!
    expect(wrapper.find(`[id="${group.attributes('aria-labelledby')}"]`).text()).toBe('Stations with 10381')
    const options = group.findAll('[role="option"]')
    // the ones that carry the number asked for come before the equivalent one
    expect(options.map(option => option.text())).toEqual([
      expect.stringContaining('Berlin-Dahlem (FU)'),
      expect.stringContaining('OSLO-BLINDERN'),
      expect.stringContaining('BERLIN-DAHLEM'),
    ])
    expect(options[0]!.text()).toContain('DWD · measurements · 00403')
    expect(options[1]!.text()).toContain('met.no · observation · SN18700 · opens the Explorer')
    expect(options[2]!.text()).toContain('NOAA · GHCN daily · GM000010381')
    // the first of them is the active one, and the search found what it was asked for: the live region counts it
    expect(wrapper.find('[role="option"][aria-selected="true"]').text()).toContain('Berlin-Dahlem (FU)')
    expect(wrapper.find('[role="status"]').text()).toContain('Stations with 10381: 3')
    await options[0]!.trigger('click')
    expect(navigateTo).toHaveBeenLastCalledWith('/map?layer=measured&station=00403')
    await options[2]!.trigger('click')
    expect(navigateTo).toHaveBeenLastCalledWith('/map?layer=ghcn&station=GM000010381')
    await options[1]!.trigger('click')
    expect(navigateTo.mock.lastCall![0]).toBe('/explorer?provider=metno&network=observation&resolution=hourly&dataset=temperature_air&mode=station&stations=SN18700')
  })

  it('does not take a word of four letters for an id: it is offered only where nothing else answers the word', async () => {
    const wrapper = await mountPalette()
    const input = wrapper.find('input[role="combobox"]')
    await input.setValue('wind')
    // the words of the app come when their index has loaded: they answer the word, and no search of every network is offered
    await vi.waitFor(() => expect(headings(wrapper)).toContain('How weather is measured'), { timeout: 5000 })
    expect(searchOption(wrapper)).toBeUndefined()
    // a theme is an answer as well
    await input.setValue('dark')
    await vi.waitFor(() => expect(wrapper.text()).toContain('Dark'))
    expect(searchOption(wrapper)).toBeUndefined()
    // four letters that nothing answers are a code
    await input.setValue('eddh')
    await vi.waitFor(() => expect(searchOption(wrapper)?.text()).toContain('Search all networks for EDDH'))
  })

  it('does not offer four lower-case letters while a list of stations is still being read, which would show the offer and take it back', async () => {
    searchMode = 'pending-always'
    const wrapper = await mountPalette()
    await wrapper.find('input[role="combobox"]').setValue('eddh')
    await vi.waitFor(() => expect(wrapper.find('[role="status"]').text()).toContain('Still reading a list of stations'), { timeout: 5000 })
    expect(searchOption(wrapper)).toBeUndefined()
    // four capital letters are a code whatever is being read
    await wrapper.find('input[role="combobox"]').setValue('EDDH')
    await vi.waitFor(() => expect(searchOption(wrapper)?.text()).toContain('Search all networks for EDDH'))
  })

  it('offers it for four capital letters, which are a code as a word is not, after what the letters find, and Enter does not take it', async () => {
    const wrapper = await mountPalette()
    const input = wrapper.find('input[role="combobox"]')
    await input.setValue('WIND')
    await vi.waitFor(() => expect(headings(wrapper)).toContain('How weather is measured'), { timeout: 5000 })
    const options = wrapper.findAll('[role="option"]')
    expect(options[0]!.text()).not.toContain('Search all networks')
    expect(options.map(option => option.attributes('id')).indexOf(searchOption(wrapper)!.attributes('id'))).toBeGreaterThan(0)
    await input.trigger('keydown', { key: 'Enter' })
    expect(wrapper.emitted('done')).toHaveLength(1)
    expect(idQueries).toEqual([])
  })

  it('asks for a WIGOS identifier and an ICAO code by the parameter of their own', async () => {
    const wrapper = await mountPalette()
    const input = wrapper.find('input[role="combobox"]')
    await input.setValue('0-20000-0-10381')
    await vi.waitFor(() => expect(searchOption(wrapper)).toBeDefined())
    await input.trigger('keydown', { key: 'Enter' })
    await vi.waitFor(() => expect(idQueries).toEqual([{ wigos_id: '0-20000-0-10381' }]))
    await input.setValue('eddh')
    await vi.waitFor(() => expect(searchOption(wrapper)).toBeDefined())
    await input.trigger('keydown', { key: 'Enter' })
    await vi.waitFor(() => expect(idQueries.at(-1)).toEqual({ icao_id: 'EDDH' }))
  })

  it('gives the search up when something else is typed, and shows none of its stations for the next text', async () => {
    const wrapper = await mountPalette()
    const input = wrapper.find('input[role="combobox"]')
    await input.setValue('10381')
    await vi.waitFor(() => expect(searchOption(wrapper)).toBeDefined())
    await input.trigger('keydown', { key: 'Enter' })
    await vi.waitFor(() => expect(idQueries).toHaveLength(1))
    await input.setValue('10382')
    await vi.waitFor(() => expect(searchOption(wrapper)!.text()).toContain('Search all networks for 10382'))
    // the first search is over: its answer arrives and is nobody's
    releaseIds!()
    await new Promise(resolve => setTimeout(resolve, 50))
    expect(wrapper.text()).not.toContain('OSLO-BLINDERN')
    expect(searchOption(wrapper)!.text()).toContain('Asks every provider')
    expect(headings(wrapper)).toContain('All networks')
  })

  it('says where no network has the id, and where the search failed, and offers the search again', async () => {
    idAnswer = 'none'
    const wrapper = await mountPalette()
    const input = wrapper.find('input[role="combobox"]')
    await input.setValue('99999')
    await vi.waitFor(() => expect(searchOption(wrapper)).toBeDefined())
    await input.trigger('keydown', { key: 'Enter' })
    await vi.waitFor(() => expect(idQueries).toHaveLength(1))
    releaseIds!()
    await vi.waitFor(() => expect(searchOption(wrapper)!.text()).toContain('No station of any network has 99999'))
    idAnswer = 'fail'
    await input.trigger('keydown', { key: 'Enter' })
    await vi.waitFor(() => expect(idQueries).toHaveLength(2))
    releaseIds!()
    await vi.waitFor(() => expect(searchOption(wrapper)!.text()).toContain('The search of all networks failed. Press Enter to try again'))
  })

  it('has no search of all networks in its place mode', async () => {
    const wrapper = await mountSuspended(AppCommandPalette, { attachTo: document.body, props: { mode: 'place' } })
    mounted.push(wrapper)
    await wrapper.find('input[role="combobox"]').setValue('10381')
    await new Promise(resolve => setTimeout(resolve, 50))
    expect(wrapper.text()).not.toContain('Search all networks')
  })
})

// In its place mode the palette is the search of the place the home page's questions are about (GH-3518)
describe('the command palette as the search of a place', () => {
  async function mountPlaces() {
    const wrapper = await mountSuspended(AppCommandPalette, { attachTo: document.body, props: { mode: 'place' } })
    mounted.push(wrapper)
    return wrapper
  }

  it('is a combobox named for the place, with nothing to choose until a name is typed', async () => {
    const wrapper = await mountPlaces()
    const input = wrapper.find('input[role="combobox"]')
    expect(input.attributes('aria-label')).toBe('Choose a place')
    expect(input.attributes('placeholder')).toBe('The name of a town or weather station …')
    expect(input.attributes('aria-expanded')).toBe('false')
    expect(wrapper.find('[role="listbox"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('Type the name of a town or weather station.')
    // none of the pages and settings of the search
    expect(wrapper.text()).not.toContain('Glossary')
  })

  it('finds the measuring stations by name from two letters on, leaves out one that stopped reporting, and makes the one chosen the place', async () => {
    vi.useFakeTimers()
    try {
      usePlace().place.value = DEFAULT_PLACE
      const wrapper = await mountPlaces()
      const input = wrapper.find('input[role="combobox"]')
      await input.setValue('a')
      await vi.advanceTimersByTimeAsync(400)
      expect(stationQueries).toEqual([])
      await input.setValue('ar')
      await vi.advanceTimersByTimeAsync(400)
      vi.useRealTimers()
      await vi.waitFor(() => expect(wrapper.findAll('[role="option"]')).toHaveLength(1))
      expect(stationNetworks).toEqual(['dwd/observation'])
      const option = wrapper.find('[role="option"]')
      expect(option.text()).toContain('Arkona')
      expect(option.text()).toContain('Mecklenburg-Vorpommern')
      expect(wrapper.text()).not.toContain('Artern')
      expect(wrapper.find('[role="group"]').text()).toContain('Weather stations')

      await input.trigger('keydown', { key: 'Enter' })
      expect(usePlace().place.value).toMatchObject({ id: '00183', name: 'Arkona', latitude: 54.68, longitude: 13.43 })
      expect(wrapper.emitted('place')![0]![0]).toMatchObject({ id: '00183' })
      expect(wrapper.emitted('done')).toHaveLength(1)
    }
    finally {
      vi.useRealTimers()
      usePlace().place.value = DEFAULT_PLACE
    }
  })

  it('announces the hint, not the failure of the text before, once the text is too short again', async () => {
    failStations = true
    const wrapper = await mountPlaces()
    const input = wrapper.find('input[role="combobox"]')
    await input.setValue('ar')
    await vi.waitFor(() => expect(wrapper.find('[role="status"]').text()).toContain('could not'), { timeout: 5000 })
    await input.setValue('a')
    await vi.waitFor(() => expect(wrapper.find('[role="status"]').text()).toBe('Type the name of a town or weather station.'), { timeout: 5000 })
  })
})

describe('the command palette finding places by name', () => {
  /** The headings of the groups, in the order they are shown */
  const headingsOf = (wrapper: Awaited<ReturnType<typeof mountPalette>>) => wrapper.findAll('[role="group"]').map(group => wrapper.find(`[id="${group.attributes('aria-labelledby')}"]`).text())

  it('shows the places OpenStreetMap has for a name as a group of their own, each with what it is and where it lies, before the stations', async () => {
    const wrapper = await mountPalette()
    await wrapper.find('input[role="combobox"]').setValue('bad tölz')
    await vi.waitFor(() => expect(headingsOf(wrapper)[0]).toBe('Places'))
    const group = wrapper.findAll('[role="group"]')[0]!
    const options = group.findAll('[role="option"]')
    expect(options.map(option => option.text())).toEqual(['Bad TölzTown · Bayern, Deutschland', 'Landkreis Bad Tölz-WolfratshausenCounty · Bayern, Deutschland'])
    // the stations are after them, in the order of the other groups
    await vi.waitFor(() => expect(headingsOf(wrapper)).toContain('Stations: DWD forecast'))
    expect(headingsOf(wrapper).slice(0, 2)).toEqual(['Places', 'Stations: DWD forecast'])
  })

  it('leads a place to the map at its point, which picks the nearest station there, in the way a position that is typed in does', async () => {
    const wrapper = await mountPalette()
    await wrapper.find('input[role="combobox"]').setValue('bad tölz')
    await vi.waitFor(() => expect(wrapper.text()).toContain('Bayern, Deutschland'))
    await wrapper.findAll('[role="option"]').find(option => option.text().startsWith('Bad Tölz'))!.trigger('click')
    expect(navigateTo).toHaveBeenCalledWith('/map?lat=47.7614&lon=11.5583')
  })

  it('shows the credit of OpenStreetMap\'s licence and the name of the service with the places, as links, and none where there are no places', async () => {
    const wrapper = await mountPalette()
    expect(wrapper.find('[data-testid="places-credit"]').exists()).toBe(false)
    await wrapper.find('input[role="combobox"]').setValue('paris')
    await vi.waitFor(() => expect(wrapper.find('[data-testid="places-credit"]').exists()).toBe(true))
    const credit = wrapper.find('[data-testid="places-credit"]')
    expect(credit.text()).toBe('© OpenStreetMap contributors (ODbL) · places via Photon')
    const links = credit.findAll('a')
    expect(links.map(link => [link.text(), link.attributes('href')])).toEqual([
      ['© OpenStreetMap contributors', 'https://www.openstreetmap.org/copyright'],
      ['ODbL', 'https://opendatacommons.org/licenses/odbl/1-0/'],
      ['Photon', 'https://photon.komoot.io'],
    ])
    for (const link of links) {
      expect(link.attributes('target')).toBe('_blank')
      expect(link.attributes('rel')).toBe('noopener noreferrer')
    }
    // the credit is outside the listbox, whose children are options and groups
    expect(wrapper.find('[role="listbox"]').find('[data-testid="places-credit"]').exists()).toBe(false)
    // and gone with the places
    await wrapper.find('input[role="combobox"]').setValue('zzz nothing')
    await vi.waitFor(() => expect(wrapper.find('[data-testid="places-credit"]').exists()).toBe(false))
  })

  it('asks from three characters on, a moment after the last key, once, and in the language of the interface', async () => {
    const wrapper = await mountPalette()
    const input = wrapper.find('input[role="combobox"]')
    await input.setValue('ba')
    await new Promise(resolve => setTimeout(resolve, 600))
    expect(placeQueries).toEqual([])
    // keys in quick succession are one request, for the text they end in
    for (const text of ['bad', 'bad ', 'bad t', 'bad tö', 'bad tölz'])
      await input.setValue(text)
    await new Promise(resolve => setTimeout(resolve, 200))
    expect(placeQueries).toEqual([])
    await vi.waitFor(() => expect(placeQueries).toEqual([{ q: 'bad tölz', lang: 'en' }]))
    await new Promise(resolve => setTimeout(resolve, 200))
    expect(placeQueries).toHaveLength(1)
  })

  it('sends no position, whole or partial, and no text with fewer than three letters, each of which is waited for by itself', async () => {
    const wrapper = await mountPalette()
    const input = wrapper.find('input[role="combobox"]')
    for (const text of ['52.5200, 13.4000', '47.76 N', '47.76 N 11.55', 'N 47.7 E', '47°45′N', '47°46\'N 11°33\'E', 'lat 47.7 lon 11.5', '47,7 N 11,5 O', 'A12', 'B 1', '10381', '0-20000-0-10381']) {
      await input.setValue(text)
      await new Promise(resolve => setTimeout(resolve, 450))
    }
    expect(placeQueries).toEqual([])
    // and a name with a number, an accent or a hyphen in it still goes
    await input.setValue('Saint-Étienne')
    await vi.waitFor(() => expect(placeQueries).toEqual([{ q: 'Saint-Étienne', lang: 'en' }]))
  }, 20_000)

  it('keeps the option the reader is on where the places arrive above it, so that an Enter pressed as they come takes what was highlighted', async () => {
    placesMode = 'slow-first'
    const wrapper = await mountPalette()
    await wrapper.find('input[role="combobox"]').setValue('bad tölz')
    await vi.waitFor(() => expect(wrapper.text()).toContain('BERLIN-TEMPELHOF'))
    const first = wrapper.find('[role="option"][aria-selected="true"]')
    const before = first.text()
    expect(before).toContain('BERLIN-TEMPELHOF')
    // the places are asked for after the stations, and arrive after them: they lead the list
    await vi.waitFor(() => expect(releasePlaces).not.toBeNull())
    releasePlaces!()
    await vi.waitFor(() => expect(wrapper.findAll('[role="group"]')[0]!.text()).toContain('Bad Tölz'))
    const selected = wrapper.findAll('[role="option"]').filter(option => option.attributes('aria-selected') === 'true')
    expect(selected).toHaveLength(1)
    expect(selected[0]!.text()).toBe(before)
    expect(wrapper.find('input[role="combobox"]').attributes('aria-activedescendant')).toBe(selected[0]!.attributes('id'))
    // Enter takes it
    await wrapper.find('input[role="combobox"]').trigger('keydown', { key: 'Enter' })
    expect(navigateTo).toHaveBeenCalledWith('/map?station=10384')
  })

  it('does not show the answer for a text that a newer one has taken the place of, which arrives late', async () => {
    placesMode = 'slow-first'
    const wrapper = await mountPalette()
    const input = wrapper.find('input[role="combobox"]')
    await input.setValue('bad tölz')
    await vi.waitFor(() => expect(placeQueries).toHaveLength(1))
    await input.setValue('paris')
    await vi.waitFor(() => expect(placeQueries).toHaveLength(2))
    await vi.waitFor(() => expect(wrapper.text()).toContain('Île-de-France'))
    // the first answer is let go after the second was shown, and is not
    releasePlaces!()
    await new Promise(resolve => setTimeout(resolve, 100))
    expect(wrapper.text()).toContain('Île-de-France')
    expect(wrapper.text()).not.toContain('Bad Tölz')
  })

  it('says so in the live region where the places could not be searched, and leaves the stations and the pages', async () => {
    placesMode = 'fail'
    const wrapper = await mountPalette()
    await wrapper.find('input[role="combobox"]').setValue('berl')
    await vi.waitFor(() => expect(wrapper.find('[role="status"]').text()).toContain('Places could not be searched just now. Keep typing to try again.'))
    expect(headingsOf(wrapper)).not.toContain('Places')
    expect(headingsOf(wrapper)).toContain('Stations: DWD forecast')
    // the next text asks again, and is answered
    placesMode = 'answer'
    await wrapper.find('input[role="combobox"]').setValue('paris')
    await vi.waitFor(() => expect(headingsOf(wrapper)).toContain('Places'))
    expect(wrapper.find('[role="status"]').text()).not.toContain('Places could not be searched')
  })

  it('shows no group and asks no more where the server says the operator has switched the search of places off', async () => {
    placesMode = 'off'
    const wrapper = await mountPalette()
    const input = wrapper.find('input[role="combobox"]')
    await input.setValue('paris')
    await vi.waitFor(() => expect(placeQueries).toHaveLength(1))
    await new Promise(resolve => setTimeout(resolve, 100))
    expect(headingsOf(wrapper)).not.toContain('Places')
    expect(wrapper.find('[data-testid="places-credit"]').exists()).toBe(false)
    // nothing about it in the live region: it is no failure
    expect(wrapper.find('[role="status"]').text()).not.toContain('Places could not')
    await input.setValue('bad tölz')
    await new Promise(resolve => setTimeout(resolve, 700))
    expect(placeQueries).toHaveLength(1)
  })

  it('counts the places in the live region, with the number of each group, and keeps one active option of the combobox', async () => {
    const wrapper = await mountPalette()
    await wrapper.find('input[role="combobox"]').setValue('paris')
    await vi.waitFor(() => expect(wrapper.find('[role="status"]').text()).toContain('Places: 2'))
    const options = wrapper.findAll('[role="option"]')
    expect(options.filter(option => option.attributes('aria-selected') === 'true')).toHaveLength(1)
    // the places are named by their heading for a screen reader
    const group = wrapper.findAll('[role="group"]')[0]!
    expect(wrapper.find(`[id="${group.attributes('aria-labelledby')}"]`).text()).toBe('Places')
  })

  // the place mode of "Ask the weather" (GH-3791): the places are the towns the questions can be about, before the stations
  describe('in the place mode of "Ask the weather"', () => {
    async function mountPlaceMode() {
      const wrapper = await mountSuspended(AppCommandPalette, { attachTo: document.body, props: { mode: 'place' } })
      mounted.push(wrapper)
      return wrapper
    }

    it('finds towns by their name by the same rules as the search: from three letters, after a pause, never a position', async () => {
      const wrapper = await mountPlaceMode()
      const input = wrapper.find('input[role="combobox"]')
      await input.setValue('pa')
      await new Promise(resolve => setTimeout(resolve, 600))
      expect(placeQueries).toEqual([])
      await input.setValue('47.76 N 11.55')
      await new Promise(resolve => setTimeout(resolve, 600))
      expect(placeQueries).toEqual([])
      await input.setValue('paris')
      await vi.waitFor(() => expect(placeQueries).toEqual([{ q: 'paris', lang: 'en' }]))
      await vi.waitFor(() => expect(wrapper.findAll('[role="group"]')[0]!.text()).toContain('Paris'))
      expect(wrapper.findAll('[role="group"]')[0]!.attributes('aria-labelledby')).toBeTruthy()
      // with the credit the licence asks for
      expect(wrapper.find('[data-testid="places-credit"]').exists()).toBe(true)
    })

    it('hands the town chosen to the page and leaves the place as it was, which the page makes of it with its nearest station', async () => {
      usePlace().place.value = DEFAULT_PLACE
      const wrapper = await mountPlaceMode()
      const input = wrapper.find('input[role="combobox"]')
      await input.setValue('bad tölz')
      await vi.waitFor(() => expect(wrapper.find('[role="option"]').exists()).toBe(true))
      await vi.waitFor(() => expect(wrapper.find('[role="option"]').text()).toContain('Bad Tölz'))
      // a click on it: the option the reader is on stays that one where the places arrive after the stations, as in the search
      await wrapper.find('[role="option"]').trigger('click')
      expect(wrapper.emitted('town')![0]![0]).toMatchObject({ id: 'N240109189', name: 'Bad Tölz', latitude: 47.7614, longitude: 11.5583 })
      expect(wrapper.emitted('place')).toBeUndefined()
      expect(wrapper.emitted('done')).toHaveLength(1)
      // no navigation: the town is the place of the questions, not a point of the map
      expect(navigateTo).not.toHaveBeenCalled()
      expect(usePlace().place.value).toEqual(DEFAULT_PLACE)
    })

    it('says in the live region where the places could not be searched, and keeps the stations', async () => {
      placesMode = 'fail'
      const wrapper = await mountPlaceMode()
      await wrapper.find('input[role="combobox"]').setValue('arkona')
      await vi.waitFor(() => expect(wrapper.find('[role="status"]').text()).toContain('Places could not be searched just now'))
      expect(wrapper.find('[role="option"]').text()).toContain('Arkona')
    })

    it('shows no town and asks no more where the operator has switched the search of places off', async () => {
      placesMode = 'off'
      const wrapper = await mountPlaceMode()
      await wrapper.find('input[role="combobox"]').setValue('paris')
      await vi.waitFor(() => expect(placeQueries).toHaveLength(1))
      await new Promise(resolve => setTimeout(resolve, 100))
      expect(wrapper.find('[data-testid="places-credit"]').exists()).toBe(false)
    })
  })
})
