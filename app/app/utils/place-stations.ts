import type { Point } from './map-tool'
import { distanceKm } from './map-tool'

// What a place found by its name (GH-3791) is used for: the closest station. A place is no station and has no measurements of its own, so the
// weather there is the weather of a station near it, and the reader is told which station, how far it is and how high it stands. Where no station
// is near, the app says so and names the nearest; a distant station is never stretched into the answer for a place.

/**
 * How far a station may be from a place for its weather to be called the place's, in kilometres: beyond it the app says there is no station near.
 *
 * 50 km is where the weather of two points stops being the same weather in most of the cases the questions ask about: a shower is 10 to 20 km
 * across, the temperature of a valley and of the ridge that is 50 km away differ by what the height says (about 6 K for 1000 m), and a coast
 * or a lee makes more. It is also about twice the spacing of DWD's stations in Germany (a station every 20 to 30 km), so a place in the
 * country has a station within it, and half the 100 km at which the map still offers a station for a click, which offers it as a station and
 * not as the place's weather.
 */
export const PLACE_REACH_KM = 50

/** How many of the stations near a place are listed */
export const NEAR_STATIONS_COUNT = 5

/** A station that has a position, and the height it stands at where it has one */
export interface PositionedStation {
  station_id: string
  name?: string | null
  latitude?: number | null
  longitude?: number | null
  elevation?: number | null
}

/** A station near a place: how far it is, and how much higher or lower it stands than the closest one (a place has no height of its own to compare with) */
export interface NearStation<S extends PositionedStation> {
  station: S
  distanceKm: number
  /** Metres above (positive) or below (negative) the closest station: null for the closest itself and where either has no height */
  heightDifference: number | null
}

/** The stations near a place, the closest first, at most `count`: the ones without a position have no distance and are left out */
export function stationsNear<S extends PositionedStation>(place: Point, stations: readonly S[], count = NEAR_STATIONS_COUNT): NearStation<S>[] {
  const placed = stations
    .filter((station): station is S & { latitude: number, longitude: number } => station.latitude != null && station.longitude != null)
    .map(station => ({ station, distanceKm: distanceKm(place, { latitude: station.latitude, longitude: station.longitude }) }))
    .sort((a, b) => a.distanceKm - b.distanceKm)
    .slice(0, count)
  const closest = placed[0]?.station.elevation
  return placed.map((near, index) => ({
    ...near,
    heightDifference: index === 0 || closest == null || near.station.elevation == null ? null : Math.round(near.station.elevation - closest),
  }))
}

/** Whether a station that far is the place's: within `PLACE_REACH_KM` */
export function withinReach(km: number): boolean {
  return km <= PLACE_REACH_KM
}

/** The station the place's weather is read at: the closest one, where it is within reach; none otherwise (the nearest is then told, not used) */
export function stationForPlace<S extends PositionedStation>(near: readonly NearStation<S>[]): NearStation<S> | null {
  const closest = near[0]
  return closest && withinReach(closest.distanceKm) ? closest : null
}
