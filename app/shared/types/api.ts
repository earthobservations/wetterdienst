// The types of the backend's answers are derived from its OpenAPI document (GH-3908): `pnpm gen:api-types` writes the
// document's types to `.generated/api-schema.d.ts` (git-ignored, never committed; `pnpm typecheck` runs it first) from
// `tests/ui/openapi.snapshot.json`, so a change to the REST contract that the app does not follow fails its typecheck.
// What the document does not describe -- the query objects the app builds, rows whose fields it leaves open (a
// station's history, a stripes station), the row of the data viewer -- is still hand-written, marked as such below.
import type { components } from '../../.generated/api-schema'

type Schemas = components['schemas']

/**
 * The part of a schema the app depends on: `K` it reads (a rename, a removal or a new type of one fails the
 * typecheck), every other field of the schema optional. The fixtures of the tests and the mock backend need
 * not spell out a field nobody reads, and the document stays the one place that says what a field is.
 */
type Reads<T, K extends keyof T> = Pick<T, K> & Partial<Omit<T, K>>

// Hand-written: the document types a resolution as a plain string.
// Resolution values from backend wetterdienst/metadata/resolution.py
export type Resolution
  = '1_minute'
    | '5_minutes'
    | '6_minutes'
    | '10_minutes'
    | '15_minutes'
    | 'hourly'
    | '6_hours'
    | 'subdaily'
    | 'daily'
    | 'monthly'
    | 'annual'

/**
 * What a value is relative to its interval, as the backend's `Aggregation` in
 * wetterdienst/metadata/parameter_table.py: a closed set, where `null` is "not stated"
 */
export type Aggregation = NonNullable<Schemas['CoverageParameter']['aggregation']>

/** Where a timestamp sits in the row's interval, as the backend's `TimestampPosition`: a closed set */
export type TimestampPosition = NonNullable<Schemas['CoverageParameter']['timestamp_position']>

// ============================================================================
// Coverage API
// ============================================================================

/** The closed set of the unit types a parameter has, as the document lists them */
export type UnitType = Schemas['CoverageParameter']['unit_type']

/**
 * Parameter info returned in coverage response, as the backend's `discover()` builds it. The app does not
 * read `unit`, `unit_source`, `aggregation` or `timestamp_position`
 */
export type CoverageParameter = Reads<Schemas['CoverageParameter'], 'name' | 'name_original' | 'unit_type' | 'description'>

/** A dataset in the coverage response, as `discover()` builds it */
export type CoverageDataset = Reads<Omit<Schemas['CoverageDataset'], 'parameters'> & { parameters: CoverageParameter[] }, 'description' | 'parameters'>

/** A resolution in the coverage response, as `discover()` builds it */
export type CoverageResolution = Reads<Omit<Schemas['CoverageResolution'], 'datasets'> & { datasets: Record<string, CoverageDataset> }, 'description' | 'datasets'>

/** One canonical parameter as `GET /api/glossary` returns it */
export type GlossaryEntry = Reads<Schemas['GlossaryEntry'], 'name' | 'unit_type' | 'unit' | 'unit_symbol' | 'description'>

/**
 * What a network is, as `GET /api/coverage` lists it: `observation`, `forecast` and `derived` are the
 * timeseries networks, which have stations and values, `radar` and `alerts` are standalone
 */
export type NetworkKind = Schemas['CoverageNetwork']['kind']

/**
 * Per-network metadata in the coverage response. Whether the credentials are accepted is not part of
 * it (that is a request to the provider): `GET /api/auth` answers it for one network
 */
export type CoverageNetworkInfo = Reads<Schemas['CoverageNetwork'], 'name_short' | 'country' | 'kind' | 'url' | 'auth' | 'configured' | 'date_required'>

/** Provider to networks mapping with per-network metadata */
export type CoverageResponse = Record<string, Record<string, CoverageNetworkInfo>>

/** Response from GET /api/auth; `valid` is `null` when the credentials could not be checked: not a rejection, so unknown */
export type AuthResponse = Schemas['AuthAnswer']

/**
 * Detailed coverage for a provider-network pair: `discover()` sends only the resolutions the
 * network has, and leaves out one whose datasets are all filtered away, so any may be missing
 */
export type ProviderNetworkCoverageResponse = Partial<Record<Resolution, CoverageResolution>>

export interface CoverageQuery {
  provider?: string
  network?: string
}

// ============================================================================
// Stations API
// ============================================================================
/** A station of the stations listing; the backend's rows carry more fields where the provider has them */
export type Station = Reads<Pick<Schemas['_Station'], 'station_id' | 'name' | 'region' | 'latitude' | 'longitude' | 'elevation' | 'start_timestamp' | 'end_timestamp'>, 'station_id' | 'name' | 'region' | 'latitude' | 'longitude' | 'elevation'>

/** The answer of `GET /api/stations` as far as the app reads it: its `metadata` block is not read */
export interface StationsResponse {
  stations: Station[]
}

// Hand-written, like every `...Query` below: what the app sends, which the document spells as parameters of an operation
export interface StationsQuery {
  provider: string
  network: string
  parameters: string // format: "resolution/dataset"
  all?: 'true' | 'false'
}

