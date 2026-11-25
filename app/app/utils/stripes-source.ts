import type { GhcnAnnualAnswer, Station, StationsResponse, StripesKind, StripesValuesResponse, ValuesResponse } from '#shared/types/api'
import { API_FETCH } from './api-answer'
import { checkStripesWindow, isSuspect, stripesFromRecord, StripesRefusedError } from './stripes-scale'
import { unitSymbol } from './unit-targets'

/**
 * Where the climate stripes' stations and years come from, and how the app gets them (GH-4258). The backend's stripes routes are
 * not used any more (`/api/stripes/stations`, `/values`, `/image`): the app reads the annual values from the generic API and
 * calculates the reference, the anomalies and the classes itself (`stripes-scale.ts`).
 *
 * - DWD: the stations of `/api/stations` whose annual record can reach the years a scale needs, and the annual values of
 *   `/api/values` (`dwd/observation`, `annual/climate_summary` and `annual/precipitation_more`, the historical period).
 * - NOAA GHCN daily: NOAA publishes days only, so the app's own server builds the years from them by the WMO rules
 *   (`GET /_ghcn/annual`, `server/utils/ghcnAnnual.ts`) and lists the stations that have a record long enough
 *   (`GET /_ghcn/stations`, made of the backend's lists of each element, GH-4270), where a browser would have to read 20 to 50 MB of stations and up to 25 MB of days.
 */

export type StripesSource = 'dwd' | 'ghcn'

/** The code of the warning of the backend, passed on by the app's server, that says the days of GHCN daily came from the mirror of NOAA's data on AWS */
const SOURCE_FALLBACK = 'source-fallback'

/** Reads an address of the API or of the app's own server, and gives its JSON; a failure it throws, as `$fetch` does */
export type StripesFetch = <T>(url: string, options?: { query?: Record<string, string> }) => Promise<T>

/** `$fetch` with what every read of the API has (an answer that is no JSON is a failure, one retry of a transient one): what the pages give the functions below */
export const stripesFetch: StripesFetch = (url, options) => $fetch<never>(url, { ...options, ...API_FETCH })

/** The annual parameter of DWD's observations each kind of stripes is made of */
export const DWD_STRIPES_PARAMETER: Record<StripesKind, string> = {
  temperature: 'annual/climate_summary/temperature_air_mean_2m',
  precipitation: 'annual/precipitation_more/precipitation_amount',
}

/** The fewest years a station's record must span to be listed: the length of record the colour scale needs (`MIN_RECORD_YEARS`) */
export const MIN_SPAN_YEARS = 10

const DWD_NETWORK = { provider: 'dwd', network: 'observation' } as const

const yearOf = (timestamp: string): number => Number(timestamp.slice(0, 4))

/**
 * Whether the record of a station of DWD can reach `MIN_SPAN_YEARS`: the span its description gives from its first to its last
 * year, inclusive. The span is all the listing has: a record with gaps is listed where its span is long enough, and is still
 * refused where it has fewer years with values, which is only known by reading it. A station with no start or end date is kept.
 */
export function hasLongRecord(station: Pick<Station, 'start_timestamp' | 'end_timestamp'>): boolean {
  if (!station.start_timestamp || !station.end_timestamp)
    return true
  return yearOf(station.end_timestamp) - yearOf(station.start_timestamp) + 1 >= MIN_SPAN_YEARS
}

/**
 * The DWD stations that climate stripes are made for: those of the historical annual record whose span can reach
 * `MIN_SPAN_YEARS`, and that still report (they have a recent record), in the order of the listing.
 */
export async function fetchDwdStripesStations(fetch: StripesFetch, kind: StripesKind): Promise<Station[]> {
  const query = { ...DWD_NETWORK, parameters: DWD_STRIPES_PARAMETER[kind], all: 'true' }
  const [historical, recent] = await Promise.all([
    fetch<StationsResponse>('/api/stations', { query: { ...query, periods: 'historical' } }),
    fetch<StationsResponse>('/api/stations', { query: { ...query, periods: 'recent' } }),
  ])
  const active = new Set((recent.stations ?? []).map(station => station.station_id))
  return (historical.stations ?? []).filter(station => hasLongRecord(station) && active.has(station.station_id))
}

/** The stations that climate stripes are made for, of a source: the ones whose record is long enough and still reports */
export async function fetchStripesStations(fetch: StripesFetch, source: StripesSource, kind: StripesKind): Promise<Station[]> {
  if (source === 'ghcn')
    return (await fetch<StationsResponse>('/_ghcn/stations', { query: { kind } })).stations ?? []
  return fetchDwdStripesStations(fetch, kind)
}

/** What the stripes of a station are asked for */
export interface StripesRequest {
  source: StripesSource
  kind: StripesKind
  station: StripesValuesResponse['series']['station']
  /** The first and the last year to show; the classes are relative to the whole record whatever they are */
  startYear?: number | null
  endYear?: number | null
  /** The unit the values are returned in, as `/api/values` takes it: `{ temperature: 'degree_celsius' }` */
  unitTargets: Record<string, string>
}

