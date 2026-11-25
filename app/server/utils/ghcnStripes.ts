import type { ResponseWarning } from '../../shared/types/api'
import type { AnnualKind, DailyRow } from './ghcnAnnual'
import { describeWrongKind, HTML_TYPE, UNEXPECTED_ANSWER_TYPE } from '../../app/utils/api-answer'
import { MIN_RECORD_YEARS } from '../../app/utils/stripes-scale'
import { unitSymbol } from '../../app/utils/unit-targets'
import { annualFromDaily, annualRows, leaveOutFailed, leaveOutSuspect, PRECIPITATION, TEMPERATURE_MAX, TEMPERATURE_MEAN, TEMPERATURE_MIN, temperatureMethod } from './ghcnAnnual'
import { AbortedError } from './ttlCache'

// What the climate stripes of NOAA's GHCN daily need from the backend, and what the app's server makes of it (GH-4258): the
// annual values of a station, calculated from its daily ones (`GET /_ghcn/annual`), and the stations that have a record long
// enough (`GET /_ghcn/stations`). Both read the backend's generic API (`/api/values`, `/api/stations`) and answer small: a
// station's years are a few kilobytes where its days are up to 25 MB, and the lists of GHCN are 8 to 21 MB of
// 133,000 stations each (three for the temperature) where the stripes' list is a few thousand. Both are kept in the server's memory for `GHCN_TTL_MS`, so a browser, and the
// next one, does not make the backend and this server read and calculate a century of days again.

/** The daily parameters of GHCN the annual values of each kind are calculated from, the first of which names the series */
export const GHCN_DAILY_PARAMETERS: Record<AnnualKind, readonly string[]> = {
  temperature: [TEMPERATURE_MEAN, TEMPERATURE_MAX, TEMPERATURE_MIN],
  precipitation: [PRECIPITATION],
}

/** The quantity of the kind, which `unit_targets` names the unit of */
export const GHCN_UNIT_TYPE: Record<AnnualKind, string> = { temperature: 'temperature', precipitation: 'precipitation' }

/**
 * How long what was read and calculated is served: 12 hours, as the backend keeps the daily files and the lists of GHCN
 * (NOAA writes them once a night). The year that is running is no year with a value until it is complete, so the annual
 * values change when NOAA corrects a day or a year comes to its end, which a day's delay does not matter for.
 */
export const GHCN_TTL_MS = 12 * 60 * 60 * 1000

/** The record the first day of which is before any of the network's (the daily values of GHCN begin in the 18th century) */
export const GHCN_FIRST_DAY = '1700-01-01'

/** A failure of the backend, or of reaching it, as the problem the app answers it with */
export class UpstreamProblem extends Error {
  status: number
  problem: Record<string, unknown>
  retryAfter?: number

  constructor(status: number, problem: Record<string, unknown>, retryAfter?: number) {
    super(String(problem.detail ?? problem.title ?? status))
    this.name = 'UpstreamProblem'
    this.status = status
    this.problem = problem
    this.retryAfter = retryAfter
  }
}

/** Reads one answer of the backend's JSON API: `path` under its `/api`, the query as it is sent; a failure is an `UpstreamProblem` */
export type BackendRead = (path: string, query: Record<string, string>) => Promise<unknown>

const RETRY_AFTER_SECONDS = 30

/** The kind of the problem for an answer that is not what the endpoint gives, as the proxy of `/api` names it */
const UNEXPECTED_KIND = UNEXPECTED_ANSWER_TYPE.replace('urn:wetterdienst:problem:', '')

/** What the backend is given to answer a read in, the body included, 90 seconds: more than its own limit for a request (60 seconds), so that it answers first; a read that takes longer is a 504 and gives its place up */
const BACKEND_TIMEOUT_MS = 90_000

/** The problem of a failure of the app's own; its `instance` and `request_id` are written where the request is answered (`ghcnRoutes.ts`) if the reader did not know the id */
function problemOf(status: number, title: string, kind: string, detail: string, requestId?: string): Record<string, unknown> {
  return { type: `urn:wetterdienst:problem:${kind}`, title, status, detail, ...(requestId ? { instance: `urn:wetterdienst:request:${requestId}`, request_id: requestId } : {}) }
}

