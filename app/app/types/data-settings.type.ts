export interface DataSettings {
  humanize: boolean
  convertUnits: boolean
  unitTargets: Record<string, string>
  // Values-specific settings
  shape: 'long' | 'wide'
  skipEmpty: boolean
  skipThreshold: number
  skipCriteria: 'min' | 'mean' | 'max'
  dropNulls: boolean
  // Geo-specific settings
  useNearbyStationDistance: number
  /** Search radius (km) for parameters that vary slowly across a region, e.g. temperature. */
  stationDistanceHomogeneous: number
  /** Search radius (km) for parameters that decorrelate faster, e.g. precipitation. */
  stationDistanceHeterogeneous: number
  /** Per-parameter overrides of the two radii above, keyed by canonical parameter name. */
  useStationDistancePerParameter: Record<string, number>
  minGainOfValuePairs: number
  numAdditionalStations: number
}

/**
 * The backend's own radii. Kept here so a setting left untouched is not sent at all, which leaves
 * a server configured through `WD_TS_GEO_STATION_DISTANCE_*` to its own values.
 */
export const STATION_DISTANCE_DEFAULTS = {
  homogeneous: 40,
  heterogeneous: 20,
} as const
