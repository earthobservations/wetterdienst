import type { IncomingMessage, Server, ServerResponse } from 'node:http'
import type { AddressInfo } from 'node:net'
import { createServer } from 'node:http'
import { createRequire } from 'node:module'
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { backendReader, stripesStationsOf, UpstreamProblem } from '../../server/utils/ghcnStripes'
import { AbortedError } from '../../server/utils/ttlCache'
import * as stub from '../helpers/ghcn-stripes-stub'

// The two routes of the app's own server that the climate stripes of GHCN daily are made from (GH-4258), run for real on an h3
// server with Nitro's auto-imports given as globals, and the backend a server of this test that answers as its generic API does:
// what the browser sees is read off a real response, and what the backend is asked is noted.
const nuxtRequire = createRequire(createRequire(import.meta.url).resolve('nuxt/package.json'))
const h3 = nuxtRequire('h3') as typeof import('h3')

const config = { apiBase: '' }
/** The servers of the test: the fake backend, and for each test the routes under test, which have a cache of their own */
let backendServer: Server
const mounted: Server[] = []
let mount: () => Promise<void>
let app: string
let backend: string
let closed: string

interface Seen { path: string, query: URLSearchParams, requestId: string | undefined }
const seen: Seen[] = []
/** What the backend answers next: a function of the request, or the default answer of the generic API */
let answer: ((request: IncomingMessage, response: ServerResponse, query: URLSearchParams) => void) | null = null
let delayMs = 0

const PROVIDER = {
  name_local: 'National Oceanic And Atmospheric Administration',
  attribution: 'NOAA National Centers for Environmental Information (NCEI), Global Historical Climatology Network',
  license: { spdx_id: 'CC0-1.0', name: 'Creative Commons Zero v1.0 Universal', url: 'https://creativecommons.org/publicdomain/zero/1.0/' },
}

/** The generic API's long frame of the stub station, in the unit asked for, with the metadata block of `with_metadata` */
function valuesAnswer(query: URLSearchParams) {
  const names = (query.get('parameters') ?? '').split(',').map(parameter => parameter.split('/')[2]!)
  const fahrenheit = (query.get('unit_targets') ?? '').includes('fahrenheit')
  const rows = stub.stubRows()
    .filter(row => names.includes(row.parameter))
    .map(row => ({
      station_id: query.get('stations'),
      resolution: 'daily',
      dataset: 'data',
      ...row,
      value: fahrenheit && row.parameter.startsWith('temperature') ? row.value! * 9 / 5 + 32 : row.value,
    }))
  const unit = (name: string) => name.startsWith('temperature') ? (fahrenheit ? '°F' : '°C') : 'mm'
  return {
    metadata: { provider: PROVIDER, parameters: names.map(name => ({ name, unit: unit(name) })), warnings: [] },
    values: rows,
  }
}

function backendHandler(request: IncomingMessage, response: ServerResponse): void {
  const url = new URL(request.url ?? '/', 'http://backend')
  seen.push({ path: url.pathname, query: url.searchParams, requestId: request.headers['x-request-id'] as string | undefined })
  const send = (status: number, body: unknown, type = 'application/json', headers: Record<string, string> = {}) => {
    response.writeHead(status, { 'content-type': type, ...headers })
    response.end(typeof body === 'string' ? body : JSON.stringify(body))
  }
  const respond = () => {
    if (answer) {
      answer(request, response, url.searchParams)
      return
    }
    if (url.pathname === '/api/values')
      send(200, valuesAnswer(url.searchParams))
    else if (url.pathname === '/api/stations')
      send(200, { stations: stub.listOf(url.searchParams.get('parameters')!.split('/')[2]!) })
    else
      send(404, { type: 'urn:wetterdienst:problem:not-found', title: 'Not Found', status: 404, detail: 'Not Found' })
  }
  if (delayMs)
    setTimeout(respond, delayMs)
  else
    respond()
}

async function raw(path: string, headers: Record<string, string> = {}) {
  const response = await fetch(`${app}${path}`, { headers })
  const text = await response.text()
  return { status: response.status, headers: response.headers, text, json: () => JSON.parse(text) }
}

