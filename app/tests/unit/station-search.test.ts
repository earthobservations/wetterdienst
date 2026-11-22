import type { Server } from 'node:http'
import type { AddressInfo } from 'node:net'
import type { StationSearchAnswer } from '../../app/utils/station-search'
import { createServer } from 'node:http'
import { createRequire } from 'node:module'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { foldSpelled, prepareStations, searchPrepared } from '../../app/utils/station-search'
import { createGhcnMapList } from '../../server/utils/ghcnStations'
import { DEFAULT_LIMIT, MAX_LIMIT, parseSearchQuery, stationSearchHandler } from '../../server/utils/stationSearch'

// The stations the search of the header finds by name or number (GH-3790): the matching, and the route that matches the lists the server keeps.

const THIS_YEAR = new Date().getUTCFullYear()

/** A backend row as `GET /api/stations` gives it */
function row(station_id: string, name: string | null, wmo_id: string | null = null, end: number | null = null, latitude = 50, longitude = 10) {
  return { station_id, name, latitude, longitude, wmo_id, start_timestamp: '1950-01-01T00:00:00+00:00', end_timestamp: end === null ? null : `${end}-12-31T00:00:00+00:00` }
}

function columnsOf(rows: ReturnType<typeof row>[]) {
  return {
    count: rows.length,
    retrieved_at: null,
    station_id: rows.map(r => r.station_id),
    latitude: rows.map(r => r.latitude),
    longitude: rows.map(r => r.longitude),
    first_year: rows.map(() => 1950),
    last_year: rows.map(r => (r.end_timestamp ? Number(r.end_timestamp.slice(0, 4)) : null)),
    name: rows.map(r => r.name),
    wmo_id: rows.map(r => r.wmo_id),
  }
}

const reporting = (lastYear: number | null) => lastYear === null || lastYear >= THIS_YEAR - 1

const HAMBURG = prepareStations(columnsOf([
  row('02597', 'Hamburg-Billwerder', null, 1997),
  row('01975', 'Hamburg-Fuhlsbüttel', '10147'),
  row('04910', 'Neustadt (Hamburg-Mitte)', null, 2010),
  row('00044', 'Großenkneten', '10338'),
  row('00183', 'Arkona'),
  row('04911', 'St. Hamburger Hallig', null),
]), reporting)

describe('the matching of the stations', () => {
  it('ignores case and accents, as the search does, and wants every word, in any order', () => {
    expect(searchPrepared(HAMBURG, 'FUHLSBUTTEL hamburg', 5).stations.map(s => s.station_id)).toEqual(['01975'])
    // `ß` is `ss` in the lists that have no such letter, so either is found
    expect(searchPrepared(HAMBURG, 'grossenkneten', 5).total).toBe(1)
    expect(searchPrepared(HAMBURG, 'zzzenkneten', 5).total).toBe(0)
    expect(searchPrepared(HAMBURG, 'großenkneten', 5).total).toBe(1)
    expect(searchPrepared(HAMBURG, 'hamburg mitte', 5).stations.map(s => s.station_id)).toEqual(['04910'])
  })

  it('puts the names that start with the query first, then a word that starts, then a name that holds it, and a station that reports before one that has stopped', () => {
    const found = searchPrepared(HAMBURG, 'hamburg', 10)
    expect(found.total).toBe(4)
    // starts with it: Fuhlsbüttel reports, Billwerder stopped in 1997 (and the St. Hamburger one reports: it is a word that starts with it)
    expect(found.stations.map(s => s.station_id)).toEqual(['01975', '02597', '04911', '04910'])
    expect(found.stations.map(s => s.reporting)).toEqual([true, false, true, false])
  })

  it('returns the best few and says how many there are in all', () => {
    const found = searchPrepared(HAMBURG, 'hamburg', 2)
    expect(found.total).toBe(4)
    expect(found.stations.map(s => s.station_id)).toEqual(['01975', '02597'])
  })

  it('finds a station by its id or its WMO number, the number as the lists write it, and puts it first', () => {
    expect(searchPrepared(HAMBURG, '01975', 5).stations.map(s => s.station_id)).toEqual(['01975'])
    expect(searchPrepared(HAMBURG, '10147', 5).stations.map(s => s.station_id)).toEqual(['01975'])
    // 1975 is read as 01975, as the backend reads a WMO number
    const typed = searchPrepared(prepareStations(columnsOf([row('01001', 'Jan Mayen', '01001'), row('51001', 'Elsewhere')]), reporting), '1001', 5)
    expect(typed.stations.map(s => s.station_id)).toEqual(['01001', '51001'])
  })

  it('finds a name as the lists without umlauts spell it, and the other way round: München is MUENCHEN, and Fuhlsbüttel is not FUHLSBUTTEL', () => {
    expect(foldSpelled('Fuhlsbüttel STRASSE Groß ÄÖ')).toBe('fuhlsbuettel strasse gross aeoe')
    const list = prepareStations(columnsOf([row('10865', 'MUENCHEN-STADT'), row('01262', 'München-Flughafen'), row('99999', 'FUHLSBUETTEL'), row('00001', 'Fuhlsbüttel'), row('00002', 'Munchen Plain')]), reporting)
    const ids = (query: string) => searchPrepared(list, query, 10).stations.map(station => station.station_id).sort()
    // typed with the umlaut: the name with `ue`, with the umlaut and without any is found
    expect(ids('münchen')).toEqual(['00002', '01262', '10865'])
    // typed as the lists without umlauts have it: the name with the umlaut is found too
    expect(ids('muenchen')).toEqual(['01262', '10865'])
    expect(ids('Fuhlsbüttel')).toEqual(['00001', '99999'])
    expect(ids('fuhlsbuettel')).toEqual(['00001', '99999'])
    expect(searchPrepared(list, 'münchen flughafen', 10).stations.map(station => station.station_id)).toEqual(['01262'])
  })

  it('finds nothing for fewer than three characters, which would be every station', () => {
    expect(searchPrepared(HAMBURG, 'ha', 5)).toEqual({ total: 0, stations: [] })
    expect(searchPrepared(HAMBURG, '   ', 5)).toEqual({ total: 0, stations: [] })
  })

  it('carries what the search shows of a station', () => {
    const [first] = searchPrepared(HAMBURG, 'fuhlsbuttel', 1).stations
    expect(first).toEqual({ station_id: '01975', name: 'Hamburg-Fuhlsbüttel', latitude: 50, longitude: 10, wmo_id: '10147', first_year: 1950, last_year: null, reporting: true })
  })

  it('takes a station with no name by its id', () => {
    const list = prepareStations(columnsOf([row('USW00094728', null)]), reporting)
    expect(searchPrepared(list, 'usw000947', 5).stations.map(s => s.station_id)).toEqual(['USW00094728'])
  })

  it('searches 133k stations in a few milliseconds, folded once', () => {
    const many = columnsOf(Array.from({ length: 133_000 }, (_, i) => row(`GM${String(i).padStart(9, '0')}`, `STATION NUMBER ${i} OF THE LIST`, null, i % 3 ? null : 2001)))
    const list = prepareStations(many, reporting)
    const started = performance.now()
    const found = searchPrepared(list, 'number 1234', 4)
    const took = performance.now() - started
    expect(found.total).toBeGreaterThan(0)
    expect(took).toBeLessThan(250)
  })
})

