import type { VueWrapper } from '@vue/test-utils'
import type { H3Event } from 'h3'
import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { getQuery, setResponseStatus } from 'h3'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import MeteogramPage from '~/pages/meteogram.vue'
import { forgetSnowStations } from '~/utils/snow-stations'
import { FORECAST_UNITS, forecastValues, SNOW_UNITS, snowForecastValues } from '../../helpers/meteogram-forecast'

// The snow panel on the Forecast page (GH-4091): the page asks which stations have a snow forecast once, then asks for the snow of
// those, with a request of its own that the forecast does not wait for and whose failure it does not show.

const echarts = vi.hoisted(() => ({ ssr: null as any }))
vi.mock('~/utils/echarts-loader', async () => {
  const { createSsrEcharts } = await import('../../helpers/ssr-echarts')
  echarts.ssr = createSsrEcharts()
  return { loadEcharts: () => echarts.ssr }
})

const ZUGSPITZPLATT = { station_id: 'Z914', name: 'ZUGSPITZPLATT', latitude: 47.4, longitude: 11.0, elevation: 2420 }
const BERLIN = { station_id: '10384', name: 'BERLIN-TEMPELHOF', latitude: 52.47, longitude: 13.4, elevation: 49 }

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })
const metadata = (units: Record<string, string>) => ({ metadata: { parameters: Object.entries(units).map(([name, unit]) => ({ name, unit })) } })