const ANNUAL = '/_ghcn/annual?kind=temperature&station=USW00000001'

const listen = (server: Server) => new Promise<string>(resolve => server.listen(0, '127.0.0.1', () => resolve(`http://127.0.0.1:${(server.address() as AddressInfo).port}`)))
const close = (server: Server) => new Promise<void>(resolve => server.close(() => resolve()))

beforeAll(async () => {
  for (const [name, value] of Object.entries({
    defineEventHandler: h3.defineEventHandler,
    getQuery: h3.getQuery,
    getRequestHeader: h3.getRequestHeader,
    setResponseStatus: h3.setResponseStatus,
    setResponseHeader: h3.setResponseHeader,
    useRuntimeConfig: () => config,
  }))
    vi.stubGlobal(name, value)
  const { ghcnAnnualHandler, ghcnStationsHandler } = await import('../../server/utils/ghcnRoutes')
  backendServer = createServer(backendHandler)
  backend = await listen(backendServer)
  // an address nothing listens at: a backend that is down
  const deadServer = createServer()
  closed = await listen(deadServer)
  await close(deadServer)

  // each test has routes of its own, so that what one cached is not served to the next
  mount = async () => {
    const router = h3.createApp()
    router.use('/_ghcn/annual', ghcnAnnualHandler())
    router.use('/_ghcn/stations', ghcnStationsHandler())
    const server = createServer(h3.toNodeListener(router))
    mounted.push(server)
    app = await listen(server)
  }
})

beforeEach(async () => {
  seen.length = 0
  answer = null
  delayMs = 0
  config.apiBase = `${backend}/api`
  await mount()
})

afterEach(async () => {
  await Promise.all(mounted.splice(0).map(close))
})

afterAll(async () => {
  vi.unstubAllGlobals()
  await close(backendServer)
})

