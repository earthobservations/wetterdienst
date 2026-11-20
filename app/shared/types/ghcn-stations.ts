/**
 * The stations of NOAA GHCN daily as the app's server hands them to the map (`GET /api/map/ghcn-stations`, GH-4267): one
 * list for all of them (133k), as columns, which are about 5 times smaller than the backend's list of objects (44 MB) and
 * parse in a few milliseconds. Every column has `count` entries and the station `i` is the `i`-th of each.
 */
export interface GhcnStationColumns {
  /** The number of stations */
  count: number
  /** When the backend answered, which is when the list was made */
  retrieved_at: string | null
  station_id: string[]
  latitude: number[]
  longitude: number[]
  /** The year of the first value, null where the list gives none */
  first_year: Array<number | null>
  /** The year of the last value, null where the station has no end: it reports */
  last_year: Array<number | null>
  name: Array<string | null>
}
