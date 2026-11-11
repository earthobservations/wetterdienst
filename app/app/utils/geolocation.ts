import type { Point } from '~/utils/map-tool'

/**
 * The reader's own position (GH-3651): what the app does with it, apart from the browser's calls (the composable
 * `useMyLocation` owns those). The position is rounded to two decimals of a degree, about 1 km, before anything else
 * sees it: that is enough for the nearest station, and no more than a station needs. It is kept in the page's memory, and
 * in the browser's localStorage (`wd-location`) only where the reader ticks "remember".
 */

export const LOCATION_STORAGE_KEY = 'wd-location'

/** What the browser's `getCurrentPosition` is given: a coarse fix is enough, and a minute is long enough to wait for one */
export const POSITION_OPTIONS: PositionOptions = { enableHighAccuracy: false, timeout: 15_000, maximumAge: 60_000 }

/**
 * Why there is no position, as the page says it: the reader refused (or the browser blocks the site), there is no
 * Geolocation API, the device could not tell, or it took too long.
 */
export type LocationFailure = 'denied' | 'unsupported' | 'unavailable' | 'timeout'

/**
 * A coordinate to two decimals of a degree (about 1 km).
 *
 * @param degrees - A latitude or a longitude
 * @returns The degrees rounded to 0.01, with no negative zero
 * @example
 * roundCoordinate(53.55123) // 53.55
 */
export function roundCoordinate(degrees: number): number {
  const rounded = Math.round(degrees * 100) / 100
  return rounded === 0 ? 0 : rounded
}

/**
 * A position rounded before anything leaves the browser.
 *
 * @param point - The position the browser reported
 * @returns The same place to about 1 km
 */
export function roundPosition(point: Point): Point {
  return { latitude: roundCoordinate(point.latitude), longitude: roundCoordinate(point.longitude) }
}

/**
 * What the `GeolocationPositionError` code of the browser means for the page.
 *
 * @param code - 1 (permission denied), 2 (position unavailable) or 3 (timeout)
 * @returns The failure the page tells
 */
export function failureOfCode(code: number): LocationFailure {
  if (code === 1)
    return 'denied'
  if (code === 3)
    return 'timeout'
  return 'unavailable'
}

/** The position a storage holds, or null: anything but two finite coordinates within the globe is left out */
export function readRememberedPosition(): Point | null {
  try {
    const raw: unknown = JSON.parse(localStorage.getItem(LOCATION_STORAGE_KEY) ?? 'null')
    if (!raw || typeof raw !== 'object')
      return null
    const { latitude, longitude } = raw as Record<string, unknown>
    if (typeof latitude !== 'number' || typeof longitude !== 'number' || !Number.isFinite(latitude) || !Number.isFinite(longitude))
      return null
    if (Math.abs(latitude) > 90 || Math.abs(longitude) > 180)
      return null
    return roundPosition({ latitude, longitude })
  }
  catch {
    return null
  }
}

/** Remembers a position, already rounded; a storage that refuses is no failure: the position is then for this visit only */
export function writeRememberedPosition(point: Point): void {
  try {
    localStorage.setItem(LOCATION_STORAGE_KEY, JSON.stringify(roundPosition(point)))
  }
  catch {
    // kept in memory by the composable, which is all that can be done
  }
}

/** Forgets the remembered position */
export function forgetRememberedPosition(): void {
  try {
    localStorage.removeItem(LOCATION_STORAGE_KEY)
  }
  catch {
    // nothing was written that could be removed
  }
}
