import type { VueWrapper } from '@vue/test-utils'
import type { H3Event } from 'h3'
import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { getQuery, setResponseStatus } from 'h3'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useNuxtApp } from '#imports'
import MeteogramPage from '~/pages/meteogram.vue'
import { distanceKm } from '~/utils/map-tool'
import { forgetPollenRegions } from '~/utils/pollen-regions'
import { forgetSnowStations } from '~/utils/snow-stations'
import { forgetChoicesOfThisVisit } from '~/utils/uv-pollen'
import { FORECAST_UNITS, forecastValues } from '../../helpers/meteogram-forecast'
import {
  germanDay,
  MOSMIX_AMSTERDAM,
  MOSMIX_BASEL,
  MOSMIX_DRESDEN,
  MOSMIX_PARIS,
  MOSMIX_SALZBURG,
  MOSMIX_STRASBOURG,
  MOSMIX_VENLO,
  OBSERVATION_DRESDEN,
  observationStation,
  POLLEN_STATIONS_ANSWER,
  pollenValues,
  SPRING_LEVELS,
  UV_BERLIN,
  UV_DRESDEN,
  uvValues,
} from '../../helpers/uv-pollen'

// The "UV & pollen" panel on the Forecast page (GH-4501): DWD's UV index and pollen load under the chart of a station in Germany, each its
// own request that the forecast does not wait for and whose failure hides only its own part, as the snow panel's does.

const echarts = vi.hoisted(() => ({ ssr: null as any }))
vi.mock('~/utils/echarts-loader', async () => {
  const { createSsrEcharts } = await import('../../helpers/ssr-echarts')
  echarts.ssr = createSsrEcharts()
  return { loadEcharts: () => echarts.ssr }
})

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })
const metadata = (units: Record<string, string>) => ({ metadata: { parameters: Object.entries(units).map(([name, unit]) => ({ name, unit })) } })

/** An answer of the backend that failed: a 500 with its `detail` */
function serverError(event: H3Event) {
  setResponseStatus(event, 500)
  return { detail: 'Upstream failed' }
}

/** A station of the forecast, somewhat away from the UV place of Dresden */
const HOSTERWITZ = { station_id: '10499', name: 'DRESDEN-HOSTERWITZ', latitude: 51.0, longitude: 13.85, elevation: 120 }

