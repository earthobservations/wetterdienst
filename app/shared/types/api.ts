// The types of the backend's answers are derived from its OpenAPI document (GH-3908): `pnpm gen:api-types` writes the
// document's types to `.generated/api-schema.d.ts` (git-ignored, never committed; `pnpm typecheck` runs it first) from
// `tests/ui/openapi.snapshot.json`, so a change to the REST contract that the app does not follow fails its typecheck.
import type { components, operations } from '../../.generated/api-schema'

type Schemas = components['schemas']

/**
 * The part of a schema the app depends on: `K` it reads (a rename, a removal or a new type of one fails the
 * typecheck), every other field of the schema optional. The fixtures of the tests and the mock backend need
 * not spell out a field nobody reads, and the document stays the one place that says what a field is.
 */
type Reads<T, K extends keyof T> = Pick<T, K> & Partial<Omit<T, K>>

/**
 * The resolutions of the backend's `Resolution` (wetterdienst/metadata/resolution.py), as the document lists them: the
 * keys of the coverage of a network. The other fields of an answer that name a resolution are plain text in it
 */
export type Resolution = Schemas['Resolution']

/**
 * The query of an operation as the app sends it: what the document lists for it, with a list parameter (`parameters`,
 * `stations`) as one comma-separated text, which the API reads as it does the repeated parameter, and a mapping
 * (`unit_targets`) as its JSON text, which the API reads as the mapping
 */
type Query<Operation extends keyof operations>
  = CommaSeparated<NonNullable<operations[Operation]['parameters']['query']>>

type CommaSeparated<Q> = {
  [K in keyof Q]: NonNullable<Q[K]> extends unknown[]
    ? Exclude<Q[K], unknown[]> | string
    : NonNullable<Q[K]> extends Record<string, unknown> ? Q[K] | string : Q[K]
}

/** The check that a type is what the document says: it fails the typecheck, naming it, where the document differs */
type Holds<T extends true> = T

type Is<A, B> = [A] extends [B] ? ([B] extends [A] ? true : false) : false

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
 * What `GET /api/coverage` answers for one network: an object keyed by resolution, which the document types as
 * text keys (`Resolution` is the closed set of them), each holding that resolution's datasets
 */
type CoverageAnswer = operations['coverage_api_coverage_get']['responses'][200]['content']['application/json']
type CoverageResolutionSchema = CoverageAnswer[string]
type CoverageDatasetSchema = CoverageResolutionSchema['datasets'][string]
type CoverageParameterSchema = CoverageDatasetSchema['parameters'][number]

/**
 * Parameter info returned in coverage response, as the backend's `discover()` builds it. The app does not
 * read `unit`, `unit_source`, `aggregation` or `timestamp_position`
 */
export type CoverageParameter = Reads<CoverageParameterSchema, 'name' | 'name_original' | 'unit_type' | 'description'>

/** The schema `T` with the type of its member `K` as the app reads it: a `K` the document has not is a type error */
type With<T, K extends keyof T, V> = { [P in keyof T]: P extends K ? V : T[P] }

/** A dataset in the coverage response, its parameters as the app reads them */
export type CoverageDataset = Reads<With<CoverageDatasetSchema, 'parameters', CoverageParameter[]>, 'description' | 'parameters'>

/** A resolution in the coverage response, its datasets as the app reads them */
export type CoverageResolution = Reads<With<CoverageResolutionSchema, 'datasets', Record<string, CoverageDataset>>, 'description' | 'datasets'>

/** One canonical parameter as `GET /api/glossary` returns it */
export type GlossaryEntry = Reads<Schemas['GlossaryEntry'], 'name' | 'unit_type' | 'unit' | 'unit_symbol' | 'description'>

/**
 * What a network is, as `GET /api/providers` lists it: `observation`, `forecast` and `derived` are the
 * timeseries networks, which have stations and values, `radar` and `alerts` are standalone
 */
export type NetworkKind = Schemas['ProviderNetwork']['kind']

/** Response from GET /api/auth; `valid` is `null` when the credentials could not be checked: not a rejection, so unknown */
export type AuthResponse = Schemas['AuthAnswer']

