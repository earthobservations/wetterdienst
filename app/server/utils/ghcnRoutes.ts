import type { AnnualKind } from './ghcnAnnual'
import type { BackendRead } from './ghcnStripes'
import { useApiBase } from './apiBase'
import { backendReader, GHCN_TTL_MS, GHCN_UNIT_TYPE, readGhcnAnnual, readGhcnStations, UpstreamProblem } from './ghcnStripes'
import { requestIdOf } from './requestId'
import { createLimiter, TtlCache } from './ttlCache'

// The two routes of the app's own server that the climate stripes of NOAA's GHCN daily are made from (GH-4258). They are not
// under `/api`, which the app proxies to the backend as it is (`server/api/[...].get.ts`): what they answer is the app's own,
// calculated from what the backend's generic API answers.
//
// - `GET /_ghcn/annual?kind=temperature&station=USW00094728&unit_targets={"temperature":"degree_celsius"}`: the annual values
//   of a station, built from its daily ones by the WMO rules.
// - `GET /_ghcn/stations`: the stations that have a record long enough for stripes and still report.
//
// Both keep what they worked out for `GHCN_TTL_MS` in the memory of the process; see `ttlCache.ts` for the bounds. Both count
// against the rate limit of the server (`server/utils/rateLimit.ts`), as each is a read of the backend.

type Reader = (apiBase: string, requestId: string) => BackendRead

/** How many stations' years the server keeps: a station's are a few kilobytes, so about 10 MB at most */
const ANNUAL_ENTRIES = 1000
/** How many reads of the backend run side by side: a station's days are up to 25 MB of JSON, and the list of GHCN 43 MB */
const CONCURRENT_READS = 4
/** What a browser keeps an answer for: the listing and a station's years change, at the soonest, with the night's files of NOAA */
const BROWSER_MAX_AGE_SECONDS = 3600

const KINDS: readonly string[] = ['temperature', 'precipitation']
/** An id of GHCN, which is letters, digits, `-` and `_`, as `USW00094728`, `CMU55-00161` and `GLUHALLEY-2` are */
const STATION_ID = /^[\w.-]{1,40}$/
const UNIT_NAME = /^[a-z][a-z_]{0,39}$/i

interface ParameterError {
  loc: string[]
  msg: string
}

function invalid(errors: ParameterError[]): UpstreamProblem {
  return new UpstreamProblem(422, {
    type: 'urn:wetterdienst:problem:invalid-parameters',
    title: 'Unprocessable Content',
    status: 422,
    detail: errors.map(error => `${error.loc.slice(1).join('.')}: ${error.msg}`).join('\n'),
    errors,
  })
}

/** What a request for the annual values names, or the 422 that says what is wrong with it */
export function parseAnnualQuery(query: Record<string, unknown>): { kind: AnnualKind, station: string, unitTargets?: Record<string, string> } {
  const errors: ParameterError[] = []
  const kind = typeof query.kind === 'string' ? query.kind : ''
  const station = typeof query.station === 'string' ? query.station : ''
  if (!KINDS.includes(kind))
    errors.push({ loc: ['query', 'kind'], msg: kind ? `Input should be 'temperature' or 'precipitation'` : 'Field required' })
  if (!station)
    errors.push({ loc: ['query', 'station'], msg: 'Field required' })
  else if (!STATION_ID.test(station))
    errors.push({ loc: ['query', 'station'], msg: 'Input should be the id of a station of GHCN daily' })
  let unit: string | undefined
  if (query.unit_targets !== undefined && query.unit_targets !== '') {
    try {
      const parsed = JSON.parse(String(query.unit_targets)) as unknown
      const entries = parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? Object.entries(parsed) : null
      const wanted = GHCN_UNIT_TYPE[kind as AnnualKind]
      if (!entries || entries.some(([type, name]) => type !== wanted || typeof name !== 'string' || !UNIT_NAME.test(name)))
        errors.push({ loc: ['query', 'unit_targets'], msg: `Input should be a mapping of ${wanted ? `'${wanted}'` : 'the quantity'} to a unit name` })
      else
        unit = entries[0]?.[1] as string | undefined
    }
    catch {
      errors.push({ loc: ['query', 'unit_targets'], msg: 'Input should be a valid JSON object' })
    }
  }
  if (errors.length)
    throw invalid(errors)
  return { kind: kind as AnnualKind, station, ...(unit ? { unitTargets: { [GHCN_UNIT_TYPE[kind as AnnualKind]]: unit } } : {}) }
}

interface Handlers {
  /** Reads the backend, as `backendReader` does; the tests give another */
  reader?: Reader
}

/** Answers a failure as the proxy of `/api` answers one: the problem, its status, and the request's id */
function answerProblem(event: Parameters<Parameters<typeof defineEventHandler>[0]>[0], failure: unknown, requestId: string): unknown {
  if (!(failure instanceof UpstreamProblem))
    throw failure
  const problem = { instance: `urn:wetterdienst:request:${requestId}`, request_id: requestId, ...failure.problem }
  setResponseStatus(event, failure.status)
  setResponseHeader(event, 'content-type', 'application/problem+json')
  setResponseHeader(event, 'x-request-id', requestId)
  if (failure.retryAfter)
    setResponseHeader(event, 'retry-after', failure.retryAfter)
  return problem
}

function allowBrowserToKeep(event: Parameters<Parameters<typeof defineEventHandler>[0]>[0], requestId: string) {
  setResponseHeader(event, 'cache-control', `public, max-age=${BROWSER_MAX_AGE_SECONDS}`)
  setResponseHeader(event, 'x-request-id', requestId)
}

/** The handler of `GET /_ghcn/annual` */
export function ghcnAnnualHandler({ reader = backendReader }: Handlers = {}) {
  const cache = new TtlCache<GhcnAnnualAnswer>({ ttlMs: GHCN_TTL_MS, maxEntries: ANNUAL_ENTRIES })
  const limit = createLimiter(CONCURRENT_READS)
  return defineEventHandler(async (event) => {
    const requestId = requestIdOf(getRequestHeader(event, 'x-request-id'))
    try {
      const { kind, station, unitTargets } = parseAnnualQuery(getQuery(event))
      const key = [kind, station, JSON.stringify(unitTargets ?? {})].join('|')
      const answer = await cache.get(key, () => limit(() => readGhcnAnnual(reader(useApiBase(), requestId), { kind, station, unitTargets })))
      allowBrowserToKeep(event, requestId)
      return answer
    }
    catch (failure) {
      return answerProblem(event, failure, requestId)
    }
  })
}

/** The handler of `GET /_ghcn/stations` */
export function ghcnStationsHandler({ reader = backendReader }: Handlers = {}) {
  const cache = new TtlCache<Station[]>({ ttlMs: GHCN_TTL_MS, maxEntries: 1 })
  const limit = createLimiter(CONCURRENT_READS)
  return defineEventHandler(async (event) => {
    const requestId = requestIdOf(getRequestHeader(event, 'x-request-id'))
    try {
      const stations = await cache.get('stations', () => limit(() => readGhcnStations(reader(useApiBase(), requestId))))
      allowBrowserToKeep(event, requestId)
      return { stations }
    }
    catch (failure) {
      return answerProblem(event, failure, requestId)
    }
  })
}
