// The types of the backend's answers are derived from its OpenAPI document (GH-3908): `pnpm gen:api-types` writes the
// document's types to `.generated/api-schema.d.ts` (git-ignored, never committed; `pnpm typecheck` runs it first) from
// `tests/ui/openapi.snapshot.json`, so a change to the REST contract that the app does not follow fails its typecheck.
// The one answer the document types loosely, `/api/coverage` (one union for its two answers), is spelt here by the two
// types of its members, held to the document by a check of the type system (`Holds`), marked as such below.
import type { components, operations } from '../../.generated/api-schema'

type Schemas = components['schemas']

/**
 * The part of a schema the app depends on: `K` it reads (a rename, a removal or a new type of one fails the
 * typecheck), every other field of the schema optional. The fixtures of the tests and the mock backend need
 * not spell out a field nobody reads, and the document stays the one place that says what a field is.
 */
type Reads<T, K extends keyof T> = Pick<T, K> & Partial<Omit<T, K>>

/**
 * The resolutions of the backend's `Resolution` (wetterdienst/metadata/resolution.py), as the document lists them for a
 * network of `GET /api/providers`: the other fields of an answer that name a resolution are plain text in it
 */
export type Resolution = Schemas['ProviderResolution']['name']

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

/**
 * What `GET /api/coverage` answers is one object for either of its two answers, which the document types as a union of
 * the two: the networks of every provider (no query), or the resolutions of one network (`provider` and `network`)
 */
type CoverageAnswer = operations['coverage_api_coverage_get']['responses'][200]['content']['application/json']

// Spelt here, not derived: the document's one union for `/api/coverage` is not one of the two (`CoverageAnswerIsTheTwo`)
/** Provider to networks mapping with per-network metadata */
export type CoverageResponse = Record<string, Record<string, CoverageNetworkInfo>>

/** Response from GET /api/auth; `valid` is `null` when the credentials could not be checked: not a rejection, so unknown */
export type AuthResponse = Schemas['AuthAnswer']

// Spelt here, not derived: see `CoverageResponse`
/**
 * Detailed coverage for a provider-network pair: `discover()` sends only the resolutions the
 * network has, and leaves out one whose datasets are all filtered away, so any may be missing
 */
export type ProviderNetworkCoverageResponse = Partial<Record<Resolution, CoverageResolution>>

// Held to the document: what it has for a value of `/api/coverage` is the networks of a provider or the resolutions of
// a network and nothing else, so a third kind of member, or a change of either, fails the typecheck
export type CoverageAnswerIsTheTwo = Holds<Is<CoverageAnswer[string], Record<string, Schemas['CoverageNetwork']> | Schemas['CoverageResolution']>>

export type CoverageQuery = Query<'coverage_api_coverage_get'>

// ============================================================================
// Stations API
// ============================================================================
/** A station of the stations listing; the backend's rows carry more fields where the provider has them */
export type Station = Reads<Pick<Schemas['_Station'], 'station_id' | 'name' | 'region' | 'latitude' | 'longitude' | 'elevation' | 'start_timestamp' | 'end_timestamp'>, 'station_id' | 'name' | 'region' | 'latitude' | 'longitude' | 'elevation'>

/** The answer of `GET /api/stations` as far as the app reads it: its `metadata` block is not read */
export interface StationsResponse {
  stations: Station[]
}

export type StationsQuery = Query<'stations_api_stations_get'>

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
// Stripes API
// ============================================================================

export type StripesKind = operations['stripes_stations_api_stripes_stations_get']['parameters']['query']['kind']

/** A station of the stripes' listing, which is the one of `/api/stations`, as is the `series.station` of its values */
export type StripesStation = Station

/** The answer of `GET /api/stripes/stations` as far as the app reads it */
export type StripesStationsResponse = StationsResponse

export type StripesStationsQuery = Query<'stripes_stations_api_stripes_stations_get'>

export type StripesValueItem = Schemas['_StripesValue']

/** What the values of the stripes are of: the station, the parameter and the unit of `value` */
export type StripesSeries = Reads<Omit<Schemas['StripesSeries'], 'station'> & { station: StripesStation }, 'station' | 'resolution' | 'dataset' | 'parameter' | 'unit'>

/** The answer of `GET /api/stripes/values`, the `metadata` block every answer has (licence, resolved request, warnings, ...) not read */
export type StripesValuesResponse = Reads<Omit<Schemas['_StripesValuesWithMetadataDict'], 'series' | 'values'> & { series: StripesSeries, values: StripesValueItem[] }, 'series' | 'values'>

export type StripesValuesQuery = Query<'stripes_values_api_stripes_values_get'>

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
