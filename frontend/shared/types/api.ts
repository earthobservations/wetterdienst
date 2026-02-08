// Resolution values from backend wetterdienst/metadata/resolution.py
export type Resolution
  = '1_minute'
    | '5_minutes'
    | '10_minutes'
    | '15_minutes'
    | 'hourly'
    | '6_hour'
    | 'subdaily'
    | 'daily'
    | 'monthly'
    | 'annual'
    | 'undefined'
    | 'dynamic'

// ============================================================================
// Coverage API
// ============================================================================

/** Parameter info returned in coverage response */
export interface CoverageParameter {
  name: string
  name_original?: string
  unit?: string
  unit_original?: string
}

/** Provider to networks mapping */
export type CoverageResponse = Record<string, string[]>

/** Detailed coverage for a provider-network pair */
export type ProviderNetworkCoverageResponse = Record<
  Resolution,
  Record<string, CoverageParameter[]>
>

export interface CoverageQuery {
  provider?: string
  network?: string
}

// ============================================================================
// Stations API
// ============================================================================
export interface Station {
  station_id: string
  name: string
  state: string
  latitude: number
  longitude: number
  height: number
  start_date?: string
  end_date?: string
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
  date: string
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
  date?: string // format: "start" or "start/end"
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
  date?: string
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
  date?: string
  humanize?: boolean
  convert_units?: boolean
}

// ============================================================================
// Stripes API
// ============================================================================

export type StripesKind = 'temperature' | 'precipitation'

export interface StripesStation {
  station_id: string
  name: string
  state: string
  latitude: number
  longitude: number
  start_date: string
  end_date: string
}

export interface StripesStationsResponse {
  stations: StripesStation[]
}

export interface StripesStationsQuery {
  kind: StripesKind
}

export interface StripesValueItem {
  date: string | null
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

export interface StripesImageQuery {
  kind: StripesKind
  station?: string
  name?: string
  format?: 'png' | 'jpg' | 'svg' | 'pdf'
  show_title?: boolean | string
  show_years?: boolean | string
  show_data_availability?: boolean | string
  start_year?: number
  end_year?: number
  dpi?: number
}

// ============================================================================
// Error Response
// ============================================================================

export interface ApiErrorResponse {
  detail: string
}
