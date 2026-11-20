import type { GhcnStationColumns } from '../../shared/types/ghcn-stations'
import { createHash } from 'node:crypto'
import { describeUnreadable, describeWrongKind, HTML_TYPE, UNEXPECTED_ANSWER_TYPE } from '../../app/utils/api-answer'
import { useApiBase } from './apiBase'

// The list of the stations of NOAA GHCN daily that the map shows (GH-4267), made from the backend's own answer for
// `noaa/ghcn` (133k stations, 44 MB of JSON, 3.8 MB gzipped, 3 s) as the columns the map needs, so that the browser asks
// for 2 MB once and not for the 44 MB. `ghcnMapStationsHandler` keeps it for a day; the route is `server/routes/_ghcn/map-stations.get.ts`,
// outside `/api`, which is the backend's namespace and is proxied to it as it is (the rate limit counts `/_ghcn/*`, as the stripes' routes).

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
export async function readGhcnStations(apiBase: string, requestId: string, fetcher: typeof fetch = globalThis.fetch, minimum = MIN_STATIONS): Promise<GhcnStationColumns | GhcnProblem> {
  let response: Response
  try {
    response = await fetcher(`${apiBase}${GHCN_STATIONS_PATH}`, { headers: { 'x-request-id': requestId }, signal: AbortSignal.timeout(BACKEND_TIMEOUT_MS) })
  }
  catch (failure) {
    // the cause names the backend's host and port: for whoever runs the app, in the log, not in the answer
    console.error(`Request ${requestId} to the backend for the GHCN stations failed:`, (failure as { cause?: unknown })?.cause ?? failure)
    return problem(502, BACKEND_UNREACHABLE_TYPE, 'Bad Gateway', 'The backend could not be reached. The cause is in the server log.', requestId)
  }
  const contentType = response.headers.get('content-type')
  let text: string
  try {
    text = await response.text()
  }
  catch (failure) {
    // a reset, or the timeout, part-way through the body: the answer is not an empty one, and says what it is
    console.error(`Request ${requestId} to the backend for the GHCN stations could not be read to its end:`, (failure as { cause?: unknown })?.cause ?? failure)
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
    console.error(`Request ${requestId} to the backend for the GHCN stations was answered with ${contentType}, not the list of stations.`)
    return problem(502, UNEXPECTED_ANSWER_TYPE, 'Bad Gateway', describeWrongKind(contentType), requestId)
  }
  let answer: { stations?: unknown, metadata?: { retrieved_at?: string } } | null
  try {
    answer = JSON.parse(text)
  }
  catch (failure) {
    console.error(`Request ${requestId} to the backend for the GHCN stations was not valid JSON:`, failure)
    return problem(502, UNEXPECTED_ANSWER_TYPE, 'Bad Gateway', describeUnreadable(contentType), requestId)
  }
  if (!answer || !Array.isArray(answer.stations)) {
    console.error(`Request ${requestId} to the backend for the GHCN stations had no list of stations.`)
    return problem(502, UNEXPECTED_ANSWER_TYPE, 'Bad Gateway', 'The answer of the API does not have the form of this endpoint: no list of `stations`.', requestId)
  }
  const columns = compactGhcnStations(answer.stations as BackendStation[], answer.metadata?.retrieved_at ?? null)
  // the network has 133k stations: none, or a part of them, is an answer that is not the list, which a day of cache would keep
  if (columns.count < Math.max(1, minimum)) {
    console.error(`Request ${requestId} to the backend for the GHCN stations was answered with ${columns.count} stations, fewer than the ${minimum} of a whole list.`)
    return problem(502, UNEXPECTED_ANSWER_TYPE, 'Bad Gateway', `The backend answered with ${columns.count} stations for NOAA GHCN daily, a part of its list.`, requestId)
  }
  return columns
}

/** How long a list is kept, and the day that a shared cache in front of the app may keep it for too */
const MAX_AGE_SECONDS = 24 * 60 * 60
/** How soon after a failed refresh of a list that is kept the next one is made: the stale list is served meanwhile */
const RETRY_AFTER_FAILURE_MS = RETRY_AFTER_SECONDS * 1000

export interface GhcnHandlerOptions {
  apiBase?: () => string
  fetcher?: typeof fetch
  now?: () => number
  /** The fewest stations of a list that is kept (`MIN_STATIONS`) */
  minimum?: number
}

interface KeptList {
  /** The list as the text that is sent: made once, so that a request does not make 8 MB of it again */
  text: string
  etag: string
  modified: Date
  madeAt: number
}

/**
 * The handler of `GET /_ghcn/map-stations`: the list of the stations as columns, kept in the memory of the process for a day. It is
 * made when the first request comes (the others that come meanwhile wait for the same backend answer) and sent as the text it was
 * made as, with an `ETag`, so that a repeated request is answered 304 and a hit costs no more than sending it. Once the day is over
 * the list in hand is sent still, and the next is made behind it (stale-while-revalidate), at most every 30 s while the backend fails.
 *
 * A failure is nobody's list: it is not kept, so that the next request asks again, and it is answered with its problem,
 * `cache-control: no-store`, since a shared cache in front of the app would keep a 502 for the day otherwise.
 *
 * Nitro's own cache (`defineCachedEventHandler`) is not used because its storage stringifies the entry and parses its 8 MB again at every hit.
 *
 * @param options - What a test stands in for
 * @returns The event handler
 */
export function ghcnMapStationsHandler(options: GhcnHandlerOptions = {}) {
  const apiBase = options.apiBase ?? useApiBase
  const now = options.now ?? Date.now
  let kept: KeptList | null = null
  let pending: Promise<GhcnProblem | null> | null = null
  let nextRefreshAt = 0

  /** Makes the list (once, whoever asks while it is made): null where it is kept, else the problem */
  function make(requestId: string): Promise<GhcnProblem | null> {
    pending ??= (async () => {
      const read = await readGhcnStations(apiBase(), requestId, options.fetcher, options.minimum)
      if ('body' in read) {
        nextRefreshAt = now() + RETRY_AFTER_FAILURE_MS
        return read
      }
      const text = JSON.stringify(read)
      kept = { text, etag: `W/"${createHash('sha1').update(text).digest('base64url')}"`, modified: new Date(now()), madeAt: now() }
      return null
    })().finally(() => {
      pending = null
    })
    return pending
  }

  return defineEventHandler(async (event) => {
    const requestId = globalThis.crypto.randomUUID().replaceAll('-', '')
    if (!kept) {
      const failed = await make(requestId)
      if (failed) {
        setResponseStatus(event, failed.status)
        for (const [name, value] of Object.entries(failed.headers))
          setResponseHeader(event, name, value)
        setResponseHeader(event, 'cache-control', 'no-store')
        return JSON.stringify(failed.body)
      }
    }
    else if (now() - kept.madeAt >= MAX_AGE_SECONDS * 1000 && !pending && now() >= nextRefreshAt) {
      void make(requestId)
    }
    const list = kept!
    if (handleCacheHeaders(event, { modifiedTime: list.modified, etag: list.etag, cacheControls: [`s-maxage=${MAX_AGE_SECONDS}`, 'stale-while-revalidate'] }))
      return
    setResponseHeader(event, 'content-type', 'application/json')
    return list.text
  })
}
