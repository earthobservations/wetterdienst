import type { H3Event } from 'h3'
import type { GhcnStationColumns } from '../../shared/types/ghcn-stations'
import { createHash } from 'node:crypto'
import { describeWrongKind, HTML_TYPE, UNEXPECTED_ANSWER_TYPE } from '../../app/utils/api-answer'
import { useApiBase } from './apiBase'
import { CsvFormatError, CsvRecordReader } from './csvRecords'

// The list of the stations of NOAA GHCN daily that the map shows (GH-4267), made from the backend's own answer for
// `noaa/ghcn` (133k stations, 16 MB of CSV, 3 s) as the columns the map needs, so that the browser asks for 2 MB once and not
// for the 44 MB that the same list is as JSON. The CSV is read as it arrives, a row at a time, into the columns, and is never
// held as a text or as an object for each station (GH-4299). `ghcnMapStationsHandler` keeps the columns for a day; the route is
// `server/routes/_ghcn/map-stations.get.ts`, outside `/api`, which is the backend's namespace and is proxied to it as it is
// (the rate limit counts every route of `/_ghcn/`).

/** What the backend is asked for: the whole network, every station with its first and last year, as the CSV that it streams */
export const GHCN_STATIONS_PATH = '/stations?provider=noaa&network=ghcn&parameters=daily/data&all=true&format=csv'
/** The header of the answer that says when the backend made it: a CSV has no place for that in its body */
const RETRIEVED_AT_HEADER = 'x-wetterdienst-retrieved-at'
/** The columns of the CSV that the list is made of, by the name in its header row */
const CSV_COLUMNS = ['station_id', 'latitude', 'longitude', 'start_timestamp', 'end_timestamp', 'name', 'wmo_id'] as const
/** How much of a body may be read before its header row is complete: the real one is 120 bytes, and a body with no line end in 16 KB is no CSV */
const MAX_HEADER_BYTES = 16 * 1024
const ADDRESS_HINT = 'The address of the API may be wrong, or a proxy in front of it answered instead of it.'

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

/** An answer that is not the list: `detail` is what the problem says, the message is for the log */
class NotTheListError extends Error {
  constructor(readonly detail: string, message: string) {
    super(message)
  }
}

/** Where each column that is read is in the header row of the CSV */
type Places = Record<typeof CSV_COLUMNS[number], number>

/** The pieces of a body, which are let go of (the connection is cancelled) where the reading stops, whether it is at the end or not */
async function* chunksOf(body: ReadableStream<Uint8Array> | null): AsyncGenerator<Uint8Array> {
  if (!body)
    return
  const reader = body.getReader()
  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done)
        return
      yield value
    }
  }
  finally {
    void reader.cancel().catch(() => {})
  }
}

/** A number of the CSV: null where the field is empty or no finite number, as a position that is not there */
function numberOf(field: string | null | undefined): number | null {
  if (!field)
    return null
  const number = Number(field)
  return Number.isFinite(number) ? number : null
}

/**
 * Reads the CSV of the backend's list from the pieces of its body into the columns of `compactGhcnStations`, by the same rules
 * and so into the same columns for the same list: a station with no position is left out, the years are the first four digits of
 * the timestamps, the name is null where it is empty, and the WMO number is trimmed and null where it is empty. The text is
 * checked as it comes: the header row must name every column that is read, every row must have as many fields as the header (a
 * cut one has fewer), a quote must be closed, and the last row must be ended by its line end, as every row of the backend's is.
 * The bytes are decoded field by field and only for the columns that are read: no text of the whole is made.
 *
 * @param chunks - The body of the answer, in the pieces it arrives in
 * @param retrievedAt - When the backend made the list
 * @returns The columns
 * @throws NotTheListError where the body is no CSV of the stations, or is cut short
 */