describe('the annual values route', () => {
  it('answers a station\'s years, calculated from the days the generic API gives, with the credit and the unit', async () => {
    const { status, json, headers } = await raw(`${ANNUAL}&unit_targets=${encodeURIComponent('{"temperature":"degree_celsius"}')}`, { 'x-request-id': 'my-request' })

    expect(status).toBe(200)
    const body = json()
    expect(body.series).toEqual({ station_id: 'USW00000001', parameter: 'temperature_air_mean_2m', unit: '°C', method: 'midrange' })
    expect(body.metadata.provider.attribution).toContain('NOAA National Centers')
    expect(body.metadata.provider.license.name).toBe('Creative Commons Zero v1.0 Universal')
    const years = Object.fromEntries(body.values.map((item: { timestamp: string, value: number | null }) => [item.timestamp.slice(0, 4), item.value]))
    expect(Object.keys(years)).toHaveLength(31)
    expect(years['2000']).toBeNull()
    expect(years['2005']).toBeNull()
    expect(years['1999']).toBeCloseTo(11.8, 3)
    expect(years['2015']).toBeCloseTo(15, 3)
    // a few kilobytes where the days are megabytes
    expect(body.values[0]).toEqual({ timestamp: '1990-01-01T00:00:00.000000+00:00', value: 10 })
    expect(headers.get('cache-control')).toBe('public, max-age=3600')
    expect(headers.get('x-request-id')).toBe('my-request')
  })

  it('reads the days from /api/values as the backend\'s stripes read them: the three parameters, the whole record, a long frame in the unit asked for', async () => {
    await raw(`${ANNUAL}&unit_targets=${encodeURIComponent('{"temperature":"degree_fahrenheit"}')}`, { 'x-request-id': 'abc123' })

    expect(seen).toHaveLength(1)
    const [read] = seen
    expect(read!.path).toBe('/api/values')
    expect(read!.requestId).toBe('abc123')
    const query = Object.fromEntries(read!.query)
    expect(query).toMatchObject({
      provider: 'noaa',
      network: 'ghcn',
      parameters: 'daily/data/temperature_air_mean_2m,daily/data/temperature_air_max_2m,daily/data/temperature_air_min_2m',
      stations: 'USW00000001',
      shape: 'long',
      humanize: 'true',
      skip_empty: 'false',
      with_metadata: 'true',
      drop_nulls: 'true',
      unit_targets: '{"temperature":"degree_fahrenheit"}',
    })
    expect(query.timestamp).toMatch(/^1700-01-01\/\d{4}-\d{2}-\d{2}$/)
    // no stripes route
    expect(seen.every(item => !/stripes/.test(item.path))).toBe(true)
  })

  it('calculates in the unit asked for, which comes first: 50 degrees Fahrenheit in 1990, the same years as a gap', async () => {
    const body = (await raw(`${ANNUAL}&unit_targets=${encodeURIComponent('{"temperature":"degree_fahrenheit"}')}`)).json()
    expect(body.series.unit).toBe('°F')
    expect(body.values[0].value).toBeCloseTo(50, 2)
    expect(body.values.filter((item: { value: number | null }) => item.value === null)).toHaveLength(2)
  })

  it('has precipitation years that are sums, built from the one parameter, with no method', async () => {
    const body = (await raw('/_ghcn/annual?kind=precipitation&station=USW00000001')).json()
    expect(seen[0]!.query.get('parameters')).toBe('daily/data/precipitation_amount')
    expect(seen[0]!.query.get('unit_targets')).toBeNull()
    expect(body.series).toEqual({ station_id: 'USW00000001', parameter: 'precipitation_amount', unit: 'mm', method: null })
    const years = Object.fromEntries(body.values.map((item: { timestamp: string, value: number | null }) => [item.timestamp.slice(0, 4), item.value]))
    expect(years['1991']).toBeCloseTo(stub.rainOf(1991), 6)
    expect(Object.entries(years).filter(([, value]) => value === null).map(([year]) => year)).toEqual(['2000', '2005', '2010'])
  })

  it('keeps what it calculated: the next asker, a browser or another, is served without a read of the backend', async () => {
    const first = await raw(ANNUAL)
    const second = await raw(ANNUAL)
    expect(seen).toHaveLength(1)
    expect(second.text).toBe(first.text)
    // another station, another kind or another unit is its own entry
    await raw('/_ghcn/annual?kind=temperature&station=USW00000002')
    await raw('/_ghcn/annual?kind=precipitation&station=USW00000001')
    await raw(`${ANNUAL}&unit_targets=${encodeURIComponent('{"temperature":"degree_fahrenheit"}')}`)
    expect(seen).toHaveLength(4)
  })

  it('reads the backend once for askers that come while it reads', async () => {
    delayMs = 50
    const responses = await Promise.all([raw(ANNUAL), raw(ANNUAL), raw(ANNUAL)])
    expect(responses.map(item => item.status)).toEqual([200, 200, 200])
    expect(seen).toHaveLength(1)
  })

  it('does not keep a failure: a backend that failed is asked again by the next one', async () => {
    answer = (_request, response) => {
      response.writeHead(500, { 'content-type': 'application/problem+json' })
      response.end(JSON.stringify({ type: 'urn:wetterdienst:problem:server-error', title: 'Internal Server Error', status: 500, detail: 'The server failed.' }))
    }
    expect((await raw(ANNUAL)).status).toBe(500)
    answer = null
    expect((await raw(ANNUAL)).status).toBe(200)
    expect(seen).toHaveLength(2)
  })

  it('passes on the backend\'s own problem, with its status, and says whose request it was', async () => {
    answer = (_request, response) => {
      response.writeHead(429, { 'content-type': 'application/problem+json', 'retry-after': '12' })
      response.end(JSON.stringify({ type: 'urn:wetterdienst:problem:rate-limited', title: 'Too Many Requests', status: 429, detail: 'Slow down.' }))
    }
    const result = await raw(ANNUAL, { 'x-request-id': 'req-1' })
    expect(result.status).toBe(429)
    expect(result.headers.get('content-type')).toBe('application/problem+json')
    expect(result.headers.get('retry-after')).toBe('12')
    expect(result.json()).toMatchObject({ type: 'urn:wetterdienst:problem:rate-limited', detail: 'Slow down.', request_id: 'req-1', instance: 'urn:wetterdienst:request:req-1' })
  })

  it('is a 404 for a station the generic API does not know, in the words the stripes of the backend had', async () => {
    answer = (_request, response) => {
      response.writeHead(200, { 'content-type': 'application/json' })
      response.end(JSON.stringify({ metadata: { provider: PROVIDER, warnings: [{ code: 'unknown-station', message: 'x' }] }, values: [] }))
    }
    const result = await raw('/_ghcn/annual?kind=temperature&station=USW99999999')
    expect(result.status).toBe(404)
    expect(result.json().detail).toBe('No station with a station_id similar to \'USW99999999\' found')
  })

  it('has no years for a station that has no days: an empty list, for the app to refuse as too few', async () => {
    answer = (_request, response) => {
      response.writeHead(200, { 'content-type': 'application/json' })
      response.end(JSON.stringify({ metadata: { provider: PROVIDER, parameters: [], warnings: [] }, values: [] }))
    }
    const result = await raw(ANNUAL)
    expect(result.status).toBe(200)
    expect(result.json().values).toEqual([])
  })

  it('is a 502 of its own where the backend cannot be reached, and where a page of HTML answers for it', async () => {
    config.apiBase = `${closed}/api`
    const down = await raw(ANNUAL)
    expect(down.status).toBe(502)
    expect(down.headers.get('retry-after')).toBe('30')
    expect(down.json()).toMatchObject({ type: 'urn:wetterdienst:problem:backend-unreachable', status: 502 })
    // the cause is the server log's, not the browser's
    expect(down.text).not.toContain('ECONNREFUSED')

    config.apiBase = `${backend}/api`
    answer = (_request, response) => {
      response.writeHead(200, { 'content-type': 'text/html; charset=utf-8' })
      response.end('<!doctype html><html><body>Service is starting</body></html>')
    }
    const page = await raw(ANNUAL)
    expect(page.status).toBe(502)
    expect(page.json()).toMatchObject({ type: 'urn:wetterdienst:problem:unexpected-answer' })
  })

  it('is a 502 where the answer is JSON that is no frame of values', async () => {
    answer = (_request, response) => {
      response.writeHead(200, { 'content-type': 'application/json' })
      response.end(JSON.stringify({ hello: 'world' }))
    }
    expect((await raw(ANNUAL)).status).toBe(502)
  })

  it.each([
    ['/_ghcn/annual', ['kind', 'station']],
    ['/_ghcn/annual?kind=wind&station=USW00000001', ['kind']],
    ['/_ghcn/annual?kind=temperature&station=../../values', ['station']],
    ['/_ghcn/annual?kind=temperature&station=USW00000001&unit_targets=nope', ['unit_targets']],
    [`/_ghcn/annual?kind=temperature&station=USW00000001&unit_targets=${encodeURIComponent('{"precipitation":"millimeter"}')}`, ['unit_targets']],
    [`/_ghcn/annual?kind=temperature&station=USW00000001&unit_targets=${encodeURIComponent('{"temperature":"degree celsius; drop"}')}`, ['unit_targets']],
  ])('refuses %s as a 422 that names %j, before anything is read', async (path, names) => {
    const result = await raw(path)
    expect(result.status).toBe(422)
    const body = result.json()
    expect(body.type).toBe('urn:wetterdienst:problem:invalid-parameters')
    expect(body.errors.map((error: { loc: string[] }) => error.loc[1])).toEqual(names)
    expect(seen).toHaveLength(0)
  })
})

