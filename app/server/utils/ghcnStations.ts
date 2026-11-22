import type { H3Event } from 'h3'
import type { GhcnStationColumns } from '../../shared/types/ghcn-stations'
import { createHash } from 'node:crypto'
import { describeUnreadable, describeWrongKind, HTML_TYPE, UNEXPECTED_ANSWER_TYPE } from '../../app/utils/api-answer'
import { useApiBase } from './apiBase'

// The list of the stations of NOAA GHCN daily that the map shows (GH-4267), made from the backend's own answer for
// `noaa/ghcn` (133k stations, 44 MB of JSON, 3.8 MB gzipped, 3 s) as the columns the map needs, so that the browser asks
// for 2 MB once and not for the 44 MB. `ghcnMapStationsHandler` keeps it for a day; the route is `server/routes/_ghcn/map-stations.get.ts`,
// outside `/api`, which is the backend's namespace and is proxied to it as it is (the rate limit counts every route of `/_ghcn/`).

/** What the backend is asked for: the whole network, every station with its first and last year */
export const GHCN_STATIONS_PATH = '/stations?provider=noaa&network=ghcn&parameters=daily/data&all=true'

/**
 * How long the backend may take: it answers in 3 s with a warm cache, and a cold one reads and parses NOAA's list first (a minute at
 * the most). The client of the route waits for longer than this (the e2e spec's 120 s), so that the 502 of a backend that is slower
 * than this reaches it, and the person's Retry is not the browser's own timeout.
 */
const BACKEND_TIMEOUT_MS = 90_000
/**
 * The fewest stations a list may have to be kept: NOAA's has 132,894, and a list of less than half of it is a broken answer (a
 * partial read of the source), which must not be the layer for a day.
 */
export const MIN_STATIONS = 50_000
const RETRY_AFTER_SECONDS = 30
// the kind of a backend that cannot be reached, as the proxy at `server/api/[...].get.ts` writes it
const BACKEND_UNREACHABLE_TYPE = 'urn:wetterdienst:problem:backend-unreachable'

interface BackendStation {
  station_id?: unknown
  latitude?: unknown
  longitude?: unknown
  name?: unknown
  start_timestamp?: unknown
  end_timestamp?: unknown
  wmo_id?: unknown
}

/** The problem the route answers with where it has no list to give: its status, and the body in the words of the backend's own */
export interface GhcnProblem {
  status: number
  headers: Record<string, string>
  body: { type: string, title: string, status: number, detail: string, instance: string, request_id: string }
}

function yearOf(timestamp: unknown): number | null {
  const year = typeof timestamp === 'string' ? Number.parseInt(timestamp.slice(0, 4), 10) : Number.NaN
  return Number.isNaN(year) ? null : year
}

/**
 * The columns of a list of stations: the ones with a position (a map can show no other), in the backend's order, the year of
 * the first and the last value read from the timestamps (null where the backend gives none), and the WMO number where it has one.
 *
 * @param stations - The `stations` of the backend's answer for `noaa/ghcn`
 * @param retrievedAt - When the backend made it
 * @returns The columns, `count` long
 */
export function compactGhcnStations(stations: BackendStation[], retrievedAt: string | null = null): GhcnStationColumns {
  const columns: GhcnStationColumns = { count: 0, retrieved_at: retrievedAt, station_id: [], latitude: [], longitude: [], first_year: [], last_year: [], name: [], wmo_id: [] }
  for (const station of stations) {
    if (typeof station.station_id !== 'string' || typeof station.latitude !== 'number' || typeof station.longitude !== 'number')
      continue
    columns.station_id.push(station.station_id)
    columns.latitude.push(station.latitude)
    columns.longitude.push(station.longitude)
    columns.first_year.push(yearOf(station.start_timestamp))
    columns.last_year.push(yearOf(station.end_timestamp))
    columns.name.push(typeof station.name === 'string' ? station.name : null)
    columns.wmo_id.push(typeof station.wmo_id === 'string' && station.wmo_id.trim() ? station.wmo_id.trim() : null)
  }
  columns.count = columns.station_id.length
  return columns
}

function problem(status: number, type: string, title: string, detail: string, requestId: string): GhcnProblem {
  return {
    status,
    headers: {
      'content-type': 'application/problem+json',
      'x-request-id': requestId,
      ...(status === 502 || status === 503 || status === 504 ? { 'retry-after': String(RETRY_AFTER_SECONDS) } : {}),
    },
    body: { type, title, status, detail, instance: `urn:wetterdienst:request:${requestId}`, request_id: requestId },
  }
}

/**
 * What a list of stations is read from, and how it is named in a log line and in a problem: `path` is the backend's, and
 * `what` and `network` complete the sentences (`for the GHCN stations`, `for NOAA GHCN daily`).
 */