/**
 * Coverage of one provider-network pair (`GET /api/coverage`, which needs both): the resolutions the network has, and
 * `discover()` leaves out one whose datasets are all filtered away, so any may be missing
 */
export type ProviderNetworkCoverageResponse = Partial<Record<Resolution, CoverageResolution>>

export type CoverageQuery = Query<'coverage_api_coverage_get'>

// ============================================================================
// Stations API
// ============================================================================
/** A station of the stations listing; the backend's rows carry more fields where the provider has them */
export type Station = Reads<Pick<Schemas['_Station'], 'station_id' | 'name' | 'region' | 'latitude' | 'longitude' | 'elevation' | 'wmo_id' | 'start_timestamp' | 'end_timestamp'>, 'station_id' | 'name' | 'region' | 'latitude' | 'longitude' | 'elevation'>

/** The answer of `GET /api/stations` as far as the app reads it: its `metadata` block is not read */
export interface StationsResponse {
  stations: Station[]
}

export type StationsQuery = Query<'stations_api_stations_get'>

/**
 * One station `GET /api/station-ids` found: the network and the list it comes from, the id the network numbers it by (`station_id`, what
 * `values` takes) and its WMO, WIGOS and ICAO ids where it has them. `matched_by` says which of them matched, `match` whether it was the
 * one asked for (`direct`) or an equivalent one
 */
export type StationIdsStation = Reads<Schemas['_StationIdsStation'], 'provider' | 'network' | 'resolution' | 'dataset' | 'station_id' | 'name' | 'latitude' | 'longitude' | 'matched_by' | 'match'>

/** The answer of `GET /api/station-ids` as far as the app reads it: the stations; its `metadata` block (what was searched, the warnings) is not read */
export interface StationIdsResponse {
  stations: StationIdsStation[]
}

/** The query of `GET /api/station-ids`: one or several WMO numbers, WIGOS identifiers or ICAO codes */
export type StationIdsQuery = Query<'station_ids_api_station_ids_get'>

// ============================================================================
// Values API
// ============================================================================
/**
 * One row for every mode of the data viewer, as the document types them: a row of `/api/values`, of
 * `/api/interpolate` and of `/api/summarize` are three types in it, and the viewer reads the union of their fields.
 * The fields every row has are required with their types, the others (a reading's `quality_flags`, an interpolation's
 * `taken_station_ids` and `distance_mean`, a summary's `taken_station_id` and `distance`) optional. The wide shape of
 * `/api/values` (one column per parameter) is not a row of it: the app asks for the long one.
 */
type LongRow = Schemas['_ValuesItemDict'] | Schemas['_InterpolatedValuesItemDict'] | Schemas['_SummarizedValuesItemDict']
type FieldsOfLongRows = { [K in KeysOf<LongRow>]: FieldOf<LongRow, K> }
type KeysOf<R> = R extends unknown ? keyof R : never
type FieldOf<R, K extends PropertyKey> = R extends unknown ? (K extends keyof R ? R[K] : never) : never

type CommonKeys = 'station_id' | 'resolution' | 'dataset' | 'parameter' | 'timestamp' | 'value'

export type Value = Reads<FieldsOfLongRows, CommonKeys>

// Held to the document: the fields required above are those every one of the three rows has
export type ValueKeysAreThoseOfEveryRow = Holds<Is<keyof Schemas['_ValuesItemDict'] & keyof Schemas['_InterpolatedValuesItemDict'] & keyof Schemas['_SummarizedValuesItemDict'], CommonKeys>>

/** The answer of `GET /api/values` as far as the app reads it: its rows are `Value`s, its `metadata` and `settings` are not read */
export type ValuesResponse = Reads<Omit<Schemas['_ValuesWithSettingsDict'], 'values'> & { values: Value[] }, 'values'>

export type ValuesQuery = Query<'values_api_values_get'>

// ============================================================================
// Interpolate API
// ============================================================================

/** The answer as far as the app reads it: its rows are `Value`s, its `metadata` and `settings` are not read */
export type InterpolateResponse = Reads<Omit<Schemas['_InterpolatedValuesWithSettingsDict'], 'values'> & { values: Value[] }, 'values'>