/** The unit of a series: the symbol the API names for the parameter, else the one of the unit asked for */
function unitOf(request: StripesRequest, named: string | undefined): string {
  return named ?? unitSymbol(Object.values(request.unitTargets)[0] ?? '')
}

/**
 * The stripes of a station of DWD: its annual values from `/api/values`, a reading a plausibility check flagged left out.
 *
 * @throws {StripesRefusedError} No such station (404), or a record the stripes cannot be made of (400): see `stripesFromRecord`
 */
async function dwdStripes(fetch: StripesFetch, request: StripesRequest): Promise<StripesValuesResponse> {
  const parameter = DWD_STRIPES_PARAMETER[request.kind]
  const [resolution, dataset, name] = parameter.split('/') as [string, string, string]
  const stationId = request.station.station_id
  const answer = await fetch<ValuesResponse>('/api/values', {
    query: {
      ...DWD_NETWORK,
      parameters: parameter,
      periods: 'historical',
      stations: stationId,
      // fixed as the backend's stripes fixed them: one row for each reading, whatever the server's settings say
      shape: 'long',
      humanize: 'true',
      skip_empty: 'false',
      with_metadata: 'true',
      unit_targets: JSON.stringify(request.unitTargets),
    },
  })
  const metadata = answer.metadata
  if (metadata?.warnings?.some(warning => warning.code === 'unknown-station')) {
    // a lookup that went without a listing of DWD's server may only be missing the station: the backend's stripes answered a 502 for it
    // (`StationListingIncompleteError`), which is a failure to try again and never "no such station" (an outage is no absence of data)
    if (metadata.warnings.some(warning => warning.code === 'file-skipped'))
      throw new StripesRefusedError(502, `No station found for ${stationId}. The lookup of the stations went without a listing of the provider, so a station that only it lists is not found, and this may be one. Try again later.`)
    throw new StripesRefusedError(404, `No station with a station_id similar to '${stationId}' found`)
  }
  const record = (answer.values ?? []).map(row => ({ year: yearOf(row.timestamp), value: isSuspect(row.quality_flags) ? null : row.value }))
  const { values, reference } = stripesFromRecord(record, { stationId, startYear: request.startYear, endYear: request.endYear })
  return {
    ...(metadata?.provider ? { metadata: { provider: metadata.provider } } : {}),
    series: {
      station: request.station,
      resolution,
      dataset,
      parameter: name,
      unit: unitOf(request, metadata?.parameters?.find(item => item.name === name)?.unit),
      method: null,
    },
    values,
    reference,
  }
}

/**
 * The stripes of a station of GHCN daily: its annual values from the app's own server, which calculates them from the days.
 *
 * @throws {StripesRefusedError} A record the stripes cannot be made of (400): see `stripesFromRecord`
 */
async function ghcnStripes(fetch: StripesFetch, request: StripesRequest): Promise<StripesValuesResponse> {
  const stationId = request.station.station_id
  const answer = await fetch<GhcnAnnualAnswer>('/_ghcn/annual', {
    query: { kind: request.kind, station: stationId, unit_targets: JSON.stringify(request.unitTargets) },
  })
  const record = answer.values.map(row => ({ year: yearOf(row.timestamp), value: row.value }))
  // the days came from the mirror of NOAA's data on AWS, whose file may end early (GH-4390): the page says so, and where the record ends,
  // which is the whole record's last year with a value and not the window's
  const fromMirror = !!answer.metadata?.warnings?.some(warning => warning.code === SOURCE_FALLBACK)
  const yearsWithValue = record.filter(row => row.value !== null).map(row => row.year)
  const mirror = fromMirror ? { last_year: yearsWithValue.length ? Math.max(...yearsWithValue) : null } : undefined
  let made: ReturnType<typeof stripesFromRecord>
  try {
    made = stripesFromRecord(record, { stationId, startYear: request.startYear, endYear: request.endYear })
  }
  catch (refusal) {
    // a record too short may be the mirror's file ending early: the refusal says where it was read from
    if (refusal instanceof StripesRefusedError && mirror)
      refusal.mirror = mirror
    throw refusal
  }
  const { values, reference } = made
  return {
    ...(answer.metadata?.provider ? { metadata: { provider: answer.metadata.provider } } : {}),
    ...(mirror ? { mirror } : {}),
    series: {
      station: request.station,
      resolution: 'daily',
      dataset: 'data',
      parameter: answer.series.parameter,
      unit: unitOf(request, answer.series.unit),
      method: answer.series.method,
    },
    values,
    reference,
  }
}

/**
 * The stripes of a station: the years with their values, anomalies and classes, the reference the classes are relative to, and
 * what the series is of. A window whose end does not follow its start is refused before anything is read.
 *
 * @param fetch - Reads the API and the app's own server
 * @param request - The station, the kind, the source, the window and the unit
 * @throws {StripesRefusedError} The stripes cannot be made of the record (a 400, 404 or 422 as the API's own refusals), and whatever the reads fail with
 */
export async function fetchStripes(fetch: StripesFetch, request: StripesRequest): Promise<StripesValuesResponse> {
  checkStripesWindow(request.startYear, request.endYear)
  return request.source === 'ghcn' ? ghcnStripes(fetch, request) : dwdStripes(fetch, request)
}