describe('the queue of reads of the annual values', () => {
  it('holds 4 reads and 16 waiting, and refuses the next with a 503 and when to come back, where a client asking for many stations would stall the rest', async () => {
    delayMs = 300
    const responses = await Promise.all(Array.from({ length: 24 }, (_, index) => raw(`/_ghcn/annual?kind=temperature&station=USW${String(index).padStart(8, '0')}`)))

    const refused = responses.filter(response => response.status === 503)
    // 4 running and 16 waiting are taken, the other four are not
    expect(refused).toHaveLength(4)
    expect(responses.filter(response => response.status === 200)).toHaveLength(20)
    expect(refused[0]!.headers.get('retry-after')).toBe('10')
    expect(refused[0]!.json()).toMatchObject({ type: 'urn:wetterdienst:problem:server-busy', status: 503 })
    // the refused ones were never read
    expect(seen).toHaveLength(20)
  }, 30_000)

  it('does not read for a client that has gone while its read waited, and takes it from the queue', async () => {
    delayMs = 400
    const running = Array.from({ length: 4 }, (_, index) => raw(`/_ghcn/annual?kind=temperature&station=USW0000000${index}`))
    // a fifth waits for a place, and its client closes the connection
    const leaving = new AbortController()
    const left = fetch(`${app}/_ghcn/annual?kind=temperature&station=USW00000099`, { signal: leaving.signal }).catch((failure: Error) => failure.name)
    await vi.waitFor(() => expect(seen).toHaveLength(4))
    leaving.abort()
    expect(await left).toBe('AbortError')

    expect((await Promise.all(running)).map(response => response.status)).toEqual([200, 200, 200, 200])
    // a sixth, which comes after, is read as it would have been
    expect((await raw('/_ghcn/annual?kind=temperature&station=USW00000098')).status).toBe(200)
    expect(seen.map(item => item.query.get('stations'))).not.toContain('USW00000099')
    expect(seen).toHaveLength(5)
  }, 30_000)

  it('keeps no read of a client that left while it ran: the next asker of the station reads it again', async () => {
    delayMs = 300
    const leaving = new AbortController()
    const left = fetch(`${app}${ANNUAL}`, { signal: leaving.signal }).catch((failure: Error) => failure.name)
    await vi.waitFor(() => expect(seen).toHaveLength(1))
    leaving.abort()
    expect(await left).toBe('AbortError')
    delayMs = 0
    expect((await raw(ANNUAL)).status).toBe(200)
    expect(seen).toHaveLength(2)
  })
})