/**
 * The reader of the backend at `apiBase` (`server/utils/apiBase.ts`): GET, the request's id passed on, a timeout, and `signal`, which
 * stops the read (`AbortedError`) where nobody waits for it any more. A problem of the backend's own is passed on as it is; an answer that is a web page or no JSON, and a backend that cannot be reached, are a 502
 * of the app's own, as the proxy of `/api` answers them.
 */
export function backendReader(apiBase: string, requestId: string, signal?: AbortSignal, fetcher: typeof fetch = globalThis.fetch, timeoutMs = BACKEND_TIMEOUT_MS): BackendRead {
  return async (path, query) => {
    const url = `${apiBase}${path}?${new URLSearchParams(query)}`
    // the limit covers the answer and its body: one timer, which the read of the body is under as well
    const limit = AbortSignal.timeout(timeoutMs)
    const timedOut = () => {
      console.error(`Request ${requestId} to the backend for ${path} took longer than ${timeoutMs / 1000} s.`)
      return new UpstreamProblem(504, problemOf(504, 'Gateway Timeout', 'upstream-timeout', 'The backend did not answer in time.', requestId), RETRY_AFTER_SECONDS)
    }
    let response: Response
    try {
      response = await fetcher(url, { headers: { 'x-request-id': requestId, 'accept': 'application/json' }, signal: signal ? AbortSignal.any([limit, signal]) : limit })
    }
    catch (failure) {
      if (signal?.aborted)
        throw new AbortedError()
      if (limit.aborted || (failure as { name?: string })?.name === 'TimeoutError')
        throw timedOut()
      console.error(`Request ${requestId} to the backend for ${path} failed:`, (failure as { cause?: unknown })?.cause ?? failure)
      throw new UpstreamProblem(502, problemOf(502, 'Bad Gateway', 'backend-unreachable', 'The backend could not be reached. The cause is in the server log.', requestId), RETRY_AFTER_SECONDS)
    }
    const contentType = response.headers.get('content-type')
    if (HTML_TYPE.test(contentType ?? '') && response.ok) {
      await response.body?.cancel()
      console.error(`Request ${requestId} to the backend for ${path} was answered with ${contentType}, not data.`)
      throw new UpstreamProblem(502, problemOf(502, 'Bad Gateway', UNEXPECTED_KIND, describeWrongKind(contentType), requestId), RETRY_AFTER_SECONDS)
    }
    let body: unknown
    try {
      body = await response.json()
    }
    catch {
      // the body is read under the same limits: a client that left, or a backend that did not finish it in time
      if (signal?.aborted)
        throw new AbortedError()
      if (limit.aborted)
        throw timedOut()
      throw new UpstreamProblem(502, problemOf(502, 'Bad Gateway', UNEXPECTED_KIND, describeWrongKind(contentType ?? 'text/plain'), requestId), RETRY_AFTER_SECONDS)
    }
    if (!response.ok) {
      const problem = body as Record<string, unknown> | null
      // the backend's own problem is the answer; anything else a proxy in front of it wrote is not
      if (problem && typeof problem === 'object' && typeof problem.detail === 'string')
        throw new UpstreamProblem(response.status, problem, Number(response.headers.get('retry-after')) || undefined)
      throw new UpstreamProblem(502, problemOf(502, 'Bad Gateway', UNEXPECTED_KIND, `The backend answered with ${response.status}, not data.`, requestId), RETRY_AFTER_SECONDS)
    }
    return body
  }
}

interface ValuesAnswer {
  values?: unknown
  metadata?: {
    provider?: unknown
    parameters?: Array<{ name?: string, unit?: string }> | null
    warnings?: Array<{ code?: string, message?: string, parameter?: string, stations?: string[] }>
  }
}

/** The code of the warning the backend gives where a station's days were read from the mirror of NOAA's data on AWS, which may end earlier (GH-4230) */
export const SOURCE_FALLBACK = 'source-fallback'