export interface StationSource {
  path: string
  what: string
  network: string
}

const GHCN_SOURCE: StationSource = { path: GHCN_STATIONS_PATH, what: 'the GHCN stations', network: 'NOAA GHCN daily' }

/**
 * Asks the backend for the stations of GHCN daily and makes the columns of them, or says why it cannot: never a list that is
 * empty or partial for want of an answer, which the route would keep for a day. The backend that cannot be reached, a body that
 * cannot be read to its end, a page of HTML or a text that is no JSON for its answer, JSON of another form, a list of fewer than
 * `minimum` stations, and the backend's own error (its problem, with its status) are each a problem of a 5xx or the backend's
 * status, which is no cache entry.
 *
 * @param apiBase - The backend's `/api` URL
 * @param requestId - The id the request is known by in the backend's log and in the problem
 * @param fetcher - `fetch`, or the one that stands in for it
 * @param minimum - The fewest stations of a list that is kept
 * @returns The columns, or the problem to answer with
 */
export function readGhcnMapStations(apiBase: string, requestId: string, fetcher: typeof fetch = globalThis.fetch, minimum = MIN_STATIONS): Promise<GhcnStationColumns | GhcnProblem> {
  return readStationColumns(apiBase, GHCN_SOURCE, requestId, fetcher, minimum)
}

/**
 * {@link readGhcnMapStations} for any list of stations the backend gives: the same checks, the same problems. The lists that
 * the search of the app reads (the forecast's points and the stations that measure, GH-3790) are read through it.
 *
 * @param apiBase - The backend's `/api` URL
 * @param source - Which list, and the words it is named by
 * @param requestId - The id the request is known by in the backend's log and in the problem
 * @param fetcher - `fetch`, or the one that stands in for it
 * @param minimum - The fewest stations of a list that is kept
 * @returns The columns, or the problem to answer with
 */
export async function readStationColumns(apiBase: string, source: StationSource, requestId: string, fetcher: typeof fetch = globalThis.fetch, minimum = MIN_STATIONS): Promise<GhcnStationColumns | GhcnProblem> {
  let response: Response
  try {
    response = await fetcher(`${apiBase}${source.path}`, { headers: { 'x-request-id': requestId }, signal: AbortSignal.timeout(BACKEND_TIMEOUT_MS) })
  }
  catch (failure) {
    // the cause names the backend's host and port: for whoever runs the app, in the log, not in the answer
    console.error(`Request ${requestId} to the backend for ${source.what} failed:`, (failure as { cause?: unknown })?.cause ?? failure)
    return problem(502, BACKEND_UNREACHABLE_TYPE, 'Bad Gateway', 'The backend could not be reached. The cause is in the server log.', requestId)
  }
  const contentType = response.headers.get('content-type')
  let text: string
  try {
    text = await response.text()
  }
  catch (failure) {
    // a reset, or the timeout, part-way through the body: the answer is not an empty one, and says what it is
    console.error(`Request ${requestId} to the backend for ${source.what} could not be read to its end:`, (failure as { cause?: unknown })?.cause ?? failure)
    return problem(502, UNEXPECTED_ANSWER_TYPE, 'Bad Gateway', 'The answer of the API could not be read to its end. The cause is in the server log.', requestId)
  }
  if (!response.ok) {
    // the backend's own problem is kept as it is, with its status
    try {
      const sent = JSON.parse(text) as GhcnProblem['body']
      if (sent && typeof sent.type === 'string' && typeof sent.detail === 'string')
        return { ...problem(response.status, sent.type, sent.title, sent.detail, sent.request_id || requestId), body: { ...sent, status: response.status } }
    }
    catch {}
    return problem(502, UNEXPECTED_ANSWER_TYPE, 'Bad Gateway', `The backend answered ${response.status} for the stations.`, requestId)
  }
  if (HTML_TYPE.test(contentType ?? '')) {
    console.error(`Request ${requestId} to the backend for ${source.what} was answered with ${contentType}, not the list of stations.`)
    return problem(502, UNEXPECTED_ANSWER_TYPE, 'Bad Gateway', describeWrongKind(contentType), requestId)
  }
  let answer: { stations?: unknown, metadata?: { retrieved_at?: string } } | null
  try {
    answer = JSON.parse(text)
  }
  catch (failure) {
    console.error(`Request ${requestId} to the backend for ${source.what} was not valid JSON:`, failure)
    return problem(502, UNEXPECTED_ANSWER_TYPE, 'Bad Gateway', describeUnreadable(contentType), requestId)
  }
  if (!answer || !Array.isArray(answer.stations)) {
    console.error(`Request ${requestId} to the backend for ${source.what} had no list of stations.`)
    return problem(502, UNEXPECTED_ANSWER_TYPE, 'Bad Gateway', 'The answer of the API does not have the form of this endpoint: no list of `stations`.', requestId)
  }
  const columns = compactGhcnStations(answer.stations as BackendStation[], answer.metadata?.retrieved_at ?? null)
  // the network has 133k stations: none, or a part of them, is an answer that is not the list, which a day of cache would keep
  if (columns.count < Math.max(1, minimum)) {
    console.error(`Request ${requestId} to the backend for ${source.what} was answered with ${columns.count} stations, fewer than the ${minimum} of a whole list.`)
    return problem(502, UNEXPECTED_ANSWER_TYPE, 'Bad Gateway', `The backend answered with ${columns.count} stations for ${source.network}, a part of its list.`, requestId)
  }
  return columns
}

