import type { Server } from 'node:http'
import type { AddressInfo } from 'node:net'
import type { GhcnStationColumns } from '../../shared/types/ghcn-stations'
import { createServer } from 'node:http'
import { createRequire } from 'node:module'
import process from 'node:process'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { stationsOfColumns } from '../../app/utils/ghcn-stations'
import { ghcnReportingRule, yearOf } from '../../app/utils/map-tool'
import { compactGhcnStations, GHCN_STATIONS_PATH, ghcnMapStationsHandler, MIN_STATIONS, readGhcnMapStations } from '../../server/utils/ghcnStations'

// The list of the stations of NOAA GHCN daily that the app's server hands to the map (GH-4267): the columns it makes of the
// backend's answer, the stations the map makes of the columns, and the handler that keeps the list for a day.

const BACKEND = 'http://backend.internal:7890/api'

function backendStation(station_id: string, latitude: number | null, longitude: number | null, start: string | null, end: string | null, name: string | null = station_id, wmo_id: string | null = null) {
  return {
    resolution: 'daily',
    dataset: 'data',
    station_id,
    start_timestamp: start,
    end_timestamp: end,
    latitude,
    longitude,
    elevation: 10.1,
    name,
    region: null,
    wmo_id,
  }
}

const STATIONS = [
  backendStation('ACW00011604', 17.1167, -61.7833, '1949-01-01T00:00:00.000000+00:00', '1949-12-31T00:00:00.000000+00:00', 'ST JOHNS COOLIDGE FLD'),
  backendStation('ACW00011647', 17.1333, -61.7833, '1957-01-01T00:00:00.000000+00:00', null, 'ST JOHNS'),
  backendStation('GM000010147', 53.6332, 9.9881, '1891-01-01T00:00:00.000000+00:00', null, 'HAMBURG-FUHLSBUETTEL', '10147'),
]

