import { mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useSettings } from '#imports'
import MapForecast from '~/components/MapForecast.vue'
import Meteogram from '~/components/Meteogram.vue'

// The forecast in the map's panel (GH-3650): one request for the station shown, whose answer is the only one that shows.
// The fetch here ignores the request's signal, as `registerEndpoint` does and as a connection that has already
// answered does: so the page's own guard against a late answer is what is tested, not the abort alone.

function station(station_id: string, name: string) {
  return { station_id, name, region: null, latitude: 52.5, longitude: 13.4, elevation: null }
}
function values(stationId: string) {
  return Array.from({ length: 72 }, (_, hour) => ({
    station_id: stationId,
    resolution: 'hourly',
    dataset: 'large',
    parameter: 'temperature_air_2m',
    timestamp: new Date(Date.UTC(2026, 9, 1 + Math.floor(hour / 24), hour % 24)).toISOString(),
    value: 10,
    quality_flags: null,
  }))
}
function gate<T>() {
  let release!: (value: T) => void
  const promise = new Promise<T>(resolve => (release = resolve))
  return { promise, release }
}

interface Answer { status: number, body: unknown }
let held: Record<string, ReturnType<typeof gate<Answer>>> = {}
const signals: Record<string, AbortSignal | undefined> = {}

beforeEach(() => {
  held = { 10384: gate(), 10147: gate() }
  globalThis.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const id = new URL(String(input), 'http://localhost').searchParams.get('stations')!
    signals[id] = init?.signal ?? undefined
    // never rejects on abort: the answer comes when the test lets it
    const { status, body } = await held[id]!.promise
    // a string is a page, as a proxy's error page is, not JSON
    if (typeof body === 'string')
      return new Response(body, { status, headers: { 'content-type': 'text/html; charset=utf-8' } })
    return new Response(JSON.stringify(body), { status })
  }) as typeof fetch
})

const mounted: Array<{ unmount: () => void }> = []
async function mountForecast(id = '10384', name = 'BERLIN') {
  const wrapper = await mountSuspended(MapForecast, { props: { station: station(id, name) }, attachTo: document.body })
  mounted.push(wrapper)
  return wrapper
}
const shownFor = (wrapper: Awaited<ReturnType<typeof mountForecast>>) => wrapper.findComponent(Meteogram).exists() ? (wrapper.findComponent(Meteogram).props('values') as Array<{ station_id: string }>)[0]!.station_id : null

afterEach(() => {
  mounted.splice(0).forEach(wrapper => wrapper.unmount())
  vi.restoreAllMocks()
})