/** How long a list is kept, and the day that a shared cache in front of the app may keep it for too */
const MAX_AGE_SECONDS = 24 * 60 * 60
/** How long after a failure the backend is not asked again: the problem is answered again, or the stale list served */
const RETRY_AFTER_FAILURE_MS = RETRY_AFTER_SECONDS * 1000

/** A list the server keeps, with when it was made */
export interface KeptList<V> {
  value: V
  modified: Date
  madeAt: number
}

/**
 * What a request for a kept list is answered with: the list, the problem (with the time that is left of the back-off, where it is
 * that), or, where the list is still being made after `waitMs`, that it is
 */
export type KeeperAnswer<V> = { kept: KeptList<V> } | { problem: GhcnProblem, waitSeconds?: number } | { pending: true }

export interface ListKeeperOptions<V> {
  /** Reads the list from the backend: the value to keep, or the problem it cannot be made of */
  read: (requestId: string) => Promise<V | GhcnProblem>
  now?: () => number
  /** What the list is called in a log line (`the GHCN stations`) */
  what?: string
}

function isProblem(read: unknown): read is GhcnProblem {
  return typeof read === 'object' && read !== null && 'body' in read && 'headers' in read && 'status' in read
}

/**
 * A list of the backend that the server keeps in memory for a day, as {@link ghcnMapStationsHandler} keeps its own (and the search
 * of the app, GH-3790, keeps the three lists it matches the same way). The first request makes it (the others that come meanwhile
 * wait for the same read); once the day is over the list in hand is served still and the next is made behind it
 * (stale-while-revalidate). A failure is nobody's list: it is not kept, and for 30 s after it the backend is not asked again at
 * every request (a read of it is 44 MB for GHCN daily): the problem is answered again with the time that is left, or the list in hand
 * is served, whose refresh waits as long.
 *
 * @param options - How the list is read, and what a test stands in for
 * @returns `get`, which answers a request, and `peek`, which gives what is kept without asking
 */
export function createListKeeper<V>(options: ListKeeperOptions<V>) {
  const now = options.now ?? Date.now
  const what = options.what ?? 'the stations'
  let kept: KeptList<V> | null = null
  let pending: Promise<GhcnProblem | null> | null = null
  /** The failure that the next requests are answered with until `backoffUntil`, and no request is made to the backend before it */
  let failure: GhcnProblem | null = null
  let backoffUntil = 0

  /** Makes the list (once, whoever asks while it is made): null where it is kept, else the problem */
  function make(requestId: string): Promise<GhcnProblem | null> {
    pending ??= (async () => {
      let read: V | GhcnProblem
      try {
        read = await options.read(requestId)
      }
      catch (unexpected) {
        // nothing the reader does not catch is allowed to reject what the requests wait for, or to be nobody's to handle
        console.error(`Request ${requestId} for ${what} failed unexpectedly:`, unexpected)
        read = problem(502, UNEXPECTED_ANSWER_TYPE, 'Bad Gateway', 'The list of the stations could not be made. The cause is in the server log.', requestId)
      }
      if (isProblem(read)) {
        failure = read
        backoffUntil = now() + RETRY_AFTER_FAILURE_MS
        return read
      }
      kept = { value: read, modified: new Date(now()), madeAt: now() }
      failure = null
      backoffUntil = 0
      return null
    })().finally(() => {
      pending = null
    })
    return pending
  }

  /**
   * The list for a request. `waitMs` is how long to wait for a list that is being made: past it the answer is `pending`, and the
   * list is made on (the search answers the stations it has and asks again, a list of 133k stations being a minute at the most).
   */
  async function get(requestId: string, { waitMs }: { waitMs?: number } = {}): Promise<KeeperAnswer<V>> {
    if (!kept) {
      // the backend failed a moment ago: it is not asked again for every page view
      if (failure && now() < backoffUntil)
        return { problem: failure, waitSeconds: Math.max(1, Math.ceil((backoffUntil - now()) / 1000)) }
      const making = make(requestId)
      let failed: GhcnProblem | null | 'late'
      if (waitMs === undefined) {
        failed = await making
      }
      else {
        let timer: ReturnType<typeof setTimeout> | undefined
        failed = await Promise.race([making, new Promise<'late'>((resolve) => {
          timer = setTimeout(resolve, waitMs, 'late')
        })])
        clearTimeout(timer)
      }
      if (failed === 'late')
        return { pending: true }
      if (failed)
        return { problem: failed }
    }
    else if (now() - kept.madeAt >= MAX_AGE_SECONDS * 1000 && !pending && now() >= backoffUntil) {
      void make(requestId)
    }
    return { kept: kept! }
  }

  return { get, peek: () => kept }
}