export type InterpolateQuery = Query<'interpolate_api_interpolate_get'>

// ============================================================================
// Summarize API
// ============================================================================

/** The answer as far as the app reads it: its rows are `Value`s, its `metadata` and `settings` are not read */
export type SummarizeResponse = Reads<Omit<Schemas['_SummarizedValuesWithSettingsDict'], 'values'> & { values: Value[] }, 'values'>

export type SummarizeQuery = Query<'summarize_api_summarize_get'>

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
// Stripes
// ============================================================================
// The climate stripes are the app's own (GH-4258): it reads the annual values from the generic API (`/api/stations`,
// `/api/values`) or, for NOAA's GHCN daily, from its own server (`/_ghcn/*`), and calculates the reference, the anomalies and
// the classes itself (`app/utils/stripes-scale.ts`, `app/utils/stripes-source.ts`). These types are therefore the app's, and
// no schema of the document: the backend has no stripes answer to derive them from.

export type StripesKind = 'temperature' | 'precipitation'

/** A station of the stripes' listing, which is the one of `/api/stations` */
export type StripesStation = Station

/** One year of the stripes: its value, its distance from the centre of the reference and its class, 0 (the lowest) to 15 */
export interface StripesValueItem {
  /** 1 January 00:00 UTC of the year */
  timestamp: string | null
  value: number | null
  anomaly: number | null
  stripe_class: number | null
}

/** One number of the reference, and which years it was calculated from */
export interface StripesReferenceStat {
  /** The mean (centre) or the standard deviation (spread), in the unit of the values */
  value: number
  first_year: number
  last_year: number
  /** How many years with data it was calculated from */
  years: number
  /** Whether the station has too few years with data in the period of the method and its whole record stands in for it */
  fallback: boolean
}

/** What the classes of the stripes are relative to: the mean of the centre, the standard deviation of the spread, the years each is calculated from and whether the whole record stood in for the period of the method */
export interface StripesReference {
  centre: StripesReferenceStat
  spread: StripesReferenceStat
  /** The scale reaches this many standard deviations to either side of the centre */
  range_sigma: number
  /** The number of classes, from the lowest value (0) to the highest */
  classes: number
}

/** What the values of the stripes are of: the station, the parameter and the unit of `value` */
export interface StripesSeries {
  station: Reads<Station, 'station_id' | 'name'>
  resolution: string
  dataset: string
  parameter: string
  /** The unit as it is written next to a number: the symbol the API names for the parameter (`°C`), or the name of the unit asked for where it names none */
  unit: string
  /** How a day of the temperature was calculated where the years were built from daily values (GHCN): the midrange of TMAX and TMIN, or TAVG at a station that has no day with both; null for DWD's own annual values and for the precipitation */
  method?: 'midrange' | 'tavg' | null
}

/** The provider block of an answer of the API: who published the data, under which licence, and the credit line */
export type StripesProvider = Schemas['ResponseMetadata']['provider']

/** The stripes of a station, as the app makes them from the annual values: the series, the reference and the years (`app/utils/stripes-source.ts`). Of the `metadata` of the values it was made from, the stripes' table file reads the provider's credit and licence (GH-4233) */
export interface StripesValuesResponse {
  metadata?: { provider?: Partial<StripesProvider> }
  series: StripesSeries
  values: StripesValueItem[]
  reference: StripesReference
  /**
   * Set where the years of GHCN daily were read from the mirror of NOAA's data on AWS (the backend's `source-fallback` warning, GH-4390),
   * which may end earlier than NOAA's own: the last year of the whole record that has a value (null if none), whatever window is shown
   */
  mirror?: { last_year: number | null }
}

/** One thing an answer of the API is missing, as the backend's `metadata.warnings` list it: a `code` that stays and a `message` that may improve */
export type ResponseWarning = Schemas['ResponseWarning']