function answer(stations: unknown[], retrieved_at = '2026-11-20T16:19:25.183109+00:00') {
  return new Response(JSON.stringify({ metadata: { retrieved_at }, stations }), { headers: { 'content-type': 'application/json' } })
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('the columns of the stations of GHCN daily', () => {
  it('are one column for each field the map reads, as long as the list, in the backend\'s order', () => {
    expect(compactGhcnStations(STATIONS, 'then')).toEqual({
      count: 3,
      retrieved_at: 'then',
      station_id: ['ACW00011604', 'ACW00011647', 'GM000010147'],
      latitude: [17.1167, 17.1333, 53.6332],
      longitude: [-61.7833, -61.7833, 9.9881],
      first_year: [1949, 1957, 1891],
      last_year: [1949, null, null],
      name: ['ST JOHNS COOLIDGE FLD', 'ST JOHNS', 'HAMBURG-FUHLSBUETTEL'],
      wmo_id: [null, null, '10147'],
    })
  })

  it('leave out a station with no position, which no map can show, and keep a year or a name that is not there as null', () => {
    const columns = compactGhcnStations([backendStation('NOPOSITION1', null, null, null, null), backendStation('ASTATION001', 1, 2, null, '2020-12-31T00:00:00+00:00', null)])
    expect(columns.station_id).toEqual(['ASTATION001'])
    expect(columns.count).toBe(1)
    expect(columns.first_year).toEqual([null])
    expect(columns.last_year).toEqual([2020])
    expect(columns.name).toEqual([null])
    expect(columns.wmo_id).toEqual([null])
  })

  it('carry the WMO number of a station as the backend writes it, trimmed, and null for none or an empty one', () => {
    const columns = compactGhcnStations([
      backendStation('GM000010147', 1, 2, null, null, 'A', ' 10147 '),
      backendStation('GM000010148', 1, 2, null, null, 'B', ''),
      backendStation('GM000010149', 1, 2, null, null, 'C', null),
    ])
    expect(columns.wmo_id).toEqual(['10147', null, null])
  })

  it('are about a fifth of the backend\'s list, which is the reason for them', () => {
    const many = Array.from({ length: 2000 }, (_, index) => backendStation(`GM${String(index).padStart(9, '0')}`, 40 + index / 1000, 5 + index / 1000, '1950-01-01T00:00:00.000000+00:00', index % 2 ? null : '1999-12-31T00:00:00.000000+00:00', `STATION NUMBER ${index}`))
    const compact = JSON.stringify(compactGhcnStations(many)).length
    expect(compact).toBeLessThan(JSON.stringify({ stations: many }).length / 3)
  })
})

describe('the stations the map makes of the columns', () => {
  const columns = compactGhcnStations(STATIONS)

  it('are the stations of the list, with the first and the last day of their years for the rest of the map to read', () => {
    const [first, second, third] = stationsOfColumns(columns)
    expect(first).toMatchObject({ station_id: 'ACW00011604', name: 'ST JOHNS COOLIDGE FLD', latitude: 17.1167, longitude: -61.7833, start_timestamp: '1949-01-01T00:00:00+00:00', end_timestamp: '1949-12-31T00:00:00+00:00' })
    expect(yearOf(first!.start_timestamp)).toBe(1949)
    expect(yearOf(first!.end_timestamp)).toBe(1949)
    // no last year is no end, which is a station that reports
    expect(second!.end_timestamp).toBeNull()
    expect(third!.start_timestamp).toBe('1891-01-01T00:00:00+00:00')
    // the WMO number is the list's: the forecast's same station is found by it, with no request for the station
    expect([first!.wmo_id, second!.wmo_id, third!.wmo_id]).toEqual([null, null, '10147'])
  })

  it('give the rule of the layer what it reads: a station reports with no end or an end last year, and has stopped before', () => {
    const now = Date.UTC(2026, 10, 20)
    const reports = ghcnReportingRule(now)
    const stations = stationsOfColumns(compactGhcnStations([
      ...STATIONS,
      backendStation('GM000000001', 50, 8, '1990-01-01T00:00:00+00:00', '2025-12-31T00:00:00+00:00'),
    ]))
    expect(stations.map(station => reports(station))).toEqual([false, true, true, true])
  })

  it('share one text for a year, not one for each station', () => {
    const [first, second] = stationsOfColumns(compactGhcnStations([STATIONS[0]!, { ...STATIONS[0]!, station_id: 'ACW00011605' }]))
    expect(first!.start_timestamp).toBe(second!.start_timestamp)
  })

  it('refuse columns that are not as long as the list says, which an answer of another form would be', () => {
    expect(() => stationsOfColumns({ ...columns, latitude: [1] })).toThrow(/unequal length/)
    expect(() => stationsOfColumns({ count: 1 } as unknown as GhcnStationColumns)).toThrow(/unequal length/)
  })
})

const ANY = 1

describe('reading the list from the backend', () => {
  it('asks the backend for the whole network of GHCN daily, with the request id', async () => {
    const fetcher = vi.fn().mockResolvedValue(answer(STATIONS))
    const read = await readGhcnMapStations(BACKEND, 'req-1', fetcher, ANY)
    expect(fetcher.mock.calls[0]![0]).toBe(`${BACKEND}${GHCN_STATIONS_PATH}`)
    expect(GHCN_STATIONS_PATH).toContain('provider=noaa&network=ghcn&parameters=daily/data&all=true')
    expect(fetcher.mock.calls[0]![1]).toMatchObject({ headers: { 'x-request-id': 'req-1' } })
    expect(read).toMatchObject({ count: 3, retrieved_at: '2026-11-20T16:19:25.183109+00:00' })
  })

  it('answers a backend that cannot be reached as a 502 problem that names no host, with when to retry, and logs the cause', async () => {
    const logged = vi.spyOn(console, 'error').mockImplementation(() => {})
    const cause = new Error('connect ECONNREFUSED 10.0.3.7:7890')
    const read = await readGhcnMapStations(BACKEND, 'req-1', vi.fn().mockRejectedValue(Object.assign(new Error('fetch failed'), { cause })), ANY)
    expect(read).toMatchObject({
      status: 502,
      headers: { 'content-type': 'application/problem+json', 'x-request-id': 'req-1', 'retry-after': '30' },
      body: { type: 'urn:wetterdienst:problem:backend-unreachable', status: 502, request_id: 'req-1' },
    })
    expect(JSON.stringify(read)).not.toMatch(/ECONNREFUSED|10\.0\.3\.7|backend\.internal/)
    expect(logged.mock.calls[0]).toContain(cause)
  })

  it('keeps the backend\'s own problem and its status, which is no list', async () => {
    const problem = { type: 'urn:wetterdienst:problem:rate-limited', title: 'Too Many Requests', status: 429, detail: 'Slow down.', instance: 'urn:wetterdienst:request:abc', request_id: 'abc' }
    const read = await readGhcnMapStations(BACKEND, 'req-1', vi.fn().mockResolvedValue(new Response(JSON.stringify(problem), { status: 429, headers: { 'content-type': 'application/problem+json' } })), ANY)
    expect(read).toMatchObject({ status: 429, body: problem })
  })

  it('answers a failure of the backend that is no problem as a 502', async () => {
    const read = await readGhcnMapStations(BACKEND, 'req-1', vi.fn().mockResolvedValue(new Response('upstream gone', { status: 503 })), ANY)
    expect(read).toMatchObject({ status: 502, body: { type: 'urn:wetterdienst:problem:unexpected-answer', detail: expect.stringContaining('503') } })
  })

  it('says that a body that could not be read to its end is that, keeps the cause in the log, and never calls it JSON that is none', async () => {
    const logged = vi.spyOn(console, 'error').mockImplementation(() => {})
    const reset = new Error('read ECONNRESET')
    const response = new Response('x', { headers: { 'content-type': 'application/json' } })
    vi.spyOn(response, 'text').mockRejectedValue(reset)
    const read = await readGhcnMapStations(BACKEND, 'req-1', vi.fn().mockResolvedValue(response), ANY)
    expect(read).toMatchObject({ status: 502, body: { type: 'urn:wetterdienst:problem:unexpected-answer', detail: expect.stringContaining('could not be read to its end') } })
    expect(JSON.stringify(read)).not.toMatch(/ECONNRESET|not valid JSON|not JSON/)
    expect(logged.mock.calls[0]).toContain(reset)
  })

  it('says that a body that is no JSON is that, in the words the app uses for it, and logs the error', async () => {
    const logged = vi.spyOn(console, 'error').mockImplementation(() => {})
    const read = await readGhcnMapStations(BACKEND, 'req-1', vi.fn().mockResolvedValue(new Response('{"stations": [', { headers: { 'content-type': 'application/json' } })), ANY)
    expect(read).toMatchObject({ status: 502, body: { detail: 'The API answered with application/json, but the body is not valid JSON. The address of the API may be wrong, or a proxy in front of it answered instead of it.' } })
    expect(logged.mock.calls[0]![1]).toBeInstanceOf(SyntaxError)
    const plain = await readGhcnMapStations(BACKEND, 'req-1', vi.fn().mockResolvedValue(new Response('nope', { headers: { 'content-type': 'text/plain' } })), ANY)
    expect(plain).toMatchObject({ status: 502, body: { detail: expect.stringContaining('text/plain, not JSON') } })
  })

  it.each([
    ['a page of HTML', () => new Response('<html>gateway</html>', { headers: { 'content-type': 'text/html' } })],
    ['JSON with no stations', () => new Response('{"detail":"x"}', { headers: { 'content-type': 'application/json' } })],
    ['no station at all, which is an outage and no network of none', () => answer([])],
  ])('answers %s as a 502 and never as a list of none, which a day of cache would keep', async (_, make) => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    const read = await readGhcnMapStations(BACKEND, 'req-1', vi.fn().mockResolvedValue(make()), ANY)
    expect(read).toMatchObject({ status: 502, body: { type: 'urn:wetterdienst:problem:unexpected-answer' } })
    expect(read).not.toHaveProperty('station_id')
  })

  it('refuses a list of fewer than 50,000 stations as a part of the list, and keeps one of 50,000', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    expect(MIN_STATIONS).toBe(50_000)
    const partial = await readGhcnMapStations(BACKEND, 'req-1', vi.fn().mockResolvedValue(answer(manyStations(MIN_STATIONS - 1))))
    expect(partial).toMatchObject({ status: 502, body: { type: 'urn:wetterdienst:problem:unexpected-answer', detail: expect.stringContaining('49999 stations') } })
    const whole = await readGhcnMapStations(BACKEND, 'req-1', vi.fn().mockResolvedValue(answer(manyStations(MIN_STATIONS))))
    expect(whole).toMatchObject({ count: MIN_STATIONS })
  })
})

