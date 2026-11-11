export interface DataSettings {
  /**
   * What an Explorer link asks for where it differs from the app settings (GH-3878): the link's `humanize`, which the
   * request sends in place of the readable names setting. Left out, the app settings' choice is sent. The page makes
   * no such choice itself, and writes it to the address only where the link brought it.
   */
  humanize?: boolean
  /** As `humanize`: the link's `convertUnits`, in place of the app settings' convert units choice. */
  convertUnits?: boolean
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
 * wetterdienst's own radii, which the explorer starts from where the server does not report its
 * own (`GET /api/settings`, GH-2359).
 */
export const STATION_DISTANCE_DEFAULTS = {
  homogeneous: 40,
  heterogeneous: 20,
} as const