/**
 * How long an answer read from the mirror is served, in the server's memory and by a browser: 5 minutes (GH-4390). The mirror's file
 * may end months before NOAA's, so the full record must be back soon after NCEI is: the answer of an outage is kept until then at
 * the most, where an answer of NCEI is kept for `GHCN_TTL_MS` (12 hours) and a browser's for an hour.
 */
export const MIRROR_TTL_MS = 5 * 60 * 1000

/** Whether the annual values were calculated from days that the backend read from the mirror */
export function readFromMirror(answer: Pick<GhcnAnnualAnswer, 'metadata'>): boolean {
  return !!answer.metadata.warnings?.some(warning => warning.code === SOURCE_FALLBACK)
}

/** The warnings of the backend's answer as the generic API gives them (a code and its text, the parameter and stations where it names them), none that is not one */
function passedOn(warnings: NonNullable<ValuesAnswer['metadata']>['warnings']): ResponseWarning[] {
  const kept: ResponseWarning[] = []
  for (const warning of Array.isArray(warnings) ? warnings : []) {
    if (typeof warning?.code !== 'string' || typeof warning.message !== 'string')
      continue
    kept.push({
      code: warning.code,
      message: warning.message,
      ...(typeof warning.parameter === 'string' ? { parameter: warning.parameter } : {}),
      ...(Array.isArray(warning.stations) ? { stations: warning.stations.filter((id): id is string => typeof id === 'string') } : {}),
    })
  }
  return kept
}

function expectValues(answer: unknown): { values: DailyRow[], metadata: NonNullable<ValuesAnswer['metadata']> } {
  const { values, metadata } = (answer ?? {}) as ValuesAnswer
  if (!Array.isArray(values) || !metadata)
    throw new UpstreamProblem(502, problemOf(502, 'Bad Gateway', UNEXPECTED_KIND, 'The answer of the API does not have the form of this endpoint: no list of `values`.'), RETRY_AFTER_SECONDS)
  return { values: values as DailyRow[], metadata }
}

/**
 * The annual values of a station of GHCN daily: its days read from `/api/values` in the unit asked for (the conversion comes
 * first, as the mean of a unit that is a linear change of another is that unit's), the readings a plausibility check flagged
 * or the source's own quality check failed left out, the years calculated by the WMO rules (`ghcnAnnual.ts`).
 *
 * @param read - Reads the backend
 * @param request - What is asked for
 * @param request.kind - The annual mean temperature, or the annual precipitation sum
 * @param request.station - The station's id
 * @param request.unitTargets - The unit the values are returned in, as `/api/values` takes it: `{ temperature: 'degree_fahrenheit' }`
 * @param request.today - The day the window of the days ends with, as `YYYY-MM-DD`
 * @throws {UpstreamProblem} The backend failed, or the station is not one of GHCN (a 404)
 */
export async function readGhcnAnnual(
  read: BackendRead,
  request: { kind: AnnualKind, station: string, unitTargets?: Record<string, string>, today?: string },
): Promise<GhcnAnnualAnswer> {
  const { kind, station, unitTargets } = request
  const parameters = GHCN_DAILY_PARAMETERS[kind]
  const answer = await read('/values', {
    provider: 'noaa',
    network: 'ghcn',
    parameters: parameters.map(name => `daily/data/${name}`).join(','),
    stations: station,
    // the dataset needs a window to read days: from before the first record of the network to now, the station's file is read whole
    timestamp: `${GHCN_FIRST_DAY}/${request.today ?? new Date().toISOString().slice(0, 10)}`,
    // fixed as the backend's stripes fixed them: one row for each reading, the canonical names the years are built by
    shape: 'long',
    humanize: 'true',
    skip_empty: 'false',
    with_metadata: 'true',
    // a reading the source has no value for is no row: the rules read a missing row and a null alike, and the rows of a record are a third fewer
    drop_nulls: 'true',
    ...(unitTargets && Object.keys(unitTargets).length ? { unit_targets: JSON.stringify(unitTargets) } : {}),
  })
  const { values, metadata } = expectValues(answer)
  // a list that is none, or an entry that is none, is read as no warning
  if (Array.isArray(metadata.warnings) && metadata.warnings.some(warning => warning?.code === 'unknown-station'))
    throw new UpstreamProblem(404, problemOf(404, 'Not Found', 'not-found', `No station with a station_id similar to '${station}' found`))

  // a value a soft plausibility check flagged suspect is no year with data, whatever the mode (GH-3676); and a day whose value
  // failed a quality check of the source is a missing day, the year is built from the rest
  const days = leaveOutFailed(leaveOutSuspect(values))
  const warnings = passedOn(metadata.warnings)
  const method = kind === 'temperature' ? temperatureMethod(days) : null
  const name = parameters[0]!
  const unit = metadata.parameters?.find(parameter => parameter.name === name)?.unit
    ?? unitSymbol(unitTargets?.[GHCN_UNIT_TYPE[kind]] ?? '')
  return {
    metadata: { provider: metadata.provider as GhcnAnnualAnswer['metadata']['provider'], ...(warnings.length ? { warnings } : {}) },
    series: { station_id: station, parameter: name, unit, method },
    values: annualRows(annualFromDaily(days, kind)),
  }
}

