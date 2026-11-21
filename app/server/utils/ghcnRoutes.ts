import type { AnnualKind } from './ghcnAnnual'
import type { BackendRead } from './ghcnStripes'
import { useApiBase } from './apiBase'
import { backendReader, GHCN_TTL_MS, GHCN_UNIT_TYPE, readGhcnAnnual, readGhcnStations, UpstreamProblem } from './ghcnStripes'
import { requestIdOf } from './requestId'
import { AbortedError, createLimiter, QueueFullError, QueueTimeoutError, TtlCache } from './ttlCache'

// The two routes of the app's own server that the climate stripes of NOAA's GHCN daily are made from (GH-4258). They are not
// under `/api`, which the app proxies to the backend as it is (`server/api/[...].get.ts`): what they answer is the app's own,
// calculated from what the backend's generic API answers.
//
// - `GET /_ghcn/annual?kind=temperature&station=USW00094728&unit_targets={"temperature":"degree_celsius"}`: the annual values
//   of a station, built from its daily ones by the WMO rules.
// - `GET /_ghcn/stations?kind=temperature`: the stations that have a record long enough for stripes of the kind and still report,
//   made of the lists the backend gives for each element of the kind.
//
// Both keep what they worked out for `GHCN_TTL_MS` in the memory of the process; see `ttlCache.ts` for the bounds. Both count
// against the rate limit of the server (`server/utils/rateLimit.ts`), as each is a read of the backend.

type Reader = (apiBase: string, requestId: string, signal?: AbortSignal) => BackendRead

/** How many stations' years the server keeps: a station's are a few kilobytes, so about 10 MB at most */
const ANNUAL_ENTRIES = 1000
/** How many reads of the backend run side by side: a station's days are up to 25 MB of JSON, and a list of GHCN stations 8 to 21 MB */
const CONCURRENT_READS = 4
/** How many reads may wait for their turn: a read is up to 25 MB of JSON, so the ones waiting hold a client each and nothing else; one more is a 503 */
const MAX_WAITING_READS = 16
/** How long a read may wait for its turn, in milliseconds, before it is a 503 and its place is given up */
const MAX_WAIT_MS = 30_000
/** What a refused read is told to wait, in seconds */
const BUSY_RETRY_AFTER_SECONDS = 10
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

/** What a request for the stations names: the kind, or the 422 that says what is wrong with it */
export function parseKindQuery(query: Record<string, unknown>): { kind: AnnualKind } {
  const kind = typeof query.kind === 'string' ? query.kind : ''
  if (!KINDS.includes(kind))
    throw invalid([{ loc: ['query', 'kind'], msg: kind ? `Input should be 'temperature' or 'precipitation'` : 'Field required' }])
  return { kind: kind as AnnualKind }
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
function answerProblem(event: Parameters<Parameters<typeof defineEventHandler>[0]>[0], raised: unknown, requestId: string): unknown {
  // the client has gone: nobody is left to tell
  if (raised instanceof AbortedError)
    return undefined
  // the queue of reads is full, or the read waited too long: the server is busy, which passes
  const failure = raised instanceof QueueFullError || raised instanceof QueueTimeoutError
    ? new UpstreamProblem(503, { type: 'urn:wetterdienst:problem:server-busy', title: 'Service Unavailable', status: 503, detail: 'The server is busy reading other stations. Try again in a moment.' }, BUSY_RETRY_AFTER_SECONDS)
    : raised
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

/** Aborts where the client closes the connection before the answer is sent: the reads it alone waits for are given up */
function closedBy(event: Parameters<Parameters<typeof defineEventHandler>[0]>[0]): AbortSignal {
  const controller = new AbortController()
  event.node.res.once('close', () => {
    if (!event.node.res.writableEnded)
      controller.abort()
  })
  return controller.signal
}

/**
 * The queue of reads of the backend, one for the process: the annual values and the lists of stations are read through it, so at
 * most `CONCURRENT_READS` run at once across both routes. It cannot deadlock: a read holds a place only while it runs, and no read
 * waits for another (a list is read in turns, each one asking for its own place, and an annual read waits for nothing).
 */
const limit = createLimiter(CONCURRENT_READS, { maxWaiting: MAX_WAITING_READS, maxWaitMs: MAX_WAIT_MS })

/** The handler of `GET /_ghcn/annual` */
export function ghcnAnnualHandler({ reader = backendReader }: Handlers = {}) {
  const cache = new TtlCache<GhcnAnnualAnswer>({ ttlMs: GHCN_TTL_MS, maxEntries: ANNUAL_ENTRIES })
  return defineEventHandler(async (event) => {
    const requestId = requestIdOf(getRequestHeader(event, 'x-request-id'))
    const closed = closedBy(event)
    try {
      const { kind, station, unitTargets } = parseAnnualQuery(getQuery(event))
      const key = [kind, station, JSON.stringify(unitTargets ?? {})].join('|')
      const apiBase = useApiBase()
      const answer = await cache.get(key, signal => limit(() => readGhcnAnnual(reader(apiBase, requestId, signal), { kind, station, unitTargets }), signal), closed)
      allowBrowserToKeep(event, requestId)
      return answer
    }
    catch (failure) {
      return answerProblem(event, failure, requestId)
    }
  })
}

/** The handler of `GET /_ghcn/stations?kind=temperature` */
export function ghcnStationsHandler({ reader = backendReader }: Handlers = {}) {
  // one list for each kind, which is read as one list of each element it is made of, one after another
  const cache = new TtlCache<Station[]>({ ttlMs: GHCN_TTL_MS, maxEntries: KINDS.length })
  return defineEventHandler(async (event) => {
    const requestId = requestIdOf(getRequestHeader(event, 'x-request-id'))
    const closed = closedBy(event)
    try {
      const { kind } = parseKindQuery(getQuery(event))
      const apiBase = useApiBase()
      const stations = await cache.get(kind, (signal) => {
        const read = reader(apiBase, requestId, signal)
        // each read of a list waits for its turn, so the lists of a kind are never read side by side, and the queue is the annual values' too
        return readGhcnStations((path, query) => limit(() => read(path, query), signal), kind)
      }, closed)
      allowBrowserToKeep(event, requestId)
      return { stations }
    }
    catch (failure) {
      return answerProblem(event, failure, requestId)
    }
  })
}