describe('the query of the route', () => {
  it('wants a query of at most 100 characters and a limit of 1 to 10, and answers the problem as the backend does', () => {
    expect(parseSearchQuery({ q: ' hamburg ' })).toEqual({ q: 'hamburg', limit: DEFAULT_LIMIT })
    expect(parseSearchQuery({ q: 'a', limit: '10' })).toEqual({ q: 'a', limit: 10 })
    expect(parseSearchQuery({})).toEqual({ errors: [{ loc: ['query', 'q'], msg: 'Field required' }] })
    expect(parseSearchQuery({ q: 'x'.repeat(101) })).toMatchObject({ errors: [{ loc: ['query', 'q'] }] })
    for (const limit of ['0', `${MAX_LIMIT + 1}`, 'many', '-1', '1.5'])
      expect(parseSearchQuery({ q: 'x', limit })).toMatchObject({ errors: [{ loc: ['query', 'limit'] }] })
  })
})

// The handler as Nitro runs it: h3's own functions are its auto-imports, and so are the utilities.
const nuxtRequire = createRequire(createRequire(import.meta.url).resolve('nuxt/package.json'))
const h3 = nuxtRequire('h3') as typeof import('h3')

const BACKEND = 'http://backend.internal:7890/api'

describe('the route', () => {
  const servers: Server[] = []
  afterEach(async () => {
    await Promise.all(servers.splice(0).map(server => new Promise(resolve => server.close(resolve))))
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  const FORECAST = [row('10147', 'HAMBURG-FUHLSBUETTEL', '10147'), row('10148', 'HAMBURG-NEUWIEDENTHAL'), ...Array.from({ length: 600 }, (_, i) => row(`X${i}`, `OTHER ${i}`))]
  const MEASURED = [row('01975', 'Hamburg-Fuhlsbüttel', '10147'), row('02597', 'Hamburg-Billwerder', null, 1997), ...Array.from({ length: 600 }, (_, i) => row(`M${i}`, `ELSEWHERE ${i}`))]
  const GHCN = [row('GM000010147', 'HAMBURG-FUHLSBUETTEL', '10147'), row('USC00123456', 'HAMBURG', null, 1980), ...Array.from({ length: 600 }, (_, i) => row(`G${i}`, `PLACE ${i}`))]

  const bodyOf = (rows: ReturnType<typeof row>[]) => new Response(JSON.stringify({ metadata: { retrieved_at: 'then' }, stations: rows }), { headers: { 'content-type': 'application/json' } })

  /** A server with the route on it and the backend answering from `answerFor` (what each list's path is asked for is counted) */
  async function serve(answerFor: (path: string) => Response | Promise<Response>, waitMs = 2000) {
    for (const [name, value] of Object.entries({
      defineEventHandler: h3.defineEventHandler,
      getQuery: h3.getQuery,
      getRequestHeader: h3.getRequestHeader,
      setResponseHeader: h3.setResponseHeader,
      setResponseStatus: h3.setResponseStatus,
      useRuntimeConfig: () => ({ apiBase: BACKEND }),
    }))
      vi.stubGlobal(name, value)
    const asked: string[] = []
    const fetcher = vi.fn(async (url: string) => {
      const path = url.replace(BACKEND, '')
      asked.push(path)
      return answerFor(path)
    })
    const options = { apiBase: () => BACKEND, fetcher: fetcher as unknown as typeof fetch, minimum: 500, waitMs }
    const app = h3.createApp()
    app.use(stationSearchHandler({ ...options, ghcn: createGhcnMapList(options) }))
    const server = createServer(h3.toNodeListener(app))
    servers.push(server)
    const origin = await new Promise<string>(resolve => server.listen(0, '127.0.0.1', () => resolve(`http://127.0.0.1:${(server.address() as AddressInfo).port}`)))
    return { asked, get: (query: string) => fetch(`${origin}/?${query}`) }
  }

  const ofPath = (path: string) => path.includes('network=mosmix') ? FORECAST : path.includes('network=ghcn') ? GHCN : MEASURED

  it('answers the best stations of each of the three networks, and how many there are, from one read of each list', async () => {
    const { asked, get } = await serve(path => bodyOf(ofPath(path)))
    const first = await get('q=hamburg&limit=1')
    expect(first.status).toBe(200)
    const answer = await first.json() as StationSearchAnswer
    expect(answer.networks.map(n => [n.network, n.total, n.stations.map(s => s.station_id)])).toEqual([
      ['forecast', 2, ['10147']],
      ['measured', 2, ['01975']],
      ['ghcn', 2, ['GM000010147']],
    ])
    expect(answer.pending).toEqual([])
    expect(answer.failed).toEqual([])
    expect(first.headers.get('cache-control')).toBe('private, max-age=300')
    await get('q=billwerder')
    expect(asked).toHaveLength(3)
    expect(asked.some(path => path.includes('network=mosmix'))).toBe(true)
  })

  it('leaves out a network that has no station for the query', async () => {
    const { get } = await serve(path => bodyOf(ofPath(path)))
    const answer = await (await get('q=billwerder')).json() as StationSearchAnswer
    expect(answer.networks.map(n => n.network)).toEqual(['measured'])
  })

  it('names the lists that could not be read and answers the others, with no copy kept by a cache', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    const { get, asked } = await serve(path => path.includes('network=ghcn') ? new Response('down', { status: 503 }) : bodyOf(ofPath(path)))
    const response = await get('q=hamburg')
    const answer = await response.json() as StationSearchAnswer
    expect(answer.failed).toEqual(['ghcn'])
    expect(answer.networks.map(n => n.network)).toEqual(['forecast', 'measured'])
    expect(response.headers.get('cache-control')).toBe('no-store')
    // the backend is not asked again at every keystroke after a failure
    await get('q=hamburg')
    expect(asked.filter(path => path.includes('network=ghcn'))).toHaveLength(1)
  })

  it('does not hold the answer for a list that is slow, says it is still being read, and has it on the next request', async () => {
    let release: (() => void) | undefined
    const slow = new Promise<void>((resolve) => {
      release = resolve
    })
    const { get } = await serve(async (path) => {
      if (path.includes('network=ghcn'))
        await slow
      return bodyOf(ofPath(path))
    }, 50)
    const first = await (await get('q=hamburg')).json() as StationSearchAnswer
    expect(first.pending).toEqual(['ghcn'])
    expect(first.networks.map(n => n.network)).toEqual(['forecast', 'measured'])
    release!()
    await vi.waitFor(async () => {
      const next = await (await get('q=hamburg')).json() as StationSearchAnswer
      expect(next.pending).toEqual([])
      expect(next.networks.map(n => n.network)).toContain('ghcn')
    })
  })

  it('answers a request with no query, or too long a one, as the backend answers an invalid one: a 422 problem', async () => {
    const { get } = await serve(path => bodyOf(ofPath(path)))
    const response = await get('limit=2')
    expect(response.status).toBe(422)
    expect(response.headers.get('content-type')).toContain('application/problem+json')
    const problem = await response.json() as { type: string, detail: string, request_id: string }
    expect(problem.type).toBe('urn:wetterdienst:problem:invalid-parameters')
    expect(problem.detail).toContain('q: Field required')
    expect(problem.request_id).toBeTruthy()
  })
})