export interface GhcnHandlerOptions {
  apiBase?: () => string
  fetcher?: typeof fetch
  now?: () => number
  /** The fewest stations of a list that is kept (`MIN_STATIONS`) */
  minimum?: number
  /** The list the route serves, where it is shared with another route (the search, GH-3790): `sharedGhcnMapList` */
  list?: GhcnMapList
}

/** The list as it is kept: the columns, and the text that is sent, made once, so that a request does not make 8 MB of it again */
export interface GhcnMapListEntry {
  columns: GhcnStationColumns
  text: string
  etag: string
}

export type GhcnMapList = ReturnType<typeof createGhcnMapList>

/** The kept list of the stations of GHCN daily, made as the route and the search of the app read it */
export function createGhcnMapList(options: Omit<GhcnHandlerOptions, 'list'> = {}) {
  const apiBase = options.apiBase ?? useApiBase
  return createListKeeper<GhcnMapListEntry>({
    now: options.now,
    what: 'the GHCN stations',
    read: async (requestId) => {
      const read = await readGhcnMapStations(apiBase(), requestId, options.fetcher, options.minimum)
      if ('body' in read)
        return read
      const text = JSON.stringify(read)
      return { columns: read, text, etag: `W/"${createHash('sha1').update(text).digest('base64url')}"` }
    },
  })
}

/** The one list of the process, which the route `/_ghcn/map-stations` and the search `/_search/stations` both read: one read of the backend (44 MB) serves both */
export const sharedGhcnMapList: GhcnMapList = createGhcnMapList()

/**
 * The handler of `GET /_ghcn/map-stations`: the list of the stations as columns, kept in the memory of the process for a day (see
 * {@link createListKeeper} for how a failure and a stale list are handled). It is sent as the text it was made as, with an `ETag`, so
 * that a repeated request is answered 304 and a hit costs no more than sending it.
 *
 * A failure is answered with its problem, `cache-control: no-store`, since a shared cache in front of the app would keep a 502 for
 * the day otherwise.
 *
 * Nitro's own cache (`defineCachedEventHandler`) is not used because its storage stringifies the entry and parses its 8 MB again at every hit.
 *
 * @param options - What a test stands in for, or the list the route serves
 * @returns The event handler
 */
export function ghcnMapStationsHandler(options: GhcnHandlerOptions = {}) {
  const now = options.now ?? Date.now
  const list = options.list ?? createGhcnMapList(options)

  /** Answers with a problem: its status and headers, never cached, and the time that is left of the back-off as when to try again */
  function answerProblem(event: H3Event, failed: GhcnProblem, waitSeconds?: number) {
    setResponseStatus(event, failed.status)
    for (const [name, value] of Object.entries(failed.headers))
      setResponseHeader(event, name, value)
    if (waitSeconds !== undefined)
      setResponseHeader(event, 'retry-after', waitSeconds)
    setResponseHeader(event, 'cache-control', 'no-store')
    return JSON.stringify(failed.body)
  }

  return defineEventHandler(async (event) => {
    const requestId = globalThis.crypto.randomUUID().replaceAll('-', '')
    const answer = await list.get(requestId)
    if (!('kept' in answer))
      return 'problem' in answer ? answerProblem(event, answer.problem, answer.waitSeconds) : undefined
    const { value, modified, madeAt } = answer.kept
    // the day that is left of the list, which a shared cache in front of the app may keep it for, and the day it may be served after it
    const remaining = Math.max(0, MAX_AGE_SECONDS - Math.floor((now() - madeAt) / 1000))
    if (handleCacheHeaders(event, { modifiedTime: modified, etag: value.etag, cacheControls: [`s-maxage=${remaining}`, `stale-while-revalidate=${MAX_AGE_SECONDS}`] }))
      return
    setResponseHeader(event, 'content-type', 'application/json')
    return value.text
  })
}