// ============================================================================
// Values API
// ============================================================================
// Hand-written: one row for every mode of the data viewer. The document types a row of `/api/values` (`_ValuesItemDict`, or
// the wide shape), of `/api/interpolate` and of `/api/summarize` apart, and the viewer reads the union of their fields
export interface Value {
  station_id: string
  resolution: string
  dataset: string
  parameter: string
  timestamp: string
  value: number | null
  // every flag the source publishes for the reading, comma-separated: the plain quality flag first, then
  // `kind:code` tokens (`G,measurement:T,source:7`); null where the provider publishes none
  quality_flags?: string | null
  taken_station_id?: string
  taken_station_ids?: string
}

export interface ValuesResponse {
  values: Value[]
}

export interface ValuesQuery {
  provider: string
  network: string
  parameters: string // format: "resolution/dataset/parameter,..."
  station: string // comma-separated station IDs
  timestamp?: string // format: "start" or "start/end"
  humanize?: boolean
  convert_units?: boolean
}

// ============================================================================
// Interpolate API
// ============================================================================

export interface InterpolateResponse {
  values: Value[]
}

export interface InterpolateQuery {
  provider: string
  network: string
  parameters: string
  latitude: number
  longitude: number
  /** Metres above sea level; the readings are brought to it before being used. */
  elevation?: number
  timestamp?: string
  humanize?: boolean
  convert_units?: boolean
}

// ============================================================================
// Summarize API
// ============================================================================

export interface SummarizeResponse {
  values: Value[]
}

export interface SummarizeQuery {
  provider: string
  network: string
  parameters: string
  latitude: number
  longitude: number
  /** Metres above sea level; the readings are brought to it before being used. */
  elevation?: number
  timestamp?: string
  humanize?: boolean
  convert_units?: boolean
}

// ============================================================================
// Settings API
// ============================================================================

/** The settings `/api/values` reports */
export type ValuesSettings = Reads<Schemas['ValuesSettings'], 'humanize' | 'convert_units' | 'unit_targets' | 'skip_empty' | 'skip_threshold' | 'skip_criteria' | 'drop_nulls' | 'shape'>

/**
 * The settings `/api/interpolate` reports (and `/api/summarize`, below): a radius, factor or gain the server holds as
 * infinite or NaN is the string "Infinity" or "NaN", JSON having no number for it
 */
export type InterpolationSettings = Reads<Schemas['InterpolationSettings'], 'humanize' | 'convert_units' | 'unit_targets' | 'skip_empty' | 'skip_threshold' | 'skip_criteria' | 'drop_nulls' | 'min_gain_of_value_pairs' | 'num_additional_stations' | 'station_distance_resolution_factors' | 'use_nearby_station_distance' | 'interpolation_station_distance' | 'interpolation_station_distance_homogeneous' | 'interpolation_station_distance_heterogeneous'>

/** The settings `/api/summarize` reports */
export type SummarySettings = Reads<Schemas['SummarySettings'], 'humanize' | 'convert_units' | 'unit_targets' | 'skip_empty' | 'skip_threshold' | 'skip_criteria' | 'drop_nulls' | 'min_gain_of_value_pairs' | 'num_additional_stations' | 'station_distance_resolution_factors' | 'summary_station_distance' | 'summary_station_distance_homogeneous' | 'summary_station_distance_heterogeneous'>

/**
 * Response from GET /api/settings: what each endpoint takes for a setting a request leaves out,
 * the server's `WD_TS_*` variables over wetterdienst's defaults
 */
export interface ServerSettings {
  values: ValuesSettings
  interpolate: InterpolationSettings
  summarize: SummarySettings
}

// ============================================================================
// Stripes API
// ============================================================================

export type StripesKind = 'temperature' | 'precipitation'

// Hand-written: the document leaves a stripes station's fields open (`series.station` is an object of any fields)
export interface StripesStation {
  station_id: string
  name: string
  region: string
  latitude: number
  longitude: number
  /** Null or left out where the station has none */
  elevation?: number | null
  start_timestamp: string | null
  end_timestamp: string | null
}

export interface StripesStationsResponse {
  stations: StripesStation[]
}

export interface StripesStationsQuery {
  kind: StripesKind
}

export interface StripesValueItem {
  timestamp: string | null
  value: number | null
}

/** What the values of the stripes are of: the station, the parameter and the unit of `value` */
export interface StripesSeries {
  station: StripesStation
  resolution: string
  dataset: string
  parameter: string
  unit: string
}

export interface StripesValuesResponse {
  /** The block every answer has (licence, resolved request, warnings, ...); the app reads nothing from it */
  metadata: Record<string, unknown>
  series: StripesSeries
  values: StripesValueItem[]
}

export interface StripesValuesQuery {
  kind: StripesKind
  station?: string
  name?: string
  format?: 'json' | 'csv'
  start_year?: number
  end_year?: number
  name_threshold?: number
}

// ============================================================================
// History API
// ============================================================================

