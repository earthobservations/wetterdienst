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

// ============================================================================
// Coverage API
// ============================================================================

/**
 * Parameter info returned in coverage response, as the backend's `discover()` builds it: every key
 * but `lead_times` is always sent, and `unit` is the unit the source publishes in, not the one
 * values come back in
 */
export interface CoverageParameter {
  name: string
  name_original: string
  unit_type: string
  unit: string
  description: string | null
  /**
   * DWD DMO only: the lead times whose run carries the parameter. Values refuse a parameter asked
   * for by name that the requested run does not carry
   */
  lead_times?: Array<'short' | 'long'>
}

/**
 * A dataset in the coverage response, as `discover()` builds it: `description` is always sent,
 * null where the source has none
 */
export interface CoverageDataset {
  description: string | null
  parameters: CoverageParameter[]
  /** Where the stations of the dataset are: its own where they are fewer than its network's, else the network's */
  extent?: NetworkExtent
}

/**
 * A resolution in the coverage response, as `discover()` builds it: `description` is always sent,
 * null where the source has none
 */
export interface CoverageResolution {
  description: string | null
  datasets: Record<string, CoverageDataset>
}

/** One canonical parameter as `GET /api/glossary` returns it */
export interface GlossaryEntry {
  name: string
  unit_type: string
  unit: string
  unit_symbol: string
  description: string
}

/**
 * What a network is, as `GET /api/coverage` lists it: `observation`, `forecast` and `derived` are the
 * timeseries networks, which have stations and values, `radar` and `alerts` are standalone
 */
export type NetworkKind = 'observation' | 'forecast' | 'derived' | 'radar' | 'alerts'

/**
 * Per-network metadata in the coverage response. Whether the credentials are accepted is not part of
 * it (that is a request to the provider): `GET /api/auth` answers it for one network
 */
export interface CoverageNetworkInfo {
  name_short: string
  country: string
  kind: NetworkKind
  /** How far the network reaches; absent from a backend that predates it. The full extent is in `GET /api/providers` */
  scope?: NetworkExtent['scope']
  url: string
  auth: boolean
  configured: boolean
  date_required: boolean
}

/** Provider to networks mapping with per-network metadata */
export type CoverageResponse = Record<string, Record<string, CoverageNetworkInfo>>

/** Response from GET /api/auth */
export interface AuthResponse {
  provider: string
  network: string
  auth: boolean
  configured: boolean
  /** `null` when the credentials could not be checked: not a rejection, so unknown */
  valid: boolean | null
}

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
export interface Station {
  station_id: string
  /**
   * Null where the provider has no name for the station, e.g. dwd/derived climate_correction_factor, whose
   * stations are postcodes.
   */
  name: string | null
  /** Null where the provider reports no region for the station, which for several, e.g. DWD MOSMIX, is every one. */
  region: string | null
  /** Null where the provider has no position for the station, e.g. the postcodes of dwd/derived climate_correction_factor. */
  latitude: number | null
  /** Null together with `latitude`. */
  longitude: number | null
  /** Null where the provider reports no elevation for the station, which for several is every one. */
  elevation: number | null
  start_timestamp?: string | null
  end_timestamp?: string | null
}

export interface StationsResponse {
  stations: Station[]
}

export interface StationsQuery {
  provider: string
  network: string
  parameters: string // format: "resolution/dataset"
  all?: 'true' | 'false'
}

// ============================================================================
// Values API
// ============================================================================
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

/**
 * A radius, factor or gain: the server writes one it holds as infinite or NaN as the string
 * "Infinity" or "NaN", JSON having no number for it
 */
export type UnboundedNumber = number | 'Infinity' | 'NaN'

/** The settings each of `/api/values`, `/api/interpolate` and `/api/summarize` reports */
export interface AppliedSettings {
  humanize: boolean
  convert_units: boolean
  /** The unit values of each quantity come in, for every quantity the server converts */
  unit_targets: Record<string, string>
  skip_empty: boolean
  skip_threshold: number
  skip_criteria: 'min' | 'mean' | 'max'
  /** Off under the wide shape, the server's or the request's */
  drop_nulls: boolean
}