describe('the forecast of the panel', () => {
  it('shows a busy state until the answer, then the day rows of the station', async () => {
    const wrapper = await mountForecast()
    expect(wrapper.find('[role="status"]').exists()).toBe(true)
    expect(wrapper.attributes('aria-busy')).toBe('true')
    held[10384]!.release({ status: 200, body: { values: values('10384') } })
    await vi.waitFor(() => expect(shownFor(wrapper)).toBe('10384'))
    expect(wrapper.attributes('aria-busy')).toBe('false')
  })

  it('shows the answer of the station now shown, and not the late answer of the one before, whichever comes last', async () => {
    const wrapper = await mountForecast('10384')
    await wrapper.setProps({ station: station('10147', 'HAMBURG') })
    held[10147]!.release({ status: 200, body: { values: values('10147') } })
    await vi.waitFor(() => expect(shownFor(wrapper)).toBe('10147'))
    // the first station's answer comes late
    held[10384]!.release({ status: 200, body: { values: values('10384') } })
    await new Promise(resolve => setTimeout(resolve, 30))
    expect(shownFor(wrapper)).toBe('10147')
    expect(wrapper.attributes('aria-busy')).toBe('false')
  })

  it('shows nothing of a late answer that is a failure either', async () => {
    const wrapper = await mountForecast('10384')
    await wrapper.setProps({ station: station('10147', 'HAMBURG') })
    held[10147]!.release({ status: 200, body: { values: values('10147') } })
    await vi.waitFor(() => expect(shownFor(wrapper)).toBe('10147'))
    held[10384]!.release({ status: 502, body: { detail: 'late' } })
    await new Promise(resolve => setTimeout(resolve, 30))
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    expect(shownFor(wrapper)).toBe('10147')
  })

  it('ends the request of the station before when another is shown, and the request of a station that is gone when it is removed', async () => {
    const abort = vi.spyOn(AbortController.prototype, 'abort')
    const wrapper = await mountForecast('10384')
    await wrapper.setProps({ station: station('10147', 'HAMBURG') })
    await vi.waitFor(() => expect(signals[10384]?.aborted).toBe(true))
    expect(signals[10147]?.aborted).toBe(false)
    expect(abort).toHaveBeenCalledTimes(1)
    wrapper.unmount()
    mounted.pop()
    expect(signals[10147]?.aborted).toBe(true)
  })

  it('tells a 200 page of HTML as a failure, not as a forecast with no values (GH-3841)', async () => {
    const wrapper = await mountForecast('10384')
    held[10384]!.release({ status: 200, body: '<!doctype html><html><body>Bad gateway</body></html>' })
    await vi.waitFor(() => expect(wrapper.find('[role="alert"]').exists()).toBe(true))
    expect(wrapper.find('[role="alert"]').text()).toContain('Backend error 502: The API answered with a web page, not data')
    expect(wrapper.findComponent(Meteogram).exists()).toBe(false)
  })

  it('tells JSON without the list of values as a failure, not as a forecast with no values (GH-3841)', async () => {
    const wrapper = await mountForecast('10384')
    held[10384]!.release({ status: 200, body: { message: 'something else answered' } })
    await vi.waitFor(() => expect(wrapper.find('[role="alert"]').exists()).toBe(true))
    expect(wrapper.find('[role="alert"]').text()).toContain('no list of `values`')
  })

  it('shows an answer with an empty list of values as it is: no failure (GH-3841)', async () => {
    const wrapper = await mountForecast('10384')
    held[10384]!.release({ status: 200, body: { values: [] } })
    await vi.waitFor(() => expect(wrapper.attributes('aria-busy')).toBe('false'))
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
  })

  it('tells why the forecast could not be read, and reads it again on Retry', async () => {
    const wrapper = await mountForecast('10384')
    held[10384]!.release({ status: 500, body: { detail: 'The forecast could not be read' } })
    await vi.waitFor(() => expect(wrapper.find('[role="alert"]').text()).toBe('Backend error 500: The forecast could not be read'))
    held[10384] = gate()
    await wrapper.find('button').trigger('click')
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    held[10384]!.release({ status: 200, body: { values: values('10384') } })
    await vi.waitFor(() => expect(shownFor(wrapper)).toBe('10384'))
  })

  it('says there is no forecast for a station whose answer holds none', async () => {
    const wrapper = await mountForecast('10384')
    held[10384]!.release({ status: 200, body: { values: [] } })
    await vi.waitFor(() => expect(wrapper.text()).toContain('No forecast data available.'))
  })
})