/** The annual values of NOAA's GHCN daily that the app's own server calculates from the daily ones (`GET /_ghcn/annual`, `server/utils/ghcnStripes.ts`): a row for every year from the first to the last with a value, the value null for a year that fails the WMO rules */
export interface GhcnAnnualAnswer {
  metadata: {
    provider: StripesProvider
    /**
     * The warnings of the backend's answer for the station, as its generic API gives them (GH-4390): `source-fallback` says the days were
     * read from the mirror of NOAA's data on AWS because NCEI did not answer, and that the most recent days may be missing. Left out where there are none
     */
    warnings?: ResponseWarning[]
  }
  series: {
    station_id: string
    parameter: string
    /** The unit symbol the API names for the parameter (`°C`) */
    unit: string
    method: 'midrange' | 'tavg' | null
  }
  values: Array<{ timestamp: string, value: number | null }>
}

// ============================================================================
// History API
// ============================================================================

// As `History` in the backend's model/history.py has them, every field of each record: the backend sends null for a
// field it has no value for, rather than leaving it out. A station's position, name and devices are records of the
// periods they held for, never fields of the history itself.

export type HistoryStationName = Schemas['_HistoryStationName']

export type HistoryOperatorName = Schemas['_HistoryOperatorName']

export type HistoryParameter = Schemas['_HistoryParameter']

export type HistoryDevice = Schemas['_HistoryDevice']

export type HistoryGeography = Schemas['_HistoryGeography']

/** A summary or a period of missing data: the backend's two records have the same fields. */
export type HistoryMissingData = Schemas['_HistoryMissing']

/**
 * One station's history: the sections asked for, all of them where none were. `station_id` is the station's id, spelt
 * as in the stations listing, and sent whatever sections were asked for, as are `resolution` and `dataset`.
 */
export type StationHistory = Reads<Schemas['_HistoryEntry'], 'station_id'>

export type HistoryResponse = Reads<Omit<Schemas['_HistoryWithMetadataDict'], 'histories'> & { histories: StationHistory[] }, 'histories'>

// ============================================================================
// Error Response
// ============================================================================

/**
 * An error, as the backend answers it: an RFC 9457 problem (`application/problem+json`), the document's `Problem`.
 * `detail` is always text; `errors` lists the invalid parameters of a request that fails validation (422). The
 * app's own server routes answer it too, with the members of a problem they have: of the document's, the ones the
 * backend always sends (`instance`, `request_id`) are optional here.
 */
export type ApiErrorResponse = Reads<Schemas['Problem'], 'type' | 'title' | 'status' | 'detail'>

// ============================================================================
// Providers API
// ============================================================================

/** The terms a provider publishes its data under, as `GET /api/providers` lists them */
export type ProviderLicense = Reads<Schemas['LicenseModel'], 'spdx_id' | 'name' | 'url'>

/** Where the stations of a network are, which the country of its provider does not say */
export type NetworkExtent = Reads<Schemas['Extent'], 'scope' | 'continents' | 'bbox'>

/**
 * A network of a provider, as `GET /api/providers` lists it: what it is and where, not what it offers (its resolutions,
 * datasets and parameters are the coverage of that network). Standalone ones (`radar`, `alerts`) are listed too.
 */
export type ProviderNetwork = Reads<Omit<Schemas['ProviderNetwork'], 'extent'> & { extent: NetworkExtent }, 'network' | 'kind' | 'url' | 'copyright' | 'auth' | 'configured' | 'date_required' | 'parameters'>

/** A provider of data, as `GET /api/providers` lists it */
export type Provider = Reads<Omit<Schemas['Provider'], 'license' | 'networks'> & { license: ProviderLicense | null, networks: ProviderNetwork[] }, 'provider' | 'name_short' | 'name_local' | 'name_english' | 'country' | 'country_code' | 'license' | 'attribution' | 'networks'>

/** The `metadata` block of an answer about the library: versions, time, producer, warnings and counts */
export type ProvidersMetadata = Reads<Schemas['CatalogueMetadata'], 'api_version' | 'schema_version' | 'retrieved_at' | 'counts' | 'warnings'>

/** Response from GET /api/providers, as far as the app reads it */
export interface ProvidersResponse {
  metadata: ProvidersMetadata
  providers: Provider[]
}
