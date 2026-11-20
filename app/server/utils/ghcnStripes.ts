import type { AnnualKind, DailyRow } from './ghcnAnnual'
import { describeWrongKind, HTML_TYPE, UNEXPECTED_ANSWER_TYPE } from '../../app/utils/api-answer'
import { unitSymbol } from '../../app/utils/unit-targets'
import { annualFromDaily, annualRows, leaveOutFailed, leaveOutSuspect, PRECIPITATION, TEMPERATURE_MAX, TEMPERATURE_MEAN, TEMPERATURE_MIN, temperatureMethod } from './ghcnAnnual'

// What the climate stripes of NOAA's GHCN daily need from the backend, and what the app's server makes of it (GH-4258): the
// annual values of a station, calculated from its daily ones (`GET /_ghcn/annual`), and the stations that have a record long
// enough (`GET /_ghcn/stations`). Both read the backend's generic API (`/api/values`, `/api/stations`) and answer small: a
// station's years are a few kilobytes where its days are up to 25 MB, and the listing of GHCN is 43 MB of 133,000 stations
// where the stripes' list is a few thousand. Both are kept in the server's memory for `GHCN_TTL_MS`, so a browser, and the
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

/** What the backend is given to be read for 90 seconds: more than its own limit for a request (60 seconds), so that it answers first */
const BACKEND_TIMEOUT_MS = 90_000

/** The problem of a failure of the app's own; its `instance` and `request_id` are written where the request is answered (`ghcnRoutes.ts`) if the reader did not know the id */
function problemOf(status: number, title: string, kind: string, detail: string, requestId?: string): Record<string, unknown> {
  return { type: `urn:wetterdienst:problem:${kind}`, title, status, detail, ...(requestId ? { instance: `urn:wetterdienst:request:${requestId}`, request_id: requestId } : {}) }
}

/**
 * The reader of the backend at `apiBase` (`server/utils/apiBase.ts`): GET, the request's id passed on, a timeout. A problem of the
 * backend's own is passed on as it is; an answer that is a web page or no JSON, and a backend that cannot be reached, are a 502
 * of the app's own, as the proxy of `/api` answers them.
 */
export function backendReader(apiBase: string, requestId: string, fetcher: typeof fetch = globalThis.fetch): BackendRead {
  return async (path, query) => {
    const url = `${apiBase}${path}?${new URLSearchParams(query)}`
    let response: Response
    try {
      response = await fetcher(url, { headers: { 'x-request-id': requestId, 'accept': 'application/json' }, signal: AbortSignal.timeout(BACKEND_TIMEOUT_MS) })
    }
    catch (failure) {
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
    warnings?: Array<{ code?: string }>
  }
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
    ...(unitTargets && Object.keys(unitTargets).length ? { unit_targets: JSON.stringify(unitTargets) } : {}),
  })
  const { values, metadata } = expectValues(answer)
  if (metadata.warnings?.some(warning => warning.code === 'unknown-station'))
    throw new UpstreamProblem(404, problemOf(404, 'Not Found', 'not-found', `No station with a station_id similar to '${station}' found`))

  // a value a soft plausibility check flagged suspect is no year with data, whatever the mode (GH-3676); and a day whose value
  // failed a quality check of the source is a missing day, the year is built from the rest
  const days = leaveOutFailed(leaveOutSuspect(values))
  const method = kind === 'temperature' ? temperatureMethod(days) : null
  const name = parameters[0]!
  const unit = metadata.parameters?.find(parameter => parameter.name === name)?.unit
    ?? unitSymbol(unitTargets?.[GHCN_UNIT_TYPE[kind]] ?? '')
  return {
    metadata: { provider: metadata.provider as GhcnAnnualAnswer['metadata']['provider'] },
    series: { station_id: station, parameter: name, unit, method },
    values: annualRows(annualFromDaily(days, kind)),
  }
}

/**
 * The stations of GHCN daily that the stripes are made for: those whose record can reach the years a scale needs
 * (`MIN_RECORD_YEARS`, 10) and that still report, which is a record that reaches into this or the last year, as the years
 * are built from complete years and the one running has not ended. The span is the one the listing gives, from the first
 * to the last year of any element of the station: it says nothing of which elements, so a station that has years of a
 * precipitation record only is listed for the temperature as well, and its stripes are refused when they are asked for.
 *
 * @param stations - The stations `/api/stations` lists for GHCN daily
 * @param thisYear - The year it is
 * @param minimumYears - The fewest years a record spans
 */
export function longRecordStations<T extends { start_timestamp?: string | null, end_timestamp?: string | null }>(stations: readonly T[], thisYear: number, minimumYears = 10): T[] {
  return stations.filter((station) => {
    if (!station.start_timestamp)
      return false
    const first = Number(station.start_timestamp.slice(0, 4))
    // a station that has no end is still reporting: its last year is the one that is running
    const last = station.end_timestamp ? Number(station.end_timestamp.slice(0, 4)) : thisYear
    return last - first + 1 >= minimumYears && last >= thisYear - 1
  })
}

/** The fields of a station the stripes' picker and the page read, which is what the list carries (the rest of a row is left out: 28,000 of them) */
const STATION_FIELDS = ['station_id', 'name', 'region', 'latitude', 'longitude', 'elevation', 'wmo_id', 'start_timestamp', 'end_timestamp'] as const

export async function readGhcnStations(read: BackendRead, thisYear = new Date().getUTCFullYear()): Promise<Station[]> {
  const answer = await read('/stations', { provider: 'noaa', network: 'ghcn', parameters: 'daily/data', all: 'true' }) as { stations?: Array<Record<string, unknown>> }
  if (!Array.isArray(answer?.stations))
    throw new UpstreamProblem(502, problemOf(502, 'Bad Gateway', UNEXPECTED_KIND, 'The answer of the API does not have the form of this endpoint: no list of `stations`.'), RETRY_AFTER_SECONDS)
  return longRecordStations(answer.stations as Array<Record<string, unknown> & { start_timestamp?: string | null, end_timestamp?: string | null }>, thisYear)
    .map(row => Object.fromEntries(STATION_FIELDS.map(field => [field, row[field] ?? null])) as unknown as Station)
}
