import type { InterpolationSettings, ServerSettings, ValuesSettings } from '#shared/types/api'
import type { DataSettings } from '~/types/data-settings.type'
import { UNIT_TARGET_TYPES } from '~/utils/unit-targets'

function finite(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}

/**
 * A search radius as the server reports it. One it holds as infinite, written "Infinity", is kept
 * as such: the request leaves a radius that is no finite number out, and the server's then applies,
 * where the explorer's own 40 or 20 km would be sent in its place.
 */
function radius(value: unknown): number | undefined {
  if (value === 'Infinity')
    return Number.POSITIVE_INFINITY
  return finite(value) ? value : undefined
}

/**
 * The explorer's settings as `GET /api/settings` reports them: the `values` block's for the general
 * and values settings, the `interpolate` block's for the interpolation and summary ones, which the
 * `summarize` block reports alike, both being read from the same `WD_TS_GEO_*` variables.
 *
 * Only the settings the explorer holds one value for. Each is checked, as a backend of another
 * version may answer otherwise: one the answer lacks, or holds where the explorer can't (a nearby
 * station distance that is off or infinite), is left out, and the explorer keeps its own.
 */
export function serverDataSettings(server: ServerSettings): Partial<DataSettings> {
  const values: Partial<ValuesSettings> = server.values ?? {}
  const geo: Partial<InterpolationSettings> = server.interpolate ?? {}
  const settings: Partial<DataSettings> = {}
  if (typeof values.humanize === 'boolean')
    settings.humanize = values.humanize
  if (typeof values.convert_units === 'boolean')
    settings.convertUnits = values.convert_units
  if (values.shape === 'long' || values.shape === 'wide')
    settings.shape = values.shape
  if (typeof values.skip_empty === 'boolean')
    settings.skipEmpty = values.skip_empty
  if (finite(values.skip_threshold))
    settings.skipThreshold = values.skip_threshold
  if (values.skip_criteria === 'min' || values.skip_criteria === 'mean' || values.skip_criteria === 'max')
    settings.skipCriteria = values.skip_criteria
  if (typeof values.drop_nulls === 'boolean')
    settings.dropNulls = values.drop_nulls
  if (finite(geo.use_nearby_station_distance))
    settings.useNearbyStationDistance = geo.use_nearby_station_distance
  const homogeneous = radius(geo.interpolation_station_distance_homogeneous)
  if (homogeneous !== undefined)
    settings.stationDistanceHomogeneous = homogeneous
  const heterogeneous = radius(geo.interpolation_station_distance_heterogeneous)
  if (heterogeneous !== undefined)
    settings.stationDistanceHeterogeneous = heterogeneous
  if (finite(geo.min_gain_of_value_pairs))
    settings.minGainOfValuePairs = geo.min_gain_of_value_pairs
  if (finite(geo.num_additional_stations))
    settings.numAdditionalStations = geo.num_additional_stations
  return settings
}

/**
 * The unit each type the explorer lists comes in where the user leaves it at "Default": the
 * server's, as `GET /api/settings` reports it, else the listed one.
 */
export function defaultUnitTargets(server: ServerSettings | null): Record<string, string> {
  const reported: Record<string, unknown> = server?.values?.unit_targets ?? {}
  return Object.fromEntries(UNIT_TARGET_TYPES.map(({ type, default: listed }) => {
    const unit = reported[type]
    return [type, typeof unit === 'string' && unit.trim() !== '' ? unit : listed]
  }))
}