// Hand-written: the document leaves a history's records open (`histories` is a list of objects of any fields).
// As `History` in the backend's model/history.py has them, every field of each record: the backend sends
// null for a field it has no value for, rather than leaving it out. A station's position, name and devices
// are records of the periods they held for, never fields of the history itself.

export interface HistoryStationName {
  station_id: string
  station_name: string
  valid_from: string
  valid_to: string | null
}

export interface HistoryOperatorName {
  station_id: string
  operator_name: string
  valid_from: string
  valid_to: string | null
}

export interface HistoryParameter {
  station_id: string
  valid_from: string
  valid_to: string
  station_name: string
  parameter: string
  description: string | null
  unit: string | null
  data_source: string | null
  extra_info: string | null
  special: string | null
  literature: string | null
}

export interface HistoryDevice {
  device_type: string | null
  station_id: string
  station_name: string | null
  longitude: number | null
  latitude: number | null
  station_elevation: number | null
  device_height: number | null
  valid_from: string
  valid_to: string
  method: string | null
}

export interface HistoryGeography {
  station_id: string
  station_elevation: number | null
  latitude: number | null
  longitude: number | null
  valid_from: string
  valid_to: string | null
  station_name: string | null
}

/** A summary or a period of missing data: the backend's two records have the same fields. */
export interface HistoryMissingData {
  station_id: string
  station_name: string | null
  parameter: string
  valid_from: string
  valid_to: string
  missing_count: number | null
  description: string | null
}

/** One station's history: the sections asked for, all of them where none were. */
export interface StationHistory {
  /** The station's id, spelt as in the stations listing: sent whatever sections were asked for. */
  station_id: string
  name?: { station: HistoryStationName[], operator: HistoryOperatorName[] }
  parameter?: HistoryParameter[]
  device?: HistoryDevice[]
  geography?: HistoryGeography[]
  missing_data?: { summary: HistoryMissingData[], periods: HistoryMissingData[] }
}

export interface HistoryResponse {
  histories: StationHistory[]
}

// ============================================================================
// Error Response
// ============================================================================

/**
 * An error, as the backend answers it: an RFC 9457 problem (`application/problem+json`).
 * `detail` is always text; `errors` lists the invalid parameters of a request that fails validation (422).
 */
// Hand-written: the app also builds this answer itself (its server routes), where the document's `Problem` requires
// `instance` and `request_id`
export interface ApiErrorResponse {
  type: string
  title: string
  status: number
  detail: string
  /** `urn:wetterdienst:request:<request_id>` */
  instance?: string
  /** The id of the request, also its `X-Request-ID` header: quote it when reporting a failure */
  request_id?: string
  errors?: { loc?: (string | number)[], msg?: string, type?: string }[]
}

// ============================================================================
// Providers API
// ============================================================================

/** The terms a provider publishes its data under, as `GET /api/providers` lists them */
export type ProviderLicense = Reads<Schemas['LicenseModel'], 'spdx_id' | 'name' | 'url'>

/** A dataset of a resolution, with how many parameters it has */
export type ProviderDataset = Reads<Omit<Schemas['ProviderDataset'], 'extent'> & { extent?: NetworkExtent }, 'name' | 'parameters'>

/** A resolution of a network, with its datasets: the app reads `name` as the `Resolution` it is */
export type ProviderResolution = Reads<Omit<Schemas['ProviderResolution'], 'name' | 'datasets'> & { name: Resolution, datasets: ProviderDataset[] }, 'name' | 'datasets'>

/** Where the stations of a network are, which the country of its provider does not say */
export type NetworkExtent = Reads<Schemas['Extent'], 'scope' | 'continents' | 'bbox'>

/**
 * A network of a provider, as `GET /api/providers?datasets=true` lists it: standalone ones (`radar`, `alerts`) have an
 * empty list. The backend's compact answer (`datasets=false`, which is to become its default) has `null`, so the app
 * asks with `datasets=true` and reads a missing list as an empty one.
 */
export type ProviderNetwork = Reads<Omit<Schemas['ProviderNetwork'], 'resolutions' | 'extent'> & { extent: NetworkExtent, resolutions: ProviderResolution[] | null }, 'network' | 'kind' | 'url' | 'copyright' | 'auth' | 'date_required' | 'parameters' | 'resolutions'>

/** A provider of data, as `GET /api/providers` lists it */
export type Provider = Reads<Omit<Schemas['Provider'], 'license' | 'networks'> & { license: ProviderLicense | null, networks: ProviderNetwork[] }, 'provider' | 'name_short' | 'name_local' | 'name_english' | 'country' | 'country_code' | 'license' | 'attribution' | 'networks'>

/** The `metadata` block of an answer about the library: versions, time, producer, warnings and counts */
export type ProvidersMetadata = Reads<Schemas['CatalogueMetadata'], 'api_version' | 'schema_version' | 'retrieved_at' | 'counts' | 'warnings'>

/** Response from GET /api/providers, as far as the app reads it */
export interface ProvidersResponse {
  metadata: ProvidersMetadata
  providers: Provider[]
}