/** The daily parameters whose station lists each kind is made of: one list for each, which the backend gives with that element's span (GH-4270) */
export const GHCN_LIST_PARAMETERS: Record<AnnualKind, { mean?: string, max?: string, min?: string, amount?: string }> = {
  temperature: { mean: TEMPERATURE_MEAN, max: TEMPERATURE_MAX, min: TEMPERATURE_MIN },
  precipitation: { amount: PRECIPITATION },
}

/** A station of one of the lists, as far as the span is concerned: the years its element has, an end that is empty meaning this year */
export interface ListedStation {
  station_id: string
  start_timestamp?: string | null
  end_timestamp?: string | null
  [field: string]: unknown
}

interface Span {
  first: number
  last: number
}

/** The lists the stations of a kind are made of: one for each daily parameter, as `GHCN_LIST_PARAMETERS` names them */
export interface StationLists {
  mean?: readonly ListedStation[]
  max?: readonly ListedStation[]
  min?: readonly ListedStation[]
  amount?: readonly ListedStation[]
}

/** The years a station's element spans, null for a station with no record of it */
function spanOf(station: ListedStation, thisYear: number): Span | null {
  if (!station.start_timestamp)
    return null
  return {
    first: Number(station.start_timestamp.slice(0, 4)),
    last: station.end_timestamp ? Number(station.end_timestamp.slice(0, 4)) : thisYear,
  }
}

/** The fields of a station the stripes' picker and the page read, which is what the list carries (the rest of a row is left out) */
const STATION_FIELDS = ['station_id', 'name', 'region', 'latitude', 'longitude', 'elevation', 'wmo_id'] as const

/**
 * The stations that climate stripes of a kind are made for, from the lists the backend gives for each element of it
 * (`/api/stations` with one `parameters` each, GH-4270), as the backend's own stripes listed them (`_ghcn_record_years` and
 * `_get_stripes_ghcn_stations`):
 *
 * - The precipitation: the span of `precipitation_amount` (PRCP).
 * - The temperature: a station has a mean from either TAVG or the days that TMAX and TMIN both have, so its span is the one of
 *   TAVG, taken with the years TMAX and TMIN have in common (from the later start to the earlier end, none where they do not
 *   meet), from the earliest start to the latest end of the two. A station in only one of TMAX and TMIN contributes nothing; one
 *   with TAVG alone contributes its TAVG span.
 * - A station is listed where its record spans `MIN_RECORD_YEARS` years (first to last, inclusive; an empty end is this year) and,
 *   as the stripes are built from complete years, still reports: its record reaches into this year or the last.
 *
 * The span is the one of the elements, not of any element the station has. `start_timestamp` is 1 January of its first year,
 * `end_timestamp` 31 December of its last, and none where that is this year (the year that runs has no end).
 *
 * @param kind - The annual mean temperature, or the annual precipitation sum
 * @param lists - The stations of each list, in the order of the listing: the first list a station is in gives its name and position
 * @param thisYear - The year it is
 * @param active - Only the stations that still report, which the picker lists; `false` for the whole list of the rule
 */