// The days follow the unit settings (GH-3980): the request carries them, the rows are told the unit the answer reports, and a
// change of them while the days are shown fetches them again; the request under way is ended by the newer
describe('the forecast of the panel in the unit of the settings', () => {
  const queries: URLSearchParams[] = []
  const signalsOfCalls: Array<AbortSignal | undefined> = []
  let waiting: Array<() => void> = []

  beforeEach(() => {
    queries.length = 0
    signalsOfCalls.length = 0
    waiting = []
    globalThis.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const query = new URL(String(input), 'http://localhost').searchParams
      queries.push(query)
      signalsOfCalls.push(init?.signal ?? undefined)
      const fahrenheit = JSON.parse(query.get('unit_targets')!).temperature === 'degree_fahrenheit'
      // an answer held until the test lets it go
      await new Promise<void>(resolve => waiting.push(resolve))
      return new Response(JSON.stringify({
        values: values('60001').map(row => ({ ...row, value: fahrenheit ? 50 : 10 })),
        metadata: { parameters: [{ name: 'temperature_air_2m', quantity: 'temperature', unit: fahrenheit ? '°F' : '°C' }] },
      }), { status: 200 })
    }) as typeof fetch
  })
  afterEach(() => {
    vi.useRealTimers()
    useSettings().settings.value.units.temperature = 'degree_celsius'
  })

  it('asks in the unit the settings choose, and tells the rows the unit the answer reports', async () => {
    // the first of October, which the values start on: the rows start at today
    vi.useFakeTimers({ toFake: ['Date'], now: new Date('2026-10-01T10:00:00Z') })
    useSettings().settings.value.units.temperature = 'degree_fahrenheit'
    const wrapper = await mountForecast('60001')
    expect(JSON.parse(queries[0]!.get('unit_targets')!).temperature).toBe('degree_fahrenheit')
    waiting.forEach(release => release())
    await vi.waitFor(() => expect(wrapper.findComponent(Meteogram).props('units')).toEqual({ temperature_air_2m: '°F' }))
    expect(wrapper.find('[data-testid="day-rows"]').text()).toContain('°F')
  })

  it('fetches the days again, in the new unit, where the settings change while they are shown', async () => {
    const wrapper = await mountForecast('60001')
    waiting.forEach(release => release())
    await vi.waitFor(() => expect(wrapper.findComponent(Meteogram).props('units')).toEqual({ temperature_air_2m: '°C' }))
    expect(queries).toHaveLength(1)

    useSettings().settings.value.units.temperature = 'degree_fahrenheit'
    await vi.waitFor(() => expect(queries).toHaveLength(2))
    expect(JSON.parse(queries[1]!.get('unit_targets')!).temperature).toBe('degree_fahrenheit')
    waiting.forEach(release => release())
    await vi.waitFor(() => expect(wrapper.findComponent(Meteogram).props('units')).toEqual({ temperature_air_2m: '°F' }))
    await new Promise(resolve => setTimeout(resolve, 30))
    expect(queries).toHaveLength(2)
  })

  it('does not fetch the days again for a unit they do not show: a speed, a pressure or an angle', async () => {
    const wrapper = await mountForecast('60001')
    waiting.forEach(release => release())
    await vi.waitFor(() => expect(wrapper.findComponent(Meteogram).props('units')).toEqual({ temperature_air_2m: '°C' }))
    useSettings().settings.value.units.speed = 'knots'
    useSettings().settings.value.units.pressure = 'pascal'
    useSettings().settings.value.units.angle = 'radian'
    await new Promise(resolve => setTimeout(resolve, 30))
    expect(queries).toHaveLength(1)
    useSettings().settings.value.units.speed = 'meter_per_second'
    useSettings().settings.value.units.pressure = 'hectopascal'
    useSettings().settings.value.units.angle = 'degree'
  })

  it('ends the request under way where the unit changes, and shows the answer of the newer one only', async () => {
    const wrapper = await mountForecast('60001')
    useSettings().settings.value.units.temperature = 'degree_fahrenheit'
    await vi.waitFor(() => expect(queries).toHaveLength(2))
    expect(signalsOfCalls[0]?.aborted).toBe(true)
    // the first answer comes late, after the second one
    waiting[1]!()
    await vi.waitFor(() => expect(wrapper.findComponent(Meteogram).props('units')).toEqual({ temperature_air_2m: '°F' }))
    waiting[0]!()
    await new Promise(resolve => setTimeout(resolve, 30))
    expect(wrapper.findComponent(Meteogram).props('units')).toEqual({ temperature_air_2m: '°F' })
  })
})
