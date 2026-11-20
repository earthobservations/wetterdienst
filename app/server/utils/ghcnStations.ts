import type { GhcnStationColumns } from '../../shared/types/ghcn-stations'
import { describeWrongKind, HTML_TYPE, UNEXPECTED_ANSWER_TYPE } from '../../app/utils/api-answer'

// The list of the stations of NOAA GHCN daily that the map shows (GH-4267), made from the backend's own answer for
// `noaa/ghcn` (133k stations, 44 MB of JSON, 3.8 MB gzipped, 3 s) as the columns the map needs, so that the browser asks
// for 2 MB once and not for the 44 MB. `server/api/map/ghcn-stations.get.ts` caches it.

/** What the backend is asked for: the whole network, every station with its first and last year */
export const GHCN_STATIONS_PATH = '/stations?provider=noaa&network=ghcn&parameters=daily/data&all=true'

/** How long the backend may take: it answers in 3 s with a warm cache, and a cold one is longer */
const BACKEND_TIMEOUT_MS = 90_000
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
 * the first and the last value read from the timestamps (null where the backend gives none).
 *
 * @param stations - The `stations` of the backend's answer for `noaa/ghcn`
 * @param retrievedAt - When the backend made it
 * @returns The columns, `count` long
 */
export function compactGhcnStations(stations: BackendStation[], retrievedAt: string | null = null): GhcnStationColumns {
  const columns: GhcnStationColumns = { count: 0, retrieved_at: retrievedAt, station_id: [], latitude: [], longitude: [], first_year: [], last_year: [], name: [] }
  for (const station of stations) {
    if (typeof station.station_id !== 'string' || typeof station.latitude !== 'number' || typeof station.longitude !== 'number')
      continue
    columns.station_id.push(station.station_id)
    columns.latitude.push(station.latitude)
    columns.longitude.push(station.longitude)
    columns.first_year.push(yearOf(station.start_timestamp))
    columns.last_year.push(yearOf(station.end_timestamp))
    columns.name.push(typeof station.name === 'string' ? station.name : null)
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
 * empty for want of an answer, which the route would keep for a day. The backend that cannot be reached, a page of HTML or
 * text that is no JSON for its answer, an answer of no stations, and the backend's own error (its problem, with its status)
 * are each a problem of a 5xx or the backend's status, which is no cache entry.
 *
 * @param apiBase - The backend's `/api` URL
 * @param requestId - The id the request is known by in the backend's log and in the problem
 * @param fetcher - `fetch`, or the one that stands in for it
 * @returns The columns, or the problem to answer with
 */
export async function readGhcnStations(apiBase: string, requestId: string, fetcher: typeof fetch = globalThis.fetch): Promise<GhcnStationColumns | GhcnProblem> {
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
  const text = await response.text().catch(() => '')
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
  let answer: { stations?: unknown, metadata?: { retrieved_at?: string } } | null = null
  if (!HTML_TYPE.test(contentType ?? '')) {
    try {
      answer = JSON.parse(text)
    }
    catch {}
  }
  if (!answer || !Array.isArray(answer.stations)) {
    console.error(`Request ${requestId} to the backend for the GHCN stations was answered with ${contentType}, not the list of stations.`)
    return problem(502, UNEXPECTED_ANSWER_TYPE, 'Bad Gateway', describeWrongKind(contentType), requestId)
  }
  const columns = compactGhcnStations(answer.stations as BackendStation[], answer.metadata?.retrieved_at ?? null)
  // the network has 133k stations: none is an answer that is not the list, which a day of cache would keep
  if (columns.count === 0)
    return problem(502, UNEXPECTED_ANSWER_TYPE, 'Bad Gateway', 'The backend answered with no stations for NOAA GHCN daily.', requestId)
  return columns
}
