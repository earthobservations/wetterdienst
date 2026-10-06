// Resolution values from backend wetterdienst/metadata/resolution.py
export type Resolution
  = '1_minute'
    | '5_minutes'
    | '6_minutes'
    | '10_minutes'
    | '15_minutes'
    | 'hourly'
    | '6_hour'
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

/** Per-network metadata in the coverage response */
export interface CoverageNetworkInfo {
  auth: boolean
  configured: boolean
  valid: boolean
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
  valid: boolean
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
  start_timestamp?: string
  end_timestamp?: string
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
  quality: number | null
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
  start_timestamp: string
  end_timestamp: string
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

export interface StripesMetadata {
  station: StripesStation
  resolution: string
  dataset: string
  parameter: string
}

export interface StripesValuesResponse {
  metadata: StripesMetadata
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

export interface ApiErrorResponse {
  detail: string
}