export interface ValuesSettings extends AppliedSettings {
  shape: 'long' | 'wide'
}

/** The settings `/api/interpolate` and `/api/summarize` share */
export interface GeoSettings extends AppliedSettings {
  min_gain_of_value_pairs: UnboundedNumber
  num_additional_stations: number
  /** The factor the heterogeneous radius is multiplied by, for every resolution */
  station_distance_resolution_factors: Record<string, UnboundedNumber>
}

export interface InterpolationSettings extends GeoSettings {
  use_nearby_station_distance: UnboundedNumber | null
  /** Radii (km) set per parameter by name; any other parameter takes one of the two below */
  interpolation_station_distance: Record<string, UnboundedNumber>
  interpolation_station_distance_homogeneous: UnboundedNumber
  interpolation_station_distance_heterogeneous: UnboundedNumber
}

export interface SummarySettings extends GeoSettings {
  /** Radii (km) set per parameter by name; any other parameter takes one of the two below */
  summary_station_distance: Record<string, UnboundedNumber>
  summary_station_distance_homogeneous: UnboundedNumber
  summary_station_distance_heterogeneous: UnboundedNumber
}

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

export interface StripesStation {
  station_id: string
  name: string
  region: string
  latitude: number
  longitude: number
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
export interface ProviderLicense {
  /** The SPDX identifier (or expression), null where the terms have none: `name` and `url` then tell them */
  spdx_id: string | null
  name: string
  url: string
}

/** A dataset of a resolution, with how many parameters it has */
export interface ProviderDataset {
  name: string
  parameters: number
  /** Only where the stations of the dataset are fewer than its network's; a dataset without it has its network's */
  extent?: NetworkExtent
}

/** A resolution of a network, with its datasets */
export interface ProviderResolution {
  name: Resolution
  datasets: ProviderDataset[]
}

/** Where the stations of a network are, which the country of its provider does not say */
export interface NetworkExtent {
  /** `global`: stations on at least five continents; `national`: one country, with its territories; `regional`: everything between */
  scope: 'global' | 'national' | 'regional'
  continents: Array<'africa' | 'antarctica' | 'asia' | 'europe' | 'north_america' | 'oceania' | 'south_america'>
  /** ISO 3166-1 alpha-2 codes, for a `regional` network where the list is short and exact: absent otherwise, and for `national` it is the provider's `country_code` */
  countries?: string[]
  /** `[west, south, east, north]` in degrees, around every station; not across the antimeridian */
  bbox: [number, number, number, number]
}

/** A network of a provider, as `GET /api/providers` lists it: standalone ones (`radar`, `alerts`) have no resolutions */
export interface ProviderNetwork {
  network: string
  kind: NetworkKind
  /** Absent from a backend that predates it */
  extent?: NetworkExtent
  /** Where the provider publishes the data of the network */
  url: string
  copyright: string
  /** Whether the network needs credentials; `GET /api/auth` tells whether they are accepted */
  auth: boolean
  date_required: boolean
  /** How many parameters the network has in all of its datasets */
  parameters: number
  resolutions: ProviderResolution[]
}

/** A provider of data, as `GET /api/providers` lists it */
export interface Provider {
  /** The name a request calls it by: `dwd` */
  provider: string
  /** The short name to write beside a flag: `DWD` */
  name_short: string
  name_local: string
  name_english: string
  country: string
  /** ISO 3166-1 alpha-2; null for a provider of several countries */
  country_code: string | null
  /** Null where the provider states no terms */
  license: ProviderLicense | null
  /** The credit line to give; null where the provider states none or asks for none */
  attribution: string | null
  networks: ProviderNetwork[]
}

/** The `metadata` block of an answer about the library: versions, time, producer, warnings and counts */
export interface ProvidersMetadata {
  api_version: string
  schema_version: string
  retrieved_at: string
  counts: { providers: number, networks: number, parameters: number }
  warnings: Array<{ code: string, message: string }>
}

/** Response from GET /api/providers */
export interface ProvidersResponse {
  metadata: ProvidersMetadata
  providers: Provider[]
}
