import type { GhcnStationColumns } from '../../shared/types/ghcn-stations'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { stationsOfColumns } from '../../app/utils/ghcn-stations'
import { ghcnReportingRule, yearOf } from '../../app/utils/map-tool'
import { compactGhcnStations, GHCN_STATIONS_PATH, readGhcnStations } from '../../server/utils/ghcnStations'

// The list of the stations of NOAA GHCN daily that the app's server hands to the map (GH-4267): the columns it makes of the
// backend's answer, the stations the map makes of the columns, and the route that keeps the list for a day.

const BACKEND = 'http://backend.internal:7890/api'

function backendStation(station_id: string, latitude: number | null, longitude: number | null, start: string | null, end: string | null, name: string | null = station_id) {
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
    wmo_id: null,
  }
}

const STATIONS = [
  backendStation('ACW00011604', 17.1167, -61.7833, '1949-01-01T00:00:00.000000+00:00', '1949-12-31T00:00:00.000000+00:00', 'ST JOHNS COOLIDGE FLD'),
  backendStation('ACW00011647', 17.1333, -61.7833, '1957-01-01T00:00:00.000000+00:00', null, 'ST JOHNS'),
  backendStation('GM000010147', 53.6332, 9.9881, '1891-01-01T00:00:00.000000+00:00', null, 'HAMBURG-FUHLSBUETTEL'),
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
    })
  })

  it('leave out a station with no position, which no map can show, and keep a year or a name that is not there as null', () => {
    const columns = compactGhcnStations([backendStation('NOPOSITION1', null, null, null, null), backendStation('ASTATION001', 1, 2, null, '2020-12-31T00:00:00+00:00', null)])
    expect(columns.station_id).toEqual(['ASTATION001'])
    expect(columns.count).toBe(1)
    expect(columns.first_year).toEqual([null])
    expect(columns.last_year).toEqual([2020])
    expect(columns.name).toEqual([null])
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

describe('reading the list from the backend', () => {
  it('asks the backend for the whole network of GHCN daily, with the request id', async () => {
    const fetcher = vi.fn().mockResolvedValue(answer(STATIONS))
    const read = await readGhcnStations(BACKEND, 'req-1', fetcher)
    expect(fetcher.mock.calls[0]![0]).toBe(`${BACKEND}${GHCN_STATIONS_PATH}`)
    expect(GHCN_STATIONS_PATH).toContain('provider=noaa&network=ghcn&parameters=daily/data&all=true')
    expect(fetcher.mock.calls[0]![1]).toMatchObject({ headers: { 'x-request-id': 'req-1' } })
    expect(read).toMatchObject({ count: 3, retrieved_at: '2026-11-20T16:19:25.183109+00:00' })
  })

  it('answers a backend that cannot be reached as a 502 problem that names no host, with when to retry, and logs the cause', async () => {
    const logged = vi.spyOn(console, 'error').mockImplementation(() => {})
    const cause = new Error('connect ECONNREFUSED 10.0.3.7:7890')
    const read = await readGhcnStations(BACKEND, 'req-1', vi.fn().mockRejectedValue(Object.assign(new Error('fetch failed'), { cause })))
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
    const read = await readGhcnStations(BACKEND, 'req-1', vi.fn().mockResolvedValue(new Response(JSON.stringify(problem), { status: 429, headers: { 'content-type': 'application/problem+json' } })))
    expect(read).toMatchObject({ status: 429, body: problem })
  })

  it('answers a failure of the backend that is no problem as a 502', async () => {
    const read = await readGhcnStations(BACKEND, 'req-1', vi.fn().mockResolvedValue(new Response('upstream gone', { status: 503 })))
    expect(read).toMatchObject({ status: 502, body: { type: 'urn:wetterdienst:problem:unexpected-answer', detail: expect.stringContaining('503') } })
  })

  it.each([
    ['a page of HTML', () => new Response('<html>gateway</html>', { headers: { 'content-type': 'text/html' } })],
    ['a text that is no JSON', () => new Response('not json', { headers: { 'content-type': 'application/json' } })],
    ['JSON with no stations', () => new Response('{"detail":"x"}', { headers: { 'content-type': 'application/json' } })],
    ['no station at all, which is an outage and no network of none', () => answer([])],
  ])('answers %s as a 502 and never as a list of none, which a day of cache would keep', async (_, make) => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    const read = await readGhcnStations(BACKEND, 'req-1', vi.fn().mockResolvedValue(make()))
    expect(read).toMatchObject({ status: 502, body: { type: 'urn:wetterdienst:problem:unexpected-answer' } })
    expect(read).not.toHaveProperty('station_id')
  })
})

describe('the route', () => {
  async function route(read: unknown) {
    let options: Record<string, unknown> = {}
    let status = 200
    vi.stubGlobal('defineCachedEventHandler', (handler: unknown, given: Record<string, unknown>) => {
      options = given
      return handler
    })
    vi.stubGlobal('defineEventHandler', (handler: unknown) => handler)
    // what Nitro's cache lets a handler's own status through as
    vi.stubGlobal('getResponseStatus', () => status)
    vi.stubGlobal('useRuntimeConfig', () => ({ apiBase: BACKEND }))
    const fetcher = vi.fn().mockImplementation(async () => read)
    vi.stubGlobal('fetch', fetcher)
    const setResponseStatus = vi.fn((_event: unknown, code: number) => {
      status = code
    })
    const setResponseHeader = vi.fn()
    vi.stubGlobal('setResponseStatus', setResponseStatus)
    vi.stubGlobal('setResponseHeader', setResponseHeader)
    vi.resetModules()
    const { default: handler } = await import('../../server/api/map/ghcn-stations.get')
    const body = await (handler as unknown as (event: unknown) => Promise<string>)({})
    return { body, options, setResponseStatus, setResponseHeader, fetcher }
  }

  it('keeps the list for a day and serves the stale one while a new one is made, under one key', async () => {
    const { options } = await route(answer(STATIONS))
    expect(options).toMatchObject({ maxAge: 24 * 60 * 60, swr: true })
    expect((options.getKey as () => string)()).toBe('all')
  })

  it('answers the columns as JSON text, which Nitro keeps and sends as it is', async () => {
    const { body, setResponseHeader, setResponseStatus } = await route(answer(STATIONS))
    expect(JSON.parse(body)).toMatchObject({ count: 3, station_id: ['ACW00011604', 'ACW00011647', 'GM000010147'] })
    expect(setResponseHeader).toHaveBeenCalledWith(expect.anything(), 'content-type', 'application/json')
    expect(setResponseStatus).not.toHaveBeenCalled()
  })

  it('answers a backend failure as an error with the status that Nitro does not keep (400 and more), and no list', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    const { body, setResponseStatus, setResponseHeader } = await route(new Response('<html></html>', { headers: { 'content-type': 'text/html' } }))
    expect(setResponseStatus).toHaveBeenCalledWith(expect.anything(), 502)
    expect(setResponseHeader).toHaveBeenCalledWith(expect.anything(), 'content-type', 'application/problem+json')
    expect(JSON.parse(body)).toMatchObject({ status: 502, type: 'urn:wetterdienst:problem:unexpected-answer' })
    expect(JSON.parse(body)).not.toHaveProperty('station_id')
    // and no CDN in front of the app keeps it for the day that Nitro's header says
    expect(setResponseHeader).toHaveBeenCalledWith(expect.anything(), 'cache-control', 'no-store')
  })

  it('leaves the cache headers of a list alone', async () => {
    const { setResponseHeader } = await route(answer(STATIONS))
    expect(setResponseHeader).not.toHaveBeenCalledWith(expect.anything(), 'cache-control', expect.anything())
  })
})