describe('a read of the backend that takes too long, or whose client has gone', () => {
  const never = (failure: Error) => (async () => {
    throw failure
  }) as unknown as typeof fetch

  it('is a 504 of its own that says to try again, and not the backend being unreachable', async () => {
    const timeout = Object.assign(new Error('timed out'), { name: 'TimeoutError' })
    const read = backendReader('http://backend/api', 'abc', undefined, never(timeout))
    const failure = await read('/values', {}).catch((error: unknown) => error)
    expect(failure).toBeInstanceOf(UpstreamProblem)
    expect(failure).toMatchObject({ status: 504, retryAfter: 30, problem: { type: 'urn:wetterdienst:problem:upstream-timeout', request_id: 'abc' } })
  })

  it('is an abort, and no failure to tell, where the signal says nobody waits for it', async () => {
    const stopped = new AbortController()
    stopped.abort()
    const read = backendReader('http://backend/api', 'abc', stopped.signal, never(new Error('aborted')))
    await expect(read('/values', {})).rejects.toBeInstanceOf(AbortedError)
  })
})

describe('the stations route', () => {
  const ids = (body: { stations: Array<{ station_id: string }> }) => body.stations.map(station => station.station_id)

  it('lists the stations the temperature is made for: from the lists of TAVG, TMAX and TMIN, one after another, with the fields the picker reads', async () => {
    const result = await raw('/_ghcn/stations?kind=temperature')

    expect(result.status).toBe(200)
    const body = result.json()
    // the TAVG of 0002, the years TMAX and TMIN have in common at 0008 (0001 ended in 2020, 0003 has 9 years in common, 0004 has no TMIN)
    expect(ids(body)).toEqual(['USW00000002', 'USW00000008'])
    expect(body.stations[0]).toEqual({
      station_id: 'USW00000002',
      name: 'TAVG ONLY',
      region: 'NY',
      latitude: 41,
      longitude: -73.5,
      elevation: 42.7,
      wmo_id: null,
      start_timestamp: '1950-01-01T00:00:00.000000+00:00',
      end_timestamp: null,
    })
    expect(body.stations[1]).toMatchObject({ start_timestamp: '1970-01-01T00:00:00.000000+00:00', end_timestamp: `${stub.THIS_YEAR - 1}-12-31T00:00:00.000000+00:00` })
    // one request for each element, each for its own parameter, none of them together
    expect(seen.map(item => item.path)).toEqual(['/api/stations', '/api/stations', '/api/stations'])
    expect(seen.map(item => Object.fromEntries(item.query))).toEqual([
      { provider: 'noaa', network: 'ghcn', parameters: 'daily/data/temperature_air_mean_2m', all: 'true' },
      { provider: 'noaa', network: 'ghcn', parameters: 'daily/data/temperature_air_max_2m', all: 'true' },
      { provider: 'noaa', network: 'ghcn', parameters: 'daily/data/temperature_air_min_2m', all: 'true' },
    ])
    expect(result.headers.get('cache-control')).toBe('public, max-age=3600')
  })

  it('lists the stations the precipitation is made for from the one list of PRCP', async () => {
    const result = await raw('/_ghcn/stations?kind=precipitation')
    expect(ids(result.json())).toEqual(['USW00000006'])
    expect(seen.map(item => item.query.get('parameters'))).toEqual(['daily/data/precipitation_amount'])
  })

  it('keeps the list of a kind, and each kind has its own, so that the lists of the backend are read once for every browser', async () => {
    await raw('/_ghcn/stations?kind=temperature')
    await raw('/_ghcn/stations?kind=temperature')
    expect(seen).toHaveLength(3)
    await raw('/_ghcn/stations?kind=precipitation')
    expect(seen).toHaveLength(4)
  })

  it('reads the lists of a kind once for browsers that come while it reads', async () => {
    delayMs = 50
    const responses = await Promise.all([raw('/_ghcn/stations?kind=temperature'), raw('/_ghcn/stations?kind=temperature')])
    expect(responses.map(item => item.status)).toEqual([200, 200])
    expect(seen).toHaveLength(3)
  })

  it('refuses a kind that is none, or none given, as a 422, before anything is read', async () => {
    for (const path of ['/_ghcn/stations', '/_ghcn/stations?kind=wind']) {
      const result = await raw(path)
      expect(result.status).toBe(422)
      expect(result.json().errors[0].loc).toEqual(['query', 'kind'])
    }
    expect(seen).toHaveLength(0)
  })

  it('tells a failure of the backend as its own problem and keeps nothing of it', async () => {
    config.apiBase = `${closed}/api`
    expect((await raw('/_ghcn/stations?kind=temperature')).status).toBe(502)
    config.apiBase = `${backend}/api`
    expect((await raw('/_ghcn/stations?kind=temperature')).status).toBe(200)
  })

  it('tells a list that is no list as a 502', async () => {
    answer = (_request, response) => {
      response.writeHead(200, { 'content-type': 'application/json' })
      response.end(JSON.stringify({ hello: 'world' }))
    }
    expect((await raw('/_ghcn/stations?kind=precipitation')).status).toBe(502)
  })
})