function manyStations(count: number) {
  return Array.from({ length: count }, (_, index) => backendStation(`GM${String(index).padStart(9, '0')}`, 40 + (index % 1000) / 100, 5 + Math.floor(index / 1000) / 10, '1950-01-01T00:00:00+00:00', null, `STATION ${index}`))
}

// The handler as Nitro runs it: h3's own functions are its auto-imports, and so are the utilities.
const nuxtRequire = createRequire(createRequire(import.meta.url).resolve('nuxt/package.json'))
const h3 = nuxtRequire('h3') as typeof import('h3')

describe('the handler of the route', () => {
  const servers: Server[] = []

  afterEach(async () => {
    await Promise.all(servers.splice(0).map(server => new Promise(resolve => server.close(resolve))))
  })

  /** A server with the handler on it, the backend answering with what `answerOf` makes (each call is counted) and the clock the test sets */
  async function serve(answerOf: () => Response | Promise<Response>, minimum = ANY, apiBase: () => string = () => BACKEND) {
    for (const [name, value] of Object.entries({
      defineEventHandler: h3.defineEventHandler,
      handleCacheHeaders: h3.handleCacheHeaders,
      setResponseHeader: h3.setResponseHeader,
      setResponseStatus: h3.setResponseStatus,
      useRuntimeConfig: () => ({ apiBase: BACKEND }),
    }))
      vi.stubGlobal(name, value)
    const clock = { now: 1_000_000 }
    const fetcher = vi.fn(async () => answerOf())
    const app = h3.createApp()
    app.use(ghcnMapStationsHandler({ fetcher: fetcher as unknown as typeof fetch, now: () => clock.now, minimum, apiBase }))
    const server = createServer(h3.toNodeListener(app))
    servers.push(server)
    const origin = await new Promise<string>(resolve => server.listen(0, '127.0.0.1', () => resolve(`http://127.0.0.1:${(server.address() as AddressInfo).port}`)))
    return { fetcher, clock, origin, get: (headers: Record<string, string> = {}) => fetch(origin, { headers }) }
  }

  it('answers the columns as JSON, from the one request to the backend, for a day, with the headers of a day\'s cache', async () => {
    const { fetcher, clock, get } = await serve(() => answer(STATIONS))
    const first = await get()
    expect(first.status).toBe(200)
    expect(first.headers.get('content-type')).toBe('application/json')
    expect(first.headers.get('cache-control')).toBe('public, s-maxage=86400, stale-while-revalidate=86400')
    // the age of the list is taken off the day that a shared cache may keep it for
    clock.now += 3_600_000
    expect((await get()).headers.get('cache-control')).toBe('public, s-maxage=82800, stale-while-revalidate=86400')
    clock.now -= 3_600_000
    expect(await first.json()).toMatchObject({ count: 3, station_id: ['ACW00011604', 'ACW00011647', 'GM000010147'], wmo_id: [null, null, '10147'] })
    clock.now += 86_400_000 - 1
    const second = await get()
    expect(second.headers.get('cache-control')).toBe('public, s-maxage=1, stale-while-revalidate=86400')
    expect(second.headers.get('cache-control')).toBe('public, s-maxage=1, stale-while-revalidate=86400')
    expect(await second.json()).toMatchObject({ count: 3 })
    expect(fetcher).toHaveBeenCalledTimes(1)
  })

  it('has the requests that come while the list is made wait for the one request to the backend', async () => {
    let release!: () => void
    const held = new Promise<void>((resolve) => {
      release = resolve
    })
    const { fetcher, get } = await serve(async () => {
      await held
      return answer(STATIONS)
    })
    const requests = [get(), get(), get()]
    await vi.waitFor(() => expect(fetcher).toHaveBeenCalledTimes(1))
    release()
    const answers = await Promise.all(requests)
    expect(answers.map(response => response.status)).toEqual([200, 200, 200])
    expect(fetcher).toHaveBeenCalledTimes(1)
  })

  it('answers 304 with no body to a request that has the list\'s ETag', async () => {
    const { get } = await serve(() => answer(STATIONS))
    const etag = (await get()).headers.get('etag')!
    expect(etag).toMatch(/^W\/"/)
    const again = await get({ 'if-none-match': etag })
    expect(again.status).toBe(304)
    expect(await again.text()).toBe('')
    expect((await get({ 'if-none-match': 'W/"other"' })).status).toBe(200)
  })

  it('serves the list in hand once the day is over, and makes the next behind it, which a request after it has', async () => {
    let retrieved = 'first'
    const { fetcher, clock, get } = await serve(() => answer(STATIONS, retrieved))
    expect((await (await get()).json()).retrieved_at).toBe('first')
    clock.now += 86_400_000
    retrieved = 'second'
    // the stale list is the answer, and the new one is on its way
    expect((await (await get()).json()).retrieved_at).toBe('first')
    await vi.waitFor(async () => expect((await (await get()).json()).retrieved_at).toBe('second'))
    expect(fetcher).toHaveBeenCalledTimes(2)
  })

  it('keeps the list in hand where the refresh fails, serves it, and asks again no sooner than 30 s', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    let failing = false
    const { fetcher, clock, get } = await serve(() => failing ? new Response('gone', { status: 503 }) : answer(STATIONS))
    await get()
    clock.now += 86_400_000
    failing = true
    for (let ask = 0; ask < 3; ask++)
      expect((await get()).status).toBe(200)
    await vi.waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2))
    expect(fetcher).toHaveBeenCalledTimes(2)
    clock.now += 31_000
    expect((await get()).status).toBe(200)
    await vi.waitFor(() => expect(fetcher).toHaveBeenCalledTimes(3))
  })

  it('answers a backend that fails as the problem, with no-store, and asks again once the 30 s are over, not at every request', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    let failing = true
    const { fetcher, clock, get } = await serve(() => failing ? new Response('<html></html>', { headers: { 'content-type': 'text/html' } }) : answer(STATIONS))
    const failed = await get()
    expect(failed.status).toBe(502)
    expect(failed.headers.get('content-type')).toBe('application/problem+json')
    expect(failed.headers.get('cache-control')).toBe('no-store')
    expect(failed.headers.get('retry-after')).toBe('30')
    expect(await failed.json()).toMatchObject({ status: 502, type: 'urn:wetterdienst:problem:unexpected-answer' })
    // a backend that answers fast and wrongly is not read (44 MB) for every page view: the problem is answered again, with the time that is left
    clock.now += 12_500
    const again = await get()
    expect(again.status).toBe(502)
    expect(again.headers.get('cache-control')).toBe('no-store')
    expect(again.headers.get('retry-after')).toBe('18')
    expect(await again.json()).toMatchObject({ status: 502, type: 'urn:wetterdienst:problem:unexpected-answer' })
    expect(fetcher).toHaveBeenCalledTimes(1)
    // and again once the time is over, when the backend has recovered
    failing = false
    clock.now += 17_500
    const recovered = await get()
    expect(recovered.status).toBe(200)
    expect((await recovered.json()).count).toBe(3)
    expect(fetcher).toHaveBeenCalledTimes(2)
  })

  it('answers what the reader does not catch as a 502 with no-store and the back-off, where there is no list: no 500, nobody left waiting', async () => {
    const logged = vi.spyOn(console, 'error').mockImplementation(() => {})
    const { clock, get, fetcher, origin } = await serve(() => answer(STATIONS), ANY, () => {
      throw new Error('the config is not there')
    })
    const failed = await get()
    expect(failed.status).toBe(502)
    expect(failed.headers.get('cache-control')).toBe('no-store')
    expect(failed.headers.get('retry-after')).toBe('30')
    expect(await failed.json()).toMatchObject({ status: 502, detail: expect.not.stringContaining('config') })
    expect(logged.mock.calls[0]![1]).toBeInstanceOf(Error)
    clock.now += 5_000
    expect((await get()).headers.get('retry-after')).toBe('25')
    expect(fetcher).not.toHaveBeenCalled()
    expect(origin).toMatch(/^http:/)
  })

  it('has a refresh of a list in hand that throws unexpectedly raise no unhandled rejection, serve the list, and wait 30 s before the next', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    const unhandled = vi.fn()
    process.on('unhandledRejection', unhandled)
    try {
      let broken = false
      const { clock, get, fetcher } = await serve(() => answer(STATIONS), ANY, () => {
        if (broken)
          throw new Error('the config is gone')
        return BACKEND
      })
      await get()
      clock.now += 86_400_000
      broken = true
      for (let ask = 0; ask < 3; ask++)
        expect((await get()).status).toBe(200)
      await new Promise(resolve => setTimeout(resolve, 50))
      expect(unhandled).not.toHaveBeenCalled()
      expect(fetcher).toHaveBeenCalledTimes(1)
      // the refresh did not read the backend, and waits as long as one that did
      broken = false
      expect((await get()).status).toBe(200)
      await new Promise(resolve => setTimeout(resolve, 50))
      expect(fetcher).toHaveBeenCalledTimes(1)
      clock.now += 31_000
      await get()
      await vi.waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2))
    }
    finally {
      process.off('unhandledRejection', unhandled)
    }
  })

  it('keeps no list of fewer than 50,000 stations for a day, by the floor it has unless it is told another', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    const { fetcher, clock, get } = await serve(() => answer(manyStations(100)), MIN_STATIONS)
    expect((await get()).status).toBe(502)
    clock.now += 31_000
    expect((await get()).status).toBe(502)
    expect(fetcher).toHaveBeenCalledTimes(2)
  })
})