export function stripesStationsOf(kind: AnnualKind, lists: StationLists, thisYear: number, active = true): Station[] {
  const spans = new Map<string, Span>()
  const rows = new Map<string, ListedStation>()
  const keep = (station: ListedStation, span: Span) => {
    if (!rows.has(station.station_id))
      rows.set(station.station_id, station)
    const known = spans.get(station.station_id)
    spans.set(station.station_id, known ? { first: Math.min(known.first, span.first), last: Math.max(known.last, span.last) } : span)
  }
  if (kind === 'precipitation') {
    for (const station of lists.amount ?? []) {
      const span = spanOf(station, thisYear)
      if (span)
        keep(station, span)
    }
  }
  else {
    for (const station of lists.mean ?? []) {
      const span = spanOf(station, thisYear)
      if (span)
        keep(station, span)
    }
    const highest = new Map<string, { station: ListedStation, span: Span }>()
    for (const station of lists.max ?? []) {
      const span = spanOf(station, thisYear)
      if (span)
        highest.set(station.station_id, { station, span })
    }
    for (const station of lists.min ?? []) {
      const span = spanOf(station, thisYear)
      const other = highest.get(station.station_id)
      if (!span || !other)
        continue
      // the years TMAX and TMIN have in common, none where they do not meet
      const common = { first: Math.max(span.first, other.span.first), last: Math.min(span.last, other.span.last) }
      if (common.first <= common.last)
        keep(other.station, common)
    }
  }
  const stations: Station[] = []
  for (const [id, row] of rows) {
    const { first, last } = spans.get(id)!
    if (last - first + 1 < MIN_RECORD_YEARS || (active && last < thisYear - 1))
      continue
    stations.push({
      ...Object.fromEntries(STATION_FIELDS.map(field => [field, row[field] ?? null])),
      start_timestamp: `${String(first).padStart(4, '0')}-01-01T00:00:00.000000+00:00`,
      end_timestamp: last >= thisYear ? null : `${String(last).padStart(4, '0')}-12-31T00:00:00.000000+00:00`,
    } as unknown as Station)
  }
  // by id, as the backend listed them
  return stations.sort((a, b) => a.station_id < b.station_id ? -1 : a.station_id > b.station_id ? 1 : 0)
}

/**
 * The stations of GHCN daily that stripes of `kind` are made for: the lists of its elements, one after another (the largest is
 * 20 MB of JSON, and the three of the temperature are 49 MB), combined by `stripesStationsOf`.
 *
 * @param read - Reads the backend, which the caller has put behind its queue of reads
 */
export async function readGhcnStations(read: BackendRead, kind: AnnualKind, thisYear = new Date().getUTCFullYear()): Promise<Station[]> {
  const lists: Record<string, ListedStation[]> = {}
  for (const [name, parameter] of Object.entries(GHCN_LIST_PARAMETERS[kind])) {
    const answer = await read('/stations', { provider: 'noaa', network: 'ghcn', parameters: `daily/data/${parameter}`, all: 'true' }) as { stations?: ListedStation[] }
    if (!Array.isArray(answer?.stations))
      throw new UpstreamProblem(502, problemOf(502, 'Bad Gateway', UNEXPECTED_KIND, 'The answer of the API does not have the form of this endpoint: no list of `stations`.'), RETRY_AFTER_SECONDS)
    // cut at once to what the combination reads, so that one full list is alive at a time (each is 8 to 21 MB of JSON): the span of
    // each station, and its fields for the lists a name is taken from (the TMIN list gives none, see `stripesStationsOf`)
    lists[name] = answer.stations.map(station => name === 'min'
      ? { station_id: station.station_id, start_timestamp: station.start_timestamp, end_timestamp: station.end_timestamp }
      : { ...Object.fromEntries(STATION_FIELDS.map(field => [field, station[field] ?? null])), station_id: station.station_id, start_timestamp: station.start_timestamp, end_timestamp: station.end_timestamp })
  }
  return stripesStationsOf(kind, lists, thisYear)
}