describe('the stations that stripes are made for, from the lists of the elements', () => {
  const lists = (kind: 'temperature' | 'precipitation') => kind === 'temperature'
    ? { mean: stub.listOf('temperature_air_mean_2m'), max: stub.listOf('temperature_air_max_2m'), min: stub.listOf('temperature_air_min_2m') }
    : { amount: stub.listOf('precipitation_amount') }
  const idsOf = (kind: 'temperature' | 'precipitation', active: boolean) => stripesStationsOf(kind, lists(kind), stub.THIS_YEAR, active).map(station => station.station_id)

  // the cases of the backend's test of the listing (`test_the_stations_are_those_whose_record_can_reach_the_minimum_years`):
  // TAVG alone (0002), TMAX with TMIN (0001, 0008); 0003's TMAX and TMIN overlap for 9 years only, 0004 has TMAX only
  it.each([
    ['temperature', false, ['USW00000001', 'USW00000002', 'USW00000008']],
    ['temperature', true, ['USW00000002', 'USW00000008']],
    ['precipitation', false, ['USW00000001', 'USW00000005', 'USW00000006']],
    ['precipitation', true, ['USW00000006']],
  ] as const)('is, for %s and active %s, %j', (kind, active, expected) => {
    expect(idsOf(kind, active)).toEqual(expected)
  })

  it('gives the span of the kind, and no end for a station that still reports (the port of the backend\'s test of the listing)', () => {
    const rows = Object.fromEntries(stripesStationsOf('temperature', lists('temperature'), stub.THIS_YEAR, false).map(station => [station.station_id, station]))
    expect(rows.USW00000001).toMatchObject({ name: 'STUB STATION', start_timestamp: '1990-01-01T00:00:00.000000+00:00', end_timestamp: '2020-12-31T00:00:00.000000+00:00' })
    // the TAVG of 1950 to this year: its year has not ended
    expect(rows.USW00000002).toMatchObject({ start_timestamp: '1950-01-01T00:00:00.000000+00:00', end_timestamp: null })
  })

  it('takes the years TMAX and TMIN have in common, taken with TAVG from its earliest start to its latest end', () => {
    const at = (id: string, first: number, last: number | null) => ({ station_id: id, name: id, start_timestamp: `${first}-01-01T00:00:00+00:00`, end_timestamp: last === null ? null : `${last}-12-31T00:00:00+00:00` })
    const listed = stripesStationsOf('temperature', {
      mean: [at('a', 2000, 2005)],
      max: [at('a', 1980, 1999), at('b', 1950, 2000), at('c', 1990, 2000), at('only-max', 1900, null)],
      min: [at('a', 1990, 2010), at('b', 1960, 2010), at('c', 2001, 2020), at('only-min', 1900, null)],
    }, 2026)
    // a: TMAX 1980-1999 and TMIN 1990-2010 have 1990-1999 in common, with TAVG 2000-2005 that is 1990-2005 (16 years); b: 1960-2000, 41 years,
    // but it ended before last year; c: TMAX and TMIN do not meet, and it has no TAVG; a station in only one of the two has nothing
    expect(listed).toEqual([])
    const active = stripesStationsOf('temperature', { mean: [at('a', 2000, 2005)], max: [at('a', 1980, 1999), at('b', 1950, 2030), at('only-max', 1900, null)], min: [at('a', 1990, 2010), at('b', 1960, 2030), at('only-min', 1900, null)] }, 2026)
    expect(active.map(station => station.station_id)).toEqual(['b'])
    const whole = stripesStationsOf('temperature', { mean: [at('a', 2000, 2005)], max: [at('a', 1980, 1999), at('c', 1990, 2000)], min: [at('a', 1990, 2010), at('c', 2001, 2020)] }, 2026, false)
    expect(whole.map(station => [station.station_id, station.start_timestamp?.slice(0, 4), station.end_timestamp?.slice(0, 4)])).toEqual([['a', '1990', '2005']])
  })

  it.each([
    ['1950', null, true], // still reporting
    ['2017', null, true], // 2017 to the year that is running, 10 years in 2026
    ['2018', null, false], // 9
    ['1950', '2025', true], // reported last year
    ['1950', '2024', false], // stopped before last year
    ['2016', '2025', true],
    ['2017', '2025', false],
    [null, '2025', false],
    [null, null, false],
  ])('lists a record of %s to %s, in 2026: %s', (start, end, listed) => {
    const station = { station_id: 'x', start_timestamp: start === null ? null : `${start}-01-01T00:00:00+00:00`, end_timestamp: end === null ? null : `${end}-12-31T00:00:00+00:00` }
    expect(stripesStationsOf('precipitation', { amount: [station] }, 2026)).toHaveLength(listed ? 1 : 0)
  })
})