export async function readGhcnStationColumns(chunks: AsyncIterable<Uint8Array> | Iterable<Uint8Array>, retrievedAt: string | null = null): Promise<GhcnStationColumns> {
  const columns: GhcnStationColumns = { count: 0, retrieved_at: retrievedAt, station_id: [], latitude: [], longitude: [], first_year: [], last_year: [], name: [], wmo_id: [] }
  // the place of each column that is read in the header row: null until that is read, when every field of it is
  let at: Places | null = null
  let wanted: Set<number> | null = null
  let width = 0
  let rows = 0
  const reader = new CsvRecordReader(column => wanted === null || wanted.has(column), (fields) => {
    rows++
    if (!at) {
      const names = fields.map(field => field ?? '')
      const found = CSV_COLUMNS.map(name => names.indexOf(name))
      const missing = CSV_COLUMNS.filter((_, index) => found[index] === -1)
      if (missing.length)
        throw new NotTheListError(`The answer of the API is not the CSV of the stations: its header row has no ${missing.map(name => `\`${name}\``).join(', ')}. ${ADDRESS_HINT}`, `header row without ${missing.join(', ')}`)
      at = Object.fromEntries(CSV_COLUMNS.map((name, index) => [name, found[index]!])) as Places
      wanted = new Set(found)
      width = names.length
      return
    }
    if (fields.length !== width)
      throw new NotTheListError('The answer of the API for the stations is cut short or malformed: a row has another number of fields than the header row.', `row ${rows} has ${fields.length} fields, the header row ${width}`)
    const stationId = fields[at.station_id]
    const latitude = numberOf(fields[at.latitude])
    const longitude = numberOf(fields[at.longitude])
    // the ones with a position: a map can show no other
    if (typeof stationId !== 'string' || latitude === null || longitude === null)
      return
    columns.station_id.push(stationId)
    columns.latitude.push(latitude)
    columns.longitude.push(longitude)
    columns.first_year.push(yearOf(fields[at.start_timestamp]))
    columns.last_year.push(yearOf(fields[at.end_timestamp]))
    columns.name.push(fields[at.name] ?? null)
    columns.wmo_id.push(fields[at.wmo_id]?.trim() || null)
  })
  let received = 0
  try {
    for await (const chunk of chunks) {
      reader.push(chunk)
      received += chunk.byteLength
      // a body that is no CSV does not have to be read to its end to be told so
      if (!at && received > MAX_HEADER_BYTES)
        throw new NotTheListError(`The answer of the API is not the CSV of the stations: it has no header row. ${ADDRESS_HINT}`, 'no header row in the first 16 KB')
    }
    reader.end()
  }
  catch (failure) {
    // a body that never got to the end of its first line is a JSON object or a text, not a CSV that was cut short
    if (failure instanceof CsvFormatError)
      throw new NotTheListError(at ? 'The answer of the API for the stations is cut short or malformed.' : `The answer of the API is not the CSV of the stations: it has no header row. ${ADDRESS_HINT}`, failure.message)
    throw failure
  }
  if (!at)
    throw new NotTheListError(`The answer of the API is not the CSV of the stations: it has no header row. ${ADDRESS_HINT}`, 'no body')
  columns.count = columns.station_id.length
  return columns
}

/**
 * Asks the backend for the stations of GHCN daily and makes the columns of them, or says why it cannot: never a list that is
 * empty or partial for want of an answer, which the route would keep for a day. The backend that cannot be reached, a body that
 * cannot be read to its end, a page of HTML or a text that is no CSV of the stations for its answer, a CSV that is cut short (a
 * row with fewer fields than the header, a row that is not ended, a quote that is not closed), a list of fewer than `minimum`
 * stations, and the backend's own error (its problem, with its status) are each a problem of a 5xx or the backend's status, which
 * is no cache entry.
 *
 * The CSV is read from the body as it arrives and never held as a whole (GH-4299). It has no place for `retrieved_at` in its
 * body, so that is the backend's header `X-Wetterdienst-Retrieved-At`, which says what `metadata.retrieved_at` of the JSON does.
 *
 * @param apiBase - The backend's `/api` URL
 * @param requestId - The id the request is known by in the backend's log and in the problem
 * @param fetcher - `fetch`, or the one that stands in for it
 * @param minimum - The fewest stations of a list that is kept
 * @returns The columns, or the problem to answer with
 */
export async function readGhcnMapStations(apiBase: string, requestId: string, fetcher: typeof fetch = globalThis.fetch, minimum = MIN_STATIONS): Promise<GhcnStationColumns | GhcnProblem> {
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
  /** A reset, or the timeout, part-way through the body: the answer is not an empty one, and says what it is */
  const unreadable = (failure: unknown) => {
    console.error(`Request ${requestId} to the backend for the GHCN stations could not be read to its end:`, (failure as { cause?: unknown })?.cause ?? failure)
    return problem(502, UNEXPECTED_ANSWER_TYPE, 'Bad Gateway', 'The answer of the API could not be read to its end. The cause is in the server log.', requestId)
  }
  if (!response.ok) {
    let text: string
    try {
      text = await response.text()
    }
    catch (failure) {
      return unreadable(failure)
    }
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
    // a page is not read, and the connection is let go
    void response.body?.cancel().catch(() => {})
    console.error(`Request ${requestId} to the backend for the GHCN stations was answered with ${contentType}, not the list of stations.`)
    return problem(502, UNEXPECTED_ANSWER_TYPE, 'Bad Gateway', describeWrongKind(contentType), requestId)
  }
  let columns: GhcnStationColumns
  try {
    columns = await readGhcnStationColumns(chunksOf(response.body), response.headers.get(RETRIEVED_AT_HEADER))
  }
  catch (failure) {
    if (!(failure instanceof NotTheListError))
      return unreadable(failure)
    console.error(`Request ${requestId} to the backend for the GHCN stations was not the CSV of the list (${contentType}): ${failure.message}`)
    return problem(502, UNEXPECTED_ANSWER_TYPE, 'Bad Gateway', failure.detail, requestId)
  }
  // the network has 133k stations: none, or a part of them, is an answer that is not the list, which a day of cache would keep
  if (columns.count < Math.max(1, minimum)) {
    console.error(`Request ${requestId} to the backend for the GHCN stations was answered with ${columns.count} stations, fewer than the ${minimum} of a whole list.`)
    return problem(502, UNEXPECTED_ANSWER_TYPE, 'Bad Gateway', `The backend answered with ${columns.count} stations for NOAA GHCN daily, a part of its list.`, requestId)
  }
  return columns
}

/** How long a list is kept, and the day that a shared cache in front of the app may keep it for too */
const MAX_AGE_SECONDS = 24 * 60 * 60
/** How long after a failure the backend is not asked again: the problem is answered again, or the stale list served */
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
 * the list in hand is sent still, and the next is made behind it (stale-while-revalidate).
 *
 * A failure is nobody's list: it is not kept, and it is answered with its problem, `cache-control: no-store`, since a shared cache in
 * front of the app would keep a 502 for the day otherwise. A backend that fails, or answers fast and wrongly, is not asked again at
 * every request (a read of it is 44 MB): for 30 s after a failure the problem is answered again, with the time that is left as its
 * `Retry-After`, where there is no list, and the list in hand is served where there is one, whose refresh waits as long.
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
  /** The failure that the next requests are answered with until `backoffUntil`, and no request is made to the backend before it */
  let failure: GhcnProblem | null = null
  let backoffUntil = 0

  /** Makes the list (once, whoever asks while it is made): null where it is kept, else the problem */
  function make(requestId: string): Promise<GhcnProblem | null> {
    pending ??= (async () => {
      let read: Awaited<ReturnType<typeof readGhcnMapStations>>
      try {
        read = await readGhcnMapStations(apiBase(), requestId, options.fetcher, options.minimum)
      }
      catch (unexpected) {
        // nothing the reader does not catch is allowed to reject what the requests wait for, or to be nobody's to handle
        console.error(`Request ${requestId} for the GHCN stations failed unexpectedly:`, unexpected)
        read = problem(502, UNEXPECTED_ANSWER_TYPE, 'Bad Gateway', 'The list of the stations could not be made. The cause is in the server log.', requestId)
      }
      if ('body' in read) {
        failure = read
        backoffUntil = now() + RETRY_AFTER_FAILURE_MS
        return read
      }
      const text = JSON.stringify(read)
      kept = { text, etag: `W/"${createHash('sha1').update(text).digest('base64url')}"`, modified: new Date(now()), madeAt: now() }
      failure = null
      backoffUntil = 0
      return null
    })().finally(() => {
      pending = null
    })
    return pending
  }

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
    if (!kept) {
      // the backend failed a moment ago: it is not asked again for every page view
      if (failure && now() < backoffUntil)
        return answerProblem(event, failure, Math.max(1, Math.ceil((backoffUntil - now()) / 1000)))
      const failed = await make(requestId)
      if (failed)
        return answerProblem(event, failed)
    }
    else if (now() - kept.madeAt >= MAX_AGE_SECONDS * 1000 && !pending && now() >= backoffUntil) {
      void make(requestId)
    }
    const list = kept!
    // the day that is left of the list, which a shared cache in front of the app may keep it for, and the day it may be served after it
    const remaining = Math.max(0, MAX_AGE_SECONDS - Math.floor((now() - list.madeAt) / 1000))
    if (handleCacheHeaders(event, { modifiedTime: list.modified, etag: list.etag, cacheControls: [`s-maxage=${remaining}`, `stale-while-revalidate=${MAX_AGE_SECONDS}`] }))
      return
    setResponseHeader(event, 'content-type', 'application/json')
    return list.text
  })
}