describe('the forecast page\'s UV & pollen panel', () => {
  let wrapper: VueWrapper | undefined
  const endpoints: Array<() => void> = []
  /** What each `/api/stations` request was for, by network, with its query */
  let stationRequests: { network: string, query: Record<string, unknown> }[]
  /** What each `/api/values` request was for: `uv`, `pollen` or `forecast`, with its query */
  let valueRequests: { kind: 'uv' | 'pollen' | 'forecast', params: URLSearchParams }[]
  let uvStationsAnswer: (event: H3Event) => unknown
  let stateAnswer: (event: H3Event) => unknown
  let regionsAnswer: () => unknown
  let uvAnswer: (params: URLSearchParams) => Promise<Response>
  let pollenAnswer: (params: URLSearchParams) => Promise<Response>

  const until = <T>(check: () => T) => vi.waitFor(check, { timeout: 10_000 })
  const panel = () => wrapper!.find('[data-testid="uv-pollen-panel"]')
  const uvPart = () => wrapper!.find('[data-testid="uv-part"]')
  const pollenPart = () => wrapper!.find('[data-testid="pollen-part"]')
  const chips = () => wrapper!.findAll('[data-testid="pollen-chips"] button')
  const pressed = () => chips().filter(chip => chip.attributes('aria-checked') === 'true').map(chip => chip.attributes('data-part'))
  const requestsFor = (kind: 'uv' | 'pollen' | 'forecast') => valueRequests.filter(request => request.kind === kind)
  const stationsFor = (network: string) => stationRequests.filter(request => request.network === network)

  beforeEach(() => {
    forgetSnowStations()
    forgetPollenRegions()
    forgetChoicesOfThisVisit()
    stationRequests = []
    valueRequests = []
    uvStationsAnswer = () => ({ stations: [UV_DRESDEN] })
    stateAnswer = () => ({ stations: [OBSERVATION_DRESDEN] })
    regionsAnswer = () => ({ stations: POLLEN_STATIONS_ANSWER })
    uvAnswer = async params => json({ values: uvValues(params.get('stations')!, [5, 3, 8]) })
    pollenAnswer = async (params) => {
      const ids = params.get('stations')!.split(',')
      // the second part of the state has a load of its own
      return json({ values: pollenValues(ids, SPRING_LEVELS, { 82: { hazel: [0.5, 1, 1.5], alder: [0, 0, 0.5] } }) })
    }
    endpoints.push(registerEndpoint('/api/stations', (event) => {
      const query = getQuery(event)
      const network = String(query.network)
      stationRequests.push({ network, query })
      if (network === 'uvi')
        return uvStationsAnswer(event)
      if (network === 'observation')
        return stateAnswer(event)
      if (network === 'pollen')
        return regionsAnswer()
      return { stations: [] }
    }))
    globalThis.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const params = new URL(String(input), 'http://localhost').searchParams
      const parameters = params.get('parameters') ?? ''
      if (parameters.startsWith('daily/data/uv_index_max')) {
        valueRequests.push({ kind: 'uv', params })
        return uvAnswer(params)
      }
      if (parameters.startsWith('daily/data/pollen_load_')) {
        valueRequests.push({ kind: 'pollen', params })
        return pollenAnswer(params)
      }
      valueRequests.push({ kind: 'forecast', params })
      return json({ values: forecastValues({ hours: 23 }).map(value => ({ ...value, dataset: 'large' })), ...metadata(FORECAST_UNITS) })
    })
  })

  const setLanguage = (code: string) => useNuxtApp().$i18n.setLocale(code as 'en')

  afterEach(async () => {
    wrapper?.unmount()
    wrapper = undefined
    // the language is the app's, which the next test finds as this one left it
    await setLanguage('en')
    endpoints.splice(0).forEach(dispose => dispose())
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
    document.body.innerHTML = ''
  })

  async function pick(station: { station_id: string, name: string, latitude: number, longitude: number, elevation: number }) {
    wrapper ??= await mountSuspended(MeteogramPage, { attachTo: document.body })
    const asked = requestsFor('forecast').length
    ;(wrapper.vm as any).selectedStation = station
    await until(() => expect(requestsFor('forecast').length).toBeGreaterThan(asked))
  }

  it('shows the UV index of the nearest place with its name and distance, and the WHO class of each day in words', async () => {
    await pick(HOSTERWITZ)
    await until(() => expect(uvPart().exists()).toBe(true))
    const km = Math.round(distanceKm(HOSTERWITZ, UV_DRESDEN))
    expect(uvPart().find('h4').text()).toBe(`UV index for Dresden (${km} km)`)
    // the place was asked for as the nearest to the station's position, and its values by its id
    expect(stationsFor('uvi')[0]!.query).toMatchObject({ parameters: 'daily/data', latitude: '51', longitude: '13.85', rank: '1' })
    expect(requestsFor('uv')[0]!.params.get('stations')).toBe('dresden')
    expect(requestsFor('uv')[0]!.params.get('parameters')).toBe('daily/data/uv_index_max')
    const days = uvPart().findAll('[data-testid="uv-day"]')
    expect(days).toHaveLength(3)
    expect(days.map(day => day.find('[data-testid="uv-index"]').text())).toEqual(['UV index 5', 'UV index 3', 'UV index 8'])
    expect(days.map(day => day.find('[data-testid="uv-class"]').text())).toEqual(['Moderate', 'Moderate', 'Very high'])
    expect(days[0]!.text()).toContain('Today')
    expect(days[1]!.text()).toContain('Tomorrow')
    expect(uvPart().text()).toContain('UV index forecast from DWD.')
  })

  it('shows no UV where the nearest place is farther than 100 km, and the pollen all the same', async () => {
    // Berlin is some 160 km from Dresden
    uvStationsAnswer = () => ({ stations: [UV_BERLIN] })
    await pick(HOSTERWITZ)
    await until(() => expect(pollenPart().exists()).toBe(true))
    expect(uvPart().exists()).toBe(false)
    expect(requestsFor('uv')).toEqual([])
  })

  it('shows chips for the part-regions of the state of the nearest observation station, the first one chosen, and the grid of its eight types by three days', async () => {
    await pick(HOSTERWITZ)
    await until(() => expect(pollenPart().exists()).toBe(true))
    expect(stationsFor('observation')[0]!.query).toMatchObject({ parameters: 'daily/climate_summary', rank: '1', latitude: '51', longitude: '13.85' })
    // the state and the parts in the reader's language (GH-4508), the choice by DWD's ids
    expect(pollenPart().find('h4').text()).toBe('Pollen load for Saxony')
    expect(chips().map(chip => chip.text())).toEqual(['Lowlands of Saxony', 'Uplands of Saxony'])
    expect(pressed()).toEqual(['81'])
    // one request for both parts of the state, in the eight types
    expect(requestsFor('pollen')).toHaveLength(1)
    expect(requestsFor('pollen')[0]!.params.get('stations')).toBe('81,82')
    expect(requestsFor('pollen')[0]!.params.get('parameters')!.split(',')).toHaveLength(8)
    const rows = pollenPart().findAll('[data-testid="pollen-row"]')
    expect(rows.map(row => row.find('th').text())).toEqual(['Hazel', 'Alder', 'Ash', 'Birch', 'Grass', 'Rye', 'Mugwort', 'Ragweed'])
    // hazel: 2, 2.5, 3 for the first part; ash: 0, 0.5, 0.5
    expect(rows[0]!.findAll('[data-testid="pollen-cell"]').map(cell => cell.text())).toEqual(['Medium', 'Medium to high', 'High'])
    expect(rows[2]!.findAll('[data-testid="pollen-cell"]').map(cell => cell.text())).toEqual(['None', 'None to low', 'None to low'])
    expect(pollenPart().text()).toContain('Pollen load forecast from DWD.')
  })

  it('shows the grid of another part when its chip is chosen, and remembers the choice for the state', async () => {
    await pick(HOSTERWITZ)
    await until(() => expect(chips()).toHaveLength(2))
    await chips()[1]!.trigger('click')
    expect(pressed()).toEqual(['82'])
    // hazel of the second part: 0.5, 1, 1.5
    expect(pollenPart().findAll('[data-testid="pollen-row"]')[0]!.findAll('[data-testid="pollen-cell"]').map(cell => cell.text())).toEqual(['None to low', 'Low', 'Low to medium'])
    // no second request for it
    expect(requestsFor('pollen')).toHaveLength(1)
    expect(JSON.parse(localStorage.getItem('wd-pollen-part')!)).toEqual({ Sachsen: '82' })
    // the next visit to the state starts at the part that was chosen
    wrapper!.unmount()
    wrapper = undefined
    forgetPollenRegions()
    // the storage is what remembers it for a visit that is not this one
    forgetChoicesOfThisVisit()
    await pick(HOSTERWITZ)
    await until(() => expect(chips()).toHaveLength(2))
    expect(pressed()).toEqual(['82'])
  })

  it('remembers the choice of each state on its own', async () => {
    localStorage.setItem('wd-pollen-part', JSON.stringify({ Bayern: '124' }))
    await pick(HOSTERWITZ)
    await until(() => expect(chips()).toHaveLength(2))
    // Bayern's choice is not Sachsen's
    expect(pressed()).toEqual(['81'])
    await chips()[1]!.trigger('click')
    expect(JSON.parse(localStorage.getItem('wd-pollen-part')!)).toEqual({ Bayern: '124', Sachsen: '82' })
  })

  describe('in the reader\'s language (GH-4508)', () => {
    const chipNames = () => chips().map(chip => chip.text())
    const describedBy = (chip: ReturnType<typeof chips>[number]) => (chip.attributes('aria-describedby') ?? '').split(' ').map(id => document.getElementById(id)?.textContent)

    it('writes the state and the parts in English, and keeps DWD\'s name on each chip as its tooltip and its description', async () => {
      await pick(HOSTERWITZ)
      await until(() => expect(chips()).toHaveLength(2))
      expect(pollenPart().find('h4').text()).toBe('Pollen load for Saxony')
      expect(wrapper!.find('[data-testid="pollen-chips"]').attributes('aria-label')).toBe('Region (Saxony)')
      expect(chipNames()).toEqual(['Lowlands of Saxony', 'Uplands of Saxony'])
      // DWD's full German name, to match with its own pages, where a sighted reader hovers and a screen reader asks for the description
      expect(chips().map(chip => chip.attributes('title'))).toEqual(['DWD\'s name: Sachsen: Tiefland Sachsen', 'DWD\'s name: Sachsen: Mittelgebirge Sachsen'])
      expect(chips().map(describedBy)).toEqual([['DWD\'s name: Sachsen: Tiefland Sachsen'], ['DWD\'s name: Sachsen: Mittelgebirge Sachsen']])
      expect(pollenPart().find('caption').text()).toBe('Pollen load forecast: Lowlands of Saxony')
      // the German is nowhere else on the panel, the names of the chips are the words the reader chose
      expect(pollenPart().find('[data-testid="pollen-chips"]').text()).not.toContain('Sachsen')
      expect(pollenPart().find('h4').text()).not.toContain('Sachsen')
    })

    it('shows DWD\'s names unchanged, with no second name beside them, in German', async () => {
      await setLanguage('de')
      await pick(HOSTERWITZ)
      await until(() => expect(chips()).toHaveLength(2))
      expect(pollenPart().find('h4').text()).toBe('Pollenbelastung für Sachsen')
      expect(chipNames()).toEqual(['Tiefland Sachsen', 'Mittelgebirge Sachsen'])
      expect(chips().map(chip => chip.attributes('title'))).toEqual([undefined, undefined])
      expect(chips().map(chip => chip.attributes('aria-describedby'))).toEqual([undefined, undefined])
      expect(pollenPart().findAll('[data-testid="pollen-dwd-name"]')).toHaveLength(0)
    })

    it('keeps the choice made in one language when the language changes: it is the part\'s id of DWD\'s state that is stored', async () => {
      await pick(HOSTERWITZ)
      await until(() => expect(chips()).toHaveLength(2))
      await chips()[1]!.trigger('click')
      expect(JSON.parse(localStorage.getItem('wd-pollen-part')!)).toEqual({ Sachsen: '82' })
      // the names follow the language at once, with the same chip chosen
      await setLanguage('fr')
      await until(() => expect(chipNames()).toEqual(['Plaine de Saxe', 'Moyennes montagnes de Saxe']))
      expect(pressed()).toEqual(['82'])
      expect(pollenPart().find('h4').text()).toBe('Charge pollinique\u00A0: Saxe')
      expect(chips()[1]!.attributes('title')).toBe('Nom du DWD\u00A0: Sachsen: Mittelgebirge Sachsen')
      // a choice made now is stored under DWD's name of the state, as before, never under the words shown
      await chips()[0]!.trigger('click')
      expect(JSON.parse(localStorage.getItem('wd-pollen-part')!)).toEqual({ Sachsen: '81' })
    })

    it('starts at the part that a visit in another language stored', async () => {
      localStorage.setItem('wd-pollen-part', JSON.stringify({ Sachsen: '82' }))
      await setLanguage('pl')
      await pick(HOSTERWITZ)
      await until(() => expect(chips()).toHaveLength(2))
      expect(pressed()).toEqual(['82'])
      expect(chipNames()).toEqual(['Nizina Saksonii', 'Średniogórze Saksonii'])
    })

    it('shows DWD\'s name for a region that DWD adds, and for a state that is none of the sixteen', async () => {
      // the pollen regions of the answer have a new part, and the nearest observation station is in a state of no table
      regionsAnswer = () => ({
        stations: [
          ...POLLEN_STATIONS_ANSWER,
          { ...POLLEN_STATIONS_ANSWER[0]!, station_id: '130', name: 'Atlantis: Neuland Atlantis', region: 'Atlantis' },
          { ...POLLEN_STATIONS_ANSWER[0]!, station_id: '131', name: 'Atlantis: Hochland', region: 'Atlantis' },
        ],
      })
      stateAnswer = () => ({ stations: [observationStation('00001', 'X', 'Atlantis', 51.1278, 13.7543)] })
      await pick(HOSTERWITZ)
      await until(() => expect(chips()).toHaveLength(2))
      expect(pollenPart().find('h4').text()).toBe('Pollen load for Atlantis')
      expect(chipNames()).toEqual(['Neuland Atlantis', 'Hochland'])
    })
  })

  it('works with no storage: the first part is chosen, a choice holds for the visit, and nothing fails', async () => {
    const refusing = {
      getItem: () => {
        throw new DOMException('denied', 'SecurityError')
      },
      setItem: () => {
        throw new DOMException('quota', 'QuotaExceededError')
      },
    }
    vi.stubGlobal('localStorage', refusing)
    await pick(HOSTERWITZ)
    await until(() => expect(chips()).toHaveLength(2))
    expect(pressed()).toEqual(['81'])
    await chips()[1]!.trigger('click')
    expect(pressed()).toEqual(['82'])
    expect(uvPart().exists()).toBe(true)
    // another station in the state: the answer comes again, and the choice is still the reader's, which the storage cannot hold
    await pick(MOSMIX_DRESDEN)
    await until(() => expect(requestsFor('pollen')).toHaveLength(2))
    await until(() => expect(chips()).toHaveLength(2))
    expect(pressed()).toEqual(['82'])
  })

  it('chooses with the arrow keys, Home and End, as a radio group does, and has one stop of Tab', async () => {
    await pick(HOSTERWITZ)
    await until(() => expect(chips()).toHaveLength(2))
    expect(wrapper!.find('[data-testid="pollen-chips"]').attributes('role')).toBe('radiogroup')
    expect(chips().map(chip => chip.attributes('role'))).toEqual(['radio', 'radio'])
    expect(chips().map(chip => chip.attributes('tabindex'))).toEqual(['0', '-1'])
    await chips()[0]!.trigger('keydown', { key: 'ArrowRight' })
    expect(pressed()).toEqual(['82'])
    expect(chips().map(chip => chip.attributes('tabindex'))).toEqual(['-1', '0'])
    // round the end
    await chips()[1]!.trigger('keydown', { key: 'ArrowRight' })
    expect(pressed()).toEqual(['81'])
    await chips()[0]!.trigger('keydown', { key: 'End' })
    expect(pressed()).toEqual(['82'])
    await chips()[1]!.trigger('keydown', { key: 'Home' })
    expect(pressed()).toEqual(['81'])
    expect(JSON.parse(localStorage.getItem('wd-pollen-part')!)).toEqual({ Sachsen: '81' })
  })

  it('shows the one line that no pollen load is expected, in place of the grid, where every level is 0', async () => {
    pollenAnswer = async params => json({ values: pollenValues(params.get('stations')!.split(','), {}) })
    await pick(HOSTERWITZ)
    await until(() => expect(pollenPart().exists()).toBe(true))
    expect(pollenPart().find('[data-testid="pollen-out-of-season"]').text()).toBe('No pollen load is expected for these days.')
    expect(pollenPart().find('table').exists()).toBe(false)
    expect(pollenPart().find('[data-testid="pollen-no-forecast"]').exists()).toBe(false)
    // the chips stay: the other part may have a load
    expect(chips()).toHaveLength(2)
  })

  it('shows the grid, with dashes, where some levels are 0 and others have no value: a missing value is no 0', async () => {
    pollenAnswer = async params => json({ values: pollenValues(params.get('stations')!.split(','), { hazel: [0, null, 0] }) })
    await pick(HOSTERWITZ)
    await until(() => expect(pollenPart().exists()).toBe(true))
    expect(pollenPart().find('[data-testid="pollen-out-of-season"]').exists()).toBe(false)
    expect(pollenPart().find('table').exists()).toBe(true)
    expect(pollenPart().findAll('[data-testid="pollen-row"]')[0]!.findAll('[data-testid="pollen-cell"]')[1]!.text()).toBe('–no value')
  })

  it('says that DWD gives nothing, and not that no load is expected, where no level has a value', async () => {
    pollenAnswer = async params => json({ values: pollenValues(params.get('stations')!.split(','), Object.fromEntries(['hazel', 'alder', 'ash', 'birch', 'grass', 'rye', 'mugwort', 'ragweed'].map(type => [type, [null, null, null]]))) })
    await pick(HOSTERWITZ)
    await until(() => expect(pollenPart().exists()).toBe(true))
    expect(pollenPart().find('[data-testid="pollen-no-forecast"]').text()).toBe('DWD gives no pollen forecast for this region right now.')
    expect(pollenPart().find('[data-testid="pollen-out-of-season"]').exists()).toBe(false)
    expect(pollenPart().find('table').exists()).toBe(false)
  })

  it('says that DWD gives nothing for a part that has no row while its sibling has them, never that no load is expected', async () => {
    // the answer has the first part only
    pollenAnswer = async params => json({ values: pollenValues(['81'], SPRING_LEVELS).filter(() => params.get('stations')!.includes('81')) })
    await pick(HOSTERWITZ)
    await until(() => expect(chips()).toHaveLength(2))
    expect(pollenPart().find('table').exists()).toBe(true)
    await chips()[1]!.trigger('click')
    expect(pollenPart().find('[data-testid="pollen-no-forecast"]').exists()).toBe(true)
    expect(pollenPart().find('[data-testid="pollen-out-of-season"]').exists()).toBe(false)
    expect(pollenPart().find('table').exists()).toBe(false)
  })

  it('shows a dash for a level that has no value, with its words for a screen reader, among levels that have', async () => {
    pollenAnswer = async params => json({ values: pollenValues(params.get('stations')!.split(','), { ...SPRING_LEVELS, birch: [null, 1, 1] }) })
    await pick(HOSTERWITZ)
    await until(() => expect(pollenPart().find('table').exists()).toBe(true))
    const birch = pollenPart().findAll('[data-testid="pollen-row"]')[3]!.findAll('[data-testid="pollen-cell"]')
    expect(birch[0]!.text()).toBe('–no value')
    expect(birch[0]!.find('.sr-only').text()).toBe('no value')
    expect(birch[1]!.text()).toBe('Low')
  })

  describe('a part that fails leaves the other', () => {
    it.each([
      ['a 500 for the place', () => {
        uvStationsAnswer = serverError
      }],
      ['a 502 for the values', () => { uvAnswer = async () => json({ detail: 'DWD could not be reached' }, 502) }],
      ['a page of HTML', () => { uvAnswer = async () => new Response('<html>Bad gateway</html>', { status: 200, headers: { 'content-type': 'text/html' } }) }],
      ['a request that fails', () => { uvAnswer = async () => Promise.reject(new TypeError('Failed to fetch')) }],
      ['a file with no day', () => { uvAnswer = async () => json({ values: [] }) }],
    ])('has the pollen where the UV request is %s', async (_name, fail) => {
      fail()
      await pick(HOSTERWITZ)
      await until(() => expect(pollenPart().exists()).toBe(true))
      expect(uvPart().exists()).toBe(false)
      expect(chips()).toHaveLength(2)
      // the forecast is not the panel's to break
      expect((wrapper!.vm as any).error).toBeNull()
      expect(wrapper!.find('[role="alert"]').exists()).toBe(false)
    })

    it.each([
      ['a 500 for the state', () => {
        stateAnswer = serverError
      }],
      ['a state that has no region', () => { stateAnswer = () => ({ stations: [observationStation('00001', 'X', 'Österreich', 51.1278, 13.7543)] }) }],
      ['a 502 for the values', () => { pollenAnswer = async () => json({ detail: 'DWD could not be reached' }, 502) }],
      ['a page of HTML', () => { pollenAnswer = async () => new Response('<html>Bad gateway</html>', { status: 200, headers: { 'content-type': 'text/html' } }) }],
      ['a request that fails', () => { pollenAnswer = async () => Promise.reject(new TypeError('Failed to fetch')) }],
    ])('has the UV where the pollen request is %s', async (_name, fail) => {
      fail()
      await pick(HOSTERWITZ)
      await until(() => expect(uvPart().exists()).toBe(true))
      // the pollen request has run its course: the answer of the failed one has been through the page
      await flushPromises()
      await until(() => expect(stationsFor('observation').length).toBeGreaterThan(0))
      expect(pollenPart().exists()).toBe(false)
      expect((wrapper!.vm as any).error).toBeNull()
      expect(wrapper!.find('[role="alert"]').exists()).toBe(false)
    })

    it('has no panel at all where both fail, and the forecast stands', async () => {
      uvAnswer = async () => json({ detail: 'down' }, 500)
      pollenAnswer = async () => json({ detail: 'down' }, 500)
      await pick(HOSTERWITZ)
      await until(() => expect(requestsFor('uv')).toHaveLength(1))
      await until(() => expect(requestsFor('pollen')).toHaveLength(1))
      await flushPromises()
      expect(panel().exists()).toBe(false)
      expect((wrapper!.vm as any).error).toBeNull()
      await until(() => expect(echarts.ssr.option().series.map((series: { id: string }) => series.id)).toContain('temp'))
    })
  })

  describe('outside Germany', () => {
    it('shows no panel and asks for nothing at a station west of the box of DWD\'s warnings', async () => {
      await pick(MOSMIX_PARIS)
      await flushPromises()
      expect(panel().exists()).toBe(false)
      expect(stationsFor('uvi')).toEqual([])
      expect(stationsFor('observation')).toEqual([])
      expect(stationsFor('pollen')).toEqual([])
      expect(requestsFor('uv')).toEqual([])
      expect(requestsFor('pollen')).toEqual([])
    })

    // stations of other countries that the box of DWD's warnings holds, and that have a German station and a place of the UV index in reach: the
    // backend would answer them a state and a place, and the country is what keeps them out
    it.each([
      ['Strasbourg-Entzheim, 18 km from Kehl and 60 km from Freiburg', MOSMIX_STRASBOURG],
      ['Salzburg, 8 km from Piding in Bayern', MOSMIX_SALZBURG],
      ['Basel', MOSMIX_BASEL],
      ['Venlo', MOSMIX_VENLO],
      ['Amsterdam', MOSMIX_AMSTERDAM],
    ])('shows no panel and asks for nothing at %s', async (_name, station) => {
      stateAnswer = () => ({ stations: [observationStation('03402', 'Kehl-Odelshofen', 'Baden-Württemberg', 48.57, 7.81)] })
      uvStationsAnswer = () => ({ stations: [UV_DRESDEN] })
      await pick(station)
      await flushPromises()
      expect(panel().exists()).toBe(false)
      expect(stationsFor('uvi')).toEqual([])
      expect(stationsFor('observation')).toEqual([])
      expect(stationsFor('pollen')).toEqual([])
      expect(requestsFor('uv')).toEqual([])
      expect(requestsFor('pollen')).toEqual([])
    })

    it('takes the panel away on a change from a station in Germany to one outside it', async () => {
      await pick(HOSTERWITZ)
      await until(() => expect(panel().exists()).toBe(true))
      await pick(MOSMIX_PARIS)
      await until(() => expect(panel().exists()).toBe(false))
    })
  })

  it('does not hold the forecast back for either request: the chart is drawn while both are still under way', async () => {
    let releaseUv!: () => void
    let releasePollen!: () => void
    uvAnswer = params => new Promise<Response>((resolve) => {
      releaseUv = () => resolve(json({ values: uvValues(params.get('stations')!, [4, 4, 4]) }))
    })
    pollenAnswer = params => new Promise<Response>((resolve) => {
      releasePollen = () => resolve(json({ values: pollenValues(params.get('stations')!.split(','), SPRING_LEVELS) }))
    })
    await pick(HOSTERWITZ)
    await until(() => expect(echarts.ssr.option().series.map((series: { id: string }) => series.id)).toContain('temp'))
    await until(() => expect(requestsFor('uv')).toHaveLength(1))
    await until(() => expect(requestsFor('pollen')).toHaveLength(1))
    expect(panel().exists()).toBe(false)
    // the UV comes first, and is shown without the pollen
    releaseUv()
    await until(() => expect(uvPart().exists()).toBe(true))
    expect(pollenPart().exists()).toBe(false)
    releasePollen()
    await until(() => expect(pollenPart().exists()).toBe(true))
  })

  it('does not show the UV or the pollen of a station that was left while they were on the way', async () => {
    let releaseUv!: () => void
    let releasePollen!: () => void
    uvAnswer = params => new Promise<Response>((resolve) => {
      releaseUv = () => resolve(json({ values: uvValues(params.get('stations')!, [4, 4, 4]) }))
    })
    pollenAnswer = params => new Promise<Response>((resolve) => {
      releasePollen = () => resolve(json({ values: pollenValues(params.get('stations')!.split(','), SPRING_LEVELS) }))
    })
    await pick(HOSTERWITZ)
    await until(() => expect(requestsFor('uv')).toHaveLength(1))
    await until(() => expect(requestsFor('pollen')).toHaveLength(1))
    // another station, where nothing is to be had (Paris asks for nothing)
    await pick(MOSMIX_PARIS)
    releaseUv()
    releasePollen()
    await flushPromises()
    await flushPromises()
    expect(panel().exists()).toBe(false)
  })

  it('asks for the list of the pollen regions once, for as many stations as are shown', async () => {
    await pick(HOSTERWITZ)
    await until(() => expect(pollenPart().exists()).toBe(true))
    await pick(MOSMIX_DRESDEN)
    await until(() => expect(requestsFor('pollen')).toHaveLength(2))
    expect(stationsFor('pollen')).toHaveLength(1)
  })

  it('does not ask again for a change of the run, which is not the station', async () => {
    await pick(HOSTERWITZ)
    await until(() => expect(pollenPart().exists()).toBe(true))
    ;(wrapper!.vm as any).selectedIssue = '2026-10-01T09:00:00'
    await until(() => expect(requestsFor('forecast')).toHaveLength(2))
    await flushPromises()
    expect(requestsFor('uv')).toHaveLength(1)
    expect(requestsFor('pollen')).toHaveLength(1)
    expect(panel().exists()).toBe(true)
  })

  it('labels the days of a file written yesterday by what they are today: yesterday is not shown', async () => {
    uvAnswer = async params => json({ values: uvValues(params.get('stations')!, [6, 5, 4], -1) })
    await pick(HOSTERWITZ)
    await until(() => expect(uvPart().exists()).toBe(true))
    const days = uvPart().findAll('[data-testid="uv-day"]')
    expect(days.map(day => day.find('[data-testid="uv-index"]').text())).toEqual(['UV index 5', 'UV index 4'])
    expect(days[0]!.text()).toContain('Today')
    expect(days[0]!.text()).not.toContain(germanDay(-1).slice(8))
  })
})