describe('the forecast page\'s snow panel', () => {
  let wrapper: VueWrapper | undefined
  const endpoints: Array<() => void> = []
  /** The requests of `/api/stations` for the snow stations, counted at the endpoint */
  const stationRequests = { snow: 0 }
  let snowStationsAnswer: (event: H3Event) => unknown
  /** What each `/api/values` request was for, in order: `snow` or `forecast`, with its query */
  let requests: { kind: 'snow' | 'forecast', params: URLSearchParams }[]
  let snowAnswer: (params: URLSearchParams) => Promise<Response>

  // what a test waits for is a state of the page, not a number of milliseconds: it is polled until it holds, and only the test's own
  // time-out (15 s, `vitest.config.ts`) ends the wait, where `vi.waitFor`'s own second ends it on a loaded machine before the page is there
  const until = <T>(check: () => T) => vi.waitFor(check, { timeout: 10_000 })
  /** The snow request is answered, with none or with the snow (`null` is a request under way): the page can be read for what it shows of it */
  const snowAnswered = () => until(() => expect((wrapper!.vm as any).snowValues).not.toBeNull())
  const toggles = () => wrapper!.findAll('button[data-panel]').map(button => button.attributes('data-panel'))
  const drawnIds = () => echarts.ssr.option().series.map((series: { id: string }) => series.id) as string[]

  beforeEach(() => {
    forgetSnowStations()
    stationRequests.snow = 0
    requests = []
    snowStationsAnswer = () => ({ stations: [ZUGSPITZPLATT] })
    snowAnswer = async () => json({ values: snowForecastValues({ hours: 23, offGrid: true }), ...metadata(SNOW_UNITS) })
    endpoints.push(registerEndpoint('/api/stations', (event) => {
      if (getQuery(event).parameters === 'hourly/snow') {
        stationRequests.snow++
        return snowStationsAnswer(event)
      }
      return { stations: [] }
    }))
    globalThis.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const params = new URL(String(input), 'http://localhost').searchParams
      if (params.get('parameters')?.startsWith('hourly/snow/')) {
        requests.push({ kind: 'snow', params })
        return snowAnswer(params)
      }
      requests.push({ kind: 'forecast', params })
      return json({ values: forecastValues({ hours: 23 }).map(value => ({ ...value, dataset: 'large' })), ...metadata(FORECAST_UNITS) })
    })
  })

  afterEach(() => {
    wrapper?.unmount()
    wrapper = undefined
    endpoints.splice(0).forEach(dispose => dispose())
    vi.restoreAllMocks()
    document.body.innerHTML = ''
  })

  async function pick(station: typeof ZUGSPITZPLATT) {
    wrapper ??= await mountSuspended(MeteogramPage, { attachTo: document.body })
    const asked = requests.filter(request => request.kind === 'forecast').length
    ;(wrapper.vm as any).selectedStation = station
    // the forecast of this station is asked for: one more than before, which a station picked after another needs
    await until(() => expect(requests.filter(request => request.kind === 'forecast').length).toBeGreaterThan(asked))
  }

  it('shows the snow panel for a station that has a snow forecast, from a request of its own for the dataset snow', async () => {
    await pick(ZUGSPITZPLATT)
    await until(() => expect(toggles()).toContain('snow'))
    const snow = requests.find(request => request.kind === 'snow')!
    expect(snow.params.get('stations')).toBe('Z914')
    expect(snow.params.get('parameters')).toBe('hourly/snow/snow_depth_new_last_3h,hourly/snow/snow_depth,hourly/snow/probability_snow_depth_new_gt_10cm_last_24h')
    // the forecast's request is the one it was, and carries no snow
    expect(requests.find(request => request.kind === 'forecast')!.params.get('parameters')).not.toContain('snow')
    await until(() => expect(drawnIds()).toEqual(expect.arrayContaining(['snowNew', 'snowDepth', 'snowChance'])))
    // the unit of the snow is the answer's
    expect(wrapper!.text()).toContain('Snow forecast from MOSMIX-SNOW, DWD.')
  })

  it('shows none for another station, which asks for no snow values', async () => {
    await pick(BERLIN)
    await until(() => expect(stationRequests.snow).toBe(1))
    await snowAnswered()
    expect(requests.filter(request => request.kind === 'snow')).toEqual([])
    expect(toggles()).toEqual(['temp', 'wind', 'precip', 'cloud', 'pressure'])
    expect(wrapper!.text()).not.toContain('MOSMIX-SNOW')
    // answered with none: `[]`, which is not the `null` of a request that is under way
    expect((wrapper!.vm as any).snowValues).toEqual([])
  })

  it('asks which stations have a snow forecast once, for as many stations as are shown', async () => {
    await pick(BERLIN)
    await until(() => expect(stationRequests.snow).toBe(1))
    await pick(ZUGSPITZPLATT)
    await until(() => expect(toggles()).toContain('snow'))
    await pick(BERLIN)
    await until(() => expect(toggles()).not.toContain('snow'))
    await snowAnswered()
    expect(stationRequests.snow).toBe(1)
    // and the snow of the one that has it was asked for once
    expect(requests.filter(request => request.kind === 'snow')).toHaveLength(1)
  })

  it('draws no panel and shows no error out of season, where the backend answers a 404 (ProductOutOfSeasonError)', async () => {
    snowAnswer = async () => json({ detail: 'No MOSMIX-SNOW run is listed within https://opendata.dwd.de/weather/local_forecasts/mos/MOSMIX-SNOW_S/all_stations/kml/: DWD publishes it from November to April only, so there is no snow forecast to read until the winter.' }, 404)
    await pick(ZUGSPITZPLATT)
    await until(() => expect(requests.some(request => request.kind === 'snow')).toBe(true))
    await snowAnswered()
    expect(toggles()).toEqual(['temp', 'wind', 'precip', 'cloud', 'pressure'])
    expect((wrapper!.vm as any).error).toBeNull()
    expect(wrapper!.find('[role="alert"]').exists()).toBe(false)
    expect(wrapper!.text()).not.toContain('MOSMIX-SNOW')
    // the forecast is there
    await until(() => expect(drawnIds()).toContain('temp'))
  })

  it.each([
    ['a 500', async () => json({ detail: 'Upstream failed' }, 500)],
    ['a 502', async () => json({ detail: 'DWD could not be reached' }, 502)],
    ['a page of HTML', async () => new Response('<html>Bad gateway</html>', { status: 200, headers: { 'content-type': 'text/html' } })],
    ['a body that is no JSON', async () => new Response('{"values": [', { status: 200, headers: { 'content-type': 'application/json' } })],
    ['no list of values', async () => json({ message: 'something else answered' })],
    ['a request that fails', async () => Promise.reject(new TypeError('Failed to fetch'))],
  ])('does not break the forecast where the snow request is %s: the panel is absent and the page says nothing of it', async (_name, answer) => {
    snowAnswer = answer
    await pick(ZUGSPITZPLATT)
    await until(() => expect(requests.some(request => request.kind === 'snow')).toBe(true))
    await snowAnswered()
    expect(toggles()).toEqual(['temp', 'wind', 'precip', 'cloud', 'pressure'])
    expect((wrapper!.vm as any).error).toBeNull()
    expect(wrapper!.find('[role="alert"]').exists()).toBe(false)
    await until(() => expect(drawnIds()).toContain('temp'))
  })

  it('does not break the forecast where the list of the stations cannot be had, and asks for it again for the next station', async () => {
    snowStationsAnswer = (event) => {
      setResponseStatus(event, 500)
      return { detail: 'Upstream failed' }
    }
    await pick(ZUGSPITZPLATT)
    await until(() => expect(stationRequests.snow).toBe(1))
    await snowAnswered()
    expect(requests.filter(request => request.kind === 'snow')).toEqual([])
    expect(toggles()).toEqual(['temp', 'wind', 'precip', 'cloud', 'pressure'])
    expect((wrapper!.vm as any).error).toBeNull()
    snowStationsAnswer = () => ({ stations: [ZUGSPITZPLATT] })
    await pick(BERLIN)
    await pick(ZUGSPITZPLATT)
    await until(() => expect(toggles()).toContain('snow'))
    expect(stationRequests.snow).toBe(2)
  })

  it('does not hold the forecast back for the snow: the chart is drawn while the snow request is still under way', async () => {
    let release!: () => void
    snowAnswer = () => new Promise<Response>((resolve) => {
      release = () => resolve(json({ values: snowForecastValues({ hours: 23 }), ...metadata(SNOW_UNITS) }))
    })
    await pick(ZUGSPITZPLATT)
    await until(() => expect(drawnIds()).toContain('temp'))
    expect(toggles()).toEqual(['temp', 'wind', 'precip', 'cloud', 'pressure'])
    expect(drawnIds()).not.toContain('snowNew')
    // the request is under way: the page says so (`null`), so a link to the snow panel is kept until it answers
    expect((wrapper!.vm as any).snowValues).toBeNull()
    release()
    await until(() => expect(toggles()).toContain('snow'))
    await until(() => expect(drawnIds()).toContain('snowNew'))
  })

  it('does not show the snow of a station that was left while its snow was on the way', async () => {
    let release!: () => void
    snowAnswer = () => new Promise<Response>((resolve) => {
      release = () => resolve(json({ values: snowForecastValues({ hours: 23 }), ...metadata(SNOW_UNITS) }))
    })
    await pick(ZUGSPITZPLATT)
    await until(() => expect(requests.some(request => request.kind === 'snow')).toBe(true))
    await pick(BERLIN)
    release()
    // the old station's answer is dropped without being read, in the microtasks that follow its arrival: a macrotask lets them run
    await flushPromises()
    await snowAnswered()
    expect(toggles()).toEqual(['temp', 'wind', 'precip', 'cloud', 'pressure'])
    expect((wrapper!.vm as any).snowValues).toEqual([])
  })

  it('asks for the snow of the run that is chosen, as for the forecast\'s', async () => {
    await pick(ZUGSPITZPLATT)
    await until(() => expect(requests.filter(request => request.kind === 'snow')).toHaveLength(1))
    expect(requests.find(request => request.kind === 'snow')!.params.get('issue')).toBeNull()
    // a run chosen in the list of the runs
    ;(wrapper!.vm as any).selectedIssue = '2026-10-01T09:00:00'
    await until(() => expect(requests.filter(request => request.kind === 'snow')).toHaveLength(2))
    await until(() => expect(requests.filter(request => request.kind === 'forecast')).toHaveLength(2))
    expect(requests.filter(request => request.kind === 'snow')[1]!.params.get('issue')).toBe('2026-10-01T09:00:00')
    expect(requests.filter(request => request.kind === 'forecast')[1]!.params.get('issue')).toBe('2026-10-01T09:00:00')
  })
})
